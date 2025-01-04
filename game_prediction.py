# game_prediction.py
import numpy as np
import pandas as pd
import pickle
from tensorflow.keras.models import load_model
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.preprocessing import LabelEncoder

# Load các mô hình đã huấn luyện
def load_models():
    model = load_model('deep_learning_model.h5')
    vectorizer = pickle.load(open('vectorizer.pkl', 'rb'))
    label_encoder = pickle.load(open('label_encoder.pkl', 'rb'))
    return model, vectorizer, label_encoder

# Tiền xử lý dữ liệu
def preprocess_data(data, vectorizer):
    return vectorizer.transform([data])

# Dự đoán kết quả Tài/Xỉu
def predict_game_result(data, model, vectorizer, label_encoder):
    processed_data = preprocess_data(data, vectorizer)
    prediction = model.predict(processed_data)
    result = label_encoder.inverse_transform([np.argmax(prediction)])
    return result[0]

# Chạy dự đoán trên dữ liệu mới
def predict(data):
    model, vectorizer, label_encoder = load_models()
    result = predict_game_result(data, model, vectorizer, label_encoder)
    return result

if __name__ == "__main__":
    new_game_data = "Dữ liệu ván trước"  # Dữ liệu từ các ván trước
    prediction = predict(new_game_data)
    print(f"Dự đoán kết quả tiếp theo: {prediction}")
