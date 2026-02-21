from loguru import logger
from sqlalchemy.dialects.postgresql import insert as pg_insert
from src.storage.db.connection import SessionLocal
from src.storage.db.models import News


def save_news(news_list):

    if not news_list:
        return

    deduped = {}
    for row in news_list:
        key = (row.get("symbol"), row.get("title"), row.get("published_at"))
        deduped[key] = row
    payload = list(deduped.values())
    if not payload:
        return

    session = SessionLocal()

    try:
        stmt = pg_insert(News).values(payload)
        stmt = stmt.on_conflict_do_update(
            index_elements=["symbol", "title", "published_at"],
            set_={
                "summary": stmt.excluded.summary,
                "url": stmt.excluded.url,
                "source": stmt.excluded.source,
                "sentiment_score": stmt.excluded.sentiment_score,
                "sentiment_label": stmt.excluded.sentiment_label,
            },
        )
        session.execute(stmt)

        session.commit()

        logger.info(f"Saved {len(payload)} news records")

    except Exception as e:

        session.rollback()

        logger.error(f"News save failed: {e}")

    finally:
        session.close()
