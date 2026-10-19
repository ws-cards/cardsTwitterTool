"""Heuristic / mock vision implementations — explicitly not production-grade models.

- Grid or sidecar-based detection (no YOLO weights claimed)
- Pillow crops
- OCR via region hints, sidecars, or filename tokens (replaceable engines)
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Mapping

from PIL import Image

from vision.card_number import extract_card_numbers, normalize_card_number
from vision.interfaces import (
    CardMatcher,
    CardNumberOCR,
    CardRegion,
    CardCropper,
    DeckBuilder,
    DeckDetector,
    DeckList,
    MatchResult,
)


class HeuristicDeckDetector(DeckDetector):
    """Detect card regions via optional sidecar JSON, else a simple grid split.

    Sidecar ``<image>.cards.json``::
        {"regions": [{"x":0,"y":0,"width":100,"height":140,"hint_text":"ABC/S123-001"}, ...]}
    """

    def __init__(self, grid: tuple[int, int] = (2, 2), max_regions: int = 16) -> None:
        self.grid = grid
        self.max_regions = max_regions

    def detect(self, image_path: Path) -> list[CardRegion]:
        image_path = Path(image_path)
        sidecar = image_path.with_suffix(image_path.suffix + ".cards.json")
        if not sidecar.exists():
            sidecar = image_path.with_name(image_path.name + ".cards.json")
        if sidecar.exists():
            data = json.loads(sidecar.read_text(encoding="utf-8"))
            regions = data.get("regions") or data.get("cards") or []
            return [CardRegion.from_dict(r) for r in regions][: self.max_regions]

        with Image.open(image_path) as im:
            w, h = im.size
        cols, rows = self.grid
        regions: list[CardRegion] = []
        cell_w, cell_h = max(1, w // cols), max(1, h // rows)
        for r in range(rows):
            for c in range(cols):
                regions.append(
                    CardRegion(
                        x=c * cell_w,
                        y=r * cell_h,
                        width=cell_w if c < cols - 1 else w - c * cell_w,
                        height=cell_h if r < rows - 1 else h - r * cell_h,
                        score=0.1,
                        meta={"method": "grid"},
                    )
                )
        return regions[: self.max_regions]


class PillowCardCropper(CardCropper):
    def crop(self, image_path: Path, regions: list[CardRegion], *, out_dir: Path) -> list[Path]:
        out_dir = Path(out_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        paths: list[Path] = []
        with Image.open(image_path) as im:
            rgb = im.convert("RGB")
            for i, region in enumerate(regions):
                box = (
                    max(0, region.x),
                    max(0, region.y),
                    min(rgb.width, region.x + region.width),
                    min(rgb.height, region.y + region.height),
                )
                if box[2] <= box[0] or box[3] <= box[1]:
                    # Degenerate region — write empty placeholder to keep indices aligned
                    crop_path = out_dir / f"crop_{i:03d}_empty.png"
                    Image.new("RGB", (1, 1), (0, 0, 0)).save(crop_path)
                    paths.append(crop_path)
                    continue
                crop = rgb.crop(box)
                crop_path = out_dir / f"crop_{i:03d}.png"
                crop.save(crop_path)
                paths.append(crop_path)
                # Persist hint beside crop for OCR engines that only see the file
                if region.hint_text:
                    crop_path.with_suffix(".hint.txt").write_text(
                        region.hint_text, encoding="utf-8"
                    )
        return paths


class HeuristicCardNumberOCR(CardNumberOCR):
    """Replaceable OCR stub: hint → sidecar → filename tokens. Never invents hits."""

    def read_number(self, crop_path: Path, *, region: CardRegion | None = None) -> str | None:
        crop_path = Path(crop_path)
        # 1) Region hint
        if region and region.hint_text:
            nums = extract_card_numbers(region.hint_text)
            return nums[0] if nums else normalize_card_number(region.hint_text)

        # 2) Sibling hint / ocr sidecar
        for side in (
            crop_path.with_suffix(".hint.txt"),
            crop_path.with_suffix(".ocr.txt"),
            crop_path.with_name(crop_path.name + ".ocr.txt"),
        ):
            if side.exists():
                text = side.read_text(encoding="utf-8").strip()
                if not text:
                    return None
                nums = extract_card_numbers(text)
                return nums[0] if nums else normalize_card_number(text)

        # 3) Filename tokens (e.g. crop_ABC_S123-001.png)
        name = crop_path.stem
        # Convert underscores to slash-friendly form
        candidate = name.replace("_", "/")
        nums = extract_card_numbers(candidate)
        if nums:
            return nums[0]
        # Pattern SET-LETTER-NUM
        m = re.search(r"([A-Za-z0-9]+)_([A-Za-z])(\d+)-(\d+)", name)
        if m:
            return normalize_card_number(f"{m.group(1)}/{m.group(2)}{m.group(3)}-{m.group(4)}")
        return None


class MockCardNumberOCR(CardNumberOCR):
    """Deterministic OCR for tests: map crop name / path → number (or None)."""

    def __init__(self, mapping: Mapping[str, str | None] | None = None) -> None:
        self.mapping = dict(mapping or {})

    def read_number(self, crop_path: Path, *, region: CardRegion | None = None) -> str | None:
        key = Path(crop_path).name
        if key in self.mapping:
            return normalize_card_number(self.mapping[key]) if self.mapping[key] else None
        stem = Path(crop_path).stem
        if stem in self.mapping:
            val = self.mapping[stem]
            return normalize_card_number(val) if val else None
        if region and region.hint_text:
            return normalize_card_number(region.hint_text)
        return None


class RaisingOCR(CardNumberOCR):
    """OCR that always raises — for resilience tests."""

    def read_number(self, crop_path: Path, *, region: CardRegion | None = None) -> str | None:
        raise RuntimeError("OCR engine exploded (test)")


class CatalogCardMatcher(CardMatcher):
    """Match by normalized card number first; name is fallback only."""

    def __init__(
        self,
        catalog: Mapping[str, dict[str, Any]] | None = None,
    ) -> None:
        # key: normalized card_number → {name, catalog_id, ...}
        self._by_number: dict[str, dict[str, Any]] = {}
        self._by_name: dict[str, dict[str, Any]] = {}
        if catalog:
            for num, info in catalog.items():
                self.add_entry(num, info)

    def add_entry(self, card_number: str, info: dict[str, Any]) -> None:
        n = normalize_card_number(card_number)
        if not n:
            return
        payload = dict(info)
        payload.setdefault("card_number", n)
        self._by_number[n] = payload
        name = (info.get("name") or "").strip().lower()
        if name:
            self._by_name[name] = payload

    def match(self, crop_path: Path, ocr_hint: str | None = None) -> MatchResult | None:
        number = normalize_card_number(ocr_hint)
        if number and number in self._by_number:
            info = self._by_number[number]
            return MatchResult(
                card_number=number,
                name=info.get("name"),
                confidence=0.95,
                matched_by="number",
                catalog_id=info.get("catalog_id") or info.get("id"),
                raw=dict(info),
            )
        if number:
            # Number-like OCR but not in catalog — still return number-first result
            return MatchResult(
                card_number=number,
                name=None,
                confidence=0.4,
                matched_by="number",
                catalog_id=None,
                raw={"uncatalogued": True},
            )
        # Name-only fallback (weak)
        if ocr_hint:
            info = self._by_name.get(ocr_hint.strip().lower())
            if info:
                return MatchResult(
                    card_number=info.get("card_number"),
                    name=info.get("name"),
                    confidence=0.3,
                    matched_by="name",
                    catalog_id=info.get("catalog_id") or info.get("id"),
                    raw=dict(info),
                )
        return MatchResult(card_number=None, confidence=0.0, matched_by="none")


class MergeDeckBuilder(DeckBuilder):
    """Merge identical card numbers within one source; keep separate across sources."""

    def build(self, cards: list[dict[str, Any]], *, source_key: str = "") -> DeckList:
        merged: dict[str, dict[str, Any]] = {}
        unknowns: list[dict[str, Any]] = []
        for card in cards:
            number = normalize_card_number(card.get("card_number"))
            qty = int(card.get("quantity") or 1)
            if not number:
                unknowns.append({**card, "quantity": qty, "card_number": None})
                continue
            if number not in merged:
                merged[number] = {
                    "card_number": number,
                    "quantity": qty,
                    "name": card.get("name"),
                    "confirmed": bool(card.get("confirmed", False)),
                }
            else:
                merged[number]["quantity"] += qty
                if not merged[number].get("name") and card.get("name"):
                    merged[number]["name"] = card.get("name")
        items = list(merged.values()) + unknowns
        items.sort(key=lambda c: (c.get("card_number") is None, c.get("card_number") or ""))
        return DeckList(cards=items, source_key=source_key, meta={"merged": True})


def default_pipeline_components(
    catalog: Mapping[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    return {
        "detector": HeuristicDeckDetector(),
        "cropper": PillowCardCropper(),
        "ocr": HeuristicCardNumberOCR(),
        "matcher": CatalogCardMatcher(catalog),
        "builder": MergeDeckBuilder(),
    }
