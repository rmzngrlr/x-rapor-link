import time
import json
import getpass
import random
import os
import re
from datetime import datetime, timedelta
from dateutil import parser

# Global stop flag
stop_requested = False
# Global persistent driver
DRIVER = None

# VERSION: v2.4 - Cookie Sharing Enabled

def request_stop():
    global stop_requested
    stop_requested = True

# Imports for Selenium are moved inside init_driver for lazy loading
uc = None
By = None
WebDriverWait = None
EC = None
Keys = None
ActionChains = None

CONFIG_FILE = 'config.json'
OUTPUT_FILE = 'links.xlsx'
COOKIE_FILE = 'twitter_cookies.json'  # YENİ: Çerez dosyası

def load_config():
    """Loads configuration from the JSON file."""
    if not os.path.exists(CONFIG_FILE):
        print(f"Error: {CONFIG_FILE} not found!", flush=True)
        return None
    
    with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)

def parse_datetime(date_str, time_str="00:00"):
    """Parses a date string (DD-MM-YYYY) and time string (HH:MM) into a datetime object."""
    try:
        full_str = f"{date_str} {time_str}"
        return datetime.strptime(full_str, "%d-%m-%Y %H:%M")
    except ValueError:
        print(f"Error: Date/Time format '{date_str} {time_str}' is incorrect.", flush=True)
        return None

def ensure_selenium_imports():
    global uc, By, WebDriverWait, EC, Keys, ActionChains
    if uc is None:
        print("Loading Selenium libraries...", flush=True)
        try:
            import undetected_chromedriver as uc
            from selenium.webdriver.common.by import By
            from selenium.webdriver.support.ui import WebDriverWait
            from selenium.webdriver.support import expected_conditions as EC
            from selenium.webdriver.common.keys import Keys
            from selenium.webdriver.common.action_chains import ActionChains
        except Exception as e:
            print(f"Error: Could not import Selenium libraries. Error details: {e}", flush=True)
            return False
    return True

# --- YENİ FONKSİYON: Çerezleri Kaydet ---
def save_cookies_to_file(driver):
    """Saves current cookies to a file for Node.js to use."""
    try:
        cookies = driver.get_cookies()
        with open(COOKIE_FILE, 'w', encoding='utf-8') as f:
            json.dump(cookies, f, indent=2)
        print(f"✔ Oturum çerezleri '{COOKIE_FILE}' dosyasına kaydedildi (Node.js ile paylaşılıyor).", flush=True)
    except Exception as e:
        print(f"⚠ Çerez kaydetme hatası: {e}", flush=True)

