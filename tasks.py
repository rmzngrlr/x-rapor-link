import json
import os
from datetime import datetime, timedelta
from db import get_db_connection
from x_scraper import run_process, CONFIG_FILE

def load_auth_credentials():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                cfg = json.load(f)
                return cfg.get("auth_username", ""), cfg.get("auth_password", "")
        except:
            pass
    return "", ""

def run_incremental_scraping():
    print(f"[{datetime.now()}] Starting incremental scraping job...")
    auth_user, auth_pass = load_auth_credentials()

    if not auth_user or not auth_pass:
        print("Scraping job aborted: No authentication credentials found in config.json")
        return

    conn = get_db_connection()
    if not conn:
        print("Scraping job aborted: Cannot connect to database.")
        return

    targets = []
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT * FROM targets")
            targets = cursor.fetchall()
    except Exception as e:
        print(f"Failed to fetch targets: {e}")
        conn.close()
        return

    for target in targets:
        target_id = target['id']
        target_name = target['target_name']
        target_type = target['target_type']

        print(f"Processing target: {target_name} ({target_type})")

        # Determine start date based on last collected tweet
        last_tweet_date = None
        try:
            with conn.cursor() as cursor:
                cursor.execute("SELECT MAX(tweet_date) as last_date FROM tweets WHERE target_id = %s", (target_id,))
                result = cursor.fetchone()
                if result and result['last_date']:
                    last_tweet_date = result['last_date']
        except Exception as e:
            print(f"Failed to get last tweet date for {target_name}: {e}")
            continue

        if last_tweet_date:
            # Add 1 second so we don't re-fetch the exact same second if possible,
            # though Twitter API/scraper might not be second-perfect. We filter on insertion anyway.
            start_datetime = last_tweet_date
        else:
            # Default to 1 day (24 hours) ago if no data exists
            start_datetime = datetime.now() - timedelta(days=1)

        end_datetime = datetime.now()

        # Run scraper
        try:
            print(f"  Scraping from {start_datetime} to {end_datetime}...")
            stats = run_process(
                username=auth_user,
                password=auth_pass,
                target_username=target_name,
                start_date_str=None, # We use datetime objects
                end_date_str=None,
                start_datetime_obj=start_datetime,
                end_datetime_obj=end_datetime,
                scrape_mode=target_type,
                only_replies=False,
                include_retweets=False, # We don't include RTs based on user request (only normal tweets)
                only_retweets=False,
                skip_excel=True # We don't need Excel for background task
            )

            if stats and stats.get('raw_data'):
                raw_data = stats['raw_data']
                new_tweets_count = 0

                with conn.cursor() as cursor:
                    for item in raw_data:
                        tweet_date = item['Date']
                        link = item['Link']
                        username = item.get('Username', '')

                        # Handle potential string dates from scraper
                        if isinstance(tweet_date, str):
                            try:
                                tweet_date = datetime.strptime(tweet_date, "%Y-%m-%d %H:%M:%S")
                            except ValueError:
                                # Fallback if parsing fails
                                pass

                        # Ensure it's STRICTLY newer than last_tweet_date if we had one
                        if last_tweet_date and isinstance(tweet_date, datetime) and tweet_date <= last_tweet_date:
                            continue

                        # Insert ignoring duplicates (thanks to UNIQUE constraint on target_id, link)
                        try:
                            cursor.execute("""
                                INSERT IGNORE INTO tweets (target_id, tweet_date, link, username)
                                VALUES (%s, %s, %s, %s)
                            """, (target_id, tweet_date, link, username))
                            if cursor.rowcount > 0:
                                new_tweets_count += 1
                        except Exception as e:
                            print(f"    Error inserting tweet {link}: {e}")

                conn.commit()
                print(f"  Completed {target_name}: {new_tweets_count} new tweets saved.")
            else:
                print(f"  Completed {target_name}: 0 new tweets.")

        except Exception as e:
            print(f"Error processing target {target_name}: {e}")

    conn.close()
    print(f"[{datetime.now()}] Incremental scraping job finished.")

if __name__ == '__main__':
    # Can run this manually to test
    run_incremental_scraping()
