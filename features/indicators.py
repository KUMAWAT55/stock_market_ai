from __future__ import annotations
"""Technical indicator computations shared by training and realtime inference."""

import numpy as np
import pandas as pd


def _rsi(series: pd.Series, period: int = 14) -> pd.Series:
    """Compute RSI using exponential smoothing (Wilder-style approximation)."""
    delta = series.diff()
    gain = delta.clip(lower=0.0)
    loss = -delta.clip(upper=0.0)
    avg_gain = gain.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()
    avg_loss = loss.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()
    rs = avg_gain / avg_loss.replace(0.0, np.nan)
    return 100.0 - (100.0 / (1.0 + rs))


def _atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    """Compute Average True Range for volatility normalization."""
    high = df["high"]
    low = df["low"]
    close = df["close"]
    prev_close = close.shift(1)
    tr = pd.concat(
        [
            (high - low).abs(),
            (high - prev_close).abs(),
            (low - prev_close).abs(),
        ],
        axis=1,
    ).max(axis=1)
    return tr.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()


def add_indicators(candles: pd.DataFrame) -> pd.DataFrame:
    """Add technical indicators used by realtime and training pipelines."""
    df = candles.copy()
    if df.empty:
        return df

    df = df.sort_values("candle_start").reset_index(drop=True)

    df["ret_1"] = df["close"].pct_change(1)
    df["ret_3"] = df["close"].pct_change(3)
    df["ret_5"] = df["close"].pct_change(5)
    df["ret_15"] = df["close"].pct_change(15)

    df["ema_12"] = df["close"].ewm(span=12, adjust=False).mean()
    df["ema_26"] = df["close"].ewm(span=26, adjust=False).mean()
    df["macd"] = df["ema_12"] - df["ema_26"]
    df["macd_signal"] = df["macd"].ewm(span=9, adjust=False).mean()
    df["macd_hist"] = df["macd"] - df["macd_signal"]

    df["rsi_14"] = _rsi(df["close"], period=14)
    df["atr_14"] = _atr(df, period=14)
    df["atr_pct"] = df["atr_14"] / df["close"].replace(0.0, np.nan)

    df["volatility_20"] = df["ret_1"].rolling(20).std()
    df["volume_sma_20"] = df["volume"].rolling(20).mean()
    df["volume_zscore_20"] = (
        (df["volume"] - df["volume_sma_20"]) / df["volume"].rolling(20).std().replace(0.0, np.nan)
    )

    df["sma_20"] = df["close"].rolling(20).mean()
    bb_std = df["close"].rolling(20).std()
    df["bb_upper"] = df["sma_20"] + 2.0 * bb_std
    df["bb_lower"] = df["sma_20"] - 2.0 * bb_std
    df["bb_width"] = (df["bb_upper"] - df["bb_lower"]) / df["close"].replace(0.0, np.nan)

    # Session progress features encode intraday seasonality into cyclical terms.
    ts = pd.to_datetime(df["candle_end"])
    minute = ts.dt.hour * 60 + ts.dt.minute
    day_progress = (minute - (9 * 60 + 15)) / (6 * 60 + 15)
    day_progress = day_progress.clip(0.0, 1.0)
    df["session_progress"] = day_progress
    df["minute_sin"] = np.sin(2.0 * np.pi * day_progress)
    df["minute_cos"] = np.cos(2.0 * np.pi * day_progress)

    numeric_cols = [
        "open",
        "high",
        "low",
        "close",
        "volume",
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

    # Standardize numeric dtypes and sanitize non-finite values for ML compatibility.
    for col in numeric_cols:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    df[numeric_cols] = df[numeric_cols].replace([np.inf, -np.inf], np.nan)
    return df
