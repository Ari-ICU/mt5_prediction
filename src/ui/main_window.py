import tkinter as tk
from tkinter import ttk
import datetime
import threading
import time
from .. import config
from ..core.events import events, EventType
from ..core.logger import logger
from ..models.data_models import MarketData, AccountData, TradeSettings
from .components.widgets import Card, ModernButton, ActionButton

class MainWindow:
    def __init__(self, root):
        self.root = root
        self.root.title("MT5 PRO TERMINAL")
        self.root.geometry(f"{config.WINDOW_WIDTH}x{config.WINDOW_HEIGHT}")
        self.root.configure(bg=config.THEME_COLOR)
        
        # UI State Variables
        self.lot_var = tk.StringVar(value=config.DEFAULT_LOT_SIZE)
        self.sl_var = tk.StringVar(value=config.DEFAULT_SL)
        self.tp_var = tk.StringVar(value=config.DEFAULT_TP)
        self.auto_trade_var = tk.BooleanVar(value=False)
        
        # Account / Server Config Variables
        self.host_var = tk.StringVar(value=config.HOST)
        self.port_var = tk.StringVar(value=str(config.PORT))
        self.endpoint_var = tk.StringVar(value=config.ENDPOINT)
        self.default_symbol_var = tk.StringVar(value=config.DEFAULT_SYMBOL)
        self.buy_conf_var = tk.StringVar(value="0.75")
        self.sell_conf_var = tk.StringVar(value="0.75")
        self.profit_target_var = tk.StringVar(value="0.0")
        self.pos_profit_var = tk.StringVar(value="0.0")
        self.pos_loss_var = tk.StringVar(value="0.0")
        self.auto_sl_tp_var = tk.BooleanVar(value=True)
        self.max_pos_var = tk.StringVar(value="5")
        
        # Data Sync Variables
        self.sync_timeframe = tk.StringVar(value="H1")
        self.sync_bars = tk.StringVar(value="5000")
        self.sync_start_date = tk.StringVar(value=time.strftime("%Y.%m.%d"))
        self.sync_end_date = tk.StringVar(value=time.strftime("%Y.%m.%d"))
        self.sync_symbol_var = tk.StringVar(value=config.DEFAULT_SYMBOL)
        
        self.last_auto_sl_tp = False
        self.symbol_combos = [] # Track combos to update values
        
        # Build UI
        self._setup_styles()
        self._setup_layout()
        
        # Setup Event Subscriptions
        events.subscribe(EventType.PRICE_UPDATE, self._on_price_update)
        events.subscribe(EventType.ACCOUNT_UPDATE, self._on_account_update)
        events.subscribe(EventType.LOG_MESSAGE, self._on_log_message)
        events.subscribe(EventType.CONNECTION_CHANGE, self._on_connection_change)
        events.subscribe(EventType.SYMBOLS_AVAILABLE, self._on_symbols_update)
        
        # Bind Settings Changes
        for var in [self.lot_var, self.sl_var, self.tp_var, self.auto_trade_var, self.buy_conf_var, self.sell_conf_var, self.profit_target_var, self.max_pos_var, self.pos_profit_var, self.pos_loss_var, self.auto_sl_tp_var, self.default_symbol_var]:
            var.trace_add("write", self._broadcast_settings)
        
        # Initial sync
        self._broadcast_settings()

    def _broadcast_settings(self, *args):
        try:
            settings = TradeSettings(
                symbol=self.default_symbol_var.get(),
                lot=float(self.lot_var.get() or 0.01),
                sl=float(self.sl_var.get() or 0),
                tp=float(self.tp_var.get() or 0),
                auto_trade=self.auto_trade_var.get(),
                auto_profit_close=float(self.profit_target_var.get() or 0.0),
                pos_profit_limit=float(self.pos_profit_var.get() or 0.0),
                pos_loss_limit=float(self.pos_loss_var.get() or 0.0),
                auto_sl_tp=self.auto_sl_tp_var.get(),
                max_positions=int(self.max_pos_var.get() or 5),
                buy_threshold=float(self.buy_conf_var.get() or 0.75),
                sell_threshold=float(self.sell_conf_var.get() or 0.75)
            )
            events.emit(EventType.SETTINGS_CHANGE, settings)
            
            # Auto-generate/Sync logic
            if settings.auto_sl_tp and not self.last_auto_sl_tp:
                # 1. Auto-generate values if they are 0
                if float(self.sl_var.get() or 0) == 0:
                    self._populate_current_price(self.sl_var)
                if float(self.tp_var.get() or 0) == 0:
                    self._populate_current_price(self.tp_var)
                
                # 2. Sync to active trades
                self.root.after(100, self._sync_all_sl_tp)
                
            self.last_auto_sl_tp = settings.auto_sl_tp
        except ValueError:
            pass

    def _save_config(self, *args):
        from ..state import state
        try:
            state.server_config.host = self.host_var.get()
            state.server_config.port = int(self.port_var.get())
            state.server_config.endpoint = self.endpoint_var.get()
            state.server_config.default_symbol = self.default_symbol_var.get()
            logger.info("✅ Configuration saved to state (Restart required for API changes)")
        except ValueError:
            logger.error("❌ Invalid configuration values")

    def _setup_styles(self):
        style = ttk.Style()
        style.theme_use('clam')
        
        # Notebook Styling
        style.configure("TNotebook", background=config.THEME_COLOR, borderwidth=0)
        style.configure("TNotebook.Tab", background=config.HEADER_BG, foreground=config.TEXT_SECONDARY, 
                        padding=[20, 10], font=(config.FONT_BOLD, 10), borderwidth=0)
        style.map("TNotebook.Tab", 
                  background=[("selected", config.CARD_BG)], 
                  foreground=[("selected", config.TEXT_PRIMARY)])

        # Combobox Styling
        style.configure("TCombobox", fieldbackground=config.INPUT_BG, background=config.CARD_BG, 
                        foreground=config.TEXT_PRIMARY, borderwidth=0, arrowcolor=config.ACCENT_BLUE)
        self.root.option_add("*TCombobox*Listbox.background", config.INPUT_BG)
        self.root.option_add("*TCombobox*Listbox.foreground", config.TEXT_PRIMARY)
        self.root.option_add("*TCombobox*Listbox.selectBackground", config.ACCENT_BLUE)
        self.root.option_add("*TCombobox*Listbox.font", (config.FONT_MONO, 11))

    def _setup_layout(self):
        # Header
        self._setup_header()
        
        # Tabs Container
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill="both", expand=True, padx=20, pady=(10, 20))
        
        # 1. Terminal Tab
        self.terminal_tab = tk.Frame(self.notebook, bg=config.THEME_COLOR)
        self.notebook.add(self.terminal_tab, text=" TERMINAL ")
        self._setup_terminal_tab()
        
        # 2. Auto-Trading Tab
        self.auto_tab = tk.Frame(self.notebook, bg=config.THEME_COLOR)
        self.notebook.add(self.auto_tab, text=" AUTO-TRADING ")
        self._setup_auto_tab()
        
        # 3. Account Config Tab
        self.config_tab = tk.Frame(self.notebook, bg=config.THEME_COLOR)
        self.notebook.add(self.config_tab, text=" ACCOUNT CONFIG ")
        self._setup_config_tab()

        # 4. Data Manager Tab
        self.data_tab = tk.Frame(self.notebook, bg=config.THEME_COLOR)
        self.notebook.add(self.data_tab, text=" DATA MANAGER ")
        self._setup_data_tab()

    def _setup_terminal_tab(self):
        # Content container
        content = tk.Frame(self.terminal_tab, bg=config.THEME_COLOR)
        content.pack(fill="both", expand=True, pady=10)
        content.columnconfigure(0, weight=3)
        content.columnconfigure(1, weight=2)
        
        left_col = tk.Frame(content, bg=config.THEME_COLOR)
        left_col.grid(row=0, column=0, sticky="nsew", padx=(0, 20))
        
        right_col = tk.Frame(content, bg=config.THEME_COLOR)
        right_col.grid(row=0, column=1, sticky="nsew")
        
        self._setup_market_card(left_col)
        self._setup_trade_card(left_col)
        self._setup_account_card(right_col)
        self._setup_log_card(right_col)

    def _setup_auto_tab(self):
        container = tk.Frame(self.auto_tab, bg=config.THEME_COLOR)
        container.pack(fill="both", expand=True, pady=20)
        
        card = Card(container)
        card.pack(fill="x")
        
        tk.Label(card, text="STRATEGY CONFIGURATION", font=(config.FONT_BOLD, 14, "bold"), 
                 fg=config.ACCENT_BLUE, bg=config.CARD_BG).pack(anchor="w", pady=(0, 20))

        # Auto Toggle in Tab too
        self.cb_auto_tab = tk.Checkbutton(card, text="ACTIVATE AI TRADING ENGINE", variable=self.auto_trade_var,
                                          bg=config.CARD_BG, fg=config.ACCENT_GREEN, selectcolor=config.CARD_BG,
                                          activebackground=config.CARD_BG, font=(config.FONT_BOLD, 12, "bold"))
        self.cb_auto_tab.pack(anchor="w", pady=10)
        
        tk.Label(card, text="The AI Trading Engine uses real-time market patterns, news sentiment, and linear regression price forecasting to execute trades automatically.", 
                 font=(config.FONT_MAIN, 10), fg=config.TEXT_MUTED, bg=config.CARD_BG, wraplength=800, justify="left").pack(anchor="w", pady=(0, 20))

        # Example threshold settings
        settings_frame = tk.Frame(card, bg=config.CARD_BG)
        settings_frame.pack(fill="x")
        
        self._create_input_field(settings_frame, "BUY CONFIDENCE (0.01-1.0)", self.buy_conf_var).pack(side="left", padx=(0, 20))
        self._create_input_field(settings_frame, "SELL CONFIDENCE (0.01-1.0)", self.sell_conf_var).pack(side="left", padx=(0, 20))
        
        # New SL/TP fields for Auto-Trading visibility
        sl_field = self._create_input_field(settings_frame, "AUTO STOP LOSS", self.sl_var)
        sl_field.pack(side="left", padx=(0, 20))
        sl_field.winfo_children()[1].configure(fg=config.ACCENT_RED) # Color the input
        
        tp_field = self._create_input_field(settings_frame, "AUTO TAKE PROFIT", self.tp_var)
        tp_field.pack(side="left", padx=(0, 20))
        tp_field.winfo_children()[1].configure(fg=config.ACCENT_GREEN) # Color the input

        # Row 2 for Profit Targets
        targets_frame = tk.Frame(card, bg=config.CARD_BG)
        targets_frame.pack(fill="x", pady=(20, 0))
        
        self._create_input_field(targets_frame, "TOT. PROFIT ($)", self.profit_target_var).pack(side="left", padx=(0, 20))
        self._create_input_field(targets_frame, "POS. PROFIT ($)", self.pos_profit_var).pack(side="left", padx=(0, 20))
        self._create_input_field(targets_frame, "POS. LOSS ($)", self.pos_loss_var).pack(side="left", padx=(0, 20))
        
        # Auto SL/TP Checkbox
        sl_tp_check = tk.Checkbutton(
            targets_frame,
            text="AUTO SL/TP",
            variable=self.auto_sl_tp_var,
            bg=config.CARD_BG,
            fg=config.ACCENT_BLUE,
            selectcolor=config.THEME_COLOR,
            activebackground=config.CARD_BG,
            activeforeground=config.ACCENT_BLUE,
            font=(config.FONT_BOLD, 10)
        )
        sl_tp_check.pack(side="left", padx=(0, 20))
        
        self._create_input_field(targets_frame, "LIMIT", self.max_pos_var).pack(side="left", padx=(0, 20))

        # Sync Button
        ModernButton(targets_frame, "SYNC SL/TP TO ALL", self._sync_all_sl_tp, config.ACCENT_BLUE, config.TEXT_ON_ACCENT).pack(side="left")

    def _setup_config_tab(self):
        container = tk.Frame(self.config_tab, bg=config.THEME_COLOR)
        container.pack(fill="both", expand=True, pady=20)
        
        card = Card(container)
        card.pack(fill="x")
        
        tk.Label(card, text="SERVER & ACCOUNT SETTINGS", font=(config.FONT_BOLD, 14, "bold"), 
                 fg=config.ACCENT_PURPLE, bg=config.CARD_BG).pack(anchor="w", pady=(0, 20))

        # Grid for settings
        grid = tk.Frame(card, bg=config.CARD_BG)
        grid.pack(fill="x")
        
        # Server Settings Row
        row1 = tk.Frame(grid, bg=config.CARD_BG)
        row1.pack(fill="x", pady=10)
        self._create_input_field(row1, "HOST ADDRESS", self.host_var).pack(side="left", padx=(0, 20))
        self._create_input_field(row1, "PORT", self.port_var).pack(side="left", padx=(0, 20))
        self._create_input_field(row1, "API ENDPOINT", self.endpoint_var).pack(side="left")

        # Trading Defaults Row
        row2 = tk.Frame(grid, bg=config.CARD_BG)
        row2.pack(fill="x", pady=(20, 10))
        self._create_combo_field(row2, "DEFAULT SYMBOL", self.default_symbol_var, config.SYMBOL_OPTIONS).pack(side="left", padx=(0, 20))
        
        # Info note
        tk.Label(card, text="Note: Changing Server Settings requires an application restart to take effect.", 
                 font=(config.FONT_MAIN, 9, "italic"), fg=config.TEXT_MUTED, bg=config.CARD_BG).pack(anchor="w", pady=(20, 0))
        
        # Save Button Placeholder
        btn_frame = tk.Frame(card, bg=config.CARD_BG)
        btn_frame.pack(fill="x", pady=(30, 0))
        ModernButton(btn_frame, "SAVE CONFIGURATION", self._save_config, config.INPUT_BG, config.TEXT_PRIMARY).pack(side="left")

    def _setup_data_tab(self):
        container = tk.Frame(self.data_tab, bg=config.THEME_COLOR)
        container.pack(fill="both", expand=True, pady=20)
        
        card = Card(container)
        card.pack(fill="x")
        
        tk.Label(card, text="HISTORICAL DATA EXTRACTION", font=(config.FONT_BOLD, 14, "bold"), 
                 fg=config.ACCENT_GREEN, bg=config.CARD_BG).pack(anchor="w", pady=(0, 20))

        tk.Label(card, text="Request customized historical data from MetaTrader 5 for AI model training.", 
                 font=(config.FONT_MAIN, 10), fg=config.TEXT_MUTED, bg=config.CARD_BG).pack(anchor="w", pady=(0, 20))

        # Controls
        ctrls = tk.Frame(card, bg=config.CARD_BG)
        ctrls.pack(fill="x", pady=10)

        # Symbol Dropdown
        sym_frame = tk.Frame(ctrls, bg=config.CARD_BG)
        sym_frame.pack(side="left", padx=(0, 30))
        self._create_combo_field(sym_frame, "SYMBOL", self.sync_symbol_var, config.SYMBOL_OPTIONS).pack()

        # Timeframe Dropdown
        tf_frame = tk.Frame(ctrls, bg=config.CARD_BG)
        tf_frame.pack(side="left", padx=(0, 30))
        tk.Label(tf_frame, text="TIMEFRAME", font=(config.FONT_BOLD, 9), fg=config.TEXT_SECONDARY, bg=config.CARD_BG).pack(anchor="w", pady=(0, 5))
        tf_options = ["M1", "M5", "M15", "M30", "H1", "H4", "D1"]
        tf_menu = tk.OptionMenu(tf_frame, self.sync_timeframe, *tf_options)
        tf_menu.config(bg=config.INPUT_BG, fg=config.TEXT_PRIMARY, bd=0, highlightthickness=0, width=10)
        tf_menu["menu"].config(bg=config.INPUT_BG, fg=config.TEXT_PRIMARY)
        tf_menu.pack()

        # Bars Count / Date Selection
        row2 = tk.Frame(card, bg=config.CARD_BG)
        row2.pack(fill="x", pady=10)

        # Labels for clarity
        tk.Label(row2, text="OR SPECIFY DATE RANGE (YYYY.MM.DD)", font=(config.FONT_BOLD, 9), 
                 fg=config.TEXT_MUTED, bg=config.CARD_BG).pack(anchor="w", pady=(10, 5))

        dates_frame = tk.Frame(row2, bg=config.CARD_BG)
        dates_frame.pack(fill="x")

        self._create_input_field(dates_frame, "START DATE", self.sync_start_date).pack(side="left", padx=(0, 20))
        self._create_input_field(dates_frame, "END DATE", self.sync_end_date).pack(side="left", padx=(0, 20))

        # Request Button
        btn_req = ModernButton(row2, "REQUEST RANGE SYNC", self._request_history_sync, 
                               config.ACCENT_GREEN, config.THEME_COLOR)
        btn_req.pack(side="left", pady=(18, 0))

    def _request_history_sync(self):
        tf = self.sync_timeframe.get()
        start = self.sync_start_date.get()
        end = self.sync_end_date.get()
        symbol = self.sync_symbol_var.get()
        logger.info(f"🛰️ Requesting data for {symbol} from {start} to {end} on {tf} from MT5...")
        events.emit(EventType.TRADE_COMMAND, {
            "action": "DATA_SYNC_RANGE",
            "symbol": symbol,
            "tf": tf,
            "start": start,
            "end": end
        })

    def _setup_header(self):
        header = tk.Frame(self.root, bg=config.HEADER_BG, height=65)
        header.pack(fill="x", side="top")
        header.pack_propagate(False)

        # 1. Logo
        logo_frame = tk.Frame(header, bg=config.HEADER_BG)
        logo_frame.pack(side="left", padx=25)
        tk.Label(logo_frame, text="MT5", font=(config.FONT_BOLD, 20, "bold"), 
                 fg=config.ACCENT_BLUE, bg=config.HEADER_BG).pack(side="left")
        tk.Label(logo_frame, text="AGENT", font=(config.FONT_MAIN, 20), 
                 fg=config.TEXT_PRIMARY, bg=config.HEADER_BG).pack(side="left", padx=8)

        # 2. Quick Lot Adjustment (Header)
        lot_frame = tk.Frame(header, bg=config.HEADER_BG)
        lot_frame.pack(side="left", padx=40)
        tk.Label(lot_frame, text="GLOBAL LOT:", font=(config.FONT_BOLD, 9), 
                 fg=config.TEXT_SECONDARY, bg=config.HEADER_BG).pack(side="left", padx=(0, 10))
        
        lot_entry = tk.Entry(lot_frame, textvariable=self.lot_var, width=6, font=(config.FONT_MONO, 11, "bold"), 
                             bg=config.INPUT_BG, fg=config.ACCENT_GREEN, bd=0, highlightthickness=1, 
                             highlightbackground=config.INPUT_BG, highlightcolor=config.ACCENT_BLUE, 
                             insertbackground="white", justify="center")
        lot_entry.pack(side="left", ipady=4)

        # 3. Connection Status
        self.status_pill = tk.Label(header, text="● OFFLINE", font=(config.FONT_MONO, 11), 
                                    bg=config.INPUT_BG, fg=config.ACCENT_RED, padx=15, pady=8)
        self.status_pill.pack(side="right", padx=25)

    def _setup_market_card(self, parent):
        card = Card(parent)
        card.pack(fill="x", pady=(0, 20))
        
        top = tk.Frame(card, bg=config.CARD_BG)
        top.pack(fill="x", pady=(0, 15))
        
        self.lbl_symbol = tk.Label(top, text="SYMBOL", font=(config.FONT_BOLD, 36, "bold"), 
                                   fg=config.TEXT_PRIMARY, bg=config.CARD_BG)
        self.lbl_symbol.pack(side="left")
        
        self.lbl_spread = tk.Label(top, text="SPREAD: --", font=(config.FONT_MONO, 12), 
                                   fg=config.ACCENT_PURPLE, bg=config.CARD_BG)
        self.lbl_spread.pack(side="right", pady=10)

        prices = tk.Frame(card, bg=config.CARD_BG)
        prices.pack(fill="x")
        prices.columnconfigure(0, weight=1)
        prices.columnconfigure(1, weight=1)
        
        self.lbl_bid = self._create_price_box(prices, "BID", config.ACCENT_RED, 0)
        self.lbl_ask = self._create_price_box(prices, "ASK", config.ACCENT_GREEN, 1)

        # AI Insights Row (REFACTORED)
        ai_frame = tk.Frame(card, bg=config.CARD_BG)
        ai_frame.pack(fill="x", pady=(20, 0))

        # Row 1: Confidence | Trend | Target
        row1 = tk.Frame(ai_frame, bg=config.CARD_BG)
        row1.pack(fill="x")
        
        # Left side: Confidence
        conf_box = tk.Frame(row1, bg=config.CARD_BG)
        conf_box.pack(side="left", fill="both", expand=True)
        tk.Label(conf_box, text="AI CONFIDENCE", font=(config.FONT_MAIN, 9, "bold"), 
                 fg=config.TEXT_MUTED, bg=config.CARD_BG).pack()
        self.lbl_ai_conf = tk.Label(conf_box, text="0.0%", font=(config.FONT_MONO, 20, "bold"), 
                                    fg=config.TEXT_SECONDARY, bg=config.CARD_BG)
        self.lbl_ai_conf.pack()

        # Center: Direction Signal
        self.lbl_ai_dir = tk.Label(row1, text="WAIT", font=(config.FONT_BOLD, 14, "bold"), 
                                   fg=config.TEXT_MUTED, bg=config.CARD_BG)
        self.lbl_ai_dir.pack(side="left", padx=10)

        # Right side: Main Prediction
        pred_box = tk.Frame(row1, bg=config.CARD_BG)
        pred_box.pack(side="left", fill="both", expand=True)
        tk.Label(pred_box, text="AI TARGET (TP3)", font=(config.FONT_MAIN, 9, "bold"), 
                 fg=config.TEXT_MUTED, bg=config.CARD_BG).pack()
        self.lbl_ai_pred = tk.Label(pred_box, text="---", font=(config.FONT_MONO, 20, "bold"), 
                                    fg=config.ACCENT_BLUE, bg=config.CARD_BG)
        self.lbl_ai_pred.pack()

        # Row 2: TP Breakdown
        row2 = tk.Frame(ai_frame, bg=config.CARD_BG)
        row2.pack(fill="x", pady=(15, 0))
        
        self.lbl_tp1 = self._create_tp_box(row2, "TP 1 (Safe)", config.TEXT_SECONDARY)
        self.lbl_tp2 = self._create_tp_box(row2, "TP 2 (Mid)", config.TEXT_PRIMARY)
        self.lbl_tp3 = self._create_tp_box(row2, "TP 3 (Max)", config.ACCENT_PURPLE)

        # Indicators Row
        ind_frame = tk.Frame(card, bg=config.CARD_BG)
        ind_frame.pack(fill="x", pady=(15, 0))
        
        self.lbl_rsi = tk.Label(ind_frame, text="RSI: --", font=(config.FONT_MONO, 11), 
                                fg=config.TEXT_MUTED, bg=config.CARD_BG)
        self.lbl_rsi.pack(side="left", padx=(0, 25))
        
        self.lbl_sma = tk.Label(ind_frame, text="SMA10: --", font=(config.FONT_MONO, 11), 
                                fg=config.TEXT_MUTED, bg=config.CARD_BG)
        self.lbl_sma.pack(side="left")

    def _create_price_box(self, parent, label, color, col):
        box = tk.Frame(parent, bg=config.CARD_BG)
        box.grid(row=0, column=col, sticky="nsew")
        tk.Label(box, text=label, font=(config.FONT_MAIN, 10, "bold"), 
                 fg=config.TEXT_MUTED, bg=config.CARD_BG).pack()
        lbl = tk.Label(box, text="0.000", font=(config.FONT_MONO, 44, "bold"), 
                       fg=color, bg=config.CARD_BG)
        lbl.pack()
        return lbl

    def _create_tp_box(self, parent, label, color):
        box = tk.Frame(parent, bg=config.CARD_BG)
        box.pack(side="left", fill="x", expand=True)
        tk.Label(box, text=label, font=(config.FONT_MAIN, 8, "bold"), 
                 fg=config.TEXT_MUTED, bg=config.CARD_BG).pack()
        lbl = tk.Label(box, text="---", font=(config.FONT_MONO, 12, "bold"), 
                       fg=color, bg=config.CARD_BG)
        lbl.pack()
        return lbl

    def _setup_trade_card(self, parent):
        card = Card(parent)
        card.pack(fill="x")
        
        tk.Label(card, text="EXECUTION", font=(config.FONT_MAIN, 11, "bold"), 
                 fg=config.TEXT_MUTED, bg=config.CARD_BG).pack(anchor="w", pady=(0, 15))

        inputs = tk.Frame(card, bg=config.CARD_BG)
        inputs.pack(fill="x", pady=(0, 25))
        
        self._create_combo_field(inputs, "SYMBOL", self.default_symbol_var, config.SYMBOL_OPTIONS).pack(side="left", padx=(0, 15))
        self._create_input_field(inputs, "VOLUME", self.lot_var).pack(side="left", padx=(0, 15))
        
        # Stop Loss Spinbox
        sl_frame = self._create_spin_field(inputs, "SL:", self.sl_var)
        sl_frame.pack(side="left", padx=(0, 15))
        
        # Take Profit Spinbox
        tp_frame = self._create_spin_field(inputs, "TP:", self.tp_var)
        tp_frame.pack(side="left")

        btns = tk.Frame(card, bg=config.CARD_BG)
        btns.pack(fill="x", pady=(0, 20))
        ActionButton(btns, "SELL", lambda: self._on_trade_btn("SELL"), config.ACCENT_RED).pack(side="left", fill="x", expand=True, padx=(0, 10))
        ActionButton(btns, "BUY", lambda: self._on_trade_btn("BUY"), config.ACCENT_GREEN).pack(side="left", fill="x", expand=True, padx=(10, 0))

        utils = tk.Frame(card, bg=config.CARD_BG)
        utils.pack(fill="x")
        
        # Split row for Win/Loss
        row_split = tk.Frame(utils, bg=config.CARD_BG)
        row_split.pack(fill="x", pady=(0, 10))
        
        ModernButton(row_split, "CLOSE WINNERS", lambda: self._on_trade_btn("CLOSE_WIN"), 
                     config.INPUT_BG, config.ACCENT_GREEN).pack(side="left", fill="x", expand=True, padx=(0, 5))
                     
        ModernButton(row_split, "CLOSE LOSERS", lambda: self._on_trade_btn("CLOSE_LOSS"), 
                     config.INPUT_BG, config.ACCENT_RED).pack(side="left", fill="x", expand=True, padx=(5, 0))

        ModernButton(utils, "CLOSE ALL POSITIONS", lambda: self._on_trade_btn("CLOSE_ALL"), 
                     config.INPUT_BG, config.TEXT_PRIMARY).pack(fill="x")

    def _create_input_field(self, parent, label, var):
        frame = tk.Frame(parent, bg=config.CARD_BG)
        tk.Label(frame, text=label, font=(config.FONT_MAIN, 9, "bold"), 
                 fg=config.TEXT_MUTED, bg=config.CARD_BG).pack(anchor="w", pady=(0, 5))
        ent = tk.Entry(frame, textvariable=var, width=10, font=(config.FONT_MONO, 13), 
                       bg=config.INPUT_BG, fg=config.TEXT_PRIMARY, bd=0, highlightthickness=1, 
                       highlightbackground=config.INPUT_BG, highlightcolor=config.ACCENT_BLUE, 
                       insertbackground="white")
        ent.pack(ipady=8, ipadx=5)
        
        # Auto-generate price on click
        if "STOP LOSS" in label or "TAKE PROFIT" in label:
            ent.bind("<FocusIn>", lambda e: self._populate_current_price(var))
            
        return frame

    def _create_combo_field(self, parent, label, var, options):
        frame = tk.Frame(parent, bg=config.CARD_BG)
        tk.Label(frame, text=label, font=(config.FONT_MAIN, 9, "bold"), 
                 fg=config.TEXT_MUTED, bg=config.CARD_BG).pack(anchor="w", pady=(0, 5))
        
        combo = ttk.Combobox(frame, textvariable=var, values=options, width=12, 
                             font=(config.FONT_MONO, 13))
        combo.pack(ipady=7)
        self.symbol_combos.append(combo)
        return frame

    def _create_spin_field(self, parent, label, var):
        frame = tk.Frame(parent, bg=config.CARD_BG)
        
        # Label to the left of the Spinbox
        tk.Label(frame, text=label, font=(config.FONT_MAIN, 10), 
                 fg=config.TEXT_PRIMARY, bg=config.CARD_BG).pack(side="left", padx=(0, 10))
        
        # Spinbox
        # We use a large range and small increment to mimic price movements
        spin = tk.Spinbox(frame, textvariable=var, from_=0, to=1000000, increment=0.01,
                          width=12, font=(config.FONT_MONO, 13), 
                          bg=config.INPUT_BG, fg=config.TEXT_PRIMARY, 
                          buttonbackground=config.CARD_BG, bd=0, highlightthickness=1,
                          highlightbackground=config.INPUT_BG, highlightcolor=config.ACCENT_BLUE,
                          insertbackground="white")
        spin.pack(side="left", ipady=6, ipadx=5)
        
        # Auto-populate current price on click/focus
        spin.bind("<FocusIn>", lambda e: self._populate_current_price(var))
        spin.bind("<Button-1>", lambda e: self._populate_current_price(var))
        
        return frame

    def _populate_current_price(self, var):
        """Helper to fill the field with current live price if it's currently 0 or empty."""
        from ..state import state
        try:
            current_val = float(var.get() or 0)
            if current_val == 0:
                # Use Ask for SL/TP typically, or Bid, depending on trade type. 
                # For simplicity, use Mid or Ask.
                price = state.market.ask if state.market.ask > 0 else state.market.bid
                if price > 0:
                    # Smart Auto-offset ($2.00 for Gold)
                    offset = 2.0 if "XAU" in state.market.symbol else (price * 0.001)
                    
                    if var == self.sl_var:
                        # Default SL to be "behind" the current price
                        var.set(f"{price - offset:.5f}")
                    elif var == self.tp_var:
                        # Default TP to be "ahead" of the current price
                        var.set(f"{price + offset:.5f}")
                    else:
                        var.set(f"{price:.5f}")
        except ValueError:
            pass

    def _setup_account_card(self, parent):
        card = Card(parent)
        card.pack(fill="x", pady=(0, 20))
        tk.Label(card, text="ACCOUNT SUMMARY", font=(config.FONT_MAIN, 11, "bold"), 
                 fg=config.TEXT_MUTED, bg=config.CARD_BG).pack(anchor="w", pady=(0, 15))

        self.lbl_account_name = self._create_metric_row(card, "Account Name")
        self.lbl_balance = self._create_metric_row(card, "Balance")
        self.lbl_equity = self._create_metric_row(card, "Equity")
        self.lbl_profit = self._create_metric_row(card, "Float P/L")
        self.lbl_pos_count = self._create_metric_row(card, "Active Trades")

        self.cb_auto = tk.Checkbutton(card, text="ENABLE AUTO-TRADING", variable=self.auto_trade_var,
                                      bg=config.CARD_BG, fg=config.ACCENT_BLUE, selectcolor=config.CARD_BG,
                                      activebackground=config.CARD_BG, font=(config.FONT_BOLD, 11, "bold"))
        self.cb_auto.pack(anchor="w", pady=(20, 0))

    def _create_metric_row(self, parent, label):
        row = tk.Frame(parent, bg=config.CARD_BG, pady=6)
        row.pack(fill="x")
        tk.Label(row, text=label, font=(config.FONT_MAIN, 11), fg=config.TEXT_SECONDARY, bg=config.CARD_BG).pack(side="left")
        lbl = tk.Label(row, text="$0.00", font=(config.FONT_MONO, 12, "bold"), fg=config.TEXT_PRIMARY, bg=config.CARD_BG)
        lbl.pack(side="right")
        return lbl

    def _setup_log_card(self, parent):
        card = Card(parent)
        card.pack(fill="both", expand=True)
        tk.Label(card, text="LOGS", font=(config.FONT_MAIN, 11, "bold"), 
                 fg=config.TEXT_MUTED, bg=config.CARD_BG).pack(anchor="w", pady=(0, 10))
        
        self.log_text = tk.Text(card, bg=config.THEME_COLOR, fg=config.TEXT_SECONDARY,
                                font=(config.FONT_MONO, 10), bd=0, highlightthickness=0, 
                                state="disabled", padx=12, pady=12)
        self.log_text.pack(fill="both", expand=True)

    # --- Event Handlers (Thread Safe) ---

    def _on_price_update(self, market: MarketData):
        self.root.after(0, lambda: self._update_price_ui(market))

    def _update_price_ui(self, market: MarketData):
        if not self.lbl_bid.winfo_exists(): return
        self.lbl_symbol.configure(text=market.symbol)
        self.lbl_bid.configure(text=f"{market.bid:.3f}")
        self.lbl_ask.configure(text=f"{market.ask:.3f}")
        self.lbl_spread.configure(text=f"SPREAD: {market.spread}")
        
        # AI Data Update
        if hasattr(self, 'lbl_ai_pred'):
            # Prediction
            self.lbl_ai_pred.configure(text=f"{market.prediction:.2f}")
            
            # Confidence
            self.lbl_ai_conf.configure(text=f"{market.confidence:.1f}%")
            # Highlight confidence
            conf_color = config.ACCENT_GREEN if market.confidence >= 100 else config.TEXT_SECONDARY
            self.lbl_ai_conf.configure(fg=conf_color)
            
            # Smart TP Calculation Logic
            curr = market.ask 
            targ = market.prediction
            
            if targ != 0 and curr != 0:
                delta = targ - curr
                
                # Determine Direction
                if delta > 0:
                    direction = "BULLISH"
                    color = config.ACCENT_GREEN
                else:
                    direction = "BEARISH"
                    color = config.ACCENT_RED
                
                self.lbl_ai_dir.configure(text=direction, fg=color)
                self.lbl_ai_pred.configure(fg=color)

                # Calculate TP Levels (33%, 66%, 100%)
                tp1 = curr + (delta * 0.33)
                tp2 = curr + (delta * 0.66)
                tp3 = targ # Main Target
                
                self.lbl_tp1.configure(text=f"{tp1:.2f}", fg=color)
                self.lbl_tp2.configure(text=f"{tp2:.2f}", fg=color)
                self.lbl_tp3.configure(text=f"{tp3:.2f}", fg=color)
            
            # Indicators Update
            if hasattr(self, 'lbl_rsi'):
                self.lbl_rsi.configure(text=f"RSI: {market.rsi:.2f}")
                self.lbl_sma.configure(text=f"SMA10: {market.sma10:.2f}")

    def _on_account_update(self, account: AccountData):
        self.root.after(0, lambda: self._update_account_ui(account))

    def _update_account_ui(self, acc: AccountData):
        if not self.lbl_balance.winfo_exists(): return
        self.lbl_account_name.configure(text=acc.name)
        self.lbl_balance.configure(text=f"${acc.balance:,.2f}")
        self.lbl_equity.configure(text=f"${acc.equity:,.2f}")
        color = config.ACCENT_GREEN if acc.profit >= 0 else config.ACCENT_RED
        self.lbl_profit.configure(text=f"{acc.profit:+,.2f}", fg=color)
        self.lbl_pos_count.configure(text=str(acc.position_count))

    def _on_log_message(self, data: dict):
        self.root.after(0, lambda: self._insert_log(data))

    def _insert_log(self, data: dict):
        if not self.log_text.winfo_exists(): return
        ts = time.strftime("%H:%M:%S")
        msg = data["msg"]
        ltype = data["type"]
        
        colors = {"info": config.ACCENT_BLUE, "success": config.ACCENT_GREEN, 
                  "warning": config.ACCENT_WARNING, "error": config.ACCENT_RED}
        
        self.log_text.configure(state="normal")
        self.log_text.insert("1.0", f"{ts} | {msg}\n")
        self.log_text.tag_add("timestamp", "1.0", f"1.{len(ts)+3}")
        self.log_text.tag_config("timestamp", foreground=colors.get(ltype, config.TEXT_SECONDARY))
        self.log_text.configure(state="disabled")

    def _on_connection_change(self, connected: bool):
        self.root.after(0, lambda: self._update_conn_ui(connected))

    def _update_conn_ui(self, connected: bool):
        color = config.ACCENT_GREEN if connected else config.ACCENT_RED
        text = "● ONLINE" if connected else "● OFFLINE"
        self.status_pill.configure(fg=color, text=text)

    def _on_symbols_update(self, syms: list):
        self.root.after(0, lambda: self._update_symbol_lists(syms))

    def _update_symbol_lists(self, syms: list):
        for combo in self.symbol_combos:
            if combo.winfo_exists():
                combo['values'] = syms

    def _on_trade_btn(self, action):
        events.emit(EventType.TRADE_COMMAND, {"action": action})

    def _sync_all_sl_tp(self):
        """Sends modify commands for all currently open positions."""
        from ..state import state
        if not state.positions:
            logger.warning("No open positions to sync.")
            return

        sl = self.sl_var.get()
        tp = self.tp_var.get()
        
        logger.info(f"🔄 Syncing SL:{sl} TP:{tp} to {len(state.positions)} positions...")
        for pos in state.positions:
            events.emit(EventType.TRADE_COMMAND, {
                "action": "MODIFY_TICKET",
                "ticket": pos.ticket,
                "sl": sl,
                "tp": tp
            })