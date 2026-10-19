from sqlalchemy import select

from storage.database import DatabaseSkeleton, TaskRow


def test_database_schema(data_root):
    db = DatabaseSkeleton(db_path=data_root / "db" / "test.sqlite")
    db.create_schema()
    with db.session() as session:
        session.add(TaskRow(state="IDLE", note="phase1"))
        session.commit()
        rows = list(session.scalars(select(TaskRow)))
        assert len(rows) == 1
        assert rows[0].state == "IDLE"
