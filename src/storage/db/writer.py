from loguru import logger
from sqlalchemy.exc import IntegrityError
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy import func

from .models import (
    SymbolMaster,
    MarketData,
    News,
    StockPrediction,
    ModelBacktestResult,
    ComplianceConsent,
    ComplianceAuditLog,
)


# ---------------- SYMBOL MASTER ----------------

def save_symbols(session, symbols):

    logger.info("Saving symbols master")

    for s in symbols:

        obj = SymbolMaster(**s)

        session.add(obj)

        try:
            session.commit()

        except IntegrityError:
            session.rollback()


def get_active_symbols(session):

    rows = session.query(SymbolMaster)\
        .filter_by(active=True)\
        .all()

    return [r.symbol for r in rows]


# ---------------- MARKET DATA ----------------

def save_market_data(session, records):

    if not records:
        return

    logger.info(f"Saving {len(records)} rows")

    deduped = {}
    for row in records:
        key = (row.get("symbol"), row.get("date"), row.get("source"))
        deduped[key] = row
    payload = list(deduped.values())
    if not payload:
        return

    stmt = pg_insert(MarketData).values(payload)
    update_map = {
        "open": stmt.excluded.open,
        "high": stmt.excluded.high,
        "low": stmt.excluded.low,
        "close": stmt.excluded.close,
        "volume": stmt.excluded.volume,
        "traded_value": stmt.excluded.traded_value,
        "vwap": stmt.excluded.vwap,
    }
    stmt = stmt.on_conflict_do_update(
        index_elements=["symbol", "date", "source"],
        set_=update_map,
    )

    try:

        session.execute(stmt)
        session.commit()
        logger.info("Committed")

    except IntegrityError:

        session.rollback()
        logger.warning("Duplicates skipped")

    except Exception as e:

        session.rollback()
        logger.error(e)


def get_symbol_price_df(session, symbol):

    rows = (
        session.query(MarketData)
        .filter(MarketData.symbol == symbol)
        .order_by(MarketData.date.asc())
        .all()
    )
    if not rows:
        return None

    import pandas as pd

    return pd.DataFrame(
        [
            {
                "date": r.date,
                "open": r.open,
                "high": r.high,
                "low": r.low,
                "close": r.close,
                "volume": r.volume,
            }
            for r in rows
        ]
    )


def get_latest_market_timestamp(session, symbol):

    return (
        session.query(func.max(MarketData.date))
        .filter(MarketData.symbol == symbol)
        .scalar()
    )


def get_symbol_news_df(session, symbol):

    rows = (
        session.query(News)
        .filter(News.symbol == symbol)
        .order_by(News.published_at.asc())
        .all()
    )

    import pandas as pd

    return pd.DataFrame(
        [
            {
                "published_at": r.published_at,
                "sentiment_score": r.sentiment_score,
            }
            for r in rows
        ]
    )


def save_stock_prediction(session, prediction):

    if not prediction:
        return

    stmt = pg_insert(StockPrediction).values([prediction])
    stmt = stmt.on_conflict_do_update(
        index_elements=["symbol", "target_date", "model_name"],
        set_={
            "prediction_date": stmt.excluded.prediction_date,
            "predicted_return": stmt.excluded.predicted_return,
            "predicted_close": stmt.excluded.predicted_close,
            "direction": stmt.excluded.direction,
            "train_rows": stmt.excluded.train_rows,
            "r2_score": stmt.excluded.r2_score,
        },
    )

    try:
        session.execute(stmt)
        session.commit()
        logger.info(
            f"Saved prediction for {prediction['symbol']} ({prediction['target_date']})"
        )
    except Exception as e:
        session.rollback()
        logger.error(f"Prediction save failed: {e}")


def save_model_backtest_result(session, result):

    if not result:
        return

    stmt = pg_insert(ModelBacktestResult).values([result])
    stmt = stmt.on_conflict_do_update(
        index_elements=["symbol", "model_name", "run_date"],
        set_={
            "sample_count": stmt.excluded.sample_count,
            "directional_accuracy": stmt.excluded.directional_accuracy,
            "mae": stmt.excluded.mae,
            "rmse": stmt.excluded.rmse,
            "avg_true_return": stmt.excluded.avg_true_return,
            "avg_pred_return": stmt.excluded.avg_pred_return,
            "cumulative_return": stmt.excluded.cumulative_return,
            "strategy_return": stmt.excluded.strategy_return,
        },
    )

    try:
        session.execute(stmt)
        session.commit()
        logger.info(
            f"Saved backtest for {result['symbol']} ({result['model_name']})"
        )
    except Exception as e:
        session.rollback()
        logger.error(f"Backtest save failed: {e}")


def save_compliance_consent(session, consent):

    if not consent:
        return

    stmt = pg_insert(ComplianceConsent).values([consent])
    stmt = stmt.on_conflict_do_update(
        index_elements=["user_key", "disclaimer_version"],
        set_={
            "accepted_at": stmt.excluded.accepted_at,
            "app_version": stmt.excluded.app_version,
        },
    )

    try:
        session.execute(stmt)
        session.commit()
        logger.info(
            f"Saved compliance consent for {consent.get('user_key')} ({consent.get('disclaimer_version')})"
        )
    except Exception as e:
        session.rollback()
        logger.error(f"Compliance consent save failed: {e}")


def get_latest_compliance_consent(session, user_key, disclaimer_version):

    return (
        session.query(ComplianceConsent)
        .filter(ComplianceConsent.user_key == user_key)
        .filter(ComplianceConsent.disclaimer_version == disclaimer_version)
        .order_by(ComplianceConsent.accepted_at.desc(), ComplianceConsent.id.desc())
        .first()
    )


def save_compliance_audit_log(session, audit_event):

    if not audit_event:
        return

    obj = ComplianceAuditLog(**audit_event)
    session.add(obj)

    try:
        session.commit()
    except Exception as e:
        session.rollback()
        logger.error(f"Compliance audit save failed: {e}")
