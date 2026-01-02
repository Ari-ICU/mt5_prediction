"""Simple AI trading strategy that uses pattern detection and news headlines.
"""

from .base import StrategyBase
from src.patterns import detect_pattern
from src.news import fetch_news
from src.core.logger import logger

class SimpleStrategy(StrategyBase):
    """A very basic strategy combining pattern detection, news, and AI prediction.
    """

    def __init__(self, name: str = "SimpleStrategy"):
        super().__init__(name)

    def run(self, state: dict) -> str:
        market_open = state.get("market_is_open", False)
        
        # 1. Load Settings
        # UI Threshold (0.0-1.0) is converted to Percentage (0-100)
        buy_threshold = float(state.get("buy_threshold", 0.75)) * 100
        sell_threshold = float(state.get("sell_threshold", 0.75)) * 100
        
        predicted_price = state.get("ai_prediction", 0)
        base_conf = state.get("ai_confidence", 0)
        current_price = state.get("current_ask", 0)
        price_delta = predicted_price - current_price
        
        # 2. Get Chart Pattern & News & Indicators
        predictor = state.get("predictor")
        
        # Extract indicators from predictor state
        state["rsi"] = state.get("rsi", predictor.last_rsi if (predictor and hasattr(predictor, 'last_rsi')) else 50.0)
        stoch_k = predictor.last_stoch_k if (predictor and hasattr(predictor, 'last_stoch_k')) else 50.0
        stoch_d = predictor.last_stoch_d if (predictor and hasattr(predictor, 'last_stoch_d')) else 50.0
        
        pattern = detect_pattern(state)
        headlines = fetch_news(state.get("current_symbol", ""))
        
        # 3. Signal Fusion: Combined Confidence
        # We start with AI confidence and BOOST it based on what you see on the chart
        final_conf = base_conf
        direction = "UP" if price_delta > 0 else "DOWN"
        
        # CHART PATTERN BOOST (+30%)
        # In a trending market, 'overbought' is actually strong BULLISH momentum.
        if direction == "UP":
            if pattern in ["bullish", "oversold", "overbought"]:
                final_conf += 30 
        elif direction == "DOWN":
            if pattern in ["bearish", "overbought", "oversold"]:
                final_conf += 30 
            
        # STOCHASTIC OSCILLATOR BOOST (+10%)
        # Standard Oversold/Overbought confirmation
        if direction == "UP":
            # If Oversold (K < 20) and crossing up, it's a good buy signal
            if stoch_k < 20:
                final_conf += 10
                logger.info(f"📈 Stochastic Oversold (K={stoch_k:.1f}) -> BOOST")
        elif direction == "DOWN":
            # If Overbought (K > 80) and crossing down
            if stoch_k > 80:
                final_conf += 10
                logger.info(f"📉 Stochastic Overbought (K={stoch_k:.1f}) -> BOOST")

        # NEWS SENTIMENT BOOST (+15%)
        bullish_keywords = ["surge", "rally", "high", "growth", "positive", "uptrend", "bullish", "jump", "buy", "gain"]
        bearish_keywords = ["crash", "drop", "plunge", "crisis", "negative", "low", "dip", "bearish", "fall", "sell", "loss"]
        sentiment_score = 0
        for h in headlines:
            h_lower = h.lower()
            if any(k in h_lower for k in bullish_keywords): sentiment_score += 1
            if any(k in h_lower for k in bearish_keywords): sentiment_score -= 1
            
        if direction == "UP" and sentiment_score > 0: final_conf += 15
        if direction == "DOWN" and sentiment_score < 0: final_conf += 15
        
        # 4. Final Final Signal Generation
        final_signal = "HOLD"
        
        if direction == "UP" and final_conf >= buy_threshold:
            # Overbought is risky but allowed if AI is extremely confident
            if pattern == "overbought" and final_conf < 90:
                logger.warning(f"⚠️ MOMENTUM RISK: RSI is high ({state['rsi']:.1f}). Need >90% conf to BUY. (Current: {final_conf:.1f}%)")
            else:
                final_signal = "BUY"
                
        elif direction == "DOWN" and final_conf >= sell_threshold:
            # Oversold is risky but allowed if AI is extremely confident
            if pattern == "oversold" and final_conf < 90:
                logger.warning(f"⚠️ MOMENTUM RISK: RSI is low ({state['rsi']:.1f}). Need >90% conf to SELL. (Current: {final_conf:.1f}%)")
            else:
                final_signal = "SELL"

        # Log factors for the user
        if market_open:
            if final_signal != "HOLD":
                logger.success(f"🔥 FINAL SIGNAL: {final_signal} | Total Conf: {final_conf:.1f}% (AI:{base_conf:.1f}% + {final_conf-base_conf:.0f}% Boosts)")
            elif final_conf > 30: # Only log near-misses or AI decisions
                 logger.debug(f"ℹ️ HOLD: AI {direction} at {final_conf:.1f}% confidence. Stoch: {stoch_k:.1f}")
                
        return final_signal