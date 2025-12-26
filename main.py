import tkinter as tk
import threading
import logging
from src.gui import MT5ControllerGUI
from src.server import start_server
from src.state import state
from src.ai.predictor import SimplePredictor

def main():
    """Entry point for the MT5 bot application.
    Sets up the Tkinter root window, starts the HTTP server in a daemon thread,
    and launches the GUI. Uses the built‑in logging module for console logs
    while still forwarding messages to the GUI via state.log.
    """
    # Configure a simple console logger (professional logging)
    logging.basicConfig(level=logging.INFO,
                        format="[%(levelname)s] %(asctime)s - %(message)s",
                        datefmt="%Y-%m-%d %H:%M:%S")
    logger = logging.getLogger(__name__)

    # Initialize AI predictor and attach to global state
    state.predictor = SimplePredictor()
    logger.info("AI predictor initialized")

    # Initialize the Root Window with a title and a reasonable size
    root = tk.Tk()
    root.title("MT5 Trading Bot – Professional Edition")
    root.geometry("1024x720")  # default window size, user can resize

    # Initialize the GUI Application
    app = MT5ControllerGUI(root)

    # Start the HTTP Server in a separate daemon thread (non‑blocking)
    server_thread = threading.Thread(target=start_server, daemon=True)
    server_thread.start()
    logger.info("HTTP server started in background thread")

    # Log initialization messages (both console and GUI)
    state.log("💻 System initialized", "info")
    state.log("📡 Waiting for MT5 connection...", "info")
    state.log("⚠️ Reminder: Ensure 'Algo Trading' button is GREEN in MT5", "warning")

    # Run the GUI main loop with graceful shutdown handling
    try:
        root.mainloop()
    except KeyboardInterrupt:
        logger.info("Application interrupted by user (KeyboardInterrupt)")
    finally:
        logger.info("Shutting down MT5 bot application")

if __name__ == "__main__":
    main()
