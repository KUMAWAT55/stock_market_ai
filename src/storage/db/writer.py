from loguru import logger
from sqlalchemy.exc import IntegrityError

from .models import SymbolMaster, MarketData, News, StockPrediction, ModelBacktestResult


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

    for r in records:

        session.add(MarketData(**r))

    try:

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

    existing = (
        session.query(StockPrediction)
        .filter(
            StockPrediction.symbol == prediction["symbol"],
            StockPrediction.target_date == prediction["target_date"],
            StockPrediction.model_name == prediction["model_name"],
        )
        .first()
    )

    if existing:
        existing.prediction_date = prediction["prediction_date"]
        existing.predicted_return = prediction["predicted_return"]
        existing.predicted_close = prediction["predicted_close"]
        existing.direction = prediction["direction"]
        existing.train_rows = prediction["train_rows"]
        existing.r2_score = prediction["r2_score"]
    else:
        session.add(StockPrediction(**prediction))

    try:
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

    existing = (
        session.query(ModelBacktestResult)
        .filter(
            ModelBacktestResult.symbol == result["symbol"],
            ModelBacktestResult.model_name == result["model_name"],
            ModelBacktestResult.run_date == result["run_date"],
        )
        .first()
    )

    if existing:
        existing.sample_count = result["sample_count"]
        existing.directional_accuracy = result["directional_accuracy"]
        existing.mae = result["mae"]
        existing.rmse = result["rmse"]
        existing.avg_true_return = result["avg_true_return"]
        existing.avg_pred_return = result["avg_pred_return"]
        existing.cumulative_return = result["cumulative_return"]
        existing.strategy_return = result["strategy_return"]
    else:
        session.add(ModelBacktestResult(**result))

    try:
        session.commit()
        logger.info(
            f"Saved backtest for {result['symbol']} ({result['model_name']})"
        )
    except Exception as e:
        session.rollback()
        logger.error(f"Backtest save failed: {e}")
