from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Dict, Any, Literal, Optional
from datetime import datetime
from uuid import uuid4

from ..services.llm import QwenClient
from .diary import DiaryFields
from ..db.session import SessionLocal
from ..db.models import SymptomEntry


router = APIRouter(tags=["diary-chat"])


ClarifierId = Literal[
    "clarifier.meal_relation",
    "clarifier.fever",
    "clarifier.bowel_changes",
]


CLARIFIER_QUESTIONS: Dict[str, str] = {
    "clarifier.meal_relation": "Do symptoms relate to meals (before/after, specific foods)?",
    "clarifier.fever": "Did you have fever recently? If yes, what temperature?",
    "clarifier.bowel_changes": "Any changes in bowel habits (constipation/diarrhea/blood)?",
}


class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    text: str


class ChatStepRequest(BaseModel):
    user_id: str
    messages: List[ChatMessage]
    fields: Optional[Dict[str, Any]] = None
    pathway: Optional[str] = "abdominal_pain"
    ts: Optional[datetime] = None


@router.post("/diary/chat/step")
async def diary_chat_step(req: ChatStepRequest):
    if not req.messages:
        raise HTTPException(status_code=400, detail="messages required")

    last_user_text = ""
    for m in reversed(req.messages):
        if m.role == "user":
            last_user_text = m.text
            break
    if not last_user_text:
        raise HTTPException(status_code=400, detail="last user message missing")

    llm = QwenClient()
    nlu = await llm.nlu_slot_fill(last_user_text)
    new_fields = nlu.get("fields", {}) or {}
    merged = dict(req.fields or {})
    # Merge: prefer non-null from new_fields
    for k, v in new_fields.items():
        if v is not None and v != "":
            merged[k] = v

    # Infer last asked clarifier (if any) and interpret a terse yes/no reply
    last_assistant_text = next((m.text for m in reversed(req.messages) if m.role == "assistant"), "")
    reverse_map = {v: k for k, v in CLARIFIER_QUESTIONS.items()}
    last_cid = reverse_map.get(last_assistant_text)
    low = last_user_text.lower().strip()
    if last_cid:
        if last_cid == "clarifier.meal_relation":
            if low in ("no", "none", "no relation"):
                merged["timing"] = "none"
        if last_cid == "clarifier.fever":
            if low.startswith("yes") or "yes" in low:
                merged.setdefault("associated", [])
                if "fever" not in merged["associated"]:
                    merged["associated"].append("fever")
                import re
                m = re.search(r"(\d{2}(?:\.\d)?)", low)
                if m:
                    try:
                        merged["fever_temp_c"] = float(m.group(1))
                    except Exception:
                        pass
            if low in ("no", "none"):
                merged["fever_temp_c"] = None
        if last_cid == "clarifier.bowel_changes":
            if low in ("no", "none", "no change", "no changes"):
                merged["bowel_changes"] = "none"

    # Determine which clarifiers are still missing based on merged fields and symptom pathway
    def missing(c: str) -> bool:
        if c == "clarifier.meal_relation":
            return not merged.get("timing")
        if c == "clarifier.fever":
            assoc = merged.get("associated") or []
            return ("fever" not in assoc) and ("fever_temp_c" not in merged)
        if c == "clarifier.bowel_changes":
            if merged.get("bowel_changes") in ("present", "none"):
                return False
            assoc = (merged.get("associated") or [])
            return not any(x in assoc for x in ["diarrhea", "constipation", "blood in stool"])
        return True

    # Avoid repeating questions already asked in prior assistant messages
    asked_ids = set()
    asked_texts = {m.text for m in req.messages if m.role == "assistant"}
    for cid, q in CLARIFIER_QUESTIONS.items():
        if q in asked_texts:
            asked_ids.add(cid)

    # Start from pathway-aware whitelist; filter by missing and not-asked
    label = (merged.get("symptom_label") or "").lower()
    if any(k in label for k in ["abdominal", "stomach", "belly", "nausea"]):
        whitelist = ["clarifier.meal_relation", "clarifier.fever", "clarifier.bowel_changes"]
    elif any(k in label for k in ["headache", "migraine", "head pain"]):
        whitelist = ["clarifier.fever"]
    else:
        whitelist = ["clarifier.fever"]
    need = [cid for cid in whitelist if missing(cid) and cid not in asked_ids]
    # Stop criteria: cap to 3 questions (4 only if critical fields missing)
    asked_count = sum(1 for m in req.messages if m.role == "assistant")
    critical_missing = not merged.get("symptom_label") or (merged.get("severity") is None)
    max_questions = 4 if critical_missing else 3
    if asked_count >= max_questions:
        need = []

    # Ask at most ONE question per turn; phrase it with the LLM if available
    clarifiers = []
    if need:
        target = need[0]
        # Use LLM to generate natural phrasing; error if unavailable
        q_text = await llm.generate_question([target], merged, [m.model_dump() for m in req.messages])
        clarifiers = [{"id": target, "question": q_text}]

    # Heuristic completeness: ready when we have a label and severity
    # BUT: only mark as ready if we're NOT currently asking a question (clarifiers is empty)
    # AND the last message is from the user (not the assistant)
    # This prevents saving while waiting for user to answer a pending question
    has_required_fields = bool(merged.get("symptom_label")) and (merged.get("severity") is not None)
    no_pending_questions = len(clarifiers) == 0  # No questions being asked right now
    last_message_from_user = req.messages and req.messages[-1].role == "user"  # User has responded
    
    # Only ready if we have required fields AND no pending questions AND user has responded
    # If we've hit question cap but still have clarifiers, wait for user's answer
    ready = has_required_fields and no_pending_questions and last_message_from_user
    
    # If we've hit the question cap and have no more questions to ask, 
    # save even if we don't have severity (better than asking too many questions)
    # But still require that the last message is from the user
    if asked_count >= max_questions and no_pending_questions and last_message_from_user:
        ready = True if merged.get("symptom_label") else ready

    # Auto-save when ready
    saved_id: Optional[str] = None
    if ready:
        text_joined = " ".join([m.text for m in req.messages if m.role == "user"]).strip()
        entry_id = uuid4().hex
        with SessionLocal() as db:
            entry = SymptomEntry(
                id=entry_id,
                user_id=req.user_id,
                ts=req.ts or datetime.utcnow(),
                symptom_raw=text_joined or "(conversation)",
                input_mode="chat",
                fields_json=SymptomEntry.dumps(merged),
                provenance_json=SymptomEntry.dumps({
                    "nlu": True,
                    "user_confirmed": True,
                    "chat": True,
                    "messages": [m.model_dump() for m in req.messages]
                }),
            )
            db.add(entry)
            db.commit()
        saved_id = entry_id

    return {"fields": merged, "clarifiers": clarifiers, "ready": ready, "saved_id": saved_id}


class ChatCommitRequest(BaseModel):
    user_id: str
    messages: List[ChatMessage]
    fields: Dict[str, Any]
    ts: Optional[datetime] = None


@router.post("/diary/chat/commit")
def diary_chat_commit(req: ChatCommitRequest):
    if not req.messages:
        raise HTTPException(status_code=400, detail="messages required")
    text_joined = " ".join([m.text for m in req.messages if m.role == "user"]).strip()
    entry_id = uuid4().hex
    with SessionLocal() as db:
        entry = SymptomEntry(
            id=entry_id,
            user_id=req.user_id,
            ts=req.ts or datetime.utcnow(),
            symptom_raw=text_joined or "(conversation)",
            input_mode="chat",
            fields_json=SymptomEntry.dumps(req.fields),
            provenance_json=SymptomEntry.dumps({"nlu": True, "user_confirmed": True, "chat": True}),
        )
        db.add(entry)
        db.commit()
    return {"id": entry_id, "ok": True}


