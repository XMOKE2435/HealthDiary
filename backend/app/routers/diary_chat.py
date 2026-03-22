import logging
from datetime import datetime
from typing import Any, Dict, List, Literal, Optional
from uuid import uuid4

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from pydantic import BaseModel

from ..services.llm import QwenClient
from .diary import DiaryFields
from ..db.session import SessionLocal
from ..db.models import SymptomEntry

log = logging.getLogger(__name__)
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


def _infer_lang_from_text(text: str) -> str:
    """Infer reply language from user text.

    Product rule: follow the *current user message* language.
    - Choose the dominant language in the message (Chinese vs English).
      Mixed sentences are common (e.g. Singaporean code-switching).
    """
    t = (text or "").strip()
    if not t:
        return "en"
    import re
    cjk = re.compile(r"[\u4e00-\u9fff\u3400-\u4dbf\uf900-\ufaff]")
    latin = re.compile(r"[A-Za-z]")
    cjk_count = sum(1 for ch in t if cjk.match(ch))
    en_count = sum(1 for ch in t if latin.match(ch))
    # If neither, default to English (numbers/punctuation only)
    if cjk_count == 0 and en_count == 0:
        return "en"
    # Dominant language wins; ties default to Chinese if any CJK present
    if cjk_count >= en_count:
        return "zh"
    return "en"


def _normalize_reply_lang(req_lang: Optional[str], user_text: str) -> str:
    """Decide reply language. Any Chinese dialect -> reply in Mandarin (zh)."""
    # Primary signal: always follow the current user message text.
    # This avoids "sticky" language behavior across turns (e.g. user says "no" -> reply in English).
    inferred = _infer_lang_from_text(user_text)
    if inferred == "en":
        return "en"

    # If inferred is Chinese, collapse any Chinese dialect to Mandarin (zh).
    # If client explicitly says English, allow it.
    if req_lang:
        low = req_lang.lower().strip()
        if low in ("en", "eng"):
            return "en"
    return "zh"


# Saved-message text per language (for mixed-language chat)
SAVED_MSG = {"en": "Thanks for sharing. I've saved this for you. I hope you feel better soon.", "zh": "谢谢您的分享，我已经为您保存好了。祝您早日好起来。"}


class ChatStepRequest(BaseModel):
    user_id: str
    messages: List[ChatMessage]
    fields: Optional[Dict[str, Any]] = None
    pathway: Optional[str] = "abdominal_pain"
    ts: Optional[datetime] = None
    lang: Optional[str] = None  # optional ASR-detected language/dialect code (reply collapses Chinese dialects to zh)


