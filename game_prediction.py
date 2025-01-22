import asyncio
import aiohttp
import json
import random
import string
from typing import Dict
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
import logging
import telegram
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, MessageHandler, filters
import os

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Load environment variables
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
if not TELEGRAM_BOT_TOKEN:
    raise ValueError("Telegram Bot Token not found in environment variables. Please set TELEGRAM_BOT_TOKEN.")
    
class NGLSpammer:
    def __init__(self, target_user_id: str, num_messages: int):
        """
        Initializes the NGL spammer with target user ID and number of messages.
        Removed proxy functionality.

        Args:
            target_user_id (str): The ID of the target NGL user.
            num_messages (int): The number of messages to send.
        """
        self.target_user_id = target_user_id
        self.num_messages = num_messages
        self.headers = {
            "Accept": "application/json, text/plain, */*",
            "Accept-Encoding": "gzip, deflate, br",
            "Accept-Language": "en-US,en;q=0.9",
            "Content-Type": "application/json",
            "Origin": "https://ngl.link",
            "Referer": f"https://ngl.link/{self.target_user_id}",
            "Sec-Ch-Ua": '"Not_A Brand";v="8", "Chromium";v="120", "Google Chrome";v="120"',
            "Sec-Ch-Ua-Mobile": "?0",
            "Sec-Ch-Ua-Platform": '"Windows"',
            "Sec-Fetch-Dest": "empty",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Site": "same-origin",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "x-ngl-csrf-token": self._generate_csrf_token()
        }
        self.base_url = "https://ngl.link/api/submit"
        self.session = aiohttp.ClientSession(headers=self.headers)
        self.executor = ThreadPoolExecutor(max_workers=50)
        self.sent_count = 0
    
    def _generate_csrf_token(self) -> str:
        """
        Generates a random string to be used as a CSRF token.

        Returns:
            str: A random 32-character string.
        """
        return ''.join(random.choice(string.ascii_letters + string.digits) for _ in range(32))

    def _generate_message_payload(self) -> Dict:
        """
        Generates a random message payload with device ID.

        Returns:
            dict: The message payload.
        """
        message_text = f"Spam message {random.randint(1000, 9999)} at {datetime.now()}"
        return {
            "question": message_text,
            "deviceId": self._generate_device_id(),
            "gameSlug": None
        }
    def _generate_device_id(self) -> str:
          """
            Generates a random device ID using the uuid.uuid4 format.

            Returns:
                str: A random device ID.
          """
          return ''.join(random.choice(string.ascii_lowercase + string.digits) for _ in range(32))


    async def _send_message(self, session: aiohttp.ClientSession) -> None:
        """
        Sends a single message to the target user.

        Args:
            session (aiohttp.ClientSession): The aiohttp session.
        """
        try:
            async with session.post(
                self.base_url,
                json=self._generate_message_payload(),
                ssl=False
            ) as response:
                response.raise_for_status()  # Raise HTTPError for bad responses (4xx or 5xx)
                response_text = await response.text()
                response_json = json.loads(response_text)
                if response_json.get("status") == "ok":
                    self.sent_count += 1
                    logging.info(f"Sent message successfully to user {self.target_user_id} . Sent total: {self.sent_count}/{self.num_messages}")
                else:
                     logging.warning(f"Failed to send message to user {self.target_user_id}. Response: {response_json}")
        except aiohttp.ClientError as e:
            logging.error(f"Aiohttp client error: {e}")
        except json.JSONDecodeError as e:
            logging.error(f"Failed to parse response JSON: {e}")
        except Exception as e:
            logging.error(f"An unexpected error occurred: {e}")
    
    async def _spam_messages(self) -> None:
        """
        Spams the target user with messages.
        """
        tasks = []
        for i in range(self.num_messages):
            task = asyncio.ensure_future(self._send_message(self.session))
            tasks.append(task)
            
            if i % 10 == 0:
                await asyncio.sleep(0.1)
        await asyncio.gather(*tasks)

    async def run(self) -> None:
         """
            Runs the spammer.
        """
         try:
             logging.info("Starting NGL spammer...")
             await self._spam_messages()
         except Exception as e:
             logging.error(f"An error occurred during execution: {e}")
         finally:
            await self.session.close()
            self.executor.shutdown(wait=True)
            logging.info("NGL spammer finished.")
    
# Telegram bot handlers
async def start_command(update: telegram.Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
     Sends a welcome message when the /start command is issued
    """
    await context.bot.send_message(chat_id=update.effective_chat.id, text="Hi! I am your NGL spammer bot. Use /spam <user_id> <number_of_messages> to start spamming.")

async def spam_command(update: telegram.Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
     Handles the /spam command.
     Extracts target user ID and number of messages, then calls the NGLSpammer to send spam
    """
    try:
      args = context.args
      if len(args) != 2:
        await context.bot.send_message(chat_id=update.effective_chat.id, text="Usage: /spam <user_id> <number_of_messages>")
        return
      
      target_user_id = args[0]
      num_messages = int(args[1])
      
      if num_messages <= 0:
         await context.bot.send_message(chat_id=update.effective_chat.id, text="Number of messages must be greater than 0.")
         return
      
      await context.bot.send_message(chat_id=update.effective_chat.id, text=f"Starting spamming {target_user_id} with {num_messages} messages...")
      spammer = NGLSpammer(target_user_id, num_messages)
      await spammer.run()
      await context.bot.send_message(chat_id=update.effective_chat.id, text=f"Finished spamming {target_user_id} with {num_messages} messages.")

    except ValueError:
      await context.bot.send_message(chat_id=update.effective_chat.id, text="Invalid number of messages, please use a whole number")
    except Exception as e:
       logging.error(f"An error occurred in spam_command: {e}")
       await context.bot.send_message(chat_id=update.effective_chat.id, text="An error occurred while processing the command.")


async def help_command(update: telegram.Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Sends help instructions when the /help command is issued
    """
    help_text = "Commands:\n/start - Starts the bot.\n/spam <user_id> <number_of_messages> - Starts spamming the NGL user.\n/help - Shows this help message."
    await context.bot.send_message(chat_id=update.effective_chat.id, text=help_text)

async def unknown_command(update: telegram.Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Sends a message when an unknown command is issued
    """
    await context.bot.send_message(chat_id=update.effective_chat.id, text="Sorry, I don't recognize that command. Use /help for available commands.")

# Main function to run the bot
async def main():
    application = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
    
    # Command handlers
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("spam", spam_command))
    application.add_handler(CommandHandler("help", help_command))
    
    # Message handler for unknown commands
    application.add_handler(MessageHandler(filters.COMMAND, unknown_command))

    logging.info("Telegram bot is running...")
    await application.run_polling()

if __name__ == "__main__":
    asyncio.run(main())