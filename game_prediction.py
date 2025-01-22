import os
import asyncio
import aiohttp
import logging
import random
import string
import secrets

from telegram import Bot, Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)
from typing import Dict, List, Optional
from urllib.parse import quote

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)

# Get the token from environment variables
TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
if not TOKEN:
    raise ValueError("Please set the TELEGRAM_BOT_TOKEN environment variable.")

user_spam_sessions: Dict[int, List[Dict]] = {}
blocked_users: List[int] = []

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/119.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Safari/605.1.15",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 13_1) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64; rv:109.0) Gecko/20100101 Firefox/119.0",
    "Mozilla/5.0 (Android 10; Mobile; rv:119.0) Gecko/119.0 Firefox/119.0",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Mobile/15E148 Safari/604.1",
]

async def generate_device_id() -> str:
    """Generates a random device ID."""
    return "".join(random.choice(string.ascii_lowercase + string.digits) for _ in range(42))


async def send_message(
    username: str, message: str, chat_id: int, session_id: int, bot: Bot
) -> None:
    """Sends spam messages using HTTP requests."""
    counter = 0
    while (
        chat_id in user_spam_sessions
        and len(user_spam_sessions[chat_id]) >= session_id
        and user_spam_sessions[chat_id][session_id - 1]["isActive"]
    ):
        try:
            device_id = await generate_device_id()
            url = "https://ngl.link/api/submit"
            headers = {
                "User-Agent": random.choice(USER_AGENTS),
                "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
                "X-NGL-DEVICE-ID": device_id,
                "Origin": "https://ngl.link",
                "Referer": "https://ngl.link/",
            }
            encoded_message = quote(message)
            body = f"username={username}&question={encoded_message}&deviceId={device_id}&gameSlug=&referrer="

            async with aiohttp.ClientSession() as session:
                async with session.post(url, headers=headers, data=body) as response:
                    if response.status != 200:
                        logging.info(f"[Lỗi] Bị giới hạn, status code: {response.status}, đang chờ 5 giây...")
                        await asyncio.sleep(5)
                    else:
                        counter += 1
                        logging.info(f"[Tin nhắn] Phiên {session_id}: Đã gửi {counter} tin nhắn.")
                        await bot.send_message(
                            chat_id, f"Phiên {session_id}: Đã gửi {counter} tin nhắn."
                        )
                    await asyncio.sleep(random.uniform(1, 3))
        except Exception as e:
            logging.error(f"[Lỗi] {e}")
            await asyncio.sleep(2)


def is_blocked(chat_id: int) -> bool:
    """Checks if a user is blocked."""
    return chat_id in blocked_users

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles the /start command."""
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id

    if is_blocked(chat_id):
        await context.bot.send_message(
            chat_id, "Bạn đã bị chặn khỏi việc sử dụng bot này."
        )
        return

    await context.bot.send_message(chat_id, f"Chào mừng! ID Telegram của bạn là: {user_id}")

    if chat_id not in user_spam_sessions:
        user_spam_sessions[chat_id] = []

    keyboard = [
        ["Bắt đầu Spam", "Danh sách Spam"],
    ]
    await context.bot.send_message(
        chat_id,
        "Chọn tính năng bạn muốn sử dụng:",
        reply_markup={"keyboard": keyboard, "resize_keyboard": True},
    )


async def handle_start_spam(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles the 'Start Spam' button."""
    chat_id = update.effective_chat.id

    if is_blocked(chat_id):
        await context.bot.send_message(
            chat_id, "Bạn đã bị chặn khỏi việc sử dụng bot này."
        )
        return

    await context.bot.send_message(chat_id, "Nhập tên người dùng muốn spam:")
    context.user_data["awaiting_username"] = True  # Set flag to wait for username


async def handle_username_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle the username input after the 'Start Spam' button."""
    chat_id = update.effective_chat.id
    username = update.message.text

    if "awaiting_username" in context.user_data and context.user_data["awaiting_username"]:
        context.user_data["username"] = username
        del context.user_data["awaiting_username"]  # Reset the flag
        await context.bot.send_message(chat_id, "Nhập tin nhắn bạn muốn gửi:")
        context.user_data["awaiting_message"] = True  # Set the flag to wait for message
    else:
        return


async def handle_message_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle the message input after the username input."""
    chat_id = update.effective_chat.id
    message = update.message.text
    username = context.user_data.get("username")

    if "awaiting_message" in context.user_data and context.user_data["awaiting_message"] and username:
        del context.user_data["awaiting_message"]
        current_session_id = len(user_spam_sessions.get(chat_id, [])) + 1
        if chat_id not in user_spam_sessions:
             user_spam_sessions[chat_id] = []
        
        session_data = {"id": current_session_id, "username": username, "message": message, "isActive": True}
        user_spam_sessions[chat_id].append(session_data)
        asyncio.create_task(send_message(username, message, chat_id, current_session_id, context.bot))
        await context.bot.send_message(chat_id, f"Phiên spam {current_session_id} đã bắt đầu!")
    else:
        return


async def handle_spam_list(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles the 'Spam List' button."""
    chat_id = update.effective_chat.id

    if is_blocked(chat_id):
        await context.bot.send_message(
            chat_id, "Bạn đã bị chặn khỏi việc sử dụng bot này."
        )
        return

    sessions = user_spam_sessions.get(chat_id, [])
    if sessions:
        list_message = "Danh sách các phiên spam hiện tại:\n"
        buttons = []
        for session in sessions:
             list_message += (
                f"{session['id']}: {session['username']} - {session['message']} "
                f"[Hoạt động: {session['isActive']}]\n"
            )
             buttons.append(
                [{"text": f"Dừng phiên {session['id']}", "callback_data": f"stop_{session['id']}"}]
            )
        await context.bot.send_message(
            chat_id,
            list_message,
            reply_markup={"inline_keyboard": buttons},
        )
    else:
        await context.bot.send_message(chat_id, "Không có phiên spam nào đang hoạt động.")


async def stop_spam_session(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles the stop spam session callback query."""
    query = update.callback_query
    chat_id = query.message.chat.id
    session_id = int(query.data.split("_")[1])
    await query.answer()

    sessions = user_spam_sessions.get(chat_id, [])
    for session in sessions:
        if session["id"] == session_id:
            session["isActive"] = False
            await context.bot.send_message(
                chat_id, f"Phiên spam {session_id} đã bị dừng."
            )
            return
    await context.bot.send_message(
        chat_id, f"Không tìm thấy phiên spam với ID {session_id}."
    )

def main() -> None:
    """Starts the bot."""
    application = ApplicationBuilder().token(TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.Regex("Bắt đầu Spam"), handle_start_spam))
    application.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_username_input))
    application.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message_input))
    application.add_handler(MessageHandler(filters.Regex("Danh sách Spam"), handle_spam_list))
    application.add_handler(CallbackQueryHandler(stop_spam_session, pattern="^stop_"))

    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()