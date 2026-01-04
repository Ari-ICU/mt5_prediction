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
        
        # CHART PATTERN BOOST
        # Strong trends get a bigger boost, and we require confirmation for regular trends
        if direction == "UP":
            if pattern == "strong_bullish":
                final_conf += 40
            elif pattern == "bullish":
                final_conf += 20
            elif pattern == "oversold": # Mean reversion setup
                final_conf += 15
        elif direction == "DOWN":
            if pattern == "strong_bearish":
                final_conf += 40
            elif pattern == "bearish":
                final_conf += 20
            elif pattern == "overbought": # Mean reversion setup
                final_conf += 15
            
        # STOCHASTIC OSCILLATOR BOOST (+10%)
        # Standard Oversold/Overbought confirmation
        if direction == "UP":
            # If Oversold (K < 20) it's a good buy signal
            if stoch_k < 20:
                final_conf += 15
                logger.debug(f"📈 Stochastic Oversold (K={stoch_k:.1f}) -> BOOST")
            elif stoch_k < 50: # Mildly bullish
                final_conf += 5
        elif direction == "DOWN":
            # If Overbought (K > 80)
            if stoch_k > 80:
                final_conf += 15
                logger.debug(f"📉 Stochastic Overbought (K={stoch_k:.1f}) -> BOOST")
            elif stoch_k > 50: # Mildly bearish
                final_conf += 5

        # NEWS SENTIMENT BOOST (+15%)
        bullish_keywords = ["surge", "rally", "high", "growth", "positive", "uptrend", "bullish", "jump", "buy", "gain", "breakout"]
        bearish_keywords = ["crash", "drop", "plunge", "crisis", "negative", "low", "dip", "bearish", "fall", "sell", "loss", "breakdown"]
        sentiment_score = 0
        for h in headlines:
            h_lower = h.lower()
            if any(k in h_lower for k in bullish_keywords): sentiment_score += 1
            if any(k in h_lower for k in bearish_keywords): sentiment_score -= 1
            
        if direction == "UP" and sentiment_score > 0: final_conf += 15
        if direction == "DOWN" and sentiment_score < 0: final_conf += 15
        
        # 4. Final Final Signal Generation
        final_signal = "HOLD"
        
        # We increase the required confidence slightly for better win rate
        # buy_threshold (usually 75%)
        
        if direction == "UP":
            # Strict Filtering: Don't BUY if pattern is bearish/overbought unless AI is nearly 100%
            if (pattern in ["bearish", "strong_bearish", "overbought"]) and final_conf < 85:
                # logger.debug(f"Skipping BUY: Pattern is {pattern} and confidence {final_conf:.1f}% too low.")
                pass
            elif final_conf >= buy_threshold:
                final_signal = "BUY"
                
        elif direction == "DOWN":
            # Strict Filtering: Don't SELL if pattern is bullish/oversold unless AI is nearly 100%
            if (pattern in ["bullish", "strong_bullish", "oversold"]) and final_conf < 85:
                 # logger.debug(f"Skipping SELL: Pattern is {pattern} and confidence {final_conf:.1f}% too low.")
                 pass
            elif final_conf >= sell_threshold:
                final_signal = "SELL"

        # Log factors for the user
        if market_open:
            if final_signal != "HOLD":
                logger.success(f"🔥 FINAL SIGNAL: {final_signal} | Total Conf: {final_conf:.1f}% (AI:{base_conf:.1f}% + {final_conf-base_conf:.0f}% Boosts)")
            elif final_conf > 30: # Only log near-misses or AI decisions
                 logger.debug(f"ℹ️ HOLD: AI {direction} at {final_conf:.1f}% confidence. Stoch: {stoch_k:.1f}")
                
        return final_signal