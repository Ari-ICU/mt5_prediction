import tkinter as tk
from tkinter import ttk, font
import threading
import time
from datetime import datetime
from . import config
from .state import state

# --- Custom UI Components ---

class Card(tk.Frame):
    """A container with a background color distinct from the main window."""
    def __init__(self, parent, pad=20, **kwargs):
        super().__init__(parent, bg=config.CARD_BG, padx=pad, pady=pad, **kwargs)

class ModernButton(tk.Label):
    """A generic flat button with hover effects."""
    def __init__(self, parent, text, command, bg, fg, width=None, font_spec=None):
        if font_spec is None:
            font_spec = (config.FONT_BOLD, 11, "bold")
            
        super().__init__(parent, text=text, bg=bg, fg=fg, 
                         font=font_spec, cursor="hand2")
        
        self.default_bg = bg
        self.hover_bg = config.HOVER_BG if bg == config.INPUT_BG else self._adjust_brightness(bg, 1.2)
        self.command = command
        
        # Styling
        self.configure(padx=15, pady=10)
        if width:
            self.configure(width=width)
            
        # Events
        self.bind("<Enter>", self.on_enter)
        self.bind("<Leave>", self.on_leave)
        self.bind("<Button-1>", self.on_click)
        
    def _adjust_brightness(self, hex_color, factor):
        return hex_color 

    def on_enter(self, e):
        self.configure(bg=self.hover_bg)
        
    def on_leave(self, e):
        self.configure(bg=self.default_bg)
        
    def on_click(self, e):
        if self.command:
            self.command()

class ActionButton(ModernButton):
    """Specialized button for BUY/SELL actions."""
    def __init__(self, parent, text, command, bg):
        super().__init__(parent, text=text, command=command, bg=bg, 
                         fg=config.TEXT_ON_ACCENT, font_spec=(config.FONT_BOLD, 16, "bold"))
        self.configure(pady=15)

# --- Main Controller ---

