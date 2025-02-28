import os
import sys
import time
import random
import threading
import tkinter as tk
import webbrowser
import requests
from tkinter import ttk, scrolledtext
from PIL import Image, ImageTk

# Selenium
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.action_chains import ActionChains

def resource_path(relative_path):
    """Trả về đường dẫn tuyệt đối tới file resource, hỗ trợ PyInstaller."""
    try:
        base_path = sys._MEIPASS
    except:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

CHROMEDRIVER_PATH = resource_path("chromedriver.exe")
ICON_PATH = resource_path("lytran.ico")
AUTHOR_IMAGE_PATH = resource_path("lytran.jpg")

# -------------------------------------------------------------------------------------------
# Proxy Manager
# -------------------------------------------------------------------------------------------
class ProxyManager:
    def __init__(self):
        self.proxy_list = []
        self.rotate_enabled = False
        self.current_index = 0

    def load_from_text(self, text):
        self.proxy_list.clear()
        self.current_index = 0
        lines = text.strip().split('\n')
        for line in lines:
            line=line.strip()
            if not line:
                continue
            parts=line.split(':')
            if len(parts)<3:
                continue
            ip=parts[0].strip()
            port=parts[1].strip()
            protocol=parts[2].strip().lower()
            self.proxy_list.append((ip, port, protocol))

    def get_next_proxy(self):
        if not self.proxy_list:
            return None
        proxy = self.proxy_list[self.current_index]
        if self.rotate_enabled:
            self.current_index = (self.current_index + 1) % len(self.proxy_list)
        return proxy

global_proxy_manager = ProxyManager()

def check_ip_current():
    try:
        r = requests.get("https://api.ipify.org", timeout=5)
        return r.text.strip()
    except:
        return "Không thể lấy IP"

# -------------------------------------------------------------------------------------------
# WebDriver
# -------------------------------------------------------------------------------------------
def get_driver(proxy=None, headless=False, w=360, h=740):
    options = webdriver.ChromeOptions()

    # Giả lập user-agent
    user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/98.0.4758.102 Safari/537.36"
    options.add_argument(f"user-agent={user_agent}")

    options.add_argument("--incognito")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("--disable-features=WebAssembly,TFLite")
    options.add_argument("--disable-popup-blocking")
    options.add_argument("--disable-geolocation")

    prefs = {"profile.default_content_setting_values.geolocation": 2}
    options.add_experimental_option("prefs", prefs)

    if proxy:
        ip, port, protocol = proxy
        if protocol not in ["http","socks4","socks5"]:
            protocol = "http"
        proxy_str = f"{protocol}://{ip}:{port}"
        options.add_argument(f"--proxy-server={proxy_str}")

    if headless:
        options.add_argument("--headless")
        options.add_argument("--window-size=1920,1080")
    else:
        options.add_argument(f"--window-size={w},{h}")

    # Giảm detection
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option("useAutomationExtension", False)

    service = Service(CHROMEDRIVER_PATH)
    driver = webdriver.Chrome(service=service, options=options)
    # Ẩn navigator.webdriver
    driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
        "source": """
        Object.defineProperty(navigator,'webdriver',{
            get:()=>undefined
        })
        """
    })
    return driver

def close_location_popup(driver):
    time.sleep(2)
    for _ in range(5):
        btns=driver.find_elements(By.XPATH,"//div[contains(text(),'Để sau')] | //button[contains(text(),'Để sau')]")
        if btns:
            driver.execute_script("arguments[0].click();", btns[0])
            time.sleep(2)
            return
        time.sleep(1)

def scroll_like_user(driver, duration=5):
    endtime = time.time()+duration
    while time.time()<endtime:
        driver.execute_script("window.scrollBy(0, 400);")
        time.sleep(random.uniform(1,2))

