import sys
from loguru import logger

from src.ingestion.nse.symbols import fetch_nse_symbols
from src.ingestion.yahoo.fetcher import fetch_yahoo_data
from src.pipelines.normalizer import normalize_yahoo
from src.ingestion.news.fetcher import fetch_news
from src.pipelines.news_loader import save_news

from src.storage.db.connection import SessionLocal
from src.storage.db.writer import (
    save_symbols,
    get_active_symbols,
    save_market_data
)

from src.configs.settings import LOG_PATH, YAHOO_PERIOD


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
    active_symbols = active_symbols[:5]

    # 3. Ingestion loop
    for sym in active_symbols:
        nse_sym=sym+".NS"
        df, info = fetch_yahoo_data(nse_sym, YAHOO_PERIOD)
        records = normalize_yahoo(df, info,sym)

        save_market_data(db, records)
    # News
        news = fetch_news((sym))

        save_news(news)

    db.close()

    logger.info("Pipeline finished")


if __name__ == "__main__":

    try:
        run()

    except Exception as e:

        logger.critical(f"Fatal error: {e}")
        sys.exit(1)
