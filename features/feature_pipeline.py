from __future__ import annotations
"""Advanced feature engineering pipeline for global multi-symbol training/inference."""

from dataclasses import dataclass
from typing import Any
import zlib
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

from config.config import get_settings
from features.indicators import add_indicators


MICROSTRUCTURE_COLUMNS = [
    "candle_body_ratio",
    "upper_wick_ratio",
    "lower_wick_ratio",
    "volume_spike_ratio",
    "range_expansion_ratio",
]

COMMON_FEATURE_COLUMNS = [
    "symbol_code",
    "rsi_dist_50",
    "rsi_pct_rank_100",
    "rsi_delta",
    "roc_5",
    "ema_slope_norm",
    "macd_hist_change",
    "macd_hist_accel",
    "ema_distance_atr_norm",
    "atr_pct_rank_100",
    "rolling_vol_pct_rank_100",
    "bb_width_pct_rank_100",
    "volatility_regime",
    "relative_strength_vs_index",
    "sector_relative_momentum",
    "volatility_pct_universe",
]

TIMEFRAME_FEATURE_COLUMNS: dict[str, list[str]] = {
    "1m": COMMON_FEATURE_COLUMNS + MICROSTRUCTURE_COLUMNS,
    "5m": COMMON_FEATURE_COLUMNS + MICROSTRUCTURE_COLUMNS,
    "15m": COMMON_FEATURE_COLUMNS + MICROSTRUCTURE_COLUMNS,
    "1h": COMMON_FEATURE_COLUMNS + ["candle_body_ratio", "range_expansion_ratio"],
    "1d": COMMON_FEATURE_COLUMNS + ["candle_body_ratio"],
}

# Backward-compatible default used by older callers if timeframe is unavailable.
FEATURE_COLUMNS: list[str] = TIMEFRAME_FEATURE_COLUMNS["15m"]


def feature_columns_for_timeframe(timeframe: str) -> list[str]:
    """Return dedicated feature list for a timeframe."""
    return TIMEFRAME_FEATURE_COLUMNS.get(timeframe, FEATURE_COLUMNS)


def _rolling_percentile(series: pd.Series, window: int = 100) -> pd.Series:
    min_periods = min(window, 30)
    return series.rolling(window=window, min_periods=min_periods).apply(
        lambda values: float(pd.Series(values).rank(pct=True).iloc[-1]),
        raw=False,
    )


def _safe_div(num: pd.Series, den: pd.Series, eps: float = 1e-12) -> pd.Series:
    return num / den.replace(0.0, np.nan).fillna(eps)


def _normalize_timestamp_series(
    series: pd.Series,
    market_tz: ZoneInfo,
) -> pd.Series:
    """Normalize mixed tz-aware/tz-naive timestamp inputs into one market timezone."""
    normalized: list[pd.Timestamp] = []
    for value in series.tolist():
        if pd.isna(value):
            normalized.append(pd.NaT)
            continue
        ts = pd.Timestamp(value)
        if ts.tzinfo is None:
            ts = ts.tz_localize(market_tz)
        else:
            ts = ts.tz_convert(market_tz)
        normalized.append(ts)
    return pd.Series(normalized, index=series.index)


def _encode_symbol(symbol: str) -> float:
    # Stable hash encoding avoids train/serve mapping drift while preserving symbol identity.
    code = zlib.crc32(symbol.encode("utf-8")) % 100_000
    return (code / 50_000.0) - 1.0


