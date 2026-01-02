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
        self.sent_closures = {}      
        self.available_symbols = []
        
        # Strategy
        from src.strategies.simple_strategy import SimpleStrategy
        self.strategy = SimpleStrategy()
        
        # AI Predictor
        self.predictor = None

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

    def _on_positions_update(self, data: list):
        self.positions = data
        
        # Check for Per-Position Profit/Loss Close
        if self.settings.pos_profit_limit > 0 or self.settings.pos_loss_limit > 0:
            if not self.market.is_open:
                # Log closed market warnings occasionally
                return 

            now = time.time()
            for pos in data:
                # 1. Profit Target
                if self.settings.pos_profit_limit > 0 and pos.profit >= self.settings.pos_profit_limit:
                    if pos.ticket in self.sent_closures and now - self.sent_closures[pos.ticket] < 10:
                        continue
                    logger.success(f"🎯 Position Profit Target Hit! (Ticket {pos.ticket}: ${pos.profit:.2f})")
                    self.sent_closures[pos.ticket] = now
                    self._on_trade_command({"action": "CLOSE_TICKET", "ticket": pos.ticket})

                # 2. Loss Target
                elif self.settings.pos_loss_limit > 0 and pos.profit <= -self.settings.pos_loss_limit:
                    if pos.ticket in self.sent_closures and now - self.sent_closures[pos.ticket] < 10:
                        continue
                    logger.warning(f"🛑 Position Loss Limit Hit! (Ticket {pos.ticket}: ${pos.profit:.2f})")
                    self.sent_closures[pos.ticket] = now
                    self._on_trade_command({"action": "CLOSE_TICKET", "ticket": pos.ticket})

    def _on_price_update(self, data: MarketData):
        self.market = data
        self.last_heartbeat = time.time()
        if not self.is_connected:
            events.emit(EventType.CONNECTION_CHANGE, True)
        
        if self.settings.auto_trade:
            self.evaluate_strategy()

    def _on_account_update(self, data: AccountData):
        self.account = data
        # Auto Profit Close
        if self.settings.auto_profit_close > 0 and data.profit >= self.settings.auto_profit_close:
            if not self.market.is_open:
                return
            now = time.time()
            if "CLOSE_ALL" in self.sent_closures and now - self.sent_closures["CLOSE_ALL"] < 10:
                return
            logger.success(f"💰 Profit Target Hit! (${data.profit:.2f})")
            self.sent_closures["CLOSE_ALL"] = now
            self._on_trade_command({"action": "CLOSE_ALL"})

    def _on_connection_change(self, status: bool):
        self.is_connected = status
        if status:
            logger.success("🔌 MT5 EA Connection Established!")
            self.last_heartbeat = time.time()
        else:
            logger.warning("📡 MT5 EA Disconnected")

    def _on_settings_update(self, settings: TradeSettings):
        if self.settings.auto_trade != settings.auto_trade:
            status = "ENABLED" if settings.auto_trade else "DISABLED"
            logger.info(f"🤖 AI Trading Engine {status}")
        
        if self.settings.symbol != settings.symbol and settings.symbol:
            logger.info(f"💱 Symbol changed to: {settings.symbol}")
            if self.predictor:
                self.predictor.history = []
            self.pending_command = f"CHANGE_SYMBOL|{settings.symbol}|0|0|0"

        self.settings = settings

    def _on_trade_command(self, cmd_data: dict):
        action = cmd_data.get("action")
        symbol = cmd_data.get("symbol") or self.settings.symbol or self.market.symbol
        
        # Handle Sync and Ticket commands
        if action == "DATA_SYNC":
            self.pending_command = f"{action}|{symbol}|{cmd_data.get('tf','H1')}|{cmd_data.get('bars','5000')}|0"
            logger.info(f"Queued Data Sync: {symbol}")
            return
        
        if action == "CLOSE_TICKET":
            self.pending_command = f"CLOSE_TICKET|{cmd_data.get('ticket')}|0|0|0"
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
        """Processes AI strategy with Asset-Agnostic Confidence Calculation."""
        try:
            # 1. Prediction & Confidence
            if self.predictor:
                # Pass full market state to predictor
                pred_price = self.predictor.predict_price({
                    "current_bid": self.market.bid,
                    "current_ask": self.market.ask
                })
                self.market.prediction = pred_price
                self.market.rsi = self.predictor.last_rsi
                self.market.sma10 = self.predictor.last_sma10
                
                # --- FIX: Calculate Confidence based on PERCENTAGE Change ---
                current_price = self.market.ask
                if current_price > 0:
                    predicted_change_pct = (pred_price - current_price) / current_price
                    
                    # Convert UI Threshold (e.g. 0.75) to a comparable scale
                    # If user inputs 0.75, they usually mean 0.075% or similar depending on your UI scaling.
                    # Assuming UI sends '0.75' to represent 0.075% movement required:
                    # Let's assume Buy Threshold of 1.0 = 0.1% price move required for 100% confidence.
                    
                    target_move_pct = (float(self.settings.buy_threshold or 0.75) / 1000.0) # 0.75 -> 0.00075 (0.075%)
                    
                    if target_move_pct == 0: target_move_pct = 0.0001 # Prevent divide by zero

                    if predicted_change_pct > 0:
                        self.market.confidence = (predicted_change_pct / target_move_pct) * 100
                    elif predicted_change_pct < 0:
                        self.market.confidence = (abs(predicted_change_pct) / target_move_pct) * 100
                    else:
                        self.market.confidence = 0
            
            # 2. Decision Matrix
            state_dict = {
                "current_symbol": self.market.symbol,
                "current_bid": self.market.bid,
                "current_ask": self.market.ask,
                "market_is_open": self.market.is_open,
                "predictor": self.predictor,
                "buy_threshold": self.settings.buy_threshold, # Passed for legacy strategy logic if needed
                "sell_threshold": self.settings.sell_threshold,
                "ai_prediction": self.market.prediction, 
                "ai_confidence": self.market.confidence,
                "rsi": self.market.rsi,
                "sma10": self.market.sma10
            }
            
            decision = self.strategy.run(state_dict)
            
            # Visual Cap for UI
            self.market.confidence = min(self.market.confidence, 100.0)
            
            # 3. Execution
            if decision in ["BUY", "SELL"]:
                if self.account.position_count >= self.settings.max_positions:
                    if int(time.time()) % 60 == 0:
                        logger.warning(f"🔔 Trade Limit Reached. Signal skipped.")
                    return

                # Cooldown
                now = time.time()
                if now - self.last_trade_time < 30:
                    return

                logger.success(f"🤖 AI SIGNAL: {decision} on {self.market.symbol} (Conf: {self.market.confidence:.1f}%)")
                self.last_trade_time = now
                
                events.emit(EventType.TRADE_COMMAND, {
                    "action": decision,
                    "sl": self.settings.sl if self.settings.auto_sl_tp else 0.0,
                    "tp": self.settings.tp if self.settings.auto_sl_tp else 0.0
                })
                
        except Exception as e:
            logger.error(f"Strategy runtime error: {e}")

# Singleton
state = AppState()