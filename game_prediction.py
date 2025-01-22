import os
import requests
import json
import time
import threading
import random
import hashlib
import subprocess
import sys
import re
import socket
import telegram
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters
import traceback
from queue import Queue

# --- Cấu hình ban đầu ---
VERSION = "1.3"
MODEL_ID = hashlib.sha256(os.urandom(32)).hexdigest()
INITIAL_LEARNING_RATE = 0.001
MAX_THREADS = 32
LEARNING_RATE_DECAY = 0.9999
DATA_DIRECTORY = os.path.join(os.path.expanduser("~"), "ai_data_" + MODEL_ID)
LOG_FILE = os.path.join(DATA_DIRECTORY, "ai_log.txt")
ERROR_LOG_FILE = os.path.join(DATA_DIRECTORY, "ai_error_log.txt")
CONFIG_FILE = os.path.join(DATA_DIRECTORY, "ai_config.json")
CACHE_DIRECTORY = os.path.join(DATA_DIRECTORY, "cache")
TELEGRAM_BOT_TOKEN = "7766543633:AAFnN9tgGWFDyApzplak0tiJTafCxciFydo"  # Cần thay thế bằng token của bot
TELEGRAM_ADMIN_ID = 6940071938  # Thay thế bằng admin ID
MESSAGE_QUEUE_MAX_SIZE = 100

os.makedirs(DATA_DIRECTORY, exist_ok=True)
os.makedirs(CACHE_DIRECTORY, exist_ok=True)

def log(message):
    with open(LOG_FILE, "a") as f:
        f.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {message}\n")
    print(message)

def error_log(message):
    with open(ERROR_LOG_FILE, "a") as f:
        f.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {message}\n")
    print(f"ERROR: {message}")
    try:
        global bot  # Khai báo global để truy cập biến bot
        if bot and TELEGRAM_ADMIN_ID:
            bot.send_message(chat_id=TELEGRAM_ADMIN_ID, text=f"ERROR: {message}")
    except Exception as e:
        print(f"Lỗi khi gửi thông báo lỗi: {e}")

def load_config():
    try:
        with open(CONFIG_FILE, "r") as f:
            return json.load(f)
    except FileNotFoundError:
        return {
            "learning_rate": INITIAL_LEARNING_RATE,
            "last_updated": time.time(),
            "version": VERSION,
            "telegram_enabled": False,
            "last_model_size": 0  # Khởi tạo last_model_size
        }
    except json.JSONDecodeError as e:
        error_log(f"Lỗi khi giải mã file cấu hình JSON: {e}. Sử dụng cấu hình mặc định.")
        return {
            "learning_rate": INITIAL_LEARNING_RATE,
            "last_updated": time.time(),
            "version": VERSION,
            "telegram_enabled": False,
            "last_model_size": 0
        }
    except Exception as e:
        error_log(f"Lỗi khi tải cấu hình: {e}. Sử dụng cấu hình mặc định.")
        return {
            "learning_rate": INITIAL_LEARNING_RATE,
            "last_updated": time.time(),
            "version": VERSION,
            "telegram_enabled": False,
            "last_model_size": 0
        }

def save_config(config):
    try:
        with open(CONFIG_FILE, "w") as f:
            json.dump(config, f, indent=4)
    except Exception as e:
        error_log(f"Lỗi khi lưu cấu hình: {e}")

config = load_config()

