# Database Table Guide (Column-Level + Sample Data)

This document explains each PostgreSQL table used by the project, with:
- column-level meaning,
- code paths that write/read each table,
- and a realistic sample row to show what the table actually stores.

---

## 1) `realtime_ticks`

**Purpose:** Stores normalized raw tick packets from Kite WebSocket before candle aggregation.

### Columns
| Column | Type | Nullable | Meaning |
|---|---|---:|---|
| `id` | `BIGSERIAL` | No | Surrogate primary key (auto-increment). |
| `instrument_token` | `BIGINT` | No | Numeric broker instrument identifier (stable mapping key). |
| `symbol` | `VARCHAR(64)` | No | Human-readable trading symbol (e.g., `NSE:RELIANCE`). |
| `ts` | `TIMESTAMP` | No | Tick event time from source stream. |
| `last_price` | `DOUBLE PRECISION` | No | Last traded price at `ts`. |
| `last_traded_quantity` | `BIGINT` | Yes | Quantity in the last trade. |
| `total_buy_quantity` | `BIGINT` | Yes | Aggregated buy-side quantity available at snapshot time. |
| `total_sell_quantity` | `BIGINT` | Yes | Aggregated sell-side quantity available at snapshot time. |
| `volume` | `BIGINT` | Yes | Cumulative traded volume for the session at that tick. |
| `oi` | `BIGINT` | Yes | Open interest (relevant for derivatives). |
| `source` | `VARCHAR(32)` | No | Tick source tag; default `kite_ws`. |
| `created_at` | `TIMESTAMP` | No | DB insert timestamp (`NOW()`). |

### Indexes / Constraints
- PK: `id`
- Index: `idx_realtime_ticks_symbol_ts(symbol, ts DESC)` for recent-per-symbol retrieval.

### Code usage
- **Write:** `DatabaseManager.insert_ticks()`
- **Read:** no dedicated read helper yet (mostly archival/forensics and future replay).

### Sample row
```json
{
  "id": 8244102,
  "instrument_token": 738561,
  "symbol": "NSE:RELIANCE",
  "ts": "2026-02-23T10:15:01",
  "last_price": 2954.35,
  "last_traded_quantity": 75,
  "total_buy_quantity": 512340,
  "total_sell_quantity": 488910,
  "volume": 10455672,
  "oi": null,
  "source": "kite_ws",
  "created_at": "2026-02-23T10:15:01.201"
}
```

---

## 2) `ohlcv_candles`

**Purpose:** Stores aggregated OHLCV candles (`15m`, `1d`) generated from tick stream.

### Columns
| Column | Type | Nullable | Meaning |
|---|---|---:|---|
| `id` | `BIGSERIAL` | No | Surrogate primary key. |
| `symbol` | `VARCHAR(64)` | No | Trading symbol the candle belongs to. |
| `timeframe` | `VARCHAR(8)` | No | Candle bucket (e.g., `15m`, `1d`). |
| `candle_start` | `TIMESTAMP` | No | Inclusive candle start boundary. |
| `candle_end` | `TIMESTAMP` | No | Exclusive/end candle boundary (implementation-defined). |
| `open` | `DOUBLE PRECISION` | No | First trade price in bucket. |
| `high` | `DOUBLE PRECISION` | No | Maximum price in bucket. |
| `low` | `DOUBLE PRECISION` | No | Minimum price in bucket. |
| `close` | `DOUBLE PRECISION` | No | Last trade price in bucket. |
| `volume` | `BIGINT` | No | Aggregate volume in bucket (default 0). |
| `tick_count` | `INTEGER` | No | Number of ticks merged into this candle. |
| `is_partial` | `BOOLEAN` | No | `true` if candle still forming; `false` when finalized. |
| `created_at` | `TIMESTAMP` | No | DB insert time. |

### Indexes / Constraints
- PK: `id`
- Unique: `(symbol, timeframe, candle_start)` for idempotent upsert.
- Index: `idx_ohlcv_candles_symbol_tf_end(symbol, timeframe, candle_end DESC)`.

### Code usage
- **Write:** `DatabaseManager.upsert_candle()` with `ON CONFLICT ... DO UPDATE`.
- **Read:** `DatabaseManager.get_recent_candles()` for feature computation and inference warmup.

### Sample row
```json
{
  "id": 190211,
  "symbol": "NSE:RELIANCE",
  "timeframe": "15m",
  "candle_start": "2026-02-23T10:15:00",
  "candle_end": "2026-02-23T10:30:00",
  "open": 2953.70,
  "high": 2959.20,
  "low": 2951.85,
  "close": 2958.05,
  "volume": 328420,
  "tick_count": 911,
  "is_partial": false,
  "created_at": "2026-02-23T10:30:00.044"
}
```

---

## 3) `model_registry`

**Purpose:** Stores model artifact location and metadata by model/timeframe/version.

### Columns
| Column | Type | Nullable | Meaning |
|---|---|---:|---|
| `id` | `BIGSERIAL` | No | Surrogate primary key. |
| `model_name` | `VARCHAR(128)` | No | Model family identifier (e.g., `xgb_classifier`). |
| `timeframe` | `VARCHAR(8)` | No | Trained horizon (`15m` or `1d`). |
| `version` | `VARCHAR(64)` | No | Version tag (timestamp/hash/semantic). |
| `artifact_path` | `TEXT` | No | Filesystem path to serialized model artifact (`.pkl`). |
| `metrics` | `JSONB` | Yes | Training/backtest metrics map (accuracy/F1/AUC/etc.). |
| `feature_list` | `JSONB` | Yes | Ordered feature names expected at inference. |
| `created_at` | `TIMESTAMP` | No | Registry write timestamp. |
| `is_active` | `BOOLEAN` | No | Activation flag for inference selection. |

### Indexes / Constraints
- PK: `id`
- Unique: `(model_name, timeframe, version)`.

### Code usage
- **Write:** `DatabaseManager.upsert_model_registry()`.
- **Read:** `DatabaseManager.get_active_model(timeframe)`.

### Sample row
```json
{
  "id": 37,
  "model_name": "xgb_classifier",
  "timeframe": "15m",
  "version": "2026-02-22T23-30-10Z",
  "artifact_path": "models/artifacts/RELIANCE_xgb_classifier_15m_2026-02-22T23-30-10Z.pkl",
  "metrics": {
    "accuracy": 0.611,
    "precision": 0.603,
    "recall": 0.627,
    "f1": 0.615,
    "roc_auc": 0.644
  },
  "feature_list": ["ret_1", "ret_3", "ret_5", "ret_15", "macd", "rsi_14", "atr_pct"],
  "created_at": "2026-02-22T23:30:10.812",
  "is_active": true
}
```

---

## 4) `prediction_events`

**Purpose:** Main event log of inference outputs with probabilities, lineage, explainability, and risk context.

### Columns
| Column | Type | Nullable | Meaning |
|---|---|---:|---|
| `id` | `BIGSERIAL` | No | Surrogate primary key. |
| `symbol` | `VARCHAR(64)` | No | Symbol predicted. |
| `timeframe` | `VARCHAR(8)` | No | Prediction horizon bucket. |
| `prediction_ts` | `TIMESTAMP` | No | Timestamp when prediction was generated. |
| `target_ts` | `TIMESTAMP` | No | Target candle timestamp prediction refers to. |
| `signal` | `VARCHAR(8)` | No | Final signal (`BUY`/`SELL`/`HOLD`). |
| `confidence` | `DOUBLE PRECISION` | No | Usually `max(prob_up, prob_down)`. |
| `prob_up` | `DOUBLE PRECISION` | No | Estimated probability of upward move. |
| `prob_down` | `DOUBLE PRECISION` | No | Estimated probability of downward/non-up move. |
| `model_name` | `VARCHAR(128)` | No | Model used for this inference. |
| `model_version` | `VARCHAR(64)` | No | Model version used for this inference. |
| `feature_snapshot` | `JSONB` | No | Feature values used to score this event. |
| `explainability` | `JSONB` | Yes | Top feature contributions / interpretation payload. |
| `risk_snapshot` | `JSONB` | Yes | Risk manager decision context (allow/override/reason). |
| `compliance_note` | `TEXT` | Yes | Human-readable compliance text attached to event. |
| `is_simulated` | `BOOLEAN` | No | Marks non-execution simulation-only mode. |
| `created_at` | `TIMESTAMP` | No | DB insert timestamp. |

### Indexes / Constraints
- PK: `id`
- Index: `idx_prediction_events_symbol_tf_ts(symbol, timeframe, prediction_ts DESC)`.

