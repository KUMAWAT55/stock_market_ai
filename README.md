# TradeIQ (Stock Market AI Platform)

A Python-based intraday analytics platform for NSE symbols that combines:
- market data ingestion,
- news + sentiment processing,
- ML prediction pipelines,
- walk-forward backtesting,
- and a gated Streamlit decision dashboard with user auth, subscription, and compliance controls.

This repository is optimized for fast experimentation and iterative model updates on short-horizon market data.

## 1. Scope and What the Project Does
https://app.eraser.io/workspace/n3p718P4tKA18NW737ZS?diagram=ZHK8-Xp1pkm5A-eAKd9X8

TradeIQ runs a full data-to-dashboard workflow:
1. Pull selected NSE symbol metadata.
2. Fetch intraday OHLCV bars from Yahoo Finance.
3. Fetch recent symbol news from Google News RSS.
4. Score sentiment using a lexicon-based NLP module.
5. Persist normalized data into PostgreSQL using SQLAlchemy + Postgres upserts.
6. Train multiple regression models to predict:
- next bar return, and
- next session close return.
7. Run walk-forward backtests with model-wise and ensemble metrics.
8. Render a portal dashboard (with authentication + gating) that shows model snapshots, indicator consensus, candlestick chart, and news.

## 2. High-Level Architecture

### 2.1 Layers

1. Ingestion Layer
- `src/ingestion/nse/symbols.py`
- `src/ingestion/yahoo/fetcher.py`
- `src/ingestion/news/fetcher.py`

2. Processing Layer
- `src/pipelines/normalizer.py`
- `src/pipelines/sentiment.py`
- `src/pipelines/predictor.py`
- `src/pipelines/backtester.py`
- `src/pipelines/news_loader.py`

3. Storage Layer
- `src/storage/db/connection.py`
- `src/storage/db/models.py`
- `src/storage/db/writer.py`
- `src/storage/db/maintenance.py`
- `src/storage/db/manage_tables.py`

4. Presentation Layer
- `src/ui/dashboard.py`

### 2.2 Runtime Flow (Pipeline Entrypoint)

Pipeline entrypoint: `src/main.py`

Execution sequence:
1. Initialize logging (`loguru`) to `logs/ui.log`.
2. Open DB session and create tables from ORM metadata.
3. Run DB maintenance:
- deduplicate rows if unique indexes are missing,
- enforce unique indexes,
- drop legacy market columns to keep intraday schema aligned.
4. Fetch and save selected NSE symbols.
5. Query active symbols.
6. For each symbol:
- compute incremental start timestamp from latest stored candle (`latest_ts - 2 days` overlap),
- fetch Yahoo intraday history (`60d`, `5m` by default),
- normalize and upsert market bars,
- fetch RSS news and upsert news rows,
- load historical price/news frames,
- run next-bar and next-session-close predictions,
- save predictions (model-wise + ensemble),
- run walk-forward backtests,
- save backtest metrics.
7. Close DB session.

## 3. Repository Structure

```text
src/
  main.py                         # End-to-end orchestration
  configs/
    settings.py                   # Runtime constants
  ingestion/
    nse/symbols.py                # NSE symbol list loader (filtered universe)
    yahoo/fetcher.py              # Yahoo OHLCV fetcher
    news/fetcher.py               # Google News RSS fetcher
  pipelines/
    normalizer.py                 # Yahoo -> DB record normalization
    sentiment.py                  # Lexicon sentiment scorer
    news_loader.py                # News upsert writer
    predictor.py                  # Feature engineering + model inference
    backtester.py                 # Walk-forward backtesting
  storage/db/
    connection.py                 # SQLAlchemy engine + SessionLocal
    models.py                     # ORM models (all platform tables)
    writer.py                     # Data access and upsert helpers
    maintenance.py                # Dedup/index/scheme alignment tasks
    manage_tables.py              # Table create/drop CLI utility
  ui/
    dashboard.py                  # Streamlit app (auth + compliance + analytics UI)

requirements.txt                  # Python dependencies
market_data.sql                   # SQL DDL reference (legacy + current concepts)
```

## 4. Configuration

File: `src/configs/settings.py`

| Variable | Default | Purpose |
|---|---|---|
| `DB_URL` | `postgresql://localhost:5432/stock_market_ai` | SQLAlchemy connection string |
| `LOG_PATH` | `logs/ui.log` | File sink for `loguru` logs |
| `YAHOO_PERIOD` | `60d` | History window when `start/end` not provided |
| `YAHOO_INTERVAL` | `5m` | Intraday candle granularity |
| `BACKTEST_MIN_TRAIN_ROWS` | `100` | Minimum rows before backtesting |
| `BACKTEST_STEP` | `4` | Evaluate every Nth point |
| `BACKTEST_TRAIN_WINDOW` | `260` | Rolling train window length |
| `BACKTEST_MAX_EVAL_POINTS` | `80` | Cap on evaluation points |

