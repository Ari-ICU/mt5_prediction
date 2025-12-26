from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

@dataclass
class MarketData:
    symbol: str = ""
    bid: float = 0.0
    ask: float = 0.0
    is_open: bool = False
    prediction: float = 0.0
    confidence: float = 0.0
    rsi: float = 0.0
    sma10: float = 0.0
    timestamp: datetime = field(default_factory=datetime.now)

    @property
    def spread(self) -> int:
        if self.ask > 0 and self.bid > 0:
            # Basic pips calculation (assuming 2-5 decimal places)
            return int((self.ask - self.bid) * 10000) if "JPY" not in self.symbol else int((self.ask - self.bid) * 100)
        return 0

@dataclass
class AccountData:
    name: str = "---"
    balance: float = 0.0
    equity: float = 0.0
    margin: float = 0.0
    free_margin: float = 0.0
    profit: float = 0.0
    position_count: int = 0
    currency: str = "USD"

@dataclass
class TradeSettings:
    lot: float = 0.01
    sl: float = 0.0
    tp: float = 0.0
    auto_trade: bool = False
    auto_profit_close: float = 0.0 # 0.0 means disabled
    pos_profit_limit: float = 0.0 # 0.0 means disabled
    pos_loss_limit: float = 0.0   # 0.0 means disabled
    max_positions: int = 5
    buy_threshold: float = 0.75
    sell_threshold: float = 0.75

@dataclass
class PositionData:
    ticket: int = 0
    symbol: str = ""
    type: str = "" # BUY/SELL
    volume: float = 0.0
    price_open: float = 0.0
    price_current: float = 0.0
    sl: float = 0.0
    tp: float = 0.0
    profit: float = 0.0

@dataclass
class ServerConfig:
    host: str = "127.0.0.1"
    port: int = 5555
    endpoint: str = "/trade"
    default_symbol: str = "XAUUSD"
