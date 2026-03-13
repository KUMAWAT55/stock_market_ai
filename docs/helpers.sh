pkill -9 -f postgres
pkill -9 -f node

pkill -9 -f models.train
pkill -9 -f uvicorn
pkill -9 -f npm



uvicorn api.main:app --host 127.0.0.1 --port 8000 --reload
streamlit run dashboard/streamlit_app.py


python3 scripts/generate_kite_token.py --api-key 0i8q0sfgfnmipuvk --print-login-url
python3 scripts/generate_kite_token.py \
  --api-key 0i8q0sfgfnmipuvk \
  --api-secret 0482yfqikiub3dggpyjd6dnv7pqg452a \
  --request-token tKPFU3OuY0EovHYLhYkKWgfROO21DovV


python3 -m models.train --timeframe 1m --lookback-days 60 --all-symbols
python3 -m models.train --timeframe 5m --lookback-days 180 --all-symbols
python3 -m models.train --timeframe 15m --lookback-days 240 --all-symbols
python3 -m models.train --timeframe 1h --lookback-days 365 --all-symbols
python3 -m models.train --timeframe 1d --lookback-days 720 --all-symbols


python3 -m models.train --timeframe 1m --lookback-days 60 --all-symbols --use-db
python3 -m models.train --timeframe 5m --lookback-days 150 --all-symbols --use-db
python3 -m models.train --timeframe 15m --lookback-days 365 --all-symbols --use-db
python3 -m models.train --timeframe 1h --lookback-days 1000 --all-symbols --use-db
python3 -m models.train --timeframe 1d --lookback-days 2000 --all-symbols --use-db






python3 scripts/backfill_manual.py --symbols ICICIBANK,RELIANCE,TCS --timeframes 1m,5m,15m,1h,1d


TRUNCATE TABLE
  realtime_ticks,
  ohlcv_candles,
  model_registry,
  prediction_events,
  risk_events,
  compliance_audit_trail,
  simulated_backtest_metrics,
  engine_heartbeat,
  app_users,
  user_subscriptions,
  compliance_consents,
  compliance_audit_logs,
  contact_messages
RESTART IDENTITY
CASCADE;