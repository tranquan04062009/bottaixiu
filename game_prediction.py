import sys
import os
import requests
import threading
import time
import json
import telebot
from telebot import types

# --- CONFIGURATION ---
BOT_TOKEN = "7766543633:AAFnN9tgGWFDyApzplak0tiJTafCxciFydo"
SHARE_COMMAND = "/share"
START_COMMAND = "/start"
HELP_COMMAND = "/help"
STOP_COMMAND = "/stop"
STATUS_COMMAND = "/status"

SHARE_IN_PROGRESS = {}  # Track shares in progress per user
ACTIVE_THREADS = {}  # Track active threads per user
STOP_REQUESTED = {} # Track user stop requests
SHARE_COUNT = {}    # Track share count per user


# --- TOKEN EXTRACTION ---
def get_token(input_file):
    gome_token = []
    for cookie in input_file:
        headers = {
            'authority': 'business.facebook.com',
            'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.9',
            'accept-language': 'vi-VN,vi;q=0.9,fr-FR;q=0.8,fr;q=0.7,en-US;q=0.6,en;q=0.5',
            'cache-control': 'max-age=0',
            'cookie': cookie,
            'referer': 'https://www.facebook.com/',
            'sec-ch-ua': '".Not/A)Brand";v="99", "Google Chrome";v="103", "Chromium";v="103"',
            'sec-ch-ua-mobile': '?0',
            'sec-ch-ua-platform': '"Linux"',
            'sec-fetch-dest': 'document',
            'sec-fetch-mode': 'navigate',
            'sec-fetch-site': 'same-origin',
            'sec-fetch-user': '?1',
            'upgrade-insecure-requests': '1',
        }
        try:
            response = requests.get('https://business.facebook.com/content_management', headers=headers)
            home_business = response.text
            token_match = home_business.split('EAAG')[1].split('","')[0]
            cookie_token = f'{cookie}|EAAG{token_match}'
            gome_token.append(cookie_token)
        except Exception:
            pass
    return gome_token

# --- SHARE FUNCTION ---
def share(tach, id_share, bot, message, delay_time):
    user_id = message.from_user.id
    if user_id not in ACTIVE_THREADS:
         ACTIVE_THREADS[user_id] = {'status':'started'}

    cookie = tach.split('|')[0]
    token = tach.split('|')[1]
    headers = {
        'accept': '*/*',
        'accept-encoding': 'gzip, deflate',
        'connection': 'keep-alive',
        'content-length': '0',
        'cookie': cookie,
        'host': 'graph.facebook.com'
    }

    try:
        if STOP_REQUESTED.get(user_id, False):
            return
        response = requests.post(f'https://graph.facebook.com/me/feed?link=https://m.facebook.com/{id_share}&published=0&access_token={token}', headers=headers)
        if response.status_code == 200:
             SHARE_COUNT[user_id] = SHARE_COUNT.get(user_id,0) + 1
             bot.send_message(message.chat.id, f'Share thành công: {id_share}, Số lần: {SHARE_COUNT[user_id]}')
        else :
           bot.send_message(message.chat.id, f"Lỗi share: Status code {response.status_code}")

    except Exception as e:
      bot.send_message(message.chat.id, f"Lỗi share: {e}")
    time.sleep(delay_time)

def start_share(message, bot, cookie_file, id_share, delay_time, total_share):
    user_id = message.from_user.id
    STOP_REQUESTED[user_id] = False
    SHARE_COUNT[user_id] = 0

    try:
        if SHARE_IN_PROGRESS.get(user_id, False):
            bot.reply_to(message, "Đang có tiến trình share khác chạy. Vui lòng đợi tiến trình hiện tại kết thúc.")
            return

        SHARE_IN_PROGRESS[user_id] = True
        input_file = cookie_file.read().split('\n')
        all_tokens = get_token(input_file)
        if not all_tokens:
             bot.send_message(message.chat.id, "Không tìm thấy token hợp lệ trong file cookie.")
             SHARE_IN_PROGRESS[user_id] = False
             return

        stt = 0
        while True:
            for tach in all_tokens:
                if STOP_REQUESTED.get(user_id, False):
                   bot.send_message(message.chat.id, "Tiến trình share đã được dừng.")
                   SHARE_IN_PROGRESS[user_id] = False
                   return

                stt += 1
                thread = threading.Thread(target=share, args=(tach, id_share, bot, message, delay_time))
                thread.start()
                if stt >= total_share:
                    break
            if stt >= total_share:
                break
        bot.send_message(message.chat.id, "Hoàn thành quá trình share.")

    except Exception as e:
        bot.send_message(message.chat.id, f"Có lỗi xảy ra: {e}")
    finally:
        SHARE_IN_PROGRESS[user_id] = False
        if user_id in ACTIVE_THREADS:
            ACTIVE_THREADS[user_id]['status'] = 'stopped'

