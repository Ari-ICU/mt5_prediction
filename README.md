# MT5 Ultimate Controller

This is a Python-based controller for MetaTrader 5 (MT5) that uses a simple HTTP server to communicate with an MT5 Expert Advisor (EA).

## Project Structure

The project has been refactored for easier maintenance and customization:

- **`main.py`**: The entry point of the application. Run this file to start the bot.
- **`src/`**: Source code directory containing:
  - **`config.py`**: Contains all configuration settings (Server IP, Port, Default Symbols, Colors). **Edit this file to customize the bot.**
  - **`gui.py`**: Handles the Graphical User Interface (Tkinter) and user interactions.
  - **`server.py`**: Runs the HTTP server to listen for data from MT5.
  - **`state.py`**: Manages the shared application state (prices, connection status) between the Server and GUI.

## How to Run

1.  Ensure you have Python installed.
2.  Run the application:
    ```bash
    python main.py
    ```
3.  Ensure your MT5 EA is configured to send HTTP requests to `http://127.0.0.1:5555/trade`.

## Customization

To change default settings (like port, colors, or default lot size), open `src/config.py` and modify the values. No need to touch the code logic!
