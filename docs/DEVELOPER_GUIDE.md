# Developer Guide (FastAPI + React)

This guide explains the runtime and module responsibilities after the React dashboard migration.

## 1. Runtime Data Flow

1. `api/main.py` starts FastAPI and initializes DB schema.
2. `realtime/realtime_engine.py` starts websocket + async workers.
3. `data/kite_client.py` streams ticks from Kite.
4. `data/tick_handler.py` normalizes/queues ticks.
5. `data/candle_aggregator.py` builds multi-timeframe candles.
6. `features/feature_pipeline.py` + `features/indicators.py` produce model features.
7. `models/predict.py` runs model inference from active model registry.
8. `compliance/risk_manager.py` applies simulation-only controls.
9. `database/db_manager.py` writes ticks/candles/predictions/risk/audit/heartbeat.
10. React app (`webapp/`) polls FastAPI consolidated snapshot endpoints.

## 2. Backend Module Responsibilities

### `api/main.py`
- Service lifecycle endpoints (`/health`, `/engine/start`, `/engine/stop`, `/engine/status`).
- Data APIs (`/candles`, `/signals/history`, `/signals/latest`, `/price/live`).
- Analytics APIs for web app:
  - `/dashboard/snapshot`
  - `/analytics/model-matrix`
  - `/analytics/indicator-heatmap`
  - `/analytics/backtest/model`
  - `/analytics/backtest/strategy`
  - `/scanner/intraday`
- Historical sync APIs (`/historical/backfill`, `/historical/ensure`).
- CORS middleware for React frontend.

### `api/analytics.py`
- Computes indicator heatmaps by timeframe.
- Builds model matrix and cross-timeframe consensus.
- Computes prediction-event backtest metrics.
- Runs quick indicator-strategy backtests (Streak-style exploration).

### `realtime/realtime_engine.py`
- Live ingestion orchestration.
- Tick persistence.
- Candle close handling.
- Feature extraction and model inference.
- Risk decisioning.
- Prediction/audit persistence.
- Historical backfill support.

### `database/db_manager.py`
- SQLAlchemy-based data access for all core entities.
- Added helper for latest predictions by timeframe.

## 3. Frontend (`webapp/`)

### Stack
- Vite + React + TypeScript
- Plotly candlestick rendering (`react-plotly.js`)
- React Router (`react-router-dom`) for full website navigation

### Key files
- `webapp/src/App.tsx`: app shell + route mapping.
- `webapp/src/pages/HomePage.tsx`, `AboutPage.tsx`, `ContactPage.tsx`: public site pages.
- `webapp/src/pages/LoginPage.tsx`, `RegisterPage.tsx`: account flow pages.
- `webapp/src/pages/DashboardPage.tsx`: protected trading dashboard.
- `webapp/src/auth.tsx`: auth provider + token/session lifecycle.
- `webapp/src/api.ts`: typed fetch clients for backend endpoints.
- `webapp/src/types.ts`: API payload interfaces.
- `webapp/src/styles.css`: responsive layout and visual system.

## 4. Local Run Commands

## 4.1 Backend

```bash
source .venv/bin/activate
uvicorn api.main:app --host 127.0.0.1 --port 8000 --reload
```

## 4.2 Frontend

```bash
cd webapp
npm install
npm run dev
```

If API is on a different host/port:

```bash
export VITE_API_BASE_URL='http://127.0.0.1:8000'
```

## 5. Debugging Entry Points

- No live updates: check `/engine/status` and websocket connectivity in payload.
- Empty charts: verify `/dashboard/snapshot` has `candles.rows`.
- No model matrix rows: verify models are active in `model_registry` for requested timeframes.
- Weak backtests: inspect `prediction_events` coverage and symbol/timeframe alignment.
- Scanner empty: lower `min_confidence` or switch scanner timeframe.

## 6. Migration Notes

- Streamlit dashboard is now legacy (`dashboard/streamlit_app.py`).
- Primary UX surface is `webapp/` + FastAPI APIs.
- Keep API contracts stable; frontend relies on consolidated `/dashboard/snapshot` for speed.
