"""Import card catalog from CSV / JSON into SQLite ``card_catalog``."""

from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from sqlalchemy import select

from storage.database import Database
from storage.models import CardCatalogRow
from vision.card_number import normalize_card_number


@dataclass
class CatalogImportStats:
    inserted: int = 0
    updated: int = 0
    skipped: int = 0
    errors: int = 0


def load_catalog_records(path: Path) -> list[dict[str, Any]]:
    path = Path(path)
    suffix = path.suffix.lower()
    if suffix == ".json":
        raw = json.loads(path.read_text(encoding="utf-8"))
        items = raw["cards"] if isinstance(raw, dict) and "cards" in raw else raw
        if not isinstance(items, list):
            raise ValueError('Catalog JSON expects a list or {"cards": [...]}')
        return [dict(x) for x in items]
    if suffix == ".csv":
        with path.open(newline="", encoding="utf-8") as fh:
            return list(csv.DictReader(fh))
    raise ValueError(f"Unsupported catalog format: {suffix}")


def import_card_catalog(
    path: Path,
    *,
    db_path: Path | None = None,
) -> CatalogImportStats:
    stats = CatalogImportStats()
    records = load_catalog_records(path)
    db = Database(db_path=db_path)
    db.create_schema()
    with db.session() as session:
        for item in records:
            try:
                raw_number = item.get("card_number") or item.get("number") or item.get("id")
                number = normalize_card_number(str(raw_number) if raw_number else None)
                if not number:
                    stats.skipped += 1
                    continue
                name = str(item.get("name") or item.get("card_name") or "")
                set_code = item.get("set_code") or item.get("set")
                if set_code is not None:
                    set_code = str(set_code)
                existing = session.scalar(
                    select(CardCatalogRow).where(CardCatalogRow.card_number == number)
                )
                if existing:
                    existing.name = name or existing.name
                    if set_code:
                        existing.set_code = set_code
                    stats.updated += 1
                else:
                    session.add(
                        CardCatalogRow(card_number=number, name=name, set_code=set_code)
                    )
                    stats.inserted += 1
            except Exception:  # noqa: BLE001
                stats.errors += 1
        session.commit()
    return stats


def load_catalog_map(db_path: Path | None = None) -> dict[str, dict[str, Any]]:
    db = Database(db_path=db_path)
    db.create_schema()
    out: dict[str, dict[str, Any]] = {}
    with db.session() as session:
        for row in session.scalars(select(CardCatalogRow)):
            out[row.card_number] = {
                "card_number": row.card_number,
                "name": row.name,
                "set_code": row.set_code,
                "catalog_id": row.id,
            }
    return out
