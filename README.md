# TradeIQ Intraday Research Platform (FastAPI + React)

TradeIQ is a local-first, SEBI-aware intraday research platform for Indian markets.

It now runs as:
- backend: FastAPI + realtime prediction engine
- frontend: React (Vite + TypeScript) interactive web app


## 1. What This Project Does

- Streams live ticks from Kite WebSocket.
- Aggregates candles for `1m, 5m, 15m, 1h, 1d`.
- Builds engineered features and runs multi-model predictions.
- Applies simulation-only risk guardrails.
- Persists candles, signals, risk, and audit trails in PostgreSQL.
- Serves API endpoints for realtime web frontends.
- Powers a responsive React intraday terminal.

## 2. New Web App Capabilities

The React app (`webapp/`) includes:
- Public website pages: Home, About, Contact.
- Account flow: Register, Login, session-based protected routes.
- Live candlestick chart with EMA overlays.
- Multi-timeframe model matrix (signal, confidence, prob-up, risk-approved signal).
- Indicator heatmap (bullish/bearish/neutral by timeframe).
- Model-event backtest view (prediction -> realized next candle return).
- Strategy Lab (Streak-style quick strategy backtests):
  - `ema_trend`
  - `rsi_reversal`
  - `macd_impulse`
- Intraday scanner endpoint support with confidence and signal filters.

## 3. High-Level Architecture

```text
Kite WebSocket ticks
  -> TickHandler
  -> CandleAggregator (1m/5m/15m/1h/1d)
  -> FeaturePipeline + indicators
  -> predict_signal() (model registry driven)
  -> RiskManager (simulation-only controls)
  -> PostgreSQL (candles/predictions/risk/audit/heartbeat)
  -> FastAPI endpoints
  -> React app polling consolidated snapshot APIs
```

## 4. Repository Layout

```text
api/
  main.py                     # FastAPI app + realtime + analytics endpoints
  analytics.py                # heatmap/matrix/backtest helper logic

realtime/
  realtime_engine.py          # live tick->candle->prediction orchestration

database/
  db_manager.py               # SQLAlchemy data access
  schema.sql                  # PostgreSQL schema

features/
  indicators.py               # indicator computations
  feature_pipeline.py         # feature transforms and selection

models/
  train.py                    # training pipeline
  predict.py                  # inference + signal mapping
  model_registry.py           # active model resolution

webapp/
  src/App.tsx                 # React terminal UI
  src/api.ts                  # frontend API client
  src/styles.css              # responsive styles

config/
  config.py
  instruments.json
  market_holidays.json
  sectors.json
  model_hyperparams.json
```

## 5. API Surface for React App

Core endpoints used by `webapp`:
- `POST /auth/register`
- `POST /auth/login`
- `GET /auth/me`
- `POST /public/contact`
- `GET /market/symbols`
- `GET /dashboard/snapshot`
- `GET /analytics/model-matrix`
- `GET /analytics/indicator-heatmap`
- `GET /analytics/backtest/model`
- `GET /analytics/backtest/strategy`
- `GET /scanner/intraday`

Infrastructure/control endpoints:
- `GET /health`
- `POST /engine/start`
- `POST /engine/stop`
- `GET /engine/status`
- `POST /historical/backfill`
- `POST /historical/ensure`

Automatic historical sync is now backend-driven:
- `GET /dashboard/snapshot` auto-queues backfill if selected symbol/timeframe is stale.
- Background sweep periodically checks configured symbols/timeframes and queues missing/stale data jobs.
- Tune using env vars:
  - `AUTO_HISTORICAL_ENSURE_ENABLED=true`
  - `AUTO_HISTORICAL_ENSURE_INTERVAL_SECONDS=300`
  - `AUTO_HISTORICAL_ENSURE_MAX_JOBS_PER_SWEEP=8`

## 6. Local Setup

## 6.1 Prerequisites
- Python `3.11+`
- PostgreSQL local instance
- Node.js `18+` (recommended `20+`) for React app
- Kite Connect credentials

## 6.2 Backend Install

```bash
cd /Users/rohkumaw/Documents/stock_market_ai
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## 6.3 Database

```bash
brew services start postgresql
createuser -s rohkumaw 2>/dev/null || true
createdb -O rohkumaw stock_market_ai 2>/dev/null || true
```

```bash
export DATABASE_URL='postgresql+psycopg2://rohkumaw@127.0.0.1:5432/stock_market_ai?gssencmode=disable'
python3 -c "from database.db_manager import DatabaseManager; DatabaseManager().init_schema(); print('schema ok')"
```

## 6.4 Kite Token

```bash
python3 scripts/generate_kite_token.py --api-key YOUR_API_KEY --print-login-url
```

Then generate and export:

```bash
python3 scripts/generate_kite_token.py \
  --api-key YOUR_API_KEY \
  --api-secret YOUR_API_SECRET \
  --request-token YOUR_REQUEST_TOKEN

export KITE_API_KEY='YOUR_API_KEY'
export KITE_ACCESS_TOKEN='YOUR_ACCESS_TOKEN'
```

## 6.5 Run Backend

```bash
uvicorn api.main:app --host 127.0.0.1 --port 8000 --reload
```

## 6.6 Run React Frontend

```bash
cd webapp
npm install
npm run dev
```

Set API base if needed:

```bash
export VITE_API_BASE_URL='http://127.0.0.1:8000'
```

## 6.7 One-Command Live Share Link

If you want to share the app with a friend over the internet from your local machine:

```bash
brew install cloudflared
./scripts/share_live.sh
```

What it does:
- starts backend (`uvicorn`)
- starts frontend (`vite`)
- opens Cloudflare Tunnel for backend + frontend
- prints a public frontend URL you can share

Stop everything with `Ctrl+C`.

Optional timeout tuning (if startup is heavy):
```bash
BACKEND_HEALTH_TIMEOUT=240 FRONTEND_HEALTH_TIMEOUT=150 ./scripts/share_live.sh
```

## 7. Intraday Usage Flow

1. Start API and ensure engine is running.
2. Open React app.
3. Select symbol/timeframe and refresh cadence.
4. Use model matrix for cross-timeframe alignment.
5. Use indicator heatmap for momentum/mean-reversion context.
6. Compare model backtest vs strategy backtest.
7. Use scanner for ranked opportunities.

## 8. Compliance Notes

- Signal/research only, no order execution module.
- Risk layer is simulation-only.
- Prediction lineage is stored in `prediction_events`.
- Audit events stored in `compliance_audit_trail` and `compliance_audit_logs`.

## 9. Additional Docs

- [Developer Guide](docs/DEVELOPER_GUIDE.md)
- [Database Tables](docs/database_tables.md)
- [Architecture V2](docs/ARCHITECTURE_REACT.md)
- [Tech Stack Learning Guide](docs/TECH_STACK_LEARNING.md)
- [Intraday Product Roadmap](docs/INTRADAY_PRODUCT_ROADMAP.md)