### Code usage
- **Write:** `DatabaseManager.insert_prediction()`.
- **Read:**
  - `DatabaseManager.list_recent_predictions(symbol, timeframe, limit)`
  - `DatabaseManager.get_latest_predictions(limit)`.

### Sample row
```json
{
  "id": 552001,
  "symbol": "NSE:RELIANCE",
  "timeframe": "15m",
  "prediction_ts": "2026-02-23T10:30:00",
  "target_ts": "2026-02-23T10:45:00",
  "signal": "BUY",
  "confidence": 0.72,
  "prob_up": 0.72,
  "prob_down": 0.28,
  "model_name": "xgb_classifier",
  "model_version": "2026-02-22T23-30-10Z",
  "feature_snapshot": {
    "ret_1": 0.0014,
    "ret_3": 0.0032,
    "macd_hist": 0.24,
    "rsi_14": 58.9,
    "atr_pct": 0.0083
  },
  "explainability": {
    "top_features": [
      {"feature": "macd_hist", "contribution": 0.31},
      {"feature": "ret_3", "contribution": 0.19}
    ]
  },
  "risk_snapshot": {
    "allowed": true,
    "cooldown_block": false,
    "max_allocation_pct": 25.0
  },
  "compliance_note": "Simulation-only research signal. Not investment advice.",
  "is_simulated": true,
  "created_at": "2026-02-23T10:30:00.051"
}
```

---

## 5) `risk_events`

**Purpose:** Event table for explicit governance/risk incidents and decisions.

### Columns
| Column | Type | Nullable | Meaning |
|---|---|---:|---|
| `id` | `BIGSERIAL` | No | Surrogate primary key. |
| `symbol` | `VARCHAR(64)` | No | Symbol impacted by event. |
| `timeframe` | `VARCHAR(8)` | No | Timeframe context for the event. |
| `event_ts` | `TIMESTAMP` | No | Timestamp when risk event occurred/recorded. |
| `event_type` | `VARCHAR(64)` | No | Event code (e.g., `cooldown_block`, `drawdown_limit_hit`). |
| `payload` | `JSONB` | No | Structured details (thresholds, observed values, actions). |
| `created_at` | `TIMESTAMP` | No | DB insert timestamp. |

### Indexes / Constraints
- PK: `id`

### Code usage
- **Write:** `DatabaseManager.insert_risk_event()`.
- **Read:** no dedicated read helper yet (used for audit/risk analytics).

### Sample row
```json
{
  "id": 1189,
  "symbol": "NSE:RELIANCE",
  "timeframe": "15m",
  "event_ts": "2026-02-23T10:45:00",
  "event_type": "cooldown_block",
  "payload": {
    "cooldown_seconds": 120,
    "seconds_since_last_signal": 49,
    "blocked_signal": "BUY",
    "final_signal": "HOLD"
  },
  "created_at": "2026-02-23T10:45:00.020"
}
```

---

## 6) `compliance_audit_trail`

**Purpose:** Compliance-first lifecycle/event history (engine state changes, policy markers, notable actor actions).

### Columns
| Column | Type | Nullable | Meaning |
|---|---|---:|---|
| `id` | `BIGSERIAL` | No | Surrogate primary key. |
| `event_ts` | `TIMESTAMP` | No | Actual event time. |
| `event_type` | `VARCHAR(128)` | No | Event label (e.g., `engine_start`, `engine_stop`, `policy_warning`). |
| `actor` | `VARCHAR(64)` | No | Actor identity (`system` by default, can be service/user). |
| `symbol` | `VARCHAR(64)` | Yes | Optional symbol context if event is symbol-scoped. |
| `timeframe` | `VARCHAR(8)` | Yes | Optional timeframe context. |
| `details` | `JSONB` | No | Structured audit details for traceability. |
| `created_at` | `TIMESTAMP` | No | DB insert timestamp. |

### Indexes / Constraints
- PK: `id`
- Index: `idx_compliance_audit_trail_event_ts(event_ts DESC)`.

### Code usage
- **Write:** `DatabaseManager.insert_compliance_audit()`.
- **Read:** no dedicated helper yet (consumed for audits/compliance reviews).

### Sample row
```json
{
  "id": 301,
  "event_ts": "2026-02-23T09:15:00",
  "event_type": "engine_start",
  "actor": "system",
  "symbol": null,
  "timeframe": null,
  "details": {
    "auto_start_engine": true,
    "loaded_timeframes": ["15m", "1d"],
    "mode": "simulation"
  },
  "created_at": "2026-02-23T09:15:00.011"
}
```