# --- Khởi tạo các lớp ---
class DataAcquisition:
    def __init__(self):
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }

    def fetch_url(self, url):
        try:
            response = requests.get(url, headers=self.headers, timeout=10)
            response.raise_for_status()
            return response.text
        except requests.exceptions.RequestException as e:
            error_log(f"Lỗi khi tải dữ liệu từ {url}: {e}")
            return None

    def fetch_cached(self, url):
        cache_file = os.path.join(CACHE_DIRECTORY, hashlib.sha256(url.encode()).hexdigest())
        if os.path.exists(cache_file):
            try:
                with open(cache_file, "r", encoding="utf-8") as f:
                    return f.read()
            except Exception as e:
                error_log(f"Lỗi khi tải dữ liệu từ cache {cache_file}: {e}")
                return self.fetch_url(url)  # Fallback to fetching if cache fails
        else:
            data = self.fetch_url(url)
            if data:
                try:
                    with open(cache_file, "w", encoding="utf-8") as f:
                        f.write(data)
                except Exception as e:
                    error_log(f"Lỗi khi lưu vào cache {cache_file}: {e}")
                return data
            return None

    def search_google(self, query):
        search_url = f"https://www.google.com/search?q={query}"
        content = self.fetch_cached(search_url)
        if not content:
            return []
        urls = re.findall(r'href="([^"]+)"', content)
        filtered_urls = [u for u in urls if u.startswith("http") and not u.startswith("https://www.google.com")]
        return filtered_urls

    def scrape_text_from_urls(self, urls):
        texts = []
        for url in urls:
            content = self.fetch_cached(url)
            if content:
                text_content = re.sub(r'<.*?>', '', content)
                texts.append(text_content)
            else:
                error_log(f"Không thể lấy nội dung từ {url}")
        return texts

    def crawl_recursive(self, seed_url, depth=2, max_urls=50):
        if depth <= 0 or len(self.crawled_urls) >= max_urls:
            return

        if seed_url in self.crawled_urls:
            return

        self.crawled_urls.add(seed_url)
        content = self.fetch_cached(seed_url)

        if content:
            new_urls = re.findall(r'href="([^"]+)"', content)
            new_urls = [url for url in new_urls if url.startswith("http") and not url.startswith("https://www.google.com")]
            random.shuffle(new_urls)

            for url in new_urls[:10]:  # Giới hạn số lượng url tiếp theo để crawl trong mỗi lượt
                if len(self.crawled_urls) >= max_urls:
                    break
                self.crawl_recursive(url, depth - 1, max_urls)

    def start_crawling(self, seed_urls, depth=2, max_urls=50):
        self.crawled_urls = set()
        for seed in seed_urls:
            self.crawl_recursive(seed, depth, max_urls)

        return list(self.crawled_urls)

class DataProcessing:
    def __init__(self):
        self.stopwords = self.load_stopwords()

    def load_stopwords(self):
        try:
            stopwords = set()
            with open(os.path.join(os.path.dirname(__file__), "stopwords.txt"), "r", encoding="utf-8") as f:
                for line in f:
                    stopwords.add(line.strip())
            return stopwords
        except FileNotFoundError:
            error_log("Không tìm thấy file stopword")
            return set()
        except Exception as e:
            error_log(f"Lỗi khi tải stopwords: {e}")
            return set()

    def clean_text(self, text):
        text = re.sub(r'[^a-zA-Z0-9\s]', '', text).lower()
        words = text.split()
        words = [word for word in words if word not in self.stopwords]
        return " ".join(words)

    def tokenize_text(self, text):
        return text.split()

    def process_text_data(self, texts):
        if not isinstance(texts, list):
            error_log("Dữ liệu đầu vào không phải là list")
            return []
        cleaned_texts = [self.clean_text(text) for text in texts]
        tokenized_texts = [self.tokenize_text(text) for text in cleaned_texts]
        return tokenized_texts

