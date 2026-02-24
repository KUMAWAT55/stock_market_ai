# Developer Guide (Micro-Level)

This guide explains the repository module-by-module so a new developer can
understand data flow quickly without reverse-engineering every file.

## 1. Runtime Data Flow

1. `api/main.py` starts the FastAPI app and optionally auto-starts realtime engine.
2. `realtime/realtime_engine.py` starts websocket + worker loops.
3. `data/kite_client.py` receives raw Kite ticks.
4. `data/tick_handler.py` normalizes and queues ticks safely across threads.
5. `data/candle_aggregator.py` builds OHLCV candles (`1m/5m/15m/1h/1d`).
6. `features/feature_pipeline.py` + `features/indicators.py` build model features.
7. `models/predict.py` loads active model artifact and predicts probability/signal.
8. `compliance/risk_manager.py` applies simulation-only governance constraints.
9. `database/db_manager.py` persists ticks, candles, predictions, risk events, audits.
10. `dashboard/streamlit_app.py` reads API + DB-backed auth/compliance and renders UI.

## 2. Module Responsibilities

### `config/`

- `config/config.py`
  - Defines `Settings` dataclass and env-driven configuration defaults.
  - Parses timeframe lists, instrument token list, and market calendar settings.
  - Provides helper methods for symbol map loading, holiday loading, and JSON-safe feature serialization.
  - `get_settings()` is cached and ensures required directories exist.

### `data/`

- `data/kite_client.py`
  - `KiteRealtimeClient`: websocket wrapper with reconnect callbacks + subscriptions.
  - `KiteHistoricalClient`: historical candle loader and Kite profile auth check.

- `data/tick_handler.py`
  - `NormalizedTick`: canonical tick schema.
  - `TickHandler`: converts raw ticks to `NormalizedTick` and pushes to bounded queue.
  - Async batch drain method (`get_batch`) bridges thread callback -> asyncio loop.

- `data/candle_aggregator.py`
  - `Candle` and `_CandleState` for immutable/mutable candle representations.
  - Aggregates ticks into configured time buckets with trading-hours validation.
  - Supports history warming and partial candle snapshots for charts.

### `features/`

- `features/indicators.py`
  - Computes returns, EMA/MACD, RSI, ATR%, Bollinger width, volatility, volume z-score.
  - Adds session-progress cyclical features (`minute_sin`, `minute_cos`).

- `features/feature_pipeline.py`
  - Defines `FEATURE_COLUMNS` contract used by training + inference.
  - `FeaturePipeline.latest_feature_row()` returns latest fully valid feature vector.
  - `build_training_frame()` adds supervised target (`target_up`).

### `models/`

- `models/train.py`
  - Offline training pipeline from candles or directly from Kite historical API.
  - Uses time-ordered train/test split + walk-forward validation.
  - Registers model version and stores simulated metrics.

- `models/predict.py`
  - Cached model loading.
  - Probability extraction across different estimator capabilities.
  - Signal mapping with configured thresholds + lightweight explainability.

- `models/model_registry.py`
  - Manages versioning metadata and active model resolution.
  - Writes local `.meta.json` beside model artifacts and syncs DB registry.

### `compliance/`

- `compliance/disclaimer.py`
  - Single source of disclaimer/risk disclosure text and version constant.

- `compliance/risk_manager.py`
  - Simulation-only guardrails: cooldown throttling, drawdown checks, stop-loss and position sizing logic.
  - Produces structured risk payload included in each prediction event.

### `database/`

- `database/schema.sql`
  - DDL for realtime + governance tables.

- `database/db_manager.py`
  - Thin SQLAlchemy access layer (no business logic).
  - Writes and reads candles/predictions/backtests/risk/compliance/heartbeat.
  - All JSON payloads are serialized explicitly before insert.

### `realtime/`

- `realtime/realtime_engine.py`
  - Core orchestrator:
    - Starts websocket client.
    - Drains tick queue.
    - Writes ticks.
    - Aggregates candles.
    - Computes features.
    - Runs model inference.
    - Applies risk governance.
    - Persists prediction + compliance audit.
  - Includes backfill API support and heartbeat writer.

### `api/`

- `api/main.py`
  - FastAPI endpoints for:
    - health/auth checks
    - engine start/stop
    - candles and signal history
    - simulated backtest retrieval
    - historical backfill trigger

### `dashboard/`

- `dashboard/streamlit_app.py`
  - Auth + registration + consent flow.
  - SEBI disclaimer gating and audit logging.
  - Controls for symbol/timeframe/backfill.
  - Live chart + current prediction + historical signals + simulated metrics.
  - Custom dark theme CSS for readability.

### `scripts/`

- `scripts/generate_kite_token.py`
  - CLI helper to generate daily Kite access token from request token.

- `scripts/archive_legacy_tables.py`
  - Utility to move inactive DB tables into backup schema (dry-run supported).

## 3. Where To Start As New Developer

1. Read `README.md` for setup and run commands.
2. Read `realtime/realtime_engine.py` for runtime orchestration.
3. Read `database/db_manager.py` to understand persisted artifacts.
4. Read `dashboard/streamlit_app.py` for user-facing flow and controls.
5. Read `models/train.py` to understand retraining and evaluation policy.

## 4. Debugging Entry Points

- No live candles: check websocket auth and `engine_heartbeat`.
- No predictions: verify active model in `model_registry` for selected timeframe.
- Missing dashboard data: verify `/candles` and `/signals/history` endpoints first.
- Backfill errors: validate instrument token map and Kite access token validity.
