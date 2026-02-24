from __future__ import annotations

import asyncio
import os
from typing import Any

from fastapi import FastAPI, HTTPException, Query
from loguru import logger

from compliance.disclaimer import DISCLAIMER_VERSION, get_disclaimer
from config.config import get_settings
from data.kite_client import KiteHistoricalClient
from database.db_manager import DatabaseManager
from realtime.realtime_engine import RealtimePredictionEngine

try:
    from kiteconnect.exceptions import TokenException
except Exception:  # pragma: no cover
    TokenException = Exception


settings = get_settings()
db = DatabaseManager()

app = FastAPI(
    title="TradeIQ Realtime Signal API",
    version="1.0.0",
    description="SEBI-aware research signal API for Indian market realtime analytics.",
)

_engine: RealtimePredictionEngine | None = None
_engine_lock = asyncio.Lock()


async def _ensure_engine() -> RealtimePredictionEngine:
    global _engine
    if _engine is None:
        _engine = RealtimePredictionEngine()
    return _engine


@app.on_event("startup")
async def startup_event() -> None:
    db.init_schema()
    auto_start = os.getenv("AUTO_START_ENGINE", "true").lower() == "true"
    if not auto_start:
        return

    async with _engine_lock:
        engine = await _ensure_engine()
        try:
            await engine.start()
            logger.info("Realtime engine auto-started")
        except Exception as exc:
            logger.warning("Realtime engine did not auto-start: {}", exc)


@app.on_event("shutdown")
async def shutdown_event() -> None:
    if _engine is None:
        return

    async with _engine_lock:
        if _engine is not None:
            await _engine.stop()


@app.get("/health")
async def health() -> dict[str, Any]:
    return {
        "status": "ok",
        "app": settings.app_name,
        "env": settings.app_env,
        "disclaimer_version": DISCLAIMER_VERSION,
    }


@app.get("/kite/auth-check")
async def kite_auth_check() -> dict[str, Any]:
    try:
        profile = await asyncio.to_thread(KiteHistoricalClient().profile)
        return {
            "status": "ok",
            "user_id": profile.get("user_id"),
            "user_name": profile.get("user_name"),
            "email": profile.get("email"),
            "user_type": profile.get("user_type"),
        }
    except TokenException as exc:
        raise HTTPException(status_code=401, detail=f"Kite auth failed: {exc}") from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Kite auth probe failed: {exc}") from exc


@app.get("/compliance/disclaimer")
async def compliance_disclaimer() -> dict[str, str]:
    disclaimer = get_disclaimer()
    return {
        "version": DISCLAIMER_VERSION,
        "title": disclaimer.title,
        "body": disclaimer.body,
        "risk_disclosure": disclaimer.risk_disclosure,
    }


@app.post("/engine/start")
async def start_engine() -> dict[str, str]:
    async with _engine_lock:
        engine = await _ensure_engine()
        await engine.start()
    return {"status": "started"}


@app.post("/engine/stop")
async def stop_engine() -> dict[str, str]:
    global _engine
    async with _engine_lock:
        if _engine is None:
            return {"status": "not_running"}
        await _engine.stop()
        _engine = None
    return {"status": "stopped"}


@app.get("/signals/latest")
async def latest_signals(limit: int = Query(default=100, ge=1, le=1000)) -> dict[str, Any]:
    rows = db.get_latest_predictions(limit=limit)
    return {"count": len(rows), "rows": rows}


@app.get("/signals/history")
async def signal_history(
    symbol: str,
    timeframe: str = Query(pattern="^(1m|5m|15m|1h|1d)$"),
    limit: int = Query(default=100, ge=1, le=1000),
) -> dict[str, Any]:
    rows = db.list_recent_predictions(symbol=symbol, timeframe=timeframe, limit=limit)
    return {"count": len(rows), "rows": rows}


@app.get("/candles")
async def candles(
    symbol: str,
    timeframe: str = Query(pattern="^(1m|5m|15m|1h|1d)$"),
    limit: int = Query(default=300, ge=10, le=2000),
) -> dict[str, Any]:
    frame = db.get_recent_candles(symbol=symbol, timeframe=timeframe, limit=limit)
    if frame.empty:
        raise HTTPException(status_code=404, detail="No candles found")
    return {
        "count": len(frame),
        "rows": frame.to_dict("records"),
    }


@app.get("/backtest/latest")
async def latest_backtest(symbol: str, timeframe: str = Query(pattern="^(15m|1d)$")) -> dict[str, Any]:
    row = db.get_latest_backtest_metrics(symbol=symbol, timeframe=timeframe)
    if row is None:
        raise HTTPException(status_code=404, detail="No backtest metrics found")
    return row


@app.post("/historical/backfill")
async def historical_backfill(
    symbol: str,
    timeframe: str = Query(pattern="^(1m|5m|15m|1h|1d)$"),
    days: int = Query(default=30, ge=1, le=2000),
) -> dict[str, Any]:
    async with _engine_lock:
        engine = await _ensure_engine()
        try:
            result = await engine.backfill_historical(symbol=symbol, timeframe=timeframe, days=days)
        except TokenException as exc:
            logger.warning("Backfill auth failure: {}", exc)
            raise HTTPException(status_code=401, detail=f"Kite auth failed: {exc}") from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except Exception as exc:
            logger.exception("Backfill failed for {} {} {}d", symbol, timeframe, days)
            raise HTTPException(status_code=500, detail=f"Backfill failed: {exc}") from exc
    return result
