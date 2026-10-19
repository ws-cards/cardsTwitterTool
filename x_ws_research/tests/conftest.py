"""Pytest fixtures — no live X dependency."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


@pytest.fixture
def data_root(tmp_path, monkeypatch):
    root = tmp_path / "data"
    monkeypatch.setenv("X_WS_DATA_ROOT", str(root))
    return root


@pytest.fixture
def sample_json(tmp_path: Path) -> Path:
    path = tmp_path / "posts.json"
    path.write_text(
        """
        {
          "posts": [
            {
              "source_id": "1",
              "author_handle": "alice",
              "text": "Weiss Schwarz deck ABC/S123-001",
              "created_at": "2024-01-01T12:00:00+00:00",
              "url": "https://example.com/1",
              "image_urls": ["https://example.com/a.jpg"]
            },
            {
              "id": "2",
              "author": "bob",
              "content": "unrelated post",
              "image_urls": []
            }
          ]
        }
        """,
        encoding="utf-8",
    )
    return path


@pytest.fixture
def sample_csv(tmp_path: Path) -> Path:
    path = tmp_path / "posts.csv"
    path.write_text(
        "source_id,author_handle,text,created_at,url,image_urls\n"
        "10,carol,Hello WS card,2024-02-01T00:00:00Z,https://example.com/10,https://example.com/c.jpg\n",
        encoding="utf-8",
    )
    return path
