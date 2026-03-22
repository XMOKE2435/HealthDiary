from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
from uuid import uuid4

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlalchemy import select

from ..db.session import SessionLocal
from ..db.models import MealEntry
from ..services.llm import QwenClient


router = APIRouter(prefix="/meals", tags=["meals"])


class MealLogRequest(BaseModel):
    user_id: str
    text: str
    ts: Optional[datetime] = None


@router.post("/log")
async def log_meal(req: MealLogRequest):
    if not req.text.strip():
        raise HTTPException(status_code=400, detail="text required")
    llm = QwenClient()
    parsed = await llm.parse_meal(req.text)
    meal_type = (parsed.get("meal_type") or "other").lower()
    items = parsed.get("items") or []

    entry_id = uuid4().hex
    with SessionLocal() as db:
        entry = MealEntry(
            id=entry_id,
            user_id=req.user_id,
            ts=req.ts or datetime.utcnow(),
            meal_type=meal_type,
            items_json=MealEntry.dumps(items),
            text_raw=req.text,
            provenance_json=MealEntry.dumps({"parsed": parsed}),
        )
        db.add(entry)
        db.commit()

    return {
        "id": entry_id,
        "meal_type": meal_type,
        "items": items,
        "parsed": parsed,
    }


@router.get("/summary")
async def meal_summary(user_id: str, window_days: int = 30):
    if window_days <= 0:
        raise HTTPException(status_code=400, detail="window_days must be > 0")
    cutoff = datetime.utcnow() - timedelta(days=window_days)
    with SessionLocal() as db:
        rows = (
            db.execute(
                select(MealEntry).where(
                    MealEntry.user_id == user_id, MealEntry.ts >= cutoff
                ).order_by(MealEntry.ts.asc())
            )
            .scalars()
            .all()
        )
        meals: List[Dict[str, Any]] = []
        for r in rows:
            meals.append(
                {
                    "id": r.id,
                    "ts": r.ts.isoformat(),
                    "meal_type": r.meal_type,
                    "items": MealEntry.loads(r.items_json),
                    "text_raw": r.text_raw,
                }
            )
    llm = QwenClient()
    analysis = await llm.analyze_meals(meals, window_days)
    return {"meals": meals, "analysis": analysis}