def get_or_create_driver(username, password):
    """
    Returns the global DRIVER instance.
    If it doesn't exist or is dead, creates a new one and logs in.
    If it exists, checks login status and re-logs in if necessary.
    """
    global DRIVER
    
    if not ensure_selenium_imports():
        return None

    # Check if driver exists and is responsive
    if DRIVER is not None:
        try:
            # Check liveness by getting title
            _ = DRIVER.title
            print("Existing driver is active.", flush=True)
        except Exception as e:
            print(f"Existing driver appears dead ({e}). Restarting...", flush=True)
            try:
                DRIVER.quit()
            except:
                pass
            DRIVER = None

    # Create if needed
    if DRIVER is None:
        print("Initializing new Chrome driver...", flush=True)
        
        # Define the persistent user data directory
        user_data_dir = os.path.join(os.getcwd(), 'chrome_profile')
        if not os.path.exists(user_data_dir):
            os.makedirs(user_data_dir, exist_ok=True)
        print(f"Using persistent profile at: {user_data_dir}", flush=True)

        options = uc.ChromeOptions()
        options.add_argument("--start-maximized")
        # Ensure that the restore session bubble doesn't appear
        options.add_argument("--disable-session-crashed-bubble")
        
        # Anti-Throttling Flags
        options.add_argument("--disable-background-timer-throttling")
        options.add_argument("--disable-backgrounding-occluded-windows")
        options.add_argument("--disable-renderer-backgrounding")
        options.add_argument("--disable-infobars")
        try:
            DRIVER = uc.Chrome(options=options, user_data_dir=user_data_dir)
             # Ensure consistent window size and Force Focus
            try:
                DRIVER.minimize_window()
                time.sleep(0.5)
                DRIVER.maximize_window()
                DRIVER.set_window_size(1920, 1080) 
            except:
                pass
        except Exception as e:
            # Check for version mismatch error
            error_str = str(e)
            if "This version of ChromeDriver only supports Chrome version" in error_str:
                print(f"Version mismatch detected. Attempting to resolve... Error: {e}", flush=True)
                # Extract "Current browser version is X.X.X.X"
                match = re.search(r"Current browser version is (\d+)", error_str)
                if match:
                    major_version = int(match.group(1))
                    print(f"Detected Chrome Major Version: {major_version}. Retrying with version_main={major_version}...", flush=True)
                    try:
                        DRIVER = uc.Chrome(options=options, user_data_dir=user_data_dir, version_main=major_version)
                        try:
                            DRIVER.minimize_window()
                            time.sleep(0.5)
                            DRIVER.maximize_window()
                            DRIVER.set_window_size(1920, 1080)
                        except:
                            pass
                    except Exception as retry_e:
                        print(f"Failed to create driver even with specific version: {retry_e}", flush=True)
                        return None
                else:
                    print(f"Could not extract version from error message: {error_str}", flush=True)
                    return None
            else:
                print(f"Failed to create driver: {e}", flush=True)
                return None

    # Ensure logged in
    if verify_login_and_refresh(DRIVER, username, password):
        # YENİ: Başarılı giriş sonrası çerezleri kaydet
        save_cookies_to_file(DRIVER)
        return DRIVER
    else:
        print("Login failed or session lost.", flush=True)
        return None

def verify_login_and_refresh(driver, username, password):
    """
    Checks if currently logged in. If not, performs login.
    If logged in, just returns True (or maybe refreshes home).
    """
    # Quick Check: If on login page, skip refresh logic and login immediately
    current_url = driver.current_url
    if "login" in current_url or "flow/login" in current_url:
         print("Detected login page. Skipping checks and logging in...", flush=True)
         return login_to_x(driver, username, password)

    wait = WebDriverWait(driver, 5)
    
    # Check for indicator of being logged in (e.g. Home/Profile link)
    try:
        # If not on x.com, navigate there first
        if "x.com" not in current_url:
            print("Navigating to X home...", flush=True)
            driver.get("https://x.com/home")

        # Quick check without refresh first
        driver.find_element(By.CSS_SELECTOR, "a[data-testid='AppTabBar_Home_Link']")
        print("Session active. Ready to scrape.", flush=True)
        return True
    except:
        # If failed and NOT on a login page, try one refresh
        pass

    # Attempt refresh to clear stale state ONLY if we are not explicitly on a login page
    print("Session not immediately detected. Refreshing page...", flush=True)
    try:
        if "x.com" not in driver.current_url:
             driver.get("https://x.com/home")
        else:
             driver.refresh()
        
        # Check if redirected to login after refresh
        time.sleep(2)
        if "login" in driver.current_url:
             return login_to_x(driver, username, password)

        wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "a[data-testid='AppTabBar_Home_Link']")))
        print("Session active after refresh.", flush=True)
        return True
    except:
        pass
        
    # Not logged in or unsure, try logging in
    print("Session not detected. Attempting login...", flush=True)
    return login_to_x(driver, username, password)

