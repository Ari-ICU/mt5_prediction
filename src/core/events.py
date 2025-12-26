from enum import Enum, auto
from typing import Dict, List, Callable, Any

class EventType(Enum):
    PRICE_UPDATE = auto()
    ACCOUNT_UPDATE = auto()
    CONNECTION_CHANGE = auto()
    MARKET_STATUS = auto()
    LOG_MESSAGE = auto()
    TRADE_COMMAND = auto()
    SETTINGS_CHANGE = auto()

class EventManager:
    """A simple Pub/Sub event dispatcher to decouple system components."""
    
    def __init__(self):
        self._listeners: Dict[EventType, List[Callable]] = {
            event_type: [] for event_type in EventType
        }

    def subscribe(self, event_type: EventType, callback: Callable):
        """Register a callback for a specific event type."""
        if callback not in self._listeners[event_type]:
            self._listeners[event_type].append(callback)

    def unsubscribe(self, event_type: EventType, callback: Callable):
        """Unregister a callback."""
        if callback in self._listeners[event_type]:
            self._listeners[event_type].remove(callback)

    def emit(self, event_type: EventType, data: Any = None):
        """Notify all subscribers of an event."""
        for callback in self._listeners[event_type]:
            try:
                if data is not None:
                    callback(data)
                else:
                    callback()
            except Exception as e:
                print(f"[Error] Failed to emit {event_type} to {callback.__name__}: {e}")

# Global instance
events = EventManager()