# -------------------------------------------------------------------------------------------
# Tìm Chỉ Từ Khoá / EXACT URL / Domain
# -------------------------------------------------------------------------------------------
def search_keyword_only(driver, log, keyword, max_pages):
    log(f"Chỉ tìm từ khoá: '{keyword}', tối đa {max_pages} trang, không vào.")
    driver.get("https://www.google.com")
    close_location_popup(driver)

    box = driver.find_element(By.NAME,"q")
    box.send_keys(keyword)
    time.sleep(random.uniform(1,3))
    box.send_keys(Keys.RETURN)
    close_location_popup(driver)

    for page in range(1, max_pages+1):
        log(f"Trang {page} => cuộn xem, không bấm vào.")
        time.sleep(2)
        scroll_like_user(driver,5)
        nxt=driver.find_elements(By.XPATH,"//a[@id='pnnext']")
        if nxt:
            nxt[0].click()
        else:
            log("Hết trang => dừng 'Chỉ tìm từ khoá'.")
            break

def search_exact_url(driver, log, keyword, exact_url, max_pages, read_time=60):
    log(f"Tìm link: {exact_url}, số trang tìm: {max_pages}")
    driver.get("https://www.google.com")
    close_location_popup(driver)

    box=driver.find_element(By.NAME,"q")
    box.send_keys(keyword)
    time.sleep(random.uniform(1,3))
    box.send_keys(Keys.RETURN)
    close_location_popup(driver)

    found=False
    for page in range(1, max_pages+1):
        log(f"Trang {page}, đang tìm link...")
        time.sleep(2)
        scroll_like_user(driver,5)

        thelink=None
        alinks=driver.find_elements(By.CSS_SELECTOR,"a")
        for lk in alinks:
            href=lk.get_attribute("href")
            if href and href.strip()==exact_url.strip():
                thelink=lk
                break
        if thelink:
            log(f"✅ Thấy link => {exact_url}, Bấm vào...")
            driver.execute_script("arguments[0].scrollIntoView({block:'center'});", thelink)
            time.sleep(1)
            ActionChains(driver).move_to_element(thelink).click().perform()

            st=time.time()
            while time.time()-st<read_time:
                driver.execute_script("window.scrollBy(0,500);")
                time.sleep(2)
            found=True
            log("Đã đọc xong, dừng.")
            break
        else:
            nxt=driver.find_elements(By.XPATH,"//a[@id='pnnext']")
            if nxt:
                nxt[0].click()
            else:
                log("Hết trang => không thấy link.")
                break
    if not found:
        log("Kết thúc => không tìm thấy link.")

def search_domain(driver, log, keyword, domain, max_pages, read_time=60):
    log(f"Tìm tên miền '{domain}', số trang tìm: {max_pages}")
    driver.get("https://www.google.com")
    close_location_popup(driver)

    box=driver.find_element(By.NAME,"q")
    box.send_keys(keyword)
    time.sleep(random.uniform(1,3))
    box.send_keys(Keys.RETURN)
    close_location_popup(driver)

    found=False
    for page in range(1, max_pages+1):
        log(f"Trang {page}, đang tìm tên miền...")
        time.sleep(2)
        scroll_like_user(driver,5)

        thelink=None
        alinks=driver.find_elements(By.CSS_SELECTOR,"a")
        for lk in alinks:
            href=lk.get_attribute("href")
            if href and domain in href:
                thelink=lk
                break
        if thelink:
            log(f"✅ Thấy tên miền => {thelink.get_attribute('href')}, Bấm vào...")
            driver.execute_script("arguments[0].scrollIntoView({block:'center'});", thelink)
            time.sleep(1)
            ActionChains(driver).move_to_element(thelink).click().perform()

            st=time.time()
            while time.time()-st<read_time:
                driver.execute_script("window.scrollBy(0,500);")
                time.sleep(2)
            found=True
            log("Đã đọc xong => dừng.")
            break
        else:
            nxt=driver.find_elements(By.XPATH,"//a[@id='pnnext']")
            if nxt:
                nxt[0].click()
            else:
                log(f"Hết trang => không thấy tên miền '{domain}'")
                break
    if not found:
        log("Kết thúc tìm tên miền => không thấy link.")

