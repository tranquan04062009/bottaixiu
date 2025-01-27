import logging
import os
import requests
import threading
import time
import json
import asyncio
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)
from requests.exceptions import RequestException

# --- CONFIGURATION ---
BOT_TOKEN = "7766543633:AAFnN9tgGWFDyApzplak0tiJTafCxciFydo"
SHARE_COMMAND = "share"
START_COMMAND = "start"
HELP_COMMAND = "help"
STOP_COMMAND = "stop"
STATUS_COMMAND = "status"

SHARE_IN_PROGRESS = {}  # Track shares in progress per user
ACTIVE_THREADS = {}  # Track active threads per user
STOP_REQUESTED = {}  # Track user stop requests
SHARE_COUNT = {}  # Track share count per user
MAX_RETRIES = 3 # Set maximum retries for requests


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
async def share(tach, id_share, context, delay_time):
    user_id = context._user_id
    if user_id not in ACTIVE_THREADS:
        ACTIVE_THREADS[user_id] = {'status': 'started'}

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
    retries = 0
    while retries < MAX_RETRIES:
        try:
             if STOP_REQUESTED.get(user_id, False):
                return
             response = requests.post(f'https://graph.facebook.com/me/feed?link=https://m.facebook.com/{id_share}&published=0&access_token={token}', headers=headers, timeout=10)
             response.raise_for_status()  # Raise HTTPError for bad responses (4xx or 5xx)

             if response.status_code == 200:
                SHARE_COUNT[user_id] = SHARE_COUNT.get(user_id, 0) + 1
                await context.bot.send_message(chat_id=user_id, text=f'Share thành công: {id_share}, Số lần: {SHARE_COUNT[user_id]}')
                break
             else:
                  await context.bot.send_message(chat_id=user_id, text=f"Lỗi share: Status code {response.status_code}")

        except RequestException as e:
           retries +=1
           if retries == MAX_RETRIES:
              await context.bot.send_message(chat_id=user_id, text=f"Lỗi share sau {MAX_RETRIES} lần thử: {e}")
              break
           else:
             logging.warning(f"Lỗi share: {e}, đang thử lại lần {retries}/{MAX_RETRIES}")
             await asyncio.sleep(2) # wait for 2 seconds before retry
        except Exception as e:
           await context.bot.send_message(chat_id=user_id, text=f"Lỗi share: {e}")
           break # Exit retry loop

    await asyncio.sleep(delay_time)

def start_share(update, context, cookie_file, id_share, delay_time, total_share):
    user_id = update.effective_user.id
    STOP_REQUESTED[user_id] = False
    SHARE_COUNT[user_id] = 0

    try:
        if SHARE_IN_PROGRESS.get(user_id, False):
            context.bot.send_message(chat_id=user_id, text="Đang có tiến trình share khác chạy. Vui lòng đợi tiến trình hiện tại kết thúc.")
            return

        SHARE_IN_PROGRESS[user_id] = True
        input_file = cookie_file.read().split('\n')
        all_tokens = get_token(input_file)
        if not all_tokens:
            context.bot.send_message(chat_id=user_id, text="Không tìm thấy token hợp lệ trong file cookie.")
            SHARE_IN_PROGRESS[user_id] = False
            return

        stt = 0
        while True:
            for tach in all_tokens:
                if STOP_REQUESTED.get(user_id, False):
                    context.bot.send_message(chat_id=user_id, text="Tiến trình share đã được dừng.")
                    SHARE_IN_PROGRESS[user_id] = False
                    return

                stt += 1
                thread = threading.Thread(target=lambda: asyncio.run(share(tach, id_share, context, delay_time)))
                thread.start()
                if stt >= total_share:
                    break
            if stt >= total_share:
                break
        context.bot.send_message(chat_id=user_id, text="Hoàn thành quá trình share.")

    except Exception as e:
        context.bot.send_message(chat_id=user_id, text=f"Có lỗi xảy ra: {e}")
    finally:
        SHARE_IN_PROGRESS[user_id] = False
        if user_id in ACTIVE_THREADS:
            ACTIVE_THREADS[user_id]['status'] = 'stopped'

# --- BOT COMMAND HANDLERS ---
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await context.bot.send_message(chat_id=update.effective_chat.id, text="Xin chào! Bot đã sẵn sàng hoạt động. Sử dụng /help để xem hướng dẫn.")

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    help_text = f"""
**Hướng Dẫn Sử Dụng Bot Share:**
Sử dụng các lệnh sau:

/{START_COMMAND}*: Bắt đầu bot.
/{HELP_COMMAND}*: Xem hướng dẫn sử dụng.
/{SHARE_COMMAND}*: Bắt đầu quá trình share.
/{STOP_COMMAND}*: Dừng tiến trình share đang chạy.
/{STATUS_COMMAND}*: Xem trạng thái của tiến trình share.

**Lệnh Share:**
Để sử dụng lệnh share bạn cần làm theo các bước sau:
1. Gửi lệnh: /{SHARE_COMMAND}.
2. Gửi một file chứa cookie (mỗi cookie trên 1 dòng).
3. Gửi id facebook cần share.
4. Gửi delay time mỗi lần share.
5. Gửi số lượng share.
"""
    await context.bot.send_message(chat_id=update.effective_chat.id, text=help_text, parse_mode='Markdown')