class MT5ControllerGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("MT5 PRO TERMINAL")
        self.root.geometry(f"{config.WINDOW_WIDTH}x{config.WINDOW_HEIGHT}")
        self.root.configure(bg=config.THEME_COLOR)
        
        # Data Bindings
        self.symbol_var = tk.StringVar(value=config.DEFAULT_SYMBOL)
        self.lot_var = tk.StringVar(value=config.DEFAULT_LOT_SIZE)
        self.sl_var = tk.StringVar(value=config.DEFAULT_SL)
        self.tp_var = tk.StringVar(value=config.DEFAULT_TP)
        self.auto_trade_var = tk.BooleanVar(value=False)
        
        # Sync inputs with global state
        self.lot_var.trace_add("write", self._sync_settings)
        self.sl_var.trace_add("write", self._sync_settings)
        self.tp_var.trace_add("write", self._sync_settings)

        # Build UI
        self._setup_layout()
        
        # Bind State Callbacks
        state.log_callback = self.log_to_gui
        state.connection_callback = self.update_connection_status
        state.price_update_callback = self.update_price_display
        state.account_update_callback = self.update_account_display
        
        # Start Watchdogs
        threading.Thread(target=self._connection_watchdog, daemon=True).start()
        
        # Initial State Sync
        self._sync_settings()

    def _sync_settings(self, *args):
        state.update_trade_settings(self.lot_var.get(), self.sl_var.get(), self.tp_var.get())

    def _setup_layout(self):
        # 1. Header
        self._setup_header()
        
        # 2. Main Content Grid
        content = tk.Frame(self.root, bg=config.THEME_COLOR)
        content.pack(fill="both", expand=True, padx=20, pady=20)
        
        # Grid Configuration
        content.columnconfigure(0, weight=3) # Market & Trade (Left)
        content.columnconfigure(1, weight=2) # Account & Logs (Right)
        content.rowconfigure(0, weight=1)

        # Left Column
        left_panel = tk.Frame(content, bg=config.THEME_COLOR)
        left_panel.grid(row=0, column=0, sticky="nsew", padx=(0, 20))
        
        self._setup_market_monitor(left_panel)
        self._setup_trade_controls(left_panel)
        
        # Right Column
        right_panel = tk.Frame(content, bg=config.THEME_COLOR)
        right_panel.grid(row=0, column=1, sticky="nsew")
        
        self._setup_account_summary(right_panel)
        self._setup_log_console(right_panel)

    def _setup_header(self):
        header = tk.Frame(self.root, bg=config.HEADER_BG, height=60)
        header.pack(fill="x", side="top")
        header.pack_propagate(False)

        # Logo
        logo_box = tk.Frame(header, bg=config.HEADER_BG)
        logo_box.pack(side="left", padx=20)
        tk.Label(logo_box, text="MT5", font=(config.FONT_BOLD, 18, "bold"), 
                 fg=config.ACCENT_BLUE, bg=config.HEADER_BG).pack(side="left")
        tk.Label(logo_box, text="PRO", font=(config.FONT_MAIN, 18), 
                 fg=config.TEXT_PRIMARY, bg=config.HEADER_BG).pack(side="left", padx=5)

        # Connection Status Pill
        self.status_pill = tk.Label(header, text="● CONNECTING...", 
                                    font=(config.FONT_MONO, 10), 
                                    bg=config.INPUT_BG, fg=config.TEXT_SECONDARY, 
                                    padx=12, pady=6)
        self.status_pill.pack(side="right", padx=20, pady=12)

    def _setup_market_monitor(self, parent):
        # --- Market Data Card ---
        card = Card(parent)
        card.pack(fill="x", pady=(0, 20))
        
        # Symbol Header
        h_frame = tk.Frame(card, bg=config.CARD_BG)
        h_frame.pack(fill="x", pady=(0, 15))
        self.lbl_symbol = tk.Label(h_frame, text=config.DEFAULT_SYMBOL, 
                                   font=(config.FONT_BOLD, 32, "bold"), 
                                   fg=config.TEXT_PRIMARY, bg=config.CARD_BG)
        self.lbl_symbol.pack(side="left")
        
        self.lbl_spread = tk.Label(h_frame, text="SPREAD: --", 
                                   font=(config.FONT_MONO, 12), 
                                   fg=config.ACCENT_PURPLE, bg=config.CARD_BG)
        self.lbl_spread.pack(side="right", pady=10)

        # Prices (Bid/Ask)
        prices_frame = tk.Frame(card, bg=config.CARD_BG)
        prices_frame.pack(fill="x")
        prices_frame.columnconfigure(0, weight=1)
        prices_frame.columnconfigure(1, weight=1)
        
        # Bid
        bid_box = tk.Frame(prices_frame, bg=config.CARD_BG)
        bid_box.grid(row=0, column=0)
        tk.Label(bid_box, text="BID", font=(config.FONT_MAIN, 10, "bold"), 
                 fg=config.TEXT_MUTED, bg=config.CARD_BG).pack()
        self.lbl_bid = tk.Label(bid_box, text="0.0000", 
                                font=(config.FONT_MONO, 42, "bold"), 
                                fg=config.ACCENT_RED, bg=config.CARD_BG)
        self.lbl_bid.pack()

        # Ask
        ask_box = tk.Frame(prices_frame, bg=config.CARD_BG)
        ask_box.grid(row=0, column=1)
        tk.Label(ask_box, text="ASK", font=(config.FONT_MAIN, 10, "bold"), 
                 fg=config.TEXT_MUTED, bg=config.CARD_BG).pack()
        self.lbl_ask = tk.Label(ask_box, text="0.0000", 
                                font=(config.FONT_MONO, 42, "bold"), 
                                fg=config.ACCENT_GREEN, bg=config.CARD_BG)
        self.lbl_ask.pack()

    def _setup_trade_controls(self, parent):
        # --- Trade Execution Card ---
        card = Card(parent)
        card.pack(fill="x")
        
        tk.Label(card, text="QUICK TRADE", font=(config.FONT_MAIN, 10, "bold"), 
                 fg=config.TEXT_MUTED, bg=config.CARD_BG).pack(anchor="w", pady=(0, 15))

        # Inputs Row
        inputs = tk.Frame(card, bg=config.CARD_BG)
        inputs.pack(fill="x", pady=(0, 20))
        
        self._create_input(inputs, "VOLUME", self.lot_var).pack(side="left", padx=(0, 15))
        self._create_input(inputs, "STOP LOSS", self.sl_var).pack(side="left", padx=(0, 15))
        self._create_input(inputs, "TAKE PROFIT", self.tp_var).pack(side="left")

        # Big Buttons
        btns = tk.Frame(card, bg=config.CARD_BG)
        btns.pack(fill="x", pady=(0, 15))
        
        # Sell
        sell_box = tk.Frame(btns, bg=config.ACCENT_RED, padx=1, pady=1) # Border trick
        sell_box.pack(side="left", fill="x", expand=True, padx=(0, 10))
        ActionButton(sell_box, "SELL", lambda: self.manual_command("SELL"), config.ACCENT_RED).pack(fill="both")

        # Buy
        buy_box = tk.Frame(btns, bg=config.ACCENT_GREEN, padx=1, pady=1)
        buy_box.pack(side="left", fill="x", expand=True, padx=(10, 0))
        ActionButton(buy_box, "BUY", lambda: self.manual_command("BUY"), config.ACCENT_GREEN).pack(fill="both")

        # Utility Buttons
        utils = tk.Frame(card, bg=config.CARD_BG)
        utils.pack(fill="x", pady=(5, 0))
        
        # Split Row for Close Win / Close Loss
        row_split = tk.Frame(utils, bg=config.CARD_BG)
        row_split.pack(fill="x", pady=(0, 8))

        ModernButton(row_split, "CLOSE WINNERS", lambda: self.manual_command("CLOSE_WIN"), 
                     config.INPUT_BG, config.ACCENT_GREEN).pack(side="left", fill="x", expand=True, padx=(0, 5))
                     
        ModernButton(row_split, "CLOSE LOSERS", lambda: self.manual_command("CLOSE_LOSS"), 
                     config.INPUT_BG, config.ACCENT_RED).pack(side="left", fill="x", expand=True, padx=(5, 0))

        # Close All Full Width
        ModernButton(utils, "CLOSE ALL POSITIONS", lambda: self.manual_command("CLOSE_ALL"), 
                     config.INPUT_BG, config.TEXT_PRIMARY).pack(fill="x")

    def _setup_account_summary(self, parent):
        card = Card(parent)
        card.pack(fill="x", pady=(0, 20))
        
        tk.Label(card, text="ACCOUNT", font=(config.FONT_MAIN, 10, "bold"), 
                 fg=config.TEXT_MUTED, bg=config.CARD_BG).pack(anchor="w", pady=(0, 15))

        self.lbl_balance = self._create_metric(card, "BALANCE")
        self.lbl_equity = self._create_metric(card, "EQUITY")
        self.lbl_margin = self._create_metric(card, "MARGIN")
        
        # Floating P/L Highlight
        pl_box = tk.Frame(card, bg=config.INPUT_BG, padx=15, pady=15)
        pl_box.pack(fill="x", pady=(15, 0))
        tk.Label(pl_box, text="PROFIT / LOSS", font=(config.FONT_MAIN, 9, "bold"), 
                 fg=config.TEXT_MUTED, bg=config.INPUT_BG).pack(anchor="w")
        self.lbl_profit = tk.Label(pl_box, text="+0.00", 
                                   font=(config.FONT_MONO, 24, "bold"), 
                                   fg=config.ACCENT_GREEN, bg=config.INPUT_BG)
        self.lbl_profit.pack(anchor="w")

        # Auto Switch
        switch_frame = tk.Frame(card, bg=config.CARD_BG, pady=5)
        switch_frame.pack(fill="x", pady=(20, 0))
        
        # Custom Checkbutton style (Standard looks bad on dark theme)
        self.cb_auto = tk.Checkbutton(switch_frame, text="ENABLE AUTO-TRADING", 
                                      variable=self.auto_trade_var,
                                      bg=config.CARD_BG, fg=config.ACCENT_BLUE,
                                      activebackground=config.CARD_BG,
                                      activeforeground=config.ACCENT_BLUE,
                                      selectcolor=config.CARD_BG,
                                      font=(config.FONT_BOLD, 10, "bold"),
                                      command=self.toggle_auto_trade)
        self.cb_auto.pack(side="left")

    def _setup_log_console(self, parent):
        card = Card(parent)
        card.pack(fill="both", expand=True)
        
        tk.Label(card, text="SYSTEM LOGS", font=(config.FONT_MAIN, 10, "bold"), 
                 fg=config.TEXT_MUTED, bg=config.CARD_BG).pack(anchor="w", pady=(0, 10))
                 
        self.log_text = tk.Text(card, bg=config.THEME_COLOR, fg=config.TEXT_SECONDARY,
                                font=(config.FONT_MONO, 9), bd=0, 
                                highlightthickness=0, state="disabled", padx=10, pady=10)
        self.log_text.pack(fill="both", expand=True)

    # --- UI Helpers ---

    def _create_input(self, parent, label, var):
        frame = tk.Frame(parent, bg=config.CARD_BG)
        tk.Label(frame, text=label, font=(config.FONT_MAIN, 8, "bold"), 
                 fg=config.TEXT_MUTED, bg=config.CARD_BG).pack(anchor="w", pady=(0, 4))
        entry = tk.Entry(frame, textvariable=var, width=8, 
                         font=(config.FONT_MONO, 12), 
                         bg=config.INPUT_BG, fg=config.TEXT_PRIMARY, 
                         insertbackground="white", bd=0, 
                         highlightthickness=1, highlightcolor=config.ACCENT_BLUE,
                         highlightbackground=config.INPUT_BG)
        entry.pack(ipady=6, ipadx=4)
        return frame

    def _create_metric(self, parent, label):
        frame = tk.Frame(parent, bg=config.CARD_BG)
        frame.pack(fill="x", pady=4)
        tk.Label(frame, text=label, font=(config.FONT_MAIN, 10), 
                 fg=config.TEXT_SECONDARY, bg=config.CARD_BG).pack(side="left")
        val = tk.Label(frame, text="0.00", font=(config.FONT_MONO, 11), 
                       fg=config.TEXT_PRIMARY, bg=config.CARD_BG)
        val.pack(side="right")
        return val

    # --- Logic & Updates ---

    def manual_command(self, action):
        if not state.is_connected:
            state.log("Command ignored: Not connected", "error")
            return
        state.queue_command(action, self.symbol_var.get().upper())

    def toggle_auto_trade(self):
        enabled = self.auto_trade_var.get()
        state.auto_trade_enabled = enabled
        msg = "Auto-Trading ENABLED" if enabled else "Auto-Trading DISABLED"
        state.log(msg, "success" if enabled else "warning")

    def _connection_watchdog(self):
        while True:
            time.sleep(1)
            # If no heartbeat for >5s, mark offline
            if state.is_connected and (time.time() - state.last_poll_time > 5):
                state.update_connection(False)

    # --- Thread-Safe GUI Updates ---

    def log_to_gui(self, msg, log_type):
        if self.root: self.root.after(0, lambda: self._insert_log(msg, log_type))

    def _insert_log(self, msg, log_type):
        if not self.log_text.winfo_exists(): return
        
        t = datetime.now().strftime("%H:%M:%S")
        colors = {
            "info": config.ACCENT_BLUE,
            "success": config.ACCENT_GREEN,
            "warning": config.ACCENT_WARNING,
            "error": config.ACCENT_RED
        }
        
        self.log_text.configure(state="normal")
        self.log_text.insert("1.0", f"{t} | {msg}\n")
        
        # Colorize the timestamp/prefix
        self.log_text.tag_add("colored", "1.0", "1.8")
        self.log_text.tag_config("colored", foreground=colors.get(log_type, config.TEXT_SECONDARY))
        
        self.log_text.configure(state="disabled")

    def update_connection_status(self, connected):
        if self.root: self.root.after(0, lambda: self._update_conn_ui(connected))

    def _update_conn_ui(self, connected):
        if not self.status_pill.winfo_exists(): return
        color = config.ACCENT_GREEN if connected else config.ACCENT_RED
        text = "● ONLINE" if connected else "● OFFLINE"
        self.status_pill.configure(fg=color, text=text)

    def update_price_display(self, symbol, bid, ask):
        if self.root: self.root.after(0, lambda: self._update_price_ui(symbol, bid, ask))

    def _update_price_ui(self, symbol, bid, ask):
        if not self.lbl_bid.winfo_exists(): return
        self.lbl_symbol.configure(text=symbol)
        self.lbl_bid.configure(text=f"{bid:.2f}")
        self.lbl_ask.configure(text=f"{ask:.2f}")
        
        spread = int((ask - bid) * 100) # Basic spread calc
        self.lbl_spread.configure(text=f"SPREAD: {spread}")

    def update_account_display(self, name, balance, equity, margin, free, profit):
        if self.root: self.root.after(0, lambda: self._update_acct_ui(balance, equity, margin, profit))

    def _update_acct_ui(self, bal, eq, marg, prof):
        if not self.lbl_balance.winfo_exists(): return
        self.lbl_balance.configure(text=f"${bal:,.2f}")
        self.lbl_equity.configure(text=f"${eq:,.2f}")
        self.lbl_margin.configure(text=f"${marg:,.2f}")
        
        pc = config.ACCENT_GREEN if prof >= 0 else config.ACCENT_RED
        self.lbl_profit.configure(text=f"{prof:+.2f}", fg=pc)