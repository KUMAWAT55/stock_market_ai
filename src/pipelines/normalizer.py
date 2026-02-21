import pandas as pd
from loguru import logger


def normalize_yahoo(df, info, symbol):

    logger.info(f"Normalizing {symbol}")

    records = []

    if df is None or df.empty:
        return records

    df = df.reset_index()
    time_col = "Datetime" if "Datetime" in df.columns else "Date"

    for _, row in df.iterrows():

        try:
            ts = pd.to_datetime(row[time_col], errors="coerce")
            if pd.isna(ts):
                continue
            if getattr(ts, "tzinfo", None) is not None:
                ts = ts.tz_localize(None)

            rec = {

                "symbol": symbol,
                "date": ts,
                "source": "yahoo",

                # Prices
                "open": float(row["Open"]),
                "high": float(row["High"]),
                "low": float(row["Low"]),
                "close": float(row["Close"]),

                # Volume
                "volume": int(row["Volume"]),
                "traded_value": float(row["Close"]) * int(row["Volume"]),
                "vwap": float((row["High"] + row["Low"] + row["Close"]) / 3),
            }

            records.append(rec)

        except Exception as e:

            logger.warning(f"Skip row: {e}")

    return records
