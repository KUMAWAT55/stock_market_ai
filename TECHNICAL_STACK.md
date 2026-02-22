# Technical Stack and Skill-Level Concept Guide

This document maps the exact technologies used in this project to the practical engineering skills required to build, maintain, and extend it.

## 1. Stack Map (At a Glance)

| Layer | Libraries/Tools | How It Is Used in This Project |
|---|---|---|
| Language Runtime | Python | All ingestion, ML, DB, and UI logic |
| Data Processing | pandas, numpy | Feature engineering, rolling windows, merges, numeric safety |
| Market Ingestion | yfinance | Intraday OHLCV pull from Yahoo |
| News Ingestion | requests, feedparser | Google News RSS querying and parsing |
| NLP Sentiment | Python regex + custom lexicon | Fast deterministic scoring for headlines/summaries |
| ML Modeling | scikit-learn, xgboost (optional) | Return prediction (base models + ensemble) |
| Backtesting | scikit-learn + numpy/pandas | Walk-forward model evaluation and strategy metrics |
| Database Connectivity | SQLAlchemy, psycopg2-binary | ORM models, sessions, upserts, SQL execution |
| Database Engine | PostgreSQL | Durable storage for symbols, prices, news, predictions, users |
| UI | Streamlit | Dashboard, auth flows, gating, metric display |
| Visualization | Plotly | Candlestick charting |
| Logging | loguru | Pipeline/runtime observability |

## 2. Skill: Python Application Engineering

### 2.1 Concepts

- Module packaging and imports:
- Project uses `src/...` package paths and module execution (`python -m src.main`).

- Separation of concerns:
- Ingestion, transformation, persistence, model training, and UI are split into focused modules.

- Error handling:
- External APIs are wrapped in `try/except` with fail-safe returns (`None`, empty list, empty DataFrame).

- Deterministic defaults:
- Model seeds (`random_state=42`) and explicit hyperparameters make runs repeatable.

### 2.2 Why this matters

This skill keeps the codebase maintainable as features grow (new symbols, new models, new tables, new UI states).

## 3. Skill: Data Ingestion Engineering

### 3.1 Technologies

- `yfinance`
- `requests`
- `feedparser`
- `pandas.read_csv`

### 3.2 Micro Concepts

- Source-specific adapters:
- Separate fetchers per source (NSE/Yahoo/News), each normalizing source quirks.

- Incremental ingestion:
- Latest stored market timestamp is used to fetch only recent data with an overlap buffer.

- Timestamp normalization:
- Timezone-aware inputs converted to timezone-naive UTC-like values before storage.

- Controlled universe:
- Hardcoded watchlist avoids uncontrolled symbol explosion and keeps runtime predictable.

- Bounded news fetch:
- `max_results` controls API payload and latency.

### 3.3 Skill output in this repo

Reliable repeated pulls of market and news data with practical safeguards against missing edges.

## 4. Skill: Data Normalization and Time-Series Handling

### 4.1 Technologies

- `pandas`, `numpy`

### 4.2 Micro Concepts

- Schema normalization:
- Raw provider columns (`Open`, `High`, `Low`, `Close`, `Volume`) are mapped to canonical names.

- Derived fields:
- `traded_value`, `vwap`, and return-based engineered features are computed consistently.

- Rolling windows:
- `rolling()` and `ewm()` are used for momentum/trend/volatility signals.

- Numeric coercion discipline:
- `pd.to_numeric(errors='coerce')` plus `inf/-inf -> NaN` prevents silent math corruption.

- Safe division patterns:
- Denominators replace zeros with NaN before ratio operations.

- Time-aware joins:
- `merge_asof(..., direction='backward', tolerance='6h')` fuses latest news sentiment into intraday bars.

### 4.3 Skill output in this repo

A stable feature matrix that tolerates noisy real-world data and supports model training.

## 5. Skill: Database Modeling and Persistence

### 5.1 Technologies

- `SQLAlchemy ORM`
- `psycopg2-binary`
- PostgreSQL dialect upserts

### 5.2 Micro Concepts

- ORM model design:
- Each table class defines structure, constraints, and defaults.

- Unique constraints as data contracts:
- Market/news/prediction/backtest/user records each have uniqueness rules tied to business keys.

- Session lifecycle:
- `SessionLocal` controls transaction boundaries and commits/rollbacks.

- Postgres upserts:
- `insert(...).on_conflict_do_update(...)` implements idempotent writes.

- Write dedupe before DB call:
- Python dict keyed by unique tuple removes duplicates in-memory before insert.

- Mixed access patterns:
- ORM for pipeline writes and SQL text reads for dashboard/reporting queries.

### 5.3 Skill output in this repo

Idempotent, duplicate-resistant storage that supports frequent pipeline reruns.

## 6. Skill: Data Integrity and Schema Operations

### 6.1 Technologies

- SQL window functions
- index creation SQL
- runtime maintenance routines

### 6.2 Micro Concepts

- Dedup by ranked rows:
- SQL uses `ROW_NUMBER() OVER (PARTITION BY ...)` and `ctid` to remove duplicate historical rows.

- Conditional maintenance:
- Cleanup pass runs only when expected unique indexes are missing.

- Schema alignment:
- Legacy columns are dropped from `market_data` to enforce the current intraday design.

- Operational idempotency:
- Re-running maintenance does not break normal operations.

### 6.3 Skill output in this repo

Automatic recovery from historical duplicate drift and consistent table semantics across runs.

## 7. Skill: Applied ML for Short-Horizon Forecasting