Environment variable used by dashboard:
- `TRADEIQ_SUBSCRIPTION_CODE`
- Default fallback: `TRADEIQ-PRO-2026`

## 5. Data Ingestion Details

### 5.1 NSE Symbol Master (`src/ingestion/nse/symbols.py`)

- Source: `https://archives.nseindia.com/content/equities/EQUITY_L.csv`
- Current universe is intentionally filtered to 20 symbols:
- `ADANIENT`, `ADANIPORTS`, `ASIANPAINT`, `AXISBANK`, `BAJFINANCE`, `BHARTIARTL`, `HCLTECH`, `HDFCBANK`, `HINDUNILVR`, `ICICIBANK`, `INFY`, `ITC`, `KOTAKBANK`, `LT`, `MARUTI`, `RELIANCE`, `SBIN`, `TATAMOTORS`, `TECHM`, `TCS`
- Saves symbol metadata fields into `symbols_master`.

### 5.2 Yahoo Market Fetch (`src/ingestion/yahoo/fetcher.py`)

- Uses `yfinance.Ticker(symbol).history(...)`.
- Supports either:
- `period + interval`, or
- `start/end + interval` for incremental fetch.
- Returns `(hist_df, info)` or `(None, None)` on failure.

### 5.3 News Fetch (`src/ingestion/news/fetcher.py`)

- Source: Google News RSS search query (`"<symbol> NSE stock"`).
- Parses feed entries via `feedparser`.
- Default cap: `max_results=5` per symbol per run.
- Converts published time to UTC-naive `datetime`.
- Runs sentiment scoring on title + summary.

## 6. Normalization and Sentiment

### 6.1 Market Data Normalization (`src/pipelines/normalizer.py`)

For each Yahoo row:
- timestamp from `Datetime` (intraday) or `Date` (fallback),
- timezone removed to store consistent naive datetimes,
- mapped to canonical fields:
- `open`, `high`, `low`, `close`, `volume`,
- derived:
- `traded_value = close * volume`,
- `vwap = (high + low + close) / 3`,
- static source: `source='yahoo'`.

### 6.2 Sentiment Engine (`src/pipelines/sentiment.py`)

- Rule-based lexicon approach (positive and negative token sets).
- Preprocessing:
- HTML unescape,
- tag removal,
- URL removal,
- whitespace normalization,
- lowercase.
- Tokenization: regex `[a-z]+`.
- Score:
- `(pos_count - neg_count) / (pos_count + neg_count)`
- Label mapping:
- `>= 0.2` -> `positive`
- `<= -0.2` -> `negative`
- otherwise `neutral`

## 7. Feature Engineering and Prediction Engine

File: `src/pipelines/predictor.py`

### 7.1 Feature Set (`FEATURE_COLUMNS`)

1. `ret_1bar` - 1-bar close return.
2. `ret_3bar` - 3-bar close return.
3. `ret_12bar` - 12-bar close return.
4. `hl_spread` - `(high - low) / close`.
5. `oc_change` - `(close - open) / open`.
6. `volume_chg` - 1-bar volume percentage change.
7. `ma5_ratio` - `close / MA(5) - 1`.
8. `ma20_ratio` - `close / MA(20) - 1`.
9. `volatility_20bar` - rolling std of returns.
10. `volume_zscore_20` - rolling z-score of volume.
11. `minute_sin` - cyclical intraday phase (sin).
12. `minute_cos` - cyclical intraday phase (cos).
13. `session_progress` - normalized day progress.
14. `sentiment_6h` - rolling 6-hour mean news sentiment, merged with `merge_asof` (6-hour tolerance).

### 7.2 Targets

- Next bar target:
- `target_return = close.shift(-1) / close - 1`
- `target_class = target_return > 0` (auxiliary)

- Next session close target:
- `next_session_close` computed from day-level last close shifted by one session.
- `target_next_close_return = next_session_close / close - 1`

### 7.3 Data Safety and Cleansing

- Numeric coercion (`pd.to_numeric(..., errors='coerce')`).
- Zero-safe denominators using `replace(0, np.nan)`.
- Replace `inf/-inf` with `NaN`.
- Keep only finite training rows.

### 7.4 Train/Test Protocol

- Chronological split:
- first 80% train,
- last 20% test.
- Minimum rows required: `60`.
- Last finite feature row is used for inference.

### 7.5 Models

1. `sgd_regression_v1`
- `StandardScaler + SGDRegressor`
- `loss='huber'`, `penalty='elasticnet'`

2. `random_forest_v1`
- `RandomForestRegressor`
- `n_estimators=280`, `max_depth=6`, `min_samples_leaf=3`

