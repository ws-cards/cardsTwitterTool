"""Replaceable vision interfaces — no real models in Phase 1."""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any


class DeckDetector(ABC):
    @abstractmethod
    def detect(self, image_path: Path) -> list[dict[str, Any]]:
        """Locate deck / card regions. Not implemented in Phase 1."""


class CardCropper(ABC):
    @abstractmethod
    def crop(self, image_path: Path, regions: list[dict[str, Any]]) -> list[Path]:
        ...


class CardNumberOCR(ABC):
    @abstractmethod
    def read_number(self, crop_path: Path) -> str | None:
        ...


class CardMatcher(ABC):
    @abstractmethod
    def match(self, crop_path: Path, ocr_hint: str | None = None) -> dict[str, Any] | None:
        ...


class DeckBuilder(ABC):
    @abstractmethod
    def build(self, cards: list[dict[str, Any]]) -> dict[str, Any]:
        ...


class NotReadyStub:
    """Mixin that raises until Phase 3 wires real implementations."""

    def _not_ready(self) -> None:
        raise NotImplementedError("Vision pipeline is not available in Phase 1")


class StubDeckDetector(NotReadyStub, DeckDetector):
    def detect(self, image_path: Path) -> list[dict[str, Any]]:
        self._not_ready()
        return []
