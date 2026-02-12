from flask import Flask, render_template, request, jsonify, redirect, url_for, flash
import threading
import uuid
import time
import os
import sys
import random

# Add current directory to path so we can import blocker_core
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from blocker_core import get_driver, scrape_retweeters, block_user, request_stop

app = Flask(__name__)
app.secret_key = 'blockersecret'

JOBS = {}
IS_BUSY = False
BUSY_LOCK = threading.Lock()

def scan_task(job_id, url):
    global IS_BUSY
    try:
        driver = get_driver()
        if not driver:
            JOBS[job_id]['status'] = 'failed'
            JOBS[job_id]['error'] = 'Driver başlatılamadı.'
            return

        def progress_update(count):
            JOBS[job_id]['progress'] = {'count': count}

        JOBS[job_id]['status'] = 'scanning'
        JOBS[job_id]['progress'] = {'count': 0}

        users = scrape_retweeters(driver, url, progress_callback=progress_update)
        JOBS[job_id]['result'] = users
        JOBS[job_id]['status'] = 'scan_completed'
    except Exception as e:
        JOBS[job_id]['status'] = 'failed'
        JOBS[job_id]['error'] = str(e)
    finally:
        with BUSY_LOCK:
            IS_BUSY = False

def block_task(job_id, users):
    global IS_BUSY
    try:
        driver = get_driver()
        if not driver:
             JOBS[job_id]['status'] = 'failed'
             return

        JOBS[job_id]['status'] = 'blocking'
        total = len(users)
        processed_count = 0
        success_count = 0

        for i, user in enumerate(users):
            # Check for stop signal via job status (or global stop)
            if JOBS[job_id].get('stop_requested'):
                break

            res = block_user(driver, user)
            processed_count += 1

            if res == 'blocked' or res == 'already_blocked':
                success_count += 1

            JOBS[job_id]['progress'] = {
                'current': processed_count,
                'success': success_count,
                'total': total,
                'last_user': user,
                'status': res
            }
            # Rate limit slightly to be safe - Random delay between 2 to 5 seconds
            # This helps avoid rate limiting or page loading issues
            time.sleep(random.uniform(2.0, 5.0))

        JOBS[job_id]['status'] = 'completed'
    except Exception as e:
        JOBS[job_id]['status'] = 'failed'
        JOBS[job_id]['error'] = str(e)
    finally:
        with BUSY_LOCK:
            IS_BUSY = False

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/scan', methods=['POST'])
def scan():
    global IS_BUSY
    url = request.form.get('url')

    if not url:
        flash("Lütfen bir link girin.", "danger")
        return redirect(url_for('index'))

    with BUSY_LOCK:
        if IS_BUSY:
            flash("Şu anda başka bir işlem yapılıyor. Lütfen bekleyin.", "warning")
            return redirect(url_for('index'))
        IS_BUSY = True

    job_id = str(uuid.uuid4())
    JOBS[job_id] = {'status': 'queued', 'type': 'scan'}

    t = threading.Thread(target=scan_task, args=(job_id, url))
    t.daemon = True
    t.start()

    return redirect(url_for('processing', job_id=job_id))

@app.route('/processing/<job_id>')
def processing(job_id):
    if job_id not in JOBS:
        return redirect(url_for('index'))
    return render_template('processing.html', job_id=job_id)

@app.route('/status/<job_id>')
def status(job_id):
    job = JOBS.get(job_id)
    if not job:
        return jsonify({'status': 'not_found'})

    response = {
        'status': job['status'],
        'type': job.get('type'),
        'error': job.get('error')
    }

    if job['status'] == 'scan_completed':
        response['redirect'] = url_for('list_users', job_id=job_id)
        response['count'] = len(job.get('result', []))

    if job['status'] == 'scanning':
        response['progress'] = job.get('progress')

    if job.get('type') == 'block':
        response['progress'] = job.get('progress')
        if job['status'] == 'completed':
             response['msg'] = "Engelleme işlemi tamamlandı."

    return jsonify(response)

@app.route('/list/<job_id>')
def list_users(job_id):
    job = JOBS.get(job_id)
    if not job or 'result' not in job:
        return redirect(url_for('index'))
    return render_template('list.html', job_id=job_id, users=job['result'])

@app.route('/block', methods=['POST'])
def block():
    global IS_BUSY
    job_id = request.form.get('job_id') # Original scan job id
    original_job = JOBS.get(job_id)

    if not original_job or 'result' not in original_job:
         return redirect(url_for('index'))

    users = original_job['result']

    with BUSY_LOCK:
        if IS_BUSY:
            flash("Şu anda başka bir işlem yapılıyor.", "warning")
            return redirect(url_for('list_users', job_id=job_id))
        IS_BUSY = True

    block_job_id = str(uuid.uuid4())
    JOBS[block_job_id] = {
        'status': 'queued',
        'type': 'block',
        'progress': {'current': 0, 'total': len(users), 'last_user': '', 'status': ''}
    }

    t = threading.Thread(target=block_task, args=(block_job_id, users))
    t.daemon = True
    t.start()

    return redirect(url_for('processing', job_id=block_job_id))

@app.route('/stop/<job_id>')
def stop_job(job_id):
    if job_id in JOBS:
        JOBS[job_id]['stop_requested'] = True
        request_stop() # Signal core to stop
    return redirect(url_for('index'))

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=3003, debug=False, threaded=True)
