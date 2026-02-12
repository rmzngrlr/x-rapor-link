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

    # Wait for manual login if needed
    print("Checking login status...")
    logged_in = False

    # Set longer page load timeout to prevent indefinite hangs
    try:
        DRIVER.set_page_load_timeout(30)
    except:
        pass

    # Check max 10 times (approx 30 seconds wait if not interacting, but loop allows manual interaction)
    # Actually, we want to block until logged in or stopped.
    # Giving user time to log in manually.

    while not STOP_REQUESTED:
        try:
            # Check for home link or profile element
            if DRIVER.find_elements(By.CSS_SELECTOR, "a[data-testid='AppTabBar_Home_Link']") or \
               DRIVER.find_elements(By.CSS_SELECTOR, "[data-testid='SideNav_AccountSwitcher_Button']") or \
               DRIVER.find_elements(By.CSS_SELECTOR, "[data-testid='primaryColumn']") or \
               "x.com/home" in DRIVER.current_url:
                print("Login detected.")
                logged_in = True
                break
        except:
            pass

        print("Waiting for user to log in... Please log in to X.com in the browser window.")
        time.sleep(3)

        # If user closed browser
        try:
            _ = DRIVER.title
        except:
            print("Browser closed.")
            DRIVER = None
            return None

    if not logged_in:
        print("Login check loop ended without success.")
        return None

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

    # Initial wait for content - More permissive
    print("Waiting for user list to load...")
    try:
        WebDriverWait(driver, 15).until(
            lambda d: d.find_elements(By.CSS_SELECTOR, "div[data-testid='UserCell']") or
                      d.find_elements(By.CSS_SELECTOR, "div[data-testid='cellInnerDiv']") or
                      d.find_elements(By.XPATH, "//div[@role='dialog']//div[@data-testid='UserCell']")
        )
    except:
        print("Timeout waiting for user list. Continuing to scrape anyway in case it loads slowly.")

    last_count = 0
    consecutive_no_change = 0
    max_no_change = 10  # Standard max retries

    # Check for early exit if list is very small
    # If first load has < 5 users, reduce max retries to avoid long wait

    while not STOP_REQUESTED:
        # Retweets usually open in a modal (dialog) or a dedicated page.
        # Prioritize cells inside a dialog if present, otherwise grab generic cells.

        cells = []
        # Try finding dialog first
        dialogs = driver.find_elements(By.XPATH, "//div[@role='dialog']")
        if dialogs:
            # If dialog exists, search specifically inside it to avoid scraping background elements (like original tweet author if visible)
            cells = dialogs[0].find_elements(By.CSS_SELECTOR, "div[data-testid='UserCell']")
            if not cells:
                 cells = dialogs[0].find_elements(By.CSS_SELECTOR, "div[data-testid='cellInnerDiv']")

        if not cells:
            # Fallback to general page search if no dialog or dialog empty
            cells = driver.find_elements(By.CSS_SELECTOR, "div[data-testid='UserCell']")
            if not cells:
                 cells = driver.find_elements(By.CSS_SELECTOR, "div[data-testid='cellInnerDiv']")

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
                        if potential_user and potential_user not in ["home", "explore", "notifications", "messages", "search", "login", "signup"]:
                            # Additional check: ensure it doesn't contain /status/ (tweet link)
                            if "/status/" not in href:
                                # Best effort check for visual indicator of blocked status in list
                                # Not perfect as DOM varies, but safer.
                                try:
                                    # If the button inside the cell says "Blocked" or "Engellendi"
                                    # This is tricky without relative xpath but let's try strict user addition
                                    users_set.add(potential_user)
                                except:
                                    pass
            except:
                pass

        current_count = len(users_set)
        if progress_callback:
            progress_callback(current_count)
        print(f"Users found: {current_count}")

        # Adjust max retries dynamically based on count
        if current_count < 5:
            effective_max_retries = 3
        else:
            effective_max_retries = max_no_change

        if current_count == last_count:
            consecutive_no_change += 1
        else:
            consecutive_no_change = 0

        last_count = current_count

        if consecutive_no_change >= effective_max_retries:
            print("No new users found for a while. Stopping scan.")
            break

        # Scroll logic with height check
        old_height = driver.execute_script("return document.body.scrollHeight")

        # Try to find the last cell and scroll it into view (handles modals better)
        if cells:
            try:
                driver.execute_script("arguments[0].scrollIntoView();", cells[-1])
            except:
                driver.execute_script("window.scrollBy(0, 800);")
        else:
            driver.execute_script("window.scrollBy(0, 800);")

        time.sleep(2)

        # Check if height changed (optional optimization, but X uses infinite scroll so height might stay same in virtual lists)
        # But for short lists, it's useful.
        new_height = driver.execute_script("return document.body.scrollHeight")
        if new_height == old_height and current_count < 10:
             # If height didn't change and we have few users, maybe we really are at the end
             pass

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

        # Navigate with timeout handling
        try:
            if driver.current_url != url:
                driver.get(url)
                # Wait for initial load
                time.sleep(1)
        except Exception as nav_err:
            print(f"Navigation timeout/error for {username}: {nav_err}")
            # Try to recover session
            try:
                driver.execute_script("window.stop();")
            except:
                pass

            # Reset to blank page to clear stuck state
            try:
                driver.get("about:blank")
                time.sleep(1)
                driver.get(url)
            except:
                return 'failed'

        wait = WebDriverWait(driver, 8)

        # Page load check (Wait for profile header or empty state)
        # If page stuck on loading (X logo), this will timeout and we can try refresh.
        try:
            wait.until(
                lambda d: d.find_elements(By.CSS_SELECTOR, "[data-testid='UserProfileHeader_Items']") or
                          d.find_elements(By.CSS_SELECTOR, "[data-testid='emptyState']") or
                          d.find_elements(By.CSS_SELECTOR, "[data-testid='userActions']")
            )
        except:
            print(f"Page load timeout for {username}. Refreshing...")
            try:
                driver.refresh()
            except:
                pass
            time.sleep(3)
            # Try waiting one more time
            try:
                wait.until(
                    lambda d: d.find_elements(By.CSS_SELECTOR, "[data-testid='UserProfileHeader_Items']") or
                              d.find_elements(By.CSS_SELECTOR, "[data-testid='emptyState']") or
                              d.find_elements(By.CSS_SELECTOR, "[data-testid='userActions']")
                )
            except:
                print(f"Failed to load profile for {username} after refresh.")
                return 'failed'

        # Check if already blocked immediately
        # X usually shows a "Blocked" button with data-testid corresponding to unblock action if blocked.
        # Or a "You blocked this account" message.

        try:
            # Check for unblock button directly on profile
            if driver.find_elements(By.CSS_SELECTOR, "[data-testid$='-unblock']"):
                print(f"User {username} is already blocked (unblock button found).")
                return 'already_blocked'

            # Check for generic "You blocked" message container
            if driver.find_elements(By.CSS_SELECTOR, "[data-testid='emptyState']"):
                 text_content = driver.find_element(By.CSS_SELECTOR, "[data-testid='emptyState']").text.lower()
                 if "blocked" in text_content or "engelledin" in text_content:
                     print(f"User {username} is already blocked (empty state text).")
                     return 'already_blocked'
        except:
            pass

        try:
            actions_btn = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, "[data-testid='userActions']")))
            actions_btn.click()
        except:
            print(f"Could not open actions for {username}. Account might be suspended or already blocked.")
            return 'failed'

        time.sleep(0.5)

        # Strict check for Block option
        try:
            block_option = driver.find_element(By.CSS_SELECTOR, "[data-testid='block']")
            block_option.click()
        except:
            # If 'block' is not found, check if 'unblock' is present in the menu
            try:
                if driver.find_elements(By.CSS_SELECTOR, "[data-testid='unblock']"):
                    print(f"User {username} is already blocked (unblock option in menu).")
                    # Close menu by clicking elsewhere or hitting escape
                    try:
                        driver.find_element(By.TAG_NAME, 'body').send_keys(Keys.ESCAPE)
                    except:
                        pass
                    return 'already_blocked'
            except:
                pass

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
