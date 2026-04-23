import json

with open('config.json', 'r') as f:
    config = json.load(f)

config['mysql_host'] = 'localhost'
config['mysql_port'] = 3306
config['mysql_user'] = 'root'
config['mysql_password'] = 'password'
config['mysql_database'] = 'xscraper_db'

with open('config.json', 'w') as f:
    json.dump(config, f, indent=4)
