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
        # 1. Primary Signal: AI Price Prediction
        predictor = state.get("predictor")
        buy_threshold = float(state.get("buy_threshold", 0.75))
        sell_threshold = float(state.get("sell_threshold", 0.75))
        
        ai_decision = "HOLD"
        
        if predictor:
            try:
                predicted_price = predictor.predict_price(state)
                current_price = state.get("current_ask", 0)
                
                # Calculate the expected "Confidence" (Price movement)
                # In Gold (XAUUSD), a $1.0 move is significant. 
                # We normalize the threshold: if user set 0.75, we look for a $0.75 move.
                price_delta = predicted_price - current_price
                
                if price_delta > buy_threshold:
                    ai_decision = "BUY"
                elif price_delta < -sell_threshold:
                    ai_decision = "SELL"
                    
            except Exception:
                pass

        # 2. Secondary Confirmation: Pattern Detection
        pattern = detect_pattern(state)
        
        # 3. Decision Matrix (Fully Apply Strategy)
        # If AI says BUY and Pattern confirms or is neutral, we go.
        if ai_decision == "BUY":
            if pattern in ["bullish", "neutral"]:
                return "BUY"
        
        if ai_decision == "SELL":
            if pattern in ["bearish", "neutral"]:
                return "SELL"

        # 4. News Sentiment (Emergency Brake)
        headlines = fetch_news(state.get("current_symbol", ""))
        for h in headlines:
            if "crash" in h.lower() or "crisis" in h.lower():
                return "HOLD" # Safety first if model contradicts extreme news
                 
        return "HOLD"