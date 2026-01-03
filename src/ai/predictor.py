import joblib
import numpy as np
import os
import pandas as pd
from ..core.logger import logger

class SimplePredictor:
    def __init__(self):
        self.model_path = "models/direction_predictor.pkl"
        self.feature_path = "models/feature_names.pkl"
        self.model = None
        self.features = None
        self.history = []  # Prices (ask/close)
        self.vol_history = []  # Volumes (optional)
        self._load_model()

    def _load_model(self):
        if os.path.exists(self.model_path):
            try:
                self.model = joblib.load(self.model_path)
                self.features = joblib.load(self.feature_path)
                logger.success("Direction Classifier loaded!")
            except Exception as e:
                logger.error(f"Failed to load model: {e}")
        else:
            logger.info("No model found. Run train_model.py first.")

    def predict_direction(self, state: dict):
        """
        Returns: (direction: int [0=down,1=up], confidence: float [0-1])
        """
        ask = state.get("current_ask", 0.0)
        volume = state.get("volume", 0.0)  # From MT5 tick if available
        self.history.append(ask)
        self.vol_history.append(volume)
        if len(self.history) > 100:
            self.history.pop(0)
            self.vol_history.pop(0)

        if self.model and len(self.history) >= 30:  # Min for features
            try:
                prices = pd.Series(self.history)
                vols = pd.Series(self.vol_history)
                
                # Recalculate features (match train_model.py exactly)
                sma10 = prices.rolling(10).mean().iloc[-1]
                sma30 = prices.rolling(30).mean().iloc[-1]
                ema12 = prices.ewm(span=12).mean().iloc[-1]
                ema26 = prices.ewm(span=26).mean().iloc[-1]
                macd = (ema12 - ema26) / ask
                vol_pct = prices.rolling(10).std().iloc[-1] / ask
                ret1 = prices.pct_change(1).iloc[-1]
                ret5 = prices.pct_change(5).iloc[-1]
                
                # RSI (simplified, handle div0)
                delta = prices.diff()
                gain = delta.where(delta > 0, 0).rolling(14).mean().iloc[-1]
                loss = -delta.where(delta < 0, 0).rolling(14).mean().iloc[-1]
                rs = gain / (loss if loss != 0 else np.finfo(float).eps)
                rsi = np.clip(100 - (100 / (1 + rs)), 0, 100)
                
                # Stoch (handle denom=0)
                low14 = prices.rolling(14).min().iloc[-1]
                high14 = prices.rolling(14).max().iloc[-1]
                denom = high14 - low14
                stoch_k = 100 * ((ask - low14) / denom) if denom != 0 else 50
                stoch_k = np.clip(stoch_k, 0, 100)
                stoch_d = stoch_k  # Simplified (use rolling if more hist)
                
                vol_change = vols.pct_change().iloc[-1] if len(vols) > 1 else 0.0
                log_vol = np.log(vols.iloc[-1] + 1) if len(vols) > 0 and vols.iloc[-1] > 0 else 0.0
                
                # ATR % (simplified: use price range as proxy for H/L)
                range_14 = (prices.rolling(14).max() - prices.rolling(14).min()).iloc[-1]
                atr_proxy = range_14 / 14  # Avg true range approx
                atr_pct = atr_proxy / ask if ask != 0 else 0.0
                
                feature_vals = [
                    ask / sma10 if sma10 != 0 else 1.0,
                    ask / sma30 if sma30 != 0 else 1.0,
                    vol_pct, macd, rsi, stoch_k, stoch_d,
                    vol_change, ret1, ret5, log_vol, atr_pct
                ]
                
                # Pad/truncate to match model features (robust)
                n_feats = len(self.features)
                if len(feature_vals) < n_feats:
                    feature_vals += [0.0] * (n_feats - len(feature_vals))
                elif len(feature_vals) > n_feats:
                    feature_vals = feature_vals[:n_feats]
                
                X = pd.DataFrame([feature_vals], columns=self.features)
                
                pred_dir = self.model.predict(X)[0]
                conf = max(self.model.predict_proba(X)[0])  # Max class prob
                
                logger.debug(f"Pred Dir: {pred_dir} | Conf: {conf:.2f} | RSI: {rsi:.1f} | ATR%: {atr_pct:.4f}")
                return int(pred_dir), float(conf)
            except Exception as e:
                logger.error(f"Predictor error: {e}")
                return 0, 0.5  # Neutral fallback
        
        return 0, 0.5  # Default no-signal