from __future__ import annotations

from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from adaptive_tutor.config import ensure_data_dir
from adaptive_tutor.models.db_models import Base


def _sqlite_url() -> str:
    db_path = ensure_data_dir()
    return f"sqlite:///{db_path}"


engine = create_engine(_sqlite_url(), echo=False, future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False, future=True)


def init_db() -> None:
    Base.metadata.create_all(bind=engine)


@contextmanager
def session_scope() -> Session:
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
