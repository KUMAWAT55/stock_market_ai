from sqlalchemy import (
    Column, Integer, String, Float,
    Date, Boolean, BigInteger, TIMESTAMP
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.sql import func

from sqlalchemy import Text, DateTime
from datetime import datetime

Base = declarative_base()


# ---------------- SYMBOL MASTER ----------------

class SymbolMaster(Base):

    __tablename__ = "symbols_master"

    id = Column(Integer, primary_key=True)

    symbol = Column(String, unique=True, nullable=False)
    name = Column(String)
    exchange = Column(String)
    series = Column(String)
    date_of_listing = Column(String)
    paid_up_value = Column(String)
    market_lot = Column(String)
    isin_number = Column(String)
    face_value = Column(String)
    active = Column(Boolean, default=True)
    created_at = Column(TIMESTAMP, server_default=func.now())


# ---------------- MARKET DATA ----------------

class MarketData(Base):

    __tablename__ = "market_data"

    id = Column(Integer, primary_key=True)

    symbol = Column(String, nullable=False)
    date = Column(Date, nullable=False)
    source = Column(String, nullable=False)

    open = Column(Float)
    high = Column(Float)
    low = Column(Float)
    close = Column(Float)
    adj_close = Column(Float)

    volume = Column(BigInteger)
    traded_value = Column(Float)
    vwap = Column(Float)

    dividend = Column(Float)
    split = Column(Float)

    market_cap = Column(BigInteger)
    pe_ratio = Column(Float)
    eps = Column(Float)
    book_value = Column(Float)
    dividend_yield = Column(Float)
    beta = Column(Float)

    sector = Column(String)
    industry = Column(String)
    exchange = Column(String)
    currency = Column(String)

    created_at = Column(TIMESTAMP, server_default=func.now())



class News(Base):

    __tablename__ = "market_news"

    id = Column(Integer, primary_key=True)

    symbol = Column(String, index=True)
    title = Column(String)

    summary = Column(Text)
    url = Column(String)

    source = Column(String)

    published_at = Column(DateTime)
    sentiment_score = Column(Float, default=0.0)
    sentiment_label = Column(String, default="neutral")

    created_at = Column(
        DateTime,
        default=datetime.utcnow
    )


class StockPrediction(Base):

    __tablename__ = "stock_predictions"

    id = Column(Integer, primary_key=True)

    symbol = Column(String, index=True, nullable=False)
    prediction_date = Column(Date, nullable=False)
    target_date = Column(Date, nullable=False)

    predicted_return = Column(Float)
    predicted_close = Column(Float)
    direction = Column(String)

    model_name = Column(String, nullable=False, default="random_forest_v1")
    train_rows = Column(Integer)
    r2_score = Column(Float)

    created_at = Column(DateTime, default=datetime.utcnow)
