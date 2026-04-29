import pymysql, json, datetime
with open('config.json') as f: c = json.load(f)
conn = pymysql.connect(host=c['mysql_host'], user=c['mysql_user'], password=c['mysql_password'], database=c['mysql_database'], port=c['mysql_port'], cursorclass=pymysql.cursors.DictCursor)
with conn.cursor() as cur:
    cur.execute("SELECT NOW() as mysql_now")
    row = cur.fetchone()
    print("MySQL NOW():", row['mysql_now'])
print("Python NOW():", datetime.datetime.now())
