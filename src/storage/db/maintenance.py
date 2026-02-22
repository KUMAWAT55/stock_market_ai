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
    "compliance_consents": """
        WITH ranked AS (
            SELECT
                ctid,
                ROW_NUMBER() OVER (
                    PARTITION BY user_key, disclaimer_version
                    ORDER BY accepted_at DESC NULLS LAST, created_at DESC NULLS LAST, id DESC
                ) AS rn
            FROM compliance_consents
        )
        DELETE FROM compliance_consents t
        USING ranked r
        WHERE t.ctid = r.ctid
          AND r.rn > 1
    """,
    "app_users": """
        WITH ranked AS (
            SELECT
                ctid,
                ROW_NUMBER() OVER (
                    PARTITION BY username
                    ORDER BY created_at DESC NULLS LAST, id DESC
                ) AS rn
            FROM app_users
        )
        DELETE FROM app_users t
        USING ranked r
        WHERE t.ctid = r.ctid
          AND r.rn > 1
    """,
    "app_users_email": """
        WITH ranked AS (
            SELECT
                ctid,
                ROW_NUMBER() OVER (
                    PARTITION BY email
                    ORDER BY created_at DESC NULLS LAST, id DESC
                ) AS rn
            FROM app_users
        )
        DELETE FROM app_users t
        USING ranked r
        WHERE t.ctid = r.ctid
          AND r.rn > 1
    """,
    "user_subscriptions": """
        WITH ranked AS (
            SELECT
                ctid,
                ROW_NUMBER() OVER (
                    PARTITION BY user_id
                    ORDER BY created_at DESC NULLS LAST, id DESC
                ) AS rn
            FROM user_subscriptions
        )
        DELETE FROM user_subscriptions t
        USING ranked r
        WHERE t.ctid = r.ctid
          AND r.rn > 1
    """,
}


UNIQUE_INDEX_QUERIES = {
    "uq_market_data_symbol_date_source": """
        CREATE UNIQUE INDEX IF NOT EXISTS uq_market_data_symbol_date_source
        ON market_data(symbol, date, source)
    """,
    "uq_market_news_symbol_title_published_at": """
        CREATE UNIQUE INDEX IF NOT EXISTS uq_market_news_symbol_title_published_at
        ON market_news(symbol, title, published_at)
    """,
    "uq_stock_predictions_symbol_target_model": """
        CREATE UNIQUE INDEX IF NOT EXISTS uq_stock_predictions_symbol_target_model
        ON stock_predictions(symbol, target_date, model_name)
    """,
    "uq_model_backtest_results_symbol_model_run_date": """
        CREATE UNIQUE INDEX IF NOT EXISTS uq_model_backtest_results_symbol_model_run_date
        ON model_backtest_results(symbol, model_name, run_date)
    """,
    "uq_compliance_consents_user_version": """
        CREATE UNIQUE INDEX IF NOT EXISTS uq_compliance_consents_user_version
        ON compliance_consents(user_key, disclaimer_version)
    """,
    "uq_app_users_username": """
        CREATE UNIQUE INDEX IF NOT EXISTS uq_app_users_username
        ON app_users(username)
    """,
    "uq_app_users_email": """
        CREATE UNIQUE INDEX IF NOT EXISTS uq_app_users_email
        ON app_users(email)
    """,
    "uq_user_subscriptions_user": """
        CREATE UNIQUE INDEX IF NOT EXISTS uq_user_subscriptions_user
        ON user_subscriptions(user_id)
    """,
}


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


def _get_index_uniqueness(session: Session, index_names: list[str]) -> dict[str, bool]:
    rows = session.execute(
        text(
            """
            SELECT c.relname AS indexname, i.indisunique AS is_unique
            FROM pg_class c
            JOIN pg_index i ON i.indexrelid = c.oid
            JOIN pg_namespace n ON n.oid = c.relnamespace
            WHERE n.nspname = 'public'
              AND c.relname = ANY(:idx_names)
            """
        ),
        {"idx_names": index_names},
    ).fetchall()
    return {str(row[0]): bool(row[1]) for row in rows}


def clean_and_enforce_uniqueness(session: Session) -> None:
    expected_indexes = list(UNIQUE_INDEX_QUERIES.keys())
    index_uniqueness = _get_index_uniqueness(session, expected_indexes)
    missing_or_non_unique = [
        index_name for index_name in expected_indexes
        if not index_uniqueness.get(index_name, False)
    ]
    if not missing_or_non_unique:
        logger.info("Uniqueness indexes already present, skipping cleanup pass")
        return

    non_unique_indexes = [
        index_name for index_name in missing_or_non_unique
        if index_name in index_uniqueness and not index_uniqueness[index_name]
    ]
    if non_unique_indexes:
        logger.warning(
            "Found non-unique index definitions where unique indexes are required: "
            + ", ".join(non_unique_indexes)
        )

    for table_name, sql in DEDUP_QUERIES.items():
        deleted = session.execute(text(sql)).rowcount or 0
        if deleted > 0:
            logger.info(f"Removed {deleted} duplicate rows from {table_name}")
    session.commit()

    for index_name in non_unique_indexes:
        # Drop same-name non-unique indexes before creating required unique ones.
        session.execute(text(f'DROP INDEX IF EXISTS "{index_name}"'))
    session.commit()

    for sql in UNIQUE_INDEX_QUERIES.values():
        session.execute(text(sql))
    session.commit()
    logger.info("Uniqueness indexes verified for ingestion and model outputs")
