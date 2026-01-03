import pandas as pd
import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import TimeSeriesSplit
from sklearn.metrics import accuracy_score
import joblib
import os
import sys
import random
import time
from tqdm import tqdm

# Debug flag
VERBOSE = False  # Set to True for prints

# --- Swarm Intelligence: PSO Optimized for Strategy Return ---
class Particle:
    def __init__(self, bounds):
        self.position = [random.uniform(lower, upper) for lower, upper in bounds]
        self.velocity = [random.uniform(-1, 1) for _ in bounds]
        self.best_position = list(self.position)
        self.best_score = -float('inf')
        self.bounds = bounds

    def update_velocity(self, global_best_position, w=0.5, c1=1.5, c2=1.5):
        for i in range(len(self.position)):
            r1, r2 = random.random(), random.random()
            cognitive = c1 * r1 * (self.best_position[i] - self.position[i])
            social = c2 * r2 * (global_best_position[i] - self.position[i])
            self.velocity[i] = w * self.velocity[i] + cognitive + social

    def update_position(self):
        for i in range(len(self.position)):
            self.position[i] += self.velocity[i]
            lower, upper = self.bounds[i]
            if self.position[i] < lower:
                self.position[i] = lower
                self.velocity[i] *= -1
            elif self.position[i] > upper:
                self.position[i] = upper
                self.velocity[i] *= -1

class PSOOptimizer:
    def __init__(self, n_particles, bounds, n_iterations, X, y, future_returns):
        self.n_particles = n_particles
        self.bounds = bounds
        self.n_iterations = n_iterations
        self.X = X
        self.y = y
        self.future_returns = future_returns
        self.global_best_position = None
        self.global_best_score = -float('inf')
        self.particles = [Particle(bounds) for _ in range(n_particles)]

    def evaluate_fitness(self, params):
        if VERBOSE:
            print(f"  Evaluating params: n_est={int(params[0])}, depth={int(params[1])}, split={int(params[2])}")
        start_time = time.time()
        n_estimators = int(params[0])
        max_depth = int(params[1])
        min_samples_split = int(params[2])
        
        model = RandomForestClassifier(
            n_estimators=n_estimators,
            max_depth=max_depth,
            min_samples_split=min_samples_split,
            random_state=42,
            n_jobs=-1  # Parallelize trees
        )
        
        tscv = TimeSeriesSplit(n_splits=3)
        fold_returns = []
        fold_num = 0
        for train_index, val_index in tscv.split(self.X):
            fold_num += 1
            if VERBOSE:
                print(f"    Fold {fold_num}: train={len(train_index)}, val={len(val_index)}")
            fold_start = time.time()
            X_train_fold, X_val_fold = self.X.iloc[train_index], self.X.iloc[val_index]
            y_train_fold, y_val_fold = self.y.iloc[train_index], self.y.iloc[val_index]
            actual_ret_fold = self.future_returns.iloc[val_index]
            model.fit(X_train_fold, y_train_fold)
            pred_fold = model.predict(X_val_fold)
            signals = 2 * pred_fold - 1
            strat_ret_fold = signals * actual_ret_fold
            fold_score = np.prod(1 + strat_ret_fold) - 1
            fold_returns.append(fold_score)
            if VERBOSE:
                print(f"      Fold {fold_num} score: {fold_score:.4f} (took {time.time() - fold_start:.1f}s)")
            if time.time() - fold_start > 30:  # Rough timeout
                print(f"Warning: Fold {fold_num} too slow (>30s), skipping remaining.")
                break
        avg_score = np.mean(fold_returns)
        if VERBOSE:
            print(f"  Fitness complete: {avg_score:.4f} (total {time.time() - start_time:.1f}s)")
        return avg_score

    def optimize(self):
        print(f"Swarm Optimization for Classifier (Return-Focused)...")
        pbar = tqdm(total=self.n_iterations, desc="PSO Iterations")
        for i in range(self.n_iterations):
            if VERBOSE:
                print(f"\n--- Iteration {i+1}/{self.n_iterations} ---")
            for j, particle in enumerate(self.particles):
                if VERBOSE:
                    print(f"  Particle {j+1}/{self.n_particles}")
                score = self.evaluate_fitness(particle.position)
                if score > particle.best_score:
                    particle.best_score = score
                    particle.best_position = list(particle.position)
                if score > self.global_best_score:
                    self.global_best_score = score
                    self.global_best_position = list(particle.position)
            for particle in self.particles:
                particle.update_velocity(self.global_best_position)
                particle.update_position()
            pbar.set_postfix({"Best Fold Avg Return": f"{self.global_best_score:.4f}"})
            pbar.update(1)
        pbar.close()
        return {
            'n_estimators': int(self.global_best_position[0]),
            'max_depth': int(self.global_best_position[1]),
            'min_samples_split': int(self.global_best_position[2])
        }

