from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase
from pathlib import Path
import sqlite3


# Preferred location: backend/app/data/healthdiary.db
_preferred_data_dir = Path(__file__).resolve().parents[1] / "data"
# Legacy location accidentally used before: backend/backend/app/data/healthdiary.db
_legacy_data_dir = Path(__file__).resolve().parents[2] / "backend" / "app" / "data"

def _count_symptom_rows(db_path: Path) -> int:
    if not db_path.exists():
        return -1
    try:
        con = sqlite3.connect(str(db_path))
        cur = con.cursor()
        cur.execute("SELECT COUNT(*) FROM symptom_entries")
        n = int(cur.fetchone()[0])
        con.close()
        return n
    except Exception:
        return -1


_preferred_db = _preferred_data_dir / "healthdiary.db"
_legacy_db = _legacy_data_dir / "healthdiary.db"
_preferred_count = _count_symptom_rows(_preferred_db)
_legacy_count = _count_symptom_rows(_legacy_db)

# Choose the DB with actual data to avoid accidental empty DB reads.
if _legacy_count > _preferred_count:
    DATA_DIR = _legacy_data_dir
else:
    DATA_DIR = _preferred_data_dir

DATA_DIR.mkdir(parents=True, exist_ok=True)
DB_PATH = DATA_DIR / "healthdiary.db"


class Base(DeclarativeBase):
    pass


engine = create_engine(f"sqlite:///{DB_PATH}", echo=False, future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)