class ModelTraining:
    def __init__(self):
        self.model = {}

    def update_model(self, tokenized_texts):
      if not tokenized_texts:
        return
      for tokens in tokenized_texts:
          for i, token in enumerate(tokens):
              if token not in self.model:
                  self.model[token] = {}

              if i < len(tokens) - 1:
                  next_token = tokens[i + 1]
                  if next_token not in self.model[token]:
                      self.model[token][next_token] = 0
                  self.model[token][next_token] += 1

    def generate_text(self, seed=""):
        current = seed
        output = [seed]
        for _ in range(20):
            if current not in self.model:
                break
            next_tokens = self.model[current]
            if not next_tokens:
                break

            total = sum(next_tokens.values())
            if total <= 0:
                break
            rand = random.randint(0, total - 1)

            cumulative = 0

            for token, count in next_tokens.items():
                cumulative += count
                if rand < cumulative:
                    current = token
                    output.append(token)
                    break

        return " ".join(output)

    def save_model(self):
        try:
            model_file = os.path.join(DATA_DIRECTORY, "ai_model.json")
            with open(model_file, "w") as f:
                json.dump(self.model, f, indent=4)
            log("Model đã được lưu")
        except Exception as e:
            error_log(f"Lỗi khi lưu model: {e}")

    def load_model(self):
        try:
            model_file = os.path.join(DATA_DIRECTORY, "ai_model.json")
            with open(model_file, "r") as f:
                self.model = json.load(f)
            log("Model đã được tải")
        except FileNotFoundError:
            log("Không tìm thấy model, sẽ tạo model mới")
        except json.JSONDecodeError as e:
            error_log(f"Lỗi khi giải mã file model JSON: {e}")
        except Exception as e:
            error_log(f"Lỗi khi tải model: {e}")

    def get_model_data(self):
        return self.model

class SelfImprovement:
    def __init__(self, data_acquisition, data_processing, model_training):
        self.data_acquisition = data_acquisition
        self.data_processing = data_processing
        self.model_training = model_training

    def adjust_learning_rate(self):
        config["learning_rate"] *= LEARNING_RATE_DECAY
        config["last_updated"] = time.time()
        save_config(config)
        log(f"Đã điều chỉnh learning rate: {config['learning_rate']:.6f}")

    def analyze_performance(self):
        # Phần này sẽ phân tích và đưa ra các cải tiến dựa trên model, đánh giá hiệu suất
        log("Bắt đầu phân tích hiệu suất...")
        model_data = self.model_training.get_model_data()
        model_size = sys.getsizeof(json.dumps(model_data))

        log(f"Kích thước model hiện tại: {model_size} bytes")

        # Kiểm tra xem có bao nhiêu từ có trong từ điển
        num_words = len(model_data)
        log(f"Số lượng từ trong model: {num_words}")

        # Tính mức độ tăng trưởng của model

        size_diff = model_size - config.get("last_model_size", 0)
        if size_diff > 0:
            log(f"Model đã tăng kích thước: {size_diff} bytes")
        else:
            log(f"Model không tăng kích thước hoặc giảm: {size_diff} bytes")
        config["last_model_size"] = model_size

        # Tính số lượng kết nối giữa các từ (context)
        context_count = 0
        for word_data in model_data.values():
            context_count += len(word_data)

        log(f"Tổng số ngữ cảnh từ model: {context_count}")

        # Kiểm tra thời gian chạy
        start_time = time.time()
        self.model_training.generate_text("hello")
        end_time = time.time()
        gen_time = end_time - start_time
        log(f"Thời gian sinh văn bản: {gen_time} giây")

        #TODO: Cải tiến logic phân tích hiệu suất

    def self_improve(self, seed_urls, max_urls=50, depth=2):
        log("Bắt đầu quá trình tự cải thiện...")

        crawled_urls = self.data_acquisition.start_crawling(seed_urls, depth, max_urls)
        log(f"Số URL đã cào được: {len(crawled_urls)}")
        if not crawled_urls:
            error_log("Không thể tìm thấy URL để tự học")
            return

        texts = self.data_acquisition.scrape_text_from_urls(crawled_urls)
        log(f"Số dữ liệu text đã cào: {len(texts)}")

        if not texts:
            error_log("Không có dữ liệu text để học")
            return

        tokenized_texts = self.data_processing.process_text_data(texts)
        self.model_training.update_model(tokenized_texts)

        self.analyze_performance()
        self.adjust_learning_rate()
        self.model_training.save_model()

        log("Quá trình tự cải thiện hoàn tất.")

