"""Base class for AI trading strategies.
All custom strategies should inherit from this class and implement the `run` method.
The `run` method receives the current market `state` dictionary and should return a command string
(e.g., "BUY", "SELL", or "HOLD").
"""

class StrategyBase:
    """Abstract base for strategies.

    Sub‑classes must implement ``run(state)`` and return a command string.
    """

    def __init__(self, name: str = "BaseStrategy"):
        self.name = name

    def run(self, state: dict) -> str:
        """Process the market ``state`` and decide an action.

        Override this method in subclasses.
        """
        raise NotImplementedError("Strategy must implement the run method")
