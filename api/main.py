from __future__ import annotations
"""FastAPI surface for dashboard, engine control, and compliance-safe data access."""

import asyncio
import os
from datetime import datetime
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
    LAG_INDICATORS,
    LEAD_INDICATORS,
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
DEFAULT_HEATMAP_INDICATORS = ",".join(dict.fromkeys(LAG_INDICATORS + LEAD_INDICATORS))

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
        # Stored timestamps are treated as market-time naive values.
        return dt.replace(tzinfo=_market_tz)
    return dt.astimezone(_market_tz)


def _format_market_dt(value: Any) -> str | None:
    dt = _to_market_dt(value)
    return dt.isoformat() if dt else None


def _normalize_row_timestamps(row: dict[str, Any], keys: tuple[str, ...]) -> dict[str, Any]:
    out = dict(row)
    for key in keys:
        if key in out:
            out[key] = _format_market_dt(out.get(key))
    return out


def _normalize_rows_timestamps(rows: list[dict[str, Any]], keys: tuple[str, ...]) -> list[dict[str, Any]]:
    return [_normalize_row_timestamps(row, keys) for row in rows]


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


@app.on_event("startup")
async def startup_event() -> None:
    """Initialize schema and optionally auto-start realtime engine on app boot."""
    global _db_ready, _db_error
    try:
        db.init_schema()
        _db_ready = True
        _db_error = None
    except Exception as exc:
        _db_ready = False
        _db_error = str(exc)
        logger.exception("Database init failed; API continuing in degraded mode: {}", exc)

    auto_start = os.getenv("AUTO_START_ENGINE", "true").lower() == "true"
    logger.info("AUTO_START_ENGINE={} (auto_start={})", os.getenv("AUTO_START_ENGINE", "true"), auto_start)
    if auto_start and _db_ready:
        async with _engine_lock:
            engine = await _ensure_engine()
            try:
                await engine.start()
                logger.info("Realtime engine auto-started")
            except Exception as exc:
                logger.warning("Realtime engine did not auto-start: {}", exc)

@app.on_event("shutdown")
async def shutdown_event() -> None:
    """Stop realtime engine gracefully on API shutdown."""
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
    symbols = settings.load_symbol_universe()
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


