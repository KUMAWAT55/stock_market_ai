from __future__ import annotations
"""Realtime orchestration engine from tick ingestion to prediction persistence."""

import asyncio
from dataclasses import asdict
from datetime import date, datetime, time, timedelta
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
from features.feature_pipeline import FeaturePipeline, feature_columns_for_timeframe
from models.model_registry import ModelDescriptor, ModelRegistry
from models.predict import predict_signal


class RealtimePredictionEngine:
    """End-to-end realtime prediction loop for configured multi-timeframe signals."""

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
        # Keep inference warmup low enough for intraday frames while still requiring stable lookback.
        self.features = FeaturePipeline(minimum_rows=30)
        self.risk = RiskManager()

        self.kite_client: KiteRealtimeClient | None = None
        self._stop = asyncio.Event()
        self._tasks: list[asyncio.Task[Any]] = []
        self._model_by_timeframe: dict[str, ModelDescriptor] = {}
        self.latest_signal_cache: dict[tuple[str, str], dict[str, Any]] = {}
        self.latest_price_cache: dict[str, dict[str, Any]] = {}
        self._last_model_refresh_ts: datetime | None = None
        self._last_bootstrap_ts: datetime | None = None

    async def start(self) -> None:
        """Initialize dependencies, start websocket, and launch worker loops."""
        if self._tasks and any(not task.done() for task in self._tasks):
            logger.info("Realtime engine already running")
            return

        self._stop.clear()
        self.db.init_schema()
        self._load_models()
        self._warm_from_db()
        await self._bootstrap_predictions_from_history()
        self._last_bootstrap_ts = datetime.utcnow()

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
        """Stop worker loops and websocket connection cleanly."""
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
        """Load active model descriptors for configured prediction timeframes."""
        self._model_by_timeframe.clear()
        # Use union so stale env vars don't silently exclude trained timeframes.
        candidate_timeframes = sorted(set(self.settings.model_timeframes + self.settings.candle_timeframes))
        for timeframe in candidate_timeframes:
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
        self._last_model_refresh_ts = datetime.utcnow()

    def _warm_from_db(self) -> None:
        """Preload recent candles so indicators/prediction can start immediately."""
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
        """Main worker: drain tick queue, persist ticks, aggregate candles, trigger predictions."""
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
                    self.latest_price_cache[tick.symbol] = {
                        "symbol": tick.symbol,
                        "last_price": float(tick.last_price),
                        "price_ts": tick.ts,
                        "source": "engine_tick",
                    }
                    closed_candles.extend(self.aggregator.process_tick(tick))

                for candle in closed_candles:
                    await self._handle_candle_close(candle)

            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.exception("Tick processing loop failed: {}", exc)
                await asyncio.sleep(1.0)

    async def _handle_candle_close(self, candle: Candle) -> None:
        """Persist closed candle and run prediction+governance for modelled timeframes."""
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

        # Build cross-sectional context for the timeframe so relative features stay meaningful.
        frame = self._build_feature_context_frame(candle.timeframe, limit_per_symbol=260)
        if frame.empty:
            return

        latest = self.features.latest_feature_row(
            frame,
            symbol=candle.symbol,
            timeframe=candle.timeframe,
        )
        if latest is None:
            return

        feature_columns = descriptor.feature_list or feature_columns_for_timeframe(candle.timeframe)
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
        risk_snapshot = self.risk.to_payload(risk_decision)
        risk_snapshot["timeframe_rules"] = self.settings.timeframe_rule_profile(candle.timeframe)

        payload = {
            "symbol": candle.symbol,
            "timeframe": candle.timeframe,
            "prediction_ts": self._prediction_ts_from_candle(candle),
            "target_ts": target_ts,
            "signal": risk_decision.approved_signal,
            "confidence": result.confidence,
            "prob_up": result.prob_up,
            "prob_down": result.prob_down,
            "model_name": descriptor.model_name,
            "model_version": descriptor.version,
            "feature_snapshot": self.settings.serialize_features(latest.features),
            "explainability": result.explainability,
            "risk_snapshot": risk_snapshot,
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

    async def _bootstrap_predictions_from_history(self) -> None:
        """Generate latest predictions from existing candle history at startup."""
        attempts = 0
        generated = 0
        skipped_no_features = 0
        skipped_not_newer = 0
        for timeframe, descriptor in self._model_by_timeframe.items():
            context = self._build_feature_context_frame(timeframe, limit_per_symbol=400)
            if context.empty:
                continue
            symbols = sorted(set(context["symbol"].astype(str)))
            for symbol in symbols:
                attempts += 1
                status = await self._generate_prediction_from_context(
                    symbol=symbol,
                    timeframe=timeframe,
                    descriptor=descriptor,
                    context_frame=context,
                    source_event="bootstrap_history",
                )
                if status == "created":
                    generated += 1
                elif status == "skip_no_features":
                    skipped_no_features += 1
                elif status == "skip_not_newer":
                    skipped_not_newer += 1

        if generated > 0:
            logger.info("Bootstrapped {} latest predictions from historical candles", generated)
        elif attempts > 0:
            logger.debug(
                "Bootstrap checked {} symbol/timeframe pairs with no new inserts (no_features={} not_newer={})",
                attempts,
                skipped_no_features,
                skipped_not_newer,
            )

    async def _generate_prediction_from_context(
        self,
        *,
        symbol: str,
        timeframe: str,
        descriptor: ModelDescriptor,
        context_frame: pd.DataFrame,
        source_event: str,
    ) -> str:
        """Build and persist one prediction using latest available context frame."""
        latest = self.features.latest_feature_row(
            context_frame,
            symbol=symbol,
            timeframe=timeframe,
        )
        if latest is None:
            return "skip_no_features"

        latest_candle_end = pd.to_datetime(latest.latest_candle["candle_end"]).to_pydatetime()

        feature_columns = descriptor.feature_list or feature_columns_for_timeframe(timeframe)
        result = await asyncio.to_thread(
            predict_signal,
            descriptor,
            latest.features,
            feature_columns,
        )

        synthetic_candle = Candle(
            symbol=symbol,
            timeframe=timeframe,
            candle_start=pd.to_datetime(latest.latest_candle["candle_start"]).to_pydatetime(),
            candle_end=latest_candle_end,
            open=float(latest.latest_candle["open"]),
            high=float(latest.latest_candle["high"]),
            low=float(latest.latest_candle["low"]),
            close=float(latest.latest_candle["close"]),
            volume=int(latest.latest_candle["volume"]),
            tick_count=0,
            is_partial=False,
        )
        prediction_ts = self._prediction_ts_from_candle(synthetic_candle)
        recent = await asyncio.to_thread(self.db.list_recent_predictions, symbol, timeframe, 1)
        if recent:
            last_prediction_ts = pd.to_datetime(recent[0].get("prediction_ts"), errors="coerce")
            if pd.notna(last_prediction_ts):
                last_prediction_dt = last_prediction_ts.to_pydatetime()
                if last_prediction_dt.tzinfo is None and prediction_ts.tzinfo is not None:
                    last_prediction_dt = last_prediction_dt.replace(tzinfo=prediction_ts.tzinfo)
                if last_prediction_dt >= prediction_ts:
                    return "skip_not_newer"

        target_ts = self._target_ts_from_candle(synthetic_candle)
        risk_decision = self.risk.evaluate(
            symbol=symbol,
            timeframe=timeframe,
            signal=result.signal,
            confidence=result.confidence,
            last_price=float(latest.latest_candle["close"]),
            realized_return=float(latest.features.get("ret_1", 0.0)),
        )
        risk_snapshot = self.risk.to_payload(risk_decision)
        risk_snapshot["timeframe_rules"] = self.settings.timeframe_rule_profile(timeframe)
        payload = {
            "symbol": symbol,
            "timeframe": timeframe,
            "prediction_ts": prediction_ts,
            "target_ts": target_ts,
            "signal": risk_decision.approved_signal,
            "confidence": result.confidence,
            "prob_up": result.prob_up,
            "prob_down": result.prob_down,
            "model_name": descriptor.model_name,
            "model_version": descriptor.version,
            "feature_snapshot": self.settings.serialize_features(latest.features),
            "explainability": result.explainability,
            "risk_snapshot": risk_snapshot,
            "compliance_note": "Research signal only. No trade execution.",
            "is_simulated": True,
        }
        await asyncio.to_thread(self.db.insert_prediction, payload)
        await asyncio.to_thread(
            self.db.insert_compliance_audit,
            "prediction_generated_bootstrap",
            {
                "model": descriptor.model_name,
                "version": descriptor.version,
                "signal": payload["signal"],
                "confidence": payload["confidence"],
                "source_event": source_event,
            },
            symbol,
            timeframe,
            "realtime_engine",
        )
        self.latest_signal_cache[(symbol, timeframe)] = payload
        return "created"

    def _build_feature_context_frame(self, timeframe: str, limit_per_symbol: int = 260) -> pd.DataFrame:
        """Assemble multi-symbol recent candles for cross-sectional feature computation."""
        rows: list[dict[str, Any]] = []
        for symbol in self.symbol_token_map.keys():
            history = self.aggregator.recent_candles(symbol=symbol, timeframe=timeframe, limit=limit_per_symbol)
            if not history:
                continue
            for c in history:
                rows.append(
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
                )
        if not rows:
            return pd.DataFrame()
        return pd.DataFrame(rows)

    def _to_market_dt(self, value: datetime) -> datetime:
        """Normalize timestamps into configured market timezone."""
        if value.tzinfo is None:
            return value.replace(tzinfo=self.market_tz)
        return value.astimezone(self.market_tz)

    def _market_close_for_day(self, day: date) -> datetime:
        """Return configured market-close timestamp for a trading day."""
        override = self.settings.partial_market_closes.get(day.isoformat())
        if override:
            hour, minute = [int(part) for part in override.split(":", 1)]
            close_time = time(hour=hour, minute=minute)
        else:
            close_time = self.settings.market_close
        return datetime.combine(day, close_time, self.market_tz)

    def _prediction_ts_from_candle(self, candle: Candle) -> datetime:
        """Use session-close timestamps for daily predictions."""
        if candle.timeframe != "1d":
            return candle.candle_end
        anchor_day = self._to_market_dt(candle.candle_start).date()
        return self._market_close_for_day(anchor_day)

    def _target_ts_from_candle(self, candle: Candle) -> datetime:
        """Compute forecast target timestamp, skipping weekends/holidays for daily bars."""
        timeframe_minutes = self.settings.timeframe_minutes
        if candle.timeframe in timeframe_minutes and candle.timeframe != "1d":
            return candle.candle_end + timedelta(minutes=timeframe_minutes[candle.timeframe])
        anchor_day = self._to_market_dt(candle.candle_start).date()
        next_day = anchor_day + timedelta(days=1)
        holidays = self.settings.load_market_holidays()
        while next_day.weekday() >= 5 or next_day in holidays:
            next_day += timedelta(days=1)
        return self._market_close_for_day(next_day)

    def _timeframe_delta(self, timeframe: str) -> timedelta:
        """Convert timeframe label into timedelta for backfilled candle_end computation."""
        minutes = self.settings.timeframe_minutes.get(timeframe)
        if minutes is None:
            raise ValueError(f"Unsupported timeframe: {timeframe}")
        return timedelta(minutes=minutes)

    def _fastest_timeframe(self) -> str:
        """Return shortest configured candle timeframe for live-price fallback."""
        timeframe_minutes = self.settings.timeframe_minutes
        if not timeframe_minutes:
            return "1m"
        return min(timeframe_minutes, key=lambda tf: timeframe_minutes[tf])

    async def backfill_historical(self, symbol: str, timeframe: str, days: int = 30) -> dict[str, Any]:
        """Backfill historical candles from Kite, persist, and warm in-memory history."""
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
            candle_start = self._to_market_dt(candle_start)
            if timeframe == "1d":
                trading_day = candle_start.date()
                candle_end = self._market_close_for_day(trading_day)
            else:
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
        descriptor = self._model_by_timeframe.get(timeframe)
        if descriptor is not None:
            context = self._build_feature_context_frame(timeframe, limit_per_symbol=400)
            if not context.empty:
                pred_status = await self._generate_prediction_from_context(
                    symbol=symbol,
                    timeframe=timeframe,
                    descriptor=descriptor,
                    context_frame=context,
                    source_event="historical_backfill",
                )
            else:
                pred_status = "skip_no_context"
        else:
            pred_status = "skip_no_model"
        await asyncio.to_thread(
            self.db.insert_compliance_audit,
            "historical_backfill",
            {
                "symbol": symbol,
                "timeframe": timeframe,
                "days": days,
                "inserted": inserted,
                "prediction_status": pred_status,
            },
            symbol,
            timeframe,
            "realtime_engine",
        )
        return {
            "symbol": symbol,
            "timeframe": timeframe,
            "days": days,
            "inserted": inserted,
            "prediction_status": pred_status,
            "from": start_dt.isoformat(),
            "to": end_dt.isoformat(),
        }

    async def _heartbeat_loop(self) -> None:
        """Periodic liveness and health telemetry writer."""
        while not self._stop.is_set():
            try:
                # Periodic model refresh enables hot-pickup of newly trained artifacts.
                if (
                    self._last_model_refresh_ts is None
                    or (datetime.utcnow() - self._last_model_refresh_ts).total_seconds() >= 60
                ):
                    self._load_models()

                # Opportunistically fill missing predictions from already available candles.
                if (
                    self._last_bootstrap_ts is None
                    or (datetime.utcnow() - self._last_bootstrap_ts).total_seconds() >= 60
                ):
                    await self._bootstrap_predictions_from_history()
                    self._last_bootstrap_ts = datetime.utcnow()

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

    def status_snapshot(self) -> dict[str, Any]:
        """Return runtime status useful for diagnostics and dashboard checks."""
        return {
            "ws_connected": bool(self.kite_client and self.kite_client.connected),
            "loaded_model_timeframes": sorted(self._model_by_timeframe.keys()),
            "configured_model_timeframes": list(self.settings.model_timeframes),
            "configured_candle_timeframes": list(self.settings.candle_timeframes),
            "dropped_ticks": self.tick_handler.dropped_ticks,
            "last_bootstrap_ts": self._last_bootstrap_ts.isoformat() if self._last_bootstrap_ts else None,
        }

    def latest_price_snapshot(self, symbol: str, timeframe: str | None = None) -> dict[str, Any] | None:
        """Return best-effort latest price snapshot from engine tick/candle caches."""
        resolved_symbol = symbol.upper().strip()
        tick_cached = self.latest_price_cache.get(resolved_symbol)
        if tick_cached:
            return {
                "symbol": resolved_symbol,
                "last_price": float(tick_cached["last_price"]),
                "price_ts": pd.to_datetime(tick_cached["price_ts"]).isoformat(),
                "source": str(tick_cached.get("source", "engine_tick")),
            }

        preferred_tf = timeframe if timeframe in self.settings.candle_timeframes else self._fastest_timeframe()
        recent = self.aggregator.recent_candles(symbol=resolved_symbol, timeframe=preferred_tf, limit=1)
        if not recent:
            return None
        candle = recent[-1]
        return {
            "symbol": resolved_symbol,
            "last_price": float(candle.close),
            "price_ts": candle.candle_end.isoformat(),
            "source": "engine_partial_candle" if candle.is_partial else "engine_candle_close",
        }

    def recent_candles_snapshot(self, symbol: str, timeframe: str, limit: int = 300) -> list[dict[str, Any]]:
        """Return in-memory candle history including the current partial candle."""
        rows: list[dict[str, Any]] = []
        for candle in self.aggregator.recent_candles(symbol=symbol.upper().strip(), timeframe=timeframe, limit=limit):
            rows.append(
                {
                    "symbol": candle.symbol,
                    "timeframe": candle.timeframe,
                    "candle_start": candle.candle_start.isoformat(),
                    "candle_end": candle.candle_end.isoformat(),
                    "open": candle.open,
                    "high": candle.high,
                    "low": candle.low,
                    "close": candle.close,
                    "volume": candle.volume,
                    "tick_count": candle.tick_count,
                    "is_partial": candle.is_partial,
                }
            )
        return rows
