from typing import List, Literal, Optional
import os
import uuid
from pathlib import Path

import httpx
from fastapi import APIRouter, HTTPException, UploadFile, File, Form, Request
from fastapi.responses import FileResponse
from pydantic import BaseModel

from ..services.llm import QwenClient

# Temporary storage for audio files (for DashScope ASR which requires public URLs)
_TEMP_AUDIO_DIR = Path(__file__).resolve().parent.parent.parent / "temp_audio"
_TEMP_AUDIO_DIR.mkdir(parents=True, exist_ok=True)

router = APIRouter(tags=["visit"])


@router.get("/visit/audio/{file_id}")
async def get_temp_audio(file_id: str):
    """Temporary endpoint to serve audio files for DashScope ASR (requires public URLs)."""
    file_path = _TEMP_AUDIO_DIR / file_id
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Audio file not found")
    # Determine content type from extension
    ext = file_path.suffix.lower()
    media_type = {
        ".webm": "audio/webm",
        ".mp3": "audio/mpeg",
        ".wav": "audio/wav",
        ".m4a": "audio/mp4",
        ".ogg": "audio/ogg"
    }.get(ext, "application/octet-stream")
    return FileResponse(file_path, media_type=media_type)


@router.post("/visit/transcribe")
async def post_transcribe(
    user_id: str = Form(...),
    lang: Literal["en", "zh"] = Form("en"),
    audio: Optional[UploadFile] = File(None),
    audio_uri: Optional[str] = Form(None),
):
    if not audio and not audio_uri:
        raise HTTPException(status_code=400, detail="Provide audio file or audio_uri")

    audio_bytes: bytes | None = None
    mime: Optional[str] = None
    if audio:
        audio_bytes = await audio.read()
        mime = audio.content_type or "audio/webm"
        # Check if audio is actually empty or too small
        if not audio_bytes or len(audio_bytes) < 100:
            raise HTTPException(status_code=400, detail="Audio file is empty or too small. Please record actual audio content.")
    else:
        audio_uri = audio_uri or ""
        if not audio_uri:
            raise HTTPException(status_code=400, detail="audio_uri required")
        try:
            async with httpx.AsyncClient(timeout=20) as client:
                resp = await client.get(audio_uri)
                resp.raise_for_status()
                audio_bytes = resp.content
                mime = resp.headers.get("Content-Type")
        except Exception as exc:
            raise HTTPException(status_code=502, detail=f"Failed to fetch audio: {exc}") from exc

    if not audio_bytes:
        raise HTTPException(status_code=400, detail="Empty audio payload")

    llm = QwenClient()
    try:
        # Qwen Omni uses base64 directly, no need for file URLs
        result = await llm.transcribe_audio(audio_bytes, lang=lang, mime=mime)
    except Exception as exc:
        import traceback
        error_detail = str(exc) or repr(exc)
        if not error_detail:
            error_detail = f"Unknown error: {type(exc).__name__}"
        print(f"Transcription error: {error_detail}")
        print(traceback.format_exc())
        raise HTTPException(status_code=502, detail=f"Transcription failed: {error_detail}") from exc
    return result


class SummaryRequest(BaseModel):
    user_id: str
    transcript: str
    lang: Literal["en", "zh"] = "en"
    spans: List[dict] | None = None


@router.post("/visit/summary")
async def post_visit_summary(req: SummaryRequest):
    if not req.transcript:
        raise HTTPException(status_code=400, detail="transcript required")
    llm = QwenClient()
    try:
        summary = await llm.summarize_visit(req.transcript, req.spans or [], req.lang)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Summary failed: {exc}") from exc
    return summary
