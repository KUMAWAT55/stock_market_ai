from __future__ import annotations
"""Feature vector assembly for realtime inference and offline model training."""

from dataclasses import dataclass
from typing import Any

import pandas as pd

from features.indicators import add_indicators


FEATURE_COLUMNS: list[str] = [
    "ret_1",
    "ret_3",
    "ret_5",
    "ret_15",
    "macd",
    "macd_signal",
    "macd_hist",
    "rsi_14",
    "atr_pct",
    "volatility_20",
    "volume_zscore_20",
    "bb_width",
    "session_progress",
    "minute_sin",
    "minute_cos",
]


@dataclass(slots=True)
class FeatureResult:
    """Container for model features and aligned source candle metadata."""

    features: dict[str, Any]
    latest_candle: dict[str, Any]


class FeaturePipeline:
    """Builds model-ready feature vectors from OHLCV candles."""

    def __init__(self, minimum_rows: int = 40) -> None:
        self.minimum_rows = minimum_rows

    def transform(self, candles: pd.DataFrame) -> pd.DataFrame:
        """Apply indicator stack and return enriched dataframe."""
        return add_indicators(candles)

    def latest_feature_row(self, candles: pd.DataFrame) -> FeatureResult | None:
        """Return the most recent fully-populated feature row, if enough history exists."""
        frame = self.transform(candles)
        if frame.empty or len(frame) < self.minimum_rows:
            return None

        clean = frame.dropna(subset=FEATURE_COLUMNS).copy()
        if clean.empty:
            return None

        latest = clean.iloc[-1]
        feature_map = {key: float(latest[key]) for key in FEATURE_COLUMNS}
        latest_candle = {
            "candle_start": latest["candle_start"],
            "candle_end": latest["candle_end"],
            "open": float(latest["open"]),
            "high": float(latest["high"]),
            "low": float(latest["low"]),
            "close": float(latest["close"]),
            "volume": int(latest["volume"]),
        }
        return FeatureResult(features=feature_map, latest_candle=latest_candle)


def build_training_frame(candles: pd.DataFrame, horizon_steps: int = 1) -> pd.DataFrame:
    """Return feature frame with binary target for next-candle direction."""
    frame = add_indicators(candles)
    frame["target_up"] = (frame["close"].shift(-horizon_steps) > frame["close"]).astype(int)
    return frame.dropna(subset=FEATURE_COLUMNS + ["target_up"]).copy()
