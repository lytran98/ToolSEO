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

# -------------------------------------------------------------------------------------------
# Quản lý Proxy
# -------------------------------------------------------------------------------------------
class ProxyManager:
    """
    Lớp quản lý danh sách proxy và trạng thái xoay vòng proxy.
    Mỗi proxy dạng (ip, port, protocol), xoay vòng sau mỗi vòng lặp nếu bật rotate_enabled.
    """
    def __init__(self):
        self.proxy_list = []      # [(ip, port, protocol), ...]
        self.rotate_enabled = False
        self.current_index = 0

    def load_from_text(self, text):
        """Đọc danh sách proxy từ text, mỗi dòng: ip:port:protocol."""
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
            protocol = parts[2].strip().lower()  # "http", "socks5", ...
            self.proxy_list.append((ip, port, protocol))

    def get_next_proxy(self):
        """Trả về proxy hiện tại, nếu rotate_enabled=True thì chuyển sang proxy kế tiếp."""
        if not self.proxy_list:
            return None
        proxy = self.proxy_list[self.current_index]
        if self.rotate_enabled:
            self.current_index = (self.current_index + 1) % len(self.proxy_list)
        return proxy

global_proxy_manager = ProxyManager()

# -------------------------------------------------------------------------------------------
# Kiểm tra IP
# -------------------------------------------------------------------------------------------
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
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.action_chains import ActionChains

def resource_path(relative_path):
    """Trả về đường dẫn tuyệt đối đến file resource (hỗ trợ PyInstaller)."""
    try:
        base_path = sys._MEIPASS
    except:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

CHROMEDRIVER_PATH = resource_path("chromedriver.exe")
ICON_PATH = resource_path("lytran.ico")
AUTHOR_IMAGE_PATH = resource_path("lytran.jpg")

def get_driver(proxy=None):
    """
    Tạo WebDriver Chrome ở chế độ ẩn danh, tắt geolocation, popup, ...
    Nếu proxy != None, cấu hình ip:port:protocol vào Chrome.
    """
    options = webdriver.ChromeOptions()
    options.add_argument("--incognito")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("--disable-features=WebAssembly,TFLite")
    options.add_argument("--disable-popup-blocking")
    options.add_argument("--disable-geolocation")
    prefs = {"profile.default_content_setting_values.geolocation": 2}
    options.add_experimental_option("prefs", prefs)

    if proxy:
        ip, port, protocol = proxy
        if protocol not in ["http", "socks4", "socks5"]:
            protocol = "http"
        proxy_str = f"{protocol}://{ip}:{port}"
        options.add_argument(f"--proxy-server={proxy_str}")

    service = Service(CHROMEDRIVER_PATH)
    driver = webdriver.Chrome(service=service, options=options)
    driver.set_window_size(360, 740)
    return driver

# -------------------------------------------------------------------------------------------
# Đóng popup "Để sau"
# -------------------------------------------------------------------------------------------
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

# -------------------------------------------------------------------------------------------
# Cuộn trang
# -------------------------------------------------------------------------------------------
def scroll_like_user(driver, duration=5):
    end_time = time.time() + duration
    while time.time() < end_time:
        driver.execute_script("window.scrollBy(0, 400);")
        time.sleep(random.uniform(1, 2))

# -------------------------------------------------------------------------------------------
# Tìm domain
# -------------------------------------------------------------------------------------------
def search_and_scroll(driver, log_callback, keyword, domain, max_pages, reading_duration):
    log_callback(f"Đang tìm '{domain}' với từ khóa '{keyword}' trên tối đa {max_pages} trang.")
    driver.get("https://www.google.com")
    close_location_popup(driver)

    search_box = driver.find_element(By.NAME, "q")
    search_box.send_keys(keyword)
    time.sleep(random.uniform(1, 3))
    search_box.send_keys(Keys.RETURN)
    close_location_popup(driver)
    
    for page in range(1, max_pages + 1):
        log_callback(f"🔎 Kiểm tra trang {page}...")
        time.sleep(2)
        scroll_like_user(driver, duration=5)
        search_results = driver.find_elements(By.CSS_SELECTOR, "a")
        for result in search_results:
            link = result.get_attribute("href")
            if link and domain in link:
                log_callback(f"🔍 Tìm thấy {link} trên trang {page}, thực hiện click...")
                driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", result)
                time.sleep(1)
                actions = ActionChains(driver)
                actions.move_to_element(result).click().perform()

                start_time = time.time()
                while time.time() - start_time < reading_duration:
                    driver.execute_script("window.scrollBy(0, 500);")
                    time.sleep(2)
                log_callback("📖 Đọc xong. Dừng tìm kiếm.")
                return
        else:
            next_buttons = driver.find_elements(By.XPATH, "//a[@id='pnnext']")
            if next_buttons:
                next_buttons[0].click()
            else:
                log_callback(f"⛔ Không tìm thấy '{domain}' ở trang {page}.")
                break
    time.sleep(5)

