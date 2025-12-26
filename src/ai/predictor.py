"""Simple AI predictor for price forecasting.
This module provides a lightweight, self‑contained predictor using scikit‑learn's
LinearRegression trained on synthetic data at import time. It offers a
`predict_price(state: dict) -> float` method that returns a forecasted ask price.
In a real project you would replace the synthetic training with a proper model
trained on historical market data.
"""

from sklearn.linear_model import LinearRegression
import numpy as np

class SimplePredictor:
    """A minimal price predictor.

    The model is trained on synthetic data when the class is instantiated.
    It expects a state dict with keys ``current_bid`` and ``current_ask``.
    """

    def __init__(self):
        # Generate synthetic training data
        # Features: [bid, ask, spread]
        bids = np.random.uniform(1700, 1800, size=200)
        asks = bids + np.random.uniform(0.5, 2.0, size=200)
        spreads = asks - bids
        X = np.column_stack([bids, asks, spreads])
        # Target: next ask price (simulated as current ask + small random move)
        y = asks + np.random.normal(0, 0.5, size=200)
        self.model = LinearRegression()
        self.model.fit(X, y)

    def predict_price(self, state: dict) -> float:
        """Return a forecasted ask price based on the current market state.

        Parameters
        ----------
        state: dict
            Must contain ``current_bid`` and ``current_ask``.
        """
        bid = state.get("current_bid", 0.0)
        ask = state.get("current_ask", 0.0)
        spread = ask - bid
        X = np.array([[bid, ask, spread]])
        pred = self.model.predict(X)[0]
        return float(pred)
