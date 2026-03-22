# HealthDairy – Complete Flow Guide

This guide walks you through the **full process**: starting the web app on your laptop, syncing code to GitHub, connecting to the Raspberry Pi via SSH, and updating the app on the Pi from Git. Use it as a single reference for the whole workflow.

---

## Part 1: Start the Web App on Your Laptop (from scratch)

### 1.1 Prerequisites

- **Python 3.10+** (check: `python --version` or `py -3 --version`)
- **Git** (for later steps)

### 1.2 Open the project and create a virtual environment

In **PowerShell** (or Command Prompt), from your project folder:

```powershell
cd D:\HealthDairy
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

If you see an execution policy error:

```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

Then run the Activate script again.

### 1.3 Install dependencies

```powershell
pip install -r backend\requirements.txt
```

### 1.4 Optional: configure LLM (recommended for full features)

Create a file **`.env`** in the **project root** (`D:\HealthDairy\.env`) with **plain** `KEY=value` lines:

```env
QWEN_ENDPOINT=https://dashscope-intl.aliyuncs.com/compatible-mode/v1
QWEN_API_KEY=your-api-key-here
QWEN_MODEL=qwen2.5-7b-instruct
QWEN_SPEECH_MODEL=qwen2.5-omni-7b
```

- **With `.env`:** Symptom chat, doctor pack, recommendations, and transcription use the LLM.
- **Without:** The app still runs with fallbacks (e.g. fixed questions, no real LLM).

### 1.5 Run the server

With `.venv` still activated:

```powershell
uvicorn backend.app.main:app --host 127.0.0.1 --port 8000
```

You should see:

- `Application startup complete`
- `Uvicorn running on http://127.0.0.1:8000`

### 1.6 Open the demo in the browser

- Go to: **http://127.0.0.1:8000/demo**  
  (You must include `/demo`; the root URL shows API docs.)

### 1.7 Stop the server

- In the terminal: **Ctrl+C**

---

## Part 2: Sync Your Code to GitHub

### 2.1 First-time only: create a GitHub repo and connect

1. **Create a new repository on GitHub**  
   - Go to https://github.com/new  
   - Name it (e.g. `HealthDairy`), leave it empty (no README/license if you already have code).

2. **Connect your local project to GitHub** (run in `D:\HealthDairy`):

   ```powershell
   git remote add origin https://github.com/YOUR_USERNAME/HealthDairy.git
   ```

   Replace `YOUR_USERNAME` and `HealthDairy` with your GitHub username and repo name. If `origin` already exists, use `git remote set-url origin https://github.com/...` instead.

3. **Push your code** (use your branch name; common defaults are `main` or `master`):

   ```powershell
   git add .
   git commit -m "Initial HealthDairy project"
   git branch -M main
   git push -u origin main
   ```

### 2.2 Regular workflow: push changes from laptop

Whenever you’ve made changes and want to save them to GitHub (and later pull on the Pi):

```powershell
cd D:\HealthDairy
git status
git add .
git commit -m "Describe your changes (e.g. Add bilingual doctor pack)"
git push origin main
```

Use your actual branch name if it’s not `main` (e.g. `git push origin master`).

---

## Part 3: SSH to the Raspberry Pi

### 3.1 Find the Pi’s IP address

**On the Raspberry Pi** (monitor + keyboard, or existing SSH session):

```bash
hostname -I
```

Use the first address (e.g. `192.168.1.100`). Write it down.

**From the laptop** you’ll use: `ssh USERNAME@PI_IP` (e.g. `ssh pi@192.168.1.100`). Default Pi OS user is often `pi`; your setup might use another (e.g. `xmoke`).

### 3.2 Connect from your laptop

**Windows (PowerShell or Command Prompt):**

```powershell
ssh pi@YOUR_PI_IP
```

Example: `ssh pi@192.168.1.100`

Enter the Pi user’s password when prompted. You’re now in a shell on the Pi.

### 3.3 Optional: SSH without password (key-based login)

**One-time on your laptop:**

```powershell
ssh-keygen -t ed25519 -C "your_email@example.com"
```

