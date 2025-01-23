from flask import Flask, request, jsonify
import json
import time
import random
from threading import Lock, Thread
import telegram
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
import requests
import logging
import asyncio
import os

# Configuration
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "YOUR_TELEGRAM_BOT_TOKEN")  # Get from env var, default
MAX_LIKES_PER_USER = int(os.environ.get("MAX_LIKES_PER_USER", 50))
API_HOST = os.environ.get("API_HOST", '0.0.0.0')
API_PORT = int(os.environ.get("API_PORT", 5000))
API_BASE_URL = f'http://{API_HOST}:{API_PORT}'

# API Class
class API:
    def __init__(self):
        self.app = Flask(__name__)
        self.likes = {}
        self.users = {}
        self.leaderboard = {
            "kills": [],
            "rank": []
        }
        self.data_lock = Lock()
        self.setup_routes()

    def generate_random_data(self):
        return {
            "uuid": str(random.randint(100000, 999999)) + str(random.randint(100000, 999999)),
            "deviceId": str(random.randint(10000000000000000000, 99999999999999999999)),
            "osVersion": random.choice(["10.1", "11.0", "12.0", "13.0"]),
            "appName": "com.dts.freefireth",
            "appVersion": str(random.randint(100, 999)) + "." + str(random.randint(100, 999)) + "." + str(random.randint(1000, 9999)),
            "time": int(time.time() * 1000)
        }

    def setup_routes(self):
        self.app.add_url_rule('/api/like', methods=['POST', 'GET'], view_func=self.like_api)
        self.app.add_url_rule('/api/user', methods=['POST', 'GET'], view_func=self.user_api)
        self.app.add_url_rule('/api/leaderboard', methods=['POST', 'GET'], view_func=self.leaderboard_api)

    def like_api(self):
        if request.method == 'POST':
            try:
                data = request.get_json()
                if not data or "target_id" not in data:
                    return jsonify({"error": "Invalid request data"}), 400

                target_id = str(data["target_id"])

                with self.data_lock:
                    if target_id not in self.likes:
                        self.likes[target_id] = 0
                    self.likes[target_id] += 1
                print(f"Liked target ID: {target_id}, total likes: {self.likes[target_id]}")
                return jsonify({"success": True, "message": "Liked", "likes": self.likes[target_id]})
            except Exception as e:
                print(f"Error processing request: {e}")
                return jsonify({"error": str(e)}), 500

        elif request.method == "GET":
            action = request.args.get("action")
            if not action:
                return jsonify({"error": "Action parameter is required."}), 400

            if action == "getUserInfo":
                user_id = request.args.get("user_id")
                if not user_id:
                    return jsonify({"error": "user_id is required for getUserInfo."}), 400
                with self.data_lock:
                    if user_id in self.users:
                        return jsonify(self.users[user_id])
                    else:
                        return jsonify({"error": f"User {user_id} not found."}), 404
            elif action == "getLeaderboard":
                leaderboard_type = request.args.get("type", "kills")
                if leaderboard_type not in self.leaderboard:
                    return jsonify({"error": "Invalid leaderboard type"}), 400
                with self.data_lock:
                    return jsonify(self.leaderboard[leaderboard_type])
            elif action == "advancedAction":
                params = {key:value for key, value in request.args.items() if key != "action"}
                return jsonify({"success": True, "action": "advancedAction", "params": params, "data": self.generate_random_data()})
            else:
                return jsonify({"error": "Invalid action."}), 400

    def user_api(self):
        if request.method == "POST":
            try:
                data = request.get_json()
                if not data or "user_id" not in data:
                    return jsonify({"error": "Invalid request data"}), 400
                user_id = str(data["user_id"])

                with self.data_lock:
                    self.users[user_id] = {**data, "registrationTime": int(time.time() * 1000)}

                print(f"User registered {user_id}")
                return jsonify({"success": True, "message": "user registered", "user_id": user_id})
            except Exception as e:
                print(f"Error processing user register: {e}")
                return jsonify({"error": str(e)}), 500
        elif request.method == "GET":
            user_id = request.args.get("user_id")
            if not user_id:
                return jsonify({"error": "User ID is required."}), 400
            with self.data_lock:
                if user_id in self.users:
                    return jsonify(self.users[user_id])
                else:
                    return jsonify({"error": f"User {user_id} not found."}), 404

    def leaderboard_api(self):
        if request.method == "POST":
            try:
                data = request.get_json()
                if not data or "type" not in data or "entries" not in data:
                    return jsonify({"error": "Invalid leaderboard request"}), 400
                leaderboard_type = data["type"]
                entries = data["entries"]
                if leaderboard_type not in self.leaderboard:
                    return jsonify({"error": "Invalid leaderboard type"}), 400
                with self.data_lock:
                    self.leaderboard[leaderboard_type] = entries
                print(f"Leaderboard updated. {leaderboard_type} - {entries}")
                return jsonify({"success": True, "message": f"Leaderboard updated {leaderboard_type}"})
            except Exception as e:
                print(f"Error processing leaderboard update: {e}")
                return jsonify({"error": str(e)}), 500
        elif request.method == "GET":
            leaderboard_type = request.args.get("type", "kills")
            if leaderboard_type not in self.leaderboard:
                return jsonify({"error": "Invalid leaderboard type"}), 400
            with self.data_lock:
                return jsonify(self.leaderboard[leaderboard_type])
    
    def run(self, host='0.0.0.0', port=5000, debug=False):  # debug=False for production use
       self.app.run(host=host, port=port, debug=debug)