def login_to_x(driver, username, password, target_username=None, interaction_callback=None):
    """Logs into X.com with manual interaction."""
    
    # If not already on login page, go there
    if "login" not in driver.current_url:
        print("Navigating to X login page...", flush=True)
        driver.get("https://x.com/i/flow/login")
    
    # Fast track: Check for username input immediately
    try:
        WebDriverWait(driver, 5).until(
            lambda d: d.find_elements(By.CSS_SELECTOR, "input[autocomplete='username']") or 
                      d.find_elements(By.CSS_SELECTOR, "a[data-testid='AppTabBar_Home_Link']")
        )
        
        # If home link is found, we are done
        if driver.find_elements(By.CSS_SELECTOR, "a[data-testid='AppTabBar_Home_Link']"):
             print("Redirected to home. Already logged in.", flush=True)
             return True
    except:
        pass

    wait = WebDriverWait(driver, 60) # Standard wait
    
    # 1. Username
    try:
        print("Entering username...", flush=True)
        username_input = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "input[autocomplete='username']")))
        
        for char in username:
            username_input.send_keys(char)
            time.sleep(random.uniform(0.02, 0.1))
            
        time.sleep(0.5)
        username_input.send_keys(Keys.RETURN)
        time.sleep(2)

        try:
            WebDriverWait(driver, 2).until(EC.visibility_of_element_located((By.NAME, "password")))
        except:
            print("Enter key didn't trigger navigation. Clicking 'Next' button...", flush=True)
            try:
                next_button = driver.find_element(By.XPATH, "//span[text()='Next' or text()='İleri']")
                driver.execute_script("arguments[0].click();", next_button)
            except Exception as e:
                print(f"Could not find/click Next button: {e}", flush=True)

        print("Waiting for password field to appear...", flush=True)
    except Exception as e:
        print(f"Error entering username (or already logged in?): {e}", flush=True)
        try:
            driver.find_element(By.CSS_SELECTOR, "a[data-testid='AppTabBar_Home_Link']")
            return True
        except:
            return False

    # 2. Password
    try:
        password_input = wait.until(EC.visibility_of_element_located((By.NAME, "password")))
        print("Password field detected. Entering password...", flush=True)
        password_input.send_keys(password)
        time.sleep(0.5)
        password_input.send_keys(Keys.RETURN)
            
    except Exception as e:
        print(f"Error entering password: {e}", flush=True)
        return False
        
    # Wait for login to complete
    try:
        print("Waiting for login to complete...", flush=True)
        wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "a[data-testid='AppTabBar_Home_Link']")))
        print("Login successful!", flush=True)
        return True
    except Exception as e:
        print("Login check timed out.", flush=True)
        return False 

def get_tweet_date(article):
    """Extracts the datetime from a tweet element."""
    try:
        time_element = article.find_element(By.TAG_NAME, "time")
        datetime_str = time_element.get_attribute("datetime")
        dt = parser.parse(datetime_str)
        # Adjust for Turkey Time (UTC+3)
        dt = dt + timedelta(hours=3)
        return dt.replace(tzinfo=None) 
    except Exception:
        return None

def get_tweet_link(article):
    """Extracts the link from a tweet element."""
    try:
        time_element = article.find_element(By.TAG_NAME, "time")
        link_element = time_element.find_element(By.XPATH, "./..")
        return link_element.get_attribute("href")
    except Exception:
        try:
            links = article.find_elements(By.TAG_NAME, "a")
            potential_links = []
            for link in links:
                href = link.get_attribute("href")
                if href and "/status/" in href:
                    if href.split("/status/")[-1].split("?")[0].isdigit():
                         potential_links.append(href)
            if potential_links:
                potential_links.sort(key=len)
                return potential_links[0]
        except Exception:
            pass
    return None

def is_retweet(article):
    try:
        social_context = article.find_elements(By.CSS_SELECTOR, "[data-testid='socialContext']")
        if social_context:
            text = social_context[0].text.lower()
            if ("retweet" in text or 
                "retweetledin" in text or 
                "retweetlendi" in text or 
                "yeniden yayınladı" in text or 
                "yeniden gönderdi" in text or 
                "reposted" in text):
                return True
        return False
    except Exception:
        return False

