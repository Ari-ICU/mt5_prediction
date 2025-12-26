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

        if self.model and len(self.history) >= 30:
            try:
                # Prepare features matches train_model.py
                prices = pd.Series(self.history)
                sma10 = prices.rolling(10).mean().iloc[-1]
                sma30 = prices.rolling(30).mean().iloc[-1]
                std10 = prices.rolling(10).std().iloc[-1]
                
                # Simple RSI
                delta = prices.diff()
                gain = delta.where(delta > 0, 0).rolling(14).mean().iloc[-1]
                loss = -delta.where(delta < 0, 0).rolling(14).mean().iloc[-1]
                rsi = 100 - (100 / (1 + (gain/loss))) if loss != 0 else 50
                
                # Mock volume features (since it's hard to get real-time history for vol)
                vol = 100  
                vol_change = 0
                
                X = pd.DataFrame([[ask, sma10, sma30, std10, rsi, vol, vol_change]], 
                                 columns=self.features)
                
                pred = self.model.predict(X)[0]
                return float(pred)
            except Exception as e:
                return ask # Fallback to current price on error
        
        # Default logic: Small random wander
        return ask + (np.random.normal(0, 0.1))
