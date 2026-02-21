import pandas as pd
from loguru import logger


NSE_URL = "https://archives.nseindia.com/content/equities/EQUITY_L.csv"


def fetch_nse_symbols():

    logger.info("Fetching NSE symbols")

    df = pd.read_csv(NSE_URL)
    symbols_to_filter = ["TATACAP", "TATAELXSI", "MRF", "RELIANCE" , "ICICIBANK" , "HDFCBANK" , "BHARTIARTL","SBIN","TCS"]
    df = df[df["SYMBOL"].isin(symbols_to_filter)]
    symbols = []

    for _, row in df.iterrows():

        symbols.append({
            "symbol": row["SYMBOL"] ,
            "name": row["NAME OF COMPANY"],
            "exchange": "NSE",
            "series" : row[" SERIES"],
            "date_of_listing" : row[" DATE OF LISTING"],
            "paid_up_value": row[" PAID UP VALUE"],
            "market_lot": row[" MARKET LOT"],
            "isin_number": row[" ISIN NUMBER"],
            "face_value": row[" FACE VALUE"]

        })

    logger.info(f"Fetched {len(symbols)} symbols")

    return symbols

fetch_nse_symbols()

