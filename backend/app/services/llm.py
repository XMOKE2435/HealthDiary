import os
import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Literal

import httpx

from ..language_mode import LanguageMode, get_current_language_mode, as_lang_code


_log = logging.getLogger(__name__)


def _load_env_from_file(env_path: Path) -> bool:
    """Parse KEY=value from file and set os.environ. Returns True if QWEN_* vars were loaded."""
    if not env_path.exists():
        return False
    try:
        content = env_path.read_text(encoding="utf-8", errors="replace")
        loaded_qwen = False
        qwen_vars_found = []
        for line in content.splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                # Handle PowerShell format: $env:KEY="value" -> KEY=value
                if line.startswith("$env:"):
                    # Remove $env: prefix and parse
                    line = line.replace("$env:", "", 1)
                k, v = line.split("=", 1)
                k, v = k.strip(), v.strip().strip("'\"").strip()
                if k:
                    os.environ[k] = v  # file always wins (overwrites empty or existing)
                    if k.startswith("QWEN_"):
                        loaded_qwen = True
                        qwen_vars_found.append(f"{k}={v[:30]}..." if len(v) > 30 else f"{k}={v}")
        if qwen_vars_found:
            print(f"[LLM]   Parsed from {env_path.name}: {', '.join(qwen_vars_found)}")
        return loaded_qwen
    except Exception as e:
        print(f"[LLM]   ERROR reading {env_path}: {e}")
        _log.warning("Could not load env from %s: %s", env_path, e)
        return False


def _ensure_qwen_env_loaded() -> None:
    """Load .env from project root and cwd so QWEN_* are set (e.g. on Pi)."""
    # Project root: backend/app/services/llm.py -> parent.parent.parent.parent
    _root = Path(__file__).resolve().parent.parent.parent.parent
    cwd = Path.cwd()
    paths_to_try = [_root / ".env", _root / "backend" / ".env", cwd / ".env"]
    loaded_from = None
    # Load from file first (manual parse) so we overwrite any empty env vars
    for p in paths_to_try:
        if _load_env_from_file(p):
            loaded_from = str(p)
            break  # Found QWEN_* vars, stop
    # Then try python-dotenv for any vars not in our manual parse
    try:
        from dotenv import load_dotenv
        load_dotenv(_root / ".env", override=False)
        load_dotenv(cwd / ".env", override=False)
    except ImportError:
        pass
    # Always print so you see it even if log level is high
    ep = (os.getenv("QWEN_ENDPOINT") or "").strip()
    key_set = bool((os.getenv("QWEN_API_KEY") or "").strip())
    if ep and key_set:
        print(f"[LLM] ✓ QWEN_* loaded (endpoint: {ep[:50]}..., key: {'set' if key_set else 'empty'})")
        if loaded_from:
            print(f"[LLM]   Loaded from: {loaded_from}")
    else:
        print(f"[LLM] ✗ QWEN_* NOT loaded. Checked paths:")
        for p in paths_to_try:
            exists = "✓" if p.exists() else "✗"
            print(f"[LLM]   {exists} {p}")
        print(f"[LLM]   Current: QWEN_ENDPOINT={'set' if ep else 'EMPTY'}, QWEN_API_KEY={'set' if key_set else 'EMPTY'}")


_ensure_qwen_env_loaded()


def build_asr_system_prompt(language_mode: LanguageMode) -> str:
    """
    Build a strict system prompt for Qwen Omni transcription based on language mode.
    - ENGLISH: transcribe to English only; keep medical details; avoid translation from Chinese unless certain.
    - CHINESE: transcribe to Simplified Chinese only; keep medical details; no extra explanations.
    """
    if language_mode == LanguageMode.CHINESE:
        return (
            "你是一个转写引擎。请把用户语音内容转写为**简体中文**，尽量保留与症状、用药相关的细节。"
            "不要输出英文解释或额外说明，只输出逐字转写的中文内容。"
        )
    return (
        "You are a transcription engine. Transcribe the user's speech from the audio input into English only. "
        "Preserve clinical and symptom-related details exactly as spoken. "
        "Do NOT translate from Chinese to English; if the user speaks Chinese, transcribe those phrases in English only if you are certain of the meaning, "
        "otherwise write them as pinyin or mark them explicitly in brackets. "
        "Output only the verbatim transcript text, no explanations."
    )


def build_summary_system_prompt(
    language_mode: LanguageMode,
    purpose: Literal["diary", "followup"],
) -> str:
    """
    Build a system prompt for patient-facing summaries and follow-up questions.
    - ENGLISH mode: require English-only responses.
    - CHINESE mode: require Simplified Chinese-only responses, suitable for older adults.
    """
    if purpose == "followup":
        if language_mode == LanguageMode.CHINESE:
            return (
                "你是一位温和、有耐心的健康问诊助手，正在帮助患者整理症状信息。\n"
                "请先用简短的一句话表达共情和安慰，然后只问**一个**后续问题（不超过 12 个字），"
                "问题要简单、具体，便于年长者理解和回答。\n"
                "只用简体中文回答，不要使用英文。不要给诊断或用药建议。"
            )
        # ENGLISH follow-up
        return (
            "You are a gentle, compassionate health intake assistant who deeply cares about patients' wellbeing. "
            "Your role is to collect symptom information with empathy, patience, and understanding.\n\n"
            "FIRST: acknowledge the patient's feelings in a short, warm sentence.\n"
            "THEN: ask ONE concise follow-up question (<= 12 words) to collect missing information.\n"
            "Use simple English suitable for older adults. Respond in English only. No diagnosis or medication advice."
        )

    # Diary-style daily summaries or brief explanations
    if language_mode == LanguageMode.CHINESE:
        return (
            "你正在为患者生成一段简单的每日健康小结或说明。"
            "请用简体中文、通俗易懂的表达方式，适合年长者阅读。\n"
            "语言要温和、安慰，避免医学术语；只用简体中文回答，不要输出英文。"
        )
    # ENGLISH diary
    return (
        "You are writing a short daily health summary or explanation for the patient. "
        "Use clear, plain English suitable for older adults, with a gentle and reassuring tone. "
        "Respond in English only; avoid technical jargon and keep it simple."
    )


