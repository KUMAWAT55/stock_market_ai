import yfinance as yf
from loguru import logger


def fetch_yahoo_data(symbol, period="1y", interval="1d", start=None, end=None):

    logger.info(f"Fetching Yahoo: {symbol}")

    try:

        ticker = yf.Ticker(symbol)

        history_kwargs = {
            "interval": interval,
            "auto_adjust": False,
        }
        if start is not None or end is not None:
            if start is not None:
                history_kwargs["start"] = start
            if end is not None:
                history_kwargs["end"] = end
        else:
            history_kwargs["period"] = period

        hist = ticker.history(**history_kwargs)

        info = ticker.info

        if hist is None or hist.empty:
            return None, None

        return hist, info

    except Exception as e:

        logger.error(f"Yahoo error {symbol}: {e}")

        return None, None
