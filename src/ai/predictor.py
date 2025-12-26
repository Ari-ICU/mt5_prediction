"""Simple AI predictor for price forecasting.
This module provides a lightweight, self‑contained predictor using scikit‑learn's
LinearRegression trained on synthetic data at import time. It offers a
`predict_price(state: dict) -> float` method that returns a forecasted ask price.
In a real project you would replace the synthetic training with a proper model
trained on historical market data.
"""

import joblib
import numpy as np
import os
import pandas as pd
from ..core.logger import logger

class SimplePredictor:
    def __init__(self):
        self.model_path = "models/price_predictor.pkl"
        self.feature_path = "models/feature_names.pkl"
        self.model = None
        self.features = None
        self.history = [] # Buffer to store recent prices for SMA/RSI calculation
        self.last_rsi = 50.0
        self.last_sma10 = 0.0
        
        self._load_model()

    def _load_model(self):
        if os.path.exists(self.model_path):
            try:
                self.model = joblib.load(self.model_path)
                self.features = joblib.load(self.feature_path)
                logger.success("🧠 AI Model loaded successfully!")
            except Exception as e:
                logger.error(f"Failed to load AI model: {e}")
        else:
            logger.info("ℹ️ No trained model found. Using default logic. Run train_model.py first.")

    def predict_price(self, state: dict) -> float:
        bid = state.get("current_bid", 0.0)
        ask = state.get("current_ask", 0.0)
        
        # Add to history for technical analysis
        self.history.append(ask)
        if len(self.history) > 100:
            self.history.pop(0)

        if self.model and len(self.history) >= 5:
            try:
                # Prepare features matches train_model.py
                prices = pd.Series(self.history)
                # Ensure we handle very small windows
                sma10 = prices.rolling(min(10, len(prices))).mean().iloc[-1]
                sma30 = prices.rolling(min(30, len(prices))).mean().iloc[-1]
                std10 = prices.rolling(min(10, len(prices))).std().iloc[-1]
                if pd.isna(std10): std10 = 0
                
                # Simple RSI (requires at least 1 gain/loss)
                if len(prices) >= 14:
                    delta = prices.diff()
                    gain = delta.where(delta > 0, 0).rolling(14).mean().iloc[-1]
                    loss = -delta.where(delta < 0, 0).rolling(14).mean().iloc[-1]
                    rsi = 100 - (100 / (1 + (gain/loss))) if loss != 0 else 50
                else:
                    rsi = 50 # Default middle ground during warm-up
                
                # Mock volume features
                vol = 100  
                vol_change = 0
                
                self.last_sma10 = sma10
                self.last_rsi = rsi
                
                X = pd.DataFrame([[ask, sma10, sma30, std10, rsi, vol, vol_change]], 
                                 columns=self.features)
                
                pred = self.model.predict(X)[0]
                logger.debug(f"📊 AI Features: Ask={ask:.2f}, SMA10={sma10:.2f}, RSI={rsi:.1f} -> Pred: {pred:.2f}")
                return float(pred)
            except Exception as e:
                logger.error(f"Predictor error: {e}")
                return ask # Fallback to current price on error
        
        # Log progress if we are collecting data
        if self.model:
            logger.info(f"⏳ Collecting AI Data: {len(self.history)}/5 ticks...")
            
        # Default logic: Small random wander
        return ask + (np.random.normal(0, 0.05))
