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


class MealEntry(Base):
    __tablename__ = "meal_entries"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    user_id: Mapped[str] = mapped_column(String, index=True)
    ts: Mapped[datetime] = mapped_column(DateTime)
    meal_type: Mapped[str] = mapped_column(String)  # breakfast / lunch / dinner / snack / other
    items_json: Mapped[str] = mapped_column(Text)  # JSON list of items
    text_raw: Mapped[str] = mapped_column(Text)  # original user text
    provenance_json: Mapped[str] = mapped_column(Text)  # JSON with parsed fields, etc.
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    @staticmethod
    def dumps(obj) -> str:
        return json.dumps(obj, ensure_ascii=False)

    @staticmethod
    def loads(s: str):
        return json.loads(s) if s else {}










