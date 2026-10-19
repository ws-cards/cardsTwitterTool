"""Keyword matching with AND/OR, case folding, and whitespace normalization.

Original post text is never mutated — only comparison views are normalized.
"""

from __future__ import annotations

import re
from typing import Iterable

from schemas.models import KeywordConfig, PostRecord

_WS_RE = re.compile(r"\s+")


def normalize_for_match(text: str, *, case_sensitive: bool, normalize_whitespace: bool) -> str:
    view = text
    if normalize_whitespace:
        view = _WS_RE.sub(" ", view).strip()
    if not case_sensitive:
        view = view.lower()
    return view


def parse_keyword_list(raw: str) -> list[str]:
    """Split comma / newline separated keywords; keep original keyword strings."""
    parts: list[str] = []
    for chunk in re.split(r"[,，\n]", raw):
        kw = chunk.strip()
        if kw:
            parts.append(kw)
    return parts


def keyword_matches(
    text: str,
    keywords: list[str],
    *,
    match_mode: str = "any",
    case_sensitive: bool = False,
    normalize_whitespace: bool = True,
) -> bool:
    if not keywords:
        return True
    haystack = normalize_for_match(
        text,
        case_sensitive=case_sensitive,
        normalize_whitespace=normalize_whitespace,
    )
    needles = [
        normalize_for_match(
            k,
            case_sensitive=case_sensitive,
            normalize_whitespace=normalize_whitespace,
        )
        for k in keywords
    ]
    hits = [n in haystack for n in needles if n]
    if not hits:
        return True
    if match_mode == "all":
        return all(hits)
    return any(hits)


def filter_posts(
    posts: Iterable[PostRecord],
    config: KeywordConfig | None = None,
    *,
    keywords: list[str] | None = None,
    match_mode: str = "any",
    case_sensitive: bool = False,
    normalize_whitespace: bool = True,
) -> list[PostRecord]:
    if config is not None:
        keywords = list(config.keywords)
        match_mode = config.match_mode
        case_sensitive = config.case_sensitive
        normalize_whitespace = config.normalize_whitespace
    keywords = keywords or []
    return [
        post
        for post in posts
        if keyword_matches(
            post.text,
            keywords,
            match_mode=match_mode,
            case_sensitive=case_sensitive,
            normalize_whitespace=normalize_whitespace,
        )
    ]
