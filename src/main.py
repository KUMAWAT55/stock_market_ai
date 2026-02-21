import sys
from loguru import logger

from src.ingestion.nse.symbols import fetch_nse_symbols
from src.ingestion.yahoo.fetcher import fetch_yahoo_data
from src.pipelines.normalizer import normalize_yahoo
from src.ingestion.news.fetcher import fetch_news
from src.pipelines.news_loader import save_news
from src.pipelines.predictor import train_and_predict_next_day
from src.pipelines.backtester import run_backtest_models

from src.storage.db.connection import SessionLocal
from src.storage.db.writer import (
    save_symbols,
    get_active_symbols,
    save_market_data,
    get_symbol_price_df,
    get_symbol_news_df,
    save_stock_prediction,
    save_model_backtest_result,
)

from src.configs.settings import (
    LOG_PATH,
    YAHOO_PERIOD,
    BACKTEST_MIN_TRAIN_ROWS,
    BACKTEST_STEP,
    BACKTEST_TRAIN_WINDOW,
    BACKTEST_MAX_EVAL_POINTS,
)


# Logging
logger.add(LOG_PATH, rotation="5 MB", level="INFO")


def run():

    logger.info("Starting Stock Market AI Platform")

    db = SessionLocal()
    # 0 Create tables


    # 1. Load symbol master
    symbols = fetch_nse_symbols()

    save_symbols(db, symbols)

    # 2. Read active symbols
    active_symbols = get_active_symbols(db)

    logger.info(f"Active symbols: {len(active_symbols)}")

    # Safety limit first run
    active_symbols = active_symbols[:10]

    # 3. Ingestion loop
    for sym in active_symbols:
        nse_sym=sym+".NS"
        df, info = fetch_yahoo_data(nse_sym, YAHOO_PERIOD)
        records = normalize_yahoo(df, info,sym)

        save_market_data(db, records)
    # News
        news = fetch_news(sym)

        save_news(news)

        price_df = get_symbol_price_df(db, sym)
        news_df = get_symbol_news_df(db, sym)
        predictions = train_and_predict_next_day(sym, price_df, news_df)
        for prediction in predictions:
            save_stock_prediction(db, prediction)

        backtest_results = run_backtest_models(
            sym,
            price_df,
            news_df,
            min_train_rows=BACKTEST_MIN_TRAIN_ROWS,
            step=BACKTEST_STEP,
            train_window=BACKTEST_TRAIN_WINDOW,
            max_eval_points=BACKTEST_MAX_EVAL_POINTS,
        )
        for result in backtest_results:
            save_model_backtest_result(db, result)

    db.close()

    logger.info("Pipeline finished")


if __name__ == "__main__":

    try:
        run()

    except Exception as e:

        logger.critical(f"Fatal error: {e}")
        sys.exit(1)