### 7.1 Technologies

- `scikit-learn` (`SGDRegressor`, `RandomForestRegressor`, `ExtraTreesRegressor`, `Pipeline`, `StandardScaler`)
- `xgboost` (`XGBRegressor`, optional)

### 7.2 Micro Concepts

- Feature-to-target alignment:
- Targets use forward shifts so features at time `t` map to returns at `t+1` (and session-close variants).

- Chronological splitting:
- Train/test split preserves time ordering to avoid leakage.

- Minimum sample gates:
- Prediction/backtesting skip when rows are insufficient.

- Model diversification:
- Linear robust model (SGD-Huber) + nonlinear bagged trees + boosted trees.

- Ensemble blending:
- Mean predicted return across available models reduces single-model variance.

- Graceful optional dependency:
- XGBoost failure does not crash the pipeline.

### 7.3 Skill output in this repo

A practical multi-model prediction system with robust fallbacks and comparable outputs.

## 8. Skill: Time-Series Backtesting and Model Monitoring

### 8.1 Technologies

- `numpy`, `pandas`, `scikit-learn`

### 8.2 Micro Concepts

- Walk-forward evaluation:
- For each evaluation index, fit on historical window and predict next point.

- Step sampling:
- Evaluate every Nth point to reduce compute cost on dense intraday data.

- Shared-sample alignment:
- Backtest rows are restricted to indices where all active models produced predictions.

- Performance metrics:
- Accuracy on sign direction, MAE, RMSE, average returns, curve-level returns.

- Strategy proxy curve:
- Simulated strategy return uses `sign(prediction) * true_return`.

### 8.3 Skill output in this repo

Model quality snapshots that are directly queryable in dashboard views.

## 9. Skill: Sentiment Analysis (Rule-Based NLP)

### 9.1 Technologies

- Python `re`, HTML cleanup utilities
- custom positive/negative lexicon sets

### 9.2 Micro Concepts

- Lightweight NLP pipeline:
- Clean text, tokenize, count signal words.

- Normalized sentiment score:
- Ratio of net polarity to total matched polarity words.

- Threshold-based labeling:
- Positive/negative/neutral buckets for downstream model and UI use.

- Determinism and explainability:
- Same text always yields same score without external model calls.

### 9.3 Skill output in this repo

Fast sentiment features suitable for high-frequency ingestion loops.

## 10. Skill: Analytics UI Engineering

### 10.1 Technologies

- `streamlit`
- `plotly`
- custom CSS/HTML inside Streamlit markdown

### 10.2 Micro Concepts

- Server-driven UI state:
- Selected symbol, auth user, compliance state, and access flags live in session state.

- Data caching:
- `@st.cache_data` and `@st.cache_resource` limit repeated DB load and schema initialization overhead.

- Composable layout:
- Columns, cards, expanders, and tables are assembled from calculated data frames.

- Conditional rendering:
- Predictions/backtests render only when policy and subscription gates pass.

- Themed visualization:
- Candlestick chart and colored diagnostics improve scan speed for operators.

### 10.3 Skill output in this repo

An operational dashboard experience with clear lock/unlock states and actionable summaries.

## 11. Skill: Product Access Control and Security Basics

### 11.1 Technologies

- PBKDF2-HMAC-SHA256 (`hashlib.pbkdf2_hmac`)
- constant-time compare (`hmac.compare_digest`)
- SQL persistence for users/subscriptions/consents/audit logs

### 11.2 Micro Concepts

- Password storage hygiene:
- Salted key-derivation hash (not plaintext, not reversible encryption).

- Iteration hardening:
- 260,000 PBKDF2 rounds increase brute-force cost.

- Account lifecycle:
- Registration, activation flags, login, logout, and session reset logic.

- Subscription gating:
- Access tied to active status and expiry timestamp.

- Compliance gating:
- Versioned disclaimer consent required before unlocking prediction views.

- Auditability:
- Major access events are inserted into audit log table with payload JSON.

### 11.3 Skill output in this repo

Baseline production-style controls for paid and compliant access to model outputs.

## 12. Skill: Observability and Runtime Operations

### 12.1 Technologies

- `loguru`
- SQL table snapshots (`model_backtest_results`, `stock_predictions`)

### 12.2 Micro Concepts

- Structured event logging:
- Ingestion progress, model skips, errors, and backtest completion are logged.

- Persistent telemetry tables:
- Prediction and backtest rows provide historical model behavior for UI and analysis.

- Failure isolation:
- Optional components (for example XGBoost) degrade gracefully without stopping core flow.

### 12.3 Skill output in this repo

Better operability during daily reruns and easier diagnosis of data/model issues.

## 13. Skill Gaps and Next Skill Upgrades

1. SQL safety hardening skill:
- Replace dashboard f-string SQL with parameterized queries.

2. Testing skill:
- Add unit tests for feature generation, sentiment scoring, and prediction target alignment.

3. MLOps skill:
- Add model registry/versioning and drift monitoring.

4. Data governance skill:
- Add migration tooling (for example Alembic) and schema version control.

5. Quant realism skill:
- Include slippage, transaction costs, and latency in backtests.

## 14. Suggested Learning Order (If You Are Building This Yourself)

1. Python packaging + pandas time-series fundamentals.
2. SQLAlchemy ORM and Postgres upsert patterns.
3. Feature engineering and leakage-safe temporal modeling.
4. Walk-forward backtesting and error metrics interpretation.
5. Streamlit app state/caching and dashboard composition.
6. Password hashing, audit logging, and policy gate design.

