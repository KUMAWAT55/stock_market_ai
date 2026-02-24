from __future__ import annotations
"""Database access layer for ticks, candles, predictions, risk, and audit logs."""

import json
from contextlib import contextmanager
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Iterator

import pandas as pd
from loguru import logger
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from config.config import get_settings


@dataclass(slots=True)
class CandleRow:
    """DB-ready candle row used by upsert operations."""

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


class DatabaseManager:
    """Thin data-access layer for realtime and compliance-safe persistence."""

    def __init__(self, db_url: str | None = None) -> None:
        settings = get_settings()
        self._db_url = db_url or settings.database_url
        self._engine: Engine = create_engine(self._db_url, pool_pre_ping=True, future=True)
        self._session_factory = sessionmaker(bind=self._engine, autocommit=False, autoflush=False)
        self._schema_path = Path(__file__).with_name("schema.sql")

    @contextmanager
    def session_scope(self) -> Iterator[Session]:
        """Transactional session context manager for ORM-style operations."""
        session = self._session_factory()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def init_schema(self) -> None:
        """Create/upgrade required tables from `database/schema.sql`."""
        ddl = self._schema_path.read_text(encoding="utf-8")
        with self._engine.begin() as conn:
            for stmt in [s.strip() for s in ddl.split(";") if s.strip()]:
                conn.execute(text(stmt))
        logger.info("Database schema initialized")

    def insert_ticks(self, rows: list[dict[str, Any]]) -> None:
        """Persist raw normalized ticks for auditability and debugging."""
        if not rows:
            return
        query = text(
            """
            INSERT INTO realtime_ticks (
                instrument_token,
                symbol,
                ts,
                last_price,
                last_traded_quantity,
                total_buy_quantity,
                total_sell_quantity,
                volume,
                oi,
                source
            ) VALUES (
                :instrument_token,
                :symbol,
                :ts,
                :last_price,
                :last_traded_quantity,
                :total_buy_quantity,
                :total_sell_quantity,
                :volume,
                :oi,
                :source
            )
            """
        )
        with self._engine.begin() as conn:
            conn.execute(query, rows)

    def upsert_candle(self, candle: CandleRow) -> None:
        """Insert or update one candle by unique key (symbol, timeframe, candle_start)."""
        query = text(
            """
            INSERT INTO ohlcv_candles (
                symbol,
                timeframe,
                candle_start,
                candle_end,
                open,
                high,
                low,
                close,
                volume,
                tick_count,
                is_partial
            ) VALUES (
                :symbol,
                :timeframe,
                :candle_start,
                :candle_end,
                :open,
                :high,
                :low,
                :close,
                :volume,
                :tick_count,
                :is_partial
            )
            ON CONFLICT (symbol, timeframe, candle_start)
            DO UPDATE SET
                candle_end = EXCLUDED.candle_end,
                open = EXCLUDED.open,
                high = EXCLUDED.high,
                low = EXCLUDED.low,
                close = EXCLUDED.close,
                volume = EXCLUDED.volume,
                tick_count = EXCLUDED.tick_count,
                is_partial = EXCLUDED.is_partial
            """
        )
        with self._engine.begin() as conn:
            conn.execute(query, asdict(candle))

    def upsert_candles_bulk(self, candles: list[CandleRow]) -> int:
        """Bulk upsert candles and return number of processed rows."""
        if not candles:
            return 0
        query = text(
            """
            INSERT INTO ohlcv_candles (
                symbol,
                timeframe,
                candle_start,
                candle_end,
                open,
                high,
                low,
                close,
                volume,
                tick_count,
                is_partial
            ) VALUES (
                :symbol,
                :timeframe,
                :candle_start,
                :candle_end,
                :open,
                :high,
                :low,
                :close,
                :volume,
                :tick_count,
                :is_partial
            )
            ON CONFLICT (symbol, timeframe, candle_start)
            DO UPDATE SET
                candle_end = EXCLUDED.candle_end,
                open = EXCLUDED.open,
                high = EXCLUDED.high,
                low = EXCLUDED.low,
                close = EXCLUDED.close,
                volume = EXCLUDED.volume,
                tick_count = EXCLUDED.tick_count,
                is_partial = EXCLUDED.is_partial
            """
        )
        payload = [asdict(candle) for candle in candles]
        with self._engine.begin() as conn:
            conn.execute(query, payload)
        return len(payload)

    def get_recent_candles(self, symbol: str, timeframe: str, limit: int = 300) -> pd.DataFrame:
        """Fetch recent candles ordered ascending for charting/feature generation."""
        query = text(
            """
            SELECT symbol, timeframe, candle_start, candle_end, open, high, low, close, volume, tick_count
            FROM ohlcv_candles
            WHERE symbol = :symbol
              AND timeframe = :timeframe
            ORDER BY candle_start DESC
            LIMIT :limit
            """
        )
        with self._engine.begin() as conn:
            df = pd.read_sql_query(query, conn, params={"symbol": symbol, "timeframe": timeframe, "limit": limit})
        if df.empty:
            return df
        return df.sort_values("candle_start").reset_index(drop=True)

    def insert_prediction(self, payload: dict[str, Any]) -> None:
        """Persist model output with full feature/risk/explainability snapshots."""
        query = text(
            """
            INSERT INTO prediction_events (
                symbol,
                timeframe,
                prediction_ts,
                target_ts,
                signal,
                confidence,
                prob_up,
                prob_down,
                model_name,
                model_version,
                feature_snapshot,
                explainability,
                risk_snapshot,
                compliance_note,
                is_simulated
            ) VALUES (
                :symbol,
                :timeframe,
                :prediction_ts,
                :target_ts,
                :signal,
                :confidence,
                :prob_up,
                :prob_down,
                :model_name,
                :model_version,
                CAST(:feature_snapshot AS JSONB),
                CAST(:explainability AS JSONB),
                CAST(:risk_snapshot AS JSONB),
                :compliance_note,
                :is_simulated
            )
            """
        )
        row = payload.copy()
        row["feature_snapshot"] = json.dumps(row.get("feature_snapshot", {}), default=str)
        row["explainability"] = json.dumps(row.get("explainability", {}), default=str)
        row["risk_snapshot"] = json.dumps(row.get("risk_snapshot", {}), default=str)
        with self._engine.begin() as conn:
            conn.execute(query, row)

    def insert_risk_event(self, symbol: str, timeframe: str, event_type: str, payload: dict[str, Any]) -> None:
        """Record governance interventions such as throttling or drawdown blocks."""
        query = text(
            """
            INSERT INTO risk_events (symbol, timeframe, event_ts, event_type, payload)
            VALUES (:symbol, :timeframe, :event_ts, :event_type, CAST(:payload AS JSONB))
            """
        )
        with self._engine.begin() as conn:
            conn.execute(
                query,
                {
                    "symbol": symbol,
                    "timeframe": timeframe,
                    "event_ts": datetime.utcnow(),
                    "event_type": event_type,
                    "payload": json.dumps(payload, default=str),
                },
            )

    def insert_compliance_audit(
        self,
        event_type: str,
        details: dict[str, Any],
        symbol: str | None = None,
        timeframe: str | None = None,
        actor: str = "system",
    ) -> None:
        """Append immutable compliance audit event."""
        query = text(
            """
            INSERT INTO compliance_audit_trail (event_ts, event_type, actor, symbol, timeframe, details)
            VALUES (:event_ts, :event_type, :actor, :symbol, :timeframe, CAST(:details AS JSONB))
            """
        )
        with self._engine.begin() as conn:
            conn.execute(
                query,
                {
                    "event_ts": datetime.utcnow(),
                    "event_type": event_type,
                    "actor": actor,
                    "symbol": symbol,
                    "timeframe": timeframe,
                    "details": json.dumps(details, default=str),
                },
            )

    def upsert_model_registry(
        self,
        model_name: str,
        timeframe: str,
        version: str,
        artifact_path: str,
        metrics: dict[str, Any],
        feature_list: list[str],
    ) -> None:
        """Store model metadata and mark a version active for its timeframe."""
        query = text(
            """
            INSERT INTO model_registry (
                model_name,
                timeframe,
                version,
                artifact_path,
                metrics,
                feature_list,
                is_active
            ) VALUES (
                :model_name,
                :timeframe,
                :version,
                :artifact_path,
                CAST(:metrics AS JSONB),
                CAST(:feature_list AS JSONB),
                TRUE
            )
            ON CONFLICT (model_name, timeframe, version)
            DO UPDATE SET
                artifact_path = EXCLUDED.artifact_path,
                metrics = EXCLUDED.metrics,
                feature_list = EXCLUDED.feature_list,
                is_active = TRUE
            """
        )
        with self._engine.begin() as conn:
            conn.execute(
                query,
                {
                    "model_name": model_name,
                    "timeframe": timeframe,
                    "version": version,
                    "artifact_path": artifact_path,
                    "metrics": json.dumps(metrics, default=str),
                    "feature_list": json.dumps(feature_list, default=str),
                },
            )

    def get_active_model(self, timeframe: str) -> dict[str, Any] | None:
        """Return latest active model metadata for a timeframe."""
        query = text(
            """
            SELECT model_name, timeframe, version, artifact_path, metrics, feature_list, created_at
            FROM model_registry
            WHERE timeframe = :timeframe
              AND is_active = TRUE
            ORDER BY created_at DESC
            LIMIT 1
            """
        )
        with self._engine.begin() as conn:
            row = conn.execute(query, {"timeframe": timeframe}).mappings().first()
        return dict(row) if row else None

    def list_recent_predictions(self, symbol: str, timeframe: str, limit: int = 100) -> list[dict[str, Any]]:
        """Return recent prediction history for one symbol/timeframe."""
        query = text(
            """
            SELECT
                symbol,
                timeframe,
                prediction_ts,
                target_ts,
                signal,
                confidence,
                prob_up,
                prob_down,
                model_name,
                model_version,
                feature_snapshot,
                explainability,
                risk_snapshot,
                is_simulated
            FROM prediction_events
            WHERE symbol = :symbol
              AND timeframe = :timeframe
            ORDER BY prediction_ts DESC
            LIMIT :limit
            """
        )
        with self._engine.begin() as conn:
            rows = conn.execute(query, {"symbol": symbol, "timeframe": timeframe, "limit": limit}).mappings().all()
        return [dict(row) for row in rows]

    def get_latest_predictions(self, limit: int = 200) -> list[dict[str, Any]]:
        """Return latest prediction per (symbol, timeframe)."""
        query = text(
            """
            SELECT DISTINCT ON (symbol, timeframe)
                symbol,
                timeframe,
                prediction_ts,
                target_ts,
                signal,
                confidence,
                prob_up,
                prob_down,
                model_name,
                model_version,
                risk_snapshot
            FROM prediction_events
            ORDER BY symbol, timeframe, prediction_ts DESC
            LIMIT :limit
            """
        )
        with self._engine.begin() as conn:
            rows = conn.execute(query, {"limit": limit}).mappings().all()
        return [dict(row) for row in rows]

    def insert_backtest_metrics(
        self,
        symbol: str,
        timeframe: str,
        model_name: str,
        model_version: str,
        metrics: dict[str, Any],
    ) -> None:
        """Store simulated backtest metrics from training pipeline."""
        query = text(
            """
            INSERT INTO simulated_backtest_metrics (
                symbol,
                timeframe,
                model_name,
                model_version,
                run_ts,
                metrics,
                is_simulated
            ) VALUES (
                :symbol,
                :timeframe,
                :model_name,
                :model_version,
                :run_ts,
                CAST(:metrics AS JSONB),
                TRUE
            )
            """
        )
        with self._engine.begin() as conn:
            conn.execute(
                query,
                {
                    "symbol": symbol,
                    "timeframe": timeframe,
                    "model_name": model_name,
                    "model_version": model_version,
                    "run_ts": datetime.utcnow(),
                    "metrics": json.dumps(metrics, default=str),
                },
            )

    def get_latest_backtest_metrics(self, symbol: str, timeframe: str) -> dict[str, Any] | None:
        """Fetch most recent simulated backtest metrics for dashboard display."""
        query = text(
            """
            SELECT model_name, model_version, run_ts, metrics, is_simulated
            FROM simulated_backtest_metrics
            WHERE symbol = :symbol AND timeframe = :timeframe
            ORDER BY run_ts DESC
            LIMIT 1
            """
        )
        with self._engine.begin() as conn:
            row = conn.execute(query, {"symbol": symbol, "timeframe": timeframe}).mappings().first()
        return dict(row) if row else None

    def write_heartbeat(self, service_name: str, status: str, details: dict[str, Any] | None = None) -> None:
        """Write liveness heartbeat for monitoring realtime engine health."""
        query = text(
            """
            INSERT INTO engine_heartbeat (service_name, status, heartbeat_ts, details)
            VALUES (:service_name, :status, :heartbeat_ts, CAST(:details AS JSONB))
            """
        )
        with self._engine.begin() as conn:
            conn.execute(
                query,
                {
                    "service_name": service_name,
                    "status": status,
                    "heartbeat_ts": datetime.utcnow(),
                    "details": json.dumps(details or {}, default=str),
                },
            )
