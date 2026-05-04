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
from datetime import datetime, timedelta
import pandas as pd
import x_scraper
from x_scraper import run_process, CONFIG_FILE, request_stop
from db import init_db, get_db_connection
from werkzeug.security import check_password_hash, generate_password_hash

# Werkzeug loglarını filtrele (Sadece hataları göster, GET/POST isteklerini gizle)
log = logging.getLogger('werkzeug')
log.setLevel(logging.ERROR)

app = Flask(__name__)
app.secret_key = 'supersecretkey'

# Global debug flag
DEBUG_MODE = False

def load_debug_config():
    """Loads debug setting from config.json"""
    global DEBUG_MODE
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                cfg = json.load(f)
                DEBUG_MODE = cfg.get("debug", False)
                # Propagate to x_scraper
                x_scraper.DEBUG_MODE = DEBUG_MODE
        except:
            pass

def log_debug(message):
    """Prints message only if DEBUG_MODE is True."""
    if DEBUG_MODE:
        print(message, flush=True)

# Initial load of debug config
load_debug_config()

# Initialize Database
init_db()

# Scheduler Setup
from apscheduler.schedulers.background import BackgroundScheduler
from tasks import run_incremental_scraping, run_daily_verification
import atexit

# Global storage
JOBS = {}
TEMP_FILES = {}

# Job Queue System
JOB_QUEUE = queue.Queue()
IS_WORKER_BUSY = False

# Yalnızca ana süreçte (main thread) çalışmasını sağlamak için basit bir kontrol
if os.environ.get('WERKZEUG_RUN_MAIN') == 'true' or not app.debug:
    scheduler = BackgroundScheduler(daemon=True)
    # Concurrency lock for manual triggers
    MANUAL_SCRAPE_LOCK = threading.Lock()

    def locked_scheduled_scrape():
        if not MANUAL_SCRAPE_LOCK.locked() and not IS_WORKER_BUSY:
            with MANUAL_SCRAPE_LOCK:
                run_incremental_scraping()
        else:
            log_debug("Zamanlanmış tarama atlandı, çünkü aktif bir manuel tarama veya ana sayfa işi devam ediyor.")

    def locked_daily_verification():
        if not MANUAL_SCRAPE_LOCK.locked() and not IS_WORKER_BUSY:
            with MANUAL_SCRAPE_LOCK:
                run_daily_verification()
        else:
            log_debug("Günlük doğrulama atlandı, çünkü aktif bir manuel tarama veya ana sayfa işi devam ediyor.")

    def generate_cron_hours(start_hour, interval_hours):
        hours = []
        current_hour = start_hour
        for _ in range(24):
            if current_hour not in hours:
                hours.append(current_hour)
            current_hour = (current_hour + interval_hours) % 24
            if current_hour == start_hour:
                break
        return ','.join(map(str, sorted(hours)))

    def apply_scheduler_settings():
        # Her hedefin kendi interval_minutes değerine göre tam vaktinde çalışması için
        # her 1 dakikada bir kontrol eden genel bir görev ekliyoruz. (cron minute='*')

        # Remove existing jobs if any
        if scheduler.get_job('incremental_scrape_job'):
            scheduler.remove_job('incremental_scrape_job')
        if scheduler.get_job('daily_verification_job'):
            scheduler.remove_job('daily_verification_job')

        # Add polling job (every minute)
        scheduler.add_job(locked_scheduled_scrape, 'cron', minute='*', id='incremental_scrape_job')

        # Add daily verification job (every day at 00:05)
        scheduler.add_job(locked_daily_verification, 'cron', hour=0, minute=5, id='daily_verification_job')

        print(f"Scheduler updated: Polling for due targets every minute. Daily verification set to 00:05.", flush=True)

    # Initial apply
    apply_scheduler_settings()
    scheduler.start()

    # Store globally to allow updating from routes
    app.apply_scheduler_settings = apply_scheduler_settings

    # Uygulama kapandığında scheduler'ı durdur
    atexit.register(lambda: scheduler.shutdown(wait=False))

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
    log_debug("İşçi iş parçacığı başlatıldı...")
    while True:
        try:
            # Blocking wait for next job
            job_id, kwargs = JOB_QUEUE.get()
            IS_WORKER_BUSY = True
            
            log_debug(f"İş işleniyor {job_id}...")
            
            if job_id in JOBS:
                JOBS[job_id]['status'] = 'running'
                
            try:
                job_type = kwargs.pop('job_type', 'scrape')
                
                if job_type == 'screenshot':
                    # Direct screenshot mode
                    links = kwargs.get('links', [])
                    log_debug(f"İş {job_id}: {len(links)} ekran görüntüsü Node.js servisi aracılığıyla işleniyor...")
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
                            log_debug(f"İş {job_id} tamamlandı (ekran görüntüleri).")
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
                        log_debug(f"İş {job_id} tamamlandı.")
                    else:
                        JOBS[job_id]['status'] = 'failed'
                        JOBS[job_id]['error'] = "İşlem başarısız oldu (Giriş hatası veya veri yok)."
                        log_debug(f"İş {job_id} başarısız oldu (istatistik yok).")
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

