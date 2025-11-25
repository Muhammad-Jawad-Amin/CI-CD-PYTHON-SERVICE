import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base


DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./library.db")

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False} if "sqlite" in DATABASE_URL else {},
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    """
    Dependency function that provides a database session.

    This generator function:
    1. Creates a new SQLAlchemy session
    2. Yields it to the caller (FastAPI endpoint)
    3. Ensures the session is closed after use (in finally block)

    The yield mechanism allows FastAPI to inject this dependency
    and automatically handle cleanup.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
