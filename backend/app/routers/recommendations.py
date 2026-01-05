from fastapi import APIRouter, HTTPException
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
from .diary import list_entries_for_user
from ..services.llm import QwenClient


router = APIRouter(tags=["recommendations"])


@router.get("/recommendations")
async def get_recommendations(user_id: str, window_days: int = 30, label: Optional[str] = None):
    if window_days <= 0:
        raise HTTPException(status_code=400, detail="window_days must be > 0")

    entries = list_entries_for_user(user_id)
    if label:
        entries = [e for e in entries if (e.get("fields", {}) or {}).get("symptom_label") == label]

    # Filter to last N days from now
    cutoff = (datetime.utcnow() - timedelta(days=window_days)).isoformat()
    entries = [e for e in entries if e.get("ts", "") >= cutoff]

    llm = QwenClient()
    suggestions = await llm.recommend_from_entries(entries, window_days)

    return {"type": "non_medical", "suggestions": suggestions}


