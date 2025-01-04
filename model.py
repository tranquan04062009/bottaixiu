import pandas as pd
import numpy as np
from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestClassifier
from sklearn.preprocessing import LabelEncoder
from sklearn.metrics import accuracy_score
import joblib

# Tiền xử lý và chuẩn hóa dữ liệu
def preprocess_data(df):
    # Giả sử dữ liệu có các cột: 'previous_rolls' là chuỗi các kết quả trước và 'result' là kết quả của ván chơi
    df['previous_rolls'] = df['previous_rolls'].apply(lambda x: list(map(int, x.split(','))))  # Chuyển chuỗi thành list
    df['result'] = df['result'].map({'Tài': 1, 'Xỉu': 0})  # Mã hóa kết quả thành 1 (Tài) và 0 (Xỉu)
    
    return df

# Hàm huấn luyện mô hình
def train_model(df):
    df = preprocess_data(df)
    X = np.array(df['previous_rolls'].to_list())  # Chuyển đổi các kết quả trước thành mảng
    X = X.reshape((X.shape[0], -1))  # Chuyển đổi thành dạng 2D

    y = df['result']

    # Chia dữ liệu thành bộ train và test
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

    # Huấn luyện mô hình Random Forest
    model = RandomForestClassifier(n_estimators=100, random_state=42)
    model.fit(X_train, y_train)

    # Đánh giá mô hình
    y_pred = model.predict(X_test)
    print(f'Accuracy: {accuracy_score(y_test, y_pred)}')

    # Lưu mô hình và các công cụ tiền xử lý
    joblib.dump(model, 'game_prediction_model.pkl')
    return model

# Hàm dự đoán kết quả Tài Xỉu
def predict_result(model, previous_rolls):
    prediction = model.predict([previous_rolls])
    return 'Tài' if prediction[0] == 1 else 'Xỉu'

# Tạo mô hình học máy
if __name__ == '__main__':
    # Giả sử bạn có một tập dữ liệu các ván chơi trước (dữ liệu thực tế cần được thu thập từ các ván chơi)
    data = {
        'previous_rolls': ['1,2,3', '4,5,6', '2,3,4', '1,2,2', '6,5,4'],  # Các kết quả của 3 con xúc xắc
        'result': ['Tài', 'Xỉu', 'Tài', 'Xỉu', 'Tài']
    }
    df = pd.DataFrame(data)

    # Huấn luyện mô hình
    model = train_model(df)
    print("Mô hình đã được huấn luyện và lưu thành công.")
