"""Persistence layer skeleton (SQLite / SQLAlchemy — Phase 2 fleshes this out)."""

from storage.database import DatabaseSkeleton, get_default_db_path

__all__ = ["DatabaseSkeleton", "get_default_db_path"]
