import pandas as pd

def detect_pattern(state: dict) -> str:
    """Detect a market pattern from the given state using RSI, SMA, and Momentum.
    Returns: 'bullish', 'bearish', 'strong_bullish', 'strong_bearish', 'oversold', 'overbought', or 'neutral'.
    """
    rsi = state.get("rsi", 50.0)
    current_price = state.get("current_ask", 0.0)
    sma10 = state.get("sma10", 0.0)
    
    # We can use the predictor history if available for EMA/Momentum
    predictor = state.get("predictor")
    ema20 = 0.0
    if predictor and len(predictor.history) >= 20:
        prices = pd.Series(predictor.history)
        ema20 = prices.ewm(span=20, adjust=False).mean().iloc[-1]
        mom = (prices.iloc[-1] - prices.iloc[-5]) / prices.iloc[-5] if len(prices) >= 5 else 0
    else:
        ema20 = sma10 # Fallback
        mom = 0

    # 1. Extreme Zone Check (Safety)
    # If RSI is extremely over-extended, we label it for the strategy to handle
    if rsi < 20:
        return "oversold"
    if rsi > 80:
        return "overbought"

    # 2. Trend + Momentum Confirmation
    # Strong Bullish: Price > SMA10 AND Price > EMA20 AND RSI > 60
    if current_price > sma10 and current_price > ema20 and rsi > 60:
        return "strong_bullish"
    
    # Strong Bearish: Price < SMA10 AND Price < EMA20 AND RSI < 40
    if current_price < sma10 and current_price < ema20 and rsi < 40:
        return "strong_bearish"

    # 3. Simple Trend Check
    if rsi > 52 and current_price > sma10:
        return "bullish"
    if rsi < 48 and current_price < sma10:
        return "bearish"

    return "neutral"
