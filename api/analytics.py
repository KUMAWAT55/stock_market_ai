from __future__ import annotations
"""Intraday analytics helpers for React dashboard APIs."""

from math import sqrt
from typing import Any

import pandas as pd

from database.db_manager import DatabaseManager
from features.indicators import add_indicators


TIMEFRAME_ORDER = ["1m", "5m", "15m", "1h", "1d"]

INDICATOR_META: dict[str, str] = {
    "ema_trend": "EMA Trend",
    "rsi_regime": "RSI Regime",
    "macd_impulse": "MACD Impulse",
    "bb_position": "Bollinger Position",
    "volume_impulse": "Volume Impulse",
    "candle_pressure": "Candle Pressure",
}


def ordered_timeframes(requested: list[str]) -> list[str]:
    """Return unique timeframes sorted by canonical intraday order."""
    cleaned = [token.strip().lower() for token in requested if token.strip()]
    unique = list(dict.fromkeys(cleaned))
    return sorted(unique, key=lambda tf: TIMEFRAME_ORDER.index(tf) if tf in TIMEFRAME_ORDER else 999)


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:
        return default


def _clamp(value: float, low: float = -1.0, high: float = 1.0) -> float:
    return max(low, min(high, float(value)))


def _bias_label(score: float) -> str:
    if score >= 0.25:
        return "bullish"
    if score <= -0.25:
        return "bearish"
    return "neutral"


def _iso_key(value: Any) -> str:
    ts = pd.to_datetime(value, errors="coerce")
    if pd.isna(ts):
        return ""
    if ts.tzinfo is not None:
        ts = ts.tz_convert("UTC").tz_localize(None)
    return ts.isoformat()


def build_indicator_heatmap(
    db: DatabaseManager,
    *,
    symbol: str,
    timeframes: list[str],
    candle_limit: int = 260,
    indicators: list[str] | None = None,
) -> dict[str, Any]:
    """Compute bullish/bearish indicator states per timeframe for a symbol."""
    enabled = set(indicators or INDICATOR_META.keys())
    enabled = {name for name in enabled if name in INDICATOR_META}
    if not enabled:
        enabled = set(INDICATOR_META.keys())

    indicator_by_tf: dict[str, dict[str, dict[str, Any]]] = {}
    summary: list[dict[str, Any]] = []

    for timeframe in ordered_timeframes(timeframes):
        candles = db.get_recent_candles(symbol=symbol, timeframe=timeframe, limit=max(80, int(candle_limit)))
        if candles.empty:
            indicator_by_tf[timeframe] = {}
            summary.append(
                {
                    "timeframe": timeframe,
                    "composite_score": None,
                    "bias": "no_data",
                    "bullish_indicators": 0,
                    "bearish_indicators": 0,
                }
            )
            continue

        frame = add_indicators(candles)
        if len(frame) < 35:
            indicator_by_tf[timeframe] = {}
            summary.append(
                {
                    "timeframe": timeframe,
                    "composite_score": None,
                    "bias": "insufficient_data",
                    "bullish_indicators": 0,
                    "bearish_indicators": 0,
                }
            )
            continue

        latest = frame.iloc[-1]
        close = _safe_float(latest.get("close"), 0.0)
        open_price = _safe_float(latest.get("open"), close)
        high = _safe_float(latest.get("high"), close)
        low = _safe_float(latest.get("low"), close)
        candle_range = max(abs(high - low), 1e-9)

        ema_26 = _safe_float(latest.get("ema_26"), close)
        ema_score = _clamp((close - ema_26) / max(abs(close), 1e-9) * 40.0)

        rsi_14 = _safe_float(latest.get("rsi_14"), 50.0)
        rsi_score = _clamp((rsi_14 - 50.0) / 20.0)

        macd_hist = _safe_float(latest.get("macd_hist"), 0.0)
        atr_pct = max(abs(_safe_float(latest.get("atr_pct"), 0.01)), 0.0005)
        macd_score = _clamp(macd_hist / atr_pct)

        bb_upper = _safe_float(latest.get("bb_upper"), close)
        bb_lower = _safe_float(latest.get("bb_lower"), close)
        bb_width = max(bb_upper - bb_lower, 1e-9)
        bb_pos = _clamp(((close - bb_lower) / bb_width - 0.5) * 2.0)

        volume_z = _safe_float(latest.get("volume_zscore_20"), 0.0)
        ret_1 = _safe_float(latest.get("ret_1"), 0.0)
        vol_impulse = _clamp((volume_z / 3.0) + (0.35 if ret_1 > 0 else -0.35 if ret_1 < 0 else 0.0))

        pressure = _clamp((close - open_price) / candle_range)

        indicator_scores = {
            "ema_trend": ema_score,
            "rsi_regime": rsi_score,
            "macd_impulse": macd_score,
            "bb_position": bb_pos,
            "volume_impulse": vol_impulse,
            "candle_pressure": pressure,
        }
        filtered = {name: score for name, score in indicator_scores.items() if name in enabled}

        tf_rows: dict[str, dict[str, Any]] = {}
        bullish = 0
        bearish = 0
        for name, score in filtered.items():
            bias = _bias_label(score)
            if bias == "bullish":
                bullish += 1
            elif bias == "bearish":
                bearish += 1
            tf_rows[name] = {
                "indicator": name,
                "label": INDICATOR_META[name],
                "score": round(score, 4),
                "bias": bias,
            }
        indicator_by_tf[timeframe] = tf_rows

        composite = sum(filtered.values()) / max(len(filtered), 1)
        summary.append(
            {
                "timeframe": timeframe,
                "composite_score": round(composite, 4),
                "bias": _bias_label(composite),
                "bullish_indicators": bullish,
                "bearish_indicators": bearish,
            }
        )

    heatmap_rows: list[dict[str, Any]] = []
    score_rows: list[dict[str, Any]] = []
    for indicator_name, label in INDICATOR_META.items():
        if indicator_name not in enabled:
            continue
        state_row: dict[str, Any] = {"indicator": indicator_name, "label": label}
        numeric_row: dict[str, Any] = {"indicator": indicator_name, "label": label}
        for timeframe in ordered_timeframes(timeframes):
            bucket = indicator_by_tf.get(timeframe, {}).get(indicator_name)
            if bucket is None:
                state_row[timeframe] = "no_data"
                numeric_row[timeframe] = None
            else:
                state_row[timeframe] = bucket["bias"]
                numeric_row[timeframe] = bucket["score"]
        heatmap_rows.append(state_row)
        score_rows.append(numeric_row)

    return {
        "symbol": symbol,
        "timeframes": ordered_timeframes(timeframes),
        "indicators": [name for name in INDICATOR_META if name in enabled],
        "heatmap_rows": heatmap_rows,
        "score_rows": score_rows,
        "summary": summary,
    }


