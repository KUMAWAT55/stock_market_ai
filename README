# Stock Market AI Platform - Full Project Documentation

## 1. Project Overview
The Stock Market AI Platform is a data pipeline + analytics dashboard system that ingests stock market data and news, computes sentiment and predictive signals, stores everything in PostgreSQL, and visualizes decision-ready insights in Streamlit.

Primary goals:
- Ingest reliable market and news data.
- Store normalized historical records for analysis.
- Generate model-based next-day predictions.
- Generate indicator-based consensus prediction.
- Present all outputs in a business-facing dashboard.

---

## 2. High-Level Architecture
The system has four layers:

1. Ingestion Layer
- Fetches NSE symbols.
- Fetches OHLCV + fundamentals from Yahoo Finance.
- Fetches related news from Google News RSS.

2. Processing Layer
- Normalizes raw Yahoo data into DB-ready records.
- Computes sentiment score/label from article text.
- Builds ML features and runs multiple prediction models.
- Computes technical-indicator consensus.

3. Storage Layer
- Uses SQLAlchemy ORM for table models and DB writes.
- Stores symbols, market data, news, and predictions.

4. Presentation Layer
- Streamlit dashboard with themed UI.
- Shows executive summary, model outputs, indicator breakdown, chart, and news.

---

## 3. Repository Structure

- `src/main.py` - Main orchestration pipeline.
- `src/configs/settings.py` - Runtime constants (DB URL, log path, Yahoo period).
- `src/ingestion/nse/symbols.py` - NSE symbol fetch.
- `src/ingestion/yahoo/fetcher.py` - Yahoo data fetch.
- `src/ingestion/news/fetcher.py` - News RSS fetch + sentiment mapping.
- `src/pipelines/normalizer.py` - Yahoo data normalization.
- `src/pipelines/sentiment.py` - Lexicon-based sentiment scoring.
- `src/pipelines/news_loader.py` - News persistence.
- `src/pipelines/predictor.py` - Multi-model prediction pipeline.
- `src/storage/db/connection.py` - SQLAlchemy engine/session.
- `src/storage/db/models.py` - ORM models.
- `src/storage/db/writer.py` - DB write/read helper functions.
- `src/storage/db/manage_tables.py` - CLI table create/drop utility.
- `src/ui/dashboard.py` - Streamlit dashboard.
- `market_data.sql` - SQL DDL script.
- `requirements.txt` - Python dependencies.

---

## 4. Data Model and Tables

### 4.1 `symbols_master`
Purpose: master list of tradable symbols.

Core columns:
- `symbol` (unique)
- `name`
- `exchange`, `series`
- listing metadata (`date_of_listing`, `isin_number`, etc.)
- `active`

### 4.2 `market_data`
Purpose: daily historical market records.

Core columns:
- key fields: `symbol`, `date`, `source`
- OHLC: `open`, `high`, `low`, `close`, `adj_close`
- volume/value: `volume`, `traded_value`, `vwap`
- corp actions: `dividend`, `split`
- fundamentals: `market_cap`, `pe_ratio`, `eps`, etc.
- metadata: `sector`, `industry`, `exchange`, `currency`

Constraint:
- Unique (`symbol`, `date`, `source`)

### 4.3 `market_news`
Purpose: news and sentiment records.

Core columns:
- `symbol`, `title`, `summary`, `url`, `source`, `published_at`
- sentiment: `sentiment_score`, `sentiment_label`

### 4.4 `stock_predictions`
Purpose: model prediction records (multiple models per symbol/date).

Core columns:
- `symbol`, `prediction_date`, `target_date`
- outputs: `predicted_return`, `predicted_close`, `direction`
- metadata: `model_name`, `train_rows`, `r2_score`, `created_at`

Model names currently used:
- `logistic_v1`
- `random_forest_v1`
- `xgboost_v1` (if available)
- `ensemble_v1`

---

## 5. Ingestion and Processing Flow

Pipeline entrypoint: `src/main.py`.

Execution sequence:
1. Load symbol list from NSE.
2. Save symbol list into `symbols_master`.
3. Read active symbols.
4. For each symbol (currently limited to first 10):
   - Fetch Yahoo market data.
   - Normalize and save market rows.
   - Fetch RSS news.
   - Save news rows.
   - Load symbol historical price/news from DB.
   - Run multi-model prediction.
   - Save each model prediction row.

---

## 6. Sentiment Engine

File: `src/pipelines/sentiment.py`

Approach:
- Lexicon-based (positive and negative word sets).
- Cleans text (HTML removal, URL removal, normalization).
- Scores as:
  - `(positive_count - negative_count) / (positive_count + negative_count)`
- Maps score to labels:
  - `>= 0.2` -> positive
  - `<= -0.2` -> negative
  - otherwise neutral

Strengths:
- Fast, deterministic, no external model dependency.

Limitations:
- Not context-aware like transformer NLP models.

---

## 7. ML Prediction Engine

File: `src/pipelines/predictor.py`

### 7.1 Feature Engineering
Features used:
- `ret_1d`, `ret_3d`
- `hl_spread`
- `oc_change`
- `volume_chg`
- `ma5_ratio`, `ma10_ratio`
- `volatility_10d`
- `sentiment_score`

Target:
- `target_return`: next-day return
- `target_class`: binary class (`target_return > 0`)

Data safety:
- Numeric coercion for OHLCV fields.
- zero-safe division via `np.nan` replacements.
- inf/-inf replaced with NaN.
- non-finite rows removed before train/infer.

### 7.2 Models

1. Logistic Regression (`logistic_v1`)
- Classification-style signal converted to return proxy.
- Output from probability of up move.

2. Random Forest Regressor (`random_forest_v1`)
- Non-linear regression on target return.

3. XGBoost Regressor (`xgboost_v1`)
- Gradient-boosted tree model.
- Graceful fallback if xgboost import/runtime fails.

4. Ensemble (`ensemble_v1`)
- Mean of available model predicted returns.
- Ensemble score = mean of available model scores.

Direction logic for all models:
- return > 0.1% -> `up`
- return < -0.1% -> `down`
- otherwise -> `flat`

---

## 8. Indicator Consensus Engine

File: `src/ui/dashboard.py` (`compute_indicator_consensus`)

Indicators currently included:
1. SMA 5/20
2. EMA 12/26
3. RSI 14
4. MACD Histogram
5. Bollinger Position
6. Stochastic %K
7. Williams %R
8. ROC 10
9. Momentum 10
10. ATR Regime
11. OBV Slope
12. Volume Ratio
13. Volatility Regime
14. CCI 20
15. ADX Trend
16. News Sentiment

Scoring:
- Bullish = +1
- Bearish = -1
- Neutral = 0

Consensus:
- Sum all indicator scores.
- Confidence = `abs(total_score) / indicator_count`.
- Label thresholds:
  - `>= +5` -> STRONG BULLISH
  - `+2 to +4` -> BULLISH
  - `-2 to -4` -> BEARISH
  - `<= -5` -> STRONG BEARISH
  - otherwise NEUTRAL

---

## 9. Dashboard Behavior

File: `src/ui/dashboard.py`

Main sections:
1. Executive Summary
2. AI Model Outputs
3. Indicator-wise Breakdown
4. Final Prediction card
5. Price Chart
6. Priority Feed
7. Full News

UI characteristics:
- Midnight-black themed custom CSS.
- Interactive cards with hover effects.
- Model output cards and indicator blocks color-coded:
  - Bullish: green
  - Bearish: red
  - Neutral: yellow

News behavior:
- Fetches latest news per symbol.
- Includes sentiment score/label rendering.

---

## 10. Database Utilities

### 10.1 Connection
File: `src/storage/db/connection.py`
- Creates `engine` using `DB_URL`.
- Exposes `SessionLocal` factory.

