import json
import logging
from enum import Enum
from pathlib import Path
from typing import Literal

# Central language mode abstraction for the entire app (UI, ASR, TTS, LLM).
# Other components should call get_current_language_mode() to decide which
# language to use for prompts, ASR language codes, TTS voices, etc.


class LanguageMode(str, Enum):
    ENGLISH = "en"
    CHINESE = "zh"


_log = logging.getLogger(__name__)
_STATE_PATH = (Path(__file__).resolve().parent / "data" / "language_mode.json")
_DEFAULT_MODE = LanguageMode.ENGLISH


def _ensure_state_dir() -> None:
    _STATE_PATH.parent.mkdir(parents=True, exist_ok=True)


def get_current_language_mode() -> LanguageMode:
    """Return the persisted language mode (defaults to ENGLISH)."""
    try:
        if _STATE_PATH.exists():
            data = json.loads(_STATE_PATH.read_text(encoding="utf-8"))
            mode = data.get("mode")
            if mode in (LanguageMode.ENGLISH.value, LanguageMode.CHINESE.value):
                return LanguageMode(mode)  # type: ignore[arg-type]
    except Exception:
        _log.exception("Failed to load language mode state; falling back to default.")
    return _DEFAULT_MODE


def set_current_language_mode(mode: LanguageMode) -> None:
    """Persist the selected language mode and log the change."""
    _ensure_state_dir()
    _STATE_PATH.write_text(json.dumps({"mode": mode.value}), encoding="utf-8")
    _log.info("Language mode set to %s", mode.name)


def as_lang_code(mode: LanguageMode | None = None) -> Literal["en", "zh"]:
    """
    Helper to get language code ("en"/"zh") for integration points (ASR, TTS, prompts).
    """
    m = mode or get_current_language_mode()
    return "zh" if m == LanguageMode.CHINESE else "en"


# NOTE for future work:
# - ASR/LLM/TTS components should call get_current_language_mode()/as_lang_code()
#   to select the right language once bilingual behavior is implemented.
# - UI can switch modes via the API in routers/language_mode.py.



