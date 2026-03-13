from __future__ import annotations
"""Centralized runtime configuration for the realtime research platform.

This module is intentionally environment-driven so local, staging, and production
setups can use the same code path with different env vars.
"""

import json
import os
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import date, time
from functools import lru_cache
from pathlib import Path
from typing import Any


ROOT_DIR = Path(__file__).resolve().parents[1]


def _parse_json_env(value: str | None, default: Any) -> Any:
    """Parse optional JSON env var and fall back to provided default."""
    if not value:
        return default
    try:
        return json.loads(value)
    except Exception:
        return default


def _parse_csv_env(value: str, default: list[str]) -> list[str]:
    """Parse comma-separated env values into normalized lowercase tokens."""
    cleaned = [item.strip().lower() for item in value.split(",") if item.strip()]
    return cleaned if cleaned else [item.lower() for item in default]


def _parse_int_csv_env(value: str) -> list[int]:
    """Parse comma-separated integers and ignore invalid tokens."""
    out: list[int] = []
    for token in value.split(","):
        token = token.strip()
        if token.isdigit():
            out.append(int(token))
    return out


@dataclass(slots=True)
class Settings:
    """Application settings loaded from environment variables with sane local defaults."""

    app_name: str = "TradeIQ Realtime Research"
    app_env: str = os.getenv("APP_ENV", "local")

    kite_api_key: str = os.getenv("KITE_API_KEY", "")
    kite_access_token: str = os.getenv("KITE_ACCESS_TOKEN", "")

    database_url: str = os.getenv(
        "DATABASE_URL",
        "postgresql+psycopg2://postgres:postgres@localhost:5432/stock_market_ai",
    )

    log_path: Path = Path(os.getenv("LOG_PATH", ROOT_DIR / "logs/realtime_engine.log"))

    model_artifact_dir: Path = Path(os.getenv("MODEL_ARTIFACT_DIR", ROOT_DIR / "models/artifacts"))

    subscribe_mode: str = os.getenv("KITE_SUBSCRIBE_MODE", "full")
    instrument_tokens: list[int] = field(default_factory=lambda: _parse_int_csv_env(os.getenv("INSTRUMENT_TOKENS", "")))
    candle_timeframes: list[str] = field(
        default_factory=lambda: _parse_csv_env(
            os.getenv("CANDLE_TIMEFRAMES", "1m,5m,15m,1h,1d"),
            default=["1m", "5m", "15m", "1h", "1d"],
        )
    )
    model_timeframes: list[str] = field(
        default_factory=lambda: _parse_csv_env(
            os.getenv("MODEL_TIMEFRAMES", "1m,5m,15m,1h,1d"),
            default=["1m", "5m", "15m", "1h", "1d"],
        )
    )

    market_timezone: str = os.getenv("MARKET_TIMEZONE", "Asia/Kolkata")
    market_open: time = time(9, 15)
    market_close: time = time(15, 30)
    partial_market_closes: dict[str, str] = field(
        default_factory=lambda: json.loads(os.getenv("PARTIAL_MARKET_CLOSES_JSON", "{}"))
    )

    signal_bullish_threshold: float = float(os.getenv("SIGNAL_BULLISH_THRESHOLD", "0.6"))
    signal_bearish_threshold: float = float(os.getenv("SIGNAL_BEARISH_THRESHOLD", "0.4"))
    signal_cooldown_seconds: int = int(os.getenv("SIGNAL_COOLDOWN_SECONDS", "120"))
    signal_thresholds_by_timeframe: dict[str, dict[str, float]] = field(
        default_factory=lambda: _parse_json_env(
            os.getenv("SIGNAL_THRESHOLDS_BY_TIMEFRAME_JSON"),
            {
                "1m": {"bullish": 0.62, "bearish": 0.38},
                "5m": {"bullish": 0.60, "bearish": 0.40},
                "15m": {"bullish": 0.58, "bearish": 0.42},
                "1h": {"bullish": 0.56, "bearish": 0.44},
                "1d": {"bullish": 0.54, "bearish": 0.46},
            },
        )
    )
    risk_rules_by_timeframe: dict[str, dict[str, float]] = field(
        default_factory=lambda: _parse_json_env(
            os.getenv("RISK_RULES_BY_TIMEFRAME_JSON"),
            {
                "1m": {
                    "min_confidence": 0.58,
                    "cooldown_seconds": 180,
                    "max_capital_allocation_pct": 0.08,
                    "stop_loss_pct": 0.005,
                    "max_drawdown_pct": 0.04,
                },
                "5m": {
                    "min_confidence": 0.56,
                    "cooldown_seconds": 240,
                    "max_capital_allocation_pct": 0.10,
                    "stop_loss_pct": 0.0075,
                    "max_drawdown_pct": 0.05,
                },
                "15m": {
                    "min_confidence": 0.55,
                    "cooldown_seconds": 360,
                    "max_capital_allocation_pct": 0.14,
                    "stop_loss_pct": 0.01,
                    "max_drawdown_pct": 0.06,
                },
                "1h": {
                    "min_confidence": 0.53,
                    "cooldown_seconds": 900,
                    "max_capital_allocation_pct": 0.18,
                    "stop_loss_pct": 0.015,
                    "max_drawdown_pct": 0.08,
                },
                "1d": {
                    "min_confidence": 0.52,
                    "cooldown_seconds": 3600,
                    "max_capital_allocation_pct": 0.20,
                    "stop_loss_pct": 0.02,
                    "max_drawdown_pct": 0.10,
                },
            },
        )
    )
    auto_backfill_days_by_timeframe: dict[str, int] = field(
        default_factory=lambda: _parse_json_env(
            os.getenv("AUTO_BACKFILL_DAYS_BY_TIMEFRAME_JSON"),
            {"1m": 7, "5m": 30, "15m": 90, "1h": 365, "1d": 1460},
        )
    )
    auto_backfill_min_candles_by_timeframe: dict[str, int] = field(
        default_factory=lambda: _parse_json_env(
            os.getenv("AUTO_BACKFILL_MIN_CANDLES_BY_TIMEFRAME_JSON"),
            {"1m": 420, "5m": 420, "15m": 260, "1h": 200, "1d": 120},
        )
    )
    auto_backfill_freshness_minutes_by_timeframe: dict[str, int] = field(
        default_factory=lambda: _parse_json_env(
            os.getenv("AUTO_BACKFILL_FRESHNESS_MINUTES_BY_TIMEFRAME_JSON"),
            {"1m": 20, "5m": 45, "15m": 120, "1h": 480, "1d": 4320},
        )
    )
    auto_historical_ensure_enabled: bool = os.getenv("AUTO_HISTORICAL_ENSURE_ENABLED", "true").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }
    auto_historical_ensure_interval_seconds: int = int(os.getenv("AUTO_HISTORICAL_ENSURE_INTERVAL_SECONDS", "300"))
    auto_historical_ensure_max_jobs_per_sweep: int = int(
        os.getenv("AUTO_HISTORICAL_ENSURE_MAX_JOBS_PER_SWEEP", "8")
    )
    forward_return_thresholds: dict[str, float] = field(
        default_factory=lambda: json.loads(
            os.getenv(
                "FORWARD_RETURN_THRESHOLDS_JSON",
                '{"1m":0.00015,"5m":0.0003,"15m":0.0006,"1h":0.0015,"1d":0.003}',
            )
        )
    )
    market_index_symbol: str = os.getenv("MARKET_INDEX_SYMBOL", "NIFTY 50")
    sector_map_file: Path = Path(
        os.getenv("SECTOR_MAP_FILE", ROOT_DIR / "config/sectors.json")
    )

    max_capital_allocation_pct: float = float(os.getenv("MAX_CAPITAL_ALLOCATION_PCT", "0.2"))
    stop_loss_pct: float = float(os.getenv("STOP_LOSS_PCT", "0.02"))
    max_drawdown_pct: float = float(os.getenv("MAX_DRAWDOWN_PCT", "0.08"))

    symbol_token_map_file: Path = Path(
        os.getenv("SYMBOL_TOKEN_MAP_FILE", ROOT_DIR / "config/instruments.json")
    )
    market_holiday_file: Path = Path(
        os.getenv("MARKET_HOLIDAY_FILE", ROOT_DIR / "config/market_holidays.json")
    )
    model_hyperparams_file: Path = Path(
        os.getenv("MODEL_HYPERPARAMS_FILE", ROOT_DIR / "config/model_hyperparams.json")
    )

    @property
    def timeframe_minutes(self) -> dict[str, int]:
        """Map configured timeframe labels to minute duration for scheduling math."""
        mapping: dict[str, int] = {}
        for timeframe in self.candle_timeframes:
            if timeframe.endswith("m") and timeframe[:-1].isdigit():
                mapping[timeframe] = int(timeframe[:-1])
                continue
            if timeframe.endswith("h") and timeframe[:-1].isdigit():
                mapping[timeframe] = int(timeframe[:-1]) * 60
                continue
            if timeframe.endswith("d") and timeframe[:-1].isdigit():
                mapping[timeframe] = int(timeframe[:-1]) * 24 * 60
        return mapping

    def load_symbol_token_map(self) -> dict[int, str]:
        """Return token->symbol map from a local JSON file if present."""
        if not self.symbol_token_map_file.exists():
            return {}
        with self.symbol_token_map_file.open("r", encoding="utf-8") as f:
            payload = json.load(f)
        # Supports either {"12345": "RELIANCE"} or [{"instrument_token":12345,"tradingsymbol":"RELIANCE"}]
        if isinstance(payload, dict):
            return {int(token): str(symbol) for token, symbol in payload.items()}
        mapping: dict[int, str] = {}
        if isinstance(payload, list):
            for row in payload:
                token = row.get("instrument_token")
                symbol = row.get("tradingsymbol") or row.get("symbol")
                if token is not None and symbol:
                    mapping[int(token)] = str(symbol)
        return mapping

    def load_market_holidays(self) -> set[date]:
        """Load holiday dates in YYYY-MM-DD format from local JSON."""
        if not self.market_holiday_file.exists():
            return set()
        with self.market_holiday_file.open("r", encoding="utf-8") as f:
            raw = json.load(f)
        holidays: set[date] = set()
        if isinstance(raw, list):
            for value in raw:
                try:
                    holidays.add(date.fromisoformat(str(value)))
                except ValueError:
                    continue
        return holidays

    def load_sector_map(self) -> dict[str, str]:
        """Load optional symbol->sector map for cross-sectional momentum features."""
        if not self.sector_map_file.exists():
            return {}
        with self.sector_map_file.open("r", encoding="utf-8") as f:
            raw = json.load(f)
        if not isinstance(raw, Mapping):
            return {}
        out: dict[str, str] = {}
        for symbol, sector in raw.items():
            if symbol and sector:
                out[str(symbol).upper()] = str(sector).upper()
        return out

    def load_symbol_universe(self) -> list[str]:
        """Return canonical symbol universe from instruments.json."""
        token_map = self.load_symbol_token_map()
        return sorted({str(symbol).upper() for symbol in token_map.values() if symbol})

    def forward_return_threshold(self, timeframe: str) -> float:
        """Return configured forward-return threshold used to define binary target."""
        raw = self.forward_return_thresholds.get(timeframe)
        if raw is None:
            return 0.0
        return float(raw)

    def signal_thresholds_for_timeframe(self, timeframe: str) -> tuple[float, float]:
        """Return validated (buy, sell) thresholds for one timeframe."""
        fallback_bullish = float(self.signal_bullish_threshold)
        fallback_bearish = float(self.signal_bearish_threshold)
        profile = self.signal_thresholds_by_timeframe.get(timeframe, {})

        bullish = float(profile.get("bullish", fallback_bullish))
        bearish = float(profile.get("bearish", fallback_bearish))
        bullish = min(1.0, max(0.0, bullish))
        bearish = min(1.0, max(0.0, bearish))
        if bearish >= bullish:
            return fallback_bullish, fallback_bearish
        return bullish, bearish

    def risk_rules_for_timeframe(self, timeframe: str) -> dict[str, float]:
        """Return validated risk control profile for one timeframe."""
        defaults: dict[str, float] = {
            "min_confidence": 0.5,
            "cooldown_seconds": float(self.signal_cooldown_seconds),
            "max_capital_allocation_pct": float(self.max_capital_allocation_pct),
            "stop_loss_pct": float(self.stop_loss_pct),
            "max_drawdown_pct": float(self.max_drawdown_pct),
        }
        raw = self.risk_rules_by_timeframe.get(timeframe)
        if isinstance(raw, Mapping):
            for key in defaults:
                try:
                    defaults[key] = float(raw.get(key, defaults[key]))
                except Exception:
                    continue

        defaults["min_confidence"] = min(1.0, max(0.0, defaults["min_confidence"]))
        defaults["cooldown_seconds"] = max(0.0, defaults["cooldown_seconds"])
        defaults["max_capital_allocation_pct"] = min(1.0, max(0.01, defaults["max_capital_allocation_pct"]))
        defaults["stop_loss_pct"] = min(1.0, max(0.0001, defaults["stop_loss_pct"]))
        defaults["max_drawdown_pct"] = min(1.0, max(0.01, defaults["max_drawdown_pct"]))
        return defaults

    def auto_backfill_days(self, timeframe: str) -> int:
        """Return lookback days used for automatic historical sync."""
        value = self.auto_backfill_days_by_timeframe.get(timeframe, 30)
        return max(1, int(value))

    def auto_backfill_min_candles(self, timeframe: str) -> int:
        """Return minimum candles required for robust feature generation."""
        value = self.auto_backfill_min_candles_by_timeframe.get(timeframe, 200)
        return max(30, int(value))

    def auto_backfill_freshness_minutes(self, timeframe: str) -> int:
        """Return staleness threshold in minutes before automatic resync."""
        value = self.auto_backfill_freshness_minutes_by_timeframe.get(timeframe, 120)
        return max(5, int(value))

    def auto_ensure_interval_seconds(self) -> int:
        """Return frequency of backend auto ensure sweeps in seconds."""
        return max(30, int(self.auto_historical_ensure_interval_seconds))

    def auto_ensure_max_jobs_per_sweep(self) -> int:
        """Return max number of backfill jobs spawned in one sweep."""
        return max(1, int(self.auto_historical_ensure_max_jobs_per_sweep))

    def timeframe_rule_profile(self, timeframe: str) -> dict[str, float]:
        """Return merged signal+risk+sync profile used by inference and dashboard."""
        bullish, bearish = self.signal_thresholds_for_timeframe(timeframe)
        risk = self.risk_rules_for_timeframe(timeframe)
        return {
            "signal_bullish_threshold": bullish,
            "signal_bearish_threshold": bearish,
            "min_confidence": risk["min_confidence"],
            "cooldown_seconds": risk["cooldown_seconds"],
            "max_capital_allocation_pct": risk["max_capital_allocation_pct"],
            "stop_loss_pct": risk["stop_loss_pct"],
            "max_drawdown_pct": risk["max_drawdown_pct"],
            "auto_backfill_days": float(self.auto_backfill_days(timeframe)),
            "auto_backfill_min_candles": float(self.auto_backfill_min_candles(timeframe)),
            "auto_backfill_freshness_minutes": float(self.auto_backfill_freshness_minutes(timeframe)),
        }

    @staticmethod
    def serialize_features(features: dict[str, Any]) -> dict[str, Any]:
        """Coerce feature values into JSON-safe payload."""
        out: dict[str, Any] = {}
        for key, value in features.items():
            if value is None:
                out[key] = None
            elif isinstance(value, (int, float, str, bool)):
                out[key] = value
            else:
                out[key] = str(value)
        return out


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return a singleton settings object and ensure required local paths exist."""
    settings = Settings()
    settings.model_artifact_dir.mkdir(parents=True, exist_ok=True)
    settings.log_path.parent.mkdir(parents=True, exist_ok=True)
    return settings
