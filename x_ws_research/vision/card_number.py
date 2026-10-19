"""Weiss Schwarz card-number normalization and extraction.

Card numbers are preferred over names, e.g. ``ABC/S123-001``, ``BD/W54-076``.
"""

from __future__ import annotations

import re

# Common WS patterns: SET/LETTER+NUM-NUM with optional trailing suffix letter
_CARD_RE = re.compile(
    r"\b("
    r"[A-Za-z0-9]{1,8}/[A-Za-z]\d{1,4}-\d{1,4}[A-Za-z]?"
    r")\b"
)
_LOOSE_RE = re.compile(
    r"([A-Za-z0-9]{1,8})[/＿_]([A-Za-z])\s*(\d{1,4})\s*[-－]\s*(\d{1,4})([A-Za-z]?)",
    re.IGNORECASE,
)


def normalize_card_number(raw: str | None) -> str | None:
    """Normalize a card number string. Returns None if empty/unusable."""
    if raw is None:
        return None
    text = str(raw).strip()
    if not text:
        return None
    text = text.replace("＿", "/").replace("_", "/").replace("－", "-")
    text = re.sub(r"\s+", "", text)
    m = _LOOSE_RE.search(text)
    if m:
        set_code, letter, a, b, suffix = m.groups()
        return f"{set_code.upper()}/{letter.upper()}{int(a)}-{int(b):03d}{suffix.upper()}"
    m2 = _CARD_RE.search(text)
    if m2:
        return m2.group(1).upper()
    # Already looks like a compact id
    if re.fullmatch(r"[A-Z0-9]{1,8}/[A-Z]\d{1,4}-\d{1,4}[A-Z]?", text.upper()):
        return text.upper()
    return text.upper() if text else None


def extract_card_numbers(text: str | None) -> list[str]:
    """Extract and normalize all card-number-like tokens from free text."""
    if not text:
        return []
    found: list[str] = []
    for m in _LOOSE_RE.finditer(text):
        set_code, letter, a, b, suffix = m.groups()
        n = f"{set_code.upper()}/{letter.upper()}{int(a)}-{int(b):03d}{suffix.upper()}"
        if n not in found:
            found.append(n)
    if found:
        return found
    for m in _CARD_RE.finditer(text):
        n = normalize_card_number(m.group(1))
        if n and n not in found:
            found.append(n)
    return found


def numbers_equal(a: str | None, b: str | None) -> bool:
    na = normalize_card_number(a)
    nb = normalize_card_number(b)
    if na is None or nb is None:
        return False
    return na == nb
