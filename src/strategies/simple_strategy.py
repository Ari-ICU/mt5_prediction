"""Simple AI trading strategy that uses pattern detection and news headlines.
"""

from .base import StrategyBase
from src.patterns import detect_pattern
from src.news import fetch_news

class SimpleStrategy(StrategyBase):
    """A very basic strategy combining pattern detection, news, and AI prediction.
    """

    def __init__(self, name: str = "SimpleStrategy"):
        super().__init__(name)

    def run(self, state: dict) -> str:
        # 1. AI Price Prediction (if available)
        predictor = state.get("predictor")
        if predictor:
            try:
                predicted_price = predictor.predict_price(state)
                current_ask = state.get("current_ask", 0)
                # Simple logic: if prediction is significantly higher than current ask, BUY
                if predicted_price > current_ask + 1.0: 
                    return "BUY"
                if predicted_price < state.get("current_bid", 0) - 1.0:
                    return "SELL"
            except Exception:
                pass

        # 2. Pattern Detection
        pattern = detect_pattern(state)
        if pattern == "bullish":
            return "BUY"
        elif pattern == "bearish":
            return "SELL"

        # 3. News Sentiment (Safe guard)
        headlines = fetch_news(state.get("current_symbol", ""))
        for h in headlines:
            if any(word in h.lower() for word in ["crash", "sell", "downgrade", "crisis"]):
                return "SELL"
            if any(word in h.lower() for word in ["soar", "buy", "upgrade", "record"]):
                return "BUY"
                
        # Default
        return "HOLD"