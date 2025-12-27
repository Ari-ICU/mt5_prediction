import pandas as pd
import numpy as np
from sklearn.ensemble import RandomForestRegressor
from sklearn.model_selection import TimeSeriesSplit
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
        
        # Use TimeSeriesSplit for valid financial validation
        tscv = TimeSeriesSplit(n_splits=3)
        scores = []
        
        # Manual Cross-Validation loop
        for train_index, val_index in tscv.split(self.X):
            X_train_fold, X_val_fold = self.X.iloc[train_index], self.X.iloc[val_index]
            y_train_fold, y_val_fold = self.y.iloc[train_index], self.y.iloc[val_index]
            
            model.fit(X_train_fold, y_train_fold)
            scores.append(model.score(X_val_fold, y_val_fold))
            
        return np.mean(scores)

    def optimize(self):
        print(f"🐝 Swarm Optimization initialized with {self.n_particles} particles...")
        
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
    # 1. Determine Symbol and Path
    if not symbol:
        if len(sys.argv) > 1:
            symbol = sys.argv[1].replace("_history.csv", "").replace("dataset/", "")
        else:
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
    
    # 2. Feature Engineering
    print("🛠️ Engineering features...")
    for col in ['open', 'high', 'low', 'close', 'volume']:
        df[col] = pd.to_numeric(df[col], errors='coerce')
    df = df.dropna()

    df['SMA_10_Ratio'] = df['close'] / df['close'].rolling(window=10).mean()
    df['SMA_30_Ratio'] = df['close'] / df['close'].rolling(window=30).mean()
    df['Volatility_Pct'] = df['close'].rolling(window=10).std() / df['close']
    df['Return_1'] = df['close'].pct_change(1)
    df['Return_5'] = df['close'].pct_change(5)
    
    delta = df['close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / loss
    df['RSI'] = 100 - (100 / (1 + rs))
    
    df['vol_change'] = df['volume'].pct_change()
    
    # Target: Next bar return
    df['target'] = (df['close'].shift(-1) - df['close']) / df['close']
    df = df.dropna()
    
    features = ['SMA_10_Ratio', 'SMA_30_Ratio', 'Volatility_Pct', 'RSI', 'vol_change', 'Return_1', 'Return_5']
    X = df[features]
    y = df['target']
    
    # Split for Final Test (Hold-out set)
    # We use the first 80% for PSO optimization + Training
    cutoff = int(len(X) * 0.8)
    X_train_opt = X.iloc[:cutoff]
    y_train_opt = y.iloc[:cutoff]
    X_test = X.iloc[cutoff:]
    y_test = y.iloc[cutoff:]
    
    # 3. Swarm Optimization
    # Bounds: [n_estimators (50-300), max_depth (5-30), min_samples_split (2-20)]
    bounds = [(50, 300), (5, 30), (2, 20)]
    
    print(f"🚀 Launching Swarm Intelligence for Hyperparameter Tuning...")
    pso = PSOOptimizer(n_particles=10, bounds=bounds, n_iterations=5, X=X_train_opt, y=y_train_opt)
    best_params = pso.optimize()
    
    print(f"✅ Best Parameters Found: {best_params}")
    
    # 4. Final Training
    print(f"🏋️ Training final model with optimized parameters...")
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
    print(f"🏆 Final Test Score (R2): {score:.4f}")
    
    # 6. Save
    os.makedirs("models", exist_ok=True)
    joblib.dump(model, "models/price_predictor.pkl")
    joblib.dump(features, "models/feature_names.pkl")
    print(f"💾 Optimized Predictor saved to models/price_predictor.pkl")

if __name__ == "__main__":
    train()