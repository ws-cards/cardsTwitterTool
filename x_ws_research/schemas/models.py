"""Shared Pydantic models (Phase 1 skeleton — validation only)."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field, field_validator


class AccountConfig(BaseModel):
    handle: str
    enabled: bool = True
    display_name: str = ""

    @field_validator("handle")
    @classmethod
    def normalize_handle(cls, value: str) -> str:
        value = value.strip().lstrip("@")
        if not value:
            raise ValueError("handle must not be empty")
        return value


class KeywordConfig(BaseModel):
    keywords: list[str] = Field(default_factory=list)
    match_mode: Literal["all", "any"] = "any"
    case_sensitive: bool = False
    normalize_whitespace: bool = True


class TaskConfig(BaseModel):
    max_posts: int = Field(default=50, ge=1, le=10_000)
    download_images: bool = True
    run_recognition: bool = False
    output_dir: Path = Field(default_factory=lambda: Path("data/exports"))


class AppSettings(BaseModel):
    accounts: list[AccountConfig] = Field(default_factory=list)
    keywords: KeywordConfig = Field(default_factory=KeywordConfig)
    task: TaskConfig = Field(default_factory=TaskConfig)
    browser_profile_dir: Path | None = None


class PostRecord(BaseModel):
    """Normalized post shape used by PostSource adapters."""

    source_id: str
    author_handle: str
    text: str = ""
    created_at: datetime | None = None
    url: str | None = None
    image_urls: list[str] = Field(default_factory=list)
    image_paths: list[Path] = Field(default_factory=list)
    raw: dict = Field(default_factory=dict)
