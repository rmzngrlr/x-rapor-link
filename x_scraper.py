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
        print(f"Hata: {CONFIG_FILE} bulunamadı!", flush=True)
        return None
    
    with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)

def parse_datetime(date_str, time_str="00:00"):
    """Parses a date string (DD-MM-YYYY) and time string (HH:MM) into a datetime object."""
    try:
        full_str = f"{date_str} {time_str}"
        return datetime.strptime(full_str, "%d-%m-%Y %H:%M")
    except ValueError:
        print(f"Hata: Tarih/Saat formatı '{date_str} {time_str}' hatalı.", flush=True)
        return None

def ensure_selenium_imports():
    global uc, By, WebDriverWait, EC, Keys, ActionChains
    if uc is None:
        print("Selenium kütüphaneleri yükleniyor...", flush=True)
        try:
            import undetected_chromedriver as uc
            from selenium.webdriver.common.by import By
            from selenium.webdriver.support.ui import WebDriverWait
            from selenium.webdriver.support import expected_conditions as EC
            from selenium.webdriver.common.keys import Keys
            from selenium.webdriver.common.action_chains import ActionChains
        except Exception as e:
            print(f"Hata: Selenium kütüphaneleri yüklenemedi. Detaylar: {e}", flush=True)
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
            print("Mevcut tarayıcı aktif.", flush=True)
        except Exception as e:
            print(f"Mevcut tarayıcı yanıt vermiyor ({e}). Yeniden başlatılıyor...", flush=True)
            try:
                DRIVER.quit()
            except:
                pass
            DRIVER = None

    # Create if needed
    if DRIVER is None:
        print("Yeni Chrome sürücüsü başlatılıyor...", flush=True)
        
        # Define the persistent user data directory
        user_data_dir = os.path.join(os.getcwd(), 'chrome_profile')
        if not os.path.exists(user_data_dir):
            os.makedirs(user_data_dir, exist_ok=True)
        print(f"Kalıcı profil yolu: {user_data_dir}", flush=True)

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
                print(f"Sürüm uyuşmazlığı tespit edildi. Çözülmeye çalışılıyor... Hata: {e}", flush=True)
                # Extract "Current browser version is X.X.X.X"
                match = re.search(r"Current browser version is (\d+)", error_str)
                if match:
                    major_version = int(match.group(1))
                    print(f"Tespit edilen Chrome Ana Sürümü: {major_version}. version_main={major_version} ile tekrar deneniyor...", flush=True)
                    try:
                        # Re-create options to avoid 'cannot reuse ChromeOptions' error
                        new_options = uc.ChromeOptions()
                        new_options.add_argument("--start-maximized")
                        new_options.add_argument("--disable-session-crashed-bubble")
                        new_options.add_argument("--disable-background-timer-throttling")
                        new_options.add_argument("--disable-backgrounding-occluded-windows")
                        new_options.add_argument("--disable-renderer-backgrounding")
                        new_options.add_argument("--disable-infobars")

                        DRIVER = uc.Chrome(options=new_options, user_data_dir=user_data_dir, version_main=major_version)
                        try:
                            DRIVER.minimize_window()
                            time.sleep(0.5)
                            DRIVER.maximize_window()
                            DRIVER.set_window_size(1920, 1080)
                        except:
                            pass
                    except Exception as retry_e:
                        print(f"Belirtilen sürümle bile sürücü oluşturulamadı: {retry_e}", flush=True)
                        return None
                else:
                    print(f"Hata mesajından sürüm bilgisi alınamadı: {error_str}", flush=True)
                    return None
            else:
                print(f"Sürücü oluşturulamadı: {e}", flush=True)
                return None

    # Ensure logged in
    if verify_login_and_refresh(DRIVER, username, password):
        # YENİ: Başarılı giriş sonrası çerezleri kaydet
        save_cookies_to_file(DRIVER)
        return DRIVER
    else:
        print("Giriş başarısız veya oturum kaybedildi.", flush=True)
        return None

