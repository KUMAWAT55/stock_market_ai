from sqlalchemy import (
    Column, Integer, String, Float,
    Date, Boolean, BigInteger, TIMESTAMP, UniqueConstraint
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
    __table_args__ = (
        UniqueConstraint("symbol", "date", "source", name="uq_market_data_symbol_date_source"),
    )

    id = Column(Integer, primary_key=True)

    symbol = Column(String, nullable=False)
    date = Column(DateTime, nullable=False, index=True)
    source = Column(String, nullable=False)

    open = Column(Float)
    high = Column(Float)
    low = Column(Float)
    close = Column(Float)

    volume = Column(BigInteger)
    traded_value = Column(Float)
    vwap = Column(Float)

    created_at = Column(TIMESTAMP, server_default=func.now())



class News(Base):

    __tablename__ = "market_news"
    __table_args__ = (
        UniqueConstraint("symbol", "title", "published_at", name="uq_market_news_symbol_title_published_at"),
    )

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
    __table_args__ = (
        UniqueConstraint("symbol", "target_date", "model_name", name="uq_stock_predictions_symbol_target_model"),
    )

    id = Column(Integer, primary_key=True)

    symbol = Column(String, index=True, nullable=False)
    prediction_date = Column(DateTime, nullable=False)
    target_date = Column(DateTime, nullable=False)

    predicted_return = Column(Float)
    predicted_close = Column(Float)
    direction = Column(String)

    model_name = Column(String, nullable=False, default="random_forest_v1")
    train_rows = Column(Integer)
    r2_score = Column(Float)

    created_at = Column(DateTime, default=datetime.utcnow)


class ModelBacktestResult(Base):

    __tablename__ = "model_backtest_results"
    __table_args__ = (
        UniqueConstraint("symbol", "model_name", "run_date", name="uq_model_backtest_results_symbol_model_run_date"),
    )

    id = Column(Integer, primary_key=True)

    symbol = Column(String, index=True, nullable=False)
    model_name = Column(String, nullable=False)
    run_date = Column(Date, nullable=False)

    sample_count = Column(Integer)
    directional_accuracy = Column(Float)
    mae = Column(Float)
    rmse = Column(Float)
    avg_true_return = Column(Float)
    avg_pred_return = Column(Float)
    cumulative_return = Column(Float)
    strategy_return = Column(Float)

    created_at = Column(DateTime, default=datetime.utcnow)
