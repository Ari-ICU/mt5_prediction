"""Simple AI predictor for price forecasting.
This module provides a lightweight, self-contained predictor using scikit-learn's
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
        self.encoder_path = "models/symbol_encoder.pkl"
        self.model = None
        self.features = None
        self.encoder = None
        self.history = []  # Buffer to store recent prices for SMA/RSI/Stoch calculation
        self.last_rsi = 50.0
        self.last_stoch_k = 50.0
        self.last_stoch_d = 50.0
        self.last_sma10 = 0.0
        self.last_sma200 = 0.0 # Trend Filter
        self.last_atr = 0.0  # For dynamic TP/SL
        
        self._load_model()

    def _load_model(self):
        if os.path.exists(self.model_path):
            try:
                self.model = joblib.load(self.model_path)
                self.features = joblib.load(self.feature_path)
                if os.path.exists(self.encoder_path):
                    self.encoder = joblib.load(self.encoder_path)
                logger.success("AI Model loaded successfully!")
                logger.info(f"Expected features: {len(self.features)} ({self.features})")
            except Exception as e:
                logger.error(f"Failed to load AI model: {e}")
        else:
            logger.info("No trained model found. Using default logic. Run train_model.py first.")

    def predict_price(self, state: dict) -> float:
        bid = state.get("current_bid", 0.0)
        ask = state.get("current_ask", 0.0)
        symbol = state.get("symbol", "BTCUSDm")  # Required for multi-symbol encoding
        
        # Add to history for technical analysis
        self.history.append(ask)
        if len(self.history) > 300: # Increased for SMA200
            self.history.pop(0)

        if self.model and len(self.history) >= 14:
            try:
                # Prepare features (matches train_model.py)
                prices = pd.Series(self.history)
                # Ensure we handle very small windows
                sma10 = prices.rolling(min(10, len(prices))).mean().iloc[-1]
                sma30 = prices.rolling(min(30, len(prices))).mean().iloc[-1]
                sma200 = prices.rolling(min(200, len(prices))).mean().iloc[-1]
                std10 = prices.rolling(min(10, len(prices))).std().iloc[-1]
                if pd.isna(std10): std10 = 0
                
                # Simple RSI
                delta = prices.diff()
                gain = delta.where(delta > 0, 0).rolling(14).mean().iloc[-1]
                loss = -delta.where(delta < 0, 0).rolling(14).mean().iloc[-1]
                rsi = 100 - (100 / (1 + (gain/loss))) if loss != 0 else 50
                
                # Stochastic Oscillator (Simulated using history of Asks as High/Low proxy)
                lowest_low = prices.rolling(14).min().iloc[-1]
                highest_high = prices.rolling(14).max().iloc[-1]
                denom = highest_high - lowest_low
                
                if denom == 0:
                    stoch_k = 50
                else:
                    stoch_k = 100 * ((ask - lowest_low) / denom)
                
                stoch_d = stoch_k  # Simplified (full buffer ideal, but ok for ticks)
                
                # Mock volume features
                vol = 100  
                vol_change = 0
                
                # ATR Approximation (Tick-based)
                # We use the High-Low range of a 10-tick window, averaged over 14 periods.
                # This captures volatility better than just consecutive tick differences.
                hl_range = prices.rolling(10).max() - prices.rolling(10).min()
                current_atr = hl_range.rolling(14).mean().iloc[-1]

                if pd.isna(current_atr) or current_atr < (0.0002 * ask):
                    current_atr = 0.0005 * ask  # Fallback: 0.05% of price (e.g., $45 for BTC)
                self.last_atr = current_atr
                
                # Relative/Momentum Features
                sma10_ratio = ask / sma10 if sma10 > 0 else 1.0
                sma30_ratio = ask / sma30 if sma30 > 0 else 1.0
                vol_pct = (prices.rolling(min(10, len(prices))).std().iloc[-1] / ask) if ask > 0 else 0
                if pd.isna(vol_pct): vol_pct = 0
                
                ret1 = (prices.iloc[-1] - prices.iloc[-2]) / prices.iloc[-2] if len(prices) >= 2 else 0
                ret5 = (prices.iloc[-1] - prices.iloc[-5]) / prices.iloc[-5] if len(prices) >= 5 else 0
                
                atr_norm = current_atr / ask
                
                self.last_sma10 = sma10
                self.last_sma200 = sma200
                self.last_rsi = rsi
                self.last_stoch_k = stoch_k
                self.last_stoch_d = stoch_d
                
                # Base 10 features
                base_features = [
                    sma10_ratio, sma30_ratio, vol_pct, 
                    rsi, stoch_k, stoch_d, 
                    vol_change, ret1, ret5,
                    atr_norm
                ]
                
                # Handle symbol encoding (appends 1 value for 2 symbols)
                symbol_encoded = np.zeros(len(self.features) - 10)  # Fallback zeros for num symbol cols
                
                # FIX: Check categories and use DataFrame with correct column name
                if self.encoder:
                    # Defensive check if symbol is in the known categories
                    # The encoder stores categories in a list of arrays (one per feature)
                    known_symbols = self.encoder.categories_[0]
                    if symbol in known_symbols:
                        try:
                            # ---------------------------------------------------------
                            # FIX IS HERE: Wrap in DataFrame with column 'symbol'
                            # ---------------------------------------------------------
                            sym_df = pd.DataFrame([[symbol]], columns=['symbol'])
                            symbol_encoded = self.encoder.transform(sym_df)[0]
                        except Exception as e:
                            # logger.warning(f"Encoding warning: {e}")
                            pass 
                
                # Full data: base + encoded (now 11 values for 11 columns)
                full_data = base_features + list(symbol_encoded)
                
                X = pd.DataFrame([full_data], columns=self.features)
                
                # Predict percentage return
                pred_return = self.model.predict(X)[0]
                pred_price = ask * (1 + pred_return)
                
                logger.debug(f"AI Return: {pred_return:+.6f} | Stoch: {stoch_k:.1f} | Speed(M5): {ret5:+.6f} | ATR: {current_atr:.5f} | Symbol Enc: {symbol_encoded} -> Target: {pred_price:.2f}")
                return float(pred_price)
            except Exception as e:
                logger.error(f"Predictor error: {e}")
                # Log data debug for troubleshooting
                logger.debug(f"Debug: len(full_data)={len(full_data) if 'full_data' in locals() else 'N/A'}, len(features)={len(self.features)}, symbol={symbol}")
                return ask  # Fallback to current price on error
        
        # Log progress if we are collecting data
        if self.model:
            logger.info(f"Collecting AI Data: {len(self.history)}/14 ticks...")
            
        # Default logic: Small random wander
        return ask + (np.random.normal(0, 0.05))