def get_reply_info(article):
    try:
        driver = article.parent
        js_script = """
        function getReactProps(dom) {
            const key = Object.keys(dom).find(key => key.startsWith("__reactProps$") || key.startsWith("__reactFiber$"));
            return key ? dom[key] : null;
        }
        function findTweetData(fiber) {
            if (!fiber) return null;
            let curr = fiber;
            while (curr) {
                if (curr.memoizedProps && curr.memoizedProps.tweet) {
                    return curr.memoizedProps.tweet;
                }
                if (curr.props && curr.props.tweet) {
                    return curr.props.tweet;
                }
                curr = curr.return;
                if (curr && curr.type && curr.type === 'body') break; 
            }
            return null;
        }
        const dom = arguments[0];
        const fiber = getReactProps(dom);
        const tweetData = findTweetData(fiber);
        if (tweetData) {
            if (tweetData.in_reply_to_screen_name) {
                return {is_reply: true, reply_to: tweetData.in_reply_to_screen_name};
            }
            if (tweetData.in_reply_to_status_id_str || tweetData.in_reply_to_user_id_str) {
                return {is_reply: true, reply_to: null};
            }
        }
        return {is_reply: false, reply_to: null}; 
        """
        result = driver.execute_script(js_script, article)
        if result:
            return result.get('is_reply', False), result.get('reply_to')
        return False, None
    except Exception as e:
        return False, None

