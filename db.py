import pymysql
import json
import os
from werkzeug.security import generate_password_hash

CONFIG_FILE = 'config.json'

def get_db_connection():
    if not os.path.exists(CONFIG_FILE):
        return None
    with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
        config = json.load(f)

    try:
        conn = pymysql.connect(
            host=config.get('mysql_host', 'localhost'),
            port=config.get('mysql_port', 3306),
            user=config.get('mysql_user', 'root'),
            password=config.get('mysql_password', ''),
            database=config.get('mysql_database', 'xscraper_db'),
            charset='utf8mb4',
            cursorclass=pymysql.cursors.DictCursor
        )
        return conn
    except Exception as e:
        print(f"Database connection error: {e}")
        return None

def init_db():
    if not os.path.exists(CONFIG_FILE):
        return None
    with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
        config = json.load(f)

    # First connect without DB to create it if not exists
    try:
        conn_init = pymysql.connect(
            host=config.get('mysql_host', 'localhost'),
            port=config.get('mysql_port', 3306),
            user=config.get('mysql_user', 'root'),
            password=config.get('mysql_password', ''),
            charset='utf8mb4',
            cursorclass=pymysql.cursors.DictCursor
        )
        with conn_init.cursor() as cursor:
            cursor.execute(f"CREATE DATABASE IF NOT EXISTS `{config.get('mysql_database', 'xscraper_db')}` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci")
        conn_init.commit()
        conn_init.close()
    except Exception as e:
        print(f"Failed to create database during init_db: {e}")
        return

    conn = get_db_connection()
    if not conn:
        print("Skipping DB initialization (cannot connect).")
        return

    try:
        with conn.cursor() as cursor:
            # Table: settings
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS settings (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    start_hour INT NOT NULL DEFAULT 0,
                    interval_hours INT NOT NULL DEFAULT 6
                )
            """)

            # Table: admin_users
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS admin_users (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    username VARCHAR(50) NOT NULL UNIQUE,
                    password_hash VARCHAR(255) NOT NULL
                )
            """)

            # Table: targets
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS targets (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    target_name VARCHAR(255) NOT NULL,
                    target_type ENUM('user', 'list') NOT NULL,
                    scrape_interval_minutes INT NOT NULL DEFAULT 60,
                    last_scraped_at DATETIME NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Try to alter targets table in case it was created before the column was added
            try:
                cursor.execute("ALTER TABLE targets ADD COLUMN last_scraped_at DATETIME NULL")
            except Exception as alt_e:
                # Ignore if column already exists
                pass

            try:
                cursor.execute("ALTER TABLE targets ADD COLUMN scrape_interval_minutes INT NOT NULL DEFAULT 60")
            except Exception as alt_e:
                pass

            # Table: tweets
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS tweets (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    target_id INT NOT NULL,
                    tweet_date DATETIME NOT NULL,
                    link VARCHAR(500) NOT NULL,
                    username VARCHAR(100),
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (target_id) REFERENCES targets(id) ON DELETE CASCADE,
                    UNIQUE KEY target_link (target_id, link)
                )
            """)

            # Insert default admin if table is empty
            cursor.execute("SELECT COUNT(*) as count FROM admin_users")
            result = cursor.fetchone()
            if result['count'] == 0:
                default_username = 'admin'
                default_password = 'admin'
                password_hash = generate_password_hash(default_password)
                cursor.execute("INSERT INTO admin_users (username, password_hash) VALUES (%s, %s)", (default_username, password_hash))
                print("Default admin user created (admin/admin).")

            # Insert default settings if table is empty
            cursor.execute("SELECT COUNT(*) as count FROM settings")
            result = cursor.fetchone()
            if result['count'] == 0:
                cursor.execute("INSERT INTO settings (start_hour, interval_hours) VALUES (0, 6)")
                print("Default settings initialized.")

        conn.commit()
        print("Database initialized successfully.")
    except Exception as e:
        print(f"Database initialization error: {e}")
    finally:
        conn.close()

if __name__ == '__main__':
    init_db()