def build_model_matrix(
    db: DatabaseManager,
    *,
    symbol: str,
    timeframes: list[str],
) -> dict[str, Any]:
    """Return per-timeframe model outputs for a symbol in one matrix payload."""
    ordered = ordered_timeframes(timeframes)
    latest_rows = db.get_latest_predictions_by_timeframe(symbol=symbol, timeframes=ordered)
    row_map = {str(row["timeframe"]): row for row in latest_rows}

    matrix: list[dict[str, Any]] = []
    confidence_scores: list[float] = []
    directional_scores: list[float] = []

    for timeframe in ordered:
        row = row_map.get(timeframe)
        if row is None:
            matrix.append(
                {
                    "timeframe": timeframe,
                    "available": False,
                    "signal": None,
                    "approved_signal": None,
                    "confidence": None,
                    "prob_up": None,
                    "prob_down": None,
                    "model_name": None,
                    "model_version": None,
                    "prediction_ts": None,
                    "target_ts": None,
                    "risk_reason": None,
                }
            )
            continue

        risk = row.get("risk_snapshot") if isinstance(row.get("risk_snapshot"), dict) else {}
        signal = str(row.get("signal") or "HOLD").upper()
        approved_signal = str(risk.get("approved_signal") or signal).upper()
        confidence = _safe_float(row.get("confidence"))
        prob_up = _safe_float(row.get("prob_up"))
        prob_down = _safe_float(row.get("prob_down"))

        confidence_scores.append(confidence)
        directional_scores.append(prob_up - prob_down)

        matrix.append(
            {
                "timeframe": timeframe,
                "available": True,
                "signal": signal,
                "approved_signal": approved_signal,
                "confidence": round(confidence, 4),
                "prob_up": round(prob_up, 4),
                "prob_down": round(prob_down, 4),
                "model_name": row.get("model_name"),
                "model_version": row.get("model_version"),
                "prediction_ts": row.get("prediction_ts"),
                "target_ts": row.get("target_ts"),
                "risk_reason": risk.get("reason"),
            }
        )

    consensus_score = sum(directional_scores) / max(len(directional_scores), 1) if directional_scores else 0.0
    avg_confidence = sum(confidence_scores) / max(len(confidence_scores), 1) if confidence_scores else 0.0
    if consensus_score >= 0.07:
        consensus_signal = "BUY"
    elif consensus_score <= -0.07:
        consensus_signal = "SELL"
    else:
        consensus_signal = "HOLD"

    return {
        "symbol": symbol,
        "timeframes": ordered,
        "rows": matrix,
        "consensus": {
            "signal": consensus_signal,
            "score": round(consensus_score, 4),
            "avg_confidence": round(avg_confidence, 4),
        },
    }


