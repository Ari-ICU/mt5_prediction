"""Base module for pattern detection.
Provide a simple placeholder function that can be extended.
"""

def detect_pattern(state: dict) -> str:
    """Detect a market pattern from the given state using RSI and SMA.
    Returns: 'bullish', 'bearish', 'oversold', 'overbought', or 'neutral'.
    """
    rsi = state.get("rsi", 50.0)
    current_price = state.get("current_ask", 0.0)
    sma10 = state.get("sma10", 0.0)

    # 1. Extreme Zone Check (Safety)
    if rsi < 25:
        return "oversold"
    if rsi > 75:
        return "overbought"

    # 2. Strength Check
    if rsi > 55 and current_price > sma10:
        return "bullish"
    if rsi < 45 and current_price < sma10:
        return "bearish"

    return "neutral"
