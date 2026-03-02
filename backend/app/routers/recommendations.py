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

    # Filter to last N days from now first
    cutoff = (datetime.utcnow() - timedelta(days=window_days)).isoformat()
    entries = [e for e in entries if e.get("ts", "") >= cutoff]

    # Optional filter by symptom label: case-insensitive, strip whitespace
    if label and label.strip():
        label_norm = label.strip().lower()
        by_label = [e for e in entries if ((e.get("fields", {}) or {}).get("symptom_label") or "").strip().lower() == label_norm]
        # If no entries match the label, use all entries in window so we still return suggestions
        if by_label:
            entries = by_label

    llm = QwenClient()
    suggestions = await llm.recommend_from_entries(entries, window_days)

    return {"type": "non_medical", "suggestions": suggestions}


