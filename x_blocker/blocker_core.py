import time
import json
import os
import random
import re

# Global variables
uc = None
By = None
WebDriverWait = None
EC = None
Keys = None

DRIVER = None
STOP_REQUESTED = False

# Path to cookies in the root directory
# Assuming this file is in x_blocker/blocker_core.py, root is ../
COOKIE_FILE = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'twitter_cookies.json'))

def request_stop():
    global STOP_REQUESTED
    STOP_REQUESTED = True

def ensure_selenium_imports():
    global uc, By, WebDriverWait, EC, Keys
    if uc is None:
        try:
            import undetected_chromedriver as uc
            from selenium.webdriver.common.by import By
            from selenium.webdriver.support.ui import WebDriverWait
            from selenium.webdriver.support import expected_conditions as EC
            from selenium.webdriver.common.keys import Keys
        except ImportError as e:
            print(f"Selenium import error: {e}")
            return False
    return True

def get_driver():
    global DRIVER
    if not ensure_selenium_imports():
        return None

    if DRIVER is not None:
        try:
            # Check liveness
            _ = DRIVER.title
            return DRIVER
        except:
            DRIVER = None

    print("Initializing Block Tool Driver...")
    # Use a separate profile directory for the blocker tool
    user_data_dir = os.path.join(os.getcwd(), 'chrome_profile_blocker')
    if not os.path.exists(user_data_dir):
        os.makedirs(user_data_dir, exist_ok=True)

    options = uc.ChromeOptions()
    options.add_argument("--start-maximized")
    options.add_argument("--disable-session-crashed-bubble")
    options.add_argument("--disable-infobars")

    # Copy generic anti-detect options from main scraper
    options.add_argument("--disable-background-timer-throttling")
    options.add_argument("--disable-backgrounding-occluded-windows")
    options.add_argument("--disable-renderer-backgrounding")

    try:
        DRIVER = uc.Chrome(options=options, user_data_dir=user_data_dir)
    except Exception as e:
        print(f"Driver init error: {e}")
        # Version mismatch handling
        error_str = str(e)
        if "This version of ChromeDriver only supports Chrome version" in error_str:
             match = re.search(r"Current browser version is (\d+)", error_str)
             if match:
                 major = int(match.group(1))
                 print(f"Version mismatch detected. Retrying with version {major}...")
                 try:
                     options = uc.ChromeOptions()
                     options.add_argument("--start-maximized")
                     DRIVER = uc.Chrome(options=options, user_data_dir=user_data_dir, version_main=major)
                 except:
                     return None
             else:
                 return None
        else:
            return None

    # Load cookies if available to restore session
    if os.path.exists(COOKIE_FILE):
        print(f"Loading cookies from {COOKIE_FILE}...")
        try:
            DRIVER.get("https://x.com")
            time.sleep(2)
            with open(COOKIE_FILE, 'r', encoding='utf-8') as f:
                cookies = json.load(f)
                for cookie in cookies:
                    try:
                        # Selenium expects 'expiry' as int, sometimes it might be float or missing
                        if 'expiry' in cookie:
                            cookie['expiry'] = int(cookie['expiry'])
                        DRIVER.add_cookie(cookie)
                    except Exception as cookie_err:
                        pass
            print("Cookies loaded. Refreshing...")
            DRIVER.refresh()
            time.sleep(3)
        except Exception as e:
            print(f"Error loading cookies: {e}")

    return DRIVER

