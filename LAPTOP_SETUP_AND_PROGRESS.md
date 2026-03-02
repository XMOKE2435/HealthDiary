# HealthDairy – Progress Summary & Laptop Setup

## Current progress and recent changes

### Demo page (inline script fixes)
- **Fixed multiple JS syntax errors** that caused “Invalid or unexpected token” and “toggleVoice is not defined”:
  - Replaced curly apostrophe in “I’ve” and switched to double-quoted strings where needed.
  - Escaped `</` in template literals (e.g. `<\/div>`) so the HTML parser doesn’t treat it as a closing tag.
  - Replaced bullet character `•` with `-` and converted long single-quoted alert/error strings to double-quoted to avoid apostrophe issues.
- **Result:** Demo loads and buttons (Voice Input, Send, Reset, etc.) work on both laptop and Pi when using a hard refresh (Ctrl+Shift+R).

### Doctor pack (bilingual + merged symptoms)
- **Symptom entries:** Each entry now has **English and Chinese titles** (e.g. “Abdominal pain / 腹痛”) and **bilingual descriptions** (summary_english, summary_chinese).
- **Merging:** The LLM **combines similar symptoms** into one entry (e.g. “stomach ache”, “abdominal pain” → one group) and returns `source_labels` so dates from all merged entries are aggregated.
- **Suggestions:** Each suggestion has **text_english** and **text_chinese** and is shown in both languages in the pack HTML.
- **Files:** `backend/app/services/llm.py` (prompt + parsing), `backend/app/routers/doctor_pack.py` (HTML rendering).

### Recommendations (empty suggestions fix)
- **Cause:** GET /recommendations was filtering by **exact** `symptom_label == "abdominal pain"`, so different casing or wording (e.g. “Abdominal pain”, “stomach ache”) produced no entries and empty suggestions.
- **Changes in** `backend/app/routers/recommendations.py`:
  - Label filter is **case-insensitive** and trims whitespace (`strip().lower()` on both sides).
  - If a label is provided but **no entries match**, the endpoint **falls back to all entries** in the time window so suggestions are still returned from the user’s data.
- **Result:** Recommendations return suggestions when the user has entries in the last N days, even if the demo’s fixed `label=abdominal pain` doesn’t match stored labels exactly.

### Other context (from earlier work)
- **Bilingual support:** Language mode (EN/中文) and LLM/ASR/TTS integration exist (`language_mode.py`, `routers/language_mode.py`).
- **Voice on Pi:** Browser speech API can fail on Chromium; using Firefox on Pi or “Upload / Select Audio” (backend transcribe) is recommended.
- **.env:** QWEN_* can be loaded from project root or `backend/.env`; manual parser supports both `KEY=value` and PowerShell-style `$env:KEY="value"`.

---

## Laptop setup from scratch (testing the app)

Follow these steps on your **Windows laptop** to run and test HealthDairy locally.

### 1. Prerequisites
- **Python 3.10+** installed (check: `python --version` or `py -3 --version`).
- **Git** (optional; only if you clone the repo).

### 2. Open the project
- Open the project folder (e.g. `D:\HealthDairy`) in your terminal (PowerShell or Command Prompt).

### 3. Create and activate a virtual environment
```powershell
cd D:\HealthDairy
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```
If you get an execution policy error, run:
```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```
Then run the Activate script again.

### 4. Install dependencies
```powershell
pip install -r backend\requirements.txt
```

### 5. Configure environment (for LLM and optional features)
Create a file named **`.env`** in the **project root** (`D:\HealthDairy\.env`), with **plain** `KEY=value` lines (no `$env:...`). For example:

```env
QWEN_ENDPOINT=https://dashscope-intl.aliyuncs.com/compatible-mode/v1
QWEN_API_KEY=your-api-key-here
QWEN_MODEL=qwen2.5-7b-instruct
QWEN_SPEECH_MODEL=qwen2.5-omni-7b
```

- **With these set:** Symptom chat, doctor pack, and recommendations use the LLM; transcription can use the speech model.
- **Without them:** The app still runs; endpoints use heuristics/fallbacks (e.g. fixed questions, no real LLM suggestions).

### 6. Run the server
From the project root (with `.venv` activated):

```powershell
uvicorn backend.app.main:app --host 127.0.0.1 --port 8000
```

You should see something like:
- `Application startup complete`
- `Uvicorn running on http://127.0.0.1:8000`

### 7. Open the demo in the browser
- In your browser go to: **http://127.0.0.1:8000/demo**  
  (You **must** include `/demo` – the root URL shows API docs, not the demo UI.)

### 8. Quick test flow
1. **Section 1 – Symptom entry:** Enter a symptom (e.g. “stomach pain”), click Send; use follow-ups until the entry is saved. Optionally try Voice Input or “Upload Audio” if you have a mic/audio file.
2. **Section 2 – Recommendations:** Click “Fetch Recommendations”. You should get non-empty suggestions if you have at least one entry in the last 30 days (label matching is now case-insensitive and falls back to all entries).
3. **Section 3 – Doctor pack:** Click “Generate Doctor Pack”, then open the pack link. You should see bilingual symptom titles/descriptions and suggestions.
4. **Section 4 – Visit capture:** Record or upload audio and run transcribe/summary if you want to test that path.

### 9. Optional: check that env is loaded
- GET **http://127.0.0.1:8000/env-check** (if that route exists) shows whether QWEN_* are set (no secrets).  
- Server logs on startup may also show `[LLM] ✓ QWEN_* loaded`.

### 10. Stop the server
- In the terminal where uvicorn is running, press **Ctrl+C**.

---

## Troubleshooting (laptop)

| Issue | What to do |
|-------|------------|
| “No module named 'fastapi'” | Ensure `.venv` is activated and you ran `pip install -r backend\requirements.txt` from the project root. |
| “LLM endpoint not configured” / 503 on chat | Add or fix `.env` in project root with `QWEN_ENDPOINT` and `QWEN_API_KEY` (plain `KEY=value`), then restart the server. |
| Buttons do nothing / “toggleVoice is not defined” | Hard refresh the demo page (Ctrl+Shift+R). If it persists, ensure you have the latest code (inline script fixes). |
| Empty recommendations | Ensure you have at least one diary entry in the last 30 days (e.g. complete Section 1 once). Label filter is now case-insensitive and falls back to all entries. |
| Voice input “not allowed” | Use **http://127.0.0.1:8000/demo** (or localhost), not http://&lt;your-IP&gt;:8000/demo; microphone is blocked on non-secure non-localhost in most browsers. |

---

## Summary

- **Progress:** Demo JS fixed; doctor pack bilingual and merged; recommendations no longer empty due to label/time filters.
- **Laptop test:** Create `.venv` → install deps → add `.env` (optional) → run `uvicorn backend.app.main:app --host 127.0.0.1 --port 8000` → open **http://127.0.0.1:8000/demo**.