### 10.2 Writer Helpers
File: `src/storage/db/writer.py`
Key functions:
- `save_symbols`
- `get_active_symbols`
- `save_market_data`
- `get_symbol_price_df`
- `get_symbol_news_df`
- `save_stock_prediction`

### 10.3 Table Management CLI
File: `src/storage/db/manage_tables.py`
Supports:
- create/drop all tables
- create/drop specific tables by name

Examples:
- `python -m src.storage.db.manage_tables create`
- `python -m src.storage.db.manage_tables create stock_predictions`
- `python -m src.storage.db.manage_tables delete market_news`

---

## 11. Configuration

File: `src/configs/settings.py`
- `DB_URL`
- `LOG_PATH`
- `YAHOO_PERIOD`

---

## 12. Dependencies

Key runtime dependencies:
- pandas, numpy
- yfinance, requests, feedparser
- sqlalchemy, psycopg2-binary
- scikit-learn, xgboost
- streamlit, plotly
- loguru

Note:
- Use Streamlit version compatible with Python 3.13+.
- Altair version should match Streamlit compatibility.

---

## 13. Running the Project

1. Install dependencies
- `pip install -r requirements.txt`

2. Ensure DB is running and reachable at `DB_URL`.

3. Create tables if needed
- `python -m src.storage.db.manage_tables create`

4. Run ingestion pipeline
- `python -m src.main`

5. Run dashboard
- `streamlit run src/ui/dashboard.py`

---

## 14. Common Issues and Fixes

### 14.1 `ModuleNotFoundError: No module named 'src'`
Cause:
- Running Streamlit from file path without root path resolved.
Fix:
- Dashboard bootstraps project root in `sys.path`.

### 14.2 `No numeric types to aggregate`
Cause:
- Non-numeric/object dtype in rolling computations (e.g., ADX path).
Fix:
- Explicit numeric coercion and `np.nan` based safe replacements.

### 14.3 Altair/Streamlit version conflicts
Cause:
- Incompatible Altair major version with Streamlit build.
Fix:
- Pin compatible versions in requirements.

### 14.4 Dropdown menu appears white/unreadable
Cause:
- BaseWeb portal listbox not inheriting theme styles.
Fix:
- Apply explicit CSS to popover/listbox/option selectors.

---

## 15. Current Trade-offs / Technical Debt

1. SQL queries in dashboard use f-strings (should migrate to parameterized SQL for safety and robustness).
2. Symbol ingestion currently includes a hardcoded symbol filter in NSE fetcher.
3. Feature/model logic lives in predictor only; no experiment tracking/version registry.
4. No unit/integration test suite yet.
5. No migration framework (Alembic) for schema evolution.

---

## 16. Recommended Next Enhancements

1. Add parameterized SQL in dashboard loaders.
2. Add walk-forward backtesting metrics per model.
3. Add model confidence calibration and disagreement score.
4. Add ML performance monitoring table (actual vs predicted drift).
5. Add alerting layer for high-confidence signals.
6. Add tests for sentiment, predictor, and indicator pipelines.
7. Add Alembic migrations.

---

## 17. Concept Glossary

- OHLCV: Open, High, Low, Close, Volume.
- VWAP: Volume Weighted Average Price.
- RSI: Relative Strength Index (momentum oscillator).
- MACD: Moving Average Convergence Divergence.
- Bollinger Bands: Volatility bands around moving average.
- ROC: Rate of Change.
- OBV: On-Balance Volume.
- ATR: Average True Range (volatility measure).
- ADX: Average Directional Index (trend strength).
- Ensemble: Combined prediction from multiple models.

---

## 18. Summary
This project already delivers a complete pipeline from ingestion to decision UI with:
- structured market/news storage,
- sentiment analytics,
- multi-model forecasting,
- indicator consensus logic,
- and a themed dashboard for operational visibility.

It is a strong foundation for expanding into production-grade quant research workflows.