def scrape_tweets(driver, target_username, start_datetime, end_datetime, search_keyword=None, scrape_mode='profile', only_replies=False):
    if scrape_mode == 'list':
        profile_url = target_username
        clean_target_username = None
        print(f"List Mode: Navigating to {profile_url}...", flush=True)
    else:
        if only_replies:
            profile_url = f"https://x.com/{target_username}/with_replies"
            print(f"Profile Mode (Replies): Navigating to {profile_url}...", flush=True)
        else:
            profile_url = f"https://x.com/{target_username}"
            print(f"Profile Mode: Navigating to {profile_url}...", flush=True)
        clean_target_username = target_username.lower().replace("@", "")
    
    if driver.current_url != profile_url:
        driver.get(profile_url)
        time.sleep(3)
    else:
        print("Already on target page. Starting scrape...", flush=True)
        time.sleep(2)

    try:
        driver.execute_script("""
            Object.defineProperty(document, 'hidden', {get: function() { return false; }, configurable: true});
            Object.defineProperty(document, 'visibilityState', {get: function() { return 'visible'; }, configurable: true});
            window.dispatchEvent(new Event('focus'));
        """)
    except Exception as e:
        pass

    collected_links = set()
    collected_data = []

    print(f"Collecting tweets between {start_datetime} and {end_datetime}...", flush=True)

    max_wait_time = 2.0
    max_stuck_retries = 15
    
    keep_scrolling = True
    consecutive_old_tweets = 0
    consecutive_scrolls_without_new_tweets = 0
    
    while keep_scrolling:
        if stop_requested:
            print("Stop requested. Breaking loop.", flush=True)
            break

        articles = driver.find_elements(By.CSS_SELECTOR, "article[data-testid='tweet']")
        
        for article in articles:
            if stop_requested:
                break
            try:
                t_datetime = get_tweet_date(article)
                if not t_datetime:
                    continue
                
                if start_datetime <= t_datetime <= end_datetime:
                    consecutive_old_tweets = 0 
                    
                    if is_retweet(article): continue
                    
                    is_rep, reply_to_handle = get_reply_info(article)
                    
                    if not only_replies:
                        if is_rep: continue
                    else:
                        final_is_reply = is_rep
                        if not final_is_reply:
                            try:
                                txt = article.text
                                if "Yanıtlanan" in txt or "Replying to" in txt or "En réponse à" in txt:
                                    final_is_reply = True
                            except:
                                pass
                        
                        if not final_is_reply:
                            continue

                        if reply_to_handle and clean_target_username:
                            if reply_to_handle.lower() == clean_target_username:
                                continue

                    if search_keyword:
                        try:
                            text_content = article.text.lower()
                            or_groups = search_keyword.lower().split(';')
                            is_match = False
                            for group in or_groups:
                                group = group.strip()
                                if not group: continue
                                and_parts = group.split(',')
                                group_match = True
                                for part in and_parts:
                                    part = part.strip()
                                    if part and part not in text_content:
                                        group_match = False
                                        break
                                if group_match:
                                    is_match = True
                                    break
                            if not is_match: continue
                        except Exception:
                            continue

                    link = get_tweet_link(article)
                    if link and link not in collected_links:
                        if scrape_mode == 'profile':
                            try:
                                link_parts = link.split('/')
                                if len(link_parts) > 3:
                                    link_username = link_parts[3].lower()
                                    if link_username != clean_target_username:
                                        continue
                            except Exception:
                                continue

                        collected_links.add(link)
                        # Extract username from link for list mode sorting
                        # Link format usually: https://x.com/username/status/123...
                        username_from_link = "Unknown"
                        try:
                            parts = link.split('/')
                            if len(parts) > 3:
                                username_from_link = parts[3]
                        except:
                            pass

                        collected_data.append({
                            "Date": t_datetime,
                            "Link": link,
                            "Username": username_from_link
                        })
                        print(f"Found tweet: {t_datetime} - {link} (User: {username_from_link})", flush=True)
                
                elif t_datetime < start_datetime:
                    consecutive_old_tweets += 1
                    if consecutive_old_tweets >= 10:
                        print("Reached tweets consistently older than start date. Stopping.", flush=True)
                        keep_scrolling = False
                        break
                else:
                    consecutive_old_tweets = 0

            except Exception as e:
                continue
        
        if not keep_scrolling:
            break

        last_text_hash = None
        if articles:
            try:
                last_text_hash = hash(articles[-1].text)
            except:
                pass

        scroll_step = driver.execute_script("return window.innerHeight") * 0.85
        driver.execute_script(f"window.scrollBy(0, {scroll_step});")
        
        start_wait = time.time()
        while time.time() - start_wait < max_wait_time:
            time.sleep(0.2)
            try:
                current_articles = driver.find_elements(By.CSS_SELECTOR, "article[data-testid='tweet']")
                if not current_articles:
                    continue
                if hash(current_articles[-1].text) != last_text_hash:
                    break
            except:
                pass
        
        new_height = driver.execute_script("return document.body.scrollHeight")
        current_scroll_y = driver.execute_script("return window.scrollY + window.innerHeight")
        
        if current_scroll_y >= new_height - 200:
            consecutive_scrolls_without_new_tweets += 1
            print(f"Reached bottom? Attempt {consecutive_scrolls_without_new_tweets}/{max_stuck_retries}", flush=True)
            if consecutive_scrolls_without_new_tweets > max_stuck_retries:
                print(f"No new content loading for {max_stuck_retries} attempts. Stopping.", flush=True)
                keep_scrolling = False
            else:
                 time.sleep(1)
        else:
            consecutive_scrolls_without_new_tweets = 0

    return collected_data

