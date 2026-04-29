import pymysql, json
with open('config.json') as f: c = json.load(f)
conn = pymysql.connect(host=c['mysql_host'], user=c['mysql_user'], password=c['mysql_password'], database=c['mysql_database'], port=c['mysql_port'], cursorclass=pymysql.cursors.DictCursor)
with conn.cursor() as cur:
    cur.execute("SELECT id, target_name, next_scrape_at, last_scraped_at, scrape_interval_minutes FROM targets")
    print("TARGETS:")
    for row in cur.fetchall():
        print(row)
    cur.execute("SELECT NOW() as mysql_now")
    print("MySQL NOW:", cur.fetchone()['mysql_now'])
import datetime
print("Python NOW:", datetime.datetime.now())