from functools import wraps
from flask import session

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'admin_logged_in' not in session:
            flash('Bu sayfaya erişmek için giriş yapmalısınız.', 'danger')
            return redirect(url_for('admin_login'))
        return f(*args, **kwargs)
    return decorated_function

# --- ADMIN ROUTES ---

@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')

        conn = get_db_connection()
        if conn:
            try:
                with conn.cursor() as cursor:
                    cursor.execute("SELECT * FROM admin_users WHERE username = %s", (username,))
                    user = cursor.fetchone()

                    if user and check_password_hash(user['password_hash'], password):
                        session['admin_logged_in'] = True
                        session['admin_username'] = user['username']
                        return redirect(url_for('admin_dashboard'))
                    else:
                        flash('Hatalı kullanıcı adı veya şifre.', 'danger')
            finally:
                conn.close()
        else:
            flash('Veritabanı bağlantı hatası.', 'danger')

    return render_template('admin/login.html')

@app.route('/admin/logout')
def admin_logout():
    session.pop('admin_logged_in', None)
    session.pop('admin_username', None)
    return redirect(url_for('admin_login'))

@app.route('/admin/trigger_scrape', methods=['POST'])
@admin_required
def admin_trigger_scrape():
    global MANUAL_SCRAPE_LOCK, IS_WORKER_BUSY
    if MANUAL_SCRAPE_LOCK.locked() or IS_WORKER_BUSY:
        flash('Şu anda aktif veya arka planda devam eden bir tarama işlemi var. Lütfen bitmesini bekleyin.', 'warning')
        return redirect(url_for('admin_dashboard'))

    def locked_scrape():
        with MANUAL_SCRAPE_LOCK:
            run_incremental_scraping(force_scrape=True)

    # Run the scraping task in a separate background thread so it doesn't block the UI
    scrape_thread = threading.Thread(target=locked_scrape, daemon=True)
    scrape_thread.start()
    flash('Arka planda tarama işlemi başlatıldı! (Tüm Hedefler)', 'success')
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/trigger_scrape/<int:target_id>', methods=['POST'])
@admin_required
def admin_trigger_scrape_target(target_id):
    global MANUAL_SCRAPE_LOCK, IS_WORKER_BUSY
    if MANUAL_SCRAPE_LOCK.locked() or IS_WORKER_BUSY:
        flash('Şu anda aktif veya arka planda devam eden bir tarama işlemi var. Lütfen bitmesini bekleyin.', 'warning')
        # Try to redirect back to target view if possible
        referer = request.headers.get("Referer")
        if referer and "target/" in referer:
            return redirect(url_for('admin_view_target', target_id=target_id))
        return redirect(url_for('admin_dashboard'))

    def locked_scrape_target():
        with MANUAL_SCRAPE_LOCK:
            run_incremental_scraping(specific_target_id=target_id, force_scrape=True)

    scrape_thread = threading.Thread(target=locked_scrape_target, daemon=True)
    scrape_thread.start()
    flash('Bu hedef için tarama arka planda başlatıldı!', 'success')

    referer = request.headers.get("Referer")
    if referer and "target/" in referer:
        return redirect(url_for('admin_view_target', target_id=target_id))
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/update_settings', methods=['POST'])
@admin_required
def admin_update_settings():
    start_hour = request.form.get('start_hour', type=int, default=0)
    interval_hours = request.form.get('interval_hours', type=int, default=6)
    new_password = request.form.get('new_password')

    if start_hour < 0 or start_hour > 23:
        flash('Başlangıç saati 0-23 arasında olmalıdır.', 'danger')
        return redirect(url_for('admin_dashboard'))

    if interval_hours < 1 or interval_hours > 24:
        flash('Tarama sıklığı 1-24 saat arasında olmalıdır.', 'danger')
        return redirect(url_for('admin_dashboard'))

    conn = get_db_connection()
    if conn:
        try:
            with conn.cursor() as cursor:
                # Update scheduler settings
                cursor.execute("SELECT COUNT(*) as count FROM settings")
                result = cursor.fetchone()
                if result['count'] == 0:
                    cursor.execute("INSERT INTO settings (start_hour, interval_hours) VALUES (%s, %s)", (start_hour, interval_hours))
                else:
                    cursor.execute("UPDATE settings SET start_hour = %s, interval_hours = %s", (start_hour, interval_hours))

                # Check and update password if provided
                if new_password:
                    if len(new_password) < 4:
                        flash('Şifre en az 4 karakter olmalıdır.', 'danger')
                    else:
                        username = session.get('admin_username')
                        new_hash = generate_password_hash(new_password)
                        cursor.execute("UPDATE admin_users SET password_hash = %s WHERE username = %s", (new_hash, username))
                        flash('Şifreniz de başarıyla güncellendi.', 'success')

            conn.commit()
            flash('Zamanlama ayarları başarıyla kaydedildi.', 'success')

            # Update scheduler dynamically
            if hasattr(app, 'apply_scheduler_settings'):
                app.apply_scheduler_settings()

        except Exception as e:
            flash(f'Hata oluştu: {e}', 'danger')
        finally:
            conn.close()

    return redirect(url_for('admin_dashboard'))

