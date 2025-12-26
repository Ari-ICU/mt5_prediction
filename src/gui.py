import tkinter as tk
from tkinter import ttk
import threading
import time
from datetime import datetime
from . import config
from .state import state

class ModernButton(tk.Label):
    """Custom Button using Label for better styling control"""
    def __init__(self, parent, text, command, bg, fg, width=None, font_size=11):
        super().__init__(parent, text=text, bg=bg, fg=fg, 
                         font=(config.FONT_BOLD, font_size, "bold"), cursor="hand2")
        self.default_bg = bg
        self.command = command
        self.padding_y = 10
        self.padding_x = 20
        self.configure(padx=self.padding_x, pady=self.padding_y)
        if width:
            self.configure(width=width)
            
        self.bind("<Enter>", self.on_hover)
        self.bind("<Leave>", self.on_leave)
        self.bind("<Button-1>", self.on_click)
        
    def on_hover(self, e):
        # Brighten color slightly or simulated hover
        self.configure(bg="#333333" if self.default_bg == config.INPUT_BG else self.default_bg) # Simple hover for neutral
        
    def on_leave(self, e):
        self.configure(bg=self.default_bg)
        
    def on_click(self, e):
        if self.command:
            self.command()

class MT5ControllerGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("MT5 PRO TERMINAL")
        self.root.geometry(f"{config.WINDOW_WIDTH}x{config.WINDOW_HEIGHT}")
        self.root.configure(bg=config.THEME_COLOR)
        
        # Check fonts (fallback)
        self.main_font = (config.FONT_MAIN, 11)
        self.header_font = (config.FONT_BOLD, 20, "bold")
        
        # Variables
        self.symbol_var = tk.StringVar(value=config.DEFAULT_SYMBOL)
        self.lot_var = tk.StringVar(value=config.DEFAULT_LOT_SIZE)
        self.auto_trade_var = tk.BooleanVar(value=False)
        self.buy_threshold_var = tk.StringVar(value=str(config.BUY_THRESHOLD_DEFAULT))
        self.sell_threshold_var = tk.StringVar(value=str(config.SELL_THRESHOLD_DEFAULT))
        self.sl_var = tk.StringVar(value=config.DEFAULT_SL)
        self.tp_var = tk.StringVar(value=config.DEFAULT_TP)
        self.max_spread_var = tk.StringVar(value=str(config.MAX_SPREAD_DEFAULT))

        self._setup_ui()
        
        # Callbacks
        state.log_callback = self.log_to_gui
        state.connection_callback = self.update_connection_status
        state.market_status_callback = self.update_market_status
        state.price_update_callback = self.update_price_display
        state.account_update_callback = self.update_account_display
        
        # Watchdog
        threading.Thread(target=self._connection_watchdog, daemon=True).start()

    def _setup_ui(self):
        # MAIN LAYOUT: Header (Top) + Content (Bottom)
        
        main_container = tk.Frame(self.root, bg=config.THEME_COLOR)
        main_container.pack(fill="both", expand=True)

        # 1. Header Navigation
        self._setup_header(main_container)

        # 2. Content Area
        self.content_area = tk.Frame(main_container, bg=config.THEME_COLOR)
        self.content_area.pack(side="top", fill="both", expand=True, padx=20, pady=20)
        
        # 3. Default View
        self.current_view_frame = None
        self.switch_view("dashboard")

    def _setup_header(self, parent):
        header = tk.Frame(parent, bg=config.HEADER_BG, height=60)
        header.pack(fill="x", side="top")
        header.pack_propagate(False)

        # Logo / Title
        logo_frame = tk.Frame(header, bg=config.HEADER_BG)
        logo_frame.pack(side="left", padx=20)
        tk.Label(logo_frame, text="MT5", font=(config.FONT_BOLD, 18, "bold"), fg=config.ACCENT_BLUE, bg=config.HEADER_BG).pack(side="left")
        tk.Label(logo_frame, text="PRO", font=(config.FONT_MAIN, 18), fg=config.TEXT_PRIMARY, bg=config.HEADER_BG).pack(side="left", padx=5)

        # Navigation Tabs
        nav_frame = tk.Frame(header, bg=config.HEADER_BG)
        nav_frame.pack(side="left", padx=40, fill="y")

        def create_nav_tab(text, view):
            btn = tk.Label(nav_frame, text=text, font=(config.FONT_MAIN, 11, "bold"), fg=config.TEXT_SECONDARY, bg=config.HEADER_BG, cursor="hand2", padx=15)
            btn.pack(side="left", fill="y")
            
            def on_click(e): 
                self.switch_view(view)
                # Reset all tabs color
                for widget in nav_frame.winfo_children():
                    widget.config(fg=config.TEXT_SECONDARY)
                # Highlight active
                btn.config(fg=config.TEXT_PRIMARY)

            btn.bind("<Button-1>", on_click)
            return btn

        self.btn_dash = create_nav_tab("DASHBOARD", "dashboard")
        self.btn_sett = create_nav_tab("SETTINGS", "settings")
        # Logs tab removed
        
        # Set initial active state
        self.btn_dash.config(fg=config.TEXT_PRIMARY)

        # Right Side Status
        status_frame = tk.Frame(header, bg=config.HEADER_BG)
        status_frame.pack(side="right", padx=20)
        

    def switch_view(self, view_name):
        # Clear current view
        if self.current_view_frame:
            self.current_view_frame.destroy()
        
        self.current_view_frame = tk.Frame(self.content_area, bg=config.THEME_COLOR)
        self.current_view_frame.pack(fill="both", expand=True)
        
        if view_name == "dashboard":
            self._setup_dashboard_view(self.current_view_frame)
        elif view_name == "settings":
            self._setup_settings_view(self.current_view_frame)

    # --- VIEWS ---
    
    def _setup_settings_view(self, parent):
        tk.Label(parent, text="SYSTEM CONFIGURATION", font=(config.FONT_BOLD, 22, "bold"), fg=config.TEXT_PRIMARY, bg=config.THEME_COLOR).pack(anchor="w", pady=(0, 30))
        
        card = tk.Frame(parent, bg=config.CARD_BG, padx=40, pady=40)
        card.pack(fill="both", expand=True)
        
        # Settings Variables (Local to view)
        self.set_symbol = tk.StringVar(value=config.DEFAULT_SYMBOL)
        self.set_lot = tk.StringVar(value=config.DEFAULT_LOT_SIZE)
        self.set_host = tk.StringVar(value=config.HOST)
        self.set_port = tk.StringVar(value=str(config.PORT))
        
        def create_setting_row(label, var):
            f = tk.Frame(card, bg=config.CARD_BG)
            f.pack(fill="x", pady=10)
            tk.Label(f, text=label, width=20, anchor="w", font=(config.FONT_MAIN, 11), fg=config.TEXT_SECONDARY, bg=config.CARD_BG).pack(side="left")
            entry = tk.Entry(f, textvariable=var, font=(config.FONT_MONO, 11), bg=config.INPUT_BG, fg=config.TEXT_PRIMARY, insertbackground="white", bd=0, highlightthickness=1)
            entry.pack(side="left", fill="x", expand=True, ipady=8, ipadx=10)
            return entry

        create_setting_row("Default Symbol", self.set_symbol)
        create_setting_row("Default Lot Size", self.set_lot)
        tk.Frame(card, bg=config.CARD_BG, height=20).pack() # Spacer
        create_setting_row("Server Host", self.set_host)
        create_setting_row("Server Port", self.set_port)
        
        # Save Button
        btn_frame = tk.Frame(card, bg=config.CARD_BG)
        btn_frame.pack(pady=40, anchor="e")
        
        def save_settings():
            # Update Config
            config.DEFAULT_SYMBOL = self.set_symbol.get()
            config.DEFAULT_LOT_SIZE = self.set_lot.get()
            config.HOST = self.set_host.get()
            try:
                config.PORT = int(self.set_port.get())
            except ValueError: pass
            
            # Update State
            state.log("✅ Settings Saved! Restart required for Server changes.", "success")
            
            # Update Dashboard inputs if they exist or will exist
            self.symbol_var.set(config.DEFAULT_SYMBOL)
            self.lot_var.set(config.DEFAULT_LOT_SIZE)

        ModernButton(btn_frame, "SAVE SETTINGS", save_settings, config.ACCENT_BLUE, config.TEXT_PRIMARY, width=20).pack()

    def _setup_dashboard_view(self, parent):
        # Grid Layout for Dashboard
        parent.columnconfigure(0, weight=3) # Trade Panel
        parent.columnconfigure(1, weight=2) # Info Panel
        parent.rowconfigure(0, weight=1)
        
        # Header (Top of Content)
        top = tk.Frame(parent, bg=config.THEME_COLOR)
        top.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 20))
        tk.Label(top, text="DASHBOARD", font=(config.FONT_BOLD, 22, "bold"), fg=config.TEXT_PRIMARY, bg=config.THEME_COLOR).pack(side="left")
        self.status_pill = tk.Label(top, text="Wait...", font=(config.FONT_MONO, 10), bg=config.INPUT_BG, fg=config.TEXT_SECONDARY, padx=12, pady=6)
        self.status_pill.pack(side="right")

        # LEFT PANEL
        left_panel = tk.Frame(parent, bg=config.THEME_COLOR)
        left_panel.grid(row=1, column=0, sticky="nsew", padx=(0, 20))
        
        self._setup_market_monitor(left_panel)
        self._setup_trade_controls(left_panel)
        
        # RIGHT PANEL
        right_panel = tk.Frame(parent, bg=config.THEME_COLOR)
        right_panel.grid(row=1, column=1, sticky="nsew")
        
        self._setup_account_panel(right_panel)
        self._setup_log_panel(right_panel)

    def _setup_market_monitor(self, parent):
        card = tk.Frame(parent, bg=config.CARD_BG)
        card.pack(fill="x", pady=(0, 20))
        
        # Header
        h = tk.Frame(card, bg=config.CARD_BG, pady=15, padx=20)
        h.pack(fill="x")
        self.lbl_symbol = tk.Label(h, text=config.DEFAULT_SYMBOL, font=(config.FONT_BOLD, 32, "bold"), fg=config.TEXT_PRIMARY, bg=config.CARD_BG)
        self.lbl_symbol.pack(side="left")
        
        self.lbl_spread = tk.Label(h, text="SPREAD: 0", font=(config.FONT_MONO, 12), fg=config.ACCENT_PURPLE, bg=config.CARD_BG)
        self.lbl_spread.pack(side="right", pady=10)

        # Price Display (Big Bid/Ask)
        prices = tk.Frame(card, bg=config.CARD_BG, pady=10)
        prices.pack(fill="x", padx=20, pady=(0, 20))
        
        prices.columnconfigure(0, weight=1)
        prices.columnconfigure(1, weight=1)
        
        # Bid
        bid_frame = tk.Frame(prices, bg=config.CARD_BG)
        bid_frame.grid(row=0, column=0)
        tk.Label(bid_frame, text="BID", font=(config.FONT_MAIN, 10, "bold"), fg=config.ACCENT_RED, bg=config.CARD_BG).pack()
        self.lbl_bid = tk.Label(bid_frame, text="0.0000", font=(config.FONT_MONO, 40, "bold"), fg=config.ACCENT_RED, bg=config.CARD_BG)
        self.lbl_bid.pack()
        
        # Ask
        ask_frame = tk.Frame(prices, bg=config.CARD_BG)
        ask_frame.grid(row=0, column=1)
        tk.Label(ask_frame, text="ASK", font=(config.FONT_MAIN, 10, "bold"), fg=config.ACCENT_GREEN, bg=config.CARD_BG).pack()
        self.lbl_ask = tk.Label(ask_frame, text="0.0000", font=(config.FONT_MONO, 40, "bold"), fg=config.ACCENT_GREEN, bg=config.CARD_BG)
        self.lbl_ask.pack()

    def _setup_trade_controls(self, parent):
        card = tk.Frame(parent, bg=config.CARD_BG, padx=20, pady=20)
        card.pack(fill="x")
        
        # Title
        tk.Label(card, text="ORDER EXECUTION", font=(config.FONT_MAIN, 10, "bold"), fg=config.TEXT_MUTED, bg=config.CARD_BG).pack(fill="x", pady=(0, 15))
        
        # Inputs Row 1
        row1 = tk.Frame(card, bg=config.CARD_BG)
        row1.pack(fill="x", pady=5)
        
        self._create_input_group(row1, "Volume", self.lot_var, width=10).pack(side="left", padx=(0, 20))

        # SL / TP Spinboxes (Horizontal Layout)
        def create_spin_row(parent, label, var):
            f = tk.Frame(parent, bg=config.CARD_BG)
            f.pack(side="left", padx=10)
            
            tk.Label(f, text=label, font=(config.FONT_MAIN, 11), fg=config.TEXT_SECONDARY, bg=config.CARD_BG).pack(side="left", padx=(0, 8))
            
            sb = tk.Spinbox(f, textvariable=var, from_=0.0, to=100000.0, increment=0.01, font=(config.FONT_MONO, 12),
                            bg=config.INPUT_BG, fg=config.TEXT_PRIMARY, bd=0, width=10, buttonbackground=config.INPUT_BG)
            sb.pack(side="left", ipady=4)
            
            # Auto-fill current price on focus if empty/zero
            def on_focus(e):
                try:
                    if float(var.get()) <= 0 and state.current_ask > 0:
                        var.set(f"{state.current_ask:.2f}")
                except ValueError: pass
            sb.bind("<FocusIn>", on_focus)
            
            return f

        create_spin_row(row1, "Stop Loss:", self.sl_var)
        create_spin_row(row1, "Take Profit:", self.tp_var)

        # Buttons (Big)
        btn_row = tk.Frame(card, bg=config.CARD_BG)
        btn_row.pack(fill="x", pady=25)
        
        # SELL Button
        sell_frame = tk.Frame(btn_row, bg=config.ACCENT_RED, padx=1, pady=1) # Border feeling
        sell_frame.pack(side="left", fill="x", expand=True, padx=(0, 10))
        btn_sell = tk.Label(sell_frame, text="SELL", font=(config.FONT_BOLD, 18, "bold"), bg=config.ACCENT_RED, fg=config.TEXT_PRIMARY, cursor="hand2", pady=15)
        btn_sell.pack(fill="both")
        btn_sell.bind("<Button-1>", lambda e: self.queue_command("SELL"))
        
        # BUY Button
        buy_frame = tk.Frame(btn_row, bg=config.ACCENT_GREEN, padx=1, pady=1)
        buy_frame.pack(side="left", fill="x", expand=True, padx=(10, 0))
        btn_buy = tk.Label(buy_frame, text="BUY", font=(config.FONT_BOLD, 18, "bold"), bg=config.ACCENT_GREEN, fg=config.TEXT_PRIMARY, cursor="hand2", pady=15)
        btn_buy.pack(fill="both")
        btn_buy.bind("<Button-1>", lambda e: self.queue_command("BUY"))

        # Management Buttons
        close_row = tk.Frame(card, bg=config.CARD_BG)
        close_row.pack(fill="x", pady=10)
        
        ModernButton(close_row, "Close Winners", lambda: self.queue_command("CLOSE_WIN"), config.INPUT_BG, config.TEXT_PRIMARY).pack(side="left", fill="x", expand=True, padx=(0,5))
        ModernButton(close_row, "Close Losers", lambda: self.queue_command("CLOSE_LOSS"), config.INPUT_BG, config.TEXT_PRIMARY).pack(side="left", fill="x", expand=True, padx=5)
        ModernButton(close_row, "CLOSE ALL", lambda: self.queue_command("CLOSE_ALL"), "#3f3f46", config.TEXT_PRIMARY).pack(side="left", fill="x", expand=True, padx=(5,0))

    def _setup_account_panel(self, parent):
        card = tk.Frame(parent, bg=config.CARD_BG, padx=20, pady=20)
        card.pack(fill="x", pady=(0, 20))
        
        tk.Label(card, text="ACCOUNT SUMMARY", font=(config.FONT_MAIN, 10, "bold"), fg=config.TEXT_MUTED, bg=config.CARD_BG).pack(fill="x", pady=(0, 15))
        
        self.lbl_balance = self._create_metric_row(card, "Balance")
        self.lbl_equity = self._create_metric_row(card, "Equity")
        self.lbl_margin = self._create_metric_row(card, "Margin")
        
        # Profit Hero
        p_frame = tk.Frame(card, bg=config.INPUT_BG, padx=15, pady=15)
        p_frame.pack(fill="x", pady=(15, 0))
        tk.Label(p_frame, text="FLOATING P/L", font=(config.FONT_MAIN, 9, "bold"), fg=config.TEXT_SECONDARY, bg=config.INPUT_BG).pack(anchor="w")
        self.lbl_profit = tk.Label(p_frame, text="+0.00", font=(config.FONT_MONO, 24, "bold"), fg=config.ACCENT_GREEN, bg=config.INPUT_BG)
        self.lbl_profit.pack(anchor="w")

        # Auto Trade Toggle
        auto_frame = tk.Frame(card, bg=config.CARD_BG)
        auto_frame.pack(fill="x", pady=(20, 0))
        
        tk.Checkbutton(auto_frame, text="Activate Auto-Agent", variable=self.auto_trade_var, 
                       bg=config.CARD_BG, fg=config.ACCENT_BLUE, activebackground=config.CARD_BG, 
                       selectcolor=config.CARD_BG, font=(config.FONT_BOLD, 11, "bold"),
                       command=self.toggle_auto_trade).pack(side="left")

    def _setup_log_panel(self, parent):
        card = tk.Frame(parent, bg=config.CARD_BG, padx=20, pady=20)
        card.pack(fill="both", expand=True)
        
        h = tk.Frame(card, bg=config.CARD_BG)
        h.pack(fill="x", pady=(0, 10))
        tk.Label(h, text="SYS LOG", font=(config.FONT_MAIN, 10, "bold"), fg=config.TEXT_MUTED, bg=config.CARD_BG).pack(side="left")
        
        self.log_text = tk.Text(card, bg=config.THEME_COLOR, fg=config.TEXT_SECONDARY, 
                                font=(config.FONT_MONO, 9), bd=0, highlightthickness=0, 
                                padx=10, pady=10, state="disabled")
        self.log_text.pack(fill="both", expand=True)

    # UI Helpers
    def _create_input_group(self, parent, label, variable, width):
        f = tk.Frame(parent, bg=config.CARD_BG)
        tk.Label(f, text=label.upper(), font=(config.FONT_MAIN, 8, "bold"), fg=config.TEXT_SECONDARY, bg=config.CARD_BG).pack(anchor="w", pady=(0,5))
        e = tk.Entry(f, textvariable=variable, width=width, font=(config.FONT_MONO, 12), 
                     bg=config.INPUT_BG, fg=config.TEXT_PRIMARY, bd=0, 
                     highlightthickness=1, highlightbackground=config.INPUT_BG, highlightcolor=config.ACCENT_BLUE)
        e.pack(ipady=8, ipadx=5, fill="x")
        return f

    def _create_metric_row(self, parent, label):
        f = tk.Frame(parent, bg=config.CARD_BG)
        f.pack(fill="x", pady=4)
        tk.Label(f, text=label, font=(config.FONT_MAIN, 10), fg=config.TEXT_SECONDARY, bg=config.CARD_BG).pack(side="left")
        val = tk.Label(f, text="0.00", font=(config.FONT_MONO, 11), fg=config.TEXT_PRIMARY, bg=config.CARD_BG)
        val.pack(side="right")
        return val

    # Logic Implementation
    def queue_command(self, action):
        sym = self.symbol_var.get().strip().upper()
        if not sym: sym = config.DEFAULT_SYMBOL
        
        if not state.is_connected:
            state.log("❌ MT5 Not Connected", "error")
            return

        cmd = f"{action}|{sym}|{self.lot_var.get()}|{self.sl_var.get()}|{self.tp_var.get()}"
        state.pending_command = cmd
        state.log(f"Queued: {action}", "info")

    def toggle_auto_trade(self):
        enabled = self.auto_trade_var.get()
        state.auto_trade_enabled = enabled
        msg = "Auto-Agent ACTIVE" if enabled else "Auto-Agent PAUSED"
        state.log(msg, "success" if enabled else "warning")
        if enabled:
            threading.Thread(target=self._auto_trade_loop, daemon=True).start()

    def _auto_trade_loop(self):
        # AI‑driven auto‑trading loop
        while state.auto_trade_enabled:
            time.sleep(1)  # poll interval
            if not state.is_connected:
                continue
            try:
                state_dict = {
                    "current_symbol": self.symbol_var.get().strip().upper() or config.DEFAULT_SYMBOL,
                    "current_bid": state.current_bid,
                    "current_ask": state.current_ask,
                    "market_is_open": state.market_is_open,
                }
                decision = state.strategy.run(state_dict)
                if decision == "BUY":
                    self.queue_command("BUY")
                elif decision == "SELL":
                    self.queue_command("SELL")
                # Log AI decision
                state.log(f"AI Auto‑Trade decision: {decision}", "info")
            except Exception as e:
                state.log(f"AI Auto‑Trade error: {e}", "error")

    def _connection_watchdog(self):
        while True:
            time.sleep(1)
            if state.is_connected and (time.time() - state.last_poll_time > 5):
                state.update_connection(False)

    # Updates
    def log_to_gui(self, msg, log_type):
        if self.root:
            self.root.after(0, lambda: self._insert_log(msg, log_type))

    def _insert_log(self, msg, log_type):
        try:
            # Check if log_text exists and is valid
            if not hasattr(self, 'log_text') or self.log_text is None:
                return
            
            # This check causes an error if the widget is already destroyed
            try:
                if not self.log_text.winfo_exists():
                    return
            except Exception:
                return

            t = datetime.now().strftime("%H:%M:%S")
            c = {"info": config.ACCENT_BLUE, "success": config.ACCENT_GREEN, "warning": config.ACCENT_WARNING, "error": config.ACCENT_RED}
            
            self.log_text.configure(state="normal")
            self.log_text.insert("1.0", f"[{t}] {msg}\n")
            
            self.log_text.tag_add("latest", "1.0", "1.end")
            self.log_text.tag_config("latest", foreground=c.get(log_type, config.TEXT_PRIMARY))
            
            self.log_text.configure(state="disabled")
        except Exception as e:
            # Fallback to console if GUI fails
            print(f"[GUI LOG ERROR] {e} - Message: {msg}")

    def update_connection_status(self, connected):
        color = config.ACCENT_GREEN if connected else config.ACCENT_RED
        txt = "ONLINE" if connected else "OFFLINE"
        if self.root:
            self.root.after(0, lambda: self._safe_config(self.status_pill, fg=color, text=f"● {txt}"))
            if hasattr(self, 'side_status_dot'):
                 self.root.after(0, lambda: self._safe_config(self.side_status_dot, fg=color))

    def update_market_status(self, is_open):
        pass

    def update_price_display(self, symbol, bid, ask):
        if self.root:
            self.root.after(0, lambda: self._update_price_safe(symbol, bid, ask))

    def _update_price_safe(self, symbol, bid, ask):
        try:
            if not hasattr(self, 'lbl_bid') or not self.lbl_bid.winfo_exists(): return
            self.lbl_bid.configure(text=f"{bid:.2f}")
            self.lbl_ask.configure(text=f"{ask:.2f}")
            self.lbl_spread.configure(text=f"SPREAD: {int((ask-bid)*100)}")
            self.lbl_symbol.configure(text=symbol)
        except Exception: pass

    def update_account_display(self, name, balance, equity, margin, free_margin, profit):
        pc = config.ACCENT_GREEN if profit >= 0 else config.ACCENT_RED
        if self.root:
            self.root.after(0, lambda: self._update_account_safe(balance, equity, margin, profit, pc))

    def _update_account_safe(self, balance, equity, margin, profit, pc):
        try:
             if not hasattr(self, 'lbl_balance') or not self.lbl_balance.winfo_exists(): return
             self.lbl_balance.configure(text=f"${balance:,.2f}")
             self.lbl_equity.configure(text=f"${equity:,.2f}")
             self.lbl_margin.configure(text=f"${margin:,.2f}")
             self.lbl_profit.configure(text=f"{profit:+.2f}", fg=pc)
        except Exception: pass

    def _safe_config(self, widget, **kwargs):
        try:
            if widget.winfo_exists():
                widget.configure(**kwargs)
        except Exception: pass
