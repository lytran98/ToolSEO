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

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.action_chains import ActionChains

def resource_path(relative_path):
    """Trả về đường dẫn tuyệt đối đến file resource, hỗ trợ PyInstaller."""
    try:
        base_path = sys._MEIPASS
    except:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

CHROMEDRIVER_PATH = resource_path("chromedriver.exe")
ICON_PATH = resource_path("lytran.ico")
AUTHOR_IMAGE_PATH = resource_path("lytran.jpg")

# -------------------------------------------------------------------------------------------
# Quản lý Proxy
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
            line = line.strip()
            if not line:
                continue
            parts = line.split(':')
            if len(parts) < 3:
                continue
            ip = parts[0].strip()
            port = parts[1].strip()
            protocol = parts[2].strip().lower()
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
    """Dùng requests để lấy IP hiện tại (không qua proxy)."""
    try:
        r = requests.get("https://api.ipify.org", timeout=5)
        return r.text.strip()
    except:
        return "Không thể lấy IP"

# -------------------------------------------------------------------------------------------
# Tạo WebDriver
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
        Object.defineProperty(navigator, 'webdriver', {
          get: () => undefined
        })
        """
    })
    return driver

def close_location_popup(driver):
    time.sleep(2)
    for _ in range(5):
        buttons = driver.find_elements(
            By.XPATH,
            "//div[contains(text(),'Để sau')] | //button[contains(text(),'Để sau')]"
        )
        if buttons:
            driver.execute_script("arguments[0].click();", buttons[0])
            time.sleep(2)
            return
        time.sleep(1)

def scroll_like_user(driver, duration=5):
    end_time = time.time() + duration
    while time.time() < end_time:
        driver.execute_script("window.scrollBy(0, 400);")
        time.sleep(random.uniform(1,2))

# -------------------------------------------------------------------------------------------
# EXACT URL vs Domain
# -------------------------------------------------------------------------------------------
def search_exact_url(driver, log, keyword, exact_url, max_pages, read_time=60):
    log(f"Tìm URL chính xác: {exact_url}, tối đa {max_pages} trang.")
    driver.get("https://www.google.com")
    close_location_popup(driver)

    box = driver.find_element(By.NAME, "q")
    box.send_keys(keyword)
    time.sleep(random.uniform(1,3))
    box.send_keys(Keys.RETURN)
    close_location_popup(driver)

    for page in range(1, max_pages+1):
        log(f"Trang {page}, tìm URL chính xác.")
        time.sleep(2)
        scroll_like_user(driver, 5)

        found = None
        links = driver.find_elements(By.CSS_SELECTOR, "a")
        for lk in links:
            href = lk.get_attribute("href")
            if href and href.strip() == exact_url.strip():
                found = lk
                break
        if found:
            log(f"✅ Thấy URL chính xác => {exact_url}, click...")
            driver.execute_script("arguments[0].scrollIntoView({block:'center'});", found)
            time.sleep(1)
            ActionChains(driver).move_to_element(found).click().perform()

            st = time.time()
            while time.time() - st < read_time:
                driver.execute_script("window.scrollBy(0,500);")
                time.sleep(2)
            log("Đã đọc URL chính xác xong, dừng.")
            return
        else:
            nxt = driver.find_elements(By.XPATH, "//a[@id='pnnext']")
            if nxt:
                nxt[0].click()
            else:
                log("Hết trang, không thấy URL chính xác.")
                break
    time.sleep(2)
    log("Kết thúc search_exact_url, không tìm thấy link.")

def search_domain(driver, log, keyword, domain, max_pages, read_time=60):
    log(f"Tìm tên miền '{domain}', tối đa {max_pages} trang.")
    driver.get("https://www.google.com")
    close_location_popup(driver)

    box = driver.find_element(By.NAME, "q")
    box.send_keys(keyword)
    time.sleep(random.uniform(1,3))
    box.send_keys(Keys.RETURN)
    close_location_popup(driver)

    for page in range(1, max_pages+1):
        log(f"Trang {page}, tìm tên miền trong link.")
        time.sleep(2)
        scroll_like_user(driver, 5)

        found = None
        links = driver.find_elements(By.CSS_SELECTOR, "a")
        for lk in links:
            href = lk.get_attribute("href")
            if href and domain in href:
                found = lk
                break

        if found:
            log(f"✅ Thấy '{domain}' => {found.get_attribute('href')}, Đang Click...")
            driver.execute_script("arguments[0].scrollIntoView({block:'center'});", found)
            time.sleep(1)
            ActionChains(driver).move_to_element(found).click().perform()

            st = time.time()
            while time.time() - st < read_time:
                driver.execute_script("window.scrollBy(0,500);")
                time.sleep(2)
            log("Đã đọc trang. Dừng.")
            return
        else:
            nxt = driver.find_elements(By.XPATH, "//a[@id='pnnext']")
            if nxt:
                nxt[0].click()
            else:
                log(f"Hết trang => không thấy tên miền '{domain}'")
                break
    time.sleep(2)
    log("Kết thúc tìm tên miền => không thấy link.")

# -------------------------------------------------------------------------------------------
# Thread
# -------------------------------------------------------------------------------------------
class AutomationThread(threading.Thread):
    def __init__(self, log, stop_event,
                 keyword, target_str,
                 max_pages, read_time,
                 loop_delay, loop_count,
                 headless, w, h):
        super().__init__()
        self.log = log
        self.stop_event = stop_event
        self.keyword = keyword.strip()
        self.target_str = target_str.strip()
        self.max_pages = max_pages
        self.read_time = read_time
        self.loop_delay = loop_delay
        self.loop_count = loop_count

        self.headless = headless
        self.w = w
        self.h = h

    def is_exact_url(self, text):
        """Nếu user nhập 'http' => EXACT URL, ngược lại => domain."""
        if text.startswith("http"):
            return True
        return False

    def run(self):
        current_loop = 0
        while not self.stop_event.is_set() and (self.loop_count == 0 or current_loop < self.loop_count):
            current_loop += 1
            self.log(f"▶ Bắt đầu vòng lặp thứ {current_loop}...")

            proxy = None
            if global_proxy_manager.proxy_list and global_proxy_manager.rotate_enabled:
                proxy = global_proxy_manager.get_next_proxy()
                self.log(f"⇒ Đang dùng Proxy: {proxy}")

            driver = get_driver(proxy=proxy, headless=self.headless, w=self.w, h=self.h)
            try:
                if self.is_exact_url(self.target_str):
                    # EXACT URL
                    search_exact_url(driver, self.log, self.keyword, self.target_str,
                                     self.max_pages, self.read_time)
                else:
                    # Domain
                    dom = self.target_str.replace("https://","").replace("http://","")
                    search_domain(driver, self.log, self.keyword, dom,
                                  self.max_pages, self.read_time)
            except Exception as e:
                self.log(f"❌ Lỗi xảy ra: {e}")
            finally:
                driver.quit()

            self.log(f"⏳ Vòng {current_loop} hoàn thành, nghỉ {self.loop_delay}s...")
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
        self.master = master
        self.master.title("Công cụ SEO v1.0.2")
        self.master.geometry("800x740")
        self.master.resizable(False,False)

        try:
            self.master.iconbitmap(ICON_PATH)
        except:
            pass

        self.style = ttk.Style(self.master)
        self.style.theme_use("clam")
        self.style.configure("Main.TFrame", background="#f0f0f0")
        self.style.configure("Header.TFrame", background="#007ACC")
        self.style.configure("Header.TLabel", background="#007ACC", foreground="white", font=("Helvetica",16,"bold"))
        self.style.configure("SubHeader.TLabel", background="#007ACC", foreground="white", font=("Helvetica",10))

        self.main_frame = ttk.Frame(self.master, style="Main.TFrame")
        self.main_frame.pack(fill="both", expand=True)

        # Header
        self.header_frame = ttk.Frame(self.main_frame, style="Header.TFrame")
        self.header_frame.pack(fill="x")

        try:
            im = Image.open(AUTHOR_IMAGE_PATH)
            im = im.resize((60,60),Image.LANCZOS)
            im_ph = ImageTk.PhotoImage(im)
            self.img_label = ttk.Label(self.header_frame, image=im_ph, style="Header.TLabel")
            self.img_label.image = im_ph
            self.img_label.pack(side="left", padx=10, pady=10)
        except:
            pass

        self.title_label = ttk.Label(self.header_frame,
                                     text="Công cụ SEO - Đẩy từ khóa lên top",
                                     style="Header.TLabel")
        self.title_label.pack(anchor="w", padx=5, pady=5)

        self.sub_label = ttk.Label(self.header_frame,
                                   text="Phiên bản 1.0.2 Dev Lý Trần",
                                   style="SubHeader.TLabel")
        self.sub_label.pack(anchor="w", padx=5, pady=5)

        # Khung cấu hình
        config_frame = ttk.Frame(self.main_frame, style="Main.TFrame")
        config_frame.pack(fill="x", padx=10, pady=(0,10))

        row_i = 0
        # Từ khóa
        tk.Label(config_frame,text="Từ khóa Google:",font=("Helvetica",10),bg="#f0f0f0")\
            .grid(row=row_i,column=0,sticky="e",padx=5,pady=5)
        self.keyword_var = tk.StringVar(value="Shop trái cây")
        tk.Entry(config_frame,textvariable=self.keyword_var,width=35,font=("Helvetica",10))\
            .grid(row=row_i,column=1,sticky="w",padx=5,pady=5)
        row_i+=1

        # Tên miền / EXACT URL
        tk.Label(config_frame,text="Tên miền/link:",font=("Helvetica",10),bg="#f0f0f0")\
            .grid(row=row_i,column=0,sticky="e",padx=5,pady=5)
        self.target_var = tk.StringVar(value="ngonfruit.com")
        tk.Entry(config_frame,textvariable=self.target_var,width=45,font=("Helvetica",10))\
            .grid(row=row_i,column=1,sticky="w",padx=5,pady=5)
        row_i+=1

        # Số trang tối đa
        tk.Label(config_frame,text="Số trang tìm:",font=("Helvetica",10),bg="#f0f0f0")\
            .grid(row=row_i,column=0,sticky="e",padx=5,pady=5)
        self.max_pages_var = tk.StringVar(value="5")
        tk.Entry(config_frame,textvariable=self.max_pages_var,width=5,font=("Helvetica",10))\
            .grid(row=row_i,column=1,sticky="w",padx=5,pady=5)
        row_i+=1

        # Thời gian xem trang
        tk.Label(config_frame,text="Thời gian xem trang (s):",font=("Helvetica",10),bg="#f0f0f0")\
            .grid(row=row_i,column=0,sticky="e",padx=5,pady=5)
        self.read_time_var = tk.StringVar(value="45")
        tk.Entry(config_frame,textvariable=self.read_time_var,width=5,font=("Helvetica",10))\
            .grid(row=row_i,column=1,sticky="w",padx=5,pady=5)
        row_i+=1

        # Thời gian nghỉ
        tk.Label(config_frame,text="Thời gian nghỉ giữa các vòng (s):",font=("Helvetica",10),bg="#f0f0f0")\
            .grid(row=row_i,column=0,sticky="e",padx=5,pady=5)
        self.loop_delay_var = tk.StringVar(value="120")
        tk.Entry(config_frame,textvariable=self.loop_delay_var,width=5,font=("Helvetica",10))\
            .grid(row=row_i,column=1,sticky="w",padx=5,pady=5)
        row_i+=1

        # Số vòng lặp
        tk.Label(config_frame,text="Số vòng lặp (0 = vô hạn):",font=("Helvetica",10),bg="#f0f0f0")\
            .grid(row=row_i,column=0,sticky="e",padx=5,pady=5)
        self.loop_count_var = tk.StringVar(value="0")
        tk.Entry(config_frame,textvariable=self.loop_count_var,width=5,font=("Helvetica",10))\
            .grid(row=row_i,column=1,sticky="w",padx=5,pady=5)
        row_i+=1

        # Kích thước tab
        tk.Label(config_frame,text="Kích thước tab (Rộng x Dài):",font=("Helvetica",10),bg="#f0f0f0")\
            .grid(row=row_i,column=0,sticky="e",padx=5,pady=5)
        self.win_w_var=tk.StringVar(value="740")
        self.win_h_var=tk.StringVar(value="740")
        tk.Entry(config_frame,textvariable=self.win_w_var,width=6,font=("Helvetica",10))\
            .grid(row=row_i,column=1,sticky="w",padx=5,pady=5)
        tk.Label(config_frame,text="x",font=("Helvetica",10),bg="#f0f0f0")\
            .grid(row=row_i,column=2,sticky="w")
        tk.Entry(config_frame,textvariable=self.win_h_var,width=6,font=("Helvetica",10))\
            .grid(row=row_i,column=3,sticky="w",padx=2,pady=5)
        row_i+=1

        # Chạy ẩn
        self.headless_var=tk.BooleanVar(value=False)
        hd_check=ttk.Checkbutton(config_frame,text="Chạy ẩn",variable=self.headless_var)
        hd_check.grid(row=row_i,column=1,sticky="w",padx=5,pady=5)
        row_i+=1

        # Khu vực log
        self.log_frame=ttk.Frame(self.main_frame, style="Main.TFrame")
        self.log_frame.pack(fill="both", expand=True, padx=10, pady=(0,10))

        self.log_text=scrolledtext.ScrolledText(self.log_frame, wrap=tk.WORD, width=100, height=15, font=("Helvetica",10))
        self.log_text.pack(fill="both", expand=True)

        # Nút
        self.btn_frame=ttk.Frame(self.main_frame, style="Main.TFrame")
        self.btn_frame.pack(fill="x", pady=(0,10))

        self.start_btn=ttk.Button(self.btn_frame,text="Bắt Đầu",command=self.start_automation)
        self.start_btn.pack(side="left", padx=5)

        self.stop_btn=ttk.Button(self.btn_frame,text="Dừng",command=self.stop_automation,state="disabled")
        self.stop_btn.pack(side="left", padx=5)

        self.reset_btn=ttk.Button(self.btn_frame,text="Khôi Phục",command=self.reset_form)
        self.reset_btn.pack(side="left", padx=5)

        self.info_btn=ttk.Button(self.btn_frame,text="Thông Tin",command=self.show_info)
        self.info_btn.pack(side="left", padx=5)

        self.proxy_btn=ttk.Button(self.btn_frame,text="Đổi Proxy",command=self.show_proxy_config)
        self.proxy_btn.pack(side="left", padx=5)

        self.automation_thread=None
        self.stop_event=threading.Event()

    def log(self, msg):
        ts=time.strftime("%H:%M:%S")
        self.log_text.insert(tk.END, f"{ts} - {msg}\n")
        self.log_text.see(tk.END)

    def start_automation(self):
        if self.automation_thread is None or not self.automation_thread.is_alive():
            kw=self.keyword_var.get().strip()
            tgt=self.target_var.get().strip()
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

            self.stop_event.clear()
            self.automation_thread = AutomationThread(
                log=self.log,
                stop_event=self.stop_event,
                keyword=kw,
                target_str=tgt,
                max_pages=mp,
                read_time=rt,
                loop_delay=ld,
                loop_count=lc,
                headless=hd,
                w=w,
                h=h
            )
            self.automation_thread.start()
            self.log("▶ Bắt đầu quá trình tự động...")
            self.start_btn.config(state="disabled")
            self.stop_btn.config(state="normal")

    def stop_automation(self):
        self.stop_event.set()
        self.log("✋ Dừng quá trình... Sẽ đóng tab nếu đang chạy.")
        self.start_btn.config(state="normal")
        self.stop_btn.config(state="disabled")
        if self.automation_thread is not None:
            self.automation_thread.join(timeout=5)

    def reset_form(self):
        """Nút Reset: dừng thread, xóa log, khôi phục giá trị mặc định."""
        self.stop_automation()
        # Xoá log
        self.log_text.delete("1.0", tk.END)

        # Thiết lập lại
        self.keyword_var.set("Shop trái cây")
        self.target_var.set("ngonfruit.com")
        self.max_pages_var.set("5")
        self.read_time_var.set("45")
        self.loop_delay_var.set("120")
        self.loop_count_var.set("0")
        self.win_w_var.set("740")
        self.win_h_var.set("740")
        self.headless_var.set(False)

        self.log("Đã khôi phục về giá trị mặc định.")

    def show_info(self):
        info_win=tk.Toplevel(self.master)
        info_win.title("Thông tin")
        info_win.geometry("345x345")
        info_win.resizable(False,False)
        try:
            info_win.iconbitmap(ICON_PATH)
        except:
            pass

        style2=ttk.Style(info_win)
        style2.theme_use("clam")
        style2.configure("InfoFrame.TFrame", background="#FFFFFF")
        style2.configure("InfoTitle.TLabel", background="#0066CC", foreground="white",
                         font=("Helvetica",13,"bold"))
        style2.configure("InfoBody.TLabel", background="#FFFFFF", foreground="#333333", font=("Helvetica",10))
        style2.configure("InfoButton.TButton", font=("Helvetica",10), padding=5)

        head=ttk.Frame(info_win, style="InfoFrame.TFrame")
        head.pack(fill="x")
        lbl_title=ttk.Label(head, text="Công Cụ Đẩy Từ Khóa Lên Top Google!", style="InfoTitle.TLabel")
        lbl_title.pack(fill="x", pady=10, padx=10)

        body=ttk.Frame(info_win, style="InfoFrame.TFrame", padding=10)
        body.pack(fill="both", expand=True)

        try:
            im=Image.open(AUTHOR_IMAGE_PATH)
            im=im.resize((100,100),Image.LANCZOS)
            im_ph=ImageTk.PhotoImage(im)
            lbl_im=ttk.Label(body, image=im_ph, style="InfoBody.TLabel")
            lbl_im.image=im_ph
            lbl_im.pack(pady=(0,10))
        except:
            pass

        info_text=(
            "Công cụ SEO - v1.0.2 Dev Lý Trần\n"
            "Hỗ trợ:\n"
            "- Chạy ẩn hoặc hiển thị.\n"
            "- Tùy chỉnh kích thước tab.\n"
            "- Tích hợp proxy + xoay vòng.\n"
            "- Nút Khôi Phục để xóa log và khôi phục giá trị.\n\n"
            "Chúc bạn sử dụng hiệu quả!"
        )
        lbl_body=ttk.Label(body, text=info_text, style="InfoBody.TLabel", justify="left")
        lbl_body.pack(pady=5)

        lbl_ct=ttk.Label(body,text="Liên hệ: Zalo",style="InfoBody.TLabel",foreground="blue",cursor="hand2")
        lbl_ct.pack()
        lbl_ct.bind("<Button-1>", lambda e: webbrowser.open("https://zalo.me/+84876437046"))

        btn_close=ttk.Button(body, text="Đóng", style="InfoButton.TButton", command=info_win.destroy)
        btn_close.pack(pady=(15,0))

    def show_proxy_config(self):
        proxy_win=tk.Toplevel(self.master)
        proxy_win.title("Cấu hình Proxy")
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
        lbl_title=ttk.Label(head, text="Cấu hình Proxy", style="ProxyTitle.TLabel")
        lbl_title.pack(fill="x", pady=10, padx=10)

        body=ttk.Frame(proxy_win, style="ProxyFrame.TFrame", padding=10)
        body.pack(fill="both", expand=True)

        ttk.Label(body, text="Nhập danh sách proxy (IP:Port:Protocol) mỗi dòng:",
                  style="ProxyBody.TLabel").pack(anchor="w")
        self.proxy_text=scrolledtext.ScrolledText(body, wrap=tk.WORD, width=55, height=10,
                                                  font=("Helvetica",9))
        self.proxy_text.pack(pady=5)

        self.rotate_var=tk.BooleanVar(value=global_proxy_manager.rotate_enabled)
        rotate_check=ttk.Checkbutton(body,text="Xoay vòng proxy sau mỗi vòng lặp",
                                     variable=self.rotate_var)
        rotate_check.pack(anchor="w", pady=5)

        bf=ttk.Frame(body)
        bf.pack(pady=5)

        btn_save=ttk.Button(bf, text="Lưu Proxy", style="ProxyButton.TButton",
                            command=self.save_proxy_list)
        btn_save.grid(row=0,column=0,padx=5)

        btn_chk=ttk.Button(bf, text="Check IP", style="ProxyButton.TButton",
                           command=self.check_ip_func)
        btn_chk.grid(row=0,column=1,padx=5)

        btn_close=ttk.Button(bf, text="Đóng", style="ProxyButton.TButton",
                             command=proxy_win.destroy)
        btn_close.grid(row=0,column=2,padx=5)

        # Proxy cũ
        lines=[]
        for (ip,port,prot) in global_proxy_manager.proxy_list:
            lines.append(f"{ip}:{port}:{prot}")
        self.proxy_text.insert(tk.END, "\n".join(lines))

    def save_proxy_list(self):
        text_data=self.proxy_text.get("1.0", tk.END)
        global_proxy_manager.load_from_text(text_data)
        global_proxy_manager.rotate_enabled=self.rotate_var.get()
        self.log(f"Đã lưu {len(global_proxy_manager.proxy_list)} proxy, Xoay = {global_proxy_manager.rotate_enabled}")

    def check_ip_func(self):
        ip=check_ip_current()
        self.log(f"IP hiện tại: {ip}")


def main():
    root=tk.Tk()
    gui=AutomationGUI(root)
    root.mainloop()

if __name__=="__main__":
    main()
