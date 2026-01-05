from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import String, DateTime, Text
from datetime import datetime
import json
from .session import Base


class SymptomEntry(Base):
    __tablename__ = "symptom_entries"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    user_id: Mapped[str] = mapped_column(String, index=True)
    ts: Mapped[datetime] = mapped_column(DateTime)
    symptom_raw: Mapped[str] = mapped_column(Text)
    input_mode: Mapped[str] = mapped_column(String)
    fields_json: Mapped[str] = mapped_column(Text)  # JSON string
    provenance_json: Mapped[str] = mapped_column(Text)  # JSON string
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    @staticmethod
    def dumps(obj) -> str:
        return json.dumps(obj, ensure_ascii=False)

    @staticmethod
    def loads(s: str):
        return json.loads(s) if s else {}










