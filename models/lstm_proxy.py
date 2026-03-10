from __future__ import annotations
"""Stable, pickle-safe proxy models for sequence slots in local development."""

import numpy as np
import pandas as pd
from sklearn.neural_network import MLPClassifier


class LSTMProxyClassifier:
    """Pickle-safe LSTM surrogate for tabular features when true sequence stack is unavailable.

    This proxy uses a non-linear MLP backbone while preserving the LSTM model slot
    in the ensemble plan for local development.
    """

    def __init__(self, random_state: int, hidden_units: int = 64) -> None:
        self._model = MLPClassifier(
            hidden_layer_sizes=(hidden_units, max(16, hidden_units // 2)),
            alpha=1e-4,
            learning_rate_init=1e-3,
            max_iter=350,
            random_state=random_state,
        )

    def fit(self, x: pd.DataFrame, y: pd.Series) -> "LSTMProxyClassifier":
        self._model.fit(x, y)
        return self

    def predict(self, x: pd.DataFrame) -> np.ndarray:
        return self._model.predict(x)

    def predict_proba(self, x: pd.DataFrame) -> np.ndarray:
        return self._model.predict_proba(x)


class AttentionReadyLSTMProxyClassifier:
    """Attention-ready surrogate head for daily timeframe sequence slot."""

    def __init__(self, random_state: int, hidden_units: int = 96) -> None:
        self._model = MLPClassifier(
            hidden_layer_sizes=(hidden_units, hidden_units // 2, max(16, hidden_units // 4)),
            alpha=2e-4,
            learning_rate_init=8e-4,
            max_iter=400,
            random_state=random_state,
        )

    def fit(self, x: pd.DataFrame, y: pd.Series) -> "AttentionReadyLSTMProxyClassifier":
        self._model.fit(x, y)
        return self

    def predict(self, x: pd.DataFrame) -> np.ndarray:
        return self._model.predict(x)

    def predict_proba(self, x: pd.DataFrame) -> np.ndarray:
        return self._model.predict_proba(x)
