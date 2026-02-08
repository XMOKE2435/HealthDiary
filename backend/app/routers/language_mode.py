from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from ..language_mode import (
    LanguageMode,
    get_current_language_mode,
    set_current_language_mode,
    as_lang_code,
)


router = APIRouter(tags=["language-mode"])


class LanguageModeResponse(BaseModel):
    mode_name: str = Field(..., description="Current language mode name (ENGLISH/CHINESE)")
    code: str = Field(..., description="Language code used internally (en/zh)")


class LanguageModeUpdate(BaseModel):
    mode: str


@router.get("/language-mode", response_model=LanguageModeResponse)
def get_language_mode():
    """Return the currently selected language mode."""
    mode = get_current_language_mode()
    return {"mode_name": mode.name, "code": as_lang_code(mode)}


@router.post("/language-mode", response_model=LanguageModeResponse)
def set_language_mode(payload: LanguageModeUpdate):
    """Set and persist the language mode."""
    raw = (payload.mode or "").strip()
    # Accept both enum names and codes
    if raw.upper() in ("ENGLISH", "EN"):
        mode = LanguageMode.ENGLISH
    elif raw.upper() in ("CHINESE", "ZH"):
        mode = LanguageMode.CHINESE
    else:
        raise HTTPException(status_code=400, detail="Unsupported language mode")
    set_current_language_mode(mode)
    mode = get_current_language_mode()
    return {"mode_name": mode.name, "code": as_lang_code(mode)}


# Future: UI can call POST /language-mode with {"mode":"ENGLISH"} or {"mode":"CHINESE"}
# and other components should read get_current_language_mode()/as_lang_code() to
# pick ASR/LLM prompt language, TTS voice, etc.


