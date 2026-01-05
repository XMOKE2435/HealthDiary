from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Any, Dict, Optional
from datetime import datetime
from uuid import uuid4
from sqlalchemy import select
from ..db.session import SessionLocal
from ..db.models import SymptomEntry


router = APIRouter(tags=["diary"])


class DiaryFields(BaseModel):
    symptom_label: Optional[str] = None
    onset: Optional[str] = None
    location: Optional[str] = None
    duration: Optional[str] = None
    character: Optional[str] = None
    aggravating: Optional[list[str]] = None
    relieving: Optional[list[str]] = None
    timing: Optional[str] = None
    severity: Optional[int] = Field(default=None, ge=0, le=10)
    associated: Optional[list[str]] = None
    triggers: Optional[list[str]] = None


class DiaryRequest(BaseModel):
    id: Optional[str] = None
    user_id: str
    ts: datetime
    symptom_raw: str
    input_mode: str
    fields: DiaryFields
    provenance: Dict[str, Any] = {}


def _check_red_flags(req: DiaryRequest) -> Optional[str]:
    text = (req.symptom_raw or "").lower()
    if "chest pain" in text and ("rest" in text or "faint" in text):
        return "red_flag_chest_pain"
    return None


@router.post("/diary")
def post_diary(req: DiaryRequest):
    red_flag = _check_red_flags(req)
    if red_flag:
        raise HTTPException(status_code=403, detail={
            "refusal": "I can’t provide diagnosis or medication advice. If this feels urgent, please seek medical care or call your local emergency number.",
            "reason": red_flag
        })

    entry_id = req.id or uuid4().hex
    with SessionLocal() as db:
        entry = SymptomEntry(
            id=entry_id,
            user_id=req.user_id,
            ts=req.ts,
            symptom_raw=req.symptom_raw,
            input_mode=req.input_mode,
            fields_json=SymptomEntry.dumps(req.fields.model_dump()),
            provenance_json=SymptomEntry.dumps(req.provenance),
        )
        db.add(entry)
        db.commit()
    return {"id": entry_id, "ok": True}


def list_entries_for_user(user_id: str) -> list[dict]:
    with SessionLocal() as db:
        rows = db.execute(
            select(SymptomEntry).where(SymptomEntry.user_id == user_id).order_by(SymptomEntry.ts.asc())
        ).scalars().all()
        out = []
        for r in rows:
            out.append({
                "id": r.id,
                "user_id": r.user_id,
                "ts": r.ts.isoformat(),
                "symptom_raw": r.symptom_raw,
                "input_mode": r.input_mode,
                "fields": SymptomEntry.loads(r.fields_json),
                "provenance": SymptomEntry.loads(r.provenance_json),
            })
        return out


