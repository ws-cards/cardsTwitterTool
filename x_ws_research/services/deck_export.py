"""Export decks to CSV (card_number, quantity, name, …)."""

from __future__ import annotations

import csv
from pathlib import Path

from sqlalchemy.orm import selectinload
from sqlalchemy import select

from storage.database import Database
from storage.models import DeckRow


def export_decks_csv(
    out_path: Path,
    *,
    db_path: Path | None = None,
    deck_ids: list[int] | None = None,
) -> Path:
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    db = Database(db_path=db_path)
    db.create_schema()

    with db.session() as session:
        stmt = select(DeckRow).options(selectinload(DeckRow.cards)).order_by(DeckRow.id.asc())
        decks = list(session.scalars(stmt))
        if deck_ids is not None:
            allow = set(deck_ids)
            decks = [d for d in decks if d.id in allow]

        with out_path.open("w", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(
                fh,
                fieldnames=[
                    "deck_id",
                    "deck_name",
                    "post_id",
                    "post_image_id",
                    "source_key",
                    "card_number",
                    "card_name",
                    "quantity",
                    "confirmed",
                ],
            )
            writer.writeheader()
            for deck in decks:
                for card in sorted(
                    deck.cards,
                    key=lambda c: (c.card_number is None, c.card_number or ""),
                ):
                    writer.writerow(
                        {
                            "deck_id": deck.id,
                            "deck_name": deck.name,
                            "post_id": deck.post_id,
                            "post_image_id": deck.post_image_id,
                            "source_key": deck.source_key,
                            "card_number": card.card_number or "",
                            "card_name": card.card_name or "",
                            "quantity": card.quantity,
                            "confirmed": int(card.confirmed),
                        }
                    )
    return out_path
