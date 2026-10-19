"""SQLite / SQLAlchemy skeleton for Phase 1 — schema placeholders only."""

from __future__ import annotations

from pathlib import Path

from sqlalchemy import Column, DateTime, Integer, String, Text, create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from services.paths import ensure_data_dirs, get_data_root


class Base(DeclarativeBase):
    pass


class TaskRow(Base):
    __tablename__ = "tasks"

    id = Column(Integer, primary_key=True, autoincrement=True)
    state = Column(String(32), nullable=False, default="IDLE")
    created_at = Column(DateTime)
    note = Column(Text, default="")


class TaskLogRow(Base):
    __tablename__ = "task_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    task_id = Column(Integer, nullable=True)
    level = Column(String(16), default="INFO")
    message = Column(Text, nullable=False)


def get_default_db_path() -> Path:
    ensure_data_dirs()
    return get_data_root() / "db" / "app.sqlite"


class DatabaseSkeleton:
    """Minimal engine bootstrap — full CRUD arrives in Phase 2."""

    def __init__(self, db_path: Path | None = None) -> None:
        self.db_path = Path(db_path) if db_path else get_default_db_path()
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.engine = create_engine(f"sqlite:///{self.db_path}", future=True)
        self._session_factory = sessionmaker(bind=self.engine, expire_on_commit=False)

    def create_schema(self) -> None:
        Base.metadata.create_all(self.engine)

    def session(self) -> Session:
        return self._session_factory()