3. `extra_trees_v1`
- `ExtraTreesRegressor`
- `n_estimators=320`, `max_depth=7`, `min_samples_leaf=2`

4. `xgboost_v1` (optional)
- `XGBRegressor` if import/runtime succeeds.
- Graceful skip with warning if unavailable.

5. `ensemble_v1`
- Mean predicted return across available base models.
- Score is mean of available model R2 scores.

Next-session-close variants are also generated:
- `sgd_next_close_v1`
- `random_forest_next_close_v1`
- `extra_trees_next_close_v1`
- `xgboost_next_close_v1`
- `ensemble_next_close_v1`

### 7.6 Direction Mapping

- `predicted_return > +0.1%` -> `up`
- `predicted_return < -0.1%` -> `down`
- otherwise -> `flat`

### 7.7 Target Timestamp Logic

- Intraday data uses median intraday delta and inferred session bounds to find next valid target timestamp.
- Daily fallback uses next business day.
- Next-session-close target is inferred from observed session close times.

## 8. Backtesting Engine

File: `src/pipelines/backtester.py`

Method: walk-forward evaluation on chronological data.

Behavior:
1. Build same features as production model path.
2. Start evaluation from `min_train_rows`.
3. At each evaluation index:
- fit each model on rolling window,
- predict one-step ahead,
- store true and predicted return.
4. Align to shared evaluation points across all active models.
5. Compute metrics per model and ensemble.

Metrics saved:
- `sample_count`
- `directional_accuracy`
- `mae`
- `rmse`
- `avg_true_return`
- `avg_pred_return`
- `cumulative_return` (market curve)
- `strategy_return` (sign(pred) * true return curve)

## 9. Database Schema (ORM Source of Truth)

Primary schema is in `src/storage/db/models.py`.

### 9.1 `symbols_master`
- Unique symbol metadata.
- Unique: `symbol`.

### 9.2 `market_data`
- Intraday OHLCV records.
- Unique: `(symbol, date, source)`.

### 9.3 `market_news`
- News + sentiment records.
- Unique: `(symbol, title, published_at)`.

### 9.4 `stock_predictions`
- Model prediction outputs.
- Unique: `(symbol, target_date, model_name)`.

### 9.5 `model_backtest_results`
- Backtest metrics per model and run date.
- Unique: `(symbol, model_name, run_date)`.

### 9.6 `app_users`
- Portal users with password hash.
- Unique: `username`, `email`.

### 9.7 `user_subscriptions`
- One active subscription row per user.
- Unique: `user_id`.

### 9.8 `compliance_consents`
- User acceptance of policy version.
- Unique: `(user_key, disclaimer_version)`.

### 9.9 `compliance_audit_logs`
- Immutable audit event records.

## 10. Storage and Deduplication Mechanics

### 10.1 Upserts (`src/storage/db/writer.py`, `src/pipelines/news_loader.py`)

- Uses Postgres dialect `insert(...).on_conflict_do_update(...)`.
- Pre-upsert payload dedupe performed in Python dict keyed by unique columns.

### 10.2 Maintenance (`src/storage/db/maintenance.py`)

- `clean_and_enforce_uniqueness(session)`
- checks expected unique indexes,
- if missing, removes duplicates using SQL window rank over `ctid`,
- recreates unique indexes.

- `align_market_data_intraday_schema(session)`
- drops legacy fundamental/corporate-action columns from `market_data` if present,
- keeps schema aligned with current intraday-only pipeline.

## 11. Dashboard and Product Controls

File: `src/ui/dashboard.py`

### 11.1 UI Stack

- Streamlit app layout + forms/dialogs.
- Plotly candlestick chart.
- Custom CSS theme with responsive behavior.
- Cached loaders with `@st.cache_data` and `@st.cache_resource`.

### 11.2 Authentication

- User registration + login forms.
- Password hashing:
- algorithm: PBKDF2-HMAC-SHA256,
- iterations: `260000`,
- random 16-byte salt,
- constant-time compare via `hmac.compare_digest`.

### 11.3 Subscription Gate

- Plan: `TradeIQ Pro`.
- Duration: `30 days` on activation.
- Requires matching subscription code and payment reference input.
- If inactive, model predictions/backtests are locked in the UI.

### 11.4 Compliance Gate

- Versioned disclaimer key: `sebi_phase1_v1_2026-02-22`.
- User must accept policy checkbox and submit consent.
- Audit events are recorded for auth and access actions.
- If compliance missing, predictions remain locked.

### 11.5 Indicator Consensus Engine (`compute_indicator_consensus`)

Input requirements:
- at least 60 price rows.

