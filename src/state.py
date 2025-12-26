from datetime import datetime
from src.strategies.simple_strategy import SimpleStrategy

class AppState:
    def __init__(self):
        # Strategy Engine
        self.strategy = SimpleStrategy()
        
        # Connection State
        self.is_connected = False
        self.last_poll_time = 0
        
        # Market Data
        self.current_symbol = ""
        self.current_bid = 0.0
        self.current_ask = 0.0
        self.last_price = 0.0
        self.market_is_open = False
        self.last_market_status = None

        # Account Data
        self.account_name = "---"
        self.account_balance = 0.0
        self.account_equity = 0.0
        self.account_margin = 0.0
        self.account_free_margin = 0.0
        self.account_profit = 0.0
        
        # Trading Settings (Synced with GUI)
        self.trade_settings = {
            "lot": 0.01,
            "sl": 0.0,
            "tp": 0.0
        }
        
        # Command Queue
        self.pending_command = ""
        
        # Auto Trading
        self.auto_trade_enabled = False
        
        # UI Callbacks
        self.log_callback = None
        self.connection_callback = None
        self.market_status_callback = None
        self.price_update_callback = None
        self.account_update_callback = None
        
        # AI Predictor (Attached from main.py)
        self.predictor = None

    def log(self, msg, log_type="info"):
        if self.log_callback:
            self.log_callback(msg, log_type)
        else:
            print(f"[{log_type.upper()}] {msg}")

    def update_connection(self, status):
        self.is_connected = status
        if self.connection_callback:
            self.connection_callback(status)

    def update_market(self, is_open):
        self.market_is_open = is_open
        if self.market_status_callback:
            self.market_status_callback(is_open)

    def update_price(self, symbol, bid, ask):
        self.current_symbol = symbol
        self.current_bid = bid
        self.current_ask = ask
        
        if self.price_update_callback:
            self.price_update_callback(symbol, bid, ask)
            
        # TRIGGER: Evaluate strategy immediately on new price data
        if self.market_is_open:
            self.evaluate_strategy()

    def update_account(self, name, balance, equity, margin, free_margin, profit):
        self.account_name = name
        self.account_balance = balance
        self.account_equity = equity
        self.account_margin = margin
        self.account_free_margin = free_margin
        self.account_profit = profit
        if self.account_update_callback:
            self.account_update_callback(name, balance, equity, margin, free_margin, profit)

    def update_trade_settings(self, lot, sl, tp):
        """Called by GUI to sync trading parameters."""
        try:
            self.trade_settings["lot"] = float(lot)
            self.trade_settings["sl"] = float(sl)
            self.trade_settings["tp"] = float(tp)
        except ValueError:
            pass # Ignore invalid inputs while typing

    def queue_command(self, action, symbol=None, lot=None, sl=None, tp=None):
        """Centralized method to queue commands for MT5."""
        if not symbol: symbol = self.current_symbol
        if lot is None: lot = self.trade_settings["lot"]
        if sl is None: sl = self.trade_settings["sl"]
        if tp is None: tp = self.trade_settings["tp"]

        # Format: ACTION|SYMBOL|LOT|SL|TP
        cmd = f"{action}|{symbol}|{lot}|{sl}|{tp}"
        self.pending_command = cmd
        self.log(f"Queued: {action} ({symbol})", "info")

    def evaluate_strategy(self):
        """Run the strategy and execute trade if Auto-Trading is enabled."""
        if not self.auto_trade_enabled:
            return

        try:
            # Build state dict for strategy
            state_dict = {
                "current_symbol": self.current_symbol,
                "current_bid": self.current_bid,
                "current_ask": self.current_ask,
                "market_is_open": self.market_is_open,
                "predictor": self.predictor # Pass AI predictor if needed
            }
            
            decision = self.strategy.run(state_dict)
            
            if decision in ["BUY", "SELL"]:
                self.log(f"🤖 AI Decision: {decision}", "success")
                self.queue_command(decision)
                
        except Exception as e:
            self.log(f"Strategy error: {e}", "error")

# Global singleton instance
state = AppState()