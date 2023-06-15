import traceback
import yaml
from addict import Dict
import smtplib
from email.mime.text import MIMEText
from email.header import Header
from email.utils import formataddr
from selenium import webdriver
from selenium.webdriver.common.by import By
from retry import retry

# 加载初始配置
with open("/data/clockin.yml") as file:
    config = Dict(yaml.load(file, Loader=yaml.FullLoader))


def send_mail(content, to_name: str = config.mail.to_name, to_addr: str = config.mail.to_addr):
    msg = MIMEText(content, "plain", "utf-8")
    msg["Subject"] = Header("广州大学自动健康打卡", "utf-8")
    msg["From"] = formataddr((config.mail.from_name, config.mail.from_addr))
    msg["To"] = formataddr((to_name, to_addr))

    server = smtplib.SMTP_SSL(config.mail.server, config.mail.port)

    server.login(config.mail.from_addr, config.mail.password)

    server.sendmail(config.mail.from_addr, [config.mail.to_addr], msg.as_string())
    server.quit()


class Task:
    def __init__(self):
        options = webdriver.ChromeOptions()
        options.add_argument('lang=zh_CN.UTF-8')
        options.add_argument('--disable-gpu')
        options.add_argument('--no-sandbox')
        options.add_argument('--headless')

        self.driver = self.connect(options)
        self.driver.set_page_load_timeout(20)
        self.driver.implicitly_wait(10)

        self.test_driver()

    def __del__(self):
        self.driver.quit()

    @retry(tries=3, delay=5)
    def connect(self, options):
        return webdriver.Remote("http://chrome:4444/wd/hub", options=options)

    @retry(tries=2, delay=1)
    def test_driver(self):
        self.driver.get("https://www.baidu.com/")

    def fake_click(self, element):
        self.driver.execute_script("arguments[0].click();", element)

    def get_message(self):
        elements = self.driver.find_elements(By.CLASS_NAME, 'dialog_content')
        return elements[0].text if len(elements) > 0 else None

    @retry(tries=10, delay=5)
    def do_table(self):
        for control in config.gzhu.controls:
            elements = self.driver.find_elements(By.ID, control)
            if len(elements) > 0:
                self.fake_click(elements[0])

    @retry(tries=10, delay=5)
    def login(self):
        # 输入用户名
        username = self.driver.find_element(By.ID, 'un')
        username.send_keys(config.gzhu.username)

        # 输入密码
        password = self.driver.find_element(By.ID, 'pd')
        password.send_keys(config.gzhu.password)

        # 登录
        login = self.driver.find_element(By.ID, 'index_login_btn')
        self.fake_click(login)

    @retry(tries=10, delay=5)
    def skip_preview(self):
        button = self.driver.find_element(By.ID, 'preview_start_button')
        self.fake_click(button)

    @retry(tries=10, delay=5)
    def submit(self):
        button = self.driver.find_element(By.PARTIAL_LINK_TEXT, '提交')
        self.fake_click(button)

    @retry(tries=10, delay=5)
    def check(self):
        message = self.driver.find_element(By.CLASS_NAME, 'dialog_content').text
        if message != '打卡成功':
            raise Exception("打卡失败。")

    @retry(tries=2, delay=1)
    def run(self):
        # 进入登录页面
        self.driver.get(config.gzhu.url)

        # 登录
        self.login()

        # 跳过预览
        self.skip_preview()

        # 开始上报
        self.do_table()

        # 提交
        self.submit()

        # 检测是否打卡成功
        self.check()


if __name__ == "__main__":
    try:
        Task().run()
        send_mail("打卡成功。")
    except:
        send_mail(f"打卡失败。\n{ traceback.format_exc() }")
