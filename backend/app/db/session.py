from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase
from pathlib import Path
import os
import shutil
import sqlite3


# Canonical location: backend/app/data/healthdiary.db
_preferred_data_dir = Path(__file__).resolve().parents[1] / "data"
# Legacy location accidentally used before: backend/backend/app/data/healthdiary.db
_legacy_data_dir = Path(__file__).resolve().parents[2] / "backend" / "app" / "data"
_preferred_db = _preferred_data_dir / "healthdiary.db"
_legacy_db = _legacy_data_dir / "healthdiary.db"


def _ensure_core_tables(con: sqlite3.Connection) -> None:
    cur = con.cursor()
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS symptom_entries (
            id TEXT PRIMARY KEY,
            user_id TEXT,
            ts TEXT,
            symptom_raw TEXT,
            input_mode TEXT,
            fields_json TEXT,
            provenance_json TEXT,
            created_at TEXT
        )
        """
    )
    cur.execute("CREATE INDEX IF NOT EXISTS ix_symptom_entries_user_id ON symptom_entries (user_id)")
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS meal_entries (
            id TEXT PRIMARY KEY,
            user_id TEXT,
            ts TEXT,
            meal_type TEXT,
            items_json TEXT,
            text_raw TEXT,
            provenance_json TEXT,
            created_at TEXT
        )
        """
    )
    cur.execute("CREATE INDEX IF NOT EXISTS ix_meal_entries_user_id ON meal_entries (user_id)")
    con.commit()


def _table_exists(con: sqlite3.Connection, table_name: str, schema: str = "main") -> bool:
    cur = con.cursor()
    cur.execute(
        f"SELECT name FROM {schema}.sqlite_master WHERE type='table' AND name=?",
        (table_name,),
    )
    return cur.fetchone() is not None


def _merge_legacy_into_preferred() -> None:
    """Safely merge legacy DB rows into canonical DB (id-based, no overwrite)."""
    _preferred_data_dir.mkdir(parents=True, exist_ok=True)
    if not _legacy_db.exists():
        return
    # If preferred doesn't exist yet, keep all data by copying legacy first.
    if not _preferred_db.exists():
        shutil.copy2(_legacy_db, _preferred_db)
        return

    con = sqlite3.connect(str(_preferred_db))
    try:
        _ensure_core_tables(con)
        cur = con.cursor()
        cur.execute("ATTACH DATABASE ? AS legacy_db", (str(_legacy_db),))
        for table in ("symptom_entries", "meal_entries"):
            if not _table_exists(con, table, schema="main"):
                continue
            if not _table_exists(con, table, schema="legacy_db"):
                continue
            # Insert only new IDs from legacy, preserve existing records.
            cur.execute(
                f"""
                INSERT OR IGNORE INTO {table}
                SELECT * FROM legacy_db.{table}
                """
            )
        con.commit()
        cur.execute("DETACH DATABASE legacy_db")
    finally:
        con.close()


_merge_legacy_into_preferred()
DATA_DIR = _preferred_data_dir
DB_PATH = Path(os.getenv("HEALTHDAIRY_DB_PATH", str(_preferred_db))).resolve()


class Base(DeclarativeBase):
    pass


engine = create_engine(f"sqlite:///{DB_PATH}", echo=False, future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)