class QwenClient:
    def __init__(self) -> None:
        self.endpoint = os.getenv("QWEN_ENDPOINT", "").strip()
        self.api_key = os.getenv("QWEN_API_KEY", "").strip()
        self.model = os.getenv("QWEN_MODEL", "qwen2.5-7b-instruct").strip()
        self.speech_model = os.getenv("QWEN_SPEECH_MODEL", "").strip() or "qwen2.5-omni-7b"
        # ASR model for speech-to-text (DashScope uses paraformer models)
        self.asr_model = os.getenv("QWEN_ASR_MODEL", "paraformer-v2").strip()
        # Dedicated speech endpoint is required for audio (DashScope native API)
        self.speech_endpoint = os.getenv("QWEN_SPEECH_ENDPOINT", "").strip()

    async def _post_json(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        if not self.endpoint:
            # Fallback mock if no endpoint configured
            return {"mock": True}
        headers = {"Authorization": f"Bearer {self.api_key}"} if self.api_key else {}
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.post(self.endpoint, json=payload, headers=headers)
            r.raise_for_status()
            return r.json()

    def _is_openai_compatible(self) -> bool:
        # crude check for OpenAI-compatible chat endpoint
        return "chat/completions" in (self.endpoint or "")

    async def _post_speech_form(self, audio_bytes: bytes, mime: str | None, lang: str, system_prompt: str, file_url: str | None = None) -> Dict[str, Any]:
        """Send audio to Qwen Omni via compatible-mode chat/completions endpoint with input_audio.
        
        Uses the same endpoint as text chat, with audio sent via input_audio in messages.content.
        Requires streaming (stream=True) as per Qwen Omni requirements.
        """
        if not self.endpoint or "chat/completions" not in self.endpoint:
            raise RuntimeError(
                "QWEN_ENDPOINT must be the compatible-mode chat/completions endpoint. "
                "Example: https://dashscope-intl.aliyuncs.com/compatible-mode/v1/chat/completions"
            )
        if not self.api_key:
            raise RuntimeError("QWEN_API_KEY not configured. Please set it to your DashScope API key.")
        
        print(f"DEBUG: Transcribing audio via Qwen Omni chat endpoint, model={self.speech_model}, size={len(audio_bytes)} bytes, mime={mime}")
        
        import base64
        fmt = self._audio_format_from_mime(mime)
        audio_b64 = base64.b64encode(audio_bytes).decode("ascii")
        data_url = f"data:audio/{fmt};base64,{audio_b64}"
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        
        payload = {
            "model": self.speech_model or "qwen2.5-omni-7b",
            "messages": [
                {
                    "role": "system",
                    "content": [
                        {
                            "type": "text",
                            "text": system_prompt
                        }
                    ]
                },
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "input_audio",
                            "input_audio": {
                                "data": data_url,
                                "format": fmt
                            }
                        },
                        {
                            "type": "text",
                            "text": f"Transcribe the attached audio into {lang} only. Return just the transcript text."
                        }
                    ]
                }
            ],
            "modalities": ["text"],
            "stream": True,
            "stream_options": {"include_usage": True}
        }
        
        text_chunks: List[str] = []
        async with httpx.AsyncClient(timeout=None) as client:
            try:
                async with client.stream("POST", self.endpoint, headers=headers, json=payload) as resp:
                    print(f"DEBUG: Stream response status={resp.status_code}")
                    resp.raise_for_status()
                    
                    async for line in resp.aiter_lines():
                        if not line or not line.startswith("data:"):
                            continue
                        data = line[5:].strip()  # Remove "data: " prefix
                        if data == "[DONE]":
                            break
                        try:
                            chunk = json.loads(data)
                            choices = chunk.get("choices", [])
                            if choices:
                                delta = choices[0].get("delta", {})
                                content = delta.get("content", "")
                                if isinstance(content, str):
                                    text_chunks.append(content)
                                elif isinstance(content, list):
                                    # Handle array format
                                    for item in content:
                                        if isinstance(item, dict) and item.get("type") == "text":
                                            text_chunks.append(item.get("text", ""))
                                        elif isinstance(item, str):
                                            text_chunks.append(item)
                        except json.JSONDecodeError as e:
                            print(f"DEBUG: Failed to parse chunk: {data[:100]}, error: {e}")
                            continue
                
                transcript = "".join(text_chunks).strip()
                print(f"DEBUG: Transcription complete, length={len(transcript)} chars")
                
                # Try to parse speaker labels if present
                spans = []
                if transcript:
                    # Simple parsing: look for "Speaker: text" patterns
                    import re
                    speaker_pattern = r"(\w+):\s*(.+?)(?=\w+:|$)"
                    matches = re.findall(speaker_pattern, transcript, re.MULTILINE | re.DOTALL)
                    if matches:
                        for idx, (speaker, text) in enumerate(matches, 1):
                            spans.append({
                                "id": f"s{idx}",
                                "speaker": speaker.lower() if speaker.lower() in ["doctor", "patient"] else "patient",
                                "text": text.strip(),
                                "start_sec": 0.0,
                                "end_sec": 0.0
                            })
                    else:
                        # No speaker labels, create single span
                        spans = [{"id": "s1", "speaker": "patient", "text": transcript, "start_sec": 0.0, "end_sec": 0.0}]
                
                return {"transcript": transcript, "spans": spans}
                
            except httpx.HTTPStatusError as exc:
                error_text = ""
                try:
                    error_text = exc.response.text[:2000]
                    print(f"DEBUG: Qwen API response body: {error_text}")
                except Exception:
                    pass
                error_msg = f"Qwen Omni transcription error {exc.response.status_code}"
                if error_text:
                    error_msg += f": {error_text}"
                print(f"DEBUG: {error_msg}")
                raise RuntimeError(error_msg) from exc
            except Exception as exc:
                print(f"DEBUG: Transcription error: {type(exc).__name__}: {exc}")
                import traceback
                print(traceback.format_exc())
                raise RuntimeError(f"Transcription failed: {exc}") from exc
    
    async def _try_native_api(self, endpoint: str, audio_bytes: bytes, mime: str | None, lang: str, file_url: str | None = None) -> Dict[str, Any]:
        """Use DashScope native ASR API with async pattern.
        
        Requires: file_url (publicly accessible URL) - the API doesn't accept base64 data directly.
        Uses paraformer-v2 model and async task pattern.
        """
        if not file_url:
            raise RuntimeError(
                "DashScope ASR API requires a publicly accessible file URL (file_urls), not base64 data. "
                "The audio file must be uploaded to a public URL first."
            )
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "X-DashScope-Async": "enable"  # Required for async transcription
        }
        
        # DashScope ASR API format - uses paraformer models
        # Try different model names if paraformer-v2 doesn't work
        asr_model = self.asr_model or "paraformer-v2"
        print(f"DEBUG: Using ASR model: {asr_model}")
        
        payload = {
            "model": asr_model,
            "input": {
                "file_urls": [file_url]  # Must be publicly accessible URLs
            }
        }
        
        async with httpx.AsyncClient(timeout=120) as client:
            # Try to submit transcription task, with fallback to alternative models
            task_id = None
            task_result = None
            models_to_try = [asr_model, "paraformer-realtime-v2", "paraformer-8k-v2", "paraformer-v1", "fun-asr", "sensevoice-v1"]
            
            for model_name in models_to_try:
                try:
                    test_payload = {"model": model_name, "input": {"file_urls": [file_url]}}
                    r = await client.post(endpoint, headers=headers, json=test_payload)
                    print(f"DEBUG: ASR task submission with model '{model_name}': status={r.status_code}")
                    
                    if r.status_code == 200:
                        task_result = r.json()
                        print(f"DEBUG: Success with model '{model_name}'. Task response: {list(task_result.keys()) if isinstance(task_result, dict) else 'not a dict'}")
                        
                        # Extract task_id from response
                        if isinstance(task_result, dict):
                            output = task_result.get("output", {})
                            if isinstance(output, dict):
                                task_id = output.get("task_id")
                            # Also check direct task_id
                            if not task_id:
                                task_id = task_result.get("task_id") or task_result.get("task", {}).get("task_id")
                        
                        if task_id:
                            print(f"DEBUG: Got task_id={task_id} with model '{model_name}', polling for results...")
                            break  # Success, exit loop
                    else:
                        error_text = r.text[:200] if hasattr(r, 'text') else ""
                        if "Model not exist" not in error_text:
                            # Different error, raise it
                            r.raise_for_status()
                except httpx.HTTPStatusError as exc:
                    error_text = ""
                    try:
                        error_text = exc.response.text[:200]
                    except Exception:
                        pass
                    if "Model not exist" in error_text:
                        print(f"DEBUG: Model '{model_name}' not found, trying next...")
                        continue  # Try next model
                    else:
                        # Different error, re-raise
                        raise
            
            if not task_id:
                raise RuntimeError(
                    f"Could not find a valid ASR model. Tried: {models_to_try}\n\n"
                    "Please set QWEN_ASR_MODEL environment variable to a valid DashScope ASR model name.\n"
                    "Check your DashScope dashboard for available models in your region."
                )
            
            try:
                
                # Step 2: Poll for results (async pattern)
                import asyncio
                max_polls = 30  # Max 30 polls
                poll_interval = 2  # Wait 2 seconds between polls
                
                for poll_num in range(max_polls):
                    await asyncio.sleep(poll_interval)
                    
                    # Query task status - DashScope uses /tasks/{task_id} endpoint
                    status_headers = {"Authorization": f"Bearer {self.api_key}"}
                    # Construct status endpoint: replace /transcription with /tasks/{task_id}
                    base_url = endpoint.rsplit("/transcription", 1)[0] if "/transcription" in endpoint else endpoint.rsplit("/", 1)[0]
                    status_url = f"{base_url}/tasks/{task_id}"
                    status_r = await client.get(status_url, headers=status_headers)
                    status_r.raise_for_status()
                    status_data = status_r.json()
                    
                    print(f"DEBUG: Poll {poll_num + 1}: status={status_data.get('output', {}).get('task_status', 'unknown')}")
                    
                    output = status_data.get("output", {})
                    task_status = output.get("task_status", "").lower()
                    
                    if task_status == "succeeded":
                        # Transcription complete
                        result = output.get("result", {})
                        sentences = result.get("sentences", [])
                        transcript = result.get("text") or ""
                        
                        # Build spans from sentences
                        spans = []
                        for idx, sent in enumerate(sentences, 1):
                            if isinstance(sent, dict):
                                spans.append({
                                    "id": f"s{idx}",
                                    "speaker": sent.get("speaker", "patient"),
                                    "text": sent.get("text", ""),
                                    "start_sec": sent.get("start", sent.get("start_time", 0.0)),
                                    "end_sec": sent.get("end", sent.get("end_time", sent.get("start", 0.0)))
                                })
                        
                        if not spans and transcript:
                            spans = [{"id": "s1", "speaker": "patient", "text": transcript, "start_sec": 0.0, "end_sec": 0.0}]
                        
                        return {"transcript": transcript, "spans": spans}
                    elif task_status in ["failed", "canceled"]:
                        error_msg = output.get("error_message", "Transcription task failed")
                        raise RuntimeError(f"Transcription task {task_status}: {error_msg}")
                    # Otherwise, continue polling (task_status is "pending" or "running")
                
                # If we get here, polling timed out
                raise RuntimeError(f"Transcription task timed out after {max_polls * poll_interval} seconds. Task ID: {task_id}")
                
            except httpx.HTTPStatusError as exc:
                error_text = ""
                try:
                    error_text = exc.response.text[:1000]
                except Exception:
                    pass
                error_msg = f"DashScope ASR API error {exc.response.status_code}"
                if error_text:
                    error_msg += f": {error_text}"
                print(f"DEBUG: {error_msg}")
                raise RuntimeError(error_msg) from exc
            except Exception as exc:
                print(f"DEBUG: ASR API error: {type(exc).__name__}: {exc}")
                import traceback
                print(traceback.format_exc())
                raise RuntimeError(f"ASR API request failed: {exc}") from exc

    async def _post_chat(self, messages: List[Dict[str, str]], response_format: str | None = None, model: str | None = None) -> str:
        """Send chat-style messages and return assistant content string.
        Supports OpenAI-compatible schema used by DashScope compatible-mode.
        """
        if not self.endpoint:
            return ""
        headers = {"Authorization": f"Bearer {self.api_key}"} if self.api_key else {}
        if self._is_openai_compatible():
            model_name = model or self.model or "qwen2.5-7b-instruct"
            payload: Dict[str, Any] = {
                "model": model_name,
                "messages": messages,
                "temperature": 0.2,
            }
            if response_format:
                # some providers accept {"type":"json_object"}
                payload["response_format"] = {"type": response_format}
            async with httpx.AsyncClient(timeout=15) as client:
                r = await client.post(self.endpoint, headers=headers, json=payload)
                r.raise_for_status()
                data = r.json()
                try:
                    return data["choices"][0]["message"]["content"].strip()
                except Exception:
                    return json.dumps(data)
        else:
            # Fallback to simple input schema
            data = await self._post_json({"input": "\n".join([f"{m['role']}: {m['content']}" for m in messages])})
            if isinstance(data, dict):
                for key in ("text", "output", "response"):
                    if key in data and isinstance(data[key], str):
                        return data[key].strip()
            if isinstance(data, str):
                return data.strip()
            return ""

    async def nlu_slot_fill(self, text: str) -> Dict[str, Any]:
        if not self.endpoint:
            # Heuristic mock for demo
            fields: Dict[str, Any] = {"symptom_label": None, "severity": None}
            t = text.lower()
            if "after" in t and "lunch" in t:
                fields["timing"] = "post-meal"
            if "after" in t and ("meal" in t or "eat" in t or "eating" in t):
                fields["timing"] = "post-meal"
            if any(k in t for k in ["stomach", "abdominal", "belly", "tummy"]):
                fields["symptom_label"] = "abdominal pain"
            if any(k in t for k in ["headache", "migraine", "head pain"]):
                fields["symptom_label"] = fields.get("symptom_label") or "headache"
            for num in range(10, -1, -1):
                if f" {num} " in f" {t} ":
                    fields["severity"] = num
                    break
            # Parse "mala" or spicy as trigger
            if "mala" in t or "spicy" in t or "chili" in t:
                fields.setdefault("triggers", [])
                if "spicy" not in fields["triggers"]:
                    fields["triggers"].append("spicy")
            # Parse fever and temperature
            if "fever" in t or "degree" in t or "degrees" in t:
                fields.setdefault("associated", [])
                if "fever" not in fields["associated"]:
                    fields["associated"].append("fever")
                # extract temperature like '39' near 'degree'
                import re
                m = re.search(r"(\d{2}(?:\.\d)?)\s*degree", t)
                if m:
                    try:
                        fields["fever_temp_c"] = float(m.group(1))
                    except Exception:
                        pass
            # Parse bowel changes
            bt = t.replace("bowel", "bowel ")  # ensure token separation
            if any(word in bt for word in ["diarrhea", "diarrhoea", "constipation", "blood in stool", "bloody stool", "blood in the stool"]):
                fields.setdefault("associated", [])
                for w in ["diarrhea", "constipation", "blood in stool"]:
                    if w.split()[0] in bt and w not in fields["associated"]:
                        fields["associated"].append(w)
                fields["bowel_changes"] = "present"
            elif ("no change" in t or "no changes" in t or "no change in habit" in t) and ("bowel" in t or "habit" in t):
                fields["bowel_changes"] = "none"
            return {"fields": fields, "provenance": {"nlu": True}}
        # Use chat completion to request strict JSON
        system = {
            "role": "system",
            "content": (
                "You extract health intake fields in strict JSON. Only output a compact JSON object with keys: "
                "symptom_label, onset, location, duration, character, aggravating, relieving, timing, "
                "severity (0-10), associated, triggers. Use null or empty list when unknown. No extra text."
            ),
        }
        user = {"role": "user", "content": f"Text: {text}"}
        content = await self._post_chat([system, user], response_format="json_object")
        try:
            obj = json.loads(content)
            return {"fields": obj, "provenance": {"nlu": True}}
        except Exception:
            # if provider returned plain text, fallback to empty
            return {"fields": {}, "provenance": {"nlu": True}}

    async def clarifier_select(self, fields: Dict[str, Any], pathway: str) -> List[str]:
        # Whitelisted clarifiers per pathway (demo subset)
        whitelist: Dict[str, List[str]] = {
            "abdominal_pain": [
                "clarifier.meal_relation",
                "clarifier.fever",
                "clarifier.bowel_changes",
            ],
            "sleep": ["clarifier.sleep_duration", "clarifier.sleep_quality"],
            "medication": ["clarifier.missed_dose", "clarifier.side_effects"],
            "meal": ["clarifier.meal_time", "clarifier.meal_composition"],
        }
        allowed = whitelist.get(pathway, [])
        if not self.endpoint:
            # Simple rule: pick first two missing-related clarifiers
            return allowed[:2]

        prompt = (
            "Given current fields and a pathway, return up to two clarifier IDs from a whitelist only. "
            f"Whitelist: {allowed}. Fields: {fields}. Pathway: {pathway}. Output JSON array of strings."
        )
        resp = await self._post_json({"input": prompt})
        # Expect array of strings, but guard in case
        if isinstance(resp, list):
            return [c for c in resp if c in allowed][:2]
        return allowed[:2]

    async def generate_question(self, missing_field_ids: List[str], fields: Dict[str, Any], messages: List[Dict[str, str]]) -> str:
        """Return ONE short, natural-language question targeting the highest-priority missing field.
        Requires LLM endpoint; will raise if unavailable so caller can handle.
        """
        if not missing_field_ids:
            return ""
        # Read env at request time so .env loaded after worker start is picked up
        endpoint = (os.getenv("QWEN_ENDPOINT") or "").strip() or self.endpoint
        if not endpoint:
            raise RuntimeError("LLM endpoint not configured")
        if not self.endpoint and endpoint:
            self.endpoint = endpoint
            self.api_key = (os.getenv("QWEN_API_KEY") or "").strip() or self.api_key
        target = missing_field_ids[0]

        # Build a compact chat with system + conversation, respecting current language mode
        mode = get_current_language_mode()
        sys = {
            "role": "system",
            "content": build_summary_system_prompt(mode, "followup"),
        }
        conv_msgs = [{"role": m.get("role", "user"), "content": m.get("text", "")} for m in messages[-6:]]
        hint = {
            "role": "system",
            "content": f"Missing clarifier IDs: {missing_field_ids}. Known fields: {json.dumps(fields, ensure_ascii=False)}",
        }
        content = await self._post_chat([sys, hint] + conv_msgs)
        return content or "Could you tell me a bit more?"

    async def recommend_from_entries(self, entries: List[Dict[str, Any]], window_days: int) -> List[Dict[str, Any]]:
        """Analyze past entries and return non-medical recommendations with evidence pointers.
        Uses LLM to interpret patterns if endpoint available; otherwise heuristic fallback.
        """
        if not entries:
            return []
        if not self.endpoint:
            # Fallback: simple rule-based
            suggestions = []
            last = entries[-1]
            last_id = last.get("id")
            fields = last.get("fields", {}) or {}
            if fields.get("severity") and fields.get("severity") >= 7:
                suggestions.append({
                    "text": "Your recent entries show higher severity. Consider preparing a Doctor Pack.",
                    "evidence": [f"entry_id:{last_id}", "feature:severity_high"]
                })
            return suggestions if suggestions else [{"text": "Continue monitoring symptoms.", "evidence": [f"entry_id:{last_id}"]}]

        # Build a detailed summary of entries for LLM analysis
        summary_lines = []
        for e in entries[-50:]:
            fields = e.get('fields') or {}
            ts = e.get('ts', '')[:10]
            label = fields.get('symptom_label', '')
            raw = e.get('symptom_raw', '')[:80]
            sev = fields.get('severity')
            timing = fields.get('timing')
            triggers = fields.get('triggers') or []
            assoc = fields.get('associated') or []
            summary_lines.append(f"{ts} | {label} | {raw} | severity={sev} | timing={timing} | triggers={','.join(triggers)} | associated={','.join(assoc)} | id={e.get('id','')}")
        labels = [((e.get('fields') or {}).get('symptom_label') or '').lower() for e in entries]
        top_labels = [l for l in {l for l in labels if l}]
        entry_text = "\n".join(summary_lines)
        mode = get_current_language_mode()
        lang_note = "Respond in English only, using simple language for older adults." if mode == LanguageMode.ENGLISH else "只用简体中文回答，用适合年长者的简单表达方式。"
        sys = {
            "role": "system",
            "content": (
                "You analyze patient diary entries and produce detailed, professional non-medical recommendations. Output strict JSON array (3-5 items), each object: "
                '{"text": "detailed recommendation paragraph (2-3 sentences explaining what to do, why based on patterns, and how to track)", "evidence": ["entry_id:..."]}. '
                "Rules: no diagnosis or medication advice; be detailed and professional; tailor to symptom categories observed; "
                "explain patterns (frequency, timing, triggers, severity trends); provide actionable next steps; "
                "always include at least one evidence token entry_id:* from provided entries; avoid generic one-liners; use clear, patient-friendly language. "
                + lang_note
            ),
        }
        user = {
            "role": "user",
            "content": (
                f"Analyze the last {window_days} days of entries with detailed information:\n"
                f"Symptom categories observed: {', '.join(top_labels) or 'n/a'}.\n"
                f"Total entries: {len(entries)}.\n"
                f"Detailed entries:\n{entry_text}\n\n"
                "Return a JSON array of 3-5 detailed, professional recommendations. Each recommendation should be 2-3 sentences explaining what to monitor/track, why (based on patterns observed), and how to do it."
            ),
        }
        content = await self._post_chat([sys, user], response_format="json_object")
        try:
            obj = json.loads(content)
            if isinstance(obj, list):
                # sanitize evidence
                valid_ids = {e.get('id') for e in entries}
                for s in obj:
                    ev = [tok for tok in (s.get('evidence') or []) if isinstance(tok, str) and tok.startswith('entry_id:') and (tok.split(':',1)[1] in valid_ids)]
                    if not ev and entries:
                        ev = [f"entry_id:{entries[-1].get('id')}"]
                    s['evidence'] = ev
                return obj
            if isinstance(obj, dict) and "suggestions" in obj:
                valid_ids = {e.get('id') for e in entries}
                out = []
                for s in obj["suggestions"]:
                    ev = [tok for tok in (s.get('evidence') or []) if isinstance(tok, str) and tok.startswith('entry_id:') and (tok.split(':',1)[1] in valid_ids)]
                    if not ev and entries:
                        ev = [f"entry_id:{entries[-1].get('id')}"]
                    s['evidence'] = ev
                    out.append(s)
                return out
        except Exception:
            pass
        # Fallback
        return [{"text": "Continue monitoring symptoms.", "evidence": [f"entry_id:{entries[-1].get('id')}"]}]

    async def summarize_doctor_pack(self, entries: List[Dict[str, Any]], window_days: int) -> Dict[str, Any]:
        """Create a bilingual doctor pack summary from diary entries.
        Returns JSON:
        {
            english_summary: str,
            chinese_summary: str,
            symptom_groups:[{symptom_label, dates[], summary, evidence[]}],
            suggestions:[{text,evidence[]}],
            structured_events: {...}
        }.
        """
        if not entries:
            return {
                "english_summary": "",
                "chinese_summary": "",
                "symptom_groups": [],
                "suggestions": [],
                "structured_events": {},
            }
        
        # Pre-group entries by symptom_label and extract dates directly from entries
        groups_by_label = {}
        for e in entries:
            fields = e.get("fields", {}) or {}
            label = (fields.get("symptom_label") or "symptom").lower()
            if label not in groups_by_label:
                groups_by_label[label] = {"dates": [], "entry_ids": []}
            date_str = (e.get("ts", "") or "")[:10]
            if date_str and date_str not in groups_by_label[label]["dates"]:
                groups_by_label[label]["dates"].append(date_str)
            groups_by_label[label]["entry_ids"].append(e.get("id"))
        
        # Build a simple structured representation of recent symptoms/events
        structured_events: Dict[str, Any] = {
            "window_days": window_days,
            "entry_count": len(entries),
            "groups_by_label": groups_by_label,
        }
        if not self.endpoint:
            # Heuristic: use pre-grouped data with bilingual labels/summaries
            out = []
            for label, data in groups_by_label.items():
                en_title = label.replace("_", " ").title()
                out.append({
                    "symptom_label": label,
                    "symptom_label_english": en_title,
                    "symptom_label_chinese": "",
                    "summary": f"Reported {len(data['entry_ids'])} times",
                    "summary_english": f"Reported {len(data['entry_ids'])} times",
                    "summary_chinese": f"本周期内记录 {len(data['entry_ids'])} 次。",
                    "dates": sorted(data["dates"]),
                    "evidence": [f"entry_id:{eid}" for eid in data["entry_ids"][:5]],
                })
            sugg = await self.recommend_from_entries(entries, window_days)
            english_summary = "Summary based on your recent diary entries."
            chinese_summary = "基于您最近的健康日记生成的就诊概要。"
            _log.info(
                "Doctor pack generated without LLM (bilingual=True, mode=%s, en=%r, zh=%r)",
                get_current_language_mode().name,
                english_summary[:100],
                chinese_summary[:100],
            )
            return {
                "english_summary": english_summary,
                "chinese_summary": chinese_summary,
                "symptom_groups": out,
                "suggestions": sugg,
                "structured_events": structured_events,
            }

        # Build context with labels, dates, and key fields for LLM summary generation
        lines = []
        for e in entries[-50:]:
            fields = e.get("fields", {}) or {}
            label = fields.get("symptom_label") or "symptom"
            ts = e.get("ts", "")[:10]
            raw = e.get("symptom_raw", "")[:60]
            sev = fields.get("severity")
            timing = fields.get("timing")
            triggers = fields.get("triggers") or []
            lines.append(
                f"{ts} | {label} | {raw} | sev={sev} timing={timing} "
                f"triggers={','.join(triggers)} | id={e.get('id','')}"
            )
        ctx = "\n".join(lines)
        sys = {
            "role": "system",
            "content": (
                "You are generating a bilingual doctor pack from structured symptom and diary data. "
                "Merge similar symptoms into a single entry (e.g. 'stomach ache', 'abdominal pain', 'belly pain' -> one group). "
                "Produce strict JSON with:\n"
                "- doctor_pack_english: concise doctor-facing summary in English.\n"
                "- doctor_pack_chinese: equivalent summary in Simplified Chinese.\n"
                "- symptom_groups: array of merged symptom entries. Each object MUST have:\n"
                "  symptom_label_english: short English title (e.g. 'Abdominal pain').\n"
                "  symptom_label_chinese: short Chinese title (e.g. '腹痛').\n"
                "  summary_english: 1-3 sentence description in English (severity, timing, triggers if known).\n"
                "  summary_chinese: same description in Simplified Chinese.\n"
                "  source_labels: array of original symptom_label strings that were merged into this entry (e.g. ['abdominal pain','stomach ache']).\n"
                "- suggestions: array of non-medical recommendations. Each object MUST have:\n"
                "  text_english: recommendation text in English.\n"
                "  text_chinese: same recommendation in Simplified Chinese.\n"
                "Rules: same content in both languages. No diagnosis or medication advice."
            ),
        }
        user = {
            "role": "user",
            "content": (
                "Structured symptom/events data from diary entries:\n"
                f"{ctx}\n\n"
                "groups_by_label (use these keys in source_labels when merging):\n"
                f"{json.dumps(groups_by_label, ensure_ascii=False)}\n\n"
                "Return strict JSON with doctor_pack_english, doctor_pack_chinese, symptom_groups (with symptom_label_english, symptom_label_chinese, summary_english, summary_chinese, source_labels), and suggestions (with text_english, text_chinese)."
            ),
        }
        content = await self._post_chat([sys, user], response_format="json_object")
        try:
            obj = json.loads(content)
            if isinstance(obj, dict):
                english_summary = obj.get("doctor_pack_english", "") or ""
                chinese_summary = obj.get("doctor_pack_chinese", "") or ""
                raw_groups = obj.get("symptom_groups") or []
                raw_suggestions = obj.get("suggestions") or []
                valid_ids = {e.get('id') for e in entries}

                def sanitize_evidence(ev):
                    ev = ev or []
                    out = [
                        tok
                        for tok in ev
                        if isinstance(tok, str)
                        and tok.startswith('entry_id:')
                        and (tok.split(':', 1)[1] in valid_ids)
                    ]
                    return out

                # Merge LLM summaries with actual dates: collect dates from all source_labels
                final_groups: List[Dict[str, Any]] = []
                for g in raw_groups:
                    if not isinstance(g, dict):
                        continue
                    source_labels = g.get("source_labels") or []
                    if not source_labels and g.get("symptom_label"):
                        source_labels = [(g.get("symptom_label") or "symptom").lower()]
                    if not source_labels:
                        source_labels = list(groups_by_label.keys())[:1]
                    all_dates = []
                    all_entry_ids = []
                    for sl in source_labels:
                        key = (sl if isinstance(sl, str) else str(sl)).lower()
                        if key in groups_by_label:
                            all_dates.extend(groups_by_label[key]["dates"])
                            all_entry_ids.extend(groups_by_label[key]["entry_ids"])
                    all_dates = sorted(set(all_dates))
                    final_groups.append({
                        "symptom_label": (g.get("symptom_label") or g.get("symptom_label_english") or "symptom").lower(),
                        "symptom_label_english": g.get("symptom_label_english") or g.get("symptom_label", "Symptom"),
                        "symptom_label_chinese": g.get("symptom_label_chinese") or "",
                        "summary": g.get("summary", ""),
                        "summary_english": g.get("summary_english") or g.get("summary", ""),
                        "summary_chinese": g.get("summary_chinese") or "",
                        "dates": all_dates,
                        "evidence": sanitize_evidence(g.get("evidence")) or [f"entry_id:{eid}" for eid in all_entry_ids[:10]],
                    })
                # If LLM didn't return groups, use pre-grouped data with heuristic bilingual fields
                if not final_groups:
                    for label, data in groups_by_label.items():
                        final_groups.append({
                            "symptom_label": label,
                            "symptom_label_english": label.replace("_", " ").title(),
                            "symptom_label_chinese": "",
                            "summary": f"Reported {len(data['entry_ids'])} times",
                            "summary_english": f"Reported {len(data['entry_ids'])} times",
                            "summary_chinese": f"本周期内记录 {len(data['entry_ids'])} 次。",
                            "dates": sorted(data["dates"]),
                            "evidence": [f"entry_id:{eid}" for eid in data["entry_ids"][:5]],
                        })
                cleaned_suggestions: List[Dict[str, Any]] = []
                for s in raw_suggestions:
                    if not isinstance(s, dict):
                        continue
                    ev = sanitize_evidence(s.get('evidence'))
                    if not ev and entries:
                        ev = [f"entry_id:{entries[-1].get('id')}"]
                    cleaned_suggestions.append({
                        "text": s.get("text", "") or s.get("text_english", ""),
                        "text_english": s.get("text_english") or s.get("text", ""),
                        "text_chinese": s.get("text_chinese") or "",
                        "evidence": ev,
                    })

                _log.info(
                    "Doctor pack generated via LLM (bilingual=True, mode=%s, en=%r, zh=%r)",
                    get_current_language_mode().name,
                    english_summary[:100],
                    chinese_summary[:100],
                )
                return {
                    "english_summary": english_summary,
                    "chinese_summary": chinese_summary,
                    "symptom_groups": final_groups,
                    "suggestions": cleaned_suggestions,
                    "structured_events": structured_events,
                }
        except Exception:
            pass
        # Fallback: use pre-grouped data with bilingual fields
        out = []
        for label, data in groups_by_label.items():
            en_title = label.replace("_", " ").title()
            out.append({
                "symptom_label": label,
                "symptom_label_english": en_title,
                "symptom_label_chinese": "",
                "summary": f"Reported {len(data['entry_ids'])} times",
                "summary_english": f"Reported {len(data['entry_ids'])} times",
                "summary_chinese": f"本周期内记录 {len(data['entry_ids'])} 次。",
                "dates": sorted(data["dates"]),
                "evidence": [f"entry_id:{eid}" for eid in data["entry_ids"][:5]],
            })
        english_summary = "Summary based on your recent diary entries."
        chinese_summary = "基于您最近的健康日记生成的就诊概要。"
        _log.info(
            "Doctor pack fallback (bilingual=True, mode=%s, en=%r, zh=%r)",
            get_current_language_mode().name,
            english_summary[:100],
            chinese_summary[:100],
        )
        return {
            "english_summary": english_summary,
            "chinese_summary": chinese_summary,
            "symptom_groups": out,
            "suggestions": [],
            "structured_events": structured_events,
        }

    async def summarize_entry(self, entry: Dict[str, Any]) -> str:
        """Summarize a single diary entry into a brief, doctor-friendly sentence.
        Prefer structured fields; use messages (if present in provenance) as context. Do not quote user wording.
        """
        fields = entry.get("fields", {}) or {}
        raw = entry.get("symptom_raw", "")
        provenance = entry.get("provenance") or {}
        messages = provenance.get("messages") or []
        if not self.endpoint:
            parts = []
            if fields.get("symptom_label"):
                parts.append(fields.get("symptom_label"))
            elif raw:
                parts.append(raw)
            if fields.get("severity") is not None:
                parts.append(f"severity {fields.get('severity')}/10")
            if fields.get("timing"):
                parts.append(f"{fields.get('timing')}")
            if fields.get("triggers"):
                parts.append(f"triggers: {', '.join(fields.get('triggers', []))}")
            if fields.get("fever_temp_c"):
                parts.append(f"fever {fields.get('fever_temp_c')}°C")
            return "; ".join(parts) if parts else (raw or "Symptom reported")

        mode = get_current_language_mode()
        sys = {
            "role": "system",
            "content": (
                build_summary_system_prompt(mode, "diary")
                + " You summarize a patient diary entry into ONE concise sentence for a doctor. "
                "Do not quote user wording; paraphrase clinically. Include symptom, severity if given, timing/triggers if relevant, associated symptoms if notable. "
                "Keep it brief (<= 20 words); no diagnosis or medication advice; natural language; avoid Q&A phrasing."
            ),
        }
        user_data = {
            "fields": fields,
            "context_messages": messages[:6],
        }
        user = {"role": "user", "content": f"Summarize this entry from fields and context: {json.dumps(user_data, ensure_ascii=False)}"}
        content = await self._post_chat([sys, user])
        text = content.strip() or (fields.get("symptom_label") or raw or "Symptom reported")
        _log.info(
            "Daily entry summary generated (mode=%s, text=%r)",
            mode.name,
            text[:100],
        )
        return text

    # --- Visit transcription & summary ---

    def _audio_format_from_mime(self, mime: Optional[str]) -> str:
        mime = (mime or "").lower()
        if "webm" in mime:
            return "webm"
        if "ogg" in mime:
            return "ogg"
        if "mp3" in mime:
            return "mp3"
        if "m4a" in mime or "aac" in mime:
            return "m4a"
        return "wav"

    async def transcribe_audio(self, audio_bytes: bytes, lang: Optional[str] = None, mime: Optional[str] = None, file_url: Optional[str] = None) -> Dict[str, Any]:
        """
        Send audio bytes to Qwen Omni speech endpoint for transcription with speaker tags.
        Language mode is derived from the provided lang code ("en"/"zh") or the persisted LanguageMode.
        """
        if not audio_bytes:
            raise ValueError("audio_bytes required")
        # Resolve language mode: prefer explicit lang param, otherwise current persisted mode
        mode = LanguageMode.CHINESE if lang == "zh" else LanguageMode.ENGLISH
        if lang is None:
            mode = get_current_language_mode()
        lang_code = as_lang_code(mode)
        system_prompt = build_asr_system_prompt(mode)
        _log.info("Transcribing audio via Qwen Omni (mode=%s, lang=%s)", mode.name, lang_code)
        data = await self._post_speech_form(audio_bytes, mime, lang_code, system_prompt, file_url)
        transcript = data.get("text") or data.get("transcript") or ""
        segments = data.get("segments") or data.get("spans") or []
        spans: List[Dict[str, Any]] = []
        if isinstance(segments, list) and segments:
            for idx, seg in enumerate(segments, start=1):
                spans.append({
                    "id": seg.get("id") or seg.get("segment_id") or f"s{idx}",
                    "speaker": (seg.get("speaker") or seg.get("role") or "patient").lower()[:20] or "patient",
                    "start": seg.get("start_sec") or seg.get("start") or seg.get("start_time") or 0.0,
                    "end": seg.get("end_sec") or seg.get("end") or seg.get("end_time") or seg.get("start_sec") or 0.0,
                    "text": seg.get("text") or seg.get("sentence") or "",
                })
        else:
            spans = [{"id": "s1", "speaker": "patient", "start": 0.0, "end": 0.0, "text": transcript or ""}]
        # Ensure defaults
        for idx, span in enumerate(spans, start=1):
            span.setdefault("id", f"s{idx}")
            span.setdefault("speaker", "patient")
            span.setdefault("start", 0.0)
            span.setdefault("end", span.get("start", 0.0))
            span.setdefault("text", "")
        return {
            "transcript": transcript or "\n".join(s.get("text", "") for s in spans if s.get("text")),
            "spans": spans,
        }

    async def summarize_visit(self, transcript: str, spans: List[Dict[str, Any]], lang: str = "en") -> Dict[str, Any]:
        """Summarize a visit transcript emphasizing doctor instructions."""
        if not transcript:
            return {"summary_md": "No transcript available.", "action_items": [], "provenance": []}
        if not self.endpoint:
            return {
                "summary_md": "- Doctor asked patient to keep a daily symptom diary.\n- Patient acknowledged and agreed to follow instructions.",
                "action_items": [
                    {"text": "Log symptoms daily with timing and triggers.", "source_span_id": "s1"},
                    {"text": "Share diary with doctor during next visit.", "source_span_id": "s2"},
                ],
                "provenance": spans or [],
            }
        sys = {
            "role": "system",
            "content": (
                "You are a clinical assistant who summarizes doctor visits for patients. "
                "Produce JSON with fields: summary_md (markdown bullet list highlighting doctor instructions, follow-ups, meds), "
                "action_items (array of {text, source_span_id}), and provenance (array of {speaker, text, source_span_id}). "
                "Focus on what the doctor said, next steps, monitoring instructions, dosing reminders. "
                "Use patient-friendly language (CEFR B1), no diagnosis beyond transcript."
            ),
        }
        payload = {
            "transcript": transcript,
            "spans": spans,
            "lang": lang,
        }
        user = {"role": "user", "content": f"Summarize this visit:\n{json.dumps(payload, ensure_ascii=False)}"}
        content = await self._post_chat([sys, user], response_format="json_object")
        try:
            data = json.loads(content)
        except Exception:
            data = {}
        summary = data.get("summary_md") if isinstance(data, dict) else None
        action_items = data.get("action_items") if isinstance(data, dict) else []
        provenance = data.get("provenance") if isinstance(data, dict) else []
        # Sanitize action items
        clean_actions = []
        for item in action_items or []:
            if not isinstance(item, dict):
                continue
            text = item.get("text")
            if not text:
                continue
            clean_actions.append({"text": text, "source_span_id": item.get("source_span_id")})
        clean_prov = []
        for span in provenance or spans or []:
            if isinstance(span, dict):
                clean_prov.append({
                    "speaker": span.get("speaker", "doctor"),
                    "text": span.get("text", ""),
                    "source_span_id": span.get("id") or span.get("source_span_id"),
                })
        return {
            "summary_md": summary or "- Unable to summarize the visit.",
            "action_items": clean_actions,
            "provenance": clean_prov,
        }


