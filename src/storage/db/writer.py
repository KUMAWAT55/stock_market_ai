from loguru import logger
from sqlalchemy.exc import IntegrityError

from .models import SymbolMaster, MarketData


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
