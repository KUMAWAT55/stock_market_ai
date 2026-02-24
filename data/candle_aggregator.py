from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from threading import RLock
from typing import Iterable
from zoneinfo import ZoneInfo

from config.config import get_settings
from data.tick_handler import NormalizedTick


@dataclass(slots=True)
class Candle:
    symbol: str
    timeframe: str
    candle_start: datetime
    candle_end: datetime
    open: float
    high: float
    low: float
    close: float
    volume: int
    tick_count: int
    is_partial: bool = False


@dataclass(slots=True)
class _CandleState:
    symbol: str
    timeframe: str
    candle_start: datetime
    candle_end: datetime
    open: float
    high: float
    low: float
    close: float
    volume: int
    tick_count: int

    def update(self, price: float, volume: int) -> None:
        self.high = max(self.high, price)
        self.low = min(self.low, price)
        self.close = price
        self.volume += max(volume, 0)
        self.tick_count += 1

    def to_candle(self, is_partial: bool = False) -> Candle:
        return Candle(
            symbol=self.symbol,
            timeframe=self.timeframe,
            candle_start=self.candle_start,
            candle_end=self.candle_end,
            open=self.open,
            high=self.high,
            low=self.low,
            close=self.close,
            volume=self.volume,
            tick_count=self.tick_count,
            is_partial=is_partial,
        )


class CandleAggregator:
    """Aggregates live ticks into configured candles in a thread-safe way."""

    def __init__(self, history_size: int = 500) -> None:
        settings = get_settings()
        self._timeframes = list(settings.candle_timeframes)
        self._tz = ZoneInfo(settings.market_timezone)
        self._market_open = settings.market_open
        self._default_market_close = settings.market_close
        self._partial_market_closes = settings.partial_market_closes
        self._market_holidays = settings.load_market_holidays()
        self._lock = RLock()
        self._states: dict[tuple[str, str], _CandleState] = {}
        self._history: dict[tuple[str, str], deque[Candle]] = defaultdict(lambda: deque(maxlen=history_size))

    def process_tick(self, tick: NormalizedTick) -> list[Candle]:
        """Consume one tick and return closed candles, if any."""
        closed: list[Candle] = []
        tick_ts = self._to_market_tz(tick.ts)

        if not self._is_trading_time(tick_ts):
            return closed

        with self._lock:
            for timeframe in self._timeframes:
                bucket_start, bucket_end = self._bucket_bounds(tick_ts, timeframe)
                key = (tick.symbol, timeframe)
                current = self._states.get(key)

                if current is None:
                    self._states[key] = _CandleState(
                        symbol=tick.symbol,
                        timeframe=timeframe,
                        candle_start=bucket_start,
                        candle_end=bucket_end,
                        open=tick.last_price,
                        high=tick.last_price,
                        low=tick.last_price,
                        close=tick.last_price,
                        volume=tick.last_traded_quantity,
                        tick_count=1,
                    )
                    continue

                if bucket_start > current.candle_start:
                    finalized = current.to_candle(is_partial=False)
                    closed.append(finalized)
                    self._history[key].append(finalized)
                    self._states[key] = _CandleState(
                        symbol=tick.symbol,
                        timeframe=timeframe,
                        candle_start=bucket_start,
                        candle_end=bucket_end,
                        open=tick.last_price,
                        high=tick.last_price,
                        low=tick.last_price,
                        close=tick.last_price,
                        volume=tick.last_traded_quantity,
                        tick_count=1,
                    )
                    continue

                current.update(price=tick.last_price, volume=tick.last_traded_quantity)

        return closed

    def flush_symbol(self, symbol: str) -> list[Candle]:
        """Force-close current candles for a symbol (e.g., engine shutdown)."""
        flushed: list[Candle] = []
        with self._lock:
            keys = [key for key in self._states if key[0] == symbol]
            for key in keys:
                candle = self._states.pop(key).to_candle(is_partial=True)
                self._history[key].append(candle)
                flushed.append(candle)
        return flushed

    def append_history(self, candles: Iterable[Candle]) -> None:
        """Warm startup state from historical candles."""
        with self._lock:
            for candle in candles:
                key = (candle.symbol, candle.timeframe)
                self._history[key].append(candle)

    def recent_candles(self, symbol: str, timeframe: str, limit: int = 300) -> list[Candle]:
        key = (symbol, timeframe)
        with self._lock:
            candles = list(self._history.get(key, deque()))
            state = self._states.get(key)
            if state is not None:
                candles.append(state.to_candle(is_partial=True))
        if limit <= 0:
            return candles
        return candles[-limit:]

    def _to_market_tz(self, ts: datetime) -> datetime:
        if ts.tzinfo is None:
            return ts.replace(tzinfo=self._tz)
        return ts.astimezone(self._tz)

    def _bucket_bounds(self, ts: datetime, timeframe: str) -> tuple[datetime, datetime]:
        if timeframe.endswith("m") and timeframe[:-1].isdigit():
            market_open_dt = datetime.combine(ts.date(), self._market_open, self._tz)
            market_close_dt = datetime.combine(ts.date(), self._close_time_for_day(ts.date()), self._tz)
            minutes_from_open = int((ts - market_open_dt).total_seconds() // 60)
            duration_minutes = int(timeframe[:-1])
            bucket_index = max(minutes_from_open, 0) // duration_minutes
            start = market_open_dt + timedelta(minutes=bucket_index * duration_minutes)
            end = min(start + timedelta(minutes=duration_minutes), market_close_dt)
            return start, end
        if timeframe.endswith("h") and timeframe[:-1].isdigit():
            market_open_dt = datetime.combine(ts.date(), self._market_open, self._tz)
            market_close_dt = datetime.combine(ts.date(), self._close_time_for_day(ts.date()), self._tz)
            minutes_from_open = int((ts - market_open_dt).total_seconds() // 60)
            duration_minutes = int(timeframe[:-1]) * 60
            bucket_index = max(minutes_from_open, 0) // duration_minutes
            start = market_open_dt + timedelta(minutes=bucket_index * duration_minutes)
            end = min(start + timedelta(minutes=duration_minutes), market_close_dt)
            return start, end

        if timeframe == "1d":
            day_start = datetime.combine(ts.date(), self._market_open, self._tz)
            day_end = datetime.combine(ts.date(), self._close_time_for_day(ts.date()), self._tz)
            return day_start, day_end

        raise ValueError(f"Unsupported timeframe for candle aggregation: {timeframe}")

    def _is_trading_time(self, ts: datetime) -> bool:
        trading_day = ts.date()
        if trading_day.weekday() >= 5:
            return False
        if trading_day in self._market_holidays:
            return False

        start = datetime.combine(trading_day, self._market_open, self._tz)
        end = datetime.combine(trading_day, self._close_time_for_day(trading_day), self._tz)
        return start <= ts <= end

    def _close_time_for_day(self, day: date) -> time:
        close_override = self._partial_market_closes.get(day.isoformat())
        if not close_override:
            return self._default_market_close
        hour, minute = close_override.split(":")
        return time(int(hour), int(minute))