async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id in ACTIVE_THREADS:
        status = ACTIVE_THREADS[user_id]['status']
        count = SHARE_COUNT.get(user_id, 0)
        await context.bot.send_message(chat_id=user_id, text=f"Trạng thái: {status}, Đã share {count} lần.")
    else:
        await context.bot.send_message(chat_id=user_id, text="Không có tiến trình share nào đang chạy.")

async def stop_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id in ACTIVE_THREADS:
        STOP_REQUESTED[user_id] = True
        await context.bot.send_message(chat_id=user_id, text="Đã yêu cầu dừng tiến trình share.")
    else:
        await context.bot.send_message(chat_id=user_id, text="Không có tiến trình share nào đang chạy để dừng.")

async def handle_share_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if SHARE_IN_PROGRESS.get(user_id, False):
        await context.bot.send_message(chat_id=user_id, text="Đang có tiến trình share khác chạy. Vui lòng đợi tiến trình hiện tại kết thúc.")
        return
    await context.bot.send_message(chat_id=user_id, text="Vui lòng gửi file chứa cookie (mỗi cookie trên 1 dòng).")
    context.user_data["waiting_for_cookie_file"] = True

async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if context.user_data.get("waiting_for_cookie_file"):
        try:
            file_id = update.message.document.file_id
            file_path = await context.bot.get_file(file_id)
            file = await context.bot.download_file(file_path.file_path)

            with open('temp_cookies.txt', 'wb') as cookie_file:
               cookie_file.write(file)
            with open('temp_cookies.txt', 'r') as cookie_file:
                 await context.bot.send_message(chat_id=user_id, text="Vui lòng nhập ID bài viết hoặc trang bạn muốn share.")
                 context.user_data["waiting_for_cookie_file"] = False
                 context.user_data["waiting_for_id"] = True

        except Exception as e:
             await context.bot.send_message(chat_id=user_id, text=f"Có lỗi xảy ra khi xử lý file: {e}")
    elif context.user_data.get("waiting_for_id"):
      await context.bot.send_message(chat_id=user_id, text="Vui lòng gửi ID bài viết bằng chữ.")
    else:
      return

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if context.user_data.get("waiting_for_id"):
        id_share = update.message.text.strip()
        await context.bot.send_message(chat_id=user_id, text="Vui lòng nhập thời gian delay giữa các lần share (giây).")
        context.user_data["waiting_for_id"] = False
        context.user_data["waiting_for_delay"] = True
        context.user_data["id_share"] = id_share
    elif context.user_data.get("waiting_for_delay"):
        try:
            delay_time = int(update.message.text.strip())
            if delay_time < 0:
                raise ValueError("Delay time phải là số dương.")
            await context.bot.send_message(chat_id=user_id, text="Vui lòng nhập số lượng share bạn muốn thực hiện.")
            context.user_data["waiting_for_delay"] = False
            context.user_data["waiting_for_total"] = True
            context.user_data["delay_time"] = delay_time
        except ValueError as e:
              await context.bot.send_message(chat_id=user_id, text=f"Giá trị không hợp lệ: {e}")
    elif context.user_data.get("waiting_for_total"):
        try:
          total_share = int(update.message.text.strip())
          if total_share < 1:
              raise ValueError("Số lượng share phải lớn hơn 0.")
          await context.bot.send_message(chat_id=user_id, text="Bắt đầu share...")
          context.user_data["waiting_for_total"] = False
          threading.Thread(target=start_share, args=(update, context, open('temp_cookies.txt', 'r'), context.user_data["id_share"], context.user_data["delay_time"], total_share)).start()
        except ValueError as e:
             await context.bot.send_message(chat_id=user_id, text=f"Giá trị không hợp lệ: {e}")
    else:
        return

# --- MAIN FUNCTION ---
if __name__ == '__main__':
    logging.basicConfig(
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        level=logging.INFO
    )
    application = ApplicationBuilder().token(BOT_TOKEN).build()
    application.add_handler(CommandHandler(START_COMMAND, start_command))
    application.add_handler(CommandHandler(HELP_COMMAND, help_command))
    application.add_handler(CommandHandler(STATUS_COMMAND, status_command))
    application.add_handler(CommandHandler(STOP_COMMAND, stop_command))
    application.add_handler(CommandHandler(SHARE_COMMAND, handle_share_command))
    application.add_handler(MessageHandler(filters.Document.ALL, handle_document))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    application.run_polling()