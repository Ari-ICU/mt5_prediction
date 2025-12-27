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
        self.positions = []
        self.last_trade_time = 0 
        self.sent_closures = {} # {ticket_or_action: timestamp}        
        self.available_symbols = [] # From MT5 Market Watch

        # Strategy (kept for immediate trigger)
        from src.strategies.simple_strategy import SimpleStrategy
        self.strategy = SimpleStrategy()
        
        # AI Predictor
        self.predictor = None

        # Subscribe to internal events to maintain state
        events.subscribe(EventType.PRICE_UPDATE, self._on_price_update)
        events.subscribe(EventType.ACCOUNT_UPDATE, self._on_account_update)
        events.subscribe(EventType.POSITIONS_UPDATE, self._on_positions_update)
        events.subscribe(EventType.CONNECTION_CHANGE, self._on_connection_change)
        events.subscribe(EventType.SETTINGS_CHANGE, self._on_settings_update)
        events.subscribe(EventType.TRADE_COMMAND, self._on_trade_command)
        events.subscribe(EventType.SYMBOLS_AVAILABLE, self._on_symbols_available)

    def _on_symbols_available(self, syms: list):
        if syms != self.available_symbols:
            self.available_symbols = syms
            # logger.debug(f"Updated symbols list: {len(syms)} symbols found.")

    def _on_positions_update(self, data: list):
        self.positions = data
        
        # Check for Per-Position Profit/Loss Close
        if self.settings.pos_profit_limit > 0 or self.settings.pos_loss_limit > 0:
            if not self.market.is_open:
                for pos in data:
                    if (self.settings.pos_profit_limit > 0 and pos.profit >= self.settings.pos_profit_limit) or \
                       (self.settings.pos_loss_limit > 0 and pos.profit <= -self.settings.pos_loss_limit):
                        if int(time.time()) % 60 == 0:
                            logger.warning(f"🕒 Market Closed: Ticket #{pos.ticket} hit target (${pos.profit:.2f}), will close on market open.")
                return 

            now = time.time()
            for pos in data:
                # 1. Profit Target
                if self.settings.pos_profit_limit > 0 and pos.profit >= self.settings.pos_profit_limit:
                    if pos.ticket in self.sent_closures and now - self.sent_closures[pos.ticket] < 10:
                        continue
                    logger.success(f"🎯 Position Profit Target Hit! (Ticket {pos.ticket}: ${pos.profit:.2f} >= ${self.settings.pos_profit_limit:.2f})")
                    self.sent_closures[pos.ticket] = now
                    self._on_trade_command({"action": "CLOSE_TICKET", "ticket": pos.ticket})

                # 2. Loss Target (pos_loss_limit is positive in UI, so check if profit <= -limit)
                elif self.settings.pos_loss_limit > 0 and pos.profit <= -self.settings.pos_loss_limit:
                    if pos.ticket in self.sent_closures and now - self.sent_closures[pos.ticket] < 10:
                        continue
                    logger.warning(f"🛑 Position Loss Limit Hit! (Ticket {pos.ticket}: ${pos.profit:.2f} <= -${self.settings.pos_loss_limit:.2f})")
                    self.sent_closures[pos.ticket] = now
                    self._on_trade_command({"action": "CLOSE_TICKET", "ticket": pos.ticket})

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
        # Check for Auto Profit Close
        if self.settings.auto_profit_close > 0 and data.profit >= self.settings.auto_profit_close:
            if not self.market.is_open:
                if int(time.time()) % 60 == 0:
                    logger.warning(f"🕒 Market Closed: Account hit profit target (${data.profit:.2f}), will close on market open.")
                return
                
            now = time.time()
            if "CLOSE_ALL" in self.sent_closures and now - self.sent_closures["CLOSE_ALL"] < 10:
                return
                
            logger.success(f"💰 Profit Target Hit! (${data.profit:.2f} >= ${self.settings.auto_profit_close:.2f})")
            self.sent_closures["CLOSE_ALL"] = now
            self._on_trade_command({"action": "CLOSE_ALL"})

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

        if self.settings.symbol != settings.symbol and settings.symbol:
            logger.info(f"💱 Symbol changed to: {settings.symbol}")
            # Reset predictor history on symbol change to avoid mixed data
            if self.predictor:
                self.predictor.history = []
            
            # Optionally tell MT5 to change symbol if supported by EA
            self.pending_command = f"CHANGE_SYMBOL|{settings.symbol}|0|0|0"

        self.settings = settings

    def _on_trade_command(self, cmd_data: dict):
        action = cmd_data.get("action")
        # Prioritize settings symbol if available, fallback to market symbol
        symbol = cmd_data.get("symbol") or self.settings.symbol or self.market.symbol
        
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

        if action == "CLOSE_TICKET":
            ticket = cmd_data.get("ticket", 0)
            self.pending_command = f"CLOSE_TICKET|{ticket}|0|0|0"
            logger.info(f"Queued Close Ticket: #{ticket}")
            return

        if action == "MODIFY_TICKET":
            ticket = cmd_data.get("ticket", 0)
            sl = cmd_data.get("sl", self.settings.sl)
            tp = cmd_data.get("tp", self.settings.tp)
            self.pending_command = f"MODIFY_TICKET|{ticket}|0|{sl}|{tp}"
            logger.info(f"Queued Modify Ticket: #{ticket} (SL:{sl} TP:{tp})")
            return

        lot = cmd_data.get("lot", self.settings.lot)
        sl = cmd_data.get("sl", self.settings.sl)
        tp = cmd_data.get("tp", self.settings.tp)
        
        if action.startswith("CLOSE"):
            now = time.time()
            key = f"{action}_{cmd_data.get('ticket', '')}"
            if key in self.sent_closures and now - self.sent_closures[key] < 5:
                return
            self.sent_closures[key] = now

        self.pending_command = f"{action}|{symbol}|{lot}|{sl}|{tp}"
        logger.info(f"Queued Order: {action} {lot} {symbol}")

    def evaluate_strategy(self):
        """Processes AI strategy and emits signals.
        Note: Automated trade commands are only emitted if the market is OPEN.
        Includes a 30-second cooldown between automated signals.
        """
        try:
            # 1. ALWAYS calculate AI Prediction for UI display (Even if market closed)
            if self.predictor:
                pred_price = self.predictor.predict_price({
                    "current_bid": self.market.bid,
                    "current_ask": self.market.ask
                })
                self.market.prediction = pred_price
                self.market.rsi = self.predictor.last_rsi
                self.market.sma10 = self.predictor.last_sma10
                
                # Calculate confidence
                buy_threshold = float(self.settings.buy_threshold or 0.75)
                sell_threshold = float(self.settings.sell_threshold or 0.75)
                delta = pred_price - self.market.ask
                
                if delta > 0 and buy_threshold > 0:
                    self.market.confidence = (delta / buy_threshold) * 100
                elif delta < 0 and sell_threshold > 0:
                    self.market.confidence = (abs(delta) / sell_threshold) * 100
                else:
                    self.market.confidence = 0

            # 2. Market Status Awareness
            is_closed = not self.market.is_open

            # 3. Decision Matrix 
            state_dict = {
                "current_symbol": self.market.symbol,
                "current_bid": self.market.bid,
                "current_ask": self.market.ask,
                "market_is_open": self.market.is_open,
                "predictor": self.predictor,
                "buy_threshold": self.settings.buy_threshold,
                "sell_threshold": self.settings.sell_threshold,
                "ai_prediction": self.market.prediction, 
                "ai_confidence": self.market.confidence,
                "rsi": self.market.rsi,
                "sma10": self.market.sma10
            }
            
            decision = self.strategy.run(state_dict)
            
            # Normalize confidence for UI display (cap at 100%)
            display_conf = min(self.market.confidence, 100.0)
            self.market.confidence = display_conf
            
            if decision in ["BUY", "SELL"]:
                # 4. Filter Limits (Max Positions)
                if self.account.position_count >= self.settings.max_positions:
                    if int(time.time()) % 60 == 0:
                        logger.warning(f"🔔 Trade Limit: {self.account.position_count}/{self.settings.max_positions} active. Signal skipped.")
                    return

                # 5. Cooldown (30s)
                now = time.time()
                if now - self.last_trade_time < 30:
                    return

                logger.success(f"🤖 AI SIGNAL DETECTED: {decision} on {self.market.symbol}")
                self.last_trade_time = now
                
                # Conditional SL/TP
                sl_val = self.settings.sl if self.settings.auto_sl_tp else 0.0
                tp_val = self.settings.tp if self.settings.auto_sl_tp else 0.0
                
                events.emit(EventType.TRADE_COMMAND, {
                    "action": decision,
                    "sl": sl_val,
                    "tp": tp_val
                })
            else:
                # Optional: Log small updates for HOLD to show activity
                if int(time.time()) % 30 == 0:
                    logger.debug(f"Strategy Activity: AI is analyzing {self.market.symbol} (Decision: HOLD)")
                
        except Exception as e:
            logger.error(f"Strategy runtime error: {e}")

# Singleton state instance
state = AppState()