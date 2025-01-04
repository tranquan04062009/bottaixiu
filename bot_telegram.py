from telegram import Update
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, CallbackContext
import joblib
from fetch_data import fetch_data_from_web
from model import predict_error

# Tải mô hình đã huấn luyện
model = joblib.load('error_prediction_model.pkl')
vectorizer = joblib.load('vectorizer.pkl')
label_encoder = joblib.load('label_encoder.pkl')

# Hàm bot Telegram
def start(update: Update, context: CallbackContext):
    update.message.reply_text("Chào bạn! Hãy gửi một link web mà bạn muốn bot phân tích.")

def handle_message(update: Update, context: CallbackContext):
    url = update.message.text
    errors = fetch_data_from_web(url)

    if not errors:
        update.message.reply_text("Không tìm thấy lỗi trong trang web này.")
        return

    # Dự đoán lỗi từ các dữ liệu thu thập được
    predictions = [predict_error(error) for error in errors]
    update.message.reply_text(f"Kết quả dự đoán: {predictions}")

def main():
    updater = Updater("7755708665:AAFkF8i1eyoEHH83pL7lP2Vu1gnLluqaCYg", use_context=True)  # Thay YOUR_API_KEY với API key của bạn
    dp = updater.dispatcher

    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(MessageHandler(Filters.text & ~Filters.command, handle_message))

    updater.start_polling()
    updater.idle()

if __name__ == '__main__':
    main()