Indicators used (20 total):
1. SMA 5/20
2. EMA 9/21
3. RSI 14
4. MACD Histogram
5. Bollinger Position
6. Stochastic %K
7. Williams %R
8. ROC 10
9. Momentum 10
10. OBV Slope
11. Price-Volume Impulse
12. Volatility Regime
13. CCI 20
14. ADX Trend
15. VWAP Bias
16. VWAP Slope
17. MFI 14
18. Donchian Breakout
19. Session Open Bias
20. News Sentiment

Scoring:
- Bullish = `+1`
- Bearish = `-1`
- Neutral = `0`

Summary thresholds:
- `>= +7` -> `STRONG BULLISH`
- `+3 to +6` -> `BULLISH`
- `-3 to -6` -> `BEARISH`
- `<= -7` -> `STRONG BEARISH`
- otherwise -> `NEUTRAL`

Confidence:
- `abs(total_score) / indicator_count`

### 11.6 Dashboard Data Panels

- Decision board and diagnostics.
- Price candlestick plot.
- Model snapshots:
- next-bar models,
- next-day-close models,
- backtest snapshot.
- Indicator card grid.
- News snapshot and expandable full feed.
- Detailed backtest expander.

## 12. SQL Utilities and CLI

### 12.1 Table Management Utility

File: `src/storage/db/manage_tables.py`

Examples:
- Create all tables:
```bash
python -m src.storage.db.manage_tables create
```
- Drop one table:
```bash
python -m src.storage.db.manage_tables delete market_news
```
- Create selected tables:
```bash
python -m src.storage.db.manage_tables create market_data market_news stock_predictions
```

### 12.2 `market_data.sql`

- Provides a SQL DDL reference script.
- Note: some columns in this script are legacy and are dropped by runtime maintenance to align with current intraday schema.

## 13. Setup and Run

### 13.1 Prerequisites

- Python 3.10+
- PostgreSQL (running and reachable)
- Network access for NSE CSV, Yahoo Finance, Google News RSS

### 13.2 Installation

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 13.3 Configure

- Update `DB_URL` in `src/configs/settings.py` for your local Postgres user/password/host.
- Optional: export `TRADEIQ_SUBSCRIPTION_CODE` for dashboard activation flow.

### 13.4 Run Pipeline

```bash
python -m src.main
```

### 13.5 Run Dashboard

```bash
streamlit run src/ui/dashboard.py
```

## 14. Logging and Observability

- Logger: `loguru`.
- File sink: `logs/ui.log`.
- Pipeline logs include fetch status, save status, skipped models, and backtest progress.

## 15. Known Limitations and Risks

1. Dashboard SQL loaders currently use f-string SQL; parameterized SQL should replace this for stronger safety.
2. Symbol universe is hardcoded to 20 NSE symbols in ingestion.
3. No automated unit/integration test suite in repository yet.
4. No migration framework (for example Alembic) is wired; schema evolution is managed through ORM + runtime maintenance.
5. Sentiment model is lexicon-based and does not capture advanced context/negation nuances.
6. Backtest is single-step walk-forward and does not model slippage/fees/latency/execution constraints.

## 16. Quick Troubleshooting

### 16.1 `ModuleNotFoundError: src`

Run commands from repository root using module mode, for example:
- `python -m src.main`

### 16.2 Empty predictions in dashboard

Check:
1. Pipeline has inserted enough intraday rows (minimum training rows).
2. Subscription is active.
3. Compliance consent is accepted.

### 16.3 Yahoo/NSE/news fetch failures

- Verify internet/network availability.
- Verify provider endpoints are reachable from your environment.

### 16.4 DB uniqueness/index conflicts

- Run pipeline once; maintenance routines will dedupe and re-apply expected unique indexes.

## 17. Dependency Stack (`requirements.txt`)

- Data and numerics: `pandas`, `numpy`
- Market/news ingestion: `yfinance`, `requests`, `feedparser`
- DB and ORM: `sqlalchemy`, `psycopg2-binary`
- ML: `scikit-learn`, `xgboost`
- UI and visualization: `streamlit`, `plotly`, `altair`
- Logging: `loguru`

## 18. Glossary

- OHLCV: Open, High, Low, Close, Volume.
- VWAP: Volume Weighted Average Price.
- RSI: Relative Strength Index.
- MACD: Moving Average Convergence Divergence.
- MFI: Money Flow Index.
- ADX: Average Directional Index.
- Ensemble Model: Average of multiple model predictions.
- Walk-forward Backtest: sequentially retraining and evaluating on future points.

## 19. Current Product Position

TradeIQ is a strong research-focused intraday analytics platform with:
- robust ingestion and upsert persistence,
- multi-model return forecasting,
- model monitoring via walk-forward snapshots,
- user/account/compliance controls in the UI,
- and a practical dashboard for operational decision support.

For technical-stack deep dive at concept/skill level, see `TECHNICAL_STACK.md`.
