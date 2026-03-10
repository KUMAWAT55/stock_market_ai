# Architecture V2: FastAPI + React Intraday Platform

## 1. Design Goals

- Remove Streamlit bottlenecks for intensive interactive UI.
- Support low-latency, high-frequency intraday refresh cycles.
- Keep prediction logic centralized in backend.
- Expose compact API contracts for frontend performance.

## 2. Component Diagram

```text
Kite WS
  -> TickHandler Queue
  -> Realtime Engine
      -> Candle Aggregator
      -> Feature Pipeline
      -> Model Inference
      -> Risk Manager
      -> PostgreSQL
  -> FastAPI
      -> Snapshot + Analytics + Scanner APIs
  -> React App (Vite)
      -> Polling + rendering chart/heatmap/matrix/backtests/scanner
```

## 3. Backend Layers

### 3.1 Ingestion Layer
- `data/kite_client.py`
- `data/tick_handler.py`

Responsibilities:
- consume raw websocket ticks
- normalize, queue, and protect against callback bursts

### 3.2 Realtime Processing Layer
- `realtime/realtime_engine.py`
- `data/candle_aggregator.py`
- `features/feature_pipeline.py`
- `models/predict.py`
- `compliance/risk_manager.py`

Responsibilities:
- aggregate multi-timeframe candles
- compute feature vectors
- run timeframe model inference
- apply simulation risk guardrails
- persist output lineage

### 3.3 API Aggregation Layer
- `api/main.py`
- `api/analytics.py`

Responsibilities:
- expose control endpoints (health/engine)
- expose data endpoints (candles/signals)
- expose analytics endpoints (heatmap, matrix, backtest, scanner)
- consolidate into `/dashboard/snapshot` to minimize frontend round-trips

## 4. Frontend Layers

### 4.1 Presentation
- `webapp/src/App.tsx`
- `webapp/src/styles.css`
- `webapp/src/pages/*`

Responsibilities:
- render responsive views for desktop/mobile
- provide advanced interactive controls (symbol/timeframe/strategy/scanner filters)
- provide full website shell pages (home/about/contact/login/register/dashboard)

### 4.2 Data Client
- `webapp/src/api.ts`
- `webapp/src/types.ts`
- `webapp/src/auth.tsx`

Responsibilities:
- typed HTTP calls
- contract-safe parsing
- centralized API base URL config
- auth token lifecycle and protected dashboard route gating

## 5. Performance Architecture Choices

- Consolidated endpoint: `/dashboard/snapshot` reduces UI API fan-out.
- Server-side precomputed analytics (heatmap/matrix/backtest) avoids heavy browser compute.
- Polling interval control (`0-60s`) for user-adjusted load.
- DB query patterns focused on latest rows per symbol/timeframe.

## 6. Security and Compliance

- CORS allowlist controlled by `CORS_ALLOW_ORIGINS`.
- Research-only architecture; no order execution API.
- Compliance/audit trails preserved in DB.
- Risk manager can downgrade raw model signal to `HOLD`.

## 7. Deployment Topology (Recommended)

- API service: `uvicorn api.main:app` (private network).
- React app: static build served via CDN/Nginx or Vite dev for local.
- PostgreSQL: managed local/server instance with backups.

## 8. API Contracts Used by React

- `GET /market/symbols`
- `GET /dashboard/snapshot`
- `GET /analytics/backtest/strategy`
- `GET /scanner/intraday`

## 9. Future Evolution

- Move from polling to websocket push for selected endpoints.
- Add Redis caching for scanner and matrix payloads.
- Add per-user watchlists and alert channels.
- Add strategy rule-builder DSL and event-based backtester.
