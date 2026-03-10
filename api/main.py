from __future__ import annotations
"""FastAPI surface for dashboard, engine control, and compliance-safe data access."""

import asyncio
import os
from datetime import datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from fastapi import FastAPI, Header, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger
from pydantic import BaseModel
from sqlalchemy.exc import IntegrityError

from api.analytics import (
    backtest_indicator_strategy,
    backtest_prediction_signals,
    build_indicator_heatmap,
    build_model_matrix,
    ordered_timeframes,
)
from api.auth_utils import decode_auth_token, hash_password, issue_auth_token, verify_password
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

_cors_origins = [
    token.strip()
    for token in os.getenv("CORS_ALLOW_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173").split(",")
    if token.strip()
]
_cors_origin_regex = os.getenv(
    "CORS_ALLOW_ORIGIN_REGEX",
    r"^https?://(localhost|127\.0\.0\.1|10(?:\.\d{1,3}){3}|192\.168(?:\.\d{1,3}){2}|172\.(?:1[6-9]|2\d|3[0-1])(?:\.\d{1,3}){2})(:\d+)?$",
).strip() or None
if any(origin == "*" for origin in _cors_origins):
    _cors_origins = ["*"]
    _cors_origin_regex = None
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins or ["*"],
    allow_origin_regex=_cors_origin_regex,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

_engine: RealtimePredictionEngine | None = None
_engine_lock = asyncio.Lock()
_market_tz = ZoneInfo(settings.market_timezone)
_market_holidays = settings.load_market_holidays()
_ensure_jobs: dict[str, dict[str, Any]] = {}
_ensure_tasks: dict[str, asyncio.Task[None]] = {}
_ensure_jobs_lock = asyncio.Lock()
_auto_ensure_loop_task: asyncio.Task[None] | None = None
_db_ready = True
_db_error: str | None = None


class RegisterRequest(BaseModel):
    username: str
    email: str
    password: str
    full_name: str | None = None


class LoginRequest(BaseModel):
    identifier: str
    password: str


class ContactRequest(BaseModel):
    full_name: str
    email: str
    subject: str
    message: str


async def _ensure_engine() -> RealtimePredictionEngine:
    """Lazily initialize singleton   engine."""
    global _engine
    if _engine is None:
        _engine = RealtimePredictionEngine()
    return _engine


def _require_db_ready() -> None:
    """Fail fast with a clear error when database is unavailable."""
    if _db_ready:
        return
    raise HTTPException(
        status_code=503,
        detail={
            "message": "Database unavailable. API running in degraded mode.",
            "db_error": _db_error,
        },
    )


def _to_market_dt(value: Any) -> datetime | None:
    """Normalize datetime-like values into configured market timezone."""
    if value is None:
        return None
    if isinstance(value, datetime):
        dt = value
    else:
        try:
            dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        except Exception:
            return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=ZoneInfo("UTC")).astimezone(_market_tz)
    return dt.astimezone(_market_tz)


def _auto_sync_policy(timeframe: str) -> dict[str, int]:
    return {
        "days": settings.auto_backfill_days(timeframe),
        "min_candles": settings.auto_backfill_min_candles(timeframe),
        "freshness_minutes": settings.auto_backfill_freshness_minutes(timeframe),
    }


def _market_close_for_day(now: datetime) -> datetime:
    override = settings.partial_market_closes.get(now.date().isoformat())
    if override:
        hour, minute = [int(part) for part in override.split(":", 1)]
    else:
        hour, minute = settings.market_close.hour, settings.market_close.minute
    return now.replace(hour=hour, minute=minute, second=0, microsecond=0)


def _latest_expected_trading_day(now: datetime) -> datetime.date:
    day = now.date()
    while day.weekday() >= 5 or day in _market_holidays:
        day = day - timedelta(days=1)
    return day


def _expected_trading_day_for_timeframe(now: datetime, timeframe: str) -> datetime.date:
    if timeframe != "1d":
        return _latest_expected_trading_day(now)

    market_open_dt = now.replace(
        hour=settings.market_open.hour,
        minute=settings.market_open.minute,
        second=0,
        microsecond=0,
    )
    market_close_dt = _market_close_for_day(now)
    if now.weekday() < 5 and now.date() not in _market_holidays and market_open_dt <= now < market_close_dt:
        return _latest_expected_trading_day(now - timedelta(days=1))
    return _latest_expected_trading_day(now)


def _ensure_job_key(symbol: str, timeframe: str) -> str:
    return f"{symbol}:{timeframe}"


def _json_safe(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    return value


def _parse_timeframes(value: str, fallback: list[str]) -> list[str]:
    requested = [token.strip().lower() for token in value.split(",") if token.strip()]
    if not requested:
        requested = list(fallback)
    return ordered_timeframes(requested)


def _best_effort_live_price(symbol: str, timeframe: str) -> dict[str, Any] | None:
    if _engine is not None:
        payload = _engine.latest_price_snapshot(symbol=symbol, timeframe=timeframe)
        if payload:
            return payload

    if not _db_ready:
        return None

    tick = db.get_latest_tick(symbol)
    if tick is not None:
        tick_ts = _to_market_dt(tick.get("ts"))
        return {
            "symbol": symbol,
            "last_price": float(tick.get("last_price") or 0.0),
            "price_ts": tick_ts.isoformat() if tick_ts else None,
            "source": "db_tick",
        }

    candle = db.get_latest_candle_close(symbol=symbol, timeframe=timeframe)
    if candle is not None:
        candle_ts = _to_market_dt(candle.get("candle_end"))
        return {
            "symbol": symbol,
            "last_price": float(candle.get("close") or 0.0),
            "price_ts": candle_ts.isoformat() if candle_ts else None,
            "source": "db_candle_partial" if bool(candle.get("is_partial")) else "db_candle_close",
        }
    return None


def _extract_bearer_token(authorization: str | None) -> str | None:
    if not authorization:
        return None
    token = authorization.strip()
    if not token:
        return None
    parts = token.split(" ", 1)
    if len(parts) == 2 and parts[0].lower() == "bearer":
        return parts[1].strip() or None
    return token


def _require_auth_user(authorization: str | None) -> dict[str, Any]:
    token = _extract_bearer_token(authorization)
    if not token:
        raise HTTPException(status_code=401, detail="Missing auth token")
    claims = decode_auth_token(token)
    if not claims:
        raise HTTPException(status_code=401, detail="Invalid or expired auth token")

    user_id = int(claims.get("uid") or 0)
    user = db.get_app_user_by_id(user_id)
    if not user or not bool(user.get("is_active")):
        raise HTTPException(status_code=401, detail="User not found or inactive")
    return {
        "id": int(user["id"]),
        "username": str(user["username"]),
        "email": str(user["email"]),
        "full_name": str(user.get("full_name") or ""),
    }


async def _run_ensure_job(
    *,
    key: str,
    symbol: str,
    timeframe: str,
    policy: dict[str, int],
    reasons: list[str],
    before: dict[str, Any],
) -> None:
    async with _ensure_jobs_lock:
        _ensure_jobs[key] = {
            "symbol": symbol,
            "timeframe": timeframe,
            "status": "running",
            "queued_at": _ensure_jobs.get(key, {}).get("queued_at", datetime.utcnow().isoformat()),
            "started_at": datetime.utcnow().isoformat(),
            "finished_at": None,
            "policy": _json_safe(policy),
            "reasons": list(reasons),
            "before": _json_safe(before),
            "after": None,
            "backfill": None,
            "error": None,
        }

    try:
        async with _engine_lock:
            engine = await _ensure_engine()
            backfill = await engine.backfill_historical(
                symbol=symbol,
                timeframe=timeframe,
                days=int(policy["days"]),
            )
        after = db.get_candle_stats(symbol=symbol, timeframe=timeframe)
        async with _ensure_jobs_lock:
            job = _ensure_jobs.get(key, {})
            job.update(
                {
                    "status": "succeeded",
                    "finished_at": datetime.utcnow().isoformat(),
                    "after": _json_safe(after),
                    "backfill": _json_safe(backfill),
                    "error": None,
                }
            )
            _ensure_jobs[key] = job
    except Exception as exc:
        logger.exception("Async ensure failed for {} {}", symbol, timeframe)
        async with _ensure_jobs_lock:
            job = _ensure_jobs.get(key, {})
            job.update(
                {
                    "status": "failed",
                    "finished_at": datetime.utcnow().isoformat(),
                    "error": str(exc),
                }
            )
            _ensure_jobs[key] = job
    finally:
        async with _ensure_jobs_lock:
            task = _ensure_tasks.get(key)
            if task is asyncio.current_task():
                _ensure_tasks.pop(key, None)


async def _ensure_job_snapshot(symbol: str, timeframe: str) -> dict[str, Any] | None:
    key = _ensure_job_key(symbol, timeframe)
    async with _ensure_jobs_lock:
        task = _ensure_tasks.get(key)
        if task is not None and task.done():
            _ensure_tasks.pop(key, None)
        job = _ensure_jobs.get(key)
        return _json_safe(job) if job is not None else None


def _backfill_needed(stats: dict[str, Any], timeframe: str) -> tuple[bool, list[str]]:
    policy = _auto_sync_policy(timeframe)
    reasons: list[str] = []
    candle_count = int(stats.get("candle_count") or 0)
    latest = _to_market_dt(stats.get("latest_candle_end"))
    if candle_count < policy["min_candles"]:
        reasons.append(f"candle_count<{policy['min_candles']}")
    if latest is None:
        reasons.append("no_latest_candle")
    else:
        now = datetime.now(_market_tz)
        age_minutes = (now - latest).total_seconds() / 60.0
        expected_day = _expected_trading_day_for_timeframe(now, timeframe)
        if latest.date() < expected_day:
            reasons.append(f"stale_day<{expected_day.isoformat()}")
        elif timeframe != "1d":
            market_open_dt = now.replace(
                hour=settings.market_open.hour,
                minute=settings.market_open.minute,
                second=0,
                microsecond=0,
            )
            market_close_dt = _market_close_for_day(now)
            session_active = (
                now.weekday() < 5
                and now.date() not in _market_holidays
                and market_open_dt <= now <= market_close_dt
            )
            if session_active and age_minutes > float(policy["freshness_minutes"]):
                reasons.append(f"stale>{policy['freshness_minutes']}m")
    return len(reasons) > 0, reasons


async def _queue_ensure_if_needed(
    *,
    symbol: str,
    timeframe: str,
    wait: bool = False,
    trigger: str = "api",
) -> dict[str, Any]:
    symbol = symbol.upper().strip()
    before = db.get_candle_stats(symbol=symbol, timeframe=timeframe)
    needs_backfill, reasons = _backfill_needed(before, timeframe)
    policy = _auto_sync_policy(timeframe)

    if not needs_backfill:
        return {
            "symbol": symbol,
            "timeframe": timeframe,
            "needs_backfill": False,
            "queued_new": False,
            "reasons": [],
            "policy": _json_safe(policy),
            "before": _json_safe(before),
            "task": await _ensure_job_snapshot(symbol, timeframe),
        }

    key = _ensure_job_key(symbol, timeframe)
    task_to_wait: asyncio.Task[None] | None = None
    queued_new = False

    async with _ensure_jobs_lock:
        existing = _ensure_tasks.get(key)
        if existing is not None and existing.done():
            _ensure_tasks.pop(key, None)
            existing = None

        if existing is None:
            _ensure_jobs[key] = {
                "symbol": symbol,
                "timeframe": timeframe,
                "status": "queued",
                "queued_at": datetime.utcnow().isoformat(),
                "started_at": None,
                "finished_at": None,
                "policy": _json_safe(policy),
                "reasons": list(reasons),
                "before": _json_safe(before),
                "after": None,
                "backfill": None,
                "error": None,
                "trigger": trigger,
            }
            existing = asyncio.create_task(
                _run_ensure_job(
                    key=key,
                    symbol=symbol,
                    timeframe=timeframe,
                    policy=policy,
                    reasons=reasons,
                    before=before,
                ),
                name=f"historical_ensure:{symbol}:{timeframe}",
            )
            _ensure_tasks[key] = existing
            queued_new = True
        if wait:
            task_to_wait = existing

    if task_to_wait is not None:
        await task_to_wait

    return {
        "symbol": symbol,
        "timeframe": timeframe,
        "needs_backfill": True,
        "queued_new": queued_new,
        "reasons": list(reasons),
        "policy": _json_safe(policy),
        "before": _json_safe(before),
        "task": await _ensure_job_snapshot(symbol, timeframe),
    }


async def _auto_historical_ensure_loop() -> None:
    interval = settings.auto_ensure_interval_seconds()
    max_jobs = settings.auto_ensure_max_jobs_per_sweep()
    logger.info(
        "Auto historical ensure loop enabled interval={}s max_jobs_per_sweep={}",
        interval,
        max_jobs,
    )
    try:
        while True:
            try:
                if not _db_ready:
                    await asyncio.sleep(interval)
                    continue

                token_map = settings.load_symbol_token_map()
                symbols = sorted(set(str(symbol).upper().strip() for symbol in token_map.values() if symbol))
                queued_count = 0

                for symbol in symbols:
                    for timeframe in settings.candle_timeframes:
                        result = await _queue_ensure_if_needed(
                            symbol=symbol,
                            timeframe=timeframe,
                            trigger="auto_sweep",
                        )
                        if result["queued_new"]:
                            queued_count += 1
                            if queued_count >= max_jobs:
                                break
                    if queued_count >= max_jobs:
                        break

                if queued_count > 0:
                    logger.info("Auto historical ensure queued {} job(s) this sweep", queued_count)
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("Auto historical ensure sweep failed")

            await asyncio.sleep(interval)
    except asyncio.CancelledError:
        logger.info("Auto historical ensure loop stopped")
        raise


@app.on_event("startup")
async def startup_event() -> None:
    """Initialize schema and optionally auto-start realtime engine on app boot."""
    global _db_ready, _db_error, _auto_ensure_loop_task
    try:
        db.init_schema()
        _db_ready = True
        _db_error = None
    except Exception as exc:
        _db_ready = False
        _db_error = str(exc)
        logger.exception("Database init failed; API continuing in degraded mode: {}", exc)

    auto_start = os.getenv("AUTO_START_ENGINE", "true").lower() == "true"
    if auto_start and _db_ready:
        async with _engine_lock:
            engine = await _ensure_engine()
            try:
                await engine.start()
                logger.info("Realtime engine auto-started")
            except Exception as exc:
                logger.warning("Realtime engine did not auto-start: {}", exc)

    if settings.auto_historical_ensure_enabled and _db_ready:
        if _auto_ensure_loop_task is None or _auto_ensure_loop_task.done():
            _auto_ensure_loop_task = asyncio.create_task(
                _auto_historical_ensure_loop(),
                name="auto_historical_ensure_loop",
            )


@app.on_event("shutdown")
async def shutdown_event() -> None:
    """Stop realtime engine gracefully on API shutdown."""
    global _auto_ensure_loop_task
    if _auto_ensure_loop_task is not None:
        _auto_ensure_loop_task.cancel()
        try:
            await _auto_ensure_loop_task
        except asyncio.CancelledError:
            pass
        _auto_ensure_loop_task = None

    if _engine is None:
        return

    async with _engine_lock:
        if _engine is not None:
            await _engine.stop()


@app.get("/health")
async def health() -> dict[str, Any]:
    """Basic health endpoint for service checks."""
    return {
        "status": "ok" if _db_ready else "degraded",
        "app": settings.app_name,
        "env": settings.app_env,
        "disclaimer_version": DISCLAIMER_VERSION,
        "db_ready": _db_ready,
        "db_error": _db_error,
    }


@app.get("/market/symbols")
async def market_symbols() -> dict[str, Any]:
    """Expose configured symbol universe for dashboard selectors/watchlists."""
    token_map = settings.load_symbol_token_map()
    symbols = sorted(set(str(symbol).upper() for symbol in token_map.values()))
    return {"count": len(symbols), "symbols": symbols}


@app.post("/auth/register")
async def auth_register(payload: RegisterRequest) -> dict[str, Any]:
    """Create app user and return signed auth token."""
    _require_db_ready()
    username = payload.username.strip().lower()
    email = payload.email.strip().lower()
    password = payload.password
    full_name = (payload.full_name or "").strip()

    if len(username) < 3:
        raise HTTPException(status_code=400, detail="Username must be at least 3 characters")
    if "@" not in email or "." not in email.split("@")[-1]:
        raise HTTPException(status_code=400, detail="Invalid email address")
    if len(password) < 8:
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters")

    if db.get_app_user_by_identifier(username):
        raise HTTPException(status_code=409, detail="Username already exists")
    if db.get_app_user_by_identifier(email):
        raise HTTPException(status_code=409, detail="Email already exists")

    try:
        user = db.create_app_user(
            username=username,
            email=email,
            password_hash=hash_password(password),
            full_name=full_name or None,
        )
    except IntegrityError as exc:
        raise HTTPException(status_code=409, detail="Username or email already exists") from exc
    except Exception as exc:
        logger.exception("Failed to register user")
        raise HTTPException(status_code=500, detail=f"Registration failed: {exc}") from exc

    token = issue_auth_token(
        user_id=int(user["id"]),
        username=str(user["username"]),
        email=str(user["email"]),
    )
    return {
        "token": token,
        "user": {
            "id": int(user["id"]),
            "username": str(user["username"]),
            "email": str(user["email"]),
            "full_name": str(user.get("full_name") or ""),
        },
    }


@app.post("/auth/login")
async def auth_login(payload: LoginRequest) -> dict[str, Any]:
    """Authenticate by username/email and return signed auth token."""
    _require_db_ready()
    identifier = payload.identifier.strip().lower()
    if not identifier or not payload.password:
        raise HTTPException(status_code=400, detail="Identifier and password required")

    user = db.get_app_user_by_identifier(identifier)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    if not bool(user.get("is_active")):
        raise HTTPException(status_code=403, detail="User is inactive")

    if not verify_password(payload.password, str(user.get("password_hash") or "")):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    token = issue_auth_token(
        user_id=int(user["id"]),
        username=str(user["username"]),
        email=str(user["email"]),
    )
    return {
        "token": token,
        "user": {
            "id": int(user["id"]),
            "username": str(user["username"]),
            "email": str(user["email"]),
            "full_name": str(user.get("full_name") or ""),
        },
    }


@app.get("/auth/me")
async def auth_me(authorization: str | None = Header(default=None)) -> dict[str, Any]:
    """Resolve currently authenticated user from Bearer token."""
    user = _require_auth_user(authorization)
    return {"user": user}


@app.post("/public/contact")
async def public_contact(payload: ContactRequest) -> dict[str, str]:
    """Store public contact-us form submission."""
    _require_db_ready()
    full_name = payload.full_name.strip()
    email = payload.email.strip().lower()
    subject = payload.subject.strip()
    message = payload.message.strip()

    if len(full_name) < 2:
        raise HTTPException(status_code=400, detail="Full name is too short")
    if "@" not in email or "." not in email.split("@")[-1]:
        raise HTTPException(status_code=400, detail="Invalid email address")
    if len(subject) < 3:
        raise HTTPException(status_code=400, detail="Subject is too short")
    if len(message) < 10:
        raise HTTPException(status_code=400, detail="Message is too short")

    db.insert_contact_message(
        full_name=full_name,
        email=email,
        subject=subject,
        message=message,
        source="webapp",
    )
    return {"status": "received"}


@app.get("/kite/auth-check")
async def kite_auth_check() -> dict[str, Any]:
    """Validate current Kite credentials via profile probe."""
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
    """Expose disclaimer text for UI clients."""
    disclaimer = get_disclaimer()
    return {
        "version": DISCLAIMER_VERSION,
        "title": disclaimer.title,
        "body": disclaimer.body,
        "risk_disclosure": disclaimer.risk_disclosure,
    }


@app.post("/engine/start")
async def start_engine() -> dict[str, str]:
    """Manually start realtime engine."""
    _require_db_ready()
    async with _engine_lock:
        engine = await _ensure_engine()
        await engine.start()
    return {"status": "started"}


@app.post("/engine/stop")
async def stop_engine() -> dict[str, str]:
    """Manually stop realtime engine."""
    global _engine
    async with _engine_lock:
        if _engine is None:
            return {"status": "not_running"}
        await _engine.stop()
        _engine = None
    return {"status": "stopped"}


@app.get("/engine/status")
async def engine_status() -> dict[str, Any]:
    """Expose runtime engine status including loaded model timeframes."""
    if _engine is None:
        return {"running": False, "details": None}
    return {"running": True, "details": _engine.status_snapshot()}


@app.get("/rules/timeframe")
async def timeframe_rules(timeframe: str = Query(pattern="^(1m|5m|15m|1h|1d)$")) -> dict[str, Any]:
    """Expose active signal/risk/backfill profile for one timeframe."""
    return {
        "timeframe": timeframe,
        "rules": settings.timeframe_rule_profile(timeframe),
    }


@app.get("/signals/latest")
async def latest_signals(limit: int = Query(default=100, ge=1, le=1000)) -> dict[str, Any]:
    """Return latest signal snapshot across symbols/timeframes."""
    _require_db_ready()
    rows = db.get_latest_predictions(limit=limit)
    return {"count": len(rows), "rows": rows}


@app.get("/signals/history")
async def signal_history(
    symbol: str,
    timeframe: str = Query(pattern="^(1m|5m|15m|1h|1d)$"),
    limit: int = Query(default=100, ge=1, le=1000),
) -> dict[str, Any]:
    """Return historical prediction records for one symbol/timeframe."""
    _require_db_ready()
    rows = db.list_recent_predictions(symbol=symbol.upper(), timeframe=timeframe, limit=limit)
    return {"count": len(rows), "rows": rows}


@app.get("/signals/probability-vector")
async def probability_vector(
    symbol: str,
    timeframes: str = Query(default="1m,5m,15m,1h,1d"),
) -> dict[str, Any]:
    """Return latest per-timeframe probabilities for one symbol (P_1m..P_1d)."""
    _require_db_ready()
    requested = [token.strip() for token in timeframes.split(",") if token.strip()]
    rows = db.get_probability_vector(symbol=symbol.upper(), timeframes=requested)
    payload: dict[str, Any] = {"symbol": symbol.upper(), "probabilities": {}}
    for tf in requested:
        latest = rows.get(tf)
        if latest is None:
            payload["probabilities"][tf] = None
            continue
        payload["probabilities"][tf] = {
            "prob_up": latest.get("prob_up"),
            "prob_down": latest.get("prob_down"),
            "signal": latest.get("signal"),
            "confidence": latest.get("confidence"),
            "prediction_ts": latest.get("prediction_ts"),
            "target_ts": latest.get("target_ts"),
            "model_version": latest.get("model_version"),
        }
    return payload


@app.get("/candles")
async def candles(
    symbol: str,
    timeframe: str = Query(pattern="^(1m|5m|15m|1h|1d)$"),
    limit: int = Query(default=300, ge=10, le=2000),
) -> dict[str, Any]:
    """Return recent candles for dashboard charting."""
    symbol = symbol.upper()
    if _engine is not None:
        live_rows = _engine.recent_candles_snapshot(symbol=symbol, timeframe=timeframe, limit=limit)
        if live_rows:
            return {
                "count": len(live_rows),
                "rows": live_rows,
                "source": "engine_live",
            }

    _require_db_ready()
    frame = db.get_recent_candles(symbol=symbol, timeframe=timeframe, limit=limit)
    if frame.empty:
        raise HTTPException(status_code=404, detail="No candles found")
    return {
        "count": len(frame),
        "rows": frame.to_dict("records"),
        "source": "db_history",
    }


@app.get("/price/live")
async def live_price(
    symbol: str,
    timeframe: str = Query(default="1m", pattern="^(1m|5m|15m|1h|1d)$"),
) -> dict[str, Any]:
    """Return best-effort live/latest price for a symbol."""
    symbol = symbol.upper().strip()

    if _engine is not None:
        payload = _engine.latest_price_snapshot(symbol=symbol, timeframe=timeframe)
        if payload:
            return payload

    if not _db_ready:
        raise HTTPException(
            status_code=503,
            detail={
                "message": "Live price unavailable: DB not ready and no engine snapshot.",
                "db_error": _db_error,
            },
        )

    tick = db.get_latest_tick(symbol)
    if tick is not None:
        tick_ts = _to_market_dt(tick.get("ts"))
        return {
            "symbol": symbol,
            "last_price": float(tick.get("last_price") or 0.0),
            "price_ts": tick_ts.isoformat() if tick_ts else None,
            "source": "db_tick",
        }

    candle = db.get_latest_candle_close(symbol=symbol, timeframe=timeframe)
    if candle is not None:
        candle_ts = _to_market_dt(candle.get("candle_end"))
        return {
            "symbol": symbol,
            "last_price": float(candle.get("close") or 0.0),
            "price_ts": candle_ts.isoformat() if candle_ts else None,
            "source": "db_candle_partial" if bool(candle.get("is_partial")) else "db_candle_close",
        }

    raise HTTPException(status_code=404, detail="No live price available")


@app.get("/backtest/latest")
async def latest_backtest(symbol: str, timeframe: str = Query(pattern="^(1m|5m|15m|1h|1d)$")) -> dict[str, Any]:
    """Fetch latest simulated backtest metrics."""
    _require_db_ready()
    requested_symbol = symbol.upper()
    source_symbol = requested_symbol
    row = db.get_latest_backtest_metrics(symbol=requested_symbol, timeframe=timeframe)
    if row is None and requested_symbol != "GLOBAL":
        source_symbol = "GLOBAL"
        row = db.get_latest_backtest_metrics(symbol=source_symbol, timeframe=timeframe)
    if row is None:
        raise HTTPException(status_code=404, detail="No backtest metrics found")
    row["requested_symbol"] = requested_symbol
    row["source_symbol"] = source_symbol
    row["fallback_used"] = source_symbol != requested_symbol
    return row


@app.get("/analytics/indicator-heatmap")
async def indicator_heatmap(
    symbol: str,
    timeframes: str = Query(default="1m,5m,15m,1h,1d"),
    indicators: str = Query(default="ema_trend,rsi_regime,macd_impulse,bb_position,volume_impulse,candle_pressure"),
    candle_limit: int = Query(default=260, ge=80, le=2000),
) -> dict[str, Any]:
    """Return bullish/bearish indicator heatmap for selected symbol and timeframes."""
    _require_db_ready()
    symbol = symbol.upper().strip()
    resolved_timeframes = _parse_timeframes(timeframes, settings.candle_timeframes)
    requested_indicators = [token.strip() for token in indicators.split(",") if token.strip()]
    return build_indicator_heatmap(
        db,
        symbol=symbol,
        timeframes=resolved_timeframes,
        candle_limit=int(candle_limit),
        indicators=requested_indicators,
    )


@app.get("/analytics/model-matrix")
async def model_matrix(
    symbol: str,
    timeframes: str = Query(default="1m,5m,15m,1h,1d"),
) -> dict[str, Any]:
    """Return per-timeframe model predictions and consensus for one symbol."""
    _require_db_ready()
    symbol = symbol.upper().strip()
    resolved_timeframes = _parse_timeframes(timeframes, settings.model_timeframes)
    return build_model_matrix(db, symbol=symbol, timeframes=resolved_timeframes)


@app.get("/analytics/backtest/model")
async def model_backtest(
    symbol: str,
    timeframe: str = Query(pattern="^(1m|5m|15m|1h|1d)$"),
    limit: int = Query(default=500, ge=100, le=5000),
) -> dict[str, Any]:
    """Run intraday backtest from model prediction events using realized returns."""
    _require_db_ready()
    return backtest_prediction_signals(
        db,
        symbol=symbol.upper().strip(),
        timeframe=timeframe,
        limit=int(limit),
    )


@app.get("/analytics/backtest/strategy")
async def strategy_backtest(
    symbol: str,
    timeframe: str = Query(pattern="^(1m|5m|15m|1h|1d)$"),
    strategy: str = Query(default="ema_trend", pattern="^(ema_trend|rsi_reversal|macd_impulse)$"),
    candle_limit: int = Query(default=700, ge=250, le=5000),
    cost_bps: float = Query(default=2.0, ge=0.0, le=50.0),
) -> dict[str, Any]:
    """Run fast rule-based strategy backtest for Streak-like strategy exploration."""
    _require_db_ready()
    return backtest_indicator_strategy(
        db,
        symbol=symbol.upper().strip(),
        timeframe=timeframe,
        strategy=strategy,
        candle_limit=int(candle_limit),
        cost_bps=float(cost_bps),
    )


@app.get("/scanner/intraday")
async def intraday_scanner(
    timeframe: str = Query(default="5m", pattern="^(1m|5m|15m|1h|1d)$"),
    signal: str = Query(default="ALL", pattern="^(ALL|BUY|SELL|HOLD)$"),
    min_confidence: float = Query(default=0.60, ge=0.0, le=1.0),
    limit: int = Query(default=50, ge=5, le=500),
) -> dict[str, Any]:
    """Return ranked intraday opportunities similar to strategy scanners."""
    _require_db_ready()
    requested_signal = signal.upper()
    rows = db.get_latest_predictions(limit=3000)

    out: list[dict[str, Any]] = []
    for row in rows:
        if str(row.get("timeframe")) != timeframe:
            continue
        risk = row.get("risk_snapshot") if isinstance(row.get("risk_snapshot"), dict) else {}
        approved_signal = str(risk.get("approved_signal") or row.get("signal") or "HOLD").upper()
        confidence = float(row.get("confidence") or 0.0)
        if confidence < float(min_confidence):
            continue
        if requested_signal != "ALL" and approved_signal != requested_signal:
            continue
        out.append(
            {
                "symbol": row.get("symbol"),
                "timeframe": row.get("timeframe"),
                "signal": row.get("signal"),
                "approved_signal": approved_signal,
                "confidence": round(confidence, 4),
                "prob_up": round(float(row.get("prob_up") or 0.0), 4),
                "prob_down": round(float(row.get("prob_down") or 0.0), 4),
                "model_name": row.get("model_name"),
                "model_version": row.get("model_version"),
                "prediction_ts": row.get("prediction_ts"),
                "target_ts": row.get("target_ts"),
                "risk_reason": risk.get("reason"),
            }
        )

    out = sorted(out, key=lambda item: float(item.get("confidence") or 0.0), reverse=True)[: int(limit)]
    return {
        "timeframe": timeframe,
        "signal": requested_signal,
        "min_confidence": min_confidence,
        "count": len(out),
        "rows": out,
    }


@app.get("/dashboard/snapshot")
async def dashboard_snapshot(
    symbol: str,
    timeframe: str = Query(default="15m", pattern="^(1m|5m|15m|1h|1d)$"),
    candle_limit: int = Query(default=300, ge=80, le=2000),
    history_limit: int = Query(default=200, ge=20, le=1000),
    matrix_timeframes: str = Query(default="1m,5m,15m,1h,1d"),
    heatmap_indicators: str = Query(default="ema_trend,rsi_regime,macd_impulse,bb_position,volume_impulse,candle_pressure"),
) -> dict[str, Any]:
    """Return consolidated payload optimized for React dashboard refresh loops."""
    _require_db_ready()
    symbol = symbol.upper().strip()
    matrix_tfs = _parse_timeframes(matrix_timeframes, settings.model_timeframes)
    indicators = [token.strip() for token in heatmap_indicators.split(",") if token.strip()]
    historical_sync = await _queue_ensure_if_needed(
        symbol=symbol,
        timeframe=timeframe,
        wait=False,
        trigger="dashboard_snapshot",
    )

    if _engine is not None:
        live_rows = _engine.recent_candles_snapshot(symbol=symbol, timeframe=timeframe, limit=int(candle_limit))
    else:
        live_rows = []

    if live_rows:
        candles_payload = {
            "count": len(live_rows),
            "rows": live_rows,
            "source": "engine_live",
        }
    else:
        frame = db.get_recent_candles(symbol=symbol, timeframe=timeframe, limit=int(candle_limit))
        candles_payload = {
            "count": len(frame),
            "rows": frame.to_dict("records"),
            "source": "db_history",
        }

    latest_history = db.list_recent_predictions(symbol=symbol, timeframe=timeframe, limit=int(history_limit))
    probability_payload = db.get_probability_vector(symbol=symbol, timeframes=matrix_tfs)
    rules = settings.timeframe_rule_profile(timeframe)
    engine_payload = {"running": False, "details": None}
    if _engine is not None:
        engine_payload = {"running": True, "details": _engine.status_snapshot()}

    requested_symbol = symbol
    source_symbol = requested_symbol
    backtest_payload = db.get_latest_backtest_metrics(symbol=requested_symbol, timeframe=timeframe)
    if backtest_payload is None and requested_symbol != "GLOBAL":
        source_symbol = "GLOBAL"
        backtest_payload = db.get_latest_backtest_metrics(symbol=source_symbol, timeframe=timeframe)

    return {
        "symbol": symbol,
        "timeframe": timeframe,
        "generated_at": datetime.utcnow().isoformat(),
        "historical_sync": {
            "needs_backfill": bool(historical_sync["needs_backfill"]),
            "queued_new": bool(historical_sync["queued_new"]),
            "reasons": historical_sync["reasons"],
            "policy": historical_sync["policy"],
            "task": historical_sync["task"],
        },
        "health": {
            "status": "ok" if _db_ready else "degraded",
            "db_ready": _db_ready,
            "db_error": _db_error,
        },
        "live_price": _best_effort_live_price(symbol=symbol, timeframe=timeframe),
        "candles": candles_payload,
        "signal_history": {
            "count": len(latest_history),
            "rows": latest_history,
        },
        "probability_vector": {
            "symbol": symbol,
            "probabilities": probability_payload,
        },
        "rules": {
            "timeframe": timeframe,
            "rules": rules,
        },
        "engine": engine_payload,
        "model_matrix": build_model_matrix(db, symbol=symbol, timeframes=matrix_tfs),
        "indicator_heatmap": build_indicator_heatmap(
            db,
            symbol=symbol,
            timeframes=matrix_tfs,
            candle_limit=max(260, int(candle_limit)),
            indicators=indicators,
        ),
        "model_backtest": backtest_prediction_signals(
            db,
            symbol=symbol,
            timeframe=timeframe,
            limit=max(200, int(history_limit) * 2),
        ),
        "simulated_backtest": {
            **(backtest_payload or {}),
            "requested_symbol": requested_symbol,
            "source_symbol": source_symbol if backtest_payload else None,
            "fallback_used": bool(backtest_payload and source_symbol != requested_symbol),
        }
        if backtest_payload
        else None,
    }


@app.post("/historical/backfill")
async def historical_backfill(
    symbol: str,
    timeframe: str = Query(pattern="^(1m|5m|15m|1h|1d)$"),
    days: int = Query(default=30, ge=1, le=2000),
) -> dict[str, Any]:
    """Trigger historical backfill through realtime engine."""
    _require_db_ready()
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


@app.post("/historical/ensure")
async def historical_ensure(
    symbol: str,
    timeframe: str = Query(pattern="^(1m|5m|15m|1h|1d)$"),
    wait: bool = Query(default=False),
) -> dict[str, Any]:
    """Ensure minimum historical coverage; can run asynchronously to avoid UI blocking."""
    _require_db_ready()
    result = await _queue_ensure_if_needed(
        symbol=symbol,
        timeframe=timeframe,
        wait=wait,
        trigger="historical_ensure_api",
    )
    task = result["task"]
    status = str((task or {}).get("status", "unknown"))
    action = "queued"
    if not result["needs_backfill"]:
        action = "none"
    elif status == "succeeded":
        action = "backfilled"
    elif status == "failed":
        action = "failed"

    return {
        "symbol": result["symbol"],
        "timeframe": result["timeframe"],
        "action": action,
        "reasons": result["reasons"],
        "policy": result["policy"],
        "before": result["before"],
        "queued_new": result["queued_new"],
        "task": task,
    }


@app.get("/historical/ensure/status")
async def historical_ensure_status(
    symbol: str,
    timeframe: str = Query(pattern="^(1m|5m|15m|1h|1d)$"),
) -> dict[str, Any]:
    """Return background ensure-job status plus current coverage need assessment."""
    _require_db_ready()
    symbol = symbol.upper().strip()
    now_stats = db.get_candle_stats(symbol=symbol, timeframe=timeframe)
    needs_backfill, reasons = _backfill_needed(now_stats, timeframe)
    task = await _ensure_job_snapshot(symbol, timeframe)
    running = str((task or {}).get("status", "")) in {"queued", "running"}
    return {
        "symbol": symbol,
        "timeframe": timeframe,
        "running": running,
        "needs_backfill": needs_backfill,
        "reasons": reasons,
        "policy": _json_safe(_auto_sync_policy(timeframe)),
        "current": _json_safe(now_stats),
        "task": task,
    }
