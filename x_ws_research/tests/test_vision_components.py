"""Unit tests for replaceable vision components — synthetic images / mocks only."""

from __future__ import annotations

import json
from pathlib import Path

from PIL import Image

from vision.heuristic import (
    CatalogCardMatcher,
    HeuristicCardNumberOCR,
    HeuristicDeckDetector,
    MergeDeckBuilder,
    MockCardNumberOCR,
    PillowCardCropper,
    RaisingOCR,
)
from vision.interfaces import CardRegion


def _png(path: Path, size=(200, 200)) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", size, (40, 40, 80)).save(path)
    return path


def test_sidecar_detector_and_crop(tmp_path):
    img = _png(tmp_path / "deck.png", (200, 100))
    sidecar = img.with_suffix(img.suffix + ".cards.json")
    sidecar.write_text(
        json.dumps(
            {
                "regions": [
                    {"x": 0, "y": 0, "width": 100, "height": 100, "hint_text": "ABC/S123-001"},
                    {"x": 100, "y": 0, "width": 100, "height": 100, "hint_text": "ABC/S123-001"},
                    {"x": 0, "y": 0, "width": 50, "height": 50, "hint_text": "BD/W54-076"},
                ]
            }
        ),
        encoding="utf-8",
    )
    regions = HeuristicDeckDetector().detect(img)
    assert len(regions) == 3
    crops = PillowCardCropper().crop(img, regions, out_dir=tmp_path / "crops")
    assert len(crops) == 3
    assert all(p.is_file() for p in crops)


def test_ocr_empty_and_hint(tmp_path):
    crop = _png(tmp_path / "crop_empty.png")
    ocr = HeuristicCardNumberOCR()
    assert ocr.read_number(crop) is None

    region = CardRegion(0, 0, 10, 10, hint_text="ABC/S10-2")
    assert ocr.read_number(crop, region=region) == "ABC/S10-002"

    hinted = tmp_path / "crop_x.png"
    _png(hinted)
    hinted.with_suffix(".hint.txt").write_text("BD/W54-076", encoding="utf-8")
    assert ocr.read_number(hinted) == "BD/W54-076"


def test_mock_ocr_and_raising(tmp_path):
    crop = _png(tmp_path / "c.png")
    mock = MockCardNumberOCR({"c.png": None})
    assert mock.read_number(crop) is None
    raising = RaisingOCR()
    try:
        raising.read_number(crop)
        assert False, "should raise"
    except RuntimeError:
        pass


def test_matcher_prefers_card_number():
    matcher = CatalogCardMatcher(
        {
            "ABC/S123-001": {"name": "Correct", "catalog_id": 1},
        }
    )
    result = matcher.match(Path("x.png"), ocr_hint="abc/s123-1")
    assert result is not None
    assert result.matched_by == "number"
    assert result.card_number == "ABC/S123-001"
    assert result.name == "Correct"

    # Uncatalogued but valid number still returns number-first
    other = matcher.match(Path("x.png"), ocr_hint="ZZ/S1-001")
    assert other is not None
    assert other.matched_by == "number"
    assert other.card_number == "ZZ/S1-001"


def test_deck_builder_merges_within_source_only():
    builder = MergeDeckBuilder()
    cards = [
        {"card_number": "ABC/S1-001", "quantity": 1},
        {"card_number": "abc/s1-1", "quantity": 2},
        {"card_number": "BD/W1-001", "quantity": 1},
    ]
    deck_a = builder.build(cards, source_key="post:1:image:1")
    assert len(deck_a.cards) == 2
    by_num = {c["card_number"]: c["quantity"] for c in deck_a.cards}
    assert by_num["ABC/S1-001"] == 3
    assert by_num["BD/W1-001"] == 1

    deck_b = builder.build(
        [{"card_number": "ABC/S1-001", "quantity": 4}],
        source_key="post:2:image:9",
    )
    # Different source_key — separate DeckList objects; quantities not cross-merged
    assert deck_a.source_key != deck_b.source_key
    assert by_num["ABC/S1-001"] == 3
    assert deck_b.cards[0]["quantity"] == 4