def save_to_excel(data, output_file=OUTPUT_FILE):
    if not data:
        print("No tweets found in the specified range.", flush=True)
        return 0, [], None
    
    try:
        from openpyxl import Workbook
        from io import BytesIO
    except ImportError:
        print("Error: openpyxl library is missing.", flush=True)
        return False, [], None

    filtered_data = data
    print(f"Post-processing: Saving {len(filtered_data)} tweets.", flush=True)

    try:
        wb = Workbook()
        ws = wb.active
        ws.title = "Links"
        ws.append(["Date", "Link", "Username"])
        
        for item in filtered_data:
            dt = item['Date']
            if dt and dt.tzinfo:
                dt = dt.replace(tzinfo=None)
            username = item.get('Username', '')
            ws.append([dt, item['Link'], username])
            ws.append([])
            
        if output_file:
            wb.save(output_file)
            count = len(filtered_data)
            print(f"Successfully saved {count} tweets to {output_file}.", flush=True)
            return count, filtered_data, None
        else:
            virtual_file = BytesIO()
            wb.save(virtual_file)
            virtual_file.seek(0)
            count = len(filtered_data)
            print(f"Successfully generated Excel in memory ({count} tweets).", flush=True)
            return count, filtered_data, virtual_file
            
    except Exception as e:
        print(f"Error saving to Excel: {e}", flush=True)
        return False, [], None

def run_process(username, password, target_username, start_date_str, end_date_str, start_time_str="00:00", end_time_str="23:59", output_file=OUTPUT_FILE, search_keyword=None, status_callback=None, interaction_callback=None, scrape_mode='profile', only_replies=False):
    global stop_requested
    stop_requested = False
    start_time_perf = time.time()

    def log(msg):
        if status_callback:
            status_callback(msg)
        print(msg, flush=True)

    start_datetime = parse_datetime(start_date_str, start_time_str)
    end_datetime = parse_datetime(end_date_str, end_time_str)

    if not start_datetime or not end_datetime:
        log("Error: Invalid date/time format.")
        return None

    log("Preparing driver...")
    driver = get_or_create_driver(username, password)

    if not driver:
        log("Error: Failed to initialize driver or login.")
        return None

    try:
        targets = [t.strip() for t in target_username.split(',') if t.strip()]
        all_data = []
        
        for i, target in enumerate(targets):
            if stop_requested: break
            log(f"Scraping {scrape_mode} target: {target} ({i+1}/{len(targets)})...")
            try:
                target_data = scrape_tweets(driver, target, start_datetime, end_datetime, search_keyword, scrape_mode, only_replies)
                if target_data:
                    # In profile mode, we want to keep the order per target, sorted by date
                    # In list mode, we might get mixed results, but we'll sort everything at the end
                    try:
                        target_data.sort(key=lambda x: x['Date'])
                    except:
                        pass
                    all_data.extend(target_data)
            except Exception as e:
                log(f"Error scraping {target}: {e}")
                continue
        
        # If in list mode, sort all data by Username then Date to group by user
        if scrape_mode == 'list' and all_data:
            log("Sorting data by User and Date for List Mode...")
            try:
                # Sort by Date first (secondary key)
                all_data.sort(key=lambda x: x['Date'])
                # Then sort by Username (primary key) - Python's sort is stable
                all_data.sort(key=lambda x: x['Username'].lower())
            except Exception as e:
                log(f"Sorting error: {e}")
        
        log("Saving to Excel...")
        result_count, filtered_data, excel_obj = save_to_excel(all_data, output_file)
        
        if result_count is not False:
            elapsed_time = time.time() - start_time_perf
            log("Process completed successfully!")
            
            link_list = [item['Link'] for item in filtered_data] if filtered_data else []

            return {
                "count": result_count, 
                "time": elapsed_time, 
                "links": link_list,
                "excel_file": excel_obj,
                "gs_status": None
            }
        else:
            log("Failed to save Excel file.")
            return None
            
    except Exception as e:
        log(f"An unexpected error occurred: {e}")
        return None
    finally:
        try:
            if driver and not stop_requested:
                driver.get("https://x.com/home")
        except:
            pass
        log("Task finished. Driver remains open for next task.")

if __name__ == "__main__":
    config = load_config()
    if config:
        print("Legacy CLI mode...", flush=True)
        username = input("Username: ")
        password = getpass.getpass("Password: ")
        target = config.get('target_username', '')
        run_process(username, password, target, config['start_date'], config['end_date'])