# -------------------------------------------------------------------------------------------
# Thread
# -------------------------------------------------------------------------------------------
class AutomationThread(threading.Thread):
    def __init__(self, log, stop_event,
                 max_pages, read_time,
                 loop_delay, loop_count,
                 headless, w, h,
                 only_keyword, keywords_list,
                 both_alternating,
                 single_keyword, target_str):
        super().__init__()
        self.log=log
        self.stop_event=stop_event
        self.max_pages=max_pages
        self.read_time=read_time
        self.loop_delay=loop_delay
        self.loop_count=loop_count
        self.headless=headless
        self.w=w
        self.h=h

        self.only_keyword=only_keyword
        self.keywords_list=keywords_list
        self.key_index=0

        self.both_alternating=both_alternating
        self.single_keyword=single_keyword.strip()
        self.target_str=target_str.strip()

    def is_exact_url(self, text):
        return text.startswith("http")

    def run(self):
        current_loop=0
        while not self.stop_event.is_set() and (self.loop_count==0 or current_loop<self.loop_count):
            current_loop+=1
            self.log(f"▶ Bắt đầu vòng {current_loop}...")

            # Proxy
            proxy=None
            if global_proxy_manager.proxy_list and global_proxy_manager.rotate_enabled:
                proxy=global_proxy_manager.get_next_proxy()
                self.log(f"⇒ Proxy: {proxy}")

            driver = get_driver(proxy=proxy, headless=self.headless, w=self.w, h=self.h)
            try:
                if self.both_alternating:
                    # xen kẽ: odd => keyword, even => domain/exact
                    if current_loop % 2 == 1:
                        # odd
                        if not self.keywords_list:
                            self.log("⚠ Chưa có danh sách từ khoá => dừng.")
                            break
                        kw = self.keywords_list[self.key_index % len(self.keywords_list)]
                        self.key_index+=1
                        search_keyword_only(driver, self.log, kw, self.max_pages)
                    else:
                        # even => domain / EXACT
                        if self.is_exact_url(self.target_str):
                            search_exact_url(driver, self.log,
                                             self.single_keyword, self.target_str,
                                             self.max_pages, self.read_time)
                        else:
                            domain_=self.target_str.replace("https://","").replace("http://","")
                            search_domain(driver, self.log,
                                          self.single_keyword, domain_,
                                          self.max_pages, self.read_time)
                elif self.only_keyword:
                    if not self.keywords_list:
                        self.log("⚠ Chưa có danh sách từ khoá => dừng.")
                        break
                    kw=self.keywords_list[self.key_index % len(self.keywords_list)]
                    self.key_index+=1
                    search_keyword_only(driver, self.log, kw, self.max_pages)
                else:
                    # domain or EXACT
                    if self.is_exact_url(self.target_str):
                        search_exact_url(driver, self.log,
                                         self.single_keyword, self.target_str,
                                         self.max_pages, self.read_time)
                    else:
                        domain_=self.target_str.replace("https://","").replace("http://","")
                        search_domain(driver, self.log,
                                      self.single_keyword, domain_,
                                      self.max_pages, self.read_time)
            except Exception as e:
                self.log(f"❌ Lỗi: {e}")
            finally:
                driver.quit()

            self.log(f"⏳ Vòng {current_loop} xong, nghỉ {self.loop_delay} giây...")
            for _ in range(self.loop_delay):
                if self.stop_event.is_set():
                    break
                time.sleep(1)
        self.log("✋ Kết thúc vòng lặp.")