def backtest_prediction_signals(
    db: DatabaseManager,
    *,
    symbol: str,
    timeframe: str,
    limit: int = 500,
) -> dict[str, Any]:
    """Backtest model prediction quality using realized next-candle returns."""
    predictions = db.list_recent_predictions(symbol=symbol, timeframe=timeframe, limit=max(100, int(limit)))
    if not predictions:
        return {
            "symbol": symbol,
            "timeframe": timeframe,
            "trade_count": 0,
            "win_rate": 0.0,
            "avg_return": 0.0,
            "total_return": 0.0,
            "max_drawdown": 0.0,
            "sharpe_like": 0.0,
            "profit_factor": 0.0,
            "trades": [],
        }

    candles = db.get_recent_candles(symbol=symbol, timeframe=timeframe, limit=max(400, int(limit) + 200))
    if candles.empty:
        return {
            "symbol": symbol,
            "timeframe": timeframe,
            "trade_count": 0,
            "win_rate": 0.0,
            "avg_return": 0.0,
            "total_return": 0.0,
            "max_drawdown": 0.0,
            "sharpe_like": 0.0,
            "profit_factor": 0.0,
            "trades": [],
        }

    frame = add_indicators(candles)
    returns_by_target: dict[str, float] = {}
    for row in frame.to_dict("records"):
        key = _iso_key(row.get("candle_end"))
        if key:
            returns_by_target[key] = _safe_float(row.get("ret_1"), 0.0)

    trades: list[dict[str, Any]] = []
    for row in sorted(predictions, key=lambda item: _iso_key(item.get("prediction_ts"))):
        risk = row.get("risk_snapshot") if isinstance(row.get("risk_snapshot"), dict) else {}
        signal = str(risk.get("approved_signal") or row.get("signal") or "HOLD").upper()
        if signal not in {"BUY", "SELL"}:
            continue
        side = 1.0 if signal == "BUY" else -1.0
        realized = returns_by_target.get(_iso_key(row.get("target_ts")))
        if realized is None:
            continue
        pnl = side * realized
        trades.append(
            {
                "prediction_ts": row.get("prediction_ts"),
                "target_ts": row.get("target_ts"),
                "signal": signal,
                "prob_up": round(_safe_float(row.get("prob_up")), 4),
                "confidence": round(_safe_float(row.get("confidence")), 4),
                "realized_return": round(realized, 6),
                "pnl": round(pnl, 6),
            }
        )

    if not trades:
        return {
            "symbol": symbol,
            "timeframe": timeframe,
            "trade_count": 0,
            "win_rate": 0.0,
            "avg_return": 0.0,
            "total_return": 0.0,
            "max_drawdown": 0.0,
            "sharpe_like": 0.0,
            "profit_factor": 0.0,
            "trades": [],
        }

    pnl_series = pd.Series([float(trade["pnl"]) for trade in trades], dtype="float64")
    equity = (1.0 + pnl_series).cumprod()
    drawdown = (equity.cummax() - equity) / equity.cummax().replace(0.0, 1.0)
    wins = (pnl_series > 0).sum()
    losses = (pnl_series < 0).sum()
    gross_profit = pnl_series[pnl_series > 0].sum()
    gross_loss = abs(pnl_series[pnl_series < 0].sum())
    std = pnl_series.std(ddof=0)
    sharpe = 0.0 if std <= 1e-12 else float(pnl_series.mean() / std * sqrt(len(pnl_series)))

    return {
        "symbol": symbol,
        "timeframe": timeframe,
        "trade_count": int(len(pnl_series)),
        "wins": int(wins),
        "losses": int(losses),
        "win_rate": round(float((pnl_series > 0).mean()), 4),
        "avg_return": round(float(pnl_series.mean()), 6),
        "total_return": round(float(equity.iloc[-1] - 1.0), 6),
        "max_drawdown": round(float(drawdown.max()), 6),
        "sharpe_like": round(sharpe, 4),
        "profit_factor": round(float(gross_profit / gross_loss), 4) if gross_loss > 0 else None,
        "trades": trades[-200:],
    }