@router.post("/diary/transcribe")
async def diary_transcribe(
    user_id: str = Form(...),
    audio: UploadFile = File(...),
    lang: Optional[str] = Form(None),
):
    """Transcribe audio for diary/symptom input using Qwen3-ASR-Flash (auto language detection)."""
    audio_bytes = await audio.read()
    mime = audio.content_type or "audio/webm"
    if not audio_bytes or len(audio_bytes) < 100:
        raise HTTPException(
            status_code=400,
            detail="Audio file is empty or too small. Please record at least a second of speech.",
        )
    llm = QwenClient()
    try:
        result = await llm.transcribe_audio_qwen3_asr(
            audio_bytes,
            mime=mime,
            language=lang if lang in ("zh", "en", "yue") else None,
        )
    except Exception as exc:
        log.exception("Diary transcribe failed")
        raise HTTPException(status_code=502, detail=f"Transcription failed: {exc}") from exc
    return result


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

    # Reply language: English for English; Chinese dialects collapse to Mandarin (zh)
    reply_lang = _normalize_reply_lang(req.lang, last_user_text)

    llm = QwenClient()
    # Canonicalize to English for understanding (single canonical language)
    canonical_en = await llm.canonicalize_to_english(last_user_text)
    nlu = await llm.nlu_slot_fill(canonical_en)
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
    low_zh = (last_user_text or "").strip()
    if last_cid:
        if last_cid == "clarifier.meal_relation":
            if low in ("no", "none", "no relation") or low_zh in ("不", "不是", "没有", "無", "无"):
                merged["timing"] = "none"
        if last_cid == "clarifier.fever":
            if low.startswith("yes") or "yes" in low or low_zh in ("是", "有", "有的", "有啊", "有喔"):
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
            if low in ("no", "none") or low_zh in ("不", "没有", "无", "無", "否"):
                merged["fever_temp_c"] = None
        if last_cid == "clarifier.bowel_changes":
            if low in ("no", "none", "no change", "no changes") or low_zh in ("没有", "无", "無"):
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

    # Ask at most ONE question per turn; use LLM to generate the question (no hardcoded fallback)
    clarifiers = []
    if need:
        target = need[0]
        try:
            q_text = await llm.generate_question([target], merged, [m.model_dump() for m in req.messages], lang=reply_lang)
        except RuntimeError as e:
            if "not configured" in str(e).lower():
                raise HTTPException(
                    status_code=503,
                    detail="LLM not configured. Set QWEN_ENDPOINT and QWEN_API_KEY in ~/HealthDiary/.env and restart the server."
                ) from e
            raise
        except Exception as e:
            log.warning("LLM generate_question failed: %s", e, exc_info=True)
            raise HTTPException(status_code=503, detail=f"LLM request failed: {e!s}") from e
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
        raw_joined = " ".join([m.text for m in req.messages if m.role == "user"]).strip()
        canonical_joined = await llm.canonicalize_to_english(raw_joined)
        entry_id = uuid4().hex
        with SessionLocal() as db:
            entry = SymptomEntry(
                id=entry_id,
                user_id=req.user_id,
                ts=req.ts or datetime.utcnow(),
                # Store canonical English for downstream analytics and doctor pack generation
                symptom_raw=canonical_joined or "(conversation)",
                input_mode="chat",
                fields_json=SymptomEntry.dumps(merged),
                provenance_json=SymptomEntry.dumps({
                    "nlu": True,
                    "user_confirmed": True,
                    "chat": True,
                    "raw_text": raw_joined,
                    "canonical_en": canonical_joined,
                    "detected_lang": req.lang,
                    "messages": [m.model_dump() for m in req.messages]
                }),
            )
            db.add(entry)
            db.commit()
        saved_id = entry_id

    saved_message: Optional[str] = None
    if saved_id:
        saved_message = SAVED_MSG.get(reply_lang, SAVED_MSG["en"])
    return {
        "fields": merged,
        "clarifiers": clarifiers,
        "ready": ready,
        "saved_id": saved_id,
        "saved_message": saved_message,
        "reply_lang": reply_lang,
    }


class ChatCommitRequest(BaseModel):
    user_id: str
    messages: List[ChatMessage]
    fields: Dict[str, Any]
    ts: Optional[datetime] = None


@router.post("/diary/chat/commit")
def diary_chat_commit(req: ChatCommitRequest):
    if not req.messages:
        raise HTTPException(status_code=400, detail="messages required")
    raw_joined = " ".join([m.text for m in req.messages if m.role == "user"]).strip()
    # Best-effort canonical English storage (no await here; commit is sync)
    # If LLM not configured, store raw text as-is.
    try:
        import asyncio
        llm = QwenClient()
        canonical_joined = asyncio.run(llm.canonicalize_to_english(raw_joined))
    except Exception:
        canonical_joined = raw_joined
    entry_id = uuid4().hex
    with SessionLocal() as db:
        entry = SymptomEntry(
            id=entry_id,
            user_id=req.user_id,
            ts=req.ts or datetime.utcnow(),
            symptom_raw=canonical_joined or "(conversation)",
            input_mode="chat",
            fields_json=SymptomEntry.dumps(req.fields),
            provenance_json=SymptomEntry.dumps({
                "nlu": True,
                "user_confirmed": True,
                "chat": True,
                "raw_text": raw_joined,
                "canonical_en": canonical_joined,
            }),
        )
        db.add(entry)
        db.commit()
    return {"id": entry_id, "ok": True}