class CodeExecution:
    def __init__(self):
        pass

    def execute_code(self, code, timeout=10):
        try:
            temp_file = "temp_code.py"
            with open(temp_file, "w", encoding="utf-8") as f:
                f.write(code)

            process = subprocess.Popen(["python", temp_file], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            stdout, stderr = process.communicate(timeout=timeout)
            os.remove(temp_file)

            if stderr:
                error_log(f"Lỗi khi chạy code: {stderr.decode()}")
                return None
            return stdout.decode()
        except subprocess.TimeoutExpired:
            error_log(f"Chạy code quá thời gian quy định ({timeout}s)")
            process.kill()
            return None
        except FileNotFoundError:
            error_log("Không tìm thấy python")
            return None
        except Exception as e:
            error_log(f"Lỗi khi chạy code: {e}")
            return None

    def run_command(self, command, timeout=10):
        try:
            process = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            stdout, stderr = process.communicate(timeout=timeout)

            if stderr:
                error_log(f"Lỗi khi chạy lệnh: {stderr.decode()}")
                return None

            return stdout.decode()
        except subprocess.TimeoutExpired:
            error_log(f"Chạy lệnh quá thời gian quy định ({timeout}s)")
            process.kill()
            return None
        except Exception as e:
            error_log(f"Lỗi khi chạy lệnh: {e}")
            return None

class ProgrammingLearning:
    def __init__(self, data_acquisition, data_processing, model_training, code_execution):
        self.data_acquisition = data_acquisition
        self.data_processing = data_processing
        self.model_training = model_training
        self.code_execution = code_execution

    def fetch_programming_tutorials(self):
        search_query = "python programming tutorial"
        log(f"Tìm kiếm hướng dẫn lập trình: {search_query}")
        urls = self.data_acquisition.search_google(search_query)
        return urls

    def learn_from_tutorials(self, urls):
        if not urls:
            error_log("Không tìm thấy hướng dẫn lập trình")
            return False

        texts = self.data_acquisition.scrape_text_from_urls(urls[:5])
        if not texts:
            error_log("Không có dữ liệu text để học lập trình")
            return False

        tokenized_texts = self.data_processing.process_text_data(texts)
        self.model_training.update_model(tokenized_texts)
        log("Đã học lập trình từ các tutorial")
        return True

    def test_code_generation(self):
        # Lấy một từ ngẫu nhiên từ từ điển của model, và tạo code ngẫu nhiên theo model
        model_data = self.model_training.get_model_data()
        if not model_data:
            error_log("Không có dữ liệu trong model để tạo code")
            return

        keys = list(model_data.keys())
        if not keys:
            error_log("Không có key trong model")
            return

        start_word = random.choice(keys)

        log(f"Bắt đầu sinh code từ: {start_word}")
        generated_code = self.model_training.generate_text(start_word)

        if not generated_code or len(generated_code.split()) < 5:
            error_log(f"Code không đủ điều kiện hoặc không tạo ra được code, bỏ qua")
            return

        log(f"Code đã được tạo ra:\n {generated_code}")

        if generated_code:
            log("Bắt đầu kiểm tra code")
            output = self.code_execution.execute_code(generated_code)
            if output:
                log(f"Code đã chạy thành công, kết quả:\n {output}")
            else:
                error_log("Code không chạy được hoặc lỗi")
        else:
            error_log("Không thể tạo code")

    def start_learning_programming(self):
        log("Bắt đầu quá trình tự học lập trình...")
        urls = self.fetch_programming_tutorials()
        if self.learn_from_tutorials(urls):
            self.test_code_generation()
        log("Kết thúc quá trình tự học lập trình.")


class TelegramIntegration:
    def __init__(self, model_training, code_execution, data_acquisition):
        self.model_training = model_training
        self.code_execution = code_execution
        self.data_acquisition = data_acquisition
        self.updater = None
        self.bot = None
        self.message_queue = Queue(maxsize=MESSAGE_QUEUE_MAX_SIZE)
        self.processing_thread = None
        self.stop_processing = False

    def start_bot(self, token):
        try:
            self.bot = telegram.Bot(token=token)
            self.updater = Updater(token=token, use_context=True)

            dp = self.updater.dispatcher

            dp.add_handler(CommandHandler("start", self.start_command))
            dp.add_handler(CommandHandler("help", self.help_command))
            dp.add_handler(MessageHandler(Filters.text, self.handle_message))

            self.updater.start_polling()
            log("Telegram bot đã được khởi động.")
            self.processing_thread = threading.Thread(target=self._process_messages)
            self.stop_processing = False
            self.processing_thread.start()
        except telegram.error.InvalidToken:
            error_log("Token telegram không hợp lệ, xin hãy kiểm tra lại.")
            return False
        except Exception as e:
            error_log(f"Lỗi khi khởi động bot telegram: {e}")
            return False
        return True

    def stop_bot(self):
        if self.updater:
            self.stop_processing = True
            if self.processing_thread and self.processing_thread.is_alive():
                self.processing_thread.join()
            self.updater.stop()
            log("Telegram bot đã dừng.")

    def start_command(self, update, context):
        context.bot.send_message(chat_id=update.effective_chat.id, text="Xin chào! Tôi là AI tự học. Hãy nhập tin nhắn để trò chuyện với tôi.")

    def help_command(self, update, context):
        context.bot.send_message(chat_id=update.effective_chat.id, text="Tôi có thể trả lời các câu hỏi, chạy code python, và thực hiện lệnh.")

    def handle_message(self, update, context):
        try:
            if not self.message_queue.full():
                self.message_queue.put((update, context))
            else:
                log(f"Telegram: Message queue is full. Dropping message from user {update.effective_chat.id}")
                context.bot.send_message(chat_id=update.effective_chat.id, text="Xin lỗi, tôi đang bận xử lý tin nhắn khác. Hãy thử lại sau.")
        except Exception as e:
            error_log(f"Lỗi khi thêm message vào queue {e}")

    def _process_messages(self):
        while not self.stop_processing:
            try:
                if not self.message_queue.empty():
                    update, context = self.message_queue.get()
                    user_input = update.message.text
                    log(f"Telegram: Nhận tin nhắn từ user {update.effective_chat.id}: {user_input}")

                    if user_input.lower().startswith("chạy code:"):
                        code = user_input[len("chạy code:"):].strip()
                        log(f"Telegram: Nhận code: {code}")
                        result = self.code_execution.execute_code(code)
                        if result:
                            context.bot.send_message(chat_id=update.effective_chat.id, text=f"Kết quả code:\n{result}")
                        else:
                            context.bot.send_message(chat_id=update.effective_chat.id, text="Lỗi khi chạy code.")
                    elif user_input.lower().startswith("chạy lệnh:"):
                        command = user_input[len("chạy lệnh:"):].strip()
                        log(f"Telegram: Nhận lệnh: {command}")
                        result = self.code_execution.run_command(command)
                        if result:
                            context.bot.send_message(chat_id=update.effective_chat.id, text=f"Kết quả lệnh:\n{result}")
                        else:
                            context.bot.send_message(chat_id=update.effective_chat.id, text="Lỗi khi chạy lệnh.")
                    elif user_input.lower().startswith("tìm kiếm:"):
                        query = user_input[len("tìm kiếm:"):].strip()
                        log(f"Telegram: Tìm kiếm: {query}")
                        search_results = self.data_acquisition.search_google(query)
                        if search_results:
                            message_text = "Kết quả tìm kiếm:\n"
                            for result in search_results:
                                message_text += f"- {result}\n"
                            context.bot.send_message(chat_id=update.effective_chat.id, text=message_text)

                            texts = self.data_acquisition.scrape_text_from_urls(search_results[:5])
                            if texts:
                                tokenized_texts = data_processing.process_text_data(texts)
                                model_training.update_model(tokenized_texts)
                                log("Model đã được cập nhật từ kết quả tìm kiếm trên telegram")
                        else:
                            context.bot.send_message(chat_id=update.effective_chat.id, text="Không tìm thấy kết quả tìm kiếm")
                    else:
                        response = self.model_training.generate_text(user_input)
                        context.bot.send_message(chat_id=update.effective_chat.id, text=f"AI: {response}")
                    self.message_queue.task_done()
                else:
                   time.sleep(0.1)
            except Exception as e:
                error_log(f"Lỗi trong message processing: {e}\n{traceback.format_exc()}")
                
# --- Các hàm chính ---
def main_loop():
    global bot
    bot = None
    data_acquisition = DataAcquisition()
    data_processing = DataProcessing()
    model_training = ModelTraining()
    code_execution = CodeExecution()
    self_improvement = SelfImprovement(data_acquisition, data_processing, model_training)
    programming_learning = ProgrammingLearning(data_acquisition, data_processing, model_training, code_execution)
    telegram_integration = TelegramIntegration(model_training, code_execution, data_acquisition)

    model_training.load_model()

    log(f"AI v{VERSION} model {MODEL_ID} đã được khởi động.")

    if config.get("telegram_enabled", False):
        log("Telegram bot đang được bật.")
        if not telegram_integration.start_bot(TELEGRAM_BOT_TOKEN):
            config["telegram_enabled"] = False
            save_config(config)
            log("Tắt telegram bot do lỗi.")
        else:
            bot = telegram_integration.bot

    try:
        while True:
            # Tự động học và cải thiện
            if time.time() - config["last_updated"] > 60 * 60 * 1:  # 1 giờ
                seed_urls = ["https://en.wikipedia.org/wiki/Main_Page", "https://vnexpress.net"]
                self_improvement.self_improve(seed_urls, 25, 2)  # Giới hạn url và độ sâu
                programming_learning.start_learning_programming()

            if not config.get("telegram_enabled", False):
                 # If Telegram is not enabled, exit the loop as no user input is possible in this case
                log("Telegram not enabled, exiting main loop")
                break
            
            try:
                user_input = input("Bạn: ")
            except EOFError:
                log("EOF received, exiting main loop")
                break # Exit the loop when an EOFError is caught
                
            if user_input.lower() == "thoát":
                log("AI đã thoát.")
                break
            elif user_input.lower() == "bật telegram":
                config["telegram_enabled"] = True
                save_config(config)
                if telegram_integration.start_bot(TELEGRAM_BOT_TOKEN):
                    log("Telegram đã được bật.")
                    bot = telegram_integration.bot
                else:
                    config["telegram_enabled"] = False
                    save_config(config)
                    log("Không thể bật telegram")
            elif user_input.lower().startswith("chạy code:"):
                code = user_input[len("chạy code:"):].strip()
                log(f"Code nhận được: {code}")
                result = code_execution.execute_code(code)
                if result:
                    print(f"Kết quả code:\n{result}")
            elif user_input.lower().startswith("chạy lệnh:"):
                command = user_input[len("chạy lệnh:"):].strip()
                log(f"Lệnh nhận được: {command}")
                result = code_execution.run_command(command)
                if result:
                    print(f"Kết quả lệnh:\n{result}")
            elif user_input.lower().startswith("tìm kiếm:"):
                query = user_input[len("tìm kiếm:"):].strip()
                log(f"Tìm kiếm: {query}")
                search_results = data_acquisition.search_google(query)
                if search_results:
                    print("Kết quả tìm kiếm:")
                    for result in search_results:
                        print(f"- {result}")

                    texts = data_acquisition.scrape_text_from_urls(search_results[:5])
                    if texts:
                        tokenized_texts = data_processing.process_text_data(texts)
                        model_training.update_model(tokenized_texts)
                        log("Model đã được cập nhật từ kết quả tìm kiếm")
                else:
                    print("Không tìm thấy kết quả tìm kiếm")

            else:
                response = model_training.generate_text(user_input)
                print(f"AI: {response}")
    except KeyboardInterrupt:
        log("AI đã dừng do người dùng ngắt.")
    except Exception as e:
        error_log(f"Lỗi: {e}\n{traceback.format_exc()}")
    finally:
        telegram_integration.stop_bot()

if __name__ == "__main__":
    main_loop()