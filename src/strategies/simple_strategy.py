"""Simple AI trading strategy that uses pattern detection and news headlines.
It inherits from StrategyBase and implements a basic decision logic.
"""

from .base import StrategyBase
from src.patterns import detect_pattern
from src.news import fetch_news

class SimpleStrategy(StrategyBase):
    """A very basic strategy combining pattern detection and news.
    Returns "BUY", "SELL" or "HOLD" based on placeholder heuristics.
    """

    def __init__(self, name: str = "SimpleStrategy"):
        super().__init__(name)

    def run(self, state: dict) -> str:
        # Use pattern detection (placeholder) – if bullish pattern, BUY
        pattern = detect_pattern(state)
        if pattern == "bullish":
            return "BUY"
        # Use news headlines – if any headline contains a sell keyword, SELL
        headlines = fetch_news(state.get("current_symbol", ""))
        for h in headlines:
            if any(word in h.lower() for word in ["sell", "downgrade", "negative"]):
                return "SELL"
        # Default hold
        return "HOLD"
