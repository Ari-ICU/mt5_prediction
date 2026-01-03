import pandas as pd
import numpy as np
from sklearn.ensemble import RandomForestRegressor
from sklearn.model_selection import TimeSeriesSplit
from sklearn.preprocessing import OneHotEncoder
import joblib
import os
import sys
import random

# --- Swarm Intelligence: Particle Swarm Optimization (PSO) ---

class Particle:
    def __init__(self, bounds):
        self.position = []
        self.velocity = []
        self.best_position = []
        self.best_score = -float('inf')
        self.bounds = bounds
        
        for lower, upper in bounds:
            self.position.append(random.uniform(lower, upper))
            self.velocity.append(random.uniform(-1, 1))
        
        self.best_position = list(self.position)

    def update_velocity(self, global_best_position, w=0.5, c1=1.5, c2=1.5):
        for i in range(len(self.position)):
            r1 = random.random()
            r2 = random.random()
            
            # Cognitive component (personal best)
            cognitive = c1 * r1 * (self.best_position[i] - self.position[i])
            # Social component (swarm best)
            social = c2 * r2 * (global_best_position[i] - self.position[i])
            
            self.velocity[i] = w * self.velocity[i] + cognitive + social

    def update_position(self):
        for i in range(len(self.position)):
            self.position[i] += self.velocity[i]
            
            # Enforce bounds
            lower, upper = self.bounds[i]
            if self.position[i] < lower:
                self.position[i] = lower
                self.velocity[i] *= -1  # Bounce back
            elif self.position[i] > upper:
                self.position[i] = upper
                self.velocity[i] *= -1

class PSOOptimizer:
    def __init__(self, n_particles, bounds, n_iterations, X, y):
        self.n_particles = n_particles
        self.bounds = bounds
        self.n_iterations = n_iterations
        self.X = X
        self.y = y
        self.global_best_position = []
        self.global_best_score = -float('inf')
        self.particles = [Particle(bounds) for _ in range(n_particles)]

    def evaluate_fitness(self, params):
        # Decode params (convert floats to ints for RF)
        n_estimators = int(params[0])
        max_depth = int(params[1])
        min_samples_split = int(params[2])
        
        # Train a quick model for validation
        model = RandomForestRegressor(
            n_estimators=n_estimators,
            max_depth=max_depth,
            min_samples_split=min_samples_split,
            n_jobs=-1,
            random_state=42
        )
        
        # Use TimeSeriesSplit for valid financial validation (increased splits for multi-symbol)
        tscv = TimeSeriesSplit(n_splits=5)
        scores = []
        
        # Manual Cross-Validation loop
        for train_index, val_index in tscv.split(self.X):
            X_train_fold, X_val_fold = self.X.iloc[train_index], self.X.iloc[val_index]
            y_train_fold, y_val_fold = self.y.iloc[train_index], self.y.iloc[val_index]
            
            model.fit(X_train_fold, y_train_fold)
            scores.append(model.score(X_val_fold, y_val_fold))
            
        return np.mean(scores)

    def optimize(self):
        print(f"Swarm Optimization initialized with {self.n_particles} particles...")
        
        for i in range(self.n_iterations):
            for particle in self.particles:
                score = self.evaluate_fitness(particle.position)
                
                # Update Personal Best
                if score > particle.best_score:
                    particle.best_score = score
                    particle.best_position = list(particle.position)
                
                # Update Global Best
                if score > self.global_best_score:
                    self.global_best_score = score
                    self.global_best_position = list(particle.position)
            
            # Move Swarm
            for particle in self.particles:
                particle.update_velocity(self.global_best_position)
                particle.update_position()
                
            print(f"   Iteration {i+1}/{self.n_iterations} | Best Score: {self.global_best_score:.4f} | Params: {self.get_best_params()}")

        return self.get_best_params()

    def get_best_params(self):
        return {
            'n_estimators': int(self.global_best_position[0]),
            'max_depth': int(self.global_best_position[1]),
            'min_samples_split': int(self.global_best_position[2])
        }

# --- Main Training Pipeline ---