Press Enter to accept the default path. Then copy your public key to the Pi (replace `pi` and `YOUR_PI_IP`):

```powershell
type $env:USERPROFILE\.ssh\id_ed25519.pub | ssh pi@YOUR_PI_IP "mkdir -p ~/.ssh && cat >> ~/.ssh/authorized_keys"
```

After that, `ssh pi@YOUR_PI_IP` will connect without asking for a password.

### 3.4 Copy/paste between laptop and Pi

- **Paste into the Pi:** Copy text on the laptop (Ctrl+C), then in the SSH terminal paste (e.g. Ctrl+V in Windows Terminal; right-click in PuTTY).
- **Copy from the Pi:** Select the output in the SSH terminal, then Ctrl+C (or right-click Copy). The text is on your laptop clipboard; paste it anywhere with Ctrl+V.

---

## Part 4: Update the Code on the Raspberry Pi from Git

Use this after you’ve pushed from the laptop (Part 2). The Pi should already have the repo cloned (e.g. `~/HealthDairy` or `~/HealthDiary` — use the folder name you actually use).

### 4.1 SSH into the Pi

From your laptop:

```powershell
ssh pi@YOUR_PI_IP
```

(Or `ssh xmoke@YOUR_PI_IP` etc. if you use a different user.)

### 4.2 Go to the project and pull latest code

On the Pi:

```bash
cd ~/HealthDairy
```

If your folder is named differently (e.g. `HealthDiary`), use that path instead.

```bash
git fetch origin
git pull origin main
```

Use your real branch name if not `main` (e.g. `git pull origin master`).

### 4.3 Reinstall dependencies (if requirements changed)

```bash
source .venv/bin/activate
pip install -r backend/requirements.txt
```

### 4.4 Restart the app

- **If you start the app manually** (e.g. in an SSH session):  
  Stop it with **Ctrl+C** in that session, then start again:

  ```bash
  cd ~/HealthDairy
  source .venv/bin/activate
  ./start_healthdiary.sh
  ```

  Or directly:

  ```bash
  uvicorn backend.app.main:app --host 0.0.0.0 --port 8000
  ```

- **If the app runs as a systemd service:**

  ```bash
  sudo systemctl restart healthdiary.service
  ```

### 4.5 First-time on Pi: clone the repo and set up

If the project is **not** on the Pi yet:

```bash
cd ~
git clone https://github.com/YOUR_USERNAME/HealthDairy.git HealthDairy
cd HealthDairy
python3 -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements.txt
```

Create `~/HealthDairy/.env` with your QWEN_* variables (same format as on the laptop). Then start the server (e.g. with `uvicorn ... --host 0.0.0.0 --port 8000` or a startup script). See `RASPBERRY_PI_SETUP.md` for full Pi setup (Python, audio, systemd, etc.).

---

## Quick reference: end-to-end flow

| Step | Where | What to do |
|------|--------|------------|
| 1 | Laptop | Develop and test: activate `.venv`, run `uvicorn backend.app.main:app --host 127.0.0.1 --port 8000`, open http://127.0.0.1:8000/demo |
| 2 | Laptop | Push to GitHub: `git add .` → `git commit -m "message"` → `git push origin main` |
| 3 | Laptop | SSH to Pi: `ssh pi@YOUR_PI_IP` |
| 4 | Pi | Update app: `cd ~/HealthDairy` → `git pull origin main` → `pip install -r backend/requirements.txt` (if needed) → restart app (Ctrl+C and rerun, or `sudo systemctl restart healthdiary.service`) |

---

## Where to get more detail

- **Laptop setup and recent changes:** `LAPTOP_SETUP_AND_PROGRESS.md`
- **Pi setup (OS, Python, audio, .env, systemd):** `RASPBERRY_PI_SETUP.md`
- **SSH, copy-paste, file transfer, Git sync:** `LAPTOP_PI_COMMUNICATION.md`

---

## How voice input is interpreted

### 1. What model is used?

- **Symptom voice input & Meal voice input (demo page)**  
  The browser’s **Web Speech API** (`SpeechRecognition` / `webkitSpeechRecognition`) is used. The “model” is whatever the browser uses (e.g. Chrome → Google’s cloud speech). You don’t configure a model; the front end only sets the **language** (`rec.lang` = `zh-CN` or `en-US`) from the Language toggle.

