"""Database engine and session helpers for the PHC AI Supervisor app."""

import os
from pathlib import Path
from typing import Final

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, declarative_base, scoped_session, sessionmaker


BASE_DIR: Final[Path] = Path(__file__).resolve().parent
DATABASE_DIR: Final[Path] = Path(
    os.getenv("RAILWAY_VOLUME_MOUNT_PATH", os.getenv("DB_DIR", str(BASE_DIR)))
)
DATABASE_FILE: Final[Path] = Path(
    os.getenv("DB_PATH", str(DATABASE_DIR / "health_agent.db"))
)
DATABASE_URL: Final[str] = f"sqlite:///{DATABASE_FILE}"

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False},
    future=True,
)
SessionLocal = scoped_session(
    sessionmaker(autocommit=False, autoflush=False, bind=engine)
)
Base = declarative_base()


def get_db_session() -> Session:
    """Return a scoped SQLAlchemy session."""
    return SessionLocal()


def init_db() -> None:
    """Create all database tables if they do not already exist."""
    import models  # noqa: F401

    Base.metadata.create_all(bind=engine)
