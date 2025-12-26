import pandas as pd
import numpy as np
from sklearn.ensemble import RandomForestRegressor
from sklearn.model_selection import train_test_split
import joblib
import os

def train():
    # 1. Load Data
    csv_path = "dataset/XAUUSDm_history.csv"
    if not os.path.exists(csv_path):
        print(f"❌ File {csv_path} not found. Please sync data first.")
        return

    print(f"📊 Loading data from {csv_path}...")
    df = pd.read_csv(csv_path, on_bad_lines='warn')
    
    # 2. Feature Engineering
    print("🛠️ Engineering features...")
    # Basic technical indicators
    df['SMA_10'] = df['close'].rolling(window=10).mean()
    df['SMA_30'] = df['close'].rolling(window=30).mean()
    df['Std_10'] = df['close'].rolling(window=10).std()
    
    # RSI Calculation
    delta = df['close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / loss
    df['RSI'] = 100 - (100 / (1 + rs))
    
    # Change in volume
    df['vol_change'] = df['volume'].pct_change()
    
    # 3. Define Target (Predict next close price)
    df['target'] = df['close'].shift(-1)
    
    # Drop rows with NaN values (from rolling windows and shift)
    df = df.dropna()
    
    # Define features
    features = ['close', 'SMA_10', 'SMA_30', 'Std_10', 'RSI', 'volume', 'vol_change']
    X = df[features]
    y = df['target']
    
    # 4. Train/Test Split
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, shuffle=False)
    
    # 5. Model Training
    print(f"🚀 Training RandomForest on {len(X_train)} samples...")
    model = RandomForestRegressor(n_estimators=100, random_state=42)
    model.fit(X_train, y_train)
    
    # 6. Evaluation
    score = model.score(X_test, y_test)
    print(f"✅ Training Complete! Model Accuracy Score (R2): {score:.4f}")
    
    # 7. Save Model
    os.makedirs("models", exist_ok=True)
    joblib.dump(model, "models/price_predictor.pkl")
    joblib.dump(features, "models/feature_names.pkl")
    print("💾 Model saved to models/price_predictor.pkl")

if __name__ == "__main__":
    train()