# --- BOT COMMAND HANDLERS ---
bot = telebot.TeleBot(BOT_TOKEN)

@bot.message_handler(commands=[START_COMMAND])
def send_welcome(message):
    bot.reply_to(message, "Xin chào! Bot đã sẵn sàng hoạt động. Sử dụng /help để xem hướng dẫn.")

@bot.message_handler(commands=[HELP_COMMAND])
def send_help(message):
    help_text = f"""
**Hướng Dẫn Sử Dụng Bot Share:**
Sử dụng các lệnh sau:

*{START_COMMAND}*: Bắt đầu bot.
*{HELP_COMMAND}*: Xem hướng dẫn sử dụng.
*{SHARE_COMMAND}*: Bắt đầu quá trình share.
*{STOP_COMMAND}*: Dừng tiến trình share đang chạy.
*{STATUS_COMMAND}*: Xem trạng thái của tiến trình share.

**Lệnh Share:**
Để sử dụng lệnh share bạn cần làm theo các bước sau:
1. Gửi lệnh: {SHARE_COMMAND}.
2. Gửi một file chứa cookie (mỗi cookie 1 dòng).
3. Gửi id facebook cần share.
4. Gửi delay time mỗi lần share.
5. Gửi số lượng share.
"""
    bot.reply_to(message, help_text, parse_mode='Markdown')

@bot.message_handler(commands=[STATUS_COMMAND])
def status(message):
    user_id = message.from_user.id
    if user_id in ACTIVE_THREADS:
        status = ACTIVE_THREADS[user_id]['status']
        count = SHARE_COUNT.get(user_id, 0)
        bot.send_message(message.chat.id, f"Trạng thái: {status}, Đã share {count} lần.")
    else:
        bot.send_message(message.chat.id, "Không có tiến trình share nào đang chạy.")

@bot.message_handler(commands=[STOP_COMMAND])
def stop_share_command(message):
    user_id = message.from_user.id
    if user_id in ACTIVE_THREADS:
        STOP_REQUESTED[user_id] = True
        bot.reply_to(message, "Đã yêu cầu dừng tiến trình share.")
    else:
        bot.reply_to(message, "Không có tiến trình share nào đang chạy để dừng.")

@bot.message_handler(commands=[SHARE_COMMAND], content_types=['text'])
def handle_share_command(message):
    user_id = message.from_user.id
    if SHARE_IN_PROGRESS.get(user_id, False):
      bot.reply_to(message, "Đang có tiến trình share khác chạy. Vui lòng đợi tiến trình hiện tại kết thúc.")
      return
    bot.reply_to(message, "Vui lòng gửi file chứa cookie (mỗi cookie trên 1 dòng).")
    bot.register_next_step_handler(message, process_cookie_file)

def process_cookie_file(message):
    if message.content_type != 'document':
        bot.reply_to(message, "Vui lòng gửi một file.")
        return
    try:
        file_info = bot.get_file(message.document.file_id)
        downloaded_file = bot.download_file(file_info.file_path)
        with open('temp_cookies.txt', 'wb') as cookie_file:
            cookie_file.write(downloaded_file)
        with open('temp_cookies.txt', 'r') as cookie_file:
            bot.reply_to(message, "Vui lòng nhập ID bài viết hoặc trang bạn muốn share.")
            bot.register_next_step_handler(message, process_id_share, cookie_file)
    except Exception as e:
        bot.reply_to(message, f"Có lỗi xảy ra khi xử lý file: {e}")

def process_id_share(message, cookie_file):
    id_share = message.text.strip()
    bot.reply_to(message, "Vui lòng nhập thời gian delay giữa các lần share (giây).")
    bot.register_next_step_handler(message, process_delay_time, cookie_file, id_share)

def process_delay_time(message, cookie_file, id_share):
    try:
        delay_time = int(message.text.strip())
        if delay_time < 0:
            raise ValueError("Delay time phải là số dương.")
        bot.reply_to(message, "Vui lòng nhập số lượng share bạn muốn thực hiện.")
        bot.register_next_step_handler(message, process_total_share, cookie_file, id_share, delay_time)
    except ValueError as e:
        bot.reply_to(message, f"Giá trị không hợp lệ: {e}")

def process_total_share(message, cookie_file, id_share, delay_time):
    try:
        total_share = int(message.text.strip())
        if total_share < 1 :
            raise ValueError("Số lượng share phải lớn hơn 0.")
        bot.reply_to(message, "Bắt đầu share...")
        threading.Thread(target=start_share, args=(message, bot, cookie_file, id_share, delay_time, total_share)).start()
    except ValueError as e:
        bot.reply_to(message, f"Giá trị không hợp lệ: {e}")

# --- MAIN FUNCTION ---
if __name__ == '__main__':
    bot.polling(none_stop=True)