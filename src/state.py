from .models.data_models import MarketData, AccountData, TradeSettings, ServerConfig
from .core.events import events, EventType
from .core.logger import logger
import time

class AppState:
    """Manages the current synchronized state of the application.
    Listens to events and maintains a local cache of the data models.
    """
    def __init__(self):
        self.market = MarketData()
        self.account = AccountData()
        self.settings = TradeSettings()
        self.server_config = ServerConfig()
        
        self.is_connected = False
        self.last_heartbeat = 0
        self.pending_command = ""
        
        # Strategy (kept for immediate trigger)
        from src.strategies.simple_strategy import SimpleStrategy
        self.strategy = SimpleStrategy()
        
        # AI Predictor
        self.predictor = None

        # Subscribe to internal events to maintain state
        events.subscribe(EventType.PRICE_UPDATE, self._on_price_update)
        events.subscribe(EventType.ACCOUNT_UPDATE, self._on_account_update)
        events.subscribe(EventType.CONNECTION_CHANGE, self._on_connection_change)
        events.subscribe(EventType.SETTINGS_CHANGE, self._on_settings_update)
        events.subscribe(EventType.TRADE_COMMAND, self._on_trade_command)

    def _on_price_update(self, data: MarketData):
        self.market = data
        self.last_heartbeat = time.time()
        if not self.is_connected:
            events.emit(EventType.CONNECTION_CHANGE, True)
        
        # Trigger strategy if auto-trade is on
        if self.settings.auto_trade:
            self.evaluate_strategy()

    def _on_account_update(self, data: AccountData):
        self.account = data

    def _on_connection_change(self, status: bool):
        if status and not self.is_connected:
            logger.success("🔌 MT5 EA Connection Established!")
        elif not status and self.is_connected:
            logger.warning("📡 MT5 EA Disconnected")
            
        self.is_connected = status
        if status:
            self.last_heartbeat = time.time()

    def _on_settings_update(self, settings: TradeSettings):
        if self.settings.auto_trade != settings.auto_trade:
            status = "ENABLED" if settings.auto_trade else "DISABLED"
            if settings.auto_trade:
                logger.success(f"🤖 AI Trading Engine {status}")
            else:
                logger.warning(f"🤖 AI Trading Engine {status}")
        
        if self.settings.lot != settings.lot:
            logger.info(f"⚙️ Global Lot updated to: {settings.lot}")

        self.settings = settings

    def _on_trade_command(self, cmd_data: dict):
        action = cmd_data.get("action")
        symbol = cmd_data.get("symbol", self.market.symbol)
        
        if action == "DATA_SYNC":
            tf = cmd_data.get("tf", "H1")
            bars = cmd_data.get("bars", "5000")
            self.pending_command = f"{action}|{symbol}|{tf}|{bars}|0"
            logger.info(f"Queued Data Sync: {symbol} {tf} ({bars} bars)")
            return

        if action == "DATA_SYNC_RANGE":
            tf = cmd_data.get("tf", "H1")
            start = cmd_data.get("start")
            end = cmd_data.get("end")
            self.pending_command = f"{action}|{symbol}|{tf}|{start}|{end}"
            logger.info(f"Queued Range Sync: {symbol} {tf} ({start} to {end})")
            return

        lot = cmd_data.get("lot", self.settings.lot)
        sl = cmd_data.get("sl", self.settings.sl)
        tp = cmd_data.get("tp", self.settings.tp)
        
        self.pending_command = f"{action}|{symbol}|{lot}|{sl}|{tp}"
        logger.info(f"Queued Order: {action} {lot} {symbol}")

    def evaluate_strategy(self):
        if not self.market.is_open:
            return

        try:
            state_dict = {
                "current_symbol": self.market.symbol,
                "current_bid": self.market.bid,
                "current_ask": self.market.ask,
                "market_is_open": self.market.is_open,
                "predictor": self.predictor,
                "buy_threshold": self.settings.buy_threshold,
                "sell_threshold": self.settings.sell_threshold
            }
            
            decision = self.strategy.run(state_dict)
            
            if decision in ["BUY", "SELL"]:
                logger.info(f"🤖 Strategy Signal: {decision}")
                events.emit(EventType.TRADE_COMMAND, {"action": decision})
                
        except Exception as e:
            logger.error(f"Strategy runtime error: {e}")

# Singleton state instance
state = AppState()