# -------------------------------------------------------------------------------------------
# GUI
# -------------------------------------------------------------------------------------------
class AutomationGUI:
    def __init__(self, master):
        self.master=master
        self.master.title("Công cụ SEO - Hỗ trợ SEO từ khóa")
        self.master.geometry("1000x1000")
        self.master.resizable(False,False)

        try:
            self.master.iconbitmap(ICON_PATH)
        except:
            pass

        # Tạo style
        self.style=ttk.Style(self.master)
        self.style.theme_use("clam")

        # Style chung
        self.style.configure("Main.TFrame", background="#f0f0f0")
        # Header
        self.style.configure("Header.TFrame", background="#007ACC")
        self.style.configure("Header.TLabel", background="#007ACC", foreground="white", font=("Helvetica",16,"bold"))
        self.style.configure("SubHeader.TLabel", background="#007ACC", foreground="white", font=("Helvetica",10))
        # LabelFrame
        self.style.configure("Block.TLabelframe", background="#f0f0f0", font=("Helvetica",11,"bold"))
        self.style.configure("Block.TLabelframe.Label", background="#f0f0f0", foreground="#333333",
                             font=("Helvetica", 11, "bold"))
        # TLabel
        self.style.configure("Config.TLabel", background="#f0f0f0", foreground="#333333", font=("Helvetica",10))
        # TCheckbutton
        self.style.configure("Config.TCheckbutton", background="#f0f0f0", foreground="#333333",
                             font=("Helvetica",10), focuscolor="")
        # TButton
        self.style.configure("Big.TButton", font=("Helvetica", 11), padding=5)

        # Main frame
        self.main_frame=ttk.Frame(self.master, style="Main.TFrame")
        self.main_frame.pack(fill="both", expand=True)

        # Header
        self.header_frame=ttk.Frame(self.main_frame, style="Header.TFrame")
        self.header_frame.pack(fill="x")

        # Ảnh
        try:
            author_img = Image.open(AUTHOR_IMAGE_PATH)
            author_img=author_img.resize((60,60), Image.LANCZOS)
            self.author_photo = ImageTk.PhotoImage(author_img)
            self.img_label=ttk.Label(self.header_frame, image=self.author_photo, style="Header.TLabel")
            self.img_label.pack(side="left", padx=10, pady=10)
        except:
            pass

        self.title_label=ttk.Label(self.header_frame, text="Công cụ SEO - Hỗ trợ SEO từ khóa",
                                   style="Header.TLabel")
        self.title_label.pack(anchor="w", padx=5, pady=5)

        self.sub_label=ttk.Label(self.header_frame, text="Phiên bản 1.0.2 - Dev Lý Trần",
                                 style="SubHeader.TLabel")
        self.sub_label.pack(anchor="w", padx=5, pady=5)

        # Khu config
        config_frame=ttk.Frame(self.main_frame, style="Main.TFrame")
        config_frame.pack(fill="x", padx=10, pady=5)

        # LabelFrame cho Tính năng
        feature_lf=ttk.Labelframe(config_frame, text="Tính năng", style="Block.TLabelframe")
        feature_lf.pack(fill="x", pady=5)

        self.only_keyword_var=tk.BooleanVar(value=False)
        onlykw_chk=ttk.Checkbutton(feature_lf, text="Chỉ tìm từ khoá", variable=self.only_keyword_var,
                                   style="Config.TCheckbutton", command=self.update_ui)
        onlykw_chk.pack(anchor="w", padx=5, pady=2)

        self.both_alt_var=tk.BooleanVar(value=False)
        alt_chk=ttk.Checkbutton(feature_lf, text="Chạy xen kẽ",
                                variable=self.both_alt_var, style="Config.TCheckbutton",
                                command=self.update_ui)
        alt_chk.pack(anchor="w", padx=5, pady=2)

        # LabelFrame cho Từ khoá
        keyword_lf=ttk.Labelframe(config_frame, text="Danh sách từ khoá", style="Block.TLabelframe")
        keyword_lf.pack(fill="x", pady=5)

        self.keyword_list_text = scrolledtext.ScrolledText(keyword_lf, wrap=tk.WORD, width=60, height=5, font=("Helvetica",9))
        self.keyword_list_text.pack(fill="x", padx=5, pady=5)

        # LabelFrame cho Domain/EXACT
        domain_lf=ttk.Labelframe(config_frame, text="Cấu hình từ khóa", style="Block.TLabelframe")
        domain_lf.pack(fill="x", pady=5)

        row_d=0
        tk.Label(domain_lf, text="Từ khoá:", bg="#f0f0f0",
                 font=("Helvetica",10)).grid(row=row_d, column=0, sticky="e", padx=5, pady=3)
        self.single_keyword_var=tk.StringVar(value="")
        tk.Entry(domain_lf, textvariable=self.single_keyword_var, width=35,
                 font=("Helvetica",10)).grid(row=row_d, column=1, sticky="w", padx=5, pady=3)
        row_d+=1

        tk.Label(domain_lf, text="Tên miền/Link:", bg="#f0f0f0",
                 font=("Helvetica",10)).grid(row=row_d, column=0, sticky="e", padx=5, pady=3)
        self.target_var=tk.StringVar(value="")
        tk.Entry(domain_lf, textvariable=self.target_var, width=45, font=("Helvetica",10))\
            .grid(row=row_d, column=1, sticky="w", padx=5, pady=3)
        row_d+=1

        # LabelFrame cho Cài đặt
        setting_lf=ttk.Labelframe(config_frame, text="Cài đặt", style="Block.TLabelframe")
        setting_lf.pack(fill="x", pady=5)

        row_s=0
        tk.Label(setting_lf, text="Số trang tìm:", bg="#f0f0f0", font=("Helvetica",10))\
            .grid(row=row_s, column=0, sticky="e", padx=5, pady=3)
        self.max_pages_var=tk.StringVar(value="5")
        tk.Entry(setting_lf, textvariable=self.max_pages_var, width=5, font=("Helvetica",10))\
            .grid(row=row_s, column=1, sticky="w", padx=5, pady=3)
        row_s+=1

        tk.Label(setting_lf, text="Thời gian đọc:", bg="#f0f0f0", font=("Helvetica",10))\
            .grid(row=row_s, column=0, sticky="e", padx=5, pady=3)
        self.read_time_var=tk.StringVar(value="45")
        tk.Entry(setting_lf, textvariable=self.read_time_var, width=5, font=("Helvetica",10))\
            .grid(row=row_s, column=1, sticky="w", padx=5, pady=3)
        row_s+=1

        tk.Label(setting_lf, text="Thời gian nghỉ:", bg="#f0f0f0", font=("Helvetica",10))\
            .grid(row=row_s, column=0, sticky="e", padx=5, pady=3)
        self.loop_delay_var=tk.StringVar(value="120")
        tk.Entry(setting_lf, textvariable=self.loop_delay_var, width=5, font=("Helvetica",10))\
            .grid(row=row_s, column=1, sticky="w", padx=5, pady=3)
        row_s+=1

        tk.Label(setting_lf, text="Số vòng lặp:", bg="#f0f0f0", font=("Helvetica",10))\
            .grid(row=row_s, column=0, sticky="e", padx=5, pady=3)
        self.loop_count_var=tk.StringVar(value="0")
        tk.Entry(setting_lf, textvariable=self.loop_count_var, width=5, font=("Helvetica",10))\
            .grid(row=row_s, column=1, sticky="w", padx=5, pady=3)
        row_s+=1

        tk.Label(setting_lf, text="Kích thước tab (Rộng x Cao):", bg="#f0f0f0", font=("Helvetica",10))\
            .grid(row=row_s, column=0, sticky="e", padx=5, pady=3)
        self.win_w_var=tk.StringVar(value="740")
        self.win_h_var=tk.StringVar(value="740")
        tk.Entry(setting_lf, textvariable=self.win_w_var, width=6, font=("Helvetica",10))\
            .grid(row=row_s, column=1, sticky="w", padx=5, pady=3)
        tk.Label(setting_lf, text="x", bg="#f0f0f0",
                 font=("Helvetica",10)).grid(row=row_s, column=2, sticky="w")
        tk.Entry(setting_lf, textvariable=self.win_h_var, width=6, font=("Helvetica",10))\
            .grid(row=row_s, column=3, sticky="w", padx=2, pady=3)
        row_s+=1

        self.headless_var=tk.BooleanVar(value=False)
        hd_chk=ttk.Checkbutton(setting_lf, text="Chạy ẩn", variable=self.headless_var,
                               style="Config.TCheckbutton")
        hd_chk.grid(row=row_s, column=1, sticky="w", padx=5, pady=3)
        row_s+=1

        # Khu Log
        self.log_frame=ttk.Labelframe(self.main_frame, text="Nhật ký", style="Block.TLabelframe")
        self.log_frame.pack(fill="both", expand=True, padx=10, pady=5)

        self.log_text=scrolledtext.ScrolledText(self.log_frame, wrap=tk.WORD, width=115, height=18,
                                                font=("Helvetica",9))
        self.log_text.pack(fill="both", expand=True, padx=5, pady=5)

        # Nút
        self.btn_frame=ttk.Frame(self.main_frame, style="Main.TFrame")
        self.btn_frame.pack(fill="x", pady=(0,10))

        self.start_btn=ttk.Button(self.btn_frame, text="Bắt Đầu", style="Big.TButton",
                                  command=self.start_automation)
        self.start_btn.pack(side="left", padx=5)

        self.stop_btn=ttk.Button(self.btn_frame, text="Dừng", style="Big.TButton",
                                 command=self.stop_automation, state="disabled")
        self.stop_btn.pack(side="left", padx=5)

        self.reset_btn=ttk.Button(self.btn_frame, text="Khôi Phục", style="Big.TButton",
                                  command=self.reset_form)
        self.reset_btn.pack(side="left", padx=5)

        self.info_btn=ttk.Button(self.btn_frame, text="Thông Tin", style="Big.TButton",
                                 command=self.show_info)
        self.info_btn.pack(side="left", padx=5)

        self.proxy_btn=ttk.Button(self.btn_frame, text="Đổi Proxy", style="Big.TButton",
                                  command=self.show_proxy_config)
        self.proxy_btn.pack(side="left", padx=5)

        self.automation_thread=None
        self.stop_event=threading.Event()

        self.update_ui()

    def update_ui(self):
        only_kw=self.only_keyword_var.get()
        alt_mode=self.both_alt_var.get()
        # Nếu only_kw hoặc alt_mode => enable scrolledtext
        if only_kw or alt_mode:
            self.keyword_list_text.config(state="normal")
        else:
            self.keyword_list_text.config(state="disabled")

    def log(self, msg):
        ts=time.strftime("%H:%M:%S")
        self.log_text.insert(tk.END, f"{ts} - {msg}\n")
        self.log_text.see(tk.END)

    def start_automation(self):
        if self.automation_thread is None or not self.automation_thread.is_alive():
            try:
                mp=int(self.max_pages_var.get().strip())
            except:
                mp=5
            try:
                rt=int(self.read_time_var.get().strip())
            except:
                rt=60
            try:
                ld=int(self.loop_delay_var.get().strip())
            except:
                ld=30
            try:
                lc=int(self.loop_count_var.get().strip())
            except:
                lc=0
            hd=self.headless_var.get()
            try:
                w=int(self.win_w_var.get().strip())
                h=int(self.win_h_var.get().strip())
            except:
                w,h=360,740

            only_kw=self.only_keyword_var.get()
            alt_mode=self.both_alt_var.get()

            raw_kw=self.keyword_list_text.get("1.0", tk.END).strip()
            kw_list=[]
            if (only_kw or alt_mode) and raw_kw:
                lines=raw_kw.split('\n')
                for line in lines:
                    l=line.strip()
                    if l:
                        kw_list.append(l)

            single_kw=self.single_keyword_var.get().strip()
            target_=self.target_var.get().strip()

            self.stop_event.clear()
            self.automation_thread=AutomationThread(
                log=self.log,
                stop_event=self.stop_event,
                max_pages=mp,
                read_time=rt,
                loop_delay=ld,
                loop_count=lc,
                headless=hd,
                w=w,
                h=h,
                only_keyword=only_kw,
                keywords_list=kw_list,
                both_alternating=alt_mode,
                single_keyword=single_kw,
                target_str=target_
            )
            self.automation_thread.start()
            self.log("▶ Bắt đầu quá trình tự động...")
            self.start_btn.config(state="disabled")
            self.stop_btn.config(state="normal")

    def stop_automation(self):
        self.stop_event.set()
        self.log("✋ Dừng quá trình... Đóng tab nếu đang chạy.")
        self.start_btn.config(state="normal")
        self.stop_btn.config(state="disabled")
        if self.automation_thread is not None:
            self.automation_thread.join(timeout=5)

    def reset_form(self):
        self.stop_automation()
        self.log_text.delete("1.0", tk.END)

        self.only_keyword_var.set(False)
        self.both_alt_var.set(False)
        self.keyword_list_text.config(state="normal")
        self.keyword_list_text.delete("1.0", tk.END)
        self.keyword_list_text.config(state="disabled")

        self.single_keyword_var.set("")
        self.target_var.set("")
        self.max_pages_var.set("5")
        self.read_time_var.set("45")
        self.loop_delay_var.set("120")
        self.loop_count_var.set("0")
        self.win_w_var.set("740")
        self.win_h_var.set("740")
        self.headless_var.set(False)

        self.log("Đã khôi phục về mặc định.")
        self.update_ui()

    def show_info(self):
        info_win=tk.Toplevel(self.master)
        info_win.title("Thông tin - Hỗ trợ SEO từ khóa")
        info_win.geometry("480x450")
        info_win.resizable(False, False)

        try:
            info_win.iconbitmap(ICON_PATH)
        except:
            pass

        style_info=ttk.Style(info_win)
        style_info.theme_use("clam")
        style_info.configure("InfoFrame.TFrame", background="#FFFFFF")
        style_info.configure("InfoTitle.TLabel", background="#007ACC", foreground="white",
                             font=("Helvetica",14,"bold"))
        style_info.configure("InfoSubHead.TLabel", background="#FFFFFF", foreground="#333333",
                             font=("Helvetica",11,"bold"))
        style_info.configure("InfoBody.TLabel", background="#FFFFFF", foreground="#333333",
                             font=("Helvetica",10), wraplength=450)
        style_info.configure("InfoButton.TButton", font=("Helvetica",10), padding=5)

        header_frame=ttk.Frame(info_win, style="InfoFrame.TFrame")
        header_frame.pack(fill="x")
        lbl_title=ttk.Label(header_frame, text="Công cụ SEO - Hỗ trợ SEO từ khóa (Version 1.0.2)",
                            style="InfoTitle.TLabel")
        lbl_title.pack(fill="x", pady=10, padx=10)

        content_frame=ttk.Frame(info_win, style="InfoFrame.TFrame", padding=10)
        content_frame.pack(fill="both", expand=True)

        # Ảnh cũ
        try:
            author_img=Image.open(AUTHOR_IMAGE_PATH)
            author_img=author_img.resize((100,100), Image.LANCZOS)
            author_photo=ImageTk.PhotoImage(author_img)
            lbl_img=ttk.Label(content_frame, image=author_photo, style="InfoBody.TLabel")
            lbl_img.image=author_photo
            lbl_img.pack(pady=(0,10))
        except:
            pass

        # Hiệu suất
        lbl_sub1=ttk.Label(content_frame, text="Hiệu suất:", style="InfoSubHead.TLabel")
        lbl_sub1.pack(anchor="w", pady=(0,5))
        lbl_sub1_body=ttk.Label(content_frame, text=(
            "• Tìm kiếm không Click → Tăng số lượt hiển thị, Giảm vị trí trung bình\n"
            "• Tìm kiếm và chọn đọc → Tăng số lượt nhấp, Tăng CTR trung bình\n"
            "• Đẩy từ khóa lên top → Kéo website lên hạng"
        ), style="InfoBody.TLabel")
        lbl_sub1_body.pack(anchor="w", pady=(0,10))

        # Hoạt động
        lbl_sub2=ttk.Label(content_frame, text="Hoạt động:", style="InfoSubHead.TLabel")
        lbl_sub2.pack(anchor="w", pady=(0,5))
        lbl_sub2_body=ttk.Label(content_frame, text=(
            "• Tìm kiếm từ khóa qua chế độ ẩn danh của trình duyệt\n"
            "• Hỗ trợ đổi IP tránh bị quét người dùng ảo\n"
            "• Xoay từ khóa tìm kiếm\n"
            "• Chế độ chạy ẩn không mở tab"
        ), style="InfoBody.TLabel")
        lbl_sub2_body.pack(anchor="w", pady=(0,10))

        # Thông tin
        lbl_sub3=ttk.Label(content_frame, text="Thông tin:", style="InfoSubHead.TLabel")
        lbl_sub3.pack(anchor="w", pady=(0,5))

        lbl_dev=ttk.Label(content_frame, text="• Dev: Lý Trần", style="InfoBody.TLabel")
        lbl_dev.pack(anchor="w")

        lbl_zalo=ttk.Label(content_frame, text="• Zalo: 0876437046", style="InfoBody.TLabel",
                           foreground="blue", cursor="hand2")
        lbl_zalo.pack(anchor="w")
        def open_zalo(*args):
            webbrowser.open("https://zalo.me/+84876437046")
        lbl_zalo.bind("<Button-1>", open_zalo)

        btn_close=ttk.Button(content_frame, text="Đóng", style="InfoButton.TButton",
                             command=info_win.destroy)
        btn_close.pack(pady=(20,0))

    def show_proxy_config(self):
        proxy_win=tk.Toplevel(self.master)
        proxy_win.title("Đổi Proxy")
        proxy_win.geometry("500x400")
        proxy_win.resizable(False,False)
        try:
            proxy_win.iconbitmap(ICON_PATH)
        except:
            pass

        style3=ttk.Style(proxy_win)
        style3.theme_use("clam")
        style3.configure("ProxyFrame.TFrame", background="#FFFFFF")
        style3.configure("ProxyTitle.TLabel", background="#0066CC", foreground="white",
                         font=("Helvetica",13,"bold"))
        style3.configure("ProxyBody.TLabel", background="#FFFFFF", foreground="#333333",
                         font=("Helvetica",10))
        style3.configure("ProxyButton.TButton", font=("Helvetica",10), padding=5)

        head=ttk.Frame(proxy_win, style="ProxyFrame.TFrame")
        head.pack(fill="x")
        lbl_t=ttk.Label(head, text="Cấu hình Proxy", style="ProxyTitle.TLabel")
        lbl_t.pack(fill="x", pady=10, padx=10)

        body=ttk.Frame(proxy_win, style="ProxyFrame.TFrame", padding=10)
        body.pack(fill="both", expand=True)

        ttk.Label(body, text="Nhập danh sách proxy ( IP : Port : Protocol):",
                  style="ProxyBody.TLabel").pack(anchor="w")
        self.proxy_text=scrolledtext.ScrolledText(body, wrap=tk.WORD, width=55, height=10,
                                                  font=("Helvetica",9))
        self.proxy_text.pack(pady=5)

        self.rotate_var=tk.BooleanVar(value=global_proxy_manager.rotate_enabled)
        rotate_check=ttk.Checkbutton(body,text="Xoay vòng proxy",
                                     variable=self.rotate_var)
        rotate_check.pack(anchor="w", pady=5)

        bf=ttk.Frame(body)
        bf.pack(pady=5)

        btn_save=ttk.Button(bf, text="Lưu Proxy", style="ProxyButton.TButton",
                            command=self.save_proxy_list)
        btn_save.grid(row=0, column=0, padx=5)

        btn_chk=ttk.Button(bf, text="Kiểm tra IP", style="ProxyButton.TButton",
                           command=self.check_ip_func)
        btn_chk.grid(row=0, column=1, padx=5)

        btn_close=ttk.Button(bf, text="Đóng", style="ProxyButton.TButton",
                             command=proxy_win.destroy)
        btn_close.grid(row=0, column=2, padx=5)

        # Proxy cũ
        lines=[]
        for (ip,port,prot) in global_proxy_manager.proxy_list:
            lines.append(f"{ip}:{port}:{prot}")
        self.proxy_text.insert(tk.END,"\n".join(lines))

    def save_proxy_list(self):
        text_data=self.proxy_text.get("1.0", tk.END)
        global_proxy_manager.load_from_text(text_data)
        global_proxy_manager.rotate_enabled=self.rotate_var.get()
        self.log(f"Đã lưu {len(global_proxy_manager.proxy_list)} proxy, Xoay={global_proxy_manager.rotate_enabled}")

    def check_ip_func(self):
        ip=check_ip_current()
        self.log(f"IP hiện tại: {ip}")


def main():
    root=tk.Tk()
    gui=AutomationGUI(root)
    root.mainloop()

if __name__=="__main__":
    main()
