from flask import Flask, render_template, request, send_file, redirect, url_for, flash, jsonify
import os
import uuid
import threading
import json
import queue
import requests
import io
import time
import logging
from datetime import datetime
from x_scraper import run_process, CONFIG_FILE

# Werkzeug loglarını filtrele (Sadece hataları göster, GET/POST isteklerini gizle)
log = logging.getLogger('werkzeug')
log.setLevel(logging.ERROR)

app = Flask(__name__)
app.secret_key = 'supersecretkey'

# Global storage
JOBS = {}
TEMP_FILES = {}

# Job Queue System
JOB_QUEUE = queue.Queue()
IS_WORKER_BUSY = False

def format_duration(seconds):
    """Saniyeyi okunabilir süre formatına çevirir (X dakika Y saniye)."""
    if not seconds:
        return "0 saniye"

    minutes = int(seconds // 60)
    secs = int(seconds % 60)

    if minutes > 0:
        return f"{minutes} dakika {secs} saniye"
    else:
        return f"{secs} saniye"

def worker_loop():
    global IS_WORKER_BUSY
    print("İşçi iş parçacığı başlatıldı...", flush=True)
    while True:
        try:
            # Blocking wait for next job
            job_id, kwargs = JOB_QUEUE.get()
            IS_WORKER_BUSY = True
            
            print(f"İş işleniyor {job_id}...", flush=True)
            
            if job_id in JOBS:
                JOBS[job_id]['status'] = 'running'
                
            try:
                job_type = kwargs.pop('job_type', 'scrape')
                
                if job_type == 'screenshot':
                    # Direct screenshot mode
                    links = kwargs.get('links', [])
                    print(f"İş {job_id}: {len(links)} ekran görüntüsü Node.js servisi aracılığıyla işleniyor...", flush=True)
                    try:
                        start_time_perf = time.time()
                        # Call Node.js service
                        # We are inside a thread, so this is synchronous blocking call which is fine
                        response = requests.post('http://localhost:3000/generate-word', json={'urls': links, 'jobId': job_id}, stream=True)
                        
                        if response.status_code == 200:
                            elapsed_time = time.time() - start_time_perf
                            formatted_time = format_duration(elapsed_time)
                            
                            # Save the file to memory
                            file_stream = io.BytesIO(response.content)
                            file_stream.seek(0)
                            
                            stats = {
                                "count": len(links),
                                "time": formatted_time,
                                "links": links,
                                "word_file": file_stream,
                                "job_type": 'screenshot'
                            }
                            JOBS[job_id]['status'] = 'completed'
                            JOBS[job_id]['result'] = stats
                            print(f"İş {job_id} tamamlandı (ekran görüntüleri).", flush=True)
                        else:
                            raise Exception(f"Node.js servisi hatası: {response.status_code} - {response.text}")
                            
                    except Exception as node_err:
                        print(f"İş {job_id} ekran görüntüsü hatası: {node_err}")
                        raise node_err
                
                else:
                    # Normal scrape mode
                    # This now uses the persistent driver in x_scraper
                    stats = run_process(**kwargs)
                    
                    if stats:
                        # x_scraper returns time as float in seconds, format it here
                        if 'time' in stats:
                            stats['time'] = format_duration(stats['time'])

                        stats['job_type'] = 'scrape'
                        JOBS[job_id]['status'] = 'completed'
                        JOBS[job_id]['result'] = stats
                        print(f"İş {job_id} tamamlandı.", flush=True)
                    else:
                        JOBS[job_id]['status'] = 'failed'
                        JOBS[job_id]['error'] = "İşlem başarısız oldu (Giriş hatası veya veri yok)."
                        print(f"İş {job_id} başarısız oldu (istatistik yok).", flush=True)
            except Exception as e:
                JOBS[job_id]['status'] = 'failed'
                JOBS[job_id]['error'] = str(e)
                print(f"İş {job_id} hatası: {e}", flush=True)
            finally:
                IS_WORKER_BUSY = False
                JOB_QUEUE.task_done()
                
        except Exception as e:
            print(f"İşçi döngüsü kritik hata: {e}", flush=True)
            IS_WORKER_BUSY = False

# Start worker thread
t = threading.Thread(target=worker_loop, daemon=True)
t.start()

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        auth_user = ""
        auth_pass = ""
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                    cfg = json.load(f)
                    auth_user = cfg.get("auth_username", "")
                    auth_pass = cfg.get("auth_password", "")
            except:
                pass
        
        if not auth_user or not auth_pass:
            error_msg = "Hata: Lütfen 'config.json' dosyasına kullanıcı adı ve şifrenizi girin."
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({'error': error_msg})
            flash(error_msg, "danger")
            return redirect(url_for('index'))

        scrape_mode = request.form.get('scrape_mode', 'profile')
        only_replies = request.form.get('only_replies') == 'true'
        target_username = request.form.get('target_username')
        search_keyword = request.form.get('search_keyword')
        start_date = request.form.get('start_date')
        end_date = request.form.get('end_date')
        start_time = request.form.get('start_time')
        end_time = request.form.get('end_time')

        job_id = str(uuid.uuid4())
        
        if scrape_mode == 'screenshot':
            direct_links_raw = request.form.get('direct_links', '')
            direct_links = [l.strip() for l in direct_links_raw.split('\n') if l.strip()]
            
            if not direct_links:
                error_msg = "Lütfen en az bir link girin."
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return jsonify({'error': error_msg})
                flash(error_msg, "danger")
                return redirect(url_for('index'))

            scrape_kwargs = {
                'job_type': 'screenshot',
                'links': direct_links
            }
        
        else:
            try:
                s_date_obj = datetime.strptime(start_date, '%Y-%m-%d')
                e_date_obj = datetime.strptime(end_date, '%Y-%m-%d')
                start_date_fmt = s_date_obj.strftime('%d-%m-%Y')
                end_date_fmt = e_date_obj.strftime('%d-%m-%Y')
            except (ValueError, TypeError):
                error_msg = "Tarih formatı hatalı veya eksik!"
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return jsonify({'error': error_msg})
                flash(error_msg, "danger")
                return redirect(url_for('index'))

            scrape_kwargs = {
                'job_type': 'scrape',
                'username': auth_user,
                'password': auth_pass,
                'target_username': target_username,
                'scrape_mode': scrape_mode,
                'only_replies': only_replies,
                'search_keyword': search_keyword,
                'start_date_str': start_date_fmt,
                'end_date_str': end_date_fmt,
                'start_time_str': start_time,
                'end_time_str': end_time,
                'output_file': None
            }
        
        # Initial status queued
        JOBS[job_id] = {'status': 'queued', 'result': None}
        
        print(f"İş sıraya alınıyor {job_id}", flush=True)
        JOB_QUEUE.put((job_id, scrape_kwargs))
        
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'job_id': job_id})
        
        return redirect(url_for('processing', job_id=job_id))

    return render_template('index.html')

@app.route('/processing/<job_id>')
def processing(job_id):
    if job_id not in JOBS:
        flash("Geçersiz işlem ID'si.", "danger")
        return redirect(url_for('index'))
    return render_template('processing.html', job_id=job_id)

@app.route('/status/<job_id>')
def job_status(job_id):
    if job_id not in JOBS:
        return {'status': 'not_found'}
    
    job = JOBS[job_id]

    response = {
        'status': job['status'],
        'redirect_url': url_for('show_result', job_id=job_id) if job['status'] == 'completed' else None,
        'message': job.get('error', '')
    }

    # Check for external progress file for screenshot jobs
    progress_file = os.path.join(os.getcwd(), 'temp', f'progress_{job_id}.json')
    if job['status'] == 'running' and os.path.exists(progress_file):
        try:
            with open(progress_file, 'r', encoding='utf-8') as f:
                progress_data = json.load(f)
                response['progress'] = progress_data
        except:
            pass

    return response

@app.route('/result/<job_id>')
def show_result(job_id):
    if job_id not in JOBS or JOBS[job_id]['status'] != 'completed':
        return redirect(url_for('index'))
    
    stats = JOBS[job_id]['result']
    if stats.get('excel_file'):
        TEMP_FILES[job_id] = stats['excel_file']
    
    if stats.get('word_file'):
        # For direct screenshot jobs
        TEMP_FILES[f"{job_id}_word"] = stats['word_file']
        
    return render_template('result.html', stats=stats, download_id=job_id)

@app.route('/download/<download_id>')
def download_file(download_id):
    if download_id in TEMP_FILES:
        file_obj = TEMP_FILES[download_id]
        file_obj.seek(0)
        
        # Detect if it's Excel or Word based on some logic or metadata? 
        # But wait, send_file with wrong mimetype might be an issue.
        # However, the user flow separates them usually.
        # But wait, `download_id` for Excel is just `job_id`. 
        # For Word generated later, we might need a different route or ID.
        
        # Let's peek at the file content or trust the route logic?
        # Actually, let's keep it simple. If it was stored as excel_file, it's excel.
        return send_file(
            file_obj, 
            as_attachment=True, 
            download_name=f"links_{download_id[:8]}.xlsx",
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
    elif f"{download_id}_word" in TEMP_FILES:
        # This handles the case where the primary output is a word file (screenshot mode)
        file_obj = TEMP_FILES[f"{download_id}_word"]
        file_obj.seek(0)
        return send_file(
            file_obj,
            as_attachment=True,
            download_name=f"report_{download_id[:8]}.docx",
            mimetype="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        )
    else:
        flash("Dosya bulunamadı veya süresi doldu.", "danger")
        return redirect(url_for('index'))

@app.route('/start_word_generation', methods=['POST'])
def start_word_generation():
    original_job_id = request.form.get('job_id')
    
    if not original_job_id or original_job_id not in JOBS:
        flash("Geçersiz işlem.", "danger")
        return redirect(url_for('index'))

    result = JOBS[original_job_id]['result']
    links = result.get('links', [])
    
    if not links:
        flash("Link bulunamadı.", "danger")
        return redirect(url_for('show_result', job_id=original_job_id))

    # Create a new job for screenshot generation
    new_job_id = str(uuid.uuid4())

    scrape_kwargs = {
        'job_type': 'screenshot',
        'links': links
    }

    JOBS[new_job_id] = {'status': 'queued', 'result': None}
    print(f"Ekran görüntüsü işi sıraya alınıyor {new_job_id}", flush=True)
    JOB_QUEUE.put((new_job_id, scrape_kwargs))

    return redirect(url_for('processing', job_id=new_job_id))

@app.route('/sw.js')
def service_worker():
    return send_file('static/sw.js', mimetype='application/javascript')

@app.route('/manifest.json')
def manifest():
    return send_file('static/manifest.json', mimetype='application/json')

@app.route('/apple-touch-icon.png')
@app.route('/apple-touch-icon-<path:filename>')
def apple_icon(filename=None):
    return send_file('static/icon-192.png', mimetype='image/png')

@app.route('/keep-alive')
def keep_alive():
    return "", 204

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False, threaded=True)
