"""Replaceable vision interfaces for deck recognition (Phase 3)."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class CardRegion:
    """Detected card region in image coordinates (pixels)."""

    x: int
    y: int
    width: int
    height: int
    score: float = 0.0
    hint_text: str | None = None  # optional pre-known OCR hint (tests / sidecar)
    meta: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {
            "x": self.x,
            "y": self.y,
            "width": self.width,
            "height": self.height,
            "score": self.score,
            "hint_text": self.hint_text,
            "meta": dict(self.meta),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CardRegion:
        return cls(
            x=int(data.get("x", 0)),
            y=int(data.get("y", 0)),
            width=int(data.get("width", 0)),
            height=int(data.get("height", 0)),
            score=float(data.get("score", 0.0)),
            hint_text=data.get("hint_text"),
            meta=dict(data.get("meta") or {}),
        )


@dataclass
class MatchResult:
    card_number: str | None
    name: str | None = None
    confidence: float = 0.0
    matched_by: str = "none"  # number | name | none
    catalog_id: int | None = None
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass
class DeckList:
    """Built deck list for a single post/image source (do not merge across posts)."""

    cards: list[dict[str, Any]]  # {card_number, quantity, name?, ...}
    source_key: str = ""
    meta: dict[str, Any] = field(default_factory=dict)


class DeckDetector(ABC):
    @abstractmethod
    def detect(self, image_path: Path) -> list[CardRegion]:
        """Locate card regions. Heuristic / mock — not a claimed YOLO model."""


class CardCropper(ABC):
    @abstractmethod
    def crop(self, image_path: Path, regions: list[CardRegion], *, out_dir: Path) -> list[Path]:
        """Crop regions to ``out_dir``; return crop file paths (same order)."""


class CardNumberOCR(ABC):
    @abstractmethod
    def read_number(self, crop_path: Path, *, region: CardRegion | None = None) -> str | None:
        """Return raw OCR text / card number candidate, or None if empty/failed."""


class CardMatcher(ABC):
    @abstractmethod
    def match(self, crop_path: Path, ocr_hint: str | None = None) -> MatchResult | None:
        """Match primarily by card number against a catalog."""


class DeckBuilder(ABC):
    @abstractmethod
    def build(self, cards: list[dict[str, Any]], *, source_key: str = "") -> DeckList:
        """Merge same card numbers within one source; never across sources."""