- **Backend transcription** (e.g. visit capture when you use “Transcribe” with an audio file)  
  The app uses **Qwen 2.5 Omni 7B** (`qwen2.5-omni-7b`) via the same DashScope chat/completions endpoint as text chat. Optional fallback: DashScope native ASR with **paraformer-v2** when a public file URL is provided.  
  Env: `QWEN_SPEECH_MODEL` (default `qwen2.5-omni-7b`), `QWEN_ASR_MODEL` (default `paraformer-v2`).

### 2. Mandarin vs English: same model, different prompt?

- **Backend (Qwen Omni):** Yes. The **same** model is used. Only the **system prompt** and the user instruction change:
  - **English mode:** `build_asr_system_prompt(ENGLISH)` → “Transcribe into English only…”
  - **Chinese mode:** `build_asr_system_prompt(CHINESE)` → “转写为简体中文…”
  The `lang` sent from the UI (or the persisted language mode) selects which prompt is used.

- **Browser (Web Speech API):** The same engine is used; you only change `rec.lang` (`en-US` vs `zh-CN`). There is no separate “model” per language.

### 3. Can the model auto-detect the user’s language?

- **Current behavior:** No. The app always uses a **single** language:
  - Demo: `window._langCode` from the Language button → `rec.lang` and `lang` in API calls.
  - Backend: `get_current_language_mode()` or request `lang` → one system prompt (en or zh).

- **Possible in principle:**
  - **Browser:** The Web Speech API does **not** support automatic language detection; you must set `lang`. So auto-detect would require a different client-side approach (e.g. another API).
  - **Backend:** You could change the Qwen Omni prompt to something like “Transcribe in the same language the user spoke” and let the model choose. DashScope’s paraformer also has `language_hints` (a list of candidate languages). SenseVoice has spoken language identification (LID). So auto-detect is **possible** with prompt or API changes, but it is **not implemented** in the current codebase.

### 4. Can Hokkien (Southern Min) be detected?

- **Browser:** Standard Web Speech API typically does **not** support Hokkien; `lang` is usually things like `en-US`, `zh-CN`. Support would be browser-dependent and generally not available.

- **Qwen Omni / DashScope (paraformer, SenseVoice):** Documentation does not list Hokkien/Southern Min explicitly. SenseVoice lists “50+ languages” and strong Chinese support but not this dialect.

- **Research:** Dedicated Hokkien ASR exists (e.g. **MinSpeech** corpus, **DataoceanAI Dolphin** with 22 Chinese dialects including Hokkien, **ChineseTaiwaneseWhisper**). So **Hokkien is possible** only by integrating a different model or API (e.g. Dolphin or a Whisper-based Hokkien model), not with the current Qwen/DashScope pipeline as-is.

### 5. Web Speech API vs product ASR

- **Web Speech API in a real product:** For a shipped product you usually want:
  - **Consistent behaviour** across browsers and devices (Web Speech varies by vendor and locale).
  - **Control over languages** (e.g. Hokkien) and **auto language detection** (Web Speech does not support this).
  - **Predictable SLAs and privacy** (your own backend ASR or a chosen cloud ASR).
  So for an **actual product**, replacing the browser’s Web Speech with a **backend ASR** (or a dedicated client-side SDK that calls your backend) is the right direction.

### 6. One ASR for Chinese + English + Hokkien with auto-detect (implementable)

