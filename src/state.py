from .models.data_models import MarketData, AccountData, TradeSettings, ServerConfig
from .core.events import events, EventType
from .core.logger import logger
from . import config
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
        self.pending_commands = [] # Queue for multiple commands
        self.positions = []
        self.last_trade_time = 0 
        self.sent_closures = {}      
        self.available_symbols = []
        self.day_start_balance = 0.0
        self.daily_loss_limit_hit = False
        self.last_strategy_eval = 0 # Throttling
        
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
                # 0. Aggressive Break-Even & Trailing SL
                if pos.profit > 0 and self.market.atr > 0:
                    atr = self.market.atr
                    current_price = self.market.bid if pos.type == 0 else self.market.ask
                    profit_in_atr = pos.profit / (atr * (100 if "XAU" in self.market.symbol else 1.0))

                    # Logic 1: Move to Break-Even (at 0.7x ATR Profit)
                    if profit_in_atr >= config.BREAK_EVEN_TRIGGER:
                        # Add a tiny buffer (10 points) to the break-even to cover spread
                        buffer = 0.0001 if "XAU" not in self.market.symbol else 0.1
                        if pos.type == 0: # BUY
                            if pos.sl < pos.price_open:
                                logger.success(f"🛡️ Protection: SL to Break-Even for Ticket {pos.ticket}")
                                self._on_trade_command({"action": "MODIFY_TICKET", "ticket": pos.ticket, "sl": pos.price_open + buffer, "tp": pos.tp})
                        else: # SELL
                            if pos.sl == 0 or pos.sl > pos.price_open:
                                logger.success(f"🛡️ Protection: SL to Break-Even for Ticket {pos.ticket}")
                                self._on_trade_command({"action": "MODIFY_TICKET", "ticket": pos.ticket, "sl": pos.price_open - buffer, "tp": pos.tp})

                    # Logic 2: Standard Trailing (at 1.5x ATR Profit)
                    if profit_in_atr >= config.TRAILING_STOP_MULT:
                        if pos.type == 0: # BUY
                            new_sl = current_price - (atr * config.TRAILING_STOP_MULT)
                            if new_sl > pos.sl + (atr * 0.1): # Only update if moving up significantly
                                self._on_trade_command({"action": "MODIFY_TICKET", "ticket": pos.ticket, "sl": new_sl, "tp": pos.tp})
                        else: # SELL
                            new_sl = current_price + (atr * config.TRAILING_STOP_MULT)
                            if (pos.sl == 0 or new_sl < pos.sl - (atr * 0.1)):
                                self._on_trade_command({"action": "MODIFY_TICKET", "ticket": pos.ticket, "sl": new_sl, "tp": pos.tp})

                # 1. Profit Target (Aggressive Close)
                if self.settings.pos_profit_limit > 0 and pos.profit >= self.settings.pos_profit_limit:
                    if pos.ticket in self.sent_closures and now - self.sent_closures[pos.ticket] < 2:
                        continue
                    logger.success(f"Position Profit Target Hit! (Ticket {pos.ticket}: ${pos.profit:.2f})")
                    self.sent_closures[pos.ticket] = now
                    self._on_trade_command({"action": "CLOSE_TICKET", "ticket": pos.ticket})

                # 2. Loss Target
                elif self.settings.pos_loss_limit > 0 and pos.profit <= -self.settings.pos_loss_limit:
                    if pos.ticket in self.sent_closures and now - self.sent_closures[pos.ticket] < 2:
                        continue
                    logger.warning(f"Position Loss Limit Hit! (Ticket {pos.ticket}: ${pos.profit:.2f})")
                    self.sent_closures[pos.ticket] = now
                    self._on_trade_command({"action": "CLOSE_TICKET", "ticket": pos.ticket})

    def _on_price_update(self, data: MarketData):
        self.market = data
        self.last_heartbeat = time.time()
        if not self.is_connected:
            events.emit(EventType.CONNECTION_CHANGE, True)
        
        if self.settings.auto_trade:
            # Throttle strategy evaluation to max 2Hz to avoid CPU chugging
            now = time.time()
            if now - self.last_strategy_eval >= 0.5:
                self.evaluate_strategy()
                self.last_strategy_eval = now

    def _on_account_update(self, data: AccountData):
        if self.day_start_balance == 0:
            self.day_start_balance = data.balance
        
        # Check Daily Drawdown
        total_loss = self.day_start_balance - data.equity
        if total_loss > (self.day_start_balance * config.MAX_DAILY_LOSS):
            if not self.daily_loss_limit_hit:
                logger.error(f"⚠️ DAILY LOSS LIMIT HIT! Stopped trading for today. Loss: ${total_loss:.2f}")
                self.daily_loss_limit_hit = True
        
        self.account = data
        # Auto Profit Close
        if self.settings.auto_profit_close > 0 and data.profit >= self.settings.auto_profit_close:
            if not self.market.is_open:
                return
            now = time.time()
            if "CLOSE_ALL" in self.sent_closures and now - self.sent_closures["CLOSE_ALL"] < 2:
                return
            logger.success(f"Profit Target Hit! (${data.profit:.2f})")
            self.sent_closures["CLOSE_ALL"] = now
            self._on_trade_command({"action": "CLOSE_ALL"})

    def _on_connection_change(self, status: bool):
        self.is_connected = status
        if status:
            logger.success("MT5 EA Connection Established!")
            self.last_heartbeat = time.time()
        else:
            logger.warning("MT5 EA Disconnected")

    def _on_settings_update(self, settings: TradeSettings):
        if self.settings.auto_trade != settings.auto_trade:
            status = "ENABLED" if settings.auto_trade else "DISABLED"
            logger.info(f"AI Trading Engine {status}")
        
        if self.settings.symbol != settings.symbol and settings.symbol:
            logger.info(f"Symbol changed to: {settings.symbol}")
            if self.predictor:
                self.predictor.history = []
            self._on_trade_command({"action": "CHANGE_SYMBOL", "symbol": settings.symbol})

        self.settings = settings

    def _on_trade_command(self, cmd_data: dict):
        action = cmd_data.get("action")
        symbol = cmd_data.get("symbol") or self.settings.symbol or self.market.symbol
        
        # Handle Sync and Ticket commands
        if action == "DATA_SYNC":
            self.pending_commands.append(f"{action}|{symbol}|{cmd_data.get('tf','H1')}|{cmd_data.get('bars','5000')}|0")
            logger.info(f"Queued Data Sync: {symbol}")
            return
        
        if action == "CLOSE_TICKET":
            self.pending_commands.append(f"CLOSE_TICKET|{cmd_data.get('ticket')}|0|0|0")
            return
        
        if action == "MODIFY_TICKET":
            self.pending_commands.append(f"MODIFY_TICKET|{cmd_data.get('ticket')}|0|{cmd_data.get('sl')}|{cmd_data.get('tp')}")
            return

        lot = cmd_data.get("lot", self.settings.lot)
        sl = cmd_data.get("sl", self.settings.sl)
        tp = cmd_data.get("tp", self.settings.tp)
        
        if action.startswith("CLOSE"):
            now = time.time()
            key = f"{action}_{cmd_data.get('ticket', '')}"
            if key in self.sent_closures and now - self.sent_closures[key] < 1:
                return
            self.sent_closures[key] = now

        self.pending_commands.append(f"{action}|{symbol}|{lot}|{sl}|{tp}")
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
                self.market.sma200 = self.predictor.last_sma200
                self.market.atr = self.predictor.last_atr  # New: ATR for dynamic levels
                
                # --- FIX: Calculate Confidence based on PERCENTAGE Change ---
                current_price = self.market.ask
                if current_price > 0:
                    predicted_change_pct = (pred_price - current_price) / current_price
                    
                    # Convert UI Threshold (e.g. 0.75) to a comparable scale
                    # If user inputs 0.75, they usually mean 0.075% or similar depending on your UI scaling.
                    # Assuming UI sends '0.75' to represent 0.075% movement required for 100% confidence.
                    # Let's assume Buy Threshold of 1.0 = 0.1% price move required for 100% confidence.
                    
                    target_move_pct = (float(self.settings.buy_threshold or 0.75) / 1000.0) # 0.75 -> 0.075%
                    if target_move_pct == 0: target_move_pct = 0.0001

                    # Raw confidence based on price movement vs threshold
                    raw_conf = (abs(predicted_change_pct) / target_move_pct) * 100
                    
                    # Sigmoid-like scaling or simple cap
                    self.market.confidence = min(raw_conf, 120.0) # Allow slightly over 100 before boosters
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
                # --- RISK FILTERS ---
                
                # Filter 0: Daily Loss Limit
                if self.daily_loss_limit_hit:
                    return

                # Filter 1: Confidence
                if self.market.confidence < config.MIN_CONFIDENCE_FOR_TRADE:
                    if int(time.time()) % 20 == 0:
                         logger.debug(f"Signal filtered: {decision} (Conf: {self.market.confidence:.1f}%) - Below {config.MIN_CONFIDENCE_FOR_TRADE}%")
                    return
                
                # --- SIGNAL REVERSAL EXIT ---
                # Before opening NEW, close OPPOSITE if we have high confidence reversal
                if self.market.confidence >= 90:
                    for pos in self.positions:
                        if (decision == "BUY" and pos.type == 1) or (decision == "SELL" and pos.type == 0):
                            logger.info(f"🔄 Reversal detected! Closing opposite Ticket {pos.ticket} before {decision}")
                            self._on_trade_command({"action": "CLOSE_TICKET", "ticket": pos.ticket})
                
                # Filter 2: Spread Filter (Don't trade if spread is too wide vs ATR)
                atr = self.market.atr
                if atr > 0:
                    current_spread = self.market.ask - self.market.bid
                    # Spread shouldn't eat more than 80% of average move or 40% of our Target Profit (atr*2.5)
                    # 40% of (atr * 2.5) = 1.0 * atr.
                    if current_spread > (atr * 1.5): 
                        logger.warning(f"Trade skipped: Spread too wide ({current_spread:.5f} > 1.5x ATR {atr:.5f})")
                        return
                
                # Filter 3: Position Limit
                if self.account.position_count >= self.settings.max_positions:
                    if int(time.time()) % 60 == 0:
                        logger.warning(f"Trade Limit Reached. Signal skipped.")
                    return
                
                # Filter 4: Trend Filter (Don't trade against the major trend)
                if self.market.sma200 > 0:
                    current_price = self.market.ask
                    if decision == "BUY" and current_price < self.market.sma200:
                         # logger.debug(f"BUY Filtered: Price {current_price:.2f} < SMA200 {self.market.sma200:.2f}")
                         return
                    if decision == "SELL" and current_price > self.market.sma200:
                         # logger.debug(f"SELL Filtered: Price {current_price:.2f} > SMA200 {self.market.sma200:.2f}")
                         return

                # Cooldown
                now = time.time()
                if now - self.last_trade_time < 30:
                    return

                # New: DYNAMIC Reward Scaling for higher win-rate
                # High Confidence (95%+) -> Aim for big moves (3x ATR)
                # Lower Confidence (85%+) -> Take profit faster (1.5x ATR)
                conf_normalized = (self.market.confidence - config.MIN_CONFIDENCE_FOR_TRADE) / (100 - config.MIN_CONFIDENCE_FOR_TRADE)
                reward_mult = config.TP_MIN_MULT + (conf_normalized * (config.TP_MAX_MULT - config.TP_MIN_MULT))
                reward_mult = max(config.TP_MIN_MULT, min(config.TP_MAX_MULT, reward_mult))

                sl_dist = atr * 1.0 
                tp_dist = atr * reward_mult

                if decision == "BUY":
                    sl = self.market.ask - sl_dist
                    tp = self.market.ask + tp_dist
                else:  # SELL
                    sl = self.market.ask + sl_dist
                    tp = self.market.ask - tp_dist

                # Filter 5: Position Sizing
                if self.settings.auto_lot:
                    # Dynamic Risk % of Equity
                    risk_amount = self.account.balance * config.RISK_PER_TRADE
                    if risk_amount > 0 and sl_dist > 0:
                        scale = 100 if "XAU" in self.market.symbol else 1.0
                        calculated_lot = risk_amount / (sl_dist * scale)
                        lot = round(max(config.MIN_LOT_SIZE, min(config.MAX_LOT_SIZE, calculated_lot)), 2)
                    else:
                        lot = self.settings.lot
                else:
                    # Manual Lot from UI
                    lot = self.settings.lot

                logger.success(f"AI SIGNAL: {decision} {lot} on {self.market.symbol} (Conf: {self.market.confidence:.1f}%) | Trend: {'UP' if self.market.ask > self.market.sma200 else 'DOWN'} | SL/TP: {sl:.5f}/{tp:.5f}")
                self.last_trade_time = now
                
                events.emit(EventType.TRADE_COMMAND, {
                    "action": decision,
                    "symbol": self.market.symbol,
                    "lot": lot,
                    "sl": sl,
                    "tp": tp
                })
                
        except Exception as e:
            logger.error(f"Strategy runtime error: {e}")

# Singleton
state = AppState()