def scrape_retweeters(driver, tweet_url, progress_callback=None):
    global STOP_REQUESTED
    STOP_REQUESTED = False

    if not tweet_url:
        return []

    # Format URL to ensure it points to /retweets
    # Remove query parameters first
    base_url = tweet_url.split("?")[0]
    if base_url.endswith("/"):
        base_url = base_url[:-1]

    if not base_url.endswith("/retweets"):
        target_url = base_url + "/retweets"
    else:
        target_url = base_url

    print(f"Navigating to {target_url}...")
    driver.get(target_url)
    time.sleep(4)

    users_set = set()

    # Initial wait for content
    try:
        WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.CSS_SELECTOR, "div[data-testid='UserCell']")))
    except:
        print("No UserCell found initially. Might be empty or restricted.")
        return []

    last_count = 0
    consecutive_no_change = 0
    max_no_change = 5  # Stop after 5 scrolls with no new users

    while not STOP_REQUESTED:
        cells = driver.find_elements(By.CSS_SELECTOR, "div[data-testid='UserCell']")

        for cell in cells:
            try:
                # Extract username
                # Look for anchor tag that links to profile
                # Usually href="/username"
                links = cell.find_elements(By.TAG_NAME, "a")
                for link in links:
                    href = link.get_attribute("href")
                    if href:
                        # href is usually https://x.com/username or /username
                        if "x.com" in href:
                            parts = href.split("x.com/")
                            if len(parts) > 1:
                                potential_user = parts[1].split('/')[0]
                            else:
                                continue
                        else:
                            potential_user = href.strip('/')

                        # Filter out non-user links
                        if potential_user and potential_user not in ["home", "explore", "notifications", "messages", "search"]:
                            users_set.add(potential_user)
            except:
                pass

        current_count = len(users_set)
        if progress_callback:
            progress_callback(current_count)
        print(f"Users found: {current_count}")

        if current_count == last_count:
            consecutive_no_change += 1
        else:
            consecutive_no_change = 0

        last_count = current_count

        if consecutive_no_change >= max_no_change:
            print("No new users found for a while. Stopping scan.")
            break

        # Scroll down
        # Try to find the last cell and scroll it into view (handles modals better)
        if cells:
            try:
                driver.execute_script("arguments[0].scrollIntoView();", cells[-1])
            except:
                driver.execute_script("window.scrollBy(0, 800);")
        else:
            driver.execute_script("window.scrollBy(0, 800);")

        time.sleep(2)

        # Check for end of page
        # Sometimes X shows a spinner or just stops

    return sorted(list(users_set))

def block_user(driver, username):
    """
    Blocks a single user.
    Returns 'blocked', 'already_blocked', or 'failed'.
    """
    try:
        url = f"https://x.com/{username}"
        if driver.current_url != url:
            driver.get(url)
            time.sleep(2)

        wait = WebDriverWait(driver, 5)

        # Check if already blocked (look for unblock button)
        # Button text varies by language, so rely on data-testid if possible,
        # but 'unblock' button usually has different testid or structure.
        # Actually, if blocked, there's usually a "You blocked this account" message.
        try:
            # Checking for specific blocked message text might be language dependent.
            # But let's check for "Unblock" button which might be data-testid="unblock" (guessing)
            # or just proceed. If blocked, 'userActions' might still be there or 'unblock' button.
            # Let's try to find 'userActions' first.
            actions_btn = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, "[data-testid='userActions']")))
            actions_btn.click()
        except:
            # If userActions is missing, maybe account is suspended or we are blocked?
            print(f"Could not open actions for {username}. Account might be suspended or already blocked.")
            return 'failed'

        time.sleep(0.5)

        # Check if "Block" is an option. If it says "Unblock" or similar, we are done.
        # X menu items: data-testid="block" or "unblock"
        try:
            block_option = driver.find_element(By.CSS_SELECTOR, "[data-testid='block']")
            block_option.click()
        except:
            # Maybe already blocked?
            try:
                driver.find_element(By.CSS_SELECTOR, "[data-testid='unblock']")
                return 'already_blocked'
            except:
                print(f"Block option not found for {username}")
                return 'failed'

        time.sleep(0.5)

        # Confirm Block
        try:
            confirm_btn = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, "[data-testid='confirmationSheetConfirm']")))
            confirm_btn.click()
            time.sleep(1)
            return 'blocked'
        except Exception as e:
            print(f"Confirmation failed for {username}: {e}")
            return 'failed'

    except Exception as e:
        print(f"Exception blocking {username}: {e}")
        return 'failed'