- **Qwen3-ASR-Flash (DashScope)** fits your stack and requirements:
  - **Languages:** Under the `zh` (中文) option, Alibaba’s docs list **普通话、四川话、闽南语、吴语** — i.e. Mandarin, Sichuanese, **闽南语 (Minnan/Hokkien)**, and Wu. Plus **Cantonese** (`yue`), **English** (`en`), and many others.
  - **Auto language detection:** If you **omit** the `language` field in `asr_options`, the model detects the spoken language. The response includes `annotations[].language` (e.g. `zh`, `en`) so you know what was detected.
  - **Implementation:** You already use DashScope (`QWEN_ENDPOINT`, `QWEN_API_KEY`). The same **compatible-mode** endpoint supports the model `qwen3-asr-flash`: send audio via `input_audio` (URL or base64) and use `extra_body.asr_options` with `enable_itn` and optionally no `language` for auto-detect. So you can add a transcription path that calls **Qwen3-ASR-Flash** instead of (or in addition to) Qwen2.5-Omni for symptom/meal/visit voice, and use the returned `language` for downstream logic (e.g. prompts, TTS).
  - **Docs:** [Alibaba Qwen-ASR API](https://help.aliyun.com/zh/model_studio/qwen-asr-api-reference) (OpenAI-compatible and DashScope sync). Model name: `qwen3-asr-flash`.

- **Other options (if you need offline or a different vendor):**
  - **DataoceanAI Dolphin:** 22 Chinese dialects (including Hokkien), 40 Eastern languages; supports LID but works best when you set `lang_sym`/`region_sym`. Python package `dataoceanai-dolphin`; requires FFmpeg and local/GPU inference.
  - **Whisper (e.g. large-v3):** Auto-detect and many languages; Hokkien is not in the standard set but **ChineseTaiwaneseWhisper** and similar fine-tunes add Taiwanese Hokkien. You’d run Whisper (or a fork) on your backend or via a third-party API.

**Summary:** For a single ASR that supports **Chinese (Mandarin + Hokkien under `zh`), English, and auto-detect**, and that you can plug into this project with minimal change: use **Qwen3-ASR-Flash** on DashScope and omit `language` in `asr_options` for auto-detection.

### 7. Reply language and storage (symptom chat)

- **1. Reply language vs input language**  
  The **assistant’s reply language follows the page language** (the Language toggle), not the language of the voice input. The backend uses **persisted language mode** (`get_current_language_mode()`) when generating follow-up questions and saved-message text. The ASR-detected language (e.g. `zh` or `en` from `/diary/transcribe`) is **not** sent to `/diary/chat/step`, so it does not affect the reply language.

- **2. Mixed language in the same dialog**  
  **All replies in a session use the same language** — the current language mode. The backend does **not** switch reply language per turn based on whether the user just spoke Chinese or English. So if the page is set to English, every follow-up question is in English; if set to Chinese, every follow-up is in Chinese, even if the user alternates languages.

- **3. How reply and chat data are stored**  
  When a symptom entry is saved:
  - **`symptom_raw`**: Concatenation of all **user** messages in that conversation (space-separated). So it can contain mixed languages (e.g. “I have stomach pain 有时候饭后更严重”).
  - **`fields_json`**: Structured fields (e.g. `symptom_label`, `severity`, `timing`) with **English keys**. Values are whatever the NLU/LLM extracted and can be in Chinese or English (e.g. `symptom_label: "腹痛"` or `"abdominal pain"`). No separate “language” field is stored for the entry.
  - **`provenance_json`**: Includes the full **messages** array (user and assistant turns), so the exact text of each question and answer is preserved in whatever language it was in.

  So: storage is **language-agnostic**; the schema uses English keys, and both the raw text and the full conversation are kept so you can later use the stored language(s) for display or analysis.

---

## Troubleshooting

| Issue | What to do |
|--------|------------|
| Laptop: “No module named 'fastapi'” | Activate venv (`.\.venv\Scripts\Activate.ps1`) and run `pip install -r backend\requirements.txt` from project root. |
| Laptop: 503 / “LLM not configured” | Add/fix `.env` in project root with `QWEN_ENDPOINT` and `QWEN_API_KEY`, restart server. |
| “Permission denied” when pushing to GitHub | Set up GitHub auth (SSH key or Personal Access Token). See GitHub docs. |
| Can’t SSH to Pi | Check Pi is on same network, SSH enabled (`sudo raspi-config` → Interface Options → SSH), and correct IP (`hostname -I` on Pi). |
| Pi: “command not found: git” | Install: `sudo apt update && sudo apt install -y git` |
| Pi: after pull, app fails | Run `pip install -r backend/requirements.txt` and ensure `.env` exists under `~/HealthDairy`. |