def verify_login_and_refresh(driver, username, password):
    """
    Checks if currently logged in. If not, performs login.
    If logged in, just returns True (or maybe refreshes home).
    """
    # Quick Check: If on login page, skip refresh logic and login immediately
    current_url = driver.current_url
    if "login" in current_url or "flow/login" in current_url:
         print("Giriş sayfası tespit edildi. Kontroller atlanıyor ve giriş yapılıyor...", flush=True)
         return login_to_x(driver, username, password)

    wait = WebDriverWait(driver, 5)
    
    # Check for indicator of being logged in (e.g. Home/Profile link)
    try:
        # If not on x.com, navigate there first
        if "x.com" not in current_url:
            print("X ana sayfasına gidiliyor...", flush=True)
            driver.get("https://x.com/home")

        # Quick check without refresh first
        driver.find_element(By.CSS_SELECTOR, "a[data-testid='AppTabBar_Home_Link']")
        print("Oturum aktif. İşlem için hazır.", flush=True)
        return True
    except:
        # If failed and NOT on a login page, try one refresh
        pass

    # Attempt refresh to clear stale state ONLY if we are not explicitly on a login page
    print("Oturum hemen algılanamadı. Sayfa yenileniyor...", flush=True)
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
        print("Yenileme sonrası oturum aktif.", flush=True)
        return True
    except:
        pass
        
    # Not logged in or unsure, try logging in
    print("Oturum algılanamadı. Giriş yapılıyor...", flush=True)
    return login_to_x(driver, username, password)

def login_to_x(driver, username, password, target_username=None, interaction_callback=None):
    """Logs into X.com with manual interaction."""
    
    # If not already on login page, go there
    if "login" not in driver.current_url:
        print("X giriş sayfasına gidiliyor...", flush=True)
        driver.get("https://x.com/i/flow/login")
    
    # Fast track: Check for username input immediately
    try:
        WebDriverWait(driver, 5).until(
            lambda d: d.find_elements(By.CSS_SELECTOR, "input[autocomplete='username']") or 
                      d.find_elements(By.CSS_SELECTOR, "a[data-testid='AppTabBar_Home_Link']")
        )
        
        # If home link is found, we are done
        if driver.find_elements(By.CSS_SELECTOR, "a[data-testid='AppTabBar_Home_Link']"):
             print("Ana sayfaya yönlendirildi. Zaten giriş yapılmış.", flush=True)
             return True
    except:
        pass

    wait = WebDriverWait(driver, 60) # Standard wait
    
    # 1. Username
    try:
        print("Kullanıcı adı giriliyor...", flush=True)
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
            print("Enter tuşu işe yaramadı. 'İleri' butonuna tıklanıyor...", flush=True)
            try:
                next_button = driver.find_element(By.XPATH, "//span[text()='Next' or text()='İleri']")
                driver.execute_script("arguments[0].click();", next_button)
            except Exception as e:
                print(f"İleri butonu bulunamadı/tıklanamadı: {e}", flush=True)

        print("Şifre alanının belirmesi bekleniyor...", flush=True)
    except Exception as e:
        print(f"Kullanıcı adı girme hatası (veya zaten giriş yapılmış?): {e}", flush=True)
        try:
            driver.find_element(By.CSS_SELECTOR, "a[data-testid='AppTabBar_Home_Link']")
            return True
        except:
            return False

    # 2. Password
    try:
        password_input = wait.until(EC.visibility_of_element_located((By.NAME, "password")))
        print("Şifre alanı tespit edildi. Şifre giriliyor...", flush=True)
        password_input.send_keys(password)
        time.sleep(0.5)
        password_input.send_keys(Keys.RETURN)
            
    except Exception as e:
        print(f"Şifre girme hatası: {e}", flush=True)
        return False
        
    # Wait for login to complete
    try:
        print("Giriş işleminin tamamlanması bekleniyor...", flush=True)
        wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "a[data-testid='AppTabBar_Home_Link']")))
        print("Giriş başarılı!", flush=True)
        return True
    except Exception as e:
        print("Giriş kontrolü zaman aşımına uğradı.", flush=True)
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
        print(f"Liste Modu: {profile_url} adresine gidiliyor...", flush=True)
    else:
        if only_replies:
            profile_url = f"https://x.com/{target_username}/with_replies"
            print(f"Profil Modu (Yanıtlar): {profile_url} adresine gidiliyor...", flush=True)
        else:
            profile_url = f"https://x.com/{target_username}"
            print(f"Profil Modu: {profile_url} adresine gidiliyor...", flush=True)
        clean_target_username = target_username.lower().replace("@", "")
    
    if driver.current_url != profile_url:
        driver.get(profile_url)
        time.sleep(3)
    else:
        print("Zaten hedef sayfadasınız. Tarama başlatılıyor...", flush=True)
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

    print(f"{start_datetime} ile {end_datetime} arasındaki tweetler toplanıyor...", flush=True)

    max_wait_time = 2.0
    max_stuck_retries = 15
    
    keep_scrolling = True
    consecutive_old_tweets = 0
    consecutive_scrolls_without_new_tweets = 0
    
    while keep_scrolling:
        if stop_requested:
            print("Durdurma istendi. Döngü kırılıyor.", flush=True)
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
                        print(f"Tweet bulundu: {t_datetime} - {link} (Kullanıcı: {username_from_link})", flush=True)
                
                elif t_datetime < start_datetime:
                    consecutive_old_tweets += 1
                    if consecutive_old_tweets >= 10:
                        print("Başlangıç tarihinden eski tweetlere ulaşıldı. Durduruluyor.", flush=True)
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
            print(f"Sayfa sonu mu? Deneme {consecutive_scrolls_without_new_tweets}/{max_stuck_retries}", flush=True)
            if consecutive_scrolls_without_new_tweets > max_stuck_retries:
                print(f"{max_stuck_retries} deneme boyunca yeni içerik yüklenmedi. Durduruluyor.", flush=True)
                keep_scrolling = False
            else:
                 time.sleep(1)
        else:
            consecutive_scrolls_without_new_tweets = 0

    return collected_data

