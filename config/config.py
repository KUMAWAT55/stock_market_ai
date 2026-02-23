from __future__ import annotations
import json
import os
from dataclasses import dataclass, field
from datetime import date, time
from functools import lru_cache
from pathlib import Path
from typing import Any


ROOT_DIR = Path(__file__).resolve().parents[1]


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
    instrument_tokens: list[int] = field(default_factory=list)

    market_timezone: str = os.getenv("MARKET_TIMEZONE", "Asia/Kolkata")
    market_open: time = time(9, 15)
    market_close: time = time(15, 30)
    partial_market_closes: dict[str, str] = field(default_factory=dict)

    signal_buy_threshold: float = float(os.getenv("SIGNAL_BUY_THRESHOLD", "0.6"))
    signal_sell_threshold: float = float(os.getenv("SIGNAL_SELL_THRESHOLD", "0.4"))
    signal_cooldown_seconds: int = int(os.getenv("SIGNAL_COOLDOWN_SECONDS", "120"))

    max_capital_allocation_pct: float = float(os.getenv("MAX_CAPITAL_ALLOCATION_PCT", "0.2"))
    stop_loss_pct: float = float(os.getenv("STOP_LOSS_PCT", "0.02"))
    max_drawdown_pct: float = float(os.getenv("MAX_DRAWDOWN_PCT", "0.08"))

    symbol_token_map_file: Path = Path(
        os.getenv("SYMBOL_TOKEN_MAP_FILE", ROOT_DIR / "config/instruments.json")
    )
    market_holiday_file: Path = Path(
        os.getenv("MARKET_HOLIDAY_FILE", ROOT_DIR / "config/market_holidays.json")
    )

    @property
    def timeframe_minutes(self) -> dict[str, int]:
        return {"15m": 15, "1d": 24 * 60}

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
    settings = Settings()
    settings.model_artifact_dir.mkdir(parents=True, exist_ok=True)
    settings.log_path.parent.mkdir(parents=True, exist_ok=True)
    return settings
