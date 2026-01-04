"""Base module for news ingestion.
Provides a placeholder function to fetch recent news headlines.
"""

import requests
import time
from .. import config
from ..core.logger import logger

import threading

_news_cache = {} # {symbol: {"data": [], "last_fetch": 0, "is_fetching": False}}

def fetch_news(symbol: str) -> list:
    """Fetch recent news items for the given symbol.
    Returns cached results immediately and updates them in the background.
    """
    symbol = symbol.upper()
    now = time.time()
    
    # 1. Check Cache
    if symbol in _news_cache:
        cache = _news_cache[symbol]
        # If cache is reasonably fresh, return it
        if now - cache["last_fetch"] < 1800:
            return cache["data"]
        
        # If we are already fetching, don't start another thread
        if cache.get("is_fetching", False):
            return cache["data"]

    # 2. Trigger Background Fetch
    if symbol not in _news_cache:
        _news_cache[symbol] = {"data": [], "last_fetch": 0, "is_fetching": False}
    
    _news_cache[symbol]["is_fetching"] = True
    thread = threading.Thread(target=_background_fetch, args=(symbol,), daemon=True)
    thread.start()
    
    return _news_cache[symbol]["data"]

def _background_fetch(symbol: str):
    """Network-bound fetch operation to be run in a separate thread."""
    try:
        from .. import config
        if not config.NEWS_API_KEY or "PASTE_YOUR" in config.NEWS_API_KEY:
            _news_cache[symbol]["is_fetching"] = False
            return

        # For XAUUSD, search for Gold and Fed news
        query = "Gold price" if "XAU" in symbol else f"{symbol} forex"
        url = f"https://newsapi.org/v2/everything?q={query}&sortBy=publishedAt&pageSize=5&apiKey={config.NEWS_API_KEY}"
        
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            articles = response.json().get("articles", [])
            headlines = [a.get("title", "") for a in articles]
            _news_cache[symbol].update({
                "data": headlines, 
                "last_fetch": time.time(),
                "is_fetching": False
            })
            logger.info(f"📰 Async: Fetched {len(headlines)} fresh news headlines for {symbol}")
        else:
            _news_cache[symbol]["is_fetching"] = False
            
    except Exception as e:
        if symbol in _news_cache:
            _news_cache[symbol]["is_fetching"] = False
        logger.error(f"❌ Async news fetch failed: {e}")
