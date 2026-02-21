from __future__ import annotations

from loguru import logger
from sqlalchemy import text
from sqlalchemy.orm import Session


DEDUP_QUERIES = {
    "market_data": """
        WITH ranked AS (
            SELECT
                ctid,
                ROW_NUMBER() OVER (
                    PARTITION BY symbol, date, source
                    ORDER BY created_at DESC NULLS LAST, id DESC
                ) AS rn
            FROM market_data
        )
        DELETE FROM market_data t
        USING ranked r
        WHERE t.ctid = r.ctid
          AND r.rn > 1
    """,
    "market_news": """
        WITH ranked AS (
            SELECT
                ctid,
                ROW_NUMBER() OVER (
                    PARTITION BY symbol, title, published_at
                    ORDER BY created_at DESC NULLS LAST, id DESC
                ) AS rn
            FROM market_news
        )
        DELETE FROM market_news t
        USING ranked r
        WHERE t.ctid = r.ctid
          AND r.rn > 1
    """,
    "stock_predictions": """
        WITH ranked AS (
            SELECT
                ctid,
                ROW_NUMBER() OVER (
                    PARTITION BY symbol, target_date, model_name
                    ORDER BY created_at DESC NULLS LAST, id DESC
                ) AS rn
            FROM stock_predictions
        )
        DELETE FROM stock_predictions t
        USING ranked r
        WHERE t.ctid = r.ctid
          AND r.rn > 1
    """,
    "model_backtest_results": """
        WITH ranked AS (
            SELECT
                ctid,
                ROW_NUMBER() OVER (
                    PARTITION BY symbol, model_name, run_date
                    ORDER BY created_at DESC NULLS LAST, id DESC
                ) AS rn
            FROM model_backtest_results
        )
        DELETE FROM model_backtest_results t
        USING ranked r
        WHERE t.ctid = r.ctid
          AND r.rn > 1
    """,
}


INDEX_QUERIES = [
    """
    CREATE UNIQUE INDEX IF NOT EXISTS uq_market_data_symbol_date_source
    ON market_data(symbol, date, source)
    """,
    """
    CREATE UNIQUE INDEX IF NOT EXISTS uq_market_news_symbol_title_published_at
    ON market_news(symbol, title, published_at)
    """,
    """
    CREATE UNIQUE INDEX IF NOT EXISTS uq_stock_predictions_symbol_target_model
    ON stock_predictions(symbol, target_date, model_name)
    """,
    """
    CREATE UNIQUE INDEX IF NOT EXISTS uq_model_backtest_results_symbol_model_run_date
    ON model_backtest_results(symbol, model_name, run_date)
    """,
]


MARKET_DATA_DROP_COLUMNS = [
    "adj_close",
    "dividend",
    "split",
    "market_cap",
    "pe_ratio",
    "eps",
    "book_value",
    "dividend_yield",
    "beta",
    "sector",
    "industry",
    "exchange",
    "currency",
]


def align_market_data_intraday_schema(session: Session) -> None:
    for column in MARKET_DATA_DROP_COLUMNS:
        session.execute(text(f"ALTER TABLE market_data DROP COLUMN IF EXISTS {column}"))
    session.commit()
    logger.info("market_data table aligned to intraday schema")


def clean_and_enforce_uniqueness(session: Session) -> None:
    expected_indexes = [
        "uq_market_data_symbol_date_source",
        "uq_market_news_symbol_title_published_at",
        "uq_stock_predictions_symbol_target_model",
        "uq_model_backtest_results_symbol_model_run_date",
    ]
    existing = session.execute(
        text(
            """
            SELECT indexname
            FROM pg_indexes
            WHERE schemaname='public'
              AND indexname = ANY(:idx_names)
            """
        ),
        {"idx_names": expected_indexes},
    ).fetchall()
    if len(existing) == len(expected_indexes):
        logger.info("Uniqueness indexes already present, skipping cleanup pass")
        return

    for table_name, sql in DEDUP_QUERIES.items():
        deleted = session.execute(text(sql)).rowcount or 0
        if deleted > 0:
            logger.info(f"Removed {deleted} duplicate rows from {table_name}")
    session.commit()

    for sql in INDEX_QUERIES:
        session.execute(text(sql))
    session.commit()
    logger.info("Uniqueness indexes verified for ingestion and model outputs")