@app.route('/admin')
@admin_required
def admin_dashboard():
    targets = []
    settings = {'start_hour': 0, 'interval_hours': 6}
    conn = get_db_connection()
    if conn:
        try:
            with conn.cursor() as cursor:
                # Get settings
                cursor.execute("SELECT start_hour, interval_hours FROM settings ORDER BY id DESC LIMIT 1")
                db_settings = cursor.fetchone()
                if db_settings:
                    settings = db_settings

                # Get targets and their tweet counts
                cursor.execute("""
                    SELECT t.id, t.target_name, t.target_type, t.scrape_interval_minutes, t.last_scraped_at, t.next_scrape_at, COUNT(tw.id) as tweet_count
                    FROM targets t
                    LEFT JOIN tweets tw ON t.id = tw.target_id
                    GROUP BY t.id
                """)
                targets = cursor.fetchall()
        finally:
            conn.close()

    return render_template('admin/dashboard.html', targets=targets, settings=settings)

def parse_next_scrape_time(time_str):
    if not time_str:
        return None
    try:
        hour, minute = map(int, time_str.split(':'))
        now = datetime.now()
        target_time = now.replace(hour=hour, minute=minute, second=0, microsecond=0)

        # If the specified time has already passed today, schedule it for tomorrow
        if target_time <= now:
            target_time += timedelta(days=1)

        return target_time.strftime('%Y-%m-%d %H:%M:%S')
    except Exception as e:
        print(f"Error parsing time: {e}")
        return None

