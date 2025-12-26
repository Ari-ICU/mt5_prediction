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
        
        # 1. Primary Signal: AI Price Prediction (Now uses pre-calculated data from state)
        predictor = state.get("predictor")
        buy_threshold = float(state.get("buy_threshold", 0.75))
        sell_threshold = float(state.get("sell_threshold", 0.75))
        
        predicted_price = state.get("ai_prediction", 0)
        conf_pct = state.get("ai_confidence", 0)
        current_price = state.get("current_ask", 0)
        price_delta = predicted_price - current_price
        
        ai_decision = "HOLD"
        
        if predictor and predicted_price > 0:
            try:
                log_msg = f"🤖 AI Confidence: {conf_pct:.1f}% | Pred: {predicted_price:.2f} (Δ {price_delta:+.2f})"
                
                if market_open:
                    if conf_pct >= 100:
                        logger.success(log_msg)
                    else:
                        logger.info(log_msg)
                
                if price_delta > buy_threshold:
                    ai_decision = "BUY"
                elif price_delta < -sell_threshold:
                    ai_decision = "SELL"
                    
            except Exception as e:
                logger.error(f"Error in strategy prediction: {e}")
                pass

        # 2. Secondary Confirmation: Pattern Detection
        pattern = detect_pattern(state)
        if pattern and market_open:
            logger.debug(f"🔍 Pattern detected: {pattern.upper()}")
        
        # 3. News Sentiment Analysis (Fundamental Confirmation)
        headlines = fetch_news(state.get("current_symbol", ""))
        bullish_keywords = ["surge", "rally", "high", "growth", "positive", "uptrend", "bullish", "jump"]
        bearish_keywords = ["crash", "drop", "plunge", "crisis", "negative", "low", "dip", "bearish", "fall"]
        
        sentiment_score = 0
        for h in headlines:
            h_lower = h.lower()
            for k in bullish_keywords:
                if k in h_lower: sentiment_score += 1
            for k in bearish_keywords:
                if k in h_lower: sentiment_score -= 1

        # 4. Final Decision Convergence
        final_decision = "HOLD"
        
        if ai_decision == "BUY":
            if pattern in ["bullish", "neutral", ""]:
                # Check news sentiment (Score < -1 means high bearish news)
                if sentiment_score < -1:
                    logger.warning(f"🛑 News Sentiment BLOCKS BUY: Score {sentiment_score}")
                else:
                    final_decision = "BUY"
                
        elif ai_decision == "SELL":
            if pattern in ["bearish", "neutral", ""]:
                # Check news sentiment (Score > 1 means high bullish news)
                if sentiment_score > 1:
                    logger.warning(f"🛑 News Sentiment BLOCKS SELL: Score {sentiment_score}")
                else:
                    final_decision = "SELL"

        if final_decision != "HOLD" and market_open:
            logger.success(f"🔥 FINAL SIGNAL: {final_decision} (AI + Pattern + News Confirmed)")
            return final_decision
            
        if ai_decision != "HOLD" and final_decision == "HOLD":
            logger.debug(f"ℹ️ HOLD: {ai_decision} signal filtered by news/patterns.")
            
        return "HOLD"