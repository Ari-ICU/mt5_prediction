# ================= CONFIGURATION =================

# Server Settings
HOST = "127.0.0.1"
PORT = 5555
ENDPOINT = "/trade"

# Trading Defaults
DEFAULT_SYMBOL = "XAUUSDm"
SYMBOL_OPTIONS = ["XAUUSDm", "BTCUSDm", "EURUSDm", "GBPUSDm", "USDJPYm", "ETHUSDm"]
DEFAULT_LOT_SIZE = "0.01"
DEFAULT_SL = "0"
DEFAULT_TP = "0"
AUTO_LOT_SIZE = 0.01
MAX_SPREAD_DEFAULT = 50

# GUI Settings
FULLSCREEN_MODE = False
WINDOW_WIDTH = 1200
WINDOW_HEIGHT = 900

# Modern Dark Theme (Obsidian/FinTech)
THEME_COLOR = "#000000"      # Pure Black for OLED contrast
HEADER_BG = "#0A0A0A"        # Very dark gray
CARD_BG = "#141414"          # Dark gray mainly for cards
INPUT_BG = "#262626"         # Lighter gray for inputs
HOVER_BG = "#333333"

# Typography Colors
TEXT_PRIMARY = "#FFFFFF"
TEXT_SECONDARY = "#A1A1AA"   # Zinc 400
TEXT_MUTED = "#52525B"       # Zinc 600
TEXT_ON_ACCENT = "#FFFFFF"

# Accents (Neon/Vibrant)
ACCENT_GREEN = "#00E676"     # Bright Neon Green
ACCENT_RED = "#FF1744"       # Bright Neon Red
ACCENT_WARNING = "#FFC400"   # Amber/Gold
ACCENT_BLUE = "#2979FF"      # Bright Blue
ACCENT_PURPLE = "#651FFF"    # Deep Violet

# Fonts
FONT_MAIN = "SF Pro Display" # Apple System Font (falls back if not present)
FONT_BOLD = "SF Pro Display"
FONT_MONO = "SF Mono"

# Auto Trading Defaults
BUY_THRESHOLD_DEFAULT = 0.00
SELL_THRESHOLD_DEFAULT = 0.00

# API Keys
NEWS_API_KEY = "06a1bc830ebe4303b34a966cc8a50e26" # Get one for free at newsapi.org
