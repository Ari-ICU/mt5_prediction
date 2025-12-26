import logging
import sys
from .events import events, EventType

class GUIHandler(logging.Handler):
    """Custom logging handler to push messages to the EventManager."""
    def emit(self, record):
        log_entry = self.format(record)
        # Determine log type for GUI styling
        log_type = "info"
        if record.levelno >= logging.ERROR:
            log_type = "error"
        elif record.levelno >= logging.WARNING:
            log_type = "warning"
        elif record.levelno == 25: # SUCCESS
            log_type = "success"
        elif record.levelno == logging.DEBUG:
            log_type = "info"
        
        events.emit(EventType.LOG_MESSAGE, {"msg": log_entry, "type": log_type})

def setup_logger(name="MT5Bot"):
    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)

    # Console Handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_formatter = logging.Formatter(
        "[%(levelname)s] %(asctime)s - %(message)s", 
        datefmt="%H:%M:%S"
    )
    console_handler.setFormatter(console_formatter)
    logger.addHandler(console_handler)

    # GUI Handler
    gui_handler = GUIHandler()
    gui_handler.setFormatter(logging.Formatter("%(message)s"))
    logger.addHandler(gui_handler)

    return logger

# Add SUCCESS level
logging.addLevelName(25, "SUCCESS")
def success(self, message, *args, **kws):
    if self.isEnabledFor(25):
        self._log(25, message, args, **kws)
logging.Logger.success = success

# Global logger
logger = setup_logger()
LogStatus = EventType.LOG_MESSAGE
