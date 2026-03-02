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

## Troubleshooting

| Issue | What to do |
|--------|------------|
| Laptop: “No module named 'fastapi'” | Activate venv (`.\.venv\Scripts\Activate.ps1`) and run `pip install -r backend\requirements.txt` from project root. |
| Laptop: 503 / “LLM not configured” | Add/fix `.env` in project root with `QWEN_ENDPOINT` and `QWEN_API_KEY`, restart server. |
| “Permission denied” when pushing to GitHub | Set up GitHub auth (SSH key or Personal Access Token). See GitHub docs. |
| Can’t SSH to Pi | Check Pi is on same network, SSH enabled (`sudo raspi-config` → Interface Options → SSH), and correct IP (`hostname -I` on Pi). |
| Pi: “command not found: git” | Install: `sudo apt update && sudo apt install -y git` |
| Pi: after pull, app fails | Run `pip install -r backend/requirements.txt` and ensure `.env` exists under `~/HealthDairy`. |
