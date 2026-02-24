from __future__ import annotations

import os
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd
import plotly.graph_objects as go
import requests
import streamlit as st

# Ensure project-root imports work when Streamlit is launched from any directory.
ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from features.indicators import add_indicators


API_BASE_URL = os.getenv("API_BASE_URL", "http://127.0.0.1:8000")


def _get(path: str, params: dict[str, Any] | None = None) -> dict[str, Any] | None:
    try:
        resp = requests.get(f"{API_BASE_URL}{path}", params=params, timeout=8)
        if resp.status_code >= 400:
            return None
        return resp.json()
    except Exception:
        return None


def _post(path: str, params: dict[str, Any] | None = None) -> dict[str, Any] | None:
    try:
        resp = requests.post(f"{API_BASE_URL}{path}", params=params, timeout=30)
        if resp.status_code >= 400:
            try:
                return {"error": resp.json()}
            except Exception:
                return {"error": {"status_code": resp.status_code, "text": resp.text}}
        return resp.json()
    except Exception as exc:
        return {"error": {"message": str(exc)}}


def _build_chart(candles_df: pd.DataFrame) -> go.Figure:
    frame = add_indicators(candles_df)
    fig = go.Figure()
    fig.add_trace(
        go.Candlestick(
            x=frame["candle_start"],
            open=frame["open"],
            high=frame["high"],
            low=frame["low"],
            close=frame["close"],
            name="OHLC",
        )
    )
    fig.add_trace(go.Scatter(x=frame["candle_start"], y=frame["ema_12"], name="EMA12", line=dict(width=1.2)))
    fig.add_trace(go.Scatter(x=frame["candle_start"], y=frame["ema_26"], name="EMA26", line=dict(width=1.2)))
    fig.update_layout(height=480, margin=dict(l=16, r=16, t=30, b=16), xaxis_rangeslider_visible=False)
    return fig


def main() -> None:
    st.set_page_config(page_title="TradeIQ Realtime Dashboard", layout="wide")
    st.title("TradeIQ Realtime Signal Dashboard")

    disclaimer = _get("/compliance/disclaimer")
    if disclaimer:
        st.warning(f"{disclaimer['title']} | {disclaimer['body']}")
        st.info(disclaimer["risk_disclosure"])

    col1, col2, col3, col4, col5 = st.columns([2, 1, 1, 1, 1])
    with col1:
        symbol = st.text_input("Symbol", value="RELIANCE").upper().strip()
    with col2:
        timeframe = st.selectbox("Timeframe", ["1m", "5m", "15m", "1h", "1d"], index=2)
    with col3:
        candle_limit = st.number_input("Candles", min_value=100, max_value=1000, value=300, step=50)
    with col4:
        refresh_secs = st.number_input("Refresh (sec, 0=off)", min_value=0, max_value=60, value=5)
    with col5:
        backfill_days = st.number_input("Backfill days", min_value=1, max_value=2000, value=30, step=5)
        backfill_clicked = st.button("Backfill", use_container_width=True)

    if backfill_clicked:
        backfill_result = _post(
            "/historical/backfill",
            params={"symbol": symbol, "timeframe": timeframe, "days": int(backfill_days)},
        )
        if backfill_result and not backfill_result.get("error"):
            st.success(
                f"Backfill complete: inserted {backfill_result.get('inserted', 0)} candles "
                f"for {symbol} {timeframe}"
            )
        else:
            st.error(f"Backfill failed: {backfill_result}")

    candle_payload = _get("/candles", params={"symbol": symbol, "timeframe": timeframe, "limit": int(candle_limit)})
    history_payload = _get("/signals/history", params={"symbol": symbol, "timeframe": timeframe, "limit": 200})
    backtest_payload = _get("/backtest/latest", params={"symbol": symbol, "timeframe": timeframe}) if timeframe in {"15m", "1d"} else None

    left, right = st.columns([2.2, 1.2])

    with left:
        st.subheader(f"{symbol} Candlestick ({timeframe})")
        if candle_payload and candle_payload.get("rows"):
            candles_df = pd.DataFrame(candle_payload["rows"])
            candles_df["candle_start"] = pd.to_datetime(candles_df["candle_start"])
            candles_df["candle_end"] = pd.to_datetime(candles_df["candle_end"])
            fig = _build_chart(candles_df)
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.error("No candle data available. Use Backfill to preload candles or wait for live market ticks.")

    with right:
        st.subheader("Current Prediction")
        latest_row = None
        if history_payload and history_payload.get("rows"):
            latest_row = history_payload["rows"][0]

        if latest_row:
            st.metric("Signal", latest_row.get("signal", "N/A"))
            st.metric("Confidence", f"{100 * float(latest_row.get('confidence', 0.0)):.2f}%")
            st.metric("Prob Up", f"{100 * float(latest_row.get('prob_up', 0.0)):.2f}%")
            st.metric("Model Version", latest_row.get("model_version", "N/A"))
            st.caption(f"Last Update: {latest_row.get('prediction_ts')}")

            risk_snapshot = latest_row.get("risk_snapshot")
            if isinstance(risk_snapshot, dict):
                st.markdown("**Risk/Governance**")
                st.json(risk_snapshot)
        else:
            if timeframe in {"15m", "1d"}:
                st.info("Prediction not available yet.")
            else:
                st.info("Prediction engine currently runs on 15m and 1d; this view is candle-only.")

    st.subheader("Historical Signals")
    if history_payload and history_payload.get("rows"):
        hist_df = pd.DataFrame(history_payload["rows"])
        display_cols = [
            "prediction_ts",
            "target_ts",
            "signal",
            "confidence",
            "prob_up",
            "prob_down",
            "model_name",
            "model_version",
            "is_simulated",
        ]
        st.dataframe(hist_df[display_cols], use_container_width=True, height=240)
    else:
        st.info("No historical signals yet")

    st.subheader("Backtest Metrics (Simulated Performance)")
    if backtest_payload:
        st.caption("Simulated performance only. Not live audited returns.")
        metrics = backtest_payload.get("metrics", {})
        if isinstance(metrics, dict):
            cols = st.columns(4)
            for idx, (k, v) in enumerate(metrics.items()):
                cols[idx % 4].metric(k, f"{float(v):.4f}" if isinstance(v, (int, float)) else str(v))
        st.json(backtest_payload)
    else:
        st.info("No backtest run found for this symbol/timeframe")

    st.caption(f"API: {API_BASE_URL} | Dashboard time: {datetime.now().isoformat(timespec='seconds')}")

    if refresh_secs > 0:
        time.sleep(int(refresh_secs))
        st.rerun()


if __name__ == "__main__":
    main()
