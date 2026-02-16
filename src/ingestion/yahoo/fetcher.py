import yfinance as yf
from loguru import logger


def fetch_yahoo_data(symbol, period="1y"):

    logger.info(f"Fetching Yahoo: {symbol}")

    try:

        ticker = yf.Ticker(symbol)

        hist = ticker.history(period=period)

        info = ticker.info

        if hist is None or hist.empty:
            return None, None

        return hist, info

    except Exception as e:

        logger.error(f"Yahoo error {symbol}: {e}")

        return None, None