@app.route('/admin/target/add', methods=['POST'])
@admin_required
def admin_add_target():
    target_name = request.form.get('target_name')
    target_type = request.form.get('target_type')
    scrape_interval_minutes = request.form.get('scrape_interval_minutes', 60, type=int)
    next_scrape_time_str = request.form.get('next_scrape_time')

    next_scrape_at = parse_next_scrape_time(next_scrape_time_str)

    if target_name and target_type in ['user', 'list']:
        conn = get_db_connection()
        if conn:
            try:
                with conn.cursor() as cursor:
                    cursor.execute(
                        "INSERT INTO targets (target_name, target_type, scrape_interval_minutes, next_scrape_at) VALUES (%s, %s, %s, %s)",
                        (target_name, target_type, scrape_interval_minutes, next_scrape_at)
                    )
                conn.commit()
                flash('Hedef başarıyla eklendi.', 'success')
            except Exception as e:
                flash(f'Hata oluştu: {e}', 'danger')
            finally:
                conn.close()
    else:
        flash('Geçersiz veri.', 'danger')

    return redirect(url_for('admin_dashboard'))

@app.route('/admin/target/edit_interval/<int:target_id>', methods=['POST'])
@admin_required
def admin_edit_target_interval(target_id):
    scrape_interval_minutes = request.form.get('scrape_interval_minutes', type=int)
    next_scrape_time_str = request.form.get('next_scrape_time')
    excel_file = request.files.get('excel_file')

    next_scrape_at = parse_next_scrape_time(next_scrape_time_str)

    if scrape_interval_minutes and scrape_interval_minutes > 0:
        conn = get_db_connection()
        if conn:
            try:
                with conn.cursor() as cursor:
                    cursor.execute("SELECT target_name, target_type FROM targets WHERE id = %s", (target_id,))
                    target = cursor.fetchone()
                    if not target:
                        flash('Hedef bulunamadı.', 'danger')
                        return redirect(url_for('admin_dashboard'))

                    target_name = target['target_name']
                    target_type = target['target_type']

                    if excel_file and excel_file.filename:
                        if target_type == 'list':
                            flash('Liste tipi hedefler için Excel yüklemesi desteklenmemektedir.', 'danger')
                            return redirect(url_for('admin_dashboard'))

                        try:
                            df = pd.read_excel(excel_file)
                            if not all(col in df.columns for col in ['Date', 'Link', 'Username']):
                                flash('Yüklenen Excel dosyasında Date, Link ve Username sütunları eksik.', 'danger')
                                return redirect(url_for('admin_dashboard'))

                            # Kullanıcı adını doğrula (Excel'de hedefin adı en az 1 kere var mı)
                            df['Username'] = df['Username'].astype(str)
                            clean_target_name = target_name.replace('@', '').lower().strip()
                            clean_usernames = df['Username'].str.replace('@', '').str.lower().str.strip()

                            if not (clean_usernames == clean_target_name).any():
                                flash(f'Yüklenen Excel dosyasında hedef kullanıcı "{target_name}" ile eşleşen bir Username bulunamadı.', 'danger')
                                return redirect(url_for('admin_dashboard'))

                            new_tweets_added = 0
                            for index, row in df.iterrows():
                                tweet_date = row['Date']
                                link = row['Link']
                                username = row['Username']

                                if pd.isna(link) or pd.isna(tweet_date):
                                    continue

                                if isinstance(tweet_date, str):
                                    try:
                                        tweet_date = datetime.strptime(tweet_date, "%Y-%m-%d %H:%M:%S")
                                    except ValueError:
                                        try:
                                            # handle other possible formats if necessary, or pass
                                            tweet_date = pd.to_datetime(tweet_date).to_pydatetime()
                                        except:
                                            pass

                                # Sadece datetime olanları veya parse edilebilenleri ekle
                                if pd.notna(tweet_date):
                                    try:
                                        cursor.execute("""
                                            INSERT IGNORE INTO tweets (target_id, tweet_date, link, username)
                                            VALUES (%s, %s, %s, %s)
                                        """, (target_id, tweet_date, str(link), str(username)))
                                        if cursor.rowcount > 0:
                                            new_tweets_added += 1
                                    except Exception as e:
                                        print(f"Excel import error for link {link}: {e}")

                            conn.commit()
                            flash(f'Tarama sıklığı güncellendi ve Excel dosyasından {new_tweets_added} yeni kayıt eklendi.', 'success')

                        except Exception as e:
                            flash(f'Excel işlenirken hata oluştu: {e}', 'danger')
                            return redirect(url_for('admin_dashboard'))
                    else:
                        flash('Tarama sıklığı/zamanı başarıyla güncellendi.', 'success')

                    if next_scrape_at:
                        cursor.execute(
                            "UPDATE targets SET scrape_interval_minutes = %s, next_scrape_at = %s WHERE id = %s",
                            (scrape_interval_minutes, next_scrape_at, target_id)
                        )
                    else:
                        cursor.execute(
                            "UPDATE targets SET scrape_interval_minutes = %s WHERE id = %s",
                            (scrape_interval_minutes, target_id)
                        )
                conn.commit()
            except Exception as e:
                flash(f'Hata oluştu: {e}', 'danger')
            finally:
                conn.close()
    else:
        flash('Geçersiz dakika değeri.', 'danger')

    return redirect(url_for('admin_dashboard'))

