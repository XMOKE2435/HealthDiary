"""Thin HTTP client for HealthDairy backend. Same API as the web app."""
from datetime import datetime
from typing import Any, Dict, List, Optional

import requests


class BackendClient:
    def __init__(self, base_url: str, timeout: int = 60):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def _post(self, path: str, json: Optional[Dict] = None, **kwargs) -> Dict[str, Any]:
        r = requests.post(f"{self.base_url}{path}", json=json, timeout=self.timeout, **kwargs)
        r.raise_for_status()
        return r.json()

    def _get(self, path: str, params: Optional[Dict] = None) -> Dict[str, Any]:
        r = requests.get(f"{self.base_url}{path}", params=params, timeout=self.timeout)
        r.raise_for_status()
        return r.json()

    def chat_step(
        self,
        user_id: str,
        messages: List[Dict[str, str]],
        fields: Optional[Dict[str, Any]] = None,
        ts: Optional[str] = None,
        pathway: str = "abdominal_pain",
    ) -> Dict[str, Any]:
        """POST /diary/chat/step. messages = [{"role":"user"|"assistant","text":"..."}]"""
        body = {
            "user_id": user_id,
            "messages": messages,
            "fields": fields or {},
            "pathway": pathway,
        }
        if ts:
            body["ts"] = ts
        return self._post("/diary/chat/step", json=body)

    def transcribe(
        self,
        user_id: str,
        audio_bytes: bytes,
        lang: Optional[str] = "en",
        filename: str = "audio.wav",
        content_type: Optional[str] = None,
        timeout: int = 120,
    ) -> Dict[str, Any]:
        """POST /visit/transcribe with multipart audio file."""
        ct = content_type or "audio/wav"
        files = {"audio": (filename, audio_bytes, ct)}
        data: Dict[str, Any] = {"user_id": user_id}
        if lang is not None and lang != "":
            data["lang"] = lang
        r = requests.post(
            f"{self.base_url}/visit/transcribe",
            files=files,
            data=data,
            timeout=timeout,
        )
        r.raise_for_status()
        return r.json()

    def diary_transcribe(
        self,
        user_id: str,
        audio_bytes: bytes,
        lang: Optional[str] = None,
    ) -> Dict[str, Any]:
        """POST /diary/transcribe with multipart audio file."""
        files = {"audio": ("audio.wav", audio_bytes, "audio/wav")}
        data: Dict[str, Any] = {"user_id": user_id}
        if lang:
            data["lang"] = lang
        r = requests.post(
            f"{self.base_url}/diary/transcribe",
            files=files,
            data=data,
            timeout=60,
        )
        r.raise_for_status()
        return r.json()

    def recommendations(
        self,
        user_id: str,
        window_days: int = 30,
        label: Optional[str] = None,
    ) -> Dict[str, Any]:
        """GET /recommendations"""
        params = {"user_id": user_id, "window_days": window_days}
        if label:
            params["label"] = label
        return self._get("/recommendations", params=params)

    def doctor_pack(
        self,
        user_id: str,
        window_days: int = 30,
    ) -> Dict[str, Any]:
        """POST /doctor-pack. Returns pdf_uri, share_token, etc."""
        return self._post("/doctor-pack", json={"user_id": user_id, "window_days": window_days})

    def fetch_doctor_pack_html(self, pdf_uri: str) -> str:
        """GET the rendered doctor-pack HTML so the desktop app can display the same content as the web app."""
        url = f"{self.base_url.rstrip('/')}{pdf_uri}"
        r = requests.get(url, timeout=self.timeout)
        r.raise_for_status()
        return r.text

    def visit_summary(
        self,
        user_id: str,
        transcript: str,
        lang: str = "en",
    ) -> Dict[str, Any]:
        """POST /visit/summary"""
        return self._post(
            "/visit/summary",
            json={"user_id": user_id, "transcript": transcript, "lang": lang},
        )

    def log_meal(
        self,
        user_id: str,
        text: str,
    ) -> Dict[str, Any]:
        """POST /meals/log"""
        body = {"user_id": user_id, "text": text}
        return self._post("/meals/log", json=body)

    def meal_summary(
        self,
        user_id: str,
        window_days: int = 30,
    ) -> Dict[str, Any]:
        """GET /meals/summary"""
        params = {"user_id": user_id, "window_days": window_days}
        return self._get("/meals/summary", params=params)