# Telegram Bot Class
class TelegramBot:
    def __init__(self, telegram_token, api_url, max_likes_per_user):
        self.telegram_token = telegram_token
        self.api_url = api_url
        self.max_likes_per_user = max_likes_per_user
        self.user_likes = {}
        logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                            level=logging.INFO)
        self.logger = logging.getLogger(__name__)
        self.application = Application.builder().token(self.telegram_token).build()
        self.application.add_handler(CommandHandler("start", self.start_handler))
        self.application.add_handler(CommandHandler("help", self.help_handler))
        self.application.add_handler(CommandHandler("like", self.like_command_handler))
        self.application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.echo_handler))
        self.application.add_error_handler(self.error_handler)

    async def start_handler(self, update: telegram.Update, context: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text("Chào mừng bạn đến với bot tăng like Free Fire! Sử dụng lệnh /like <số lượng> <id game> để tăng like.")

    async def help_handler(self, update: telegram.Update, context: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text("Sử dụng lệnh /like <số lượng> <id game> để tăng like. Ví dụ: /like 10 123456")

    async def _make_api_request(self, method, url, data=None):
          try:
            headers = {'Content-Type': 'application/json'}
            async with asyncio.Lock():
              if method == "GET":
                  loop = asyncio.get_event_loop()
                  response = await loop.run_in_executor(None, requests.get, url, headers=headers)
                  response.raise_for_status()
                  return response.json()
              elif method == "POST":
                  loop = asyncio.get_event_loop()
                  response = await loop.run_in_executor(None, requests.post, url, headers=headers, data=json.dumps(data))
                  response.raise_for_status()
                  return response.json()
              else:
                  raise ValueError(f"Method {method} is not supported.")

          except requests.exceptions.RequestException as e:
              self.logger.error(f"Error during API request: {e}")
              return None
          except ValueError as e:
              self.logger.error(f"Value Error during API request {e}")
              return None
          except Exception as e:
              self.logger.error(f"An unexpected error occurred: {e}")
              return None

    def _generate_random_data(self):
        return {
            "uuid": str(random.randint(100000, 999999)) + str(random.randint(100000, 999999)),
            "deviceId": str(random.randint(10000000000000000000, 99999999999999999999)),
            "osVersion": random.choice(["10.1", "11.0", "12.0", "13.0"]),
            "appName": "com.dts.freefireth",
            "appVersion": str(random.randint(100, 999)) + "." + str(random.randint(100, 999)) + "." + str(random.randint(1000, 9999)),
            "time": int(time.time() * 1000)
        }

    async def like_command_handler(self, update: telegram.Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.message.from_user.id
        if len(context.args) != 2:
            await update.message.reply_text("Sử dụng lệnh đúng: /like <số lượng> <id game>")
            return

        try:
            num_likes = int(context.args[0])
            target_id = str(context.args[1])
        except ValueError:
            await update.message.reply_text("Số lượng likes và ID game phải là số.")
            return

        if user_id not in self.user_likes:
            self.user_likes[user_id] = 0

        if (self.user_likes[user_id] + num_likes) > self.max_likes_per_user:
            await update.message.reply_text(f"Bạn đã đạt giới hạn like trong ngày. Chỉ còn {self.max_likes_per_user - self.user_likes[user_id]} likes.")
            return

        success_count = 0
        for _ in range(num_likes):
            data = {
                "target_id": target_id,
                **self._generate_random_data()
            }
            response = await self._make_api_request("POST", f"{self.api_url}/api/like", data)
            if response and response.get("success"):
                self.user_likes[user_id] += 1
                success_count += 1
                await asyncio.sleep(random.uniform(0.1, 0.3))
            else:
                await update.message.reply_text(f"Lỗi khi tăng like cho ID {target_id}. Vui lòng thử lại sau.")
                return
        await update.message.reply_text(f"Đã tăng {success_count} like cho ID {target_id} thành công.")

    async def echo_handler(self, update: telegram.Update, context: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text("Bạn đã nói: " + update.message.text + ", vui lòng dùng lệnh.")

    async def error_handler(self, update: telegram.Update, context: ContextTypes.DEFAULT_TYPE):
        self.logger.warning('Update "%s" caused error "%s"', update, context.error)

    def run(self):
        self.application.run_polling()

# Main function
def main():
    api_instance = API()
    # Run Flask in main thread and disable debug
    api_instance.run(host=API_HOST, port=API_PORT, debug=False)
    
    bot_instance = TelegramBot(TELEGRAM_TOKEN, API_BASE_URL, MAX_LIKES_PER_USER)
    bot_instance.run()

if __name__ == '__main__':
    main()