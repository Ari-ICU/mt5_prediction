# 🤖 MT5 AI-Pro Trading Bot

A high-performance algorithmic trading system that bridges **Python's Machine Learning** capabilities with **MetaTrader 5**. This bot features real-time price forecasting, automated execution, and advanced profit management through a modern, premium GUI.

---

## 🌟 Key Features

### 🧠 AI Intelligence
- **Linear Regression Forecasting**: Predicts the next price move based on historical ticks.
- **Technical Indicators**: Real-time calculation of **RSI** and **SMA10** as AI features.
- **Confidence Scoring**: Dynamic confidence percentage that ensures trades are only taken on high-probability signals.
- **Pattern Recognition**: Bullish/Bearish pattern detection as a secondary trade confirmation.

### ⚙️ Auto-Trading Engine
- **Automated Execution**: Hands-free BUY/SELL orders based on AI signals.
- **Trade Protection**: Automatic Stop Loss (SL) and Take Profit (TP) placement.
- **Rate Limiting**: Integrated 30-second cooldown between trades to prevent order spamming.
- **Market Resilience**: Smart checks that prevent execution when the market is closed (Retcode 10040 protection).

### 💰 Profit & Risk Management
- **Total Profit Close**: Automatically closes all positions when the account-wide profit target is hit.
- **Per-Position Profit Close**: Closes individual trades once they reach a specific dollar profit.
- **Max Operations Limit**: User-defined cap on the number of open positions allowed simultaneously.

---

## 📂 Project Structure

- **`main.py`**: The application entry point.
- **`src/ai/`**: AI model logic and price prediction engine.
- **`src/strategies/`**: Decision matrix combining AI, News, and Patterns.
- **`src/ui/`**: Modern Tkinter-based dashboard with real-time logging.
- **`src/server.py`**: High-speed HTTP server for MT5 communication.
- **`src/state.py`**: Global state management and automated strategy orchestration.
- **`src/models/`**: Data models (pydantic-style) for market and trade information.
- **`SocketClient.mq5`**: The bridge Expert Advisor for MetaTrader 5.

---

## 🚀 Getting Started

### 1. Prerequisites
- Python 3.10+
- MetaTrader 5 Terminal (Windows or Mac via Wine/Crossover)

### 2. Installation
1. Clone the repository.
2. Install dependencies (if any):
   ```bash
   pip install scikit-learn numpy 
   ```

### 3. Setup MetaTrader 5
1. Open MT5 > Tools > Options > Expert Advisors.
2. Enable **"Allow WebRequest for listed URL"** and add: `http://127.0.0.1:5555`
3. Load `SocketClient.mq5` onto any chart (H1 timeframe recommended).

### 4. Launch the Bot
```bash
/usr/local/bin/python3 main.py
```

---

## 🛠️ Configuration
Most settings can be adjusted in real-time via the **AUTO-TRADING** tab in the UI:
- **Buy/Sell Confidence**: Adjust how aggressive the AI should be.
- **Tot. Profit ($)**: Target profit to clear the entire account.
- **Pos. Profit ($)**: Individual target for each trade.
- **Limit**: Max allowed open trades.

---

## 📈 Technical Specs
- **Communication Protocol**: HTTP POST (MT5 to Python) / JSON Response (Python to MT5).
- **GUI Framework**: Tkinter with a custom Dark-Aesthetics theme.
- **Prediction Delta**: Real-time calculation every tick.
