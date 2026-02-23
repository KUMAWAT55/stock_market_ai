from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime
from queue import Empty, Full, Queue
from typing import Any

from loguru import logger


@dataclass(slots=True)
class NormalizedTick:
    instrument_token: int
    symbol: str
    ts: datetime
    last_price: float
    last_traded_quantity: int
    total_buy_quantity: int
    total_sell_quantity: int
    volume: int
    oi: int
    source: str = "kite_ws"


class TickHandler:
    """Thread-safe bridge from Kite websocket callbacks to async consumers."""

    def __init__(self, token_symbol_map: dict[int, str], max_queue_size: int = 50000) -> None:
        self.token_symbol_map = token_symbol_map
        self._queue: Queue[NormalizedTick] = Queue(maxsize=max_queue_size)
        self._dropped_ticks = 0

    @property
    def dropped_ticks(self) -> int:
        return self._dropped_ticks

    def on_ticks(self, _ws: Any, ticks: list[dict[str, Any]]) -> None:
        if not ticks:
            return
        for raw in ticks:
            normalized = self._normalize(raw)
            if normalized is None:
                continue
            try:
                self._queue.put_nowait(normalized)
            except Full:
                self._dropped_ticks += 1
                if self._dropped_ticks % 100 == 0:
                    logger.warning("Dropped {} ticks due to queue saturation", self._dropped_ticks)

    def _normalize(self, tick: dict[str, Any]) -> NormalizedTick | None:
        token = int(tick.get("instrument_token", 0))
        symbol = self.token_symbol_map.get(token)
        if not symbol:
            return None

        ts = tick.get("exchange_timestamp") or tick.get("last_trade_time") or datetime.utcnow()
        if isinstance(ts, str):
            ts = datetime.fromisoformat(ts)

        return NormalizedTick(
            instrument_token=token,
            symbol=symbol,
            ts=ts,
            last_price=float(tick.get("last_price", 0.0)),
            last_traded_quantity=int(tick.get("last_traded_quantity") or 0),
            total_buy_quantity=int(tick.get("total_buy_quantity") or 0),
            total_sell_quantity=int(tick.get("total_sell_quantity") or 0),
            volume=int(tick.get("volume_traded") or tick.get("volume") or 0),
            oi=int(tick.get("oi") or 0),
        )

    async def get_batch(self, max_batch_size: int = 2000, timeout: float = 0.5) -> list[NormalizedTick]:
        def _drain() -> list[NormalizedTick]:
            items: list[NormalizedTick] = []
            try:
                first = self._queue.get(timeout=timeout)
            except Empty:
                return items

            items.append(first)
            while len(items) < max_batch_size:
                try:
                    items.append(self._queue.get_nowait())
                except Empty:
                    break
            return items

        return await asyncio.to_thread(_drain)
