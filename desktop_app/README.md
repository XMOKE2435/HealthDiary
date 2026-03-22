# HealthDairy Desktop App (Option C – full native UI)

Native desktop application built with **Python + PySide6 (Qt)**. Uses the Pi’s (or your PC’s) **default microphone** and talks to your **existing HealthDairy backend**. The **web app is unchanged** and remains the full reference for testing.

---

## How to start the app

1. **Start the backend** (in one terminal):
   ```powershell
   cd D:\HealthDairy
   .\.venv\Scripts\Activate.ps1
   uvicorn backend.app.main:app --host 127.0.0.1 --port 8000
   ```
2. **Run the desktop app** (in another terminal):
   ```powershell
   cd D:\HealthDairy
   .\.venv\Scripts\Activate.ps1
   pip install -r desktop_app\requirements.txt
   python desktop_app\main.py
   ```
3. In the app, open **Settings** and set **Backend URL** (default `http://127.0.0.1:8000`), **User ID**, and **Language**. Settings are saved automatically and restored next time.

---

## What the desktop app does

- **Settings:** Backend URL, user ID, language (en/zh).
- **Symptom entry:** Chat with the backend (type or voice: **Start recording** (up to **3 s**) and **Stop & transcribe** when done—same idea as the web demo; then the backend transcribes and sends the text as your message).
- **Recommendations:** Fetch and show suggestions.
- **Doctor pack:** Generate pack and show link.
- **Visit capture:** Record → transcribe → get summary (all via backend).

---

## Prerequisites

- **Python 3.9+**
- **Backend running** (e.g. `uvicorn backend.app.main:app --host 0.0.0.0 --port 8000` on the Pi or your laptop)

---

## Run on your laptop (development)

1. **Terminal in project root:**
   ```powershell
   cd D:\HealthDairy
   ```
2. **Create and activate a venv for the desktop app (optional but recommended):**
   ```powershell
   python -m venv desktop_app\.venv
   .\desktop_app\.venv\Scripts\Activate.ps1
   ```
   Or use your existing project venv if you prefer.

3. **Install desktop app dependencies:**
   ```powershell
   pip install -r desktop_app\requirements.txt
   ```
4. **Start the backend** (in another terminal) if not already running:
   ```powershell
   cd D:\HealthDairy
   .\.venv\Scripts\Activate.ps1
   uvicorn backend.app.main:app --host 127.0.0.1 --port 8000
   ```
5. **Run the desktop app:**
   ```powershell
   python desktop_app\main.py
   ```
6. In the app: leave **Backend URL** as `http://127.0.0.1:8000` (or your backend address), set **User ID**, then use the tabs (Symptom entry, Recommendations, Doctor pack, Visit capture).

---

## Run on the Raspberry Pi

1. **SSH to the Pi**, pull latest code:
   ```bash
   cd ~/HealthDairy
   git pull origin main
   ```
2. **Create venv and install deps:**
   ```bash
   python3 -m venv desktop_app/.venv
   source desktop_app/.venv/bin/activate
   pip install -r desktop_app/requirements.txt
   ```
3. **Start the backend** (in another session or in background):
   ```bash
   cd ~/HealthDairy
   source .venv/bin/activate
   uvicorn backend.app.main:app --host 0.0.0.0 --port 8000
   ```
4. **Run the desktop app** (with display connected to the Pi, or over VNC):
   ```bash
   cd ~/HealthDairy
   source desktop_app/.venv/bin/activate
   python desktop_app/main.py
   ```
5. In **Settings**, set **Backend URL** to `http://127.0.0.1:8000` (if backend is on the same Pi). Use the **Record** buttons to use the Pi’s default microphone.

---

## Web app unchanged

- The **web app** at `http://...:8000/demo` is still the full HealthDairy UI for testing (symptom chat, recommendations, doctor pack, visit capture, language, etc.).
- The desktop app is a **second client** to the same backend. You can use both: web for quick testing, desktop for the “real” app on the Pi with native audio.

---

## Troubleshooting

| Issue | What to do |
|--------|------------|
| `No module named 'PySide6'` | Activate the venv and run `pip install -r desktop_app/requirements.txt`. |
| Recording fails / no sound | Set the correct default microphone in system settings (Pi or PC). |
| Connection refused / Error when clicking buttons | Ensure the backend is running and **Backend URL** in Settings matches (e.g. `http://127.0.0.1:8000`). |
| On Pi: app window doesn’t show | Run from a session with a display (monitor or VNC). Use `export DISPLAY=:0` if needed. |
