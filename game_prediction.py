import logging
import random
import time
import json
import aiohttp
from concurrent.futures import ThreadPoolExecutor
from telegram import Update, Bot
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters
import threading
import os
import platform
import asyncio
from typing import List, Dict, Callable, Any, Optional

# Cấu hình logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class NGLSpammer:
    def __init__(self, message_template: str, concurrent_requests: int) -> None:
        self.message_template: str = message_template
        self.concurrent_requests: int = concurrent_requests
        self.executor: ThreadPoolExecutor = ThreadPoolExecutor(max_workers=concurrent_requests)
        self.headers: Dict[str, str] = {
            "Accept": "application/json, text/plain, */*",
            "Accept-Encoding": "gzip, deflate, br",
            "Accept-Language": "en-US,en;q=0.9",
            "Connection": "keep-alive",
            "Content-Type": "application/json;charset=UTF-8",
            "Host": "ngl.link",
            "Origin": "https://ngl.link",
            "Referer": "https://ngl.link/",
            "Sec-Ch-Ua": '"Not_A Brand";v="8", "Chromium";v="120", "Google Chrome";v="120"',
            "Sec-Ch-Ua-Mobile": "?0",
            "Sec-Ch-Ua-Platform": f'"{self._get_platform_name()}"',
            "Sec-Fetch-Dest": "empty",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Site": "same-origin",
            "User-Agent": self._generate_user_agent(),
            "X-NGL-Client-Version": "1.2.5"
        }
        self.success_count: int = 0
        self.lock: threading.Lock = threading.Lock()


    def _get_platform_name(self) -> str:
        os_name: str = platform.system()
        if os_name == "Windows":
            return "Windows"
        if os_name == "Darwin":
            return "macOS"
        if os_name == "Linux":
            return "Linux"
        return "Unknown"

    def _generate_random_string(self, length: int) -> str:
        return ''.join(random.choice('abcdefghijklmnopqrstuvwxyz0123456789') for _ in range(length))
    
    def _generate_user_agent(self) -> str:
        os_name: str = platform.system()
        if os_name == "Windows":
             chrome_version: str = f"{random.randint(90, 120)}.0.{random.randint(0, 9999)}.{random.randint(0, 99)}"
             return f"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/{chrome_version} Safari/537.36"
        if os_name == "Darwin":
            safari_version: str = f"{random.randint(600, 610)}.{random.randint(1, 9)}.{random.randint(0, 9)}"
            return f"Mozilla/5.0 (Macintosh; Intel Mac OS X 10_{random.randint(10, 15)}_{random.randint(0, 9)}) AppleWebKit/{safari_version} (KHTML, like Gecko) Version/{random.randint(10, 15)}.0 Safari/{safari_version}"
        if os_name == "Linux":
            firefox_version: str = f"{random.randint(80, 110)}.0"
            return f"Mozilla/5.0 (X11; Linux x86_64; rv:{firefox_version}) Gecko/20100101 Firefox/{firefox_version}"
        return "Mozilla/5.0 (Unknown) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

    async def _send_message(self, target_user_id: str, message_content: str, session: aiohttp.ClientSession) -> None:
        url: str = "https://ngl.link/api/submit"
        device_id: str = self._generate_random_string(32)
        payload: Dict[str, Any] = {
            "deviceId": device_id,
            "gameSlug": None,
            "question": message_content,
            "username": target_user_id
        }
        headers_copy: Dict[str, str] = self.headers.copy()
        headers_copy["User-Agent"] = self._generate_user_agent()

        try:
            async with session.post(url, headers=headers_copy, json=payload) as response:
                response.raise_for_status()  # Raise HTTPError for bad responses (4xx or 5xx)
                response_json: Dict[str, Any] = await response.json()
                with self.lock:
                    if response_json.get('status') == 'success':
                        self.success_count += 1
                        logging.info(f"Tin nhắn gửi thành công tới {target_user_id}: {message_content} (Tổng thành công: {self.success_count})")
                    else:
                        logging.warning(f"Gửi tin nhắn thất bại tới {target_user_id}: {message_content}. Phản hồi: {response_json}")
        except aiohttp.ClientError as e:
            logging.error(f"Lỗi khi gửi tin nhắn tới {target_user_id}: {message_content}. Lỗi: {e}")
        except Exception as e:
            logging.exception(f"Lỗi không xác định khi gửi tin nhắn tới {target_user_id}: {message_content}")



    def _send_messages_sync(self, target_user_id: str, num_messages: int, update_callback: Callable[[int], None]) -> None:
         self.success_count = 0
         async def send_messages_async() -> None:
           async with aiohttp.ClientSession() as session:
             for i in range(num_messages):
                message: str = self.message_template.format(random_string=self._generate_random_string(10))
                await self._send_message(target_user_id, message, session)
                with self.lock:
                    update_callback(self.success_count)
         asyncio.run(send_messages_async())


    def start_spamming(self, target_user_id: str, num_messages: int, update_callback: Callable[[int], None]) -> None:
        logging.info(f"Bắt đầu spam tin nhắn tới {target_user_id} với {num_messages} tin nhắn.")
        start_time: float = time.time()
        self._send_messages_sync(target_user_id, num_messages, update_callback)
        elapsed_time: float = time.time() - start_time
        logging.info(f"Hoàn thành spam. Tổng thời gian: {elapsed_time:.2f} giây. Tổng tin nhắn thành công: {self.success_count}")
    

    async def close(self) -> None:
        await self.executor.shutdown(wait=True)