@app.get("/kite/instruments")
async def kite_instruments(
    exchange: str | None = Query(default=None),
    symbol: str | None = Query(default=None),
    limit: int = Query(default=200, ge=1, le=2000),
) -> dict[str, Any]:
    """Fetch Kite instrument list with optional exchange/symbol filtering."""
    try:
        client = KiteHistoricalClient().client
        rows = await asyncio.to_thread(client.instruments, exchange) if exchange else await asyncio.to_thread(client.instruments)
    except TokenException as exc:
        raise HTTPException(status_code=401, detail=f"Kite auth failed: {exc}") from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Kite instruments fetch failed: {exc}") from exc

    def normalize(value: Any) -> str:
        return str(value or "").strip().lower()

    filtered: list[dict[str, Any]] = []
    symbol_query = normalize(symbol)
    token_query: int | None = None
    if symbol_query and symbol_query.isdigit():
        token_query = int(symbol_query)

    for row in rows or []:
        if token_query is not None:
            if int(row.get("instrument_token") or 0) != token_query:
                continue
        elif symbol_query:
            if symbol_query not in normalize(row.get("tradingsymbol")) and symbol_query not in normalize(row.get("name")):
                continue
        filtered.append(
            {
                "instrument_token": row.get("instrument_token"),
                "tradingsymbol": row.get("tradingsymbol"),
                "name": row.get("name"),
                "exchange": row.get("exchange"),
                "segment": row.get("segment"),
                "instrument_type": row.get("instrument_type"),
                "lot_size": row.get("lot_size"),
                "tick_size": row.get("tick_size"),
            }
        )
        if len(filtered) >= int(limit):
            break

    return {
        "exchange": exchange,
        "symbol": symbol,
        "count": len(filtered),
        "rows": filtered,
    }


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
    rows = _normalize_rows_timestamps(rows, ("prediction_ts", "target_ts"))
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
    rows = _normalize_rows_timestamps(rows, ("prediction_ts", "target_ts"))
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
            "prediction_ts": _format_market_dt(latest.get("prediction_ts")),
            "target_ts": _format_market_dt(latest.get("target_ts")),
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
                "rows": _normalize_rows_timestamps(live_rows, ("candle_start", "candle_end")),
                "source": "engine_live",
            }

    _require_db_ready()
    frame = db.get_recent_candles(symbol=symbol, timeframe=timeframe, limit=limit)
    if frame.empty:
        raise HTTPException(status_code=404, detail="No candles found")
    return {
        "count": len(frame),
        "rows": _normalize_rows_timestamps(frame.to_dict("records"), ("candle_start", "candle_end")),
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
    row = db.get_latest_backtest_metrics(symbol=requested_symbol, timeframe=timeframe)
    if row is None:
        raise HTTPException(status_code=404, detail="No backtest metrics found")
    row["requested_symbol"] = requested_symbol
    row["source_symbol"] = requested_symbol
    row["fallback_used"] = False
    return row


@app.get("/analytics/indicator-heatmap")
async def indicator_heatmap(
    symbol: str,
    timeframes: str = Query(default="1m,5m,15m,1h,1d"),
    indicators: str = Query(default=DEFAULT_HEATMAP_INDICATORS),
    group: str = Query(default="all", pattern="^(all|lag|lead)$"),
    candle_limit: int = Query(default=260, ge=80, le=2000),
) -> dict[str, Any]:
    """Return bullish/bearish indicator heatmap for selected symbol and timeframes."""
    _require_db_ready()
    symbol = symbol.upper().strip()
    resolved_timeframes = _parse_timeframes(timeframes, settings.candle_timeframes)
    if group == "lag":
        requested_indicators = LAG_INDICATORS
    elif group == "lead":
        requested_indicators = LEAD_INDICATORS
    else:
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
    payload = build_model_matrix(db, symbol=symbol, timeframes=resolved_timeframes)
    payload["rows"] = _normalize_rows_timestamps(payload.get("rows", []), ("prediction_ts", "target_ts"))
    return payload


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
    signal: str = Query(default="ALL", pattern="^(ALL|BULLISH|BEARISH|HOLD)$"),
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
                "prediction_ts": _format_market_dt(row.get("prediction_ts")),
                "target_ts": _format_market_dt(row.get("target_ts")),
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
    heatmap_indicators: str = Query(default=DEFAULT_HEATMAP_INDICATORS),
) -> dict[str, Any]:
    """Return consolidated payload optimized for React dashboard refresh loops."""
    _require_db_ready()
    symbol = symbol.upper().strip()
    matrix_tfs = _parse_timeframes(matrix_timeframes, settings.model_timeframes)
    indicators = [token.strip() for token in heatmap_indicators.split(",") if token.strip()]
    historical_sync = {
        "needs_backfill": False,
        "queued_new": False,
        "reasons": ["disabled"],
        "policy": None,
        "task": None,
    }

    if _engine is not None:
        live_rows = _engine.recent_candles_snapshot(symbol=symbol, timeframe=timeframe, limit=int(candle_limit))
    else:
        live_rows = []

    if live_rows:
        candles_payload = {
            "count": len(live_rows),
            "rows": _normalize_rows_timestamps(live_rows, ("candle_start", "candle_end")),
            "source": "engine_live",
        }
    else:
        frame = db.get_recent_candles(symbol=symbol, timeframe=timeframe, limit=int(candle_limit))
        candles_payload = {
            "count": len(frame),
            "rows": _normalize_rows_timestamps(frame.to_dict("records"), ("candle_start", "candle_end")),
            "source": "db_history",
        }

    latest_history = db.list_recent_predictions(symbol=symbol, timeframe=timeframe, limit=int(history_limit))
    latest_history = _normalize_rows_timestamps(latest_history, ("prediction_ts", "target_ts"))
    probability_payload_raw = db.get_probability_vector(symbol=symbol, timeframes=matrix_tfs)
    probability_payload = {
        tf: {
            **row,
            "prediction_ts": _format_market_dt(row.get("prediction_ts")),
            "target_ts": _format_market_dt(row.get("target_ts")),
        }
        for tf, row in probability_payload_raw.items()
    }
    rules = settings.timeframe_rule_profile(timeframe)
    engine_payload = {"running": False, "details": None}
    if _engine is not None:
        engine_payload = {"running": True, "details": _engine.status_snapshot()}

    requested_symbol = symbol
    source_symbol = requested_symbol
    backtest_payload = db.get_latest_backtest_metrics(symbol=requested_symbol, timeframe=timeframe)

    model_matrix_payload = build_model_matrix(db, symbol=symbol, timeframes=matrix_tfs)
    model_matrix_payload["rows"] = _normalize_rows_timestamps(
        model_matrix_payload.get("rows", []),
        ("prediction_ts", "target_ts"),
    )

    return {
        "symbol": symbol,
        "timeframe": timeframe,
        "generated_at": datetime.now(_market_tz).isoformat(),
        "historical_sync": historical_sync,
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
        "model_matrix": model_matrix_payload,
        "indicator_heatmap": build_indicator_heatmap(
            db,
            symbol=symbol,
            timeframes=matrix_tfs,
            candle_limit=max(260, int(candle_limit)),
            indicators=indicators,
        ),
        "indicator_heatmap_lag": build_indicator_heatmap(
            db,
            symbol=symbol,
            timeframes=matrix_tfs,
            candle_limit=max(260, int(candle_limit)),
            indicators=LAG_INDICATORS,
        ),
        "indicator_heatmap_lead": build_indicator_heatmap(
            db,
            symbol=symbol,
            timeframes=matrix_tfs,
            candle_limit=max(260, int(candle_limit)),
            indicators=LEAD_INDICATORS,
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
            "fallback_used": False,
        }
        if backtest_payload
        else None,
    }