---

## 7) `simulated_backtest_metrics`

**Purpose:** Stores historical model evaluation snapshots from simulation/backtesting runs.

### Columns
| Column | Type | Nullable | Meaning |
|---|---|---:|---|
| `id` | `BIGSERIAL` | No | Surrogate primary key. |
| `symbol` | `VARCHAR(64)` | No | Symbol used for backtest run. |
| `timeframe` | `VARCHAR(8)` | No | Timeframe used for backtest run. |
| `model_name` | `VARCHAR(128)` | No | Model type evaluated. |
| `model_version` | `VARCHAR(64)` | No | Version evaluated. |
| `run_ts` | `TIMESTAMP` | No | Backtest execution timestamp. |
| `metrics` | `JSONB` | No | Performance metrics payload. |
| `is_simulated` | `BOOLEAN` | No | Explicitly marks non-live execution context. |
| `created_at` | `TIMESTAMP` | No | DB insert timestamp. |

### Indexes / Constraints
- PK: `id`

### Code usage
- **Write:** `DatabaseManager.insert_backtest_metrics()`.
- **Read:** `DatabaseManager.get_latest_backtest_metrics(symbol, timeframe)`.

### Sample row
```json
{
  "id": 74,
  "symbol": "NSE:RELIANCE",
  "timeframe": "15m",
  "model_name": "xgb_classifier",
  "model_version": "2026-02-22T23-30-10Z",
  "run_ts": "2026-02-22T23:31:20",
  "metrics": {
    "accuracy": 0.611,
    "precision": 0.603,
    "recall": 0.627,
    "f1": 0.615,
    "walk_forward_mean_accuracy": 0.594
  },
  "is_simulated": true,
  "created_at": "2026-02-22T23:31:20.017"
}
```

---

## 8) `engine_heartbeat`

**Purpose:** Operational telemetry table for service liveness and health snapshots.

### Columns
| Column | Type | Nullable | Meaning |
|---|---|---:|---|
| `id` | `BIGSERIAL` | No | Surrogate primary key. |
| `service_name` | `VARCHAR(128)` | No | Service identity (e.g., `realtime_engine`). |
| `status` | `VARCHAR(32)` | No | Health/state label (`running`, `degraded`, `stopped`). |
| `heartbeat_ts` | `TIMESTAMP` | No | Time heartbeat was emitted. |
| `details` | `JSONB` | Yes | Optional structured runtime telemetry. |
| `created_at` | `TIMESTAMP` | No | DB insert timestamp. |

### Indexes / Constraints
- PK: `id`

### Code usage
- **Write:** `DatabaseManager.write_heartbeat()`.
- **Read:** no dedicated helper yet (typically queried by operations dashboards/scripts).

### Sample row
```json
{
  "id": 9055,
  "service_name": "realtime_engine",
  "status": "running",
  "heartbeat_ts": "2026-02-23T10:30:15",
  "details": {
    "ws_connected": true,
    "queue_dropped_ticks": 0,
    "loaded_models": ["15m", "1d"]
  },
  "created_at": "2026-02-23T10:30:15.005"
}
```

---

## Cross-table flow (what each table will hold over time)

1. **Tick ingress:** high-volume raw packets accumulate in `realtime_ticks`.
2. **Aggregation:** each timeframe window materializes/upserts rows in `ohlcv_candles`.
3. **Inference lineage:** every scored signal appends a row in `prediction_events`.
4. **Risk governance:** any guardrail trigger appends to `risk_events` and may annotate `prediction_events.risk_snapshot`.
5. **Compliance:** lifecycle/system actions append to `compliance_audit_trail`.
6. **Model lifecycle:** trained artifacts and metadata live in `model_registry`; performance snapshots append to `simulated_backtest_metrics`.
7. **Operations:** runtime health emits periodic `engine_heartbeat` rows.

## Implementation notes
- JSON payload columns are intentionally JSONB for schema-flexible metadata (`metrics`, `details`, explainability/risk payloads).
- Python write helpers serialize maps/lists with `json.dumps(..., default=str)` and cast to JSONB in SQL.
- Most tables are append-only event logs; notable upsert tables are `ohlcv_candles` and `model_registry`.