# --- Telegram Bot ---
class TelegramBot:
    def __init__(self, telegram_token: str, spammer: NGLSpammer) -> None:
        self.bot: Bot = Bot(token=telegram_token)
        self.spammer: NGLSpammer = spammer
        self.application: ApplicationBuilder = (
            ApplicationBuilder()
            .token(telegram_token)
            .build()
        )
        self.application.add_handler(CommandHandler("start", self.start_command))
        self.application.add_handler(CommandHandler("help", self.help_command))
        self.application.add_handler(CommandHandler("spam", self.spam_command))
        self.application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.echo))
        self.spam_progress: Dict[int, Dict[str, int]] = {}


    async def echo(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if update.message:
            await context.bot.send_message(chat_id=update.effective_chat.id, text=update.message.text)

    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        await context.bot.send_message(chat_id=update.effective_chat.id, text="Chào bạn, hãy sử dụng /help để xem các lệnh.")

    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        help_text: str = """
        Các lệnh:
        /start - Khởi động bot.
        /help - Xem danh sách các lệnh.
        /spam <user_id> <số_tin_nhắn> <nội_dung> - Bắt đầu spam tin nhắn ẩn danh. Ví dụ: /spam username 100 Hello there {random_string}.
        """
        await context.bot.send_message(chat_id=update.effective_chat.id, text=help_text)
    
    def _spam_update_callback(self, chat_id: int) -> Callable[[int], None]:
      def callback(success_count: int) -> None:
           if chat_id in self.spam_progress:
             self.spam_progress[chat_id]["current_count"] = success_count
             total_messages: int = self.spam_progress[chat_id]["total_messages"]
             percent: float =  (success_count / total_messages) * 100 if total_messages else 0
             asyncio.create_task(self.bot.send_message(chat_id=chat_id, text=f"Tiến độ spam: {success_count}/{total_messages} ({percent:.2f}%)"))
      return callback

    async def spam_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        try:
            args: List[str] = context.args
            if len(args) < 3:
                await context.bot.send_message(chat_id=update.effective_chat.id, text="Vui lòng sử dụng đúng định dạng: /spam <user_id> <số_tin_nhắn> <nội_dung>")
                return
            target_user_id: str = args[0]
            num_messages: int = int(args[1])
            message_template: str = " ".join(args[2:])
            if num_messages <= 0:
                await context.bot.send_message(chat_id=update.effective_chat.id, text="Số tin nhắn phải lớn hơn 0.")
                return
            logging.info(f"Nhận lệnh spam: {target_user_id}, {num_messages}, {message_template}")
            self.spammer.message_template = message_template
            chat_id: int = update.effective_chat.id
            self.spam_progress[chat_id] = {"total_messages": num_messages, "current_count": 0}
            update_callback: Callable[[int], None] = self._spam_update_callback(chat_id)
            thread: threading.Thread = threading.Thread(target=self.spammer.start_spamming, args=(target_user_id, num_messages, update_callback))
            thread.start()
            await context.bot.send_message(chat_id=chat_id, text="Đang tiến hành spam, vui lòng chờ...")
        except ValueError:
            await context.bot.send_message(chat_id=update.effective_chat.id, text="Số tin nhắn không hợp lệ. Vui lòng nhập một số.")
        except Exception as e:
            logging.exception(f"Lỗi khi thực hiện lệnh spam: {e}")
            await context.bot.send_message(chat_id=update.effective_chat.id, text=f"Có lỗi xảy ra: {e}")
    
    async def run(self) -> None:
        logging.info("Bot telegram đã khởi động...")
        await self.application.run_polling()

async def main() -> None:
    telegram_token: str = "7766543633:AAFnN9tgGWFDyApzplak0tiJTafCxciFydo"  # Thay thế bằng token bot telegram của bạn
    message_template: str = "This is a message sent by bot {random_string}"  # Template tin nhắn, có thể tùy chỉnh
    concurrent_requests: int = 20  # Số lượng request đồng thời
    spammer: NGLSpammer = NGLSpammer(message_template, concurrent_requests)
    bot: TelegramBot = TelegramBot(telegram_token, spammer)
    await bot.run()

if __name__ == "__main__":
    asyncio.run(main())