def train(symbol=None):
    # 1. Auto-Detect All Symbols (or single if specified)
    csv_files = [f for f in os.listdir("dataset") if f.endswith("_history.csv")]
    if not csv_files:
        print("No datasets found in 'dataset/' folder. Please add *_history.csv files.")
        return
    
    if symbol:
        csv_path = f"dataset/{symbol}_history.csv"
        if not os.path.exists(csv_path):
            print(f"Specified file {csv_path} not found.")
            return
        csv_files = [f"{symbol}_history.csv"]  # Limit to one
    
    print(f"Found datasets: {csv_files}")
    dfs = []
    for f in csv_files:
        csv_path = f"dataset/{f}"
        df = pd.read_csv(csv_path, on_bad_lines='warn')
        print(f"Loaded {len(df)} rows for {f.replace('_history.csv', '')}")
        # Add symbol column for multi-asset awareness
        symbol_name = f.replace('_history.csv', '')
        df['symbol'] = symbol_name
        dfs.append(df)
    
    # Combine all
    df = pd.concat(dfs, ignore_index=True)
    print(f"Combined dataset shape: {df.shape}")
    
    # 2. Feature Engineering
    print("Engineering features...")
    for col in ['open', 'high', 'low', 'close', 'volume']:
        df[col] = pd.to_numeric(df[col], errors='coerce')
    df = df.dropna(subset=['open', 'high', 'low', 'close', 'volume'])

    # Moving Averages
    df['SMA_10_Ratio'] = df['close'] / df['close'].rolling(window=10).mean()
    df['SMA_30_Ratio'] = df['close'] / df['close'].rolling(window=30).mean()
    df['Volatility_Pct'] = df['close'].rolling(window=10).std() / df['close']
    
    # Returns
    df['Return_1'] = df['close'].pct_change(1)
    df['Return_5'] = df['close'].pct_change(5)
    
    # RSI
    delta = df['close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / loss
    df['RSI'] = 100 - (100 / (1 + rs))
    
    # Stochastic Oscillator (14, 3, 3)
    low_14 = df['low'].rolling(window=14).min()
    high_14 = df['high'].rolling(window=14).max()
    df['Stoch_K'] = 100 * ((df['close'] - low_14) / (high_14 - low_14))
    df['Stoch_D'] = df['Stoch_K'].rolling(window=3).mean()
    
    df['vol_change'] = df['volume'].pct_change()
    
    # ATR (Average True Range)
    df['tr'] = np.maximum.reduce([
        df['high'] - df['low'],
        np.abs(df['high'] - df['close'].shift()),
        np.abs(df['low'] - df['close'].shift())
    ])
    df['ATR'] = df['tr'].rolling(14).mean()
    df['ATR_norm'] = df['ATR'] / df['close']
    
    # Target: Next bar return
    df['target'] = (df['close'].shift(-1) - df['close']) / df['close']
    df = df.dropna()
    
    # One-hot encode symbol for multi-asset
    encoder = OneHotEncoder(sparse_output=False, drop='first')
    symbol_encoded = encoder.fit_transform(df[['symbol']])
    symbol_df = pd.DataFrame(symbol_encoded, columns=[f'symbol_{c}' for c in encoder.get_feature_names_out(['symbol'])])
    df = pd.concat([df.reset_index(drop=True), symbol_df.reset_index(drop=True)], axis=1)
    
    features = [
        'SMA_10_Ratio', 'SMA_30_Ratio', 'Volatility_Pct', 
        'RSI', 'Stoch_K', 'Stoch_D', 
        'vol_change', 'Return_1', 'Return_5',
        'ATR_norm'
    ] + [col for col in df.columns if col.startswith('symbol_')]  # Add encoded symbols
    
    X = df[features]
    y = df['target']
    
    # Split for Final Test (Hold-out set)
    cutoff = int(len(X) * 0.8)
    X_train_opt = X.iloc[:cutoff]
    y_train_opt = y.iloc[:cutoff]
    X_test = X.iloc[cutoff:]
    y_test = y.iloc[cutoff:]
    
    # 3. Swarm Optimization (wider bounds for multi-data)
    bounds = [(50, 400), (5, 35), (2, 25)]  # Slightly expanded
    
    print(f"Launching Swarm Intelligence for Hyperparameter Tuning...")
    pso = PSOOptimizer(n_particles=10, bounds=bounds, n_iterations=5, X=X_train_opt, y=y_train_opt)
    best_params = pso.optimize()
    
    print(f"Best Parameters Found: {best_params}")
    
    # 4. Final Training
    print(f"Training final model with optimized parameters...")
    model = RandomForestRegressor(
        n_estimators=best_params['n_estimators'],
        max_depth=best_params['max_depth'],
        min_samples_split=best_params['min_samples_split'],
        random_state=42,
        n_jobs=-1
    )
    model.fit(X_train_opt, y_train_opt)
    
    # 5. Evaluation
    score = model.score(X_test, y_test)
    print(f"Final Test Score (R2) on Combined Data: {score:.4f}")
    
    # 6. Save (also save encoder for predictor use)
    os.makedirs("models", exist_ok=True)
    joblib.dump(model, "models/price_predictor.pkl")
    joblib.dump(features, "models/feature_names.pkl")
    joblib.dump(encoder, "models/symbol_encoder.pkl")
    print(f"Multi-Symbol Predictor saved to models/price_predictor.pkl")

if __name__ == "__main__":
    # Optional: Pass symbol to train only on one, e.g., python train_model.py BTCUSDm
    if len(sys.argv) > 1:
        train(sys.argv[1])
    else:
        train()  # All symbols