@app.route('/admin/target/delete/<int:target_id>', methods=['POST'])
@admin_required
def admin_delete_target(target_id):
    conn = get_db_connection()
    if conn:
        try:
            with conn.cursor() as cursor:
                cursor.execute("DELETE FROM targets WHERE id = %s", (target_id,))
            conn.commit()
            flash('Hedef ve ona bağlı tweetler silindi.', 'success')
        except Exception as e:
            flash(f'Hata oluştu: {e}', 'danger')
        finally:
            conn.close()

    return redirect(url_for('admin_dashboard'))

@app.route('/admin/target/<int:target_id>')
@admin_required
def admin_view_target(target_id):
    target = None
    tweets = []

    conn = get_db_connection()
    if conn:
        try:
            with conn.cursor() as cursor:
                cursor.execute("SELECT * FROM targets WHERE id = %s", (target_id,))
                target = cursor.fetchone()

                if target:
                    cursor.execute("SELECT * FROM tweets WHERE target_id = %s ORDER BY tweet_date DESC", (target_id,))
                    tweets = cursor.fetchall()
        finally:
            conn.close()

    if not target:
        flash('Hedef bulunamadı.', 'danger')
        return redirect(url_for('admin_dashboard'))

    return render_template('admin/target_tweets.html', target=target, tweets=tweets)

@app.route('/admin/target/<int:target_id>/delete_tweets', methods=['POST'])
@admin_required
def admin_delete_all_target_tweets(target_id):
    conn = get_db_connection()
    if conn:
        try:
            with conn.cursor() as cursor:
                cursor.execute("DELETE FROM tweets WHERE target_id = %s", (target_id,))
            conn.commit()
            flash('Hedefin tüm tweetleri başarıyla silindi.', 'success')
        except Exception as e:
            flash(f'Hata oluştu: {e}', 'danger')
        finally:
            conn.close()

    return redirect(url_for('admin_view_target', target_id=target_id))

