# deep_learning_model.py
from tensorflow.keras.models import Sequential
from tensorflow.keras.layers import Dense, LSTM
import numpy as np

# Xây dựng mô hình học sâu LSTM
def build_lstm_model(input_shape):
    model = Sequential()
    model.add(LSTM(50, activation='relu', input_shape=input_shape))
    model.add(Dense(1, activation='sigmoid'))
    model.compile(optimizer='adam', loss='binary_crossentropy', metrics=['accuracy'])
    return model

# Huấn luyện mô hình với dữ liệu
def train_lstm_model(X_train, y_train):
    model = build_lstm_model((X_train.shape[1], 1))
    model.fit(X_train, y_train, epochs=50, batch_size=32)
    model.save('deep_learning_model.h5')
    print("Mô hình LSTM đã được huấn luyện và lưu lại.")

if __name__ == "__main__":
    # Giả sử X_train, y_train đã được chuẩn bị sẵn
    X_train = np.array([...])  # Dữ liệu đầu vào
    y_train = np.array([...])  # Dữ liệu kết quả Tài/Xỉu
    train_lstm_model(X_train, y_train)