# --- Main Training Pipeline ---
def train(symbol=None):
    if not symbol:
        if len(sys.argv) > 1:
            symbol = sys.argv[1].replace("_history.csv", "").replace("dataset/", "")
        else:
            csv_files = [f for f in os.listdir("dataset") if f.endswith("_history.csv")]
            if not csv_files:
                print("No datasets found. Sync data first.")
                return
            symbol = csv_files[0].replace("_history.csv", "")
    csv_path = f"dataset/{symbol}_history.csv"
    if not os.path.exists(csv_path):
        print(f"File {csv_path} not found.")
        return

    print(f"Loading data for {symbol}...")
    df = pd.read_csv(csv_path)
    print(f"Raw data shape: {df.shape}")  # Debug: Check size
    df['time'] = pd.to_datetime(df['time'])
    df.set_index('time', inplace=True)
    
    # Feature Engineering (Enhanced for BTC)
    for col in ['open', 'high', 'low', 'close', 'volume']:
        df[col] = pd.to_numeric(df[col], errors='coerce')
    df = df.dropna()

    # EMAs for MACD
    def ema(series, period):
        return series.ewm(span=period).mean()
    df['EMA12'] = ema(df['close'], 12)
    df['EMA26'] = ema(df['close'], 26)
    df['MACD'] = (df['EMA12'] - df['EMA26']) / df['close']

    print("Computing features...")
    feature_progress = tqdm(total=10, desc="Features")
    df['SMA_10_Ratio'] = df['close'] / df['close'].rolling(10).mean()
    feature_progress.update(1)
    df['SMA_30_Ratio'] = df['close'] / df['close'].rolling(30).mean()
    feature_progress.update(1)
    df['Volatility_Pct'] = df['close'].rolling(10).std() / df['close']
    feature_progress.update(1)
    df['Return_1'] = df['close'].pct_change(1)
    feature_progress.update(1)
    df['Return_5'] = df['close'].pct_change(5)
    feature_progress.update(1)
    delta = df['close'].diff()
    gain = delta.where(delta > 0, 0).rolling(14).mean()
    loss = -delta.where(delta < 0, 0).rolling(14).mean()
    rs = gain / loss.replace(0, np.finfo(float).eps)  # Avoid div0 with tiny eps
    df['RSI'] = np.clip(100 - (100 / (1 + rs)), 0, 100)  # Clip inf/NaN
    feature_progress.update(1)
    low_14 = df['low'].rolling(14).min()
    high_14 = df['high'].rolling(14).max()
    stoch_denom = high_14 - low_14
    df['Stoch_K'] = 100 * ((df['close'] - low_14) / stoch_denom.replace(0, np.finfo(float).eps))
    df['Stoch_K'] = np.clip(df['Stoch_K'], 0, 100)
    df['Stoch_D'] = df['Stoch_K'].rolling(3).mean()
    feature_progress.update(1)
    df['vol_change'] = df['volume'].pct_change()
    feature_progress.update(1)
    
    # BTC Enhancement
    df['log_volume'] = np.log(df['volume'] + 1)
    feature_progress.update(1)
    atr_df = pd.DataFrame({
        'hl': df['high'] - df['low'],
        'hc': abs(df['high'] - df['close'].shift()),
        'lc': abs(df['low'] - df['close'].shift())
    }).max(axis=1).rolling(14).mean()
    df['ATR_Pct'] = atr_df / df['close']
    feature_progress.update(1)
    feature_progress.close()
    
    # Target
    df['future_return'] = df['close'].pct_change().shift(-1)
    df['future_return'] = np.clip(df['future_return'], -0.1, 0.1)
    df['target'] = np.where(df['future_return'] > 0, 1, 0)
    df = df.dropna()
    print(f"Clean data shape: {df.shape}")  # Debug
    
    features = [
        'SMA_10_Ratio', 'SMA_30_Ratio', 'Volatility_Pct', 'MACD',
        'RSI', 'Stoch_K', 'Stoch_D', 'vol_change', 'Return_1', 'Return_5',
        'log_volume', 'ATR_Pct'
    ]
    X = df[features].replace([np.inf, -np.inf], np.nan).fillna(0)  # Robust clean
    y = df['target']
    future_returns = df['future_return']
    
    if len(X) < 50:
        print("Warning: Too few samples (<50). PSO unreliable – add more data.")
        return
    
    cutoff = int(len(X) * 0.8)
    X_train_opt = X.iloc[:cutoff]
    y_train_opt = y.iloc[:cutoff]
    future_train_opt = future_returns.iloc[:cutoff]
    X_test = X.iloc[cutoff:]
    y_test = y.iloc[cutoff:]
    future_test = future_returns.iloc[cutoff:]
    print(f"Train size: {len(X_train_opt)}, Test: {len(X_test)}")  # Debug
    
    # PSO (Reduced for speed)
    bounds = [(50, 300), (5, 30), (2, 20)]
    pso = PSOOptimizer(5, bounds, 3, X_train_opt, y_train_opt, future_train_opt)  # Smaller: 5x3=15 evals/iter
    best_params = pso.optimize()
    
    # Rest unchanged...
    print("Final model training...")
    model = RandomForestClassifier(**best_params, random_state=42, n_jobs=-1)
    model.fit(X_train_opt, y_train_opt)
    
    pred_test = model.predict(X_test)
    acc = accuracy_score(y_test, pred_test)
    print(f"Test Accuracy: {acc:.4f}")
    
    signals = 2 * pred_test - 1
    min_len = min(len(future_test), len(signals))
    future_test = future_test.iloc[:min_len]
    signals = signals[:min_len]
    strategy_returns = signals * future_test
    cum_return = np.prod(1 + strategy_returns) - 1
    win_rate = np.sum(strategy_returns > 0) / len(strategy_returns)
    mean_ret = np.mean(strategy_returns)
    std_ret = np.std(strategy_returns)
    sharpe = np.sqrt(365) * mean_ret / std_ret if std_ret > 0 else 0
    print(f"Backtest Cum Return: {cum_return:.4f}")
    print(f"Win Rate: {win_rate:.4f}")
    print(f"Sharpe Ratio: {sharpe:.4f}")
    
    if cum_return > 0 or acc > 0.52:
        os.makedirs("models", exist_ok=True)
        joblib.dump(model, "models/direction_predictor.pkl")
        joblib.dump(features, "models/feature_names.pkl")
        print("Profitable model saved!")
    else:
        print("Warning: No strong edge. Add more data or features.")

if __name__ == "__main__":
    train()