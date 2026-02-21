DB_URL = "postgresql://localhost:5432/stock_market_ai"

LOG_PATH = "logs/ui.log"

YAHOO_PERIOD = "10y"

# Backtest controls (tuned for faster pipeline execution)
BACKTEST_MIN_TRAIN_ROWS = 100
BACKTEST_STEP = 4
BACKTEST_TRAIN_WINDOW = 260
BACKTEST_MAX_EVAL_POINTS = 80
