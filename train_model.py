import pandas as pd
import numpy as np
from sklearn.ensemble import RandomForestRegressor
from sklearn.model_selection import train_test_split
import joblib
import os
import sys

def train(symbol=None):
    # 1. Determine Symbol and Path
    if not symbol:
        # Check if symbol was passed as argument (e.g. python train_model.py BTCUSDm)
        if len(sys.argv) > 1:
            symbol = sys.argv[1].replace("_history.csv", "").replace("dataset/", "")
        else:
            # Default to BTCUSDm if it exists, otherwise list alternatives
            if os.path.exists("dataset/BTCUSDm_history.csv"):
                symbol = "BTCUSDm"
            else:
                csv_files = [f for f in os.listdir("dataset") if f.endswith("_history.csv")]
                if not csv_files:
                    print("❌ No datasets found in 'dataset/' folder. Please sync data from the UI first.")
                    return
                symbol = csv_files[0].replace("_history.csv", "")

    csv_path = f"dataset/{symbol}_history.csv"
    if not os.path.exists(csv_path):
        print(f"❌ File {csv_path} not found.")
        return

    print(f"📊 Loading data for {symbol} from {csv_path}...")
    df = pd.read_csv(csv_path, on_bad_lines='warn')
    
    if len(df) < 100:
        print(f"⚠️ Dataset too small ({len(df)} rows). Please sync more data for better accuracy.")
    
    # 2. Feature Engineering (Adding Momentum/Speed)
    print("🛠️ Engineering features...")
    # Clean data (ensure numeric types)
    for col in ['open', 'high', 'low', 'close', 'volume']:
        df[col] = pd.to_numeric(df[col], errors='coerce')
    df = df.dropna()

    # Ratios (Trend Location)
    df['SMA_10_Ratio'] = df['close'] / df['close'].rolling(window=10).mean()
    df['SMA_30_Ratio'] = df['close'] / df['close'].rolling(window=30).mean()
    df['Volatility_Pct'] = df['close'].rolling(window=10).std() / df['close']
    
    # Momentum (Speed - Critical for ATH)
    df['Return_1'] = df['close'].pct_change(1) # Speed of last bar
    df['Return_5'] = df['close'].pct_change(5) # Speed of last 5 bars
    
    # RSI for Overbought/Oversold
    delta = df['close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / loss
    df['RSI'] = 100 - (100 / (1 + rs))
    
    df['vol_change'] = df['volume'].pct_change()
    
    # 3. Define Target (1-bar forward return)
    # The goal is to predict if the NEXT bar's close is higher or lower than current close
    df['target'] = (df['close'].shift(-1) - df['close']) / df['close']
    
    df = df.dropna()
    
    if len(df) < 50:
        print("❌ Not enough data after feature engineering. Sync more candles.")
        return

    # Feature Set: Momentum + Trend + Volume
    features = ['SMA_10_Ratio', 'SMA_30_Ratio', 'Volatility_Pct', 'RSI', 'vol_change', 'Return_1', 'Return_5']
    X = df[features]
    y = df['target']
    
    # 4. Train/Test Split
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, shuffle=False)
    
    # 5. Model Training (Powerful forest for high-speed markets)
    print(f"🚀 Training Momentum-Aware Predictor for {symbol} on {len(X_train)} samples...")
    # Using a slightly deeper forest to capture complex crypto/XAU patterns
    model = RandomForestRegressor(n_estimators=150, max_depth=12, random_state=42)
    model.fit(X_train, y_train)
    
    # 6. Evaluation
    score = model.score(X_test, y_test)
    print(f"✅ Training Complete! (R2 Score: {score:.4f})")
    
    # 7. Save Model
    os.makedirs("models", exist_ok=True)
    joblib.dump(model, "models/price_predictor.pkl")
    joblib.dump(features, "models/feature_names.pkl")
    print(f"💾 Return Predictor for {symbol} saved to models/price_predictor.pkl")

if __name__ == "__main__":
    train()
