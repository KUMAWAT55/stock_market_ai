import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import numpy as np
import sys
from textwrap import dedent
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.append(str(ROOT_DIR))

from src.storage.db.connection import engine


st.set_page_config(
    page_title="TradeIQ",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Manrope:wght@500;600;700;800&family=Source+Sans+3:wght@400;500;600;700&display=swap');

    :root {
        --bg: #f3f6fb;
        --bg-soft: #eaf0f7;
        --surface: #ffffff;
        --surface-soft: #f8fafd;
        --border: #d3dce8;
        --border-strong: #b7c4d8;
        --text-main: #0f172a;
        --text-dim: #475569;
        --brand: #1d4ed8;
        --brand-dark: #143f95;
        --brand-soft: #dbe7ff;
        --pos: #15803d;
        --neg: #b91c1c;
        --neu: #b45309;
        --shadow-sm: 0 5px 16px rgba(15, 23, 42, 0.08);
        --shadow-md: 0 10px 24px rgba(15, 23, 42, 0.11);
    }

    .stApp {
        font-family: "Source Sans 3", "Segoe UI", sans-serif;
        color: var(--text-main);
        background:
            radial-gradient(840px 460px at -8% -16%, rgba(37, 99, 235, 0.11), transparent 68%),
            radial-gradient(760px 420px at 108% -8%, rgba(14, 116, 144, 0.08), transparent 66%),
            linear-gradient(180deg, var(--bg) 0%, var(--bg-soft) 100%);
    }

    .main .block-container {
        max-width: 1320px;
        padding-top: 0.9rem;
        padding-bottom: 1rem;
        padding-left: 1rem;
        padding-right: 1rem;
    }

    header[data-testid="stHeader"] {
        background: transparent;
    }

    div[data-testid="stToolbar"] {
        background: transparent;
    }

    section[data-testid="stSidebar"] {
        background: linear-gradient(180deg, #f7f9fc 0%, #eff4fb 100%);
        border-right: 1px solid var(--border);
    }

    section[data-testid="stSidebar"] label,
    section[data-testid="stSidebar"] p,
    section[data-testid="stSidebar"] .stMarkdown,
    section[data-testid="stSidebar"] [data-testid="stSelectbox"] {
        font-family: "Manrope", "Segoe UI", sans-serif !important;
    }

    .sidebar-title {
        margin-bottom: 0.55rem;
        padding: 0.55rem 0.65rem;
        border-radius: 10px;
        background: var(--surface);
        border: 1px solid var(--border);
        box-shadow: var(--shadow-sm);
    }

    .sidebar-kicker {
        color: #33557a;
        font-size: 0.65rem;
        text-transform: uppercase;
        letter-spacing: 0.09em;
        font-weight: 800;
        margin-bottom: 0.15rem;
    }

    .sidebar-heading {
        color: #0f2a4f;
        font-size: 0.94rem;
        font-weight: 800;
    }

    section[data-testid="stSidebar"] [data-baseweb="select"] > div {
        background: var(--surface) !important;
        border: 1px solid var(--border) !important;
        border-radius: 10px !important;
        box-shadow: none !important;
    }

    div[data-testid="stSelectbox"] [data-baseweb="select"] > div {
        background: var(--surface) !important;
        border: 1px solid var(--border) !important;
        border-radius: 10px !important;
        box-shadow: none !important;
    }

    section[data-testid="stSidebar"] [data-baseweb="select"] > div:hover,
    div[data-testid="stSelectbox"] [data-baseweb="select"] > div:hover {
        border-color: var(--border-strong) !important;
    }

    section[data-testid="stSidebar"] [data-baseweb="select"] > div:focus-within,
    div[data-testid="stSelectbox"] [data-baseweb="select"] > div:focus-within {
        border-color: var(--brand) !important;
        box-shadow: 0 0 0 3px rgba(29, 78, 216, 0.16) !important;
    }

    section[data-testid="stSidebar"] [data-baseweb="select"] span {
        color: #0f172a !important;
        font-weight: 700;
    }

    div[data-testid="stSelectbox"] [data-baseweb="select"] span {
        color: #0f172a !important;
        font-weight: 700;
    }

    section[data-testid="stSidebar"] [data-baseweb="select"] input {
        color: #0f172a !important;
        background: transparent !important;
    }
    section[data-testid="stSidebar"] [data-baseweb="select"] svg {
        fill: #64748b !important;
    }
    div[data-baseweb="popover"],
    div[data-baseweb="popover"] > div,
    div[role="listbox"],
    ul[role="listbox"],
    [data-baseweb="menu"],
    [data-baseweb="select"] [role="listbox"] {
        background: #ffffff !important;
        border: 1px solid var(--border) !important;
        border-radius: 10px !important;
        box-shadow: 0 12px 24px rgba(15, 23, 42, 0.12) !important;
    }

    div[data-baseweb="popover"] ul,
    div[data-baseweb="popover"] li {
        background: transparent !important;
    }
    div[data-baseweb="popover"] [role="option"],
    div[role="listbox"] [role="option"],
    ul[role="listbox"] li,
    [data-baseweb="menu"] li {
        color: #0f172a !important;
        background: transparent !important;
        font-weight: 600 !important;
        opacity: 1 !important;
    }
    div[data-baseweb="popover"] [role="option"][aria-selected="true"],
    div[role="listbox"] [role="option"][aria-selected="true"] {
        background: rgba(29, 78, 216, 0.14) !important;
    }

    div[data-baseweb="popover"] [role="option"]:hover,
    div[role="listbox"] [role="option"]:hover {
        background: rgba(29, 78, 216, 0.08) !important;
    }

    h1, h2, h3 {
        font-family: "Manrope", "Segoe UI", sans-serif;
        letter-spacing: 0.01em;
        color: var(--text-main);
        opacity: 1 !important;
    }
    p, label, span, div {
        color: var(--text-main);
        opacity: 1;
    }

    .app-title {
        position: relative;
        background: linear-gradient(135deg, var(--brand-dark) 0%, #1e58b2 100%);
        border: 1px solid #194789;
        border-radius: 14px;
        padding: 0.9rem 1rem;
        margin-bottom: 0.75rem;
        box-shadow: var(--shadow-md);
        overflow: hidden;
    }

    .app-title > * {
        position: relative;
        z-index: 1;
    }

    .app-title::before {
        content: "";
        position: absolute;
        inset: 0 auto 0 0;
        width: 6px;
        background: linear-gradient(180deg, #93c5fd, #bfdbfe);
        z-index: 0;
    }

    .app-title::after {
        content: "";
        position: absolute;
        inset: 0;
        background: radial-gradient(440px 220px at 92% -18%, rgba(147, 197, 253, 0.24), transparent 70%);
        pointer-events: none;
        z-index: 0;
    }

    .app-kicker {
        color: #c8ddff;
        font-size: 0.66rem;
        letter-spacing: 0.11em;
        text-transform: uppercase;
        font-weight: 800;
        margin-bottom: 0.18rem;
    }

    .app-heading {
        font-size: 1.54rem;
        line-height: 1.08;
        font-weight: 800;
        margin: 0;
        color: #ffffff;
    }

    .app-sub {
        color: #dce9ff;
        margin-top: 0.28rem;
        font-size: 0.79rem;
        font-weight: 600;
    }

    .decision-card,
    .snapshot-card {
        background: var(--surface);
        border: 1px solid var(--border);
        border-radius: 12px;
        padding: 0.65rem 0.75rem;
        margin-bottom: 0.45rem;
        box-shadow: var(--shadow-sm);
        transition: border-color 160ms ease, box-shadow 160ms ease;
    }

    .decision-card:hover,
    .snapshot-card:hover,
    .news-card:hover,
    .indicator-box:hover,
    div[data-testid="stPlotlyChart"]:hover {
        border-color: var(--border-strong);
        box-shadow: var(--shadow-md);
    }

    .snapshot-label {
        color: #5d6d82;
        font-size: 0.67rem;
        text-transform: uppercase;
        letter-spacing: 0.08em;
        margin-bottom: 0.14rem;
        font-weight: 800;
    }

    .snapshot-value {
        color: var(--text-main);
        font-size: 1.03rem;
        font-weight: 800;
        line-height: 1.2;
    }

    .news-card {
        background: var(--surface);
        border: 1px solid var(--border);
        border-radius: 12px;
        padding: 0.65rem 0.75rem;
        margin-bottom: 0.45rem;
        box-shadow: var(--shadow-sm);
    }

    .news-title {
        color: var(--text-main);
        font-weight: 700;
        margin-bottom: 0.24rem;
        font-size: 0.87rem;
        line-height: 1.3;
    }

    .news-meta {
        color: var(--text-dim);
        font-size: 0.76rem;
        margin-bottom: 0.16rem;
        font-weight: 600;
    }

    .news-link {
        color: var(--brand);
        text-decoration: none;
        font-size: 0.77rem;
        font-weight: 700;
        border-bottom: 1px solid rgba(29, 78, 216, 0.36);
    }

    .news-link:hover {
        color: #123ea5;
        border-bottom-color: rgba(18, 62, 165, 0.72);
    }

    .metric-grid {
        display: grid;
        grid-template-columns: repeat(3, minmax(0, 1fr));
        gap: 0.45rem;
        margin-bottom: 0.25rem;
    }

    .metric-grid .snapshot-card {
        margin-bottom: 0;
    }

    .indicator-grid {
        display: grid;
        grid-template-columns: repeat(4, minmax(0, 1fr));
        gap: 0.42rem;
        margin-bottom: 0.1rem;
    }

    .indicator-box {
        border-radius: 10px;
        padding: 0.52rem 0.56rem;
        border: 1px solid var(--border);
        box-shadow: var(--shadow-sm);
    }

    div[data-testid="stPlotlyChart"] {
        background: var(--surface);
        border: 1px solid var(--border);
        border-radius: 12px;
        padding: 0.42rem;
        box-shadow: var(--shadow-sm);
        transition: border-color 160ms ease, box-shadow 160ms ease;
    }

    div[data-testid="stPlotlyChart"] .js-plotly-plot,
    div[data-testid="stPlotlyChart"] .plot-container,
    div[data-testid="stPlotlyChart"] .svg-container {
        background: transparent !important;
    }

    .indicator-name {
        font-size: 0.7rem;
        font-weight: 700;
        margin-bottom: 0.12rem;
        color: #2f435c;
    }

    .indicator-signal {
        font-size: 0.82rem;
        font-weight: 800;
        color: #0f172a;
    }

    h3 {
        font-size: 1.03rem !important;
        margin-top: 0.2rem !important;
        margin-bottom: 0.38rem !important;
        color: #0f2543 !important;
    }

    div[data-testid="stHeading"] {
        margin-top: 0.05rem !important;
        margin-bottom: 0.15rem !important;
    }

    .indicator-bull {
        background: #ecfdf3;
        border-color: #b8e8cc;
        color: var(--pos);
    }

    .indicator-bear {
        background: #fef2f2;
        border-color: #f6c3c3;
        color: var(--neg);
    }

    .indicator-neutral {
        background: #fffbeb;
        border-color: #f9e0ad;
        color: var(--neu);
    }

    .stDataFrame,
    .stTable {
        border: 1px solid var(--border);
        border-radius: 12px;
        overflow: hidden;
        box-shadow: var(--shadow-sm);
        background: var(--surface);
    }

    details[data-testid="stExpander"] {
        border: 1px solid var(--border);
        border-radius: 12px;
        background: var(--surface);
        box-shadow: var(--shadow-sm);
    }

    details[data-testid="stExpander"] summary {
        font-family: "Manrope", "Segoe UI", sans-serif;
        font-weight: 700;
        color: #1a365d;
    }

    .stDataFrame div,
    .stDataFrame span,
    .stTable div,
    .stTable span {
        color: #11223d !important;
        opacity: 1 !important;
    }

    @media (prefers-reduced-motion: reduce) {
        .decision-card,
        .snapshot-card,
        .news-card,
        .indicator-box,
        div[data-testid="stPlotlyChart"],
        section[data-testid="stSidebar"] [data-baseweb="select"] > div,
        div[data-testid="stSelectbox"] [data-baseweb="select"] > div {
            transition: none !important;
            animation: none !important;
        }
    }

    @media (max-width: 1200px) {
        .main .block-container {
            max-width: 100%;
            padding-left: 0.75rem;
            padding-right: 0.75rem;
        }
        .indicator-grid {
            grid-template-columns: repeat(3, minmax(0, 1fr));
        }
        .metric-grid {
            grid-template-columns: repeat(3, minmax(0, 1fr));
        }
    }

    @media (max-width: 940px) {
        .app-heading {
            font-size: 1.38rem;
        }
        .app-sub {
            font-size: 0.75rem;
        }
        .indicator-grid {
            grid-template-columns: repeat(2, minmax(0, 1fr));
        }
        .metric-grid {
            grid-template-columns: repeat(2, minmax(0, 1fr));
        }
        div[data-testid="stHorizontalBlock"] {
            display: flex;
            flex-direction: column;
            gap: 0.7rem;
        }
        div[data-testid="column"] {
            width: 100% !important;
            flex: 1 1 100% !important;
            min-width: 100% !important;
        }
        section[data-testid="stSidebar"] {
            min-width: 250px !important;
            max-width: 300px !important;
        }
    }

    @media (max-width: 640px) {
        .main .block-container {
            padding-left: 0.5rem;
            padding-right: 0.5rem;
            padding-top: 0.55rem;
            padding-bottom: 0.7rem;
        }
        .app-heading {
            font-size: 1.21rem;
        }
        .app-kicker {
            font-size: 0.6rem;
        }
        .snapshot-value {
            font-size: 0.9rem;
        }
        .indicator-grid {
            grid-template-columns: repeat(1, minmax(0, 1fr));
            gap: 0.38rem;
        }
        .metric-grid {
            grid-template-columns: repeat(1, minmax(0, 1fr));
            gap: 0.38rem;
        }
        .decision-card,
        .snapshot-card,
        .news-card,
        .indicator-box {
            padding: 0.56rem 0.58rem;
            border-radius: 9px;
        }
        div[data-testid="stPlotlyChart"] {
            padding: 0.32rem;
        }
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# ----------------------------------
# Indicator Consensus
# ----------------------------------

def _safe_series(df, col):
    return pd.to_numeric(df[col], errors="coerce")


def compute_indicator_consensus(price_df, sentiment_score):
    df = price_df.copy()
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df = df.sort_values("date").dropna(subset=["date"]).copy()

    for col in ["open", "high", "low", "close", "volume"]:
        df[col] = _safe_series(df, col)

    if len(df) < 60:
        return {
            "summary": "INSUFFICIENT DATA",
            "score": 0,
            "confidence": 0.0,
            "rows": pd.DataFrame(columns=["Indicator", "Signal", "Score"]),
        }

    close = df["close"]
    high = df["high"]
    low = df["low"]
    volume = df["volume"].fillna(0)
    prev_close = close.shift(1)

    sma5 = close.rolling(5).mean()
    sma20 = close.rolling(20).mean()
    ema9 = close.ewm(span=9, adjust=False).mean()
    ema21 = close.ewm(span=21, adjust=False).mean()
    ema12 = close.ewm(span=12, adjust=False).mean()
    ema26 = close.ewm(span=26, adjust=False).mean()

    delta = close.diff()
    gain = delta.clip(lower=0).rolling(14).mean()
    loss = (-delta.clip(upper=0)).rolling(14).mean()
    rs = gain / loss.replace(0, pd.NA)
    rsi14 = 100 - (100 / (1 + rs))

    macd = ema12 - ema26
    macd_signal = macd.ewm(span=9, adjust=False).mean()
    macd_hist = macd - macd_signal

    bb_mid = close.rolling(20).mean()
    bb_std = close.rolling(20).std()
    bb_upper = bb_mid + (2 * bb_std)
    bb_lower = bb_mid - (2 * bb_std)
    bb_pos = (close - bb_lower) / (bb_upper - bb_lower)

    lowest14 = low.rolling(14).min()
    highest14 = high.rolling(14).max()
    stoch_k = ((close - lowest14) / (highest14 - lowest14)) * 100
    williams_r = ((highest14 - close) / (highest14 - lowest14)) * -100

    roc10 = close.pct_change(10) * 100
    momentum10 = close - close.shift(10)

    tr = pd.concat(
        [(high - low), (high - prev_close).abs(), (low - prev_close).abs()],
        axis=1,
    ).max(axis=1)

    obv = ((close.diff().fillna(0).apply(lambda x: 1 if x > 0 else (-1 if x < 0 else 0))) * volume).cumsum()
    obv_slope = obv.diff(5)

    volume_ratio = volume / volume.rolling(20).mean().replace(0, pd.NA)
    price_change = close.diff()
    vol_10 = close.pct_change().rolling(10).std()
    vol_30 = close.pct_change().rolling(30).std()
    vol_regime = vol_10 / vol_30.replace(0, pd.NA)

    tp = (high + low + close) / 3
    tp_ma = tp.rolling(20).mean()
    tp_dev = (tp - tp_ma).abs().rolling(20).mean()
    cci20 = (tp - tp_ma) / (0.015 * tp_dev.replace(0, pd.NA))

    plus_dm = (high.diff()).where((high.diff() > (low.shift(1) - low)) & (high.diff() > 0), 0.0)
    minus_dm = (low.shift(1) - low).where(((low.shift(1) - low) > high.diff()) & ((low.shift(1) - low) > 0), 0.0)
    plus_dm = pd.to_numeric(plus_dm, errors="coerce")
    minus_dm = pd.to_numeric(minus_dm, errors="coerce")
    tr14 = pd.to_numeric(tr.rolling(14).sum(), errors="coerce")

    plus_di = 100.0 * (plus_dm.rolling(14).sum() / tr14.replace(0, np.nan))
    minus_di = 100.0 * (minus_dm.rolling(14).sum() / tr14.replace(0, np.nan))
    plus_di = pd.to_numeric(plus_di, errors="coerce")
    minus_di = pd.to_numeric(minus_di, errors="coerce")

    dx = ((plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, np.nan)) * 100.0
    dx = pd.to_numeric(dx, errors="coerce")
    adx14 = dx.rolling(14).mean()

    cum_vol = volume.cumsum().replace(0, np.nan)
    cum_tpv = (tp * volume).cumsum()
    vwap = cum_tpv / cum_vol
    vwap_slope = vwap.diff(5)

    tp_diff = tp.diff()
    raw_mf = tp * volume
    pos_mf = raw_mf.where(tp_diff > 0, 0.0)
    neg_mf = raw_mf.where(tp_diff < 0, 0.0).abs()
    mfi_ratio = pos_mf.rolling(14).sum() / neg_mf.rolling(14).sum().replace(0, np.nan)
    mfi14 = 100 - (100 / (1 + mfi_ratio))

    donchian_upper = high.rolling(20).max().shift(1)
    donchian_lower = low.rolling(20).min().shift(1)

    session_key = df["date"].dt.floor("D")
    session_open = df.groupby(session_key)["open"].transform("first")

    idx = df.index[-1]
    indicator_rows = []

    def _safe_bool(value):
        if pd.isna(value):
            return False
        try:
            return bool(value)
        except Exception:
            return False

    def add_indicator(name, bullish, bearish):
        bull = _safe_bool(bullish)
        bear = _safe_bool(bearish)
        if bull and not bear:
            indicator_rows.append({"Indicator": name, "Signal": "Bullish", "Score": 1})
        elif bear and not bull:
            indicator_rows.append({"Indicator": name, "Signal": "Bearish", "Score": -1})
        else:
            indicator_rows.append({"Indicator": name, "Signal": "Neutral", "Score": 0})

    add_indicator("SMA 5/20", sma5.loc[idx] > sma20.loc[idx], sma5.loc[idx] < sma20.loc[idx])
    add_indicator("EMA 9/21", ema9.loc[idx] > ema21.loc[idx], ema9.loc[idx] < ema21.loc[idx])
    add_indicator("RSI 14", rsi14.loc[idx] < 35, rsi14.loc[idx] > 70)
    add_indicator("MACD Histogram", macd_hist.loc[idx] > 0, macd_hist.loc[idx] < 0)
    add_indicator("Bollinger Position", bb_pos.loc[idx] < 0.2, bb_pos.loc[idx] > 0.8)
    add_indicator("Stochastic %K", stoch_k.loc[idx] < 20, stoch_k.loc[idx] > 80)
    add_indicator("Williams %R", williams_r.loc[idx] < -80, williams_r.loc[idx] > -20)
    add_indicator("ROC 10", roc10.loc[idx] > 0, roc10.loc[idx] < 0)
    add_indicator("Momentum 10", momentum10.loc[idx] > 0, momentum10.loc[idx] < 0)
    add_indicator("OBV Slope", obv_slope.loc[idx] > 0, obv_slope.loc[idx] < 0)
    add_indicator(
        "Price-Volume Impulse",
        (price_change.loc[idx] > 0) and (volume_ratio.loc[idx] > 1.1),
        (price_change.loc[idx] < 0) and (volume_ratio.loc[idx] > 1.1),
    )
    add_indicator("Volatility Regime", vol_regime.loc[idx] < 1.0, vol_regime.loc[idx] > 1.3)
    add_indicator("CCI 20", cci20.loc[idx] < -100, cci20.loc[idx] > 100)
    add_indicator(
        "ADX Trend",
        (plus_di.loc[idx] > minus_di.loc[idx]) and (adx14.loc[idx] > 20),
        (plus_di.loc[idx] < minus_di.loc[idx]) and (adx14.loc[idx] > 20),
    )
    add_indicator("VWAP Bias", close.loc[idx] > vwap.loc[idx], close.loc[idx] < vwap.loc[idx])
    add_indicator("VWAP Slope", vwap_slope.loc[idx] > 0, vwap_slope.loc[idx] < 0)
    add_indicator("MFI 14", mfi14.loc[idx] < 25, mfi14.loc[idx] > 75)
    add_indicator(
        "Donchian Breakout",
        close.loc[idx] > donchian_upper.loc[idx],
        close.loc[idx] < donchian_lower.loc[idx],
    )
    add_indicator("Session Open Bias", close.loc[idx] > session_open.loc[idx], close.loc[idx] < session_open.loc[idx])
    add_indicator("News Sentiment", sentiment_score > 0.1, sentiment_score < -0.1)

    result_df = pd.DataFrame(indicator_rows)
    result_df["Score"] = pd.to_numeric(result_df["Score"], errors="coerce").fillna(0).astype(int)
    total_score = int(result_df["Score"].sum())
    max_abs_score = len(result_df)
    confidence = abs(total_score) / max_abs_score if max_abs_score else 0.0

    if total_score >= 7:
        summary = "STRONG BULLISH"
    elif total_score >= 3:
        summary = "BULLISH"
    elif total_score <= -7:
        summary = "STRONG BEARISH"
    elif total_score <= -3:
        summary = "BEARISH"
    else:
        summary = "NEUTRAL"

    return {
        "summary": summary,
        "score": total_score,
        "confidence": confidence,
        "rows": result_df,
    }

st.markdown(
    """
    <div class="app-title">
        <div class="app-kicker">Intraday Intelligence Desk</div>
        <h1 class="app-heading">TradeIQ</h1>
        <div class="app-sub">Signal Depth. Execution Edge.</div>
    </div>
    """,
    unsafe_allow_html=True,
)

# ----------------------------------
# Sidebar
# ----------------------------------

@st.cache_data
def load_symbols():
    symbols_df = pd.read_sql(
        """
        SELECT symbol, name
        FROM symbols_master
        WHERE active = true
        ORDER BY symbol
        """,
        engine,
    )

    if not symbols_df.empty:
        return symbols_df

    fallback_df = pd.read_sql(
        """
        SELECT DISTINCT symbol, NULL AS name
        FROM market_data
        ORDER BY symbol
        """,
        engine,
    )
    return fallback_df


# ----------------------------------
# Load Data
# ----------------------------------

@st.cache_data
def load_prices(sym):

    return pd.read_sql(f"""
        SELECT *
        FROM market_data
        WHERE symbol='{sym}'
        ORDER BY date
    """, engine)


@st.cache_data
def load_news(sym):

    return pd.read_sql(f"""
        SELECT *
        FROM market_news
        WHERE symbol='{sym.replace(".NS","")}'
        ORDER BY published_at DESC
        LIMIT 5
    """, engine)


@st.cache_data
def load_latest_prediction(sym):

    try:
        return pd.read_sql(
            f"""
            SELECT *
            FROM stock_predictions
            WHERE symbol='{sym}'
            ORDER BY target_date DESC
            LIMIT 1
            """,
            engine,
        )
    except Exception:
        return pd.DataFrame()


@st.cache_data
def load_model_predictions(sym):
    try:
        df = pd.read_sql(
            f"""
            SELECT *
            FROM stock_predictions
            WHERE symbol='{sym}'
            ORDER BY target_date DESC, created_at DESC
            LIMIT 200
            """,
            engine,
        )
        if df.empty:
            return df
        return df.sort_values(
            by=["target_date", "created_at"], ascending=[False, False]
        ).drop_duplicates(subset=["model_name"], keep="first")
    except Exception:
        return pd.DataFrame()


@st.cache_data
def load_backtest_results(sym):
    try:
        df = pd.read_sql(
            f"""
            SELECT *
            FROM model_backtest_results
            WHERE symbol='{sym}'
            ORDER BY run_date DESC, created_at DESC
            LIMIT 200
            """,
            engine,
        )
        if df.empty:
            return df
        return df.sort_values(
            by=["run_date", "created_at"], ascending=[False, False]
        ).drop_duplicates(subset=["model_name"], keep="first")
    except Exception:
        return pd.DataFrame()


# ----------------------------------
# Sidebar
# ----------------------------------

symbols_df = load_symbols()

if symbols_df.empty:
    st.warning("No symbols found in symbols_master or market_data.")
    st.stop()

symbol_labels = symbols_df.apply(
    lambda row: f"{row['symbol']} - {row['name']}" if pd.notna(row["name"]) and row["name"] else row["symbol"],
    axis=1,
).tolist()
label_to_symbol = dict(zip(symbol_labels, symbols_df["symbol"]))

st.sidebar.markdown(
    dedent(
        f"""
        <div class="sidebar-title">
            <div class="sidebar-kicker">Workspace</div>
            <div class="sidebar-heading">Market Controls</div>
            <div class="news-meta" style="margin:0.1rem 0 0;">Tracked Symbols: {len(symbol_labels)}</div>
        </div>
        """
    ),
    unsafe_allow_html=True,
)

selected_label = st.sidebar.selectbox(
    "Select Stock / Ticker",
    symbol_labels,
)
symbol = label_to_symbol[selected_label]


# ----------------------------------
# Fetch
# ----------------------------------

prices = load_prices(symbol)
news = load_news(symbol)
prediction_df = load_latest_prediction(symbol)
model_predictions_df = load_model_predictions(symbol)
backtest_df = load_backtest_results(symbol)

if prices.empty:
    st.warning(f"No market data found for {symbol}.")
    st.stop()

latest_close = float(prices["close"].iloc[-1])
latest_high = float(prices["high"].iloc[-1])
latest_low = float(prices["low"].iloc[-1])
latest_volume = float(prices["volume"].iloc[-1]) if "volume" in prices and not pd.isna(prices["volume"].iloc[-1]) else 0.0
latest_date = pd.to_datetime(prices["date"].iloc[-1], errors="coerce")
latest_date_text = latest_date.strftime("%d %b %Y") if pd.notna(latest_date) else "-"
sentiment_avg = float(news["sentiment_score"].fillna(0).mean()) if not news.empty and "sentiment_score" in news.columns else 0.0
prediction_text = "Not available"
prediction_target = "-"
if not prediction_df.empty:
    p = prediction_df.iloc[0]
    pred_ret = float(p["predicted_return"]) * 100.0 if pd.notna(p["predicted_return"]) else 0.0
    prediction_text = f"{p['direction'].upper()} ({pred_ret:+.2f}%)"
    prediction_target = str(p["target_date"])

if not model_predictions_df.empty:
    ensemble_row = model_predictions_df[
        model_predictions_df["model_name"] == "ensemble_v1"
    ]
    if not ensemble_row.empty:
        p = ensemble_row.iloc[0]
        pred_ret = float(p["predicted_return"]) * 100.0 if pd.notna(p["predicted_return"]) else 0.0
        prediction_text = f"{p['direction'].upper()} ({pred_ret:+.2f}%)"
        prediction_target = str(p["target_date"])

indicator_consensus = compute_indicator_consensus(prices, sentiment_avg)
indicator_summary = indicator_consensus["summary"]
indicator_score = indicator_consensus["score"]
indicator_conf = indicator_consensus["confidence"] * 100.0
indicator_rows = indicator_consensus["rows"]
indicator_count = int(len(indicator_rows))

# ----------------------------------
# Layout
# ----------------------------------

prev_close = float(prices["close"].iloc[-2]) if len(prices) > 1 else latest_close
day_change_pct = ((latest_close - prev_close) / prev_close * 100.0) if prev_close else 0.0
day_change_text = f"{day_change_pct:+.2f}%"
day_change_color = "#15803d" if day_change_pct > 0 else ("#b91c1c" if day_change_pct < 0 else "#b45309")
day_range_text = f"{latest_low:,.2f} - {latest_high:,.2f}"
sentiment_color = "#15803d" if sentiment_avg > 0.1 else ("#b91c1c" if sentiment_avg < -0.1 else "#b45309")

model_order = [
    "sgd_regression_v1",
    "random_forest_v1",
    "extra_trees_v1",
    "xgboost_v1",
    "ensemble_v1",
]
model_label = {
    "sgd_regression_v1": "SGD",
    "random_forest_v1": "RF",
    "extra_trees_v1": "ET",
    "xgboost_v1": "XGB",
    "ensemble_v1": "ENS",
}

final_color = "#15803d"
if "BEARISH" in indicator_summary:
    final_color = "#b91c1c"
elif "NEUTRAL" in indicator_summary or "INSUFFICIENT" in indicator_summary:
    final_color = "#0f766e"

bull_count = int((indicator_rows["Signal"] == "Bullish").sum()) if not indicator_rows.empty else 0
bear_count = int((indicator_rows["Signal"] == "Bearish").sum()) if not indicator_rows.empty else 0
neutral_count = int((indicator_rows["Signal"] == "Neutral").sum()) if not indicator_rows.empty else 0

model_snapshot_rows = []
if not model_predictions_df.empty:
    for model_name in model_order:
        model_row = model_predictions_df[model_predictions_df["model_name"] == model_name]
        if model_row.empty:
            continue
        row = model_row.iloc[0]
        pred_ret = float(row["predicted_return"]) * 100.0 if pd.notna(row["predicted_return"]) else 0.0
        direction = str(row["direction"]).upper()
        model_snapshot_rows.append(
            {
                "Model": model_label.get(model_name, model_name),
                "Signal": direction,
                "Pred Return (%)": round(pred_ret, 2),
            }
        )

backtest_snapshot_rows = []
if not backtest_df.empty:
    for model_name in model_order:
        model_row = backtest_df[backtest_df["model_name"] == model_name]
        if model_row.empty:
            continue
        row = model_row.iloc[0]
        hit = float(row["directional_accuracy"]) * 100.0 if pd.notna(row["directional_accuracy"]) else 0.0
        strat_ret = float(row["strategy_return"]) * 100.0 if pd.notna(row["strategy_return"]) else 0.0
        backtest_snapshot_rows.append(
            {
                "Model": model_label.get(model_name, model_name),
                "Hit Rate (%)": round(hit, 1),
                "Strategy (%)": round(strat_ret, 2),
            }
        )

st.subheader("Decision Board")
decision_col, metric_col = st.columns([1.2, 1.0], gap="small")

with decision_col:
    st.markdown(
        dedent(
            f"""
            <div class="decision-card">
                <div class="snapshot-label">Primary Decision Signal</div>
                <div class="snapshot-value" style="color:{final_color}; font-size:1.28rem;">{indicator_summary}</div>
                <div class="news-meta">As of: {latest_date_text}</div>
                <div class="news-meta">ML Signal: {prediction_text}</div>
                <div class="news-meta">Composite: {indicator_score:+d} / {indicator_count} | Confidence: {indicator_conf:.1f}%</div>
                <div class="news-meta">Bullish: {bull_count} | Bearish: {bear_count} | Neutral: {neutral_count}</div>
            </div>
            """
        ),
        unsafe_allow_html=True,
    )

with metric_col:
    st.markdown(
        dedent(
            f"""
            <div class="metric-grid">
                <div class="snapshot-card">
                    <div class="snapshot-label">Last Close</div>
                    <div class="snapshot-value">{latest_close:,.2f}</div>
                </div>
                <div class="snapshot-card">
                    <div class="snapshot-label">Day Change</div>
                    <div class="snapshot-value" style="color:{day_change_color};">{day_change_text}</div>
                </div>
                <div class="snapshot-card">
                    <div class="snapshot-label">Day Range</div>
                    <div class="snapshot-value">{day_range_text}</div>
                </div>
                <div class="snapshot-card">
                    <div class="snapshot-label">Volume</div>
                    <div class="snapshot-value">{latest_volume:,.0f}</div>
                </div>
                <div class="snapshot-card">
                    <div class="snapshot-label">Avg Sentiment</div>
                    <div class="snapshot-value" style="color:{sentiment_color};">{sentiment_avg:+.2f}</div>
                </div>
                <div class="snapshot-card">
                    <div class="snapshot-label">ML Target</div>
                    <div class="snapshot-value">{prediction_target}</div>
                </div>
            </div>
            """
        ),
        unsafe_allow_html=True,
    )

main_col, side_col = st.columns([1.35, 0.9], gap="small")

with main_col:
    st.subheader(f"{symbol} Price Action")
    fig = go.Figure()
    fig.add_trace(go.Candlestick(
        x=prices["date"],
        open=prices["open"],
        high=prices["high"],
        low=prices["low"],
        close=prices["close"],
        name="Price",
        increasing_line_color="#16a34a",
        increasing_fillcolor="rgba(22,163,74,0.35)",
        decreasing_line_color="#dc2626",
        decreasing_fillcolor="rgba(220,38,38,0.35)",
    ))
    fig.update_layout(
        template="plotly_white",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="#f8fbff",
        font=dict(color="#0f172a", family="Source Sans 3"),
        xaxis_rangeslider_visible=False,
        margin=dict(l=8, r=8, t=8, b=8),
        height=360,
    )
    fig.update_xaxes(gridcolor="rgba(148,163,184,0.22)", linecolor="rgba(148,163,184,0.35)", tickfont=dict(size=12))
    fig.update_yaxes(gridcolor="rgba(148,163,184,0.24)", linecolor="rgba(148,163,184,0.35)", tickfont=dict(size=12))
    st.plotly_chart(fig, use_container_width=True)

with side_col:
    st.subheader("Model Snapshot")
    if model_snapshot_rows:
        st.dataframe(pd.DataFrame(model_snapshot_rows), use_container_width=True, hide_index=True)
    else:
        st.info("No model predictions available.")

    st.subheader("Backtest Snapshot")
    if backtest_snapshot_rows:
        st.dataframe(pd.DataFrame(backtest_snapshot_rows), use_container_width=True, hide_index=True)
    else:
        st.info("No backtest results available.")

bottom_col1, bottom_col2 = st.columns([1.25, 0.75], gap="small")

with bottom_col1:
    st.subheader("Indicator Breakdown")
    if not indicator_rows.empty:
        indicator_cards = []
        for _, row in indicator_rows.sort_values(by="Indicator").iterrows():
            signal = str(row["Signal"]).strip().lower()
            box_class = "indicator-neutral"
            if signal == "bullish":
                box_class = "indicator-bull"
            elif signal == "bearish":
                box_class = "indicator-bear"
            indicator_cards.append(
                f"""
                <div class="indicator-box {box_class}">
                    <div class="indicator-name">{row['Indicator']}</div>
                    <div class="indicator-signal">{row['Signal']}</div>
                </div>
                """
            )
        st.markdown(
            dedent(
                f"""
                <div class="indicator-grid">
                    {''.join(indicator_cards)}
                </div>
                """
            ),
            unsafe_allow_html=True,
        )

with bottom_col2:
    st.subheader("News Snapshot")
    if not news.empty:
        for _, row in news.head(2).iterrows():
            sentiment = (row.get("sentiment_label") or "neutral").lower()
            score = row.get("sentiment_score")
            color_map = {"positive": "#15803d", "negative": "#b91c1c", "neutral": "#ca8a04"}
            color = color_map.get(sentiment, "#ca8a04")
            score_text = f"{float(score):.2f}" if pd.notna(score) else "0.00"
            st.markdown(
                dedent(
                    f"""
                    <div class="news-card">
                        <div class="news-title">{row['title']}</div>
                        <div class="news-meta">Source: {row['source']}</div>
                        <div class="news-meta">
                            Sentiment: <span style="color:{color}; font-weight:700;">{sentiment.title()} ({score_text})</span>
                        </div>
                        <a class="news-link" href="{row['url']}" target="_blank">Read More</a>
                    </div>
                    """
                ),
                unsafe_allow_html=True,
            )
    else:
        st.info("No recent news")

with st.expander("Detailed Backtest Metrics", expanded=False):
    if not backtest_df.empty:
        backtest_view = backtest_df.copy()
        backtest_view["directional_accuracy"] = (
            pd.to_numeric(backtest_view["directional_accuracy"], errors="coerce") * 100.0
        ).round(2)
        backtest_view["mae"] = pd.to_numeric(backtest_view["mae"], errors="coerce").round(5)
        backtest_view["rmse"] = pd.to_numeric(backtest_view["rmse"], errors="coerce").round(5)
        backtest_view["strategy_return"] = (
            pd.to_numeric(backtest_view["strategy_return"], errors="coerce") * 100.0
        ).round(2)
        st.dataframe(
            backtest_view[["model_name", "run_date", "sample_count", "directional_accuracy", "mae", "rmse", "strategy_return"]]
            .rename(
                columns={
                    "model_name": "Model",
                    "run_date": "Run Date",
                    "sample_count": "Samples",
                    "directional_accuracy": "Hit Rate (%)",
                    "mae": "MAE",
                    "rmse": "RMSE",
                    "strategy_return": "Strategy Return (%)",
                }
            ),
            use_container_width=True,
            hide_index=True,
        )
    else:
        st.info("No backtest results available yet.")

with st.expander("More News", expanded=False):
    if not news.empty and len(news) > 2:
        for _, row in news.iloc[2:].iterrows():
            sentiment = (row.get("sentiment_label") or "neutral").lower()
            score = row.get("sentiment_score")
            color_map = {"positive": "#15803d", "negative": "#b91c1c", "neutral": "#ca8a04"}
            color = color_map.get(sentiment, "#ca8a04")
            score_text = f"{float(score):.2f}" if pd.notna(score) else "0.00"
            st.markdown(
                dedent(
                    f"""
                    <div class="news-card">
                        <div class="news-title">{row['title']}</div>
                        <div class="news-meta">Source: {row['source']}</div>
                        <div class="news-meta">
                            Sentiment: <span style="color:{color}; font-weight:700;">{sentiment.title()} ({score_text})</span>
                        </div>
                        <a class="news-link" href="{row['url']}" target="_blank">Read More</a>
                    </div>
                    """
                ),
                unsafe_allow_html=True,
            )
    elif news.empty:
        st.info("No recent news.")
    else:
        st.info("No additional news beyond the snapshot.")
