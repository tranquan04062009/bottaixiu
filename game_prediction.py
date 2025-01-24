import requests
import telegram
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters
import json
import time
import random
import string
import asyncio

# --- Cấu hình Telegram Bot ---
TELEGRAM_BOT_TOKEN = "7766543633:AAFnN9tgGWFDyApzplak0tiJTafCxciFydo"  # Thay thế bằng token bot Telegram của bạn
ADMIN_USER_ID = 6940071938  # Thay bằng ID tài khoản telegram của bạn

# --- Cấu hình API Tăng Like Free Fire ---
API_URL = "http://ff-community-api.vercel.app/ff.Likes"
# Sử dụng sleep_min và sleep_max để random thời gian nghỉ giữa các lần gửi yêu cầu
SLEEP_MIN = 0.2
SLEEP_MAX = 0.8

# --- Hàm tạo key ngẫu nhiên ---
def generate_random_key(length):
    letters_and_digits = string.ascii_letters + string.digits
    return ''.join(random.choice(letters_and_digits) for i in range(length))

# --- Hàm gửi yêu cầu API tăng like ---
def send_like_request(uid, bot, chat_id):
    key = generate_random_key(32)  # Tạo key ngẫu nhiên 32 ký tự
    params = {"uid": uid, "r": key}

    try:
        response = requests.get(API_URL, params=params)
        response.raise_for_status()  # Báo lỗi nếu response trả về lỗi HTTP

        data = response.json()

        if data and data.get("status") == "Success":
            bot.send_message(chat_id=chat_id, text=f"✅ Đã gửi like thành công cho UID: {uid}. Key: {key}")

        elif data and data.get("status") == "Fail":
            bot.send_message(chat_id=chat_id, text=f"❌ Gửi like thất bại cho UID: {uid}, nguyên nhân: {data.get('message')}")
        
        else:
           bot.send_message(chat_id=chat_id, text=f"❌ Gửi like thất bại cho UID: {uid}, lỗi không xác định")

    except requests.exceptions.RequestException as e:
        bot.send_message(chat_id=chat_id, text=f"❌ Lỗi khi gửi yêu cầu: {e}")


def like_command_handler(update, context):
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id

    if user_id != ADMIN_USER_ID:
        context.bot.send_message(chat_id=chat_id, text="❌ Bạn không có quyền sử dụng lệnh này.")
        return
    
    try:
        uid_to_like = context.args[0]
    except IndexError:
        context.bot.send_message(chat_id=chat_id, text="Vui lòng cung cấp UID Free Fire để tăng like, ví dụ: /like 123456789")
        return

    try:
        int(uid_to_like)
    except ValueError:
        context.bot.send_message(chat_id=chat_id, text="UID phải là một số.")
        return

    num_likes = 1
    if len(context.args) > 1:
        try:
            num_likes = int(context.args[1])
            if num_likes <= 0:
                context.bot.send_message(chat_id=chat_id, text="Số lần like phải lớn hơn 0.")
                return
        except ValueError:
            context.bot.send_message(chat_id=chat_id, text="Số lần like phải là một số.")
            return
    
    context.bot.send_message(chat_id=chat_id, text=f"Đang thực hiện tăng {num_likes} like cho UID: {uid_to_like}...")

    for _ in range(num_likes):
       send_like_request(uid_to_like, context.bot, chat_id)
       time.sleep(random.uniform(SLEEP_MIN, SLEEP_MAX))

def start(update, context):
  context.bot.send_message(chat_id=update.effective_chat.id, text="Chào mừng bạn đến với bot tăng like Free Fire!\n\nĐể sử dụng, hãy dùng lệnh /like <UID> <Số lượng like (tùy chọn)> \n\nLưu ý: Bạn cần phải là admin mới có thể dùng lệnh này.")

def unknown(update, context):
    context.bot.send_message(chat_id=update.effective_chat.id, text="❌ Lệnh không hợp lệ.")


# --- Hàm chính chạy bot ---
def main():
    application = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
    
    # --- Các command ---
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("like", like_command_handler))

    # --- Xử lý các lệnh không xác định ---
    application.add_handler(MessageHandler(filters.COMMAND, unknown))

    application.run_polling()

if __name__ == "__main__":
    main()