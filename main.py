import tkinter as tk
import threading
from src.core.logger import logger
from src.core.events import events, EventType
from src.state import state
from src.ui.main_window import MainWindow
from src.server import start_server
from src.ai.predictor import SimplePredictor

def main():
    """Application entry point with clean separation of concerns."""
    
    # 1. Setup UI First (to catch subsequent logs)
    root = tk.Tk()
    app = MainWindow(root)

    # 2. Initialize logic and services
    state.predictor = SimplePredictor()
    logger.info("⚡ AI Trading Engine Initialized")

    # 3. Start background services
    server_thread = threading.Thread(target=start_server, daemon=True)
    server_thread.start()
    
    # 4. Connection Watchdog (simple heartbeat checker)
    def heartbeat_monitor():
        import time
        while True:
            time.sleep(2)
            # If no price update for > 30s, consider it offline
            if state.is_connected and (time.time() - state.last_heartbeat > 30):
                logger.warning("Heartbeat lost - MT5 disconnected (Bot is busy?)")
                events.emit(EventType.CONNECTION_CHANGE, False)
                
    threading.Thread(target=heartbeat_monitor, daemon=True).start()

    # 5. Application Lifecycle
    logger.info("🚀 MT5 Agent is ready. Waiting for EA connection...")
    
    try:
        root.mainloop()
    except KeyboardInterrupt:
        logger.info("User requested shutdown.")
    finally:
        logger.info("System shutting down. Goodbye!")

if __name__ == "__main__":
    main()
