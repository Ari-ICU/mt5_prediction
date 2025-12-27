"""Base module for news ingestion.
Provides a placeholder function to fetch recent news headlines.
"""

import requests
import time
from .. import config
from ..core.logger import logger

_news_cache = {} # {symbol: {"data": [], "last_fetch": 0}}

def fetch_news(symbol: str) -> list:
    """Fetch recent news items for the given symbol using NewsAPI.
    Returns a list of strings (headlines).
    """
    symbol = symbol.upper()
    now = time.time()
    
    # Cache news for 30 minutes to avoid API limit (free tier)
    if symbol in _news_cache:
        cache = _news_cache[symbol]
        if now - cache["last_fetch"] < 1800:
            return cache["data"]

    if not config.NEWS_API_KEY or "PASTE_YOUR" in config.NEWS_API_KEY:
        return []

    try:
        # For XAUUSD, search for Gold and Fed news
        query = "Gold price" if "XAU" in symbol.upper() else f"{symbol} forex"
        url = f"https://newsapi.org/v2/everything?q={query}&sortBy=publishedAt&pageSize=5&apiKey={config.NEWS_API_KEY}"
        
        response = requests.get(url, timeout=5)
        if response.status_code == 200:
            articles = response.json().get("articles", [])
            headlines = [a.get("title", "") for a in articles]
            _news_cache[symbol] = {"data": headlines, "last_fetch": now}
            logger.info(f"📰 Fetched {len(headlines)} fresh news headlines for {symbol}")
            return headlines
        else:
            logger.warning(f"⚠️ NewsAPI Error: {response.status_code}")
            return []
    except Exception as e:
        logger.error(f"❌ Failed to fetch news: {e}")
        return []