def _apply_symbol_transforms(frame: pd.DataFrame) -> pd.DataFrame:
    groups: list[pd.DataFrame] = []
    for _symbol, part in frame.groupby("symbol", sort=False):
        part = add_indicators(part)
        part = part.sort_values("candle_start").reset_index(drop=True)

        part["symbol_code"] = float(_encode_symbol(str(part.loc[0, "symbol"])))
        part["rsi_dist_50"] = part["rsi_14"] - 50.0
        part["rsi_pct_rank_100"] = _rolling_percentile(part["rsi_14"], window=100)
        part["rsi_delta"] = part["rsi_14"].diff(1)
        part["roc_5"] = part["close"].pct_change(5)

        part["ema_slope_norm"] = _safe_div(part["ema_12"].diff(3), part["atr_14"])
        part["macd_hist_change"] = part["macd_hist"].diff(1)
        part["macd_hist_accel"] = part["macd_hist_change"].diff(1)
        part["ema_distance_atr_norm"] = _safe_div((part["ema_12"] - part["ema_26"]), part["atr_14"])

        part["atr_pct_rank_100"] = _rolling_percentile(part["atr_pct"], window=100)
        part["rolling_vol_pct_rank_100"] = _rolling_percentile(part["volatility_20"], window=100)
        part["bb_width_pct_rank_100"] = _rolling_percentile(part["bb_width"], window=100)

        vol_pct = part["rolling_vol_pct_rank_100"].fillna(0.5)
        part["volatility_regime"] = np.select(
            [vol_pct < 0.33, vol_pct < 0.66],
            [0.0, 1.0],
            default=2.0,
        )

        candle_range = (part["high"] - part["low"]).abs().replace(0.0, np.nan)
        candle_body = (part["close"] - part["open"]).abs()
        upper_wick = part["high"] - part[["open", "close"]].max(axis=1)
        lower_wick = part[["open", "close"]].min(axis=1) - part["low"]

        part["candle_body_ratio"] = _safe_div(candle_body, candle_range)
        part["upper_wick_ratio"] = _safe_div(upper_wick.clip(lower=0.0), candle_range)
        part["lower_wick_ratio"] = _safe_div(lower_wick.clip(lower=0.0), candle_range)
        part["volume_spike_ratio"] = _safe_div(part["volume"], part["volume"].rolling(30).median())
        part["range_expansion_ratio"] = _safe_div(candle_range, candle_range.rolling(30).median())

        groups.append(part)
    return pd.concat(groups, axis=0, ignore_index=True)


def _apply_cross_sectional_transforms(
    frame: pd.DataFrame,
    index_symbol: str | None,
    sector_map: dict[str, str] | None,
) -> pd.DataFrame:
    part = frame.copy()

    if index_symbol and index_symbol in set(part["symbol"].astype(str)):
        idx_returns = (
            part.loc[part["symbol"] == index_symbol, ["candle_end", "ret_1"]]
            .drop_duplicates(subset=["candle_end"])
            .rename(columns={"ret_1": "index_ret_1"})
        )
        part = part.merge(idx_returns, on="candle_end", how="left")
    else:
        part["index_ret_1"] = part.groupby("candle_end")["ret_1"].transform("median")

    part["index_ret_1"] = part["index_ret_1"].fillna(0.0)
    part["relative_strength_vs_index"] = part["ret_1"].fillna(0.0) - part["index_ret_1"]

    sector_mapping = {str(k).upper(): str(v).upper() for k, v in (sector_map or {}).items()}
    part["sector"] = part["symbol"].astype(str).str.upper().map(sector_mapping).fillna("UNKNOWN")
    sector_mean = part.groupby(["candle_end", "sector"])["roc_5"].transform("mean")
    part["sector_relative_momentum"] = part["roc_5"].fillna(0.0) - sector_mean.fillna(0.0)

    part["volatility_pct_universe"] = (
        part.groupby("candle_end")["volatility_20"].rank(pct=True).fillna(0.5)
    )
    return part


def feature_enriched_frame(
    candles: pd.DataFrame,
    index_symbol: str | None = None,
    sector_map: dict[str, str] | None = None,
) -> pd.DataFrame:
    """Return globally engineered frame including advanced transforms."""
    if candles.empty:
        return candles.copy()

    settings = get_settings()
    market_tz = ZoneInfo(settings.market_timezone)

    frame = candles.copy()
    frame["symbol"] = frame["symbol"].astype(str).str.upper()
    frame["candle_start"] = _normalize_timestamp_series(frame["candle_start"], market_tz=market_tz)
    frame["candle_end"] = _normalize_timestamp_series(frame["candle_end"], market_tz=market_tz)
    frame = frame.sort_values(["symbol", "candle_start"]).reset_index(drop=True)

    transformed = _apply_symbol_transforms(frame)
    transformed = _apply_cross_sectional_transforms(
        transformed,
        index_symbol=index_symbol,
        sector_map=sector_map,
    )

    numeric_cols = [
        *COMMON_FEATURE_COLUMNS,
        *MICROSTRUCTURE_COLUMNS,
    ]
    for col in numeric_cols:
        transformed[col] = pd.to_numeric(transformed[col], errors="coerce")
    transformed[numeric_cols] = transformed[numeric_cols].replace([np.inf, -np.inf], np.nan)
    return transformed