def save_to_excel(data, output_file=OUTPUT_FILE):
    if not data:
        print("Belirtilen aralıkta tweet bulunamadı.", flush=True)
        return 0, [], None
    
    try:
        from openpyxl import Workbook
        from io import BytesIO
    except ImportError:
        print("Hata: openpyxl kütüphanesi eksik.", flush=True)
        return False, [], None

    filtered_data = data
    print(f"İşleniyor: {len(filtered_data)} tweet kaydedilecek.", flush=True)

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
            print(f"{count} tweet başarıyla {output_file} dosyasına kaydedildi.", flush=True)
            return count, filtered_data, None
        else:
            virtual_file = BytesIO()
            wb.save(virtual_file)
            virtual_file.seek(0)
            count = len(filtered_data)
            print(f"Excel bellekte başarıyla oluşturuldu ({count} tweet).", flush=True)
            return count, filtered_data, virtual_file
            
    except Exception as e:
        print(f"Excel kaydetme hatası: {e}", flush=True)
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
        log("Hata: Geçersiz tarih/saat formatı.")
        return None

    log("Sürücü hazırlanıyor...")
    driver = get_or_create_driver(username, password)

    if not driver:
        log("Hata: Sürücü başlatılamadı veya giriş yapılamadı.")
        return None

    try:
        targets = [t.strip() for t in target_username.split(',') if t.strip()]
        all_data = []
        
        for i, target in enumerate(targets):
            if stop_requested: break
            log(f"{scrape_mode} hedefi taranıyor: {target} ({i+1}/{len(targets)})...")
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
                log(f"{target} taranırken hata: {e}")
                continue
        
        # If in list mode, sort all data by Username then Date to group by user
        if scrape_mode == 'list' and all_data:
            log("Liste Modu için veriler Kullanıcı ve Tarihe göre sıralanıyor...")
            try:
                # Sort by Date first (secondary key)
                all_data.sort(key=lambda x: x['Date'])
                # Then sort by Username (primary key) - Python's sort is stable
                all_data.sort(key=lambda x: x['Username'].lower())
            except Exception as e:
                log(f"Sıralama hatası: {e}")
        
        log("Excel'e kaydediliyor...")
        result_count, filtered_data, excel_obj = save_to_excel(all_data, output_file)
        
        if result_count is not False:
            elapsed_time = time.time() - start_time_perf
            log("İşlem başarıyla tamamlandı!")
            
            link_list = [item['Link'] for item in filtered_data] if filtered_data else []

            return {
                "count": result_count, 
                "time": elapsed_time, 
                "links": link_list,
                "excel_file": excel_obj,
                "gs_status": None
            }
        else:
            log("Excel dosyası kaydedilemedi.")
            return None
            
    except Exception as e:
        log(f"Beklenmeyen bir hata oluştu: {e}")
        return None
    finally:
        try:
            if driver and not stop_requested:
                driver.get("https://x.com/home")
        except:
            pass
        log("Görev tamamlandı. Sürücü bir sonraki görev için açık kalıyor.")

if __name__ == "__main__":
    config = load_config()
    if config:
        print("Eski CLI modu...", flush=True)
        username = input("Username: ")
        password = getpass.getpass("Password: ")
        target = config.get('target_username', '')
        run_process(username, password, target, config['start_date'], config['end_date'])
