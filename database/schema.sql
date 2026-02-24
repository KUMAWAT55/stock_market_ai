CREATE TABLE IF NOT EXISTS realtime_ticks (
    id BIGSERIAL PRIMARY KEY,
    instrument_token BIGINT NOT NULL,
    symbol VARCHAR(64) NOT NULL,
    ts TIMESTAMP NOT NULL,
    last_price DOUBLE PRECISION NOT NULL,
    last_traded_quantity BIGINT,
    total_buy_quantity BIGINT,
    total_sell_quantity BIGINT,
    volume BIGINT,
    oi BIGINT,
    source VARCHAR(32) NOT NULL DEFAULT 'kite_ws',
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_realtime_ticks_symbol_ts
    ON realtime_ticks(symbol, ts DESC);


CREATE TABLE IF NOT EXISTS ohlcv_candles (
    id BIGSERIAL PRIMARY KEY,
    symbol VARCHAR(64) NOT NULL,
    timeframe VARCHAR(8) NOT NULL,
    candle_start TIMESTAMP NOT NULL,
    candle_end TIMESTAMP NOT NULL,
    open DOUBLE PRECISION NOT NULL,
    high DOUBLE PRECISION NOT NULL,
    low DOUBLE PRECISION NOT NULL,
    close DOUBLE PRECISION NOT NULL,
    volume BIGINT NOT NULL DEFAULT 0,
    tick_count INTEGER NOT NULL DEFAULT 0,
    is_partial BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    UNIQUE(symbol, timeframe, candle_start)
);

CREATE INDEX IF NOT EXISTS idx_ohlcv_candles_symbol_tf_end
    ON ohlcv_candles(symbol, timeframe, candle_end DESC);


CREATE TABLE IF NOT EXISTS model_registry (
    id BIGSERIAL PRIMARY KEY,
    model_name VARCHAR(128) NOT NULL,
    timeframe VARCHAR(8) NOT NULL,
    version VARCHAR(64) NOT NULL,
    artifact_path TEXT NOT NULL,
    metrics JSONB,
    feature_list JSONB,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    UNIQUE(model_name, timeframe, version)
);


CREATE TABLE IF NOT EXISTS prediction_events (
    id BIGSERIAL PRIMARY KEY,
    symbol VARCHAR(64) NOT NULL,
    timeframe VARCHAR(8) NOT NULL,
    prediction_ts TIMESTAMP NOT NULL,
    target_ts TIMESTAMP NOT NULL,
    signal VARCHAR(8) NOT NULL,
    confidence DOUBLE PRECISION NOT NULL,
    prob_up DOUBLE PRECISION NOT NULL,
    prob_down DOUBLE PRECISION NOT NULL,
    model_name VARCHAR(128) NOT NULL,
    model_version VARCHAR(64) NOT NULL,
    feature_snapshot JSONB NOT NULL,
    explainability JSONB,
    risk_snapshot JSONB,
    compliance_note TEXT,
    is_simulated BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_prediction_events_symbol_tf_ts
    ON prediction_events(symbol, timeframe, prediction_ts DESC);


CREATE TABLE IF NOT EXISTS risk_events (
    id BIGSERIAL PRIMARY KEY,
    symbol VARCHAR(64) NOT NULL,
    timeframe VARCHAR(8) NOT NULL,
    event_ts TIMESTAMP NOT NULL,
    event_type VARCHAR(64) NOT NULL,
    payload JSONB NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);


CREATE TABLE IF NOT EXISTS compliance_audit_trail (
    id BIGSERIAL PRIMARY KEY,
    event_ts TIMESTAMP NOT NULL,
    event_type VARCHAR(128) NOT NULL,
    actor VARCHAR(64) NOT NULL DEFAULT 'system',
    symbol VARCHAR(64),
    timeframe VARCHAR(8),
    details JSONB NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_compliance_audit_trail_event_ts
    ON compliance_audit_trail(event_ts DESC);


CREATE TABLE IF NOT EXISTS simulated_backtest_metrics (
    id BIGSERIAL PRIMARY KEY,
    symbol VARCHAR(64) NOT NULL,
    timeframe VARCHAR(8) NOT NULL,
    model_name VARCHAR(128) NOT NULL,
    model_version VARCHAR(64) NOT NULL,
    run_ts TIMESTAMP NOT NULL,
    metrics JSONB NOT NULL,
    is_simulated BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);


CREATE TABLE IF NOT EXISTS engine_heartbeat (
    id BIGSERIAL PRIMARY KEY,
    service_name VARCHAR(128) NOT NULL,
    status VARCHAR(32) NOT NULL,
    heartbeat_ts TIMESTAMP NOT NULL,
    details JSONB,
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);


CREATE TABLE IF NOT EXISTS app_users (
    id BIGSERIAL PRIMARY KEY,
    username VARCHAR(64) NOT NULL UNIQUE,
    email VARCHAR(256) NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    full_name VARCHAR(128),
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_app_users_username
    ON app_users(username);

CREATE INDEX IF NOT EXISTS idx_app_users_email
    ON app_users(email);


CREATE TABLE IF NOT EXISTS user_subscriptions (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL REFERENCES app_users(id) ON DELETE CASCADE,
    plan_name VARCHAR(64) NOT NULL DEFAULT 'TradeIQ Pro',
    status VARCHAR(32) NOT NULL DEFAULT 'active',
    start_at TIMESTAMP,
    end_at TIMESTAMP,
    payment_reference VARCHAR(128),
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    UNIQUE(user_id)
);


CREATE TABLE IF NOT EXISTS compliance_consents (
    id BIGSERIAL PRIMARY KEY,
    user_key VARCHAR(128) NOT NULL,
    disclaimer_version VARCHAR(64) NOT NULL,
    accepted_at TIMESTAMP NOT NULL DEFAULT NOW(),
    app_version VARCHAR(64),
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    UNIQUE(user_key, disclaimer_version)
);

CREATE INDEX IF NOT EXISTS idx_compliance_consents_user_key
    ON compliance_consents(user_key);


CREATE TABLE IF NOT EXISTS compliance_audit_logs (
    id BIGSERIAL PRIMARY KEY,
    user_key VARCHAR(128) NOT NULL,
    event_type VARCHAR(128) NOT NULL,
    symbol VARCHAR(64),
    payload JSONB,
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_compliance_audit_logs_user_key
    ON compliance_audit_logs(user_key, created_at DESC);
