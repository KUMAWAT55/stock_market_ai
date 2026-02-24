from __future__ import annotations

import asyncio
from dataclasses import asdict
from datetime import datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

import pandas as pd
from loguru import logger

from compliance.risk_manager import RiskManager
from config.config import get_settings
from data.candle_aggregator import Candle, CandleAggregator
from data.kite_client import KiteHistoricalClient, KiteRealtimeClient
from data.tick_handler import TickHandler
from database.db_manager import CandleRow, DatabaseManager
from features.feature_pipeline import FEATURE_COLUMNS, FeaturePipeline
from models.model_registry import ModelDescriptor, ModelRegistry
from models.predict import predict_signal


class RealtimePredictionEngine:
    """End-to-end realtime prediction loop for 15m and daily signals."""

    def __init__(self) -> None:
        self.settings = get_settings()
        logger.add(self.settings.log_path, rotation="50 MB", retention=5, enqueue=True)

        self.db = DatabaseManager()
        self.registry = ModelRegistry(self.db)
        self.market_tz = ZoneInfo(self.settings.market_timezone)

        token_symbol_map = self.settings.load_symbol_token_map()
        if not token_symbol_map:
            logger.warning(
                "No token map found at {}. Populate JSON to enable live subscriptions.",
                self.settings.symbol_token_map_file,
            )
        self.token_symbol_map = token_symbol_map
        self.symbol_token_map: dict[str, int] = {}
        for token, symbol in token_symbol_map.items():
            self.symbol_token_map.setdefault(symbol.upper(), token)

        self.instrument_tokens = self.settings.instrument_tokens or sorted(token_symbol_map.keys())
        self.tick_handler = TickHandler(token_symbol_map=token_symbol_map)
        self.aggregator = CandleAggregator(history_size=1000)
        self.features = FeaturePipeline(minimum_rows=50)
        self.risk = RiskManager()

        self.kite_client: KiteRealtimeClient | None = None
        self._stop = asyncio.Event()
        self._tasks: list[asyncio.Task[Any]] = []
        self._model_by_timeframe: dict[str, ModelDescriptor] = {}
        self.latest_signal_cache: dict[tuple[str, str], dict[str, Any]] = {}

    async def start(self) -> None:
        if self._tasks and any(not task.done() for task in self._tasks):
            logger.info("Realtime engine already running")
            return

        self._stop.clear()
        self.db.init_schema()
        self._load_models()
        self._warm_from_db()

        if not self.instrument_tokens:
            raise RuntimeError("No instrument tokens configured. Add config/instruments.json or INSTRUMENT_TOKENS env.")

        self.kite_client = KiteRealtimeClient(
            instrument_tokens=self.instrument_tokens,
            tick_callback=self.tick_handler.on_ticks,
        )
        self.kite_client.connect()

        self.db.insert_compliance_audit(
            event_type="engine_start",
            details={
                "instruments": len(self.instrument_tokens),
                "timeframes": list(self.settings.candle_timeframes),
                "execution": "signals_only",
            },
            actor="realtime_engine",
        )

        self._tasks = [
            asyncio.create_task(self._consume_ticks_loop(), name="consume_ticks_loop"),
            asyncio.create_task(self._heartbeat_loop(), name="heartbeat_loop"),
        ]

        logger.info("Realtime engine started")

    async def stop(self) -> None:
        if not self._tasks:
            return

        self._stop.set()
        for task in self._tasks:
            task.cancel()
        await asyncio.gather(*self._tasks, return_exceptions=True)
        self._tasks = []

        if self.kite_client is not None:
            self.kite_client.disconnect()

        self.db.insert_compliance_audit(
            event_type="engine_stop",
            details={"reason": "manual_stop"},
            actor="realtime_engine",
        )
        logger.info("Realtime engine stopped")

    def _load_models(self) -> None:
        self._model_by_timeframe.clear()
        for timeframe in self.settings.model_timeframes:
            descriptor = self.registry.get_active(timeframe)
            if descriptor is None:
                logger.warning("No active model found for timeframe {}", timeframe)
                continue
            self._model_by_timeframe[timeframe] = descriptor
            logger.info(
                "Active model loaded for {}: {} {}",
                timeframe,
                descriptor.model_name,
                descriptor.version,
            )

    def _warm_from_db(self) -> None:
        token_map = self.settings.load_symbol_token_map()
        symbols = sorted(set(token_map.values()))
        warm_candles: list[Candle] = []
        for symbol in symbols:
            for timeframe in self.settings.candle_timeframes:
                frame = self.db.get_recent_candles(symbol=symbol, timeframe=timeframe, limit=400)
                if frame.empty:
                    continue
                for row in frame.to_dict("records"):
                    warm_candles.append(
                        Candle(
                            symbol=symbol,
                            timeframe=timeframe,
                            candle_start=pd.to_datetime(row["candle_start"]).to_pydatetime(),
                            candle_end=pd.to_datetime(row["candle_end"]).to_pydatetime(),
                            open=float(row["open"]),
                            high=float(row["high"]),
                            low=float(row["low"]),
                            close=float(row["close"]),
                            volume=int(row["volume"]),
                            tick_count=int(row["tick_count"]),
                            is_partial=False,
                        )
                    )
        self.aggregator.append_history(warm_candles)
        if warm_candles:
            logger.info("Warm-loaded {} candles from DB", len(warm_candles))

    async def _consume_ticks_loop(self) -> None:
        while not self._stop.is_set():
            try:
                batch = await self.tick_handler.get_batch(max_batch_size=1500, timeout=0.7)
                if not batch:
                    await asyncio.sleep(0.05)
                    continue

                await asyncio.to_thread(
                    self.db.insert_ticks,
                    [asdict(tick) for tick in batch],
                )

                closed_candles: list[Candle] = []
                for tick in batch:
                    closed_candles.extend(self.aggregator.process_tick(tick))

                for candle in closed_candles:
                    await self._handle_candle_close(candle)

            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.exception("Tick processing loop failed: {}", exc)
                await asyncio.sleep(1.0)

    async def _handle_candle_close(self, candle: Candle) -> None:
        await asyncio.to_thread(
            self.db.upsert_candle,
            CandleRow(
                symbol=candle.symbol,
                timeframe=candle.timeframe,
                candle_start=candle.candle_start,
                candle_end=candle.candle_end,
                open=candle.open,
                high=candle.high,
                low=candle.low,
                close=candle.close,
                volume=candle.volume,
                tick_count=candle.tick_count,
                is_partial=candle.is_partial,
            ),
        )

        descriptor = self._model_by_timeframe.get(candle.timeframe)
        if descriptor is None:
            return

        history = self.aggregator.recent_candles(candle.symbol, candle.timeframe, limit=500)
        frame = pd.DataFrame(
            [
                {
                    "symbol": c.symbol,
                    "timeframe": c.timeframe,
                    "candle_start": c.candle_start,
                    "candle_end": c.candle_end,
                    "open": c.open,
                    "high": c.high,
                    "low": c.low,
                    "close": c.close,
                    "volume": c.volume,
                }
                for c in history
            ]
        )
        if frame.empty:
            return

        latest = self.features.latest_feature_row(frame)
        if latest is None:
            return

        feature_columns = descriptor.feature_list or FEATURE_COLUMNS
        result = await asyncio.to_thread(
            predict_signal,
            descriptor,
            latest.features,
            feature_columns,
        )

        target_ts = self._target_ts_from_candle(candle)
        risk_decision = self.risk.evaluate(
            symbol=candle.symbol,
            timeframe=candle.timeframe,
            signal=result.signal,
            confidence=result.confidence,
            last_price=candle.close,
            realized_return=float(latest.features.get("ret_1", 0.0)),
        )

        payload = {
            "symbol": candle.symbol,
            "timeframe": candle.timeframe,
            "prediction_ts": candle.candle_end,
            "target_ts": target_ts,
            "signal": risk_decision.approved_signal,
            "confidence": result.confidence,
            "prob_up": result.prob_up,
            "prob_down": result.prob_down,
            "model_name": descriptor.model_name,
            "model_version": descriptor.version,
            "feature_snapshot": self.settings.serialize_features(latest.features),
            "explainability": result.explainability,
            "risk_snapshot": self.risk.to_payload(risk_decision),
            "compliance_note": "Research signal only. No trade execution.",
            "is_simulated": True,
        }

        await asyncio.to_thread(self.db.insert_prediction, payload)
        if risk_decision.reason != "Approved":
            await asyncio.to_thread(
                self.db.insert_risk_event,
                candle.symbol,
                candle.timeframe,
                "signal_guardrail",
                self.risk.to_payload(risk_decision),
            )

        await asyncio.to_thread(
            self.db.insert_compliance_audit,
            "prediction_generated",
            {
                "model": descriptor.model_name,
                "version": descriptor.version,
                "signal": payload["signal"],
                "confidence": payload["confidence"],
            },
            candle.symbol,
            candle.timeframe,
            "realtime_engine",
        )

        self.latest_signal_cache[(candle.symbol, candle.timeframe)] = payload

    def _target_ts_from_candle(self, candle: Candle) -> datetime:
        timeframe_minutes = self.settings.timeframe_minutes
        if candle.timeframe in timeframe_minutes and candle.timeframe != "1d":
            return candle.candle_end + timedelta(minutes=timeframe_minutes[candle.timeframe])
        next_day = candle.candle_end + timedelta(days=1)
        holidays = self.settings.load_market_holidays()
        while next_day.date().weekday() >= 5 or next_day.date() in holidays:
            next_day += timedelta(days=1)
        return next_day

    def _timeframe_delta(self, timeframe: str) -> timedelta:
        minutes = self.settings.timeframe_minutes.get(timeframe)
        if minutes is None:
            raise ValueError(f"Unsupported timeframe: {timeframe}")
        return timedelta(minutes=minutes)

    async def backfill_historical(self, symbol: str, timeframe: str, days: int = 30) -> dict[str, Any]:
        symbol = symbol.upper().strip()
        if timeframe not in self.settings.candle_timeframes:
            raise ValueError(f"Unsupported timeframe: {timeframe}")

        instrument_token = self.symbol_token_map.get(symbol)
        if instrument_token is None:
            raise ValueError(
                f"Symbol {symbol} not found in instrument map. Update {self.settings.symbol_token_map_file}."
            )

        historical = KiteHistoricalClient()
        end_dt = datetime.now(self.market_tz)
        start_dt = end_dt - timedelta(days=max(1, int(days)))
        frame = await asyncio.to_thread(
            historical.fetch_candles,
            instrument_token,
            timeframe,
            start_dt,
            end_dt,
        )

        if frame.empty:
            return {
                "symbol": symbol,
                "timeframe": timeframe,
                "days": days,
                "inserted": 0,
                "from": start_dt.isoformat(),
                "to": end_dt.isoformat(),
            }

        candle_rows: list[CandleRow] = []
        warm_candles: list[Candle] = []
        delta = self._timeframe_delta(timeframe)
        for row in frame.to_dict("records"):
            candle_start = pd.to_datetime(row["candle_start"]).to_pydatetime()
            if candle_start.tzinfo is None:
                candle_start = candle_start.replace(tzinfo=self.market_tz)
            else:
                candle_start = candle_start.astimezone(self.market_tz)
            candle_end = candle_start + delta
            volume = int(row.get("volume") or 0)
            open_price = float(row.get("open") or 0.0)
            high_price = float(row.get("high") or 0.0)
            low_price = float(row.get("low") or 0.0)
            close_price = float(row.get("close") or 0.0)

            candle_rows.append(
                CandleRow(
                    symbol=symbol,
                    timeframe=timeframe,
                    candle_start=candle_start,
                    candle_end=candle_end,
                    open=open_price,
                    high=high_price,
                    low=low_price,
                    close=close_price,
                    volume=volume,
                    tick_count=0,
                    is_partial=False,
                )
            )
            warm_candles.append(
                Candle(
                    symbol=symbol,
                    timeframe=timeframe,
                    candle_start=candle_start,
                    candle_end=candle_end,
                    open=open_price,
                    high=high_price,
                    low=low_price,
                    close=close_price,
                    volume=volume,
                    tick_count=0,
                    is_partial=False,
                )
            )

        inserted = await asyncio.to_thread(self.db.upsert_candles_bulk, candle_rows)
        self.aggregator.append_history(warm_candles)
        await asyncio.to_thread(
            self.db.insert_compliance_audit,
            "historical_backfill",
            {"symbol": symbol, "timeframe": timeframe, "days": days, "inserted": inserted},
            symbol,
            timeframe,
            "realtime_engine",
        )
        return {
            "symbol": symbol,
            "timeframe": timeframe,
            "days": days,
            "inserted": inserted,
            "from": start_dt.isoformat(),
            "to": end_dt.isoformat(),
        }

    async def _heartbeat_loop(self) -> None:
        while not self._stop.is_set():
            try:
                details = {
                    "queue_dropped_ticks": self.tick_handler.dropped_ticks,
                    "ws_connected": bool(self.kite_client and self.kite_client.connected),
                    "loaded_models": sorted(self._model_by_timeframe.keys()),
                }
                await asyncio.to_thread(self.db.write_heartbeat, "realtime_engine", "running", details)
                await asyncio.sleep(15)
            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.exception("Heartbeat loop error: {}", exc)
                await asyncio.sleep(5)
