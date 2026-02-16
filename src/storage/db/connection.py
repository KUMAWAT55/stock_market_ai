from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from configs.settings import DB_URL


engine = create_engine(DB_URL, pool_pre_ping=True)

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)
