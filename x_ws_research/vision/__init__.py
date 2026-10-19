"""Vision / recognition package (replaceable interfaces + heuristics)."""

from vision.card_number import extract_card_numbers, normalize_card_number
from vision.heuristic import (
    CatalogCardMatcher,
    HeuristicCardNumberOCR,
    HeuristicDeckDetector,
    MergeDeckBuilder,
    MockCardNumberOCR,
    PillowCardCropper,
    RaisingOCR,
    default_pipeline_components,
)
from vision.interfaces import (
    CardCropper,
    CardMatcher,
    CardNumberOCR,
    CardRegion,
    DeckBuilder,
    DeckDetector,
    DeckList,
    MatchResult,
)

__all__ = [
    "CardCropper",
    "CardMatcher",
    "CardNumberOCR",
    "CardRegion",
    "CatalogCardMatcher",
    "DeckBuilder",
    "DeckDetector",
    "DeckList",
    "HeuristicCardNumberOCR",
    "HeuristicDeckDetector",
    "MatchResult",
    "MergeDeckBuilder",
    "MockCardNumberOCR",
    "PillowCardCropper",
    "RaisingOCR",
    "default_pipeline_components",
    "extract_card_numbers",
    "normalize_card_number",
]
