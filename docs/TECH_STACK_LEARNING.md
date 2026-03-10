# Tech Stack Learning Guide (Detailed)

This document explains each technology used in TradeIQ, why it exists, and what to learn first.

## 1. Python Backend Fundamentals

## 1.1 FastAPI
What it is:
- Modern async web framework with type hints and OpenAPI generation.

Where used:
- `api/main.py`

Core concepts to learn:
- path operations (`@app.get`, `@app.post`)
- query validation (`Query(pattern=...)`, bounds)
- exception handling (`HTTPException`)
- startup/shutdown lifecycle events
- middleware (`CORSMiddleware`)

Why it matters in this app:
- clean typed contracts between realtime engine and React UI
- predictable low-latency APIs for polling

Practice path:
1. Add a small test endpoint with query params.
2. Add validation and observe 422 responses.
3. Add middleware and verify CORS behavior in browser.

## 1.2 Asyncio (Python async runtime)
What it is:
- event-loop concurrency model.

Where used:
- `api/main.py` (engine lifecycle locks, async tasks)
- `realtime/realtime_engine.py` (worker loops)

Core concepts:
- coroutine (`async def`)
- task creation (`asyncio.create_task`)
- cancellation (`task.cancel`)
- lock semantics (`asyncio.Lock`)
- moving blocking work off event loop (`asyncio.to_thread`)

Why it matters:
- market feed + DB IO + API should not block each other

## 1.3 SQLAlchemy + PostgreSQL
What it is:
- SQL toolkit + relational DB.

Where used:
- `database/db_manager.py`
- `database/schema.sql`

Core concepts:
- engine/session lifecycle
- transactions (`with self._engine.begin()`)
- JSONB usage for flexible model/risk payloads
- index design for latest-row queries
- upsert patterns (`ON CONFLICT ... DO UPDATE`)

Why it matters:
- prediction lineage and auditability are data-engineering critical

Recommended SQL topics for this project:
- `DISTINCT ON` for latest record per key
- composite indexes (`symbol, timeframe, prediction_ts DESC`)
- query plans (`EXPLAIN ANALYZE`)

## 2. Realtime Market Data Pipeline

## 2.1 Websocket ingestion
Where:
- `data/kite_client.py`
- `data/tick_handler.py`

Learn:
- callback-based websocket handlers
- queue buffering and dropped-message management
- reconnection behavior and health visibility

## 2.2 Candle aggregation
Where:
- `data/candle_aggregator.py`

Learn:
- OHLCV construction from tick stream
- timeframe bucket boundary logic
- partial candle handling

## 2.3 Realtime orchestration
Where:
- `realtime/realtime_engine.py`

Learn:
- ingestion loop -> aggregation -> inference pipeline
- state caching for latest signal/price
- heartbeat emission

## 3. Quant/ML Layer

## 3.1 Technical indicators
Where:
- `features/indicators.py`

Learn:
- EMA, MACD, RSI, ATR, Bollinger features
- volatility and volume normalization
- session-aware cyclical features

## 3.2 Feature engineering (cross-sectional)
Where:
- `features/feature_pipeline.py`

Learn:
- symbol encoding
- percentile ranks over rolling windows
- relative strength vs index
- sector-relative momentum

## 3.3 Model lifecycle
Where:
- `models/train.py`
- `models/predict.py`
- `models/model_registry.py`

Learn:
- time-based split vs random split
- calibration (Platt/isotonic)
- multi-model ensembles and stacking
- model versioning and registry activation

## 3.4 Prediction governance
Where:
- `compliance/risk_manager.py`

Learn:
- confidence gates
- cooldown throttling
- drawdown simulation
- capital allocation caps

## 4. React Frontend Fundamentals

## 4.1 Vite + React + TypeScript
Where:
- `webapp/`

Learn:
- Vite dev/build flow
- component state with hooks
- side effects (`useEffect`)
- memoization for chart transforms (`useMemo`)
- typed API clients with interfaces

## 4.2 Plotly charting
Where:
- `webapp/src/App.tsx`

Learn:
- candlestick trace structure
- multi-trace overlays (EMA lines)
- responsive layout config

## 4.3 Responsive UX engineering
Where:
- `webapp/src/styles.css`

Learn:
- CSS variables for design system
- grid layout for desktop/mobile
- dense data-table readability patterns

## 5. API-to-UI Contracts

### 5.1 Snapshot pattern
Endpoint:
- `GET /dashboard/snapshot`

Concept:
- one payload includes chart + matrix + heatmap + backtest summary
- reduces client orchestration overhead and request waterfalls

### 5.2 Analytics endpoints
Endpoints:
- `/analytics/model-matrix`
- `/analytics/indicator-heatmap`
- `/analytics/backtest/model`
- `/analytics/backtest/strategy`
- `/scanner/intraday`

Concept:
- backend computes expensive analytics once
- frontend focuses on rendering and interaction

## 6. Backtesting Concepts Used

## 6.1 Model-event backtest
- Uses prediction events and realized next-candle returns at `target_ts`.
- Useful for “does model signal direction align with realized bar move?” evaluation.

## 6.2 Strategy backtest (rule-based)
- Quick sandbox for idea validation (`ema_trend`, `rsi_reversal`, `macd_impulse`).
- Includes per-change transaction cost (`cost_bps`).

Metrics to understand:
- trade count
- win rate
- average return per trade
- total return
- max drawdown
- sharpe-like ratio
- profit factor

## 7. Intraday Product Concepts

- Multi-timeframe confirmation: avoid one-timeframe blind trades.
- Scanner ranking: shortlist by confidence + risk-approved signal.
- Heatmap context: align indicator regime with model outputs.
- Strategy lab: evaluate conditional logic quickly before coding full automation.

## 8. Suggested Learning Sequence (Practical)

1. Read `api/main.py` + test endpoints manually in browser/curl.
2. Read `realtime/realtime_engine.py` to understand live lifecycle.
3. Read `database/schema.sql` and inspect tables in Postgres.
4. Run React app and map each UI panel to API payload sections.
5. Modify one strategy in `api/analytics.py` and verify UI updates.
6. Train one timeframe model and inspect registry + matrix impact.

## 9. Minimal Exercises

1. Add a new indicator row to heatmap payload.
2. Add a new scanner filter (`min_prob_up`).
3. Add a new strategy (`supertrend_breakout`) in strategy backtest endpoint.
4. Add frontend watchlist persistence via localStorage.
5. Add a unit test for model-backtest metric calculations.
