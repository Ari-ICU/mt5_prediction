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
                
                # Relative/Momentum Features (Must match train_model.py)
                sma10_ratio = ask / sma10 if sma10 > 0 else 1.0
                sma30_ratio = ask / sma30 if sma30 > 0 else 1.0
                vol_pct = (prices.rolling(min(10, len(prices))).std().iloc[-1] / ask) if ask > 0 else 0
                if pd.isna(vol_pct): vol_pct = 0
                
                # return = (now - then) / then
                ret1 = (prices.iloc[-1] - prices.iloc[-2]) / prices.iloc[-2] if len(prices) >= 2 else 0
                ret5 = (prices.iloc[-1] - prices.iloc[-5]) / prices.iloc[-5] if len(prices) >= 5 else 0
                
                self.last_sma10 = sma10
                self.last_rsi = rsi
                
                # Order MUST match train_model.py: ['SMA_10_Ratio', 'SMA_30_Ratio', 'Volatility_Pct', 'RSI', 'vol_change', 'Return_1', 'Return_5']
                X = pd.DataFrame([[sma10_ratio, sma30_ratio, vol_pct, rsi, vol_change, ret1, ret5]], 
                                 columns=self.features)
                
                # Model now predicts PERCENTAGE CHANGE (return)
                pred_return = self.model.predict(X)[0]
                pred_price = ask * (1 + pred_return)
                
                logger.debug(f"📊 AI Return: {pred_return:+.6f} | Speed(M5): {ret5:+.6f} -> Target: {pred_price:.2f}")
                return float(pred_price)
            except Exception as e:
                logger.error(f"Predictor error: {e}")
                return ask # Fallback to current price on error
        
        # Log progress if we are collecting data
        if self.model:
            logger.info(f"⏳ Collecting AI Data: {len(self.history)}/5 ticks...")
            
        # Default logic: Small random wander
        return ask + (np.random.normal(0, 0.05))
