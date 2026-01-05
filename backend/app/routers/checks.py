from fastapi import APIRouter
from pydantic import BaseModel
from typing import Any, Dict, List, Literal
import asyncio

from ..services.llm import QwenClient


router = APIRouter(prefix="/checks", tags=["checks"])


class CheckRequest(BaseModel):
    user_id: str
    text: str
    pathway: Literal["meal", "sleep", "medication", "abdominal_pain"]


@router.post("/meal")
async def check_meal(req: CheckRequest):
    llm = QwenClient()
    nlu = await llm.nlu_slot_fill(req.text)
    fields: Dict[str, Any] = nlu.get("fields", {})
    clarifiers: List[str] = await llm.clarifier_select(fields, "meal")
    return {"fields": fields, "clarifiers": clarifiers}


@router.post("/sleep")
async def check_sleep(req: CheckRequest):
    llm = QwenClient()
    nlu = await llm.nlu_slot_fill(req.text)
    fields: Dict[str, Any] = nlu.get("fields", {})
    clarifiers: List[str] = await llm.clarifier_select(fields, "sleep")
    return {"fields": fields, "clarifiers": clarifiers}


@router.post("/medication")
async def check_medication(req: CheckRequest):
    llm = QwenClient()
    nlu = await llm.nlu_slot_fill(req.text)
    fields: Dict[str, Any] = nlu.get("fields", {})
    clarifiers: List[str] = await llm.clarifier_select(fields, "medication")
    return {"fields": fields, "clarifiers": clarifiers}



