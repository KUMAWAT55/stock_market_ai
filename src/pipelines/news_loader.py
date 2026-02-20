from loguru import logger
from src.storage.db.connection import SessionLocal
from src.storage.db.models import News


def save_news(news_list):

    if not news_list:
        return

    session = SessionLocal()

    try:

        session.bulk_insert_mappings(
            News,
            news_list
        )

        session.commit()

        logger.info(f"Saved {len(news_list)} news records")

    except Exception as e:

        session.rollback()

        logger.error(f"News save failed: {e}")

    finally:
        session.close()