@app.route('/admin/tweet/delete_selected', methods=['POST'])
@admin_required
def admin_delete_selected_tweets():
    target_id = request.form.get('target_id')
    tweet_ids_str = request.form.get('tweet_ids')

    if not tweet_ids_str:
        flash('Silinecek link seçilmedi.', 'warning')
        return redirect(url_for('admin_view_target', target_id=target_id) if target_id else url_for('admin_dashboard'))

    # Parse and validate the IDs
    try:
        tweet_ids = [int(i.strip()) for i in tweet_ids_str.split(',') if i.strip()]
    except ValueError:
        flash('Geçersiz veri biçimi.', 'danger')
        return redirect(url_for('admin_view_target', target_id=target_id) if target_id else url_for('admin_dashboard'))

    if not tweet_ids:
        flash('Silinecek geçerli link bulunamadı.', 'warning')
        return redirect(url_for('admin_view_target', target_id=target_id) if target_id else url_for('admin_dashboard'))

    conn = get_db_connection()
    if conn:
        try:
            with conn.cursor() as cursor:
                # Use parameter expansion for IN clause
                format_strings = ','.join(['%s'] * len(tweet_ids))
                cursor.execute(f"DELETE FROM tweets WHERE id IN ({format_strings})", tuple(tweet_ids))
            conn.commit()
            flash(f'{len(tweet_ids)} adet link başarıyla silindi.', 'success')
        except Exception as e:
            flash(f'Hata oluştu: {e}', 'danger')
        finally:
            conn.close()

    if target_id:
        return redirect(url_for('admin_view_target', target_id=target_id))
    return redirect(url_for('admin_dashboard'))


@app.route('/admin/tweet/delete/<int:tweet_id>', methods=['POST'])
@admin_required
def admin_delete_single_tweet(tweet_id):
    target_id = request.form.get('target_id')
    conn = get_db_connection()
    if conn:
        try:
            with conn.cursor() as cursor:
                cursor.execute("DELETE FROM tweets WHERE id = %s", (tweet_id,))
            conn.commit()
            flash('Seçili link başarıyla silindi.', 'success')
        except Exception as e:
            flash(f'Hata oluştu: {e}', 'danger')
        finally:
            conn.close()

    if target_id:
        return redirect(url_for('admin_view_target', target_id=target_id))
    return redirect(url_for('admin_dashboard'))


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
        content_filter = request.form.get('content_filter', 'none')
        only_replies = content_filter == 'only_replies'
        include_retweets = content_filter == 'include_retweets'
        only_retweets = content_filter == 'only_retweets'
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
                'include_retweets': include_retweets,
                'only_retweets': only_retweets,
                'search_keyword': search_keyword,
                'start_date_str': start_date_fmt,
                'end_date_str': end_date_fmt,
                'start_time_str': start_time,
                'end_time_str': end_time,
                'output_file': None
            }
        
        # Initial status queued
        JOBS[job_id] = {'status': 'queued', 'result': None}
        
        log_debug(f"İş sıraya alınıyor {job_id}")
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
    log_debug(f"Ekran görüntüsü işi sıraya alınıyor {new_job_id}")
    JOB_QUEUE.put((new_job_id, scrape_kwargs))

    return redirect(url_for('processing', job_id=new_job_id))

@app.route('/cancel/<job_id>', methods=['POST'])
def cancel_job(job_id):
    if job_id not in JOBS:
        return jsonify({'success': False, 'message': 'İşlem bulunamadı.'}), 404

    job = JOBS[job_id]

    if job['status'] == 'completed':
        return jsonify({'success': False, 'message': 'İşlem zaten tamamlanmış.'}), 400

    if job['status'] in ['queued', 'running']:
        # If it's running, signal the scraper to stop
        if job['status'] == 'running':
            request_stop()
            log_debug(f"İptal sinyali gönderildi (İş: {job_id})")

        # Mark as failed/canceled so the frontend knows it stopped
        job['status'] = 'failed'
        job['error'] = 'Kullanıcı tarafından iptal edildi.'
        return jsonify({'success': True, 'message': 'İşlem iptal ediliyor.'})

    return jsonify({'success': False, 'message': 'Bu işlem iptal edilemez.'}), 400

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
