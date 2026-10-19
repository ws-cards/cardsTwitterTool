"""SQLAlchemy ORM models for posts, images, tasks, and Phase 3 skeletons."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class PostRow(Base):
    __tablename__ = "posts"
    __table_args__ = (UniqueConstraint("source_id", name="uq_posts_source_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    author_handle: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    text: Mapped[str] = mapped_column(Text, nullable=False, default="")
    created_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    processed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    recognition_status: Mapped[str] = mapped_column(String(32), default="none", nullable=False)
    imported_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )
    raw_json: Mapped[str | None] = mapped_column(Text, nullable=True)

    images: Mapped[list[PostImageRow]] = relationship(
        "PostImageRow",
        back_populates="post",
        cascade="all, delete-orphan",
    )


class PostImageRow(Base):
    __tablename__ = "post_images"
    __table_args__ = (
        UniqueConstraint("post_id", "sha256", name="uq_post_images_post_sha"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    post_id: Mapped[int] = mapped_column(ForeignKey("posts.id", ondelete="CASCADE"), index=True)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    file_path: Mapped[str] = mapped_column(String(1024), nullable=False)
    source_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    original_name: Mapped[str | None] = mapped_column(String(512), nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    post: Mapped[PostRow] = relationship("PostRow", back_populates="images")


class TaskRow(Base):
    __tablename__ = "tasks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    kind: Mapped[str] = mapped_column(String(64), default="import", nullable=False)
    state: Mapped[str] = mapped_column(String(32), nullable=False, default="IDLE")
    source_path: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    note: Mapped[str] = mapped_column(Text, default="")
    posts_inserted: Mapped[int] = mapped_column(Integer, default=0)
    posts_skipped: Mapped[int] = mapped_column(Integer, default=0)
    images_linked: Mapped[int] = mapped_column(Integer, default=0)
    error_count: Mapped[int] = mapped_column(Integer, default=0)

    logs: Mapped[list[TaskLogRow]] = relationship(
        "TaskLogRow",
        back_populates="task",
        cascade="all, delete-orphan",
    )


class TaskLogRow(Base):
    __tablename__ = "task_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    task_id: Mapped[int | None] = mapped_column(
        ForeignKey("tasks.id", ondelete="CASCADE"), nullable=True, index=True
    )
    level: Mapped[str] = mapped_column(String(16), default="INFO")
    message: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    task: Mapped[TaskRow | None] = relationship("TaskRow", back_populates="logs")


# --- Phase 3 skeletons (tables exist; no business logic yet) ---


class DeckRow(Base):
    __tablename__ = "decks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(256), default="")
    post_id: Mapped[int | None] = mapped_column(ForeignKey("posts.id"), nullable=True)
    post_image_id: Mapped[int | None] = mapped_column(
        ForeignKey("post_images.id"), nullable=True, index=True
    )
    source_key: Mapped[str] = mapped_column(String(256), default="", index=True)
    status: Mapped[str] = mapped_column(String(32), default="draft")  # draft|confirmed
    note: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )

    cards: Mapped[list[DeckCardRow]] = relationship(
        "DeckCardRow",
        back_populates="deck",
        cascade="all, delete-orphan",
    )


class DeckCardRow(Base):
    __tablename__ = "deck_cards"
    __table_args__ = (
        UniqueConstraint("deck_id", "card_number", name="uq_deck_cards_deck_number"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    deck_id: Mapped[int] = mapped_column(ForeignKey("decks.id", ondelete="CASCADE"), index=True)
    card_number: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    card_name: Mapped[str | None] = mapped_column(String(256), nullable=True)
    quantity: Mapped[int] = mapped_column(Integer, default=1)
    confirmed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    correction_log: Mapped[str | None] = mapped_column(Text, nullable=True)

    deck: Mapped[DeckRow] = relationship("DeckRow", back_populates="cards")


class CardCatalogRow(Base):
    __tablename__ = "card_catalog"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    card_number: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(256), default="")
    set_code: Mapped[str | None] = mapped_column(String(64), nullable=True)


class RecognitionResultRow(Base):
    __tablename__ = "recognition_results"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    post_image_id: Mapped[int | None] = mapped_column(
        ForeignKey("post_images.id"), nullable=True, index=True
    )
    deck_id: Mapped[int | None] = mapped_column(ForeignKey("decks.id"), nullable=True)
    crop_path: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="pending")
    # pending | matched | empty | failed | corrected
    card_number: Mapped[str | None] = mapped_column(String(64), nullable=True)
    card_name: Mapped[str | None] = mapped_column(String(256), nullable=True)
    confidence: Mapped[str | None] = mapped_column(String(32), nullable=True)
    confirmed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    detail_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )
