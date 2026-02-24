from __future__ import annotations

from datetime import datetime
from typing import Any, Callable

import pandas as pd
from loguru import logger

from config.config import get_settings

try:
    from kiteconnect import KiteConnect, KiteTicker
    from kiteconnect.exceptions import TokenException
except Exception:  # pragma: no cover - optional runtime dependency for docs/static checks
    KiteConnect = None
    KiteTicker = None
    TokenException = Exception


TickCallback = Callable[[Any, list[dict[str, Any]]], None]


class KiteRealtimeClient:
    """Wrapper around KiteTicker with reconnect-safe callbacks."""

    def __init__(self, instrument_tokens: list[int], tick_callback: TickCallback) -> None:
        settings = get_settings()
        if KiteTicker is None:
            raise RuntimeError("kiteconnect package not installed. Install `kiteconnect` first.")
        if not settings.kite_api_key or not settings.kite_access_token:
            raise RuntimeError("Missing KITE_API_KEY or KITE_ACCESS_TOKEN in environment.")

        self.settings = settings
        self.instrument_tokens = instrument_tokens
        self._tick_callback = tick_callback
        self._connected = False

        self.ws = KiteTicker(
            api_key=settings.kite_api_key,
            access_token=settings.kite_access_token,
            reconnect=True,
            reconnect_max_tries=50,
            reconnect_max_delay=60,
        )
        self._bind_callbacks()

    @property
    def connected(self) -> bool:
        return self._connected

    def _bind_callbacks(self) -> None:
        def on_connect(ws: Any, _response: Any) -> None:
            mode = getattr(ws, f"MODE_{self.settings.subscribe_mode.upper()}", ws.MODE_FULL)
            ws.subscribe(self.instrument_tokens)
            ws.set_mode(mode, self.instrument_tokens)
            self._connected = True
            logger.info("Kite websocket connected and subscribed to {} instruments", len(self.instrument_tokens))

        def on_close(_ws: Any, code: int, reason: str) -> None:
            self._connected = False
            logger.warning("Kite websocket closed: code={} reason={}", code, reason)

        def on_error(_ws: Any, code: int, reason: str) -> None:
            logger.error("Kite websocket error: code={} reason={}", code, reason)
            if "403" in str(reason):
                logger.error(
                    "Kite WS 403 detected. Usually caused by expired/invalid access token or inactive Kite Connect subscription."
                )

        def on_reconnect(_ws: Any, attempts_count: int) -> None:
            logger.warning("Kite websocket reconnect attempt #{}", attempts_count)

        def on_noreconnect(_ws: Any) -> None:
            self._connected = False
            logger.error("Kite websocket gave up reconnecting")

        self.ws.on_connect = on_connect
        self.ws.on_ticks = self._tick_callback
        self.ws.on_close = on_close
        self.ws.on_error = on_error
        self.ws.on_reconnect = on_reconnect
        self.ws.on_noreconnect = on_noreconnect

    def connect(self) -> None:
        """Start websocket in non-blocking threaded mode."""
        self.ws.connect(threaded=True)

    def disconnect(self) -> None:
        try:
            self.ws.stop()
        finally:
            self._connected = False


class KiteHistoricalClient:
    """Historical candle loader for model training and warm startup."""

    def __init__(self) -> None:
        settings = get_settings()
        if KiteConnect is None:
            raise RuntimeError("kiteconnect package not installed. Install `kiteconnect` first.")
        if not settings.kite_api_key or not settings.kite_access_token:
            raise RuntimeError("Missing KITE_API_KEY or KITE_ACCESS_TOKEN in environment.")

        self.client = KiteConnect(api_key=settings.kite_api_key)
        self.client.set_access_token(settings.kite_access_token)

    @staticmethod
    def _to_kite_interval(timeframe: str) -> str:
        mapping = {
            "1m": "minute",
            "5m": "5minute",
            "15m": "15minute",
            "30m": "30minute",
            "1h": "60minute",
            "1d": "day",
        }
        if timeframe not in mapping:
            raise ValueError(f"Unsupported timeframe: {timeframe}")
        return mapping[timeframe]

    def fetch_candles(
        self,
        instrument_token: int,
        timeframe: str,
        from_dt: datetime,
        to_dt: datetime,
    ) -> pd.DataFrame:
        interval = self._to_kite_interval(timeframe)
        rows = self.client.historical_data(
            instrument_token=instrument_token,
            from_date=from_dt,
            to_date=to_dt,
            interval=interval,
            continuous=False,
            oi=True,
        )

        if not rows:
            return pd.DataFrame()

        frame = pd.DataFrame(rows)
        frame = frame.rename(columns={"date": "candle_start"})
        frame["candle_start"] = pd.to_datetime(frame["candle_start"], utc=True)
        frame["candle_end"] = frame["candle_start"]
        return frame[["candle_start", "candle_end", "open", "high", "low", "close", "volume"]]

    def profile(self) -> dict[str, Any]:
        """Validate session by fetching Kite profile."""
        return self.client.profile()
