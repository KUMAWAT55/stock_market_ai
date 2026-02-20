from sqlalchemy import create_engine  
# Import function to create a SQLAlchemy database engine
from sqlalchemy.orm import sessionmaker  
# Import function to create a session factory

from src.configs.settings import DB_URL
# Import the database URL from your configuration settings

# Create a SQLAlchemy engine instance using the database URL.
# pool_pre_ping=True checks connections before using them, helping avoid stale connections.
engine = create_engine(DB_URL, pool_pre_ping=True)

# Create a session factory bound to the engine.
# autocommit=False: Transactions are not committed automatically.
# autoflush=False: Changes are not flushed to the database automatically.
# bind=engine: Sessions will use the above engine for DB operations.
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)