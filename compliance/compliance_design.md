# Compliance Design (SEBI-Aware Research Analytics)

## Scope and Positioning
- System purpose: **research and analytics signal generation** for NSE instruments.
- Output type: BULLISH/BEARISH/HOLD signals with confidence and explainability.
- Explicitly excluded: auto-order placement, broker execution, unattended algo trading.

## Core SEBI-Safe Controls
- `compliance/disclaimer.py` provides a clear disclaimer version and risk disclosure text.
- Dashboard renders disclaimer and risk disclosure prominently on top.
- Every prediction write includes:
  - `prediction_ts`
  - `model_name`
  - `model_version`
  - `feature_snapshot` (JSON)
  - `prob_up`, `prob_down`, confidence
  - `explainability` summary
  - `risk_snapshot`
- `database/compliance_audit_trail` stores immutable audit events.
- Backtest table and UI are labeled as **simulated performance**.

## Data Governance and Auditability
- `database/prediction_events` stores full prediction lineage and compliance note.
- `database/compliance_audit_trail` stores lifecycle events (`engine_start`, `prediction_generated`, `engine_stop`).
- `database/engine_heartbeat` records service liveness and state metadata.

## Model Governance
- Model artifacts are versioned locally (`models/artifacts/*.pkl`).
- Model metadata is stored in Postgres `model_registry` with metrics + feature list.
- Explainability is produced from feature importances/coefficients proxy to avoid black-box-only outputs.

## Risk & Governance Module
- `compliance/risk_manager.py` enforces:
  - signal throttling (cooldown)
  - max capital allocation cap (simulation)
  - stop-loss simulation
  - drawdown monitor with hard guardrail
- If guardrail trips, signal is downgraded to HOLD and logged as risk event.

## Communication and Disclosure Rules
- Do not display projected return promises.
- Any historical/backtest metric is shown as simulated and non-guaranteed.
- UI copy avoids assurance language and highlights market risk.

## Operational Considerations
- WebSocket disconnects: Kite auto-reconnect enabled with reconnect callbacks and heartbeat logging.
- Market holidays: optional `config/market_holidays.json` is applied by candle aggregator.
- Partial days: optional per-date close overrides via `partial_market_closes` config.

## Extension Guardrails
- If execution is added in future, separate it into a distinct service with:
  - explicit user authorization,
  - broker-level risk checks,
  - order throttling,
  - pre-trade and post-trade audit logs,
  - legal/compliance sign-off.