def backtest_indicator_strategy(
    db: DatabaseManager,
    *,
    symbol: str,
    timeframe: str,
    strategy: str,
    candle_limit: int = 700,
    cost_bps: float = 2.0,
) -> dict[str, Any]:
    """Run a quick intraday rule backtest for Streak-like strategy exploration."""
    candles = db.get_recent_candles(symbol=symbol, timeframe=timeframe, limit=max(250, int(candle_limit)))
    if candles.empty:
        return {
            "symbol": symbol,
            "timeframe": timeframe,
            "strategy": strategy,
            "trade_count": 0,
            "win_rate": 0.0,
            "avg_return": 0.0,
            "total_return": 0.0,
            "max_drawdown": 0.0,
            "sharpe_like": 0.0,
            "trades": [],
            "latest_signal": "no_data",
        }

    frame = add_indicators(candles).copy()
    frame = frame.dropna(subset=["ret_1", "ema_12", "ema_26", "rsi_14", "macd_hist"]).reset_index(drop=True)
    if frame.empty:
        return {
            "symbol": symbol,
            "timeframe": timeframe,
            "strategy": strategy,
            "trade_count": 0,
            "win_rate": 0.0,
            "avg_return": 0.0,
            "total_return": 0.0,
            "max_drawdown": 0.0,
            "sharpe_like": 0.0,
            "trades": [],
            "latest_signal": "insufficient_data",
        }

    if strategy == "ema_trend":
        frame["signal"] = 0
        frame.loc[(frame["ema_12"] > frame["ema_26"]) & (frame["rsi_14"] >= 55), "signal"] = 1
        frame.loc[(frame["ema_12"] < frame["ema_26"]) & (frame["rsi_14"] <= 45), "signal"] = -1
        strategy_note = "EMA12/EMA26 trend with RSI filter"
    elif strategy == "rsi_reversal":
        frame["signal"] = 0
        frame.loc[(frame["rsi_14"] <= 30) & (frame["close"] <= frame["bb_lower"]), "signal"] = 1
        frame.loc[(frame["rsi_14"] >= 70) & (frame["close"] >= frame["bb_upper"]), "signal"] = -1
        strategy_note = "RSI reversion with Bollinger confirmation"
    else:
        frame["signal"] = 0
        frame.loc[(frame["macd_hist"] > 0) & (frame["ret_1"] > 0), "signal"] = 1
        frame.loc[(frame["macd_hist"] < 0) & (frame["ret_1"] < 0), "signal"] = -1
        strategy_note = "MACD impulse continuation"

    frame["next_ret"] = frame["ret_1"].shift(-1).fillna(0.0)
    frame["position_change"] = frame["signal"].diff().abs().fillna(frame["signal"].abs())
    trade_cost = float(max(0.0, cost_bps)) / 10000.0
    frame["gross_pnl"] = frame["signal"] * frame["next_ret"]
    frame["net_pnl"] = frame["gross_pnl"] - (frame["position_change"] * trade_cost)

    active = frame[frame["signal"] != 0].copy()
    if active.empty:
        return {
            "symbol": symbol,
            "timeframe": timeframe,
            "strategy": strategy,
            "strategy_note": strategy_note,
            "trade_count": 0,
            "win_rate": 0.0,
            "avg_return": 0.0,
            "total_return": 0.0,
            "max_drawdown": 0.0,
            "sharpe_like": 0.0,
            "trades": [],
            "latest_signal": "flat",
        }

    pnl = active["net_pnl"].astype(float)
    equity = (1.0 + pnl).cumprod()
    drawdown = (equity.cummax() - equity) / equity.cummax().replace(0.0, 1.0)
    std = pnl.std(ddof=0)
    sharpe = 0.0 if std <= 1e-12 else float(pnl.mean() / std * sqrt(len(pnl)))

    trades = active[["candle_end", "signal", "next_ret", "gross_pnl", "net_pnl"]].tail(200).copy()
    trades["signal"] = trades["signal"].map({1: "BUY", -1: "SELL", 0: "HOLD"})
    trades = trades.rename(columns={"candle_end": "target_ts"})

    latest_signal = active.iloc[-1]["signal"]
    latest_label = "BUY" if latest_signal > 0 else "SELL" if latest_signal < 0 else "HOLD"

    return {
        "symbol": symbol,
        "timeframe": timeframe,
        "strategy": strategy,
        "strategy_note": strategy_note,
        "trade_count": int(len(pnl)),
        "win_rate": round(float((pnl > 0).mean()), 4),
        "avg_return": round(float(pnl.mean()), 6),
        "total_return": round(float(equity.iloc[-1] - 1.0), 6),
        "max_drawdown": round(float(drawdown.max()), 6),
        "sharpe_like": round(sharpe, 4),
        "trades": trades.to_dict("records"),
        "latest_signal": latest_label,
    }