def filter_correlated_features(
    frame: pd.DataFrame,
    feature_columns: list[str],
    threshold: float = 0.97,
) -> tuple[list[str], list[str]]:
    """Drop highly correlated features to reduce multicollinearity."""
    if not feature_columns:
        return [], []
    corr = frame[feature_columns].corr().abs()
    upper = corr.where(np.triu(np.ones(corr.shape), k=1).astype(bool))
    dropped = [column for column in upper.columns if (upper[column] > threshold).any()]
    kept = [column for column in feature_columns if column not in dropped]
    return kept, dropped


@dataclass(slots=True)
class FeatureResult:
    """Container for model features and aligned source candle metadata."""

    features: dict[str, Any]
    latest_candle: dict[str, Any]


class FeaturePipeline:
    """Build model-ready feature vectors from OHLCV candles."""

    def __init__(self, minimum_rows: int = 40) -> None:
        self.minimum_rows = minimum_rows
        settings = get_settings()
        self._index_symbol = settings.market_index_symbol.upper()
        self._sector_map = settings.load_sector_map()

    def transform(self, candles: pd.DataFrame) -> pd.DataFrame:
        """Apply advanced feature engineering for all symbols in input frame."""
        return feature_enriched_frame(
            candles,
            index_symbol=self._index_symbol,
            sector_map=self._sector_map,
        )

    def latest_feature_row(
        self,
        candles: pd.DataFrame,
        *,
        symbol: str | None = None,
        timeframe: str | None = None,
    ) -> FeatureResult | None:
        """Return latest fully-populated feature vector for inference.

        If `symbol` is provided, extraction is constrained to that symbol so
        cross-sectional transforms can be computed on a global frame while
        serving one symbol's prediction.
        """
        frame = self.transform(candles)
        if frame.empty or len(frame) < self.minimum_rows:
            return None

        resolved_timeframe = timeframe
        if resolved_timeframe is None:
            resolved_timeframe = str(frame["timeframe"].iloc[-1]) if "timeframe" in frame.columns else "15m"
        cols = feature_columns_for_timeframe(resolved_timeframe)

        working = frame
        if symbol is not None and "symbol" in working.columns:
            working = working[working["symbol"].astype(str).str.upper() == symbol.upper()].copy()
            if working.empty:
                return None

        clean = working.dropna(subset=cols).copy()
        if clean.empty:
            return None

        latest = clean.sort_values("candle_end").iloc[-1]
        feature_map = {key: float(latest[key]) for key in cols}
        feature_map["symbol"] = str(latest["symbol"])
        if "ret_1" in latest.index and pd.notna(latest["ret_1"]):
            feature_map["ret_1"] = float(latest["ret_1"])
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


def build_training_frame(
    candles: pd.DataFrame,
    horizon_steps: int = 1,
    timeframe: str | None = None,
    target_threshold: float = 0.0,
    index_symbol: str | None = None,
    sector_map: dict[str, str] | None = None,
) -> pd.DataFrame:
    """Return feature frame with binary target for forward-return direction."""
    frame = feature_enriched_frame(candles, index_symbol=index_symbol, sector_map=sector_map)
    if frame.empty:
        return frame

    horizon = max(1, int(horizon_steps))
    frame = frame.sort_values(["symbol", "candle_start"]).reset_index(drop=True)
    frame["forward_return"] = frame.groupby("symbol")["close"].shift(-horizon) / frame["close"] - 1.0
    frame["target_up"] = (frame["forward_return"] > float(target_threshold)).astype(int)

    resolved_timeframe = timeframe
    if resolved_timeframe is None and "timeframe" in frame.columns:
        resolved_timeframe = str(frame["timeframe"].iloc[-1])
    feature_columns = feature_columns_for_timeframe(resolved_timeframe or "15m")
    return frame.dropna(subset=feature_columns + ["target_up"]).copy()
