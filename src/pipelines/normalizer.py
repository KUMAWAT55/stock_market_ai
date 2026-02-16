import pandas as pd
from loguru import logger


def normalize_yahoo(df, info, symbol):

    logger.info(f"Normalizing {symbol}")

    records = []

    if df is None or df.empty:
        return records

    df = df.reset_index()

    for _, row in df.iterrows():

        try:

            rec = {

                "symbol": symbol,
                "date": pd.to_datetime(row["Date"]).date(),
                "source": "yahoo",

                # Prices
                "open": float(row["Open"]),
                "high": float(row["High"]),
                "low": float(row["Low"]),
                "close": float(row["Close"]),
                "adj_close": float(row.get("Adj Close", row["Close"])),

                # Volume
                "volume": int(row["Volume"]),
                "traded_value": float(row["Close"]) * int(row["Volume"]),
                "vwap": float((row["High"] + row["Low"] + row["Close"]) / 3),

                # Corporate
                "dividend": float(row.get("Dividends", 0)),
                "split": float(row.get("Stock Splits", 0)),

                # Fundamentals
                "market_cap": info.get("marketCap"),
                "pe_ratio": info.get("trailingPE"),
                "eps": info.get("trailingEps"),
                "book_value": info.get("bookValue"),
                "dividend_yield": info.get("dividendYield"),
                "beta": info.get("beta"),

                # Meta
                "sector": info.get("sector"),
                "industry": info.get("industry"),
                "exchange": info.get("exchange"),
                "currency": info.get("currency")
            }

            records.append(rec)

        except Exception as e:

            logger.warning(f"Skip row: {e}")

    return records
