pkill -9 -f streamlit
pkill -9 -f uvicorn
pkill -9 -f models.train
pkill -9 -f postgres
pkill -9 -f npm



uvicorn api.main:app --host 127.0.0.1 --port 8000 --reload
streamlit run dashboard/streamlit_app.py


python3 scripts/generate_kite_token.py --api-key 0i8q0sfgfnmipuvk --print-login-url
python3 scripts/generate_kite_token.py \
  --api-key 0i8q0sfgfnmipuvk \
  --api-secret 0482yfqikiub3dggpyjd6dnv7pqg452a \
  --request-token xkawpMV7MKQFVhE3h5oXZDNUw8kGbps2



python3 -m models.train --timeframe 15m --lookback-days 240 --all-symbols
python3 -m models.train --timeframe 1d --lookback-days 720 --all-symbols
python3 -m models.train --timeframe 1m --lookback-days 60 --all-symbols
python3 -m models.train --timeframe 5m --lookback-days 180 --all-symbols
python3 -m models.train --timeframe 1h --lookback-days 365 --all-symbols