# -------------------------------------------------------------------------------------------
# Thread tự động
# -------------------------------------------------------------------------------------------
class AutomationThread(threading.Thread):
    def __init__(self, log_callback, stop_event, keyword, domain,
                 max_pages, reading_duration, cycle_delay, cycle_count):
        super().__init__()
        self.log_callback = log_callback
        self.stop_event = stop_event
        self.keyword = keyword
        self.domain = domain
        self.max_pages = max_pages
        self.reading_duration = reading_duration
        self.cycle_delay = cycle_delay
        self.cycle_count = cycle_count  # 0 => vô hạn

    def run(self):
        current_cycle = 0
        while not self.stop_event.is_set() and (self.cycle_count == 0 or current_cycle < self.cycle_count):
            current_cycle += 1
            self.log_callback(f"▶ Bắt đầu chu kỳ (Vòng {current_cycle})...")

            # Lấy proxy nếu có & rotate_enabled
            proxy = None
            if global_proxy_manager.proxy_list and global_proxy_manager.rotate_enabled:
                proxy = global_proxy_manager.get_next_proxy()
                self.log_callback(f"⇒ Đang dùng Proxy: {proxy}")

            driver = get_driver(proxy=proxy)
            try:
                search_and_scroll(driver, self.log_callback,
                                  self.keyword, self.domain,
                                  self.max_pages, self.reading_duration)
            except Exception as e:
                self.log_callback(f"❌ Lỗi: {e}")
            finally:
                driver.quit()
            self.log_callback(f"⏳ Chu kỳ hoàn thành. Nghỉ {self.cycle_delay} giây...")

            for _ in range(self.cycle_delay):
                if self.stop_event.is_set():
                    break
                time.sleep(1)
        self.log_callback("✋ Tự động dừng lại.")

# -------------------------------------------------------------------------------------------
# Giao diện
# -------------------------------------------------------------------------------------------
class AutomationGUI:
    def __init__(self, master):
        self.master = master
        self.master.title("Tool SEO")
        self.master.geometry("700x680")
        self.master.resizable(False, False)

        try:
            self.master.iconbitmap(ICON_PATH)
        except:
            pass

        self.style = ttk.Style(self.master)
        self.style.theme_use("clam")
        self.style.configure("Main.TFrame", background="#f0f0f0")
        self.style.configure("Header.TFrame", background="#007ACC")
        self.style.configure("Header.TLabel", background="#007ACC", foreground="white", font=("Helvetica", 16, "bold"))
        self.style.configure("SubHeader.TLabel", background="#007ACC", foreground="white", font=("Helvetica", 10))
        self.style.configure("TButton", font=("Helvetica", 12), padding=5)
        self.style.map("TButton",
            foreground=[("active", "#005A8C")],
            background=[("active", "#e0e0e0")]
        )

        self.main_frame = ttk.Frame(self.master, style="Main.TFrame")
        self.main_frame.pack(fill="both", expand=True)

        # Header
        self.header_frame = ttk.Frame(self.main_frame, style="Header.TFrame")
        self.header_frame.pack(fill="x")

        # Ảnh tác giả
        try:
            author_img = Image.open(AUTHOR_IMAGE_PATH)
            # Sửa ANTIALIAS => Image.LANCZOS
            author_img = author_img.resize((60, 60), Image.LANCZOS)
            self.author_photo = ImageTk.PhotoImage(author_img)
            self.img_label = ttk.Label(self.header_frame, image=self.author_photo, style="Header.TLabel")
            self.img_label.pack(side="left", padx=10, pady=10)
        except Exception as e:
            print("Không tải được ảnh tác giả:", e)

        self.title_label = ttk.Label(self.header_frame, text="Tool SEO", style="Header.TLabel")
        self.title_label.pack(anchor="w", padx=5, pady=5)

        self.sub_label = ttk.Label(self.header_frame,
                                   text="Tác giả: Lý Trần\nLiên hệ: Zalo",
                                   style="SubHeader.TLabel")
        self.sub_label.pack(anchor="w", padx=5, pady=5)

        self.zalo_link = ttk.Label(self.header_frame, text="(Mở Zalo)", foreground="white",
                                   cursor="hand2", style="SubHeader.TLabel")
        self.zalo_link.pack(anchor="w", padx=5)
        self.zalo_link.bind("<Button-1>", lambda e: webbrowser.open("https://zalo.me/+84876437046"))

        # Cấu hình
        config_frame = ttk.Frame(self.main_frame, style="Main.TFrame")
        config_frame.pack(fill="x", padx=10, pady=(0, 10))

        # Thông số
        tk.Label(config_frame, text="Từ khóa tìm kiếm:", font=("Helvetica", 10), background="#f0f0f0")\
            .grid(row=0, column=0, sticky="e", padx=5, pady=5)
        self.keyword_var = tk.StringVar(value="Nulled Congnghe360")
        tk.Entry(config_frame, textvariable=self.keyword_var, width=30, font=("Helvetica", 10))\
            .grid(row=0, column=1, sticky="w", padx=5, pady=5)

        tk.Label(config_frame, text="Domain cần tìm:", font=("Helvetica", 10), background="#f0f0f0")\
            .grid(row=1, column=0, sticky="e", padx=5, pady=5)
        self.domain_var = tk.StringVar(value="congnghe360.com")
        tk.Entry(config_frame, textvariable=self.domain_var, width=30, font=("Helvetica", 10))\
            .grid(row=1, column=1, sticky="w", padx=5, pady=5)

        tk.Label(config_frame, text="Số trang tìm tối đa:", font=("Helvetica", 10), background="#f0f0f0")\
            .grid(row=2, column=0, sticky="e", padx=5, pady=5)
        self.max_pages_var = tk.StringVar(value="5")
        tk.Entry(config_frame, textvariable=self.max_pages_var, width=5, font=("Helvetica", 10))\
            .grid(row=2, column=1, sticky="w", padx=5, pady=5)

        tk.Label(config_frame, text="Thời gian xem trang (s):", font=("Helvetica", 10), background="#f0f0f0")\
            .grid(row=3, column=0, sticky="e", padx=5, pady=5)
        self.reading_duration_var = tk.StringVar(value="60")
        tk.Entry(config_frame, textvariable=self.reading_duration_var, width=5, font=("Helvetica", 10))\
            .grid(row=3, column=1, sticky="w", padx=5, pady=5)

        tk.Label(config_frame, text="Thời gian nghỉ vòng lặp (s):", font=("Helvetica", 10), background="#f0f0f0")\
            .grid(row=4, column=0, sticky="e", padx=5, pady=5)
        self.cycle_delay_var = tk.StringVar(value="30")
        tk.Entry(config_frame, textvariable=self.cycle_delay_var, width=5, font=("Helvetica", 10))\
            .grid(row=4, column=1, sticky="w", padx=5, pady=5)

        tk.Label(config_frame, text="Số vòng lặp (0: vô hạn):", font=("Helvetica", 10), background="#f0f0f0")\
            .grid(row=5, column=0, sticky="e", padx=5, pady=5)
        self.cycle_count_var = tk.StringVar(value="0")
        tk.Entry(config_frame, textvariable=self.cycle_count_var, width=5, font=("Helvetica", 10))\
            .grid(row=5, column=1, sticky="w", padx=5, pady=5)

        # Log
        self.log_frame = ttk.Frame(self.main_frame, style="Main.TFrame")
        self.log_frame.pack(fill="both", expand=True, padx=10, pady=(0,10))
        self.log_text = scrolledtext.ScrolledText(self.log_frame, wrap=tk.WORD, width=80,
                                                  height=15, font=("Helvetica", 10))
        self.log_text.pack(fill="both", expand=True)

        # Nút
        self.button_frame = ttk.Frame(self.main_frame, style="Main.TFrame")
        self.button_frame.pack(fill="x", pady=(0,10))

        self.start_button = ttk.Button(self.button_frame, text="Bắt Đầu", command=self.start_automation)
        self.start_button.pack(side="left", padx=20)

        self.stop_button = ttk.Button(self.button_frame, text="Kết Thúc",
                                      command=self.stop_automation, state="disabled")
        self.stop_button.pack(side="left", padx=20)

        self.info_button = ttk.Button(self.button_frame, text="Info", command=self.show_info)
        self.info_button.pack(side="left", padx=20)

        self.proxy_button = ttk.Button(self.button_frame, text="Đổi Proxy", command=self.show_proxy_config)
        self.proxy_button.pack(side="left", padx=20)

        self.automation_thread = None
        self.stop_event = threading.Event()

    def log(self, message):
        timestamp = time.strftime('%H:%M:%S')
        self.log_text.insert(tk.END, f"{timestamp} - {message}\n")
        self.log_text.see(tk.END)

    def start_automation(self):
        if self.automation_thread is None or not self.automation_thread.is_alive():
            keyword = self.keyword_var.get().strip()
            domain = self.domain_var.get().strip()
            try:
                max_pages = int(self.max_pages_var.get().strip())
            except:
                max_pages = 3
            try:
                reading_duration = int(self.reading_duration_var.get().strip())
            except:
                reading_duration = 60
            try:
                cycle_delay = int(self.cycle_delay_var.get().strip())
            except:
                cycle_delay = 30
            try:
                cycle_count = int(self.cycle_count_var.get().strip())
            except:
                cycle_count = 0

            self.stop_event.clear()
            self.automation_thread = AutomationThread(
                self.log, self.stop_event,
                keyword, domain, max_pages,
                reading_duration, cycle_delay,
                cycle_count
            )
            self.automation_thread.start()
            self.log("▶ Tự động bắt đầu.")
            self.start_button.config(state="disabled")
            self.stop_button.config(state="normal")

    def stop_automation(self):
        self.stop_event.set()
        self.log("✋ Dừng tự động... Đóng tất cả các tab và thoát chương trình.")
        self.start_button.config(state="normal")
        self.stop_button.config(state="disabled")
        if self.automation_thread is not None:
            self.automation_thread.join(timeout=5)
        self.master.destroy()
        sys.exit(0)

    def show_info(self):
        info_win = tk.Toplevel(self.master)
        info_win.title("Thông tin Tool SEO")
        info_win.geometry("460x460")
        info_win.resizable(False, False)
        try:
            info_win.iconbitmap(ICON_PATH)
        except:
            pass

        style2 = ttk.Style(info_win)
        style2.theme_use("clam")
        style2.configure("InfoFrame.TFrame", background="#FFFFFF")
        style2.configure("InfoTitle.TLabel", background="#0066CC", foreground="white",
                         font=("Helvetica", 13, "bold"))
        style2.configure("InfoBody.TLabel", background="#FFFFFF", foreground="#333333",
                         font=("Helvetica", 10))
        style2.configure("InfoButton.TButton", font=("Helvetica", 10), padding=5)

        header_info = ttk.Frame(info_win, style="InfoFrame.TFrame")
        header_info.pack(fill="x")
        title_label = ttk.Label(header_info, text="Thông tin Tool SEO", style="InfoTitle.TLabel")
        title_label.pack(fill="x", pady=10, padx=10)

        content_info = ttk.Frame(info_win, style="InfoFrame.TFrame", padding=10)
        content_info.pack(fill="both", expand=True)

        try:
            author_img = Image.open(AUTHOR_IMAGE_PATH)
            author_img = author_img.resize((100, 100), Image.LANCZOS)
            author_photo = ImageTk.PhotoImage(author_img)
            img_label = ttk.Label(content_info, image=author_photo, style="InfoBody.TLabel")
            img_label.image = author_photo
            img_label.pack(pady=(0, 10))
        except:
            pass

        info_text = (
            "Tool SEO\n\n"
            "Tác giả: Lý Trần\n"
            "Hướng dẫn sử dụng:\n"
            "- Nhập từ khóa tìm kiếm, domain cần tìm, số trang.\n"
            "- Thời gian xem trang, nghỉ vòng lặp, số vòng.\n"
            "- Nhấn 'Bắt Đầu' => Tool chạy.\n"
            "- Khi domain tìm thấy => click & cuộn.\n"
            "- Nhấn 'Kết Thúc' => đóng tất cả tab.\n"
        )
        info_label = ttk.Label(content_info, text=info_text, style="InfoBody.TLabel", justify="left")
        info_label.pack(pady=5)

        link_label = ttk.Label(content_info, text="Liên hệ: Zalo", style="InfoBody.TLabel",
                               foreground="blue", cursor="hand2")
        link_label.pack()
        link_label.bind("<Button-1>", lambda e: webbrowser.open("https://zalo.me/+84876437046"))

        close_btn = ttk.Button(content_info, text="Đóng", style="InfoButton.TButton",
                               command=info_win.destroy)
        close_btn.pack(pady=(15,0))

    # ---------------------------------------------------------------------------------------
    # Cửa sổ Đổi Proxy
    # ---------------------------------------------------------------------------------------
    def show_proxy_config(self):
        proxy_win = tk.Toplevel(self.master)
        proxy_win.title("Cấu hình Proxy")
        proxy_win.geometry("500x400")
        proxy_win.resizable(False, False)
        try:
            proxy_win.iconbitmap(ICON_PATH)
        except:
            pass

        style3 = ttk.Style(proxy_win)
        style3.theme_use("clam")
        style3.configure("ProxyFrame.TFrame", background="#FFFFFF")
        style3.configure("ProxyTitle.TLabel", background="#0066CC", foreground="white",
                         font=("Helvetica", 13, "bold"))
        style3.configure("ProxyBody.TLabel", background="#FFFFFF", foreground="#333333",
                         font=("Helvetica", 10))
        style3.configure("ProxyButton.TButton", font=("Helvetica", 10), padding=5)

        header_frame = ttk.Frame(proxy_win, style="ProxyFrame.TFrame")
        header_frame.pack(fill="x")
        title_label = ttk.Label(header_frame, text="Cấu hình Proxy", style="ProxyTitle.TLabel")
        title_label.pack(fill="x", pady=10, padx=10)

        content_frame = ttk.Frame(proxy_win, style="ProxyFrame.TFrame", padding=10)
        content_frame.pack(fill="both", expand=True)

        ttk.Label(content_frame, text="Nhập danh sách proxy (IP:Port:Protocol) mỗi dòng:",
                  style="ProxyBody.TLabel").pack(anchor="w")
        self.proxy_text = scrolledtext.ScrolledText(content_frame, wrap=tk.WORD, width=55, height=10, font=("Helvetica", 9))
        self.proxy_text.pack(pady=5)

        self.rotate_var = tk.BooleanVar(value=global_proxy_manager.rotate_enabled)
        rotate_check = ttk.Checkbutton(content_frame, text="Xoay vòng proxy sau mỗi vòng lặp", variable=self.rotate_var)
        rotate_check.pack(anchor="w", pady=5)

        button_frame = ttk.Frame(content_frame)
        button_frame.pack(pady=5)

        load_btn = ttk.Button(button_frame, text="Lưu Proxy", style="ProxyButton.TButton",
                              command=self.save_proxy_list)
        load_btn.grid(row=0, column=0, padx=5)

        checkip_btn = ttk.Button(button_frame, text="Check IP", style="ProxyButton.TButton",
                                 command=self.check_ip_func)
        checkip_btn.grid(row=0, column=1, padx=5)

        close_btn = ttk.Button(button_frame, text="Đóng", style="ProxyButton.TButton",
                               command=proxy_win.destroy)
        close_btn.grid(row=0, column=2, padx=5)

        # Load sẵn proxy cũ
        lines = []
        for (ip, port, protocol) in global_proxy_manager.proxy_list:
            lines.append(f"{ip}:{port}:{protocol}")
        self.proxy_text.insert(tk.END, "\n".join(lines))

    def save_proxy_list(self):
        text_data = self.proxy_text.get("1.0", tk.END)
        global_proxy_manager.load_from_text(text_data)
        global_proxy_manager.rotate_enabled = self.rotate_var.get()
        self.log(f"Đã lưu {len(global_proxy_manager.proxy_list)} proxy. Xoay vòng = {global_proxy_manager.rotate_enabled}")

    def check_ip_func(self):
        current_ip = check_ip_current()
        self.log(f"IP hiện tại: {current_ip}")


def main():
    root = tk.Tk()
    gui = AutomationGUI(root)
    root.mainloop()

if __name__ == "__main__":
    main()
