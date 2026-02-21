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
    page_title="QuantBrain",
    layout="wide"
)

st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Manrope:wght@400;500;600;700;800&family=DM+Sans:wght@400;500;700&display=swap');
    :root {
        --bg: #050812;
        --bg-2: #0b1020;
        --card: rgba(20, 28, 51, 0.76);
        --card-strong: #121a33;
        --card-border: rgba(82, 106, 166, 0.42);
        --text-main: #e6eeff;
        --text-dim: #9caed2;
        --accent: #30d5b8;
        --brand: #4c8bff;
        --brand-soft: rgba(76, 139, 255, 0.16);
        --pos: #3ee68d;
        --neg: #ff6a7a;
        --neu: #ffd35a;
        --shadow-sm: 0 10px 26px rgba(1, 4, 12, 0.52);
        --shadow-lg: 0 20px 44px rgba(0, 2, 8, 0.72);
    }
    .stApp {
        font-family: "DM Sans", "Segoe UI", sans-serif;
        color: var(--text-main);
        background:
            radial-gradient(1100px 560px at -10% -25%, rgba(76, 139, 255, 0.28), transparent 62%),
            radial-gradient(900px 520px at 115% -10%, rgba(48, 213, 184, 0.16), transparent 56%),
            linear-gradient(180deg, var(--bg) 0%, var(--bg-2) 100%);
    }
    .main .block-container {
        max-width: 1320px;
        padding-top: 0.55rem;
        padding-bottom: 0.65rem;
    }
    header[data-testid="stHeader"] {
        background: rgba(0, 0, 0, 0);
    }
    div[data-testid="stToolbar"] {
        background: rgba(0, 0, 0, 0);
    }
    section[data-testid="stSidebar"] {
        background: linear-gradient(180deg, #070c19 0%, #0a1122 72%, #080f1e 100%);
        border-right: 1px solid rgba(82, 106, 166, 0.34);
        box-shadow: inset -1px 0 0 rgba(76, 139, 255, 0.09);
    }
    section[data-testid="stSidebar"] label,
    section[data-testid="stSidebar"] p,
    section[data-testid="stSidebar"] .stMarkdown,
    section[data-testid="stSidebar"] [data-testid="stSelectbox"] {
        font-family: "Manrope", "Segoe UI", sans-serif;
    }
    section[data-testid="stSidebar"] [data-baseweb="select"] > div {
        background: linear-gradient(145deg, rgba(16, 25, 47, 0.96), rgba(14, 21, 41, 0.92)) !important;
        border: 1px solid rgba(82, 106, 166, 0.62) !important;
        border-radius: 10px !important;
        box-shadow: inset 0 0 0 1px rgba(76, 139, 255, 0.18), 0 4px 10px rgba(0, 0, 0, 0.34);
    }
    section[data-testid="stSidebar"] [data-baseweb="select"] span {
        color: #e6eeff !important;
        font-weight: 600;
    }
    section[data-testid="stSidebar"] [data-baseweb="select"] input {
        color: #e6eeff !important;
        background: transparent !important;
    }
    section[data-testid="stSidebar"] [data-baseweb="select"] svg {
        fill: #9fb0d4 !important;
    }
    div[data-baseweb="popover"],
    div[data-baseweb="popover"] > div,
    div[role="listbox"] {
        background: #0f1830 !important;
        border: 1px solid rgba(82, 106, 166, 0.62) !important;
        border-radius: 10px !important;
        box-shadow: 0 12px 24px rgba(0, 0, 0, 0.48) !important;
    }
    div[data-baseweb="popover"] ul,
    div[data-baseweb="popover"] li {
        background: transparent !important;
    }
    div[data-baseweb="popover"] [role="option"],
    div[role="listbox"] [role="option"] {
        color: #e6eeff !important;
        background: transparent !important;
        font-weight: 600 !important;
    }
    div[data-baseweb="popover"] [role="option"][aria-selected="true"],
    div[role="listbox"] [role="option"][aria-selected="true"] {
        background: rgba(76, 139, 255, 0.28) !important;
    }
    div[data-baseweb="popover"] [role="option"]:hover,
    div[role="listbox"] [role="option"]:hover {
        background: rgba(76, 139, 255, 0.20) !important;
    }
    h1, h2, h3 {
        font-family: "Manrope", "Segoe UI", sans-serif;
        letter-spacing: 0.01em;
        color: var(--text-main);
    }
    p, label, span, div {
        color: var(--text-main);
    }
    .app-title {
        position: relative;
        background: linear-gradient(145deg, rgba(30, 43, 78, 0.92), rgba(26, 37, 70, 0.78));
        border: 1px solid var(--card-border);
        border-radius: 12px;
        padding: 0.68rem 0.82rem;
        margin-bottom: 0.5rem;
        box-shadow: var(--shadow-sm);
        transition: transform 220ms ease, box-shadow 220ms ease;
        overflow: hidden;
    }
    .app-title::after {
        content: "";
        position: absolute;
        inset: 0 auto 0 0;
        width: 3px;
        background: linear-gradient(180deg, #4f8cff, #36d7b7);
    }
    .app-title:hover {
        transform: translateY(-3px) scale(1.004);
        box-shadow: var(--shadow-lg);
    }
    .app-kicker {
        color: var(--brand);
        font-size: 0.67rem;
        letter-spacing: 0.12em;
        text-transform: uppercase;
        font-weight: 800;
        margin-bottom: 0.2rem;
    }
    .app-heading {
        font-size: 1.45rem;
        line-height: 1.1;
        font-weight: 800;
        margin: 0;
    }
    .app-sub {
        color: var(--text-dim);
        margin-top: 0.22rem;
        font-size: 0.78rem;
    }
    .snapshot-card {
        background: linear-gradient(160deg, var(--card), rgba(26, 38, 70, 0.65));
        border: 1px solid var(--card-border);
        border-radius: 10px;
        padding: 8px 10px;
        margin-bottom: 7px;
        box-shadow: var(--shadow-sm);
        backdrop-filter: blur(12px);
        transition: transform 200ms ease, box-shadow 200ms ease, border-color 200ms ease;
    }
    .snapshot-card:hover {
        transform: translateY(-3px) scale(1.012);
        border-color: rgba(79, 140, 255, 0.60);
        box-shadow: var(--shadow-lg);
    }
    .snapshot-label {
        color: var(--text-dim);
        font-size: 0.68rem;
        text-transform: uppercase;
        letter-spacing: 0.06em;
        margin-bottom: 3px;
        font-weight: 700;
    }
    .snapshot-value {
        color: var(--text-main);
        font-size: 0.98rem;
        font-weight: 800;
    }
    .news-card {
        background: linear-gradient(160deg, rgba(26, 37, 70, 0.90), rgba(23, 34, 62, 0.74));
        border: 1px solid var(--card-border);
        border-radius: 10px;
        padding: 8px 10px;
        margin-bottom: 7px;
        box-shadow: var(--shadow-sm);
        backdrop-filter: blur(8px);
        transition: transform 200ms ease, box-shadow 200ms ease, border-color 200ms ease;
    }
    .news-card:hover {
        transform: translateY(-3px) scale(1.01);
        border-color: rgba(79, 140, 255, 0.60);
        box-shadow: var(--shadow-lg);
    }
    .news-title {
        color: var(--text-main);
        font-weight: 600;
        margin-bottom: 3px;
        font-size: 0.82rem;
        line-height: 1.2;
    }
    .news-meta {
        color: var(--text-dim);
        font-size: 0.73rem;
        margin-bottom: 4px;
    }
    .news-link {
        color: var(--brand);
        text-decoration: none;
        font-size: 0.78rem;
        font-weight: 700;
        border-bottom: 1px dashed rgba(79, 140, 255, 0.5);
    }
    .news-link:hover {
        border-bottom-color: rgba(79, 140, 255, 0.95);
    }
    .indicator-grid {
        display: grid;
        grid-template-columns: repeat(4, minmax(0, 1fr));
        gap: 6px;
        margin-bottom: 8px;
    }
    .indicator-box {
        border-radius: 10px;
        padding: 7px 8px;
        border: 1px solid transparent;
        box-shadow: var(--shadow-sm);
        transition: transform 170ms ease, box-shadow 170ms ease, border-color 170ms ease;
    }
    .indicator-box:hover {
        transform: translateY(-3px) scale(1.015);
        box-shadow: var(--shadow-lg);
    }
    div[data-testid="stPlotlyChart"] {
        background: linear-gradient(160deg, rgba(27,39,73,0.96), rgba(22,33,63,0.86));
        border: 1px solid var(--card-border);
        border-radius: 12px;
        padding: 8px;
        box-shadow: var(--shadow-sm);
        transition: transform 180ms ease, box-shadow 180ms ease;
    }
    div[data-testid="stPlotlyChart"] .js-plotly-plot,
    div[data-testid="stPlotlyChart"] .plot-container,
    div[data-testid="stPlotlyChart"] .svg-container {
        background: transparent !important;
    }
    div[data-testid="stPlotlyChart"]:hover {
        transform: translateY(-3px) scale(1.004);
        box-shadow: var(--shadow-lg);
    }
    .indicator-name {
        font-size: 0.69rem;
        font-weight: 700;
        margin-bottom: 2px;
    }
    .indicator-signal {
        font-size: 0.8rem;
        font-weight: 800;
    }
    h3 {
        font-size: 1.02rem !important;
        margin-top: 0.25rem !important;
        margin-bottom: 0.25rem !important;
    }
    div[data-testid="stHeading"] {
        margin-top: 0.12rem !important;
        margin-bottom: 0.18rem !important;
    }
    .indicator-bull {
        background: linear-gradient(150deg, rgba(46, 175, 118, 0.24), rgba(25, 112, 76, 0.20));
        border-color: rgba(62, 230, 141, 0.58);
        color: var(--pos);
    }
    .indicator-bear {
        background: linear-gradient(150deg, rgba(255, 106, 122, 0.26), rgba(137, 33, 48, 0.22));
        border-color: rgba(255, 122, 139, 0.62);
        color: var(--neg);
    }
    .indicator-neutral {
        background: linear-gradient(150deg, rgba(255, 211, 90, 0.25), rgba(150, 108, 24, 0.20));
        border-color: rgba(255, 211, 90, 0.65);
        color: var(--neu);
    }
    .stDataFrame, .stTable {
        border: 1px solid var(--card-border);
        border-radius: 10px;
        overflow: hidden;
    }
    @media (max-width: 900px) {
        .app-heading {
            font-size: 1.45rem;
        }
        .indicator-grid {
            grid-template-columns: repeat(2, minmax(0, 1fr));
        }
    }
    @media (max-width: 560px) {
        .indicator-grid {
            grid-template-columns: repeat(1, minmax(0, 1fr));
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
    atr14 = tr.rolling(14).mean()
    atr_ratio = atr14 / close.replace(0, pd.NA)
    atr_baseline = atr_ratio.rolling(20).mean()

    obv = ((close.diff().fillna(0).apply(lambda x: 1 if x > 0 else (-1 if x < 0 else 0))) * volume).cumsum()
    obv_slope = obv.diff(5)

    volume_ratio = volume / volume.rolling(20).mean().replace(0, pd.NA)
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

    idx = df.index[-1]
    indicator_rows = []

    def add_indicator(name, bullish, bearish):
        if bullish:
            indicator_rows.append({"Indicator": name, "Signal": "Bullish", "Score": 1})
        elif bearish:
            indicator_rows.append({"Indicator": name, "Signal": "Bearish", "Score": -1})
        else:
            indicator_rows.append({"Indicator": name, "Signal": "Neutral", "Score": 0})

    add_indicator("SMA 5/20", sma5.loc[idx] > sma20.loc[idx], sma5.loc[idx] < sma20.loc[idx])
    add_indicator("EMA 12/26", ema12.loc[idx] > ema26.loc[idx], ema12.loc[idx] < ema26.loc[idx])
    add_indicator("RSI 14", rsi14.loc[idx] < 35, rsi14.loc[idx] > 70)
    add_indicator("MACD Histogram", macd_hist.loc[idx] > 0, macd_hist.loc[idx] < 0)
    add_indicator("Bollinger Position", bb_pos.loc[idx] < 0.2, bb_pos.loc[idx] > 0.8)
    add_indicator("Stochastic %K", stoch_k.loc[idx] < 20, stoch_k.loc[idx] > 80)
    add_indicator("Williams %R", williams_r.loc[idx] < -80, williams_r.loc[idx] > -20)
    add_indicator("ROC 10", roc10.loc[idx] > 0, roc10.loc[idx] < 0)
    add_indicator("Momentum 10", momentum10.loc[idx] > 0, momentum10.loc[idx] < 0)
    add_indicator("ATR Regime", atr_ratio.loc[idx] < atr_baseline.loc[idx], atr_ratio.loc[idx] > atr_baseline.loc[idx] * 1.2)
    add_indicator("OBV Slope", obv_slope.loc[idx] > 0, obv_slope.loc[idx] < 0)
    add_indicator("Volume Ratio", volume_ratio.loc[idx] > 1.1, volume_ratio.loc[idx] < 0.9)
    add_indicator("Volatility Regime", vol_regime.loc[idx] < 1.0, vol_regime.loc[idx] > 1.3)
    add_indicator("CCI 20", cci20.loc[idx] < -100, cci20.loc[idx] > 100)
    add_indicator(
        "ADX Trend",
        (plus_di.loc[idx] > minus_di.loc[idx]) and (adx14.loc[idx] > 20),
        (plus_di.loc[idx] < minus_di.loc[idx]) and (adx14.loc[idx] > 20),
    )
    add_indicator("News Sentiment", sentiment_score > 0.1, sentiment_score < -0.1)

    result_df = pd.DataFrame(indicator_rows)
    result_df["Score"] = pd.to_numeric(result_df["Score"], errors="coerce").fillna(0).astype(int)
    total_score = int(result_df["Score"].sum())
    max_abs_score = len(result_df)
    confidence = abs(total_score) / max_abs_score if max_abs_score else 0.0

    if total_score >= 5:
        summary = "STRONG BULLISH"
    elif total_score >= 2:
        summary = "BULLISH"
    elif total_score <= -5:
        summary = "STRONG BEARISH"
    elif total_score <= -2:
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
        <div class="app-kicker">Quant Research Lab</div>
        <h1 class="app-heading">QuantBrain</h1>
        <div class="app-sub">Turning Noise into Intelligence.</div>
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

selected_label = st.sidebar.selectbox(
    "Select Stock",
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

if prices.empty:
    st.warning(f"No market data found for {symbol}.")
    st.stop()

latest_close = float(prices["close"].iloc[-1])
latest_high = float(prices["high"].iloc[-1])
latest_low = float(prices["low"].iloc[-1])
latest_volume = float(prices["volume"].iloc[-1]) if "volume" in prices and not pd.isna(prices["volume"].iloc[-1]) else 0.0
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
day_range_text = f"{latest_low:,.2f} - {latest_high:,.2f}"

st.subheader("Executive Summary")
st.markdown(
    dedent(
        f"""
        <div class="indicator-grid">
            <div class="snapshot-card">
                <div class="snapshot-label">Last Close</div>
                <div class="snapshot-value">{latest_close:,.2f}</div>
            </div>
            <div class="snapshot-card">
                <div class="snapshot-label">Day Change</div>
                <div class="snapshot-value">{day_change_text}</div>
            </div>
            <div class="snapshot-card">
                <div class="snapshot-label">ML Prediction</div>
                <div class="snapshot-value">{prediction_text}</div>
            </div>
            <div class="snapshot-card">
                <div class="snapshot-label">Indicator Consensus</div>
                <div class="snapshot-value">{indicator_summary}</div>
            </div>
        </div>
        """
    ),
    unsafe_allow_html=True,
)

st.subheader("🤖 AI Model Outputs")
model_order = ["logistic_v1", "random_forest_v1", "xgboost_v1", "ensemble_v1"]
model_label = {
    "logistic_v1": "Logistic",
    "random_forest_v1": "Random Forest",
    "xgboost_v1": "XGBoost",
    "ensemble_v1": "Ensemble",
}
if not model_predictions_df.empty:
    model_cards = []
    for model_name in model_order:
        model_row = model_predictions_df[model_predictions_df["model_name"] == model_name]
        if model_row.empty:
            continue
        row = model_row.iloc[0]
        pred_ret = float(row["predicted_return"]) * 100.0 if pd.notna(row["predicted_return"]) else 0.0
        direction = str(row["direction"]).upper()
        color = "#ca8a04"
        if direction == "UP":
            color = "#15803d"
        elif direction == "DOWN":
            color = "#b91c1c"
        model_cards.append(
            f"""
            <div class="snapshot-card">
                <div class="snapshot-label">{model_label.get(model_name, model_name)}</div>
                <div class="snapshot-value" style="color:{color};">{direction} ({pred_ret:+.2f}%)</div>
            </div>
            """
        )
    st.markdown(
        dedent(
            f"""
            <div class="indicator-grid">
                {''.join(model_cards)}
            </div>
            """
        ),
        unsafe_allow_html=True,
    )
else:
    st.info("No model predictions available.")

detail_col1, detail_col2 = st.columns([1, 1], gap="small")

with detail_col1:
    st.subheader("📊 Indicator-Wise Breakdown")
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

with detail_col2:
    st.subheader("🎯 Final Prediction")
    final_color = "#15803d"
    if "BEARISH" in indicator_summary:
        final_color = "#b91c1c"
    elif "NEUTRAL" in indicator_summary or "INSUFFICIENT" in indicator_summary:
        final_color = "#0f766e"

    bull_count = int((indicator_rows["Signal"] == "Bullish").sum()) if not indicator_rows.empty else 0
    bear_count = int((indicator_rows["Signal"] == "Bearish").sum()) if not indicator_rows.empty else 0
    neutral_count = int((indicator_rows["Signal"] == "Neutral").sum()) if not indicator_rows.empty else 0

    st.markdown(
        dedent(
            f"""
            <div class="news-card">
                <div class="news-meta">Primary Decision Signal</div>
                <div class="snapshot-value" style="color:{final_color};">{indicator_summary}</div>
                <div class="news-meta">Composite Score: {indicator_score:+d} / {indicator_count} indicators</div>
                <div class="news-meta">Confidence: {indicator_conf:.1f}% | Day Range: {day_range_text}</div>
                <div class="news-meta">Bullish: {bull_count} | Bearish: {bear_count} | Neutral: {neutral_count}</div>
            </div>
            """
        ),
        unsafe_allow_html=True,
    )

col1, col2 = st.columns([1, 1], gap="small")

with col1:
    st.subheader(f"{symbol} Price Chart")
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
        template="plotly_dark",
        paper_bgcolor="#162342",
        plot_bgcolor="#131d36",
        font=dict(color="#dbe8ff"),
        xaxis_rangeslider_visible=False,
        margin=dict(l=8, r=8, t=10, b=8),
    )
    fig.update_xaxes(gridcolor="rgba(116,143,199,0.22)")
    fig.update_yaxes(gridcolor="rgba(116,143,199,0.24)")
    st.plotly_chart(fig, use_container_width=True)

with col2:
    st.subheader("Priority Feed")
    st.markdown(
        dedent(
            f"""
            <div class="snapshot-card">
                <div class="snapshot-label">Volume</div>
                <div class="snapshot-value">{latest_volume:,.0f}</div>
            </div>
            <div class="snapshot-card">
                <div class="snapshot-label">Avg Sentiment</div>
                <div class="snapshot-value">{sentiment_avg:+.2f}</div>
            </div>
            <div class="snapshot-card">
                <div class="snapshot-label">ML Target Date</div>
                <div class="snapshot-value">{prediction_target}</div>
            </div>
            """
        ),
        unsafe_allow_html=True,
    )

    if not news.empty:
        for _, row in news.head(3).iterrows():
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
                        <div class="news-meta">Sentiment: <span style="color:{color};font-weight:700;">{sentiment.title()} ({score_text})</span></div>
                    </div>
                    """
                ),
                unsafe_allow_html=True,
            )

st.subheader("📰 Full News")
if not news.empty:
    for _, row in news.iterrows():
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
