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

    created_at = Column(
        DateTime,
        default=datetime.utcnow
    )