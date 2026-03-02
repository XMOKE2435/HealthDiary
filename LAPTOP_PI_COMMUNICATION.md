# Quick Communication Between Laptop and Raspberry Pi

This guide shows you how to quickly send commands and files between your laptop and Raspberry Pi without typing everything manually.

---

## Method 1: SSH from Laptop (Recommended - Fastest)

### Step 1: Find Your Pi's IP Address

On Raspberry Pi:
```bash
hostname -I
```

Write down the IP address (e.g., `192.168.1.100`)

### Step 2: SSH from Laptop

**On Windows (PowerShell or Command Prompt):**
```bash
ssh pi@YOUR_PI_IP
# Example: ssh pi@192.168.1.100
```

**On Mac/Linux:**
```bash
ssh pi@YOUR_PI_IP
```

Enter password when prompted.

### Step 3: Copy-paste between laptop and Pi

Once you're in an SSH session, your **laptop’s keyboard and clipboard** are what the Pi sees:

| What you want to do | How |
|---------------------|-----|
| **Paste lines into the Pi** (e.g. `.env` content, commands) | Copy the text on your laptop (Ctrl+C), then **paste in the SSH terminal** (Ctrl+V in Windows Terminal/PowerShell; **right-click** in PuTTY). The pasted text is sent to the Pi. |
| **Copy output from the Pi** (e.g. a command’s result, file contents) | In the same SSH terminal, **select the text** with the mouse, then copy (Ctrl+C or right-click). That text is now on your **laptop clipboard** — paste it anywhere on the laptop with Ctrl+V. **Short:** Select in SSH terminal → Ctrl+C → paste on laptop with Ctrl+V. |

**Tips:**
- Always **SSH from the laptop** (`ssh pi@YOUR_PI_IP`). Then you’re typing and pasting on the laptop and it all runs on the Pi.
- **Windows:** In **PuTTY**, paste is **right-click**. In **Windows Terminal** or **PowerShell**, use **Ctrl+V** to paste.
- To paste into `nano` on the Pi: paste in the terminal as above; nano will receive the lines. For multiple lines, paste once and they’ll be inserted.

So: open SSH from laptop → paste your lines in the terminal → they run or get typed on the Pi.

---

## Method 2: SSH with Key-Based Authentication (No Password Needed)

This lets you SSH without typing password every time.

### Step 1: Generate SSH Key on Laptop (if you don't have one)

**On Windows:**
```powershell
ssh-keygen -t ed25519 -C "your_email@example.com"
```

Press Enter to accept defaults. It will create keys in `C:\Users\YourUsername\.ssh\`

**On Mac/Linux:**
```bash
ssh-keygen -t ed25519 -C "your_email@example.com"
```

### Step 2: Copy Public Key to Raspberry Pi

**On Windows:**
```powershell
type $env:USERPROFILE\.ssh\id_ed25519.pub | ssh pi@YOUR_PI_IP "mkdir -p ~/.ssh && cat >> ~/.ssh/authorized_keys"
```

**On Mac/Linux:**
```bash
ssh-copy-id pi@YOUR_PI_IP
```

Enter password once, then you won't need it again!

### Step 3: Test SSH (No Password!)

```bash
ssh pi@YOUR_PI_IP
```

Should connect without asking for password!

---

## Method 3: VS Code Remote SSH (Best for Development)

This lets you edit files on Pi directly from your laptop's VS Code!

### Step 1: Install VS Code Remote SSH Extension

1. Open VS Code on your laptop
2. Go to Extensions (Ctrl+Shift+X)
3. Search for "Remote - SSH"
4. Install it

### Step 2: Connect to Raspberry Pi

1. Press F1 (or Ctrl+Shift+P)
2. Type "Remote-SSH: Connect to Host"
3. Enter: `pi@YOUR_PI_IP`
4. Enter password (first time only)

### Step 3: Open Project Folder

Once connected:
1. File → Open Folder
2. Navigate to `/home/pi/HealthDairy`
3. Now you can edit files directly on Pi from your laptop!

**Benefits:**
- Edit files on Pi from laptop
- Run terminal commands
- Use laptop's full keyboard
- Copy/paste easily
- Debug directly

---

## Method 4: File Transfer (SCP/SFTP)

### Copy Files from Laptop to Pi

**On Windows (PowerShell):**
```powershell
scp D:\HealthDairy\file.txt pi@YOUR_PI_IP:/home/pi/HealthDairy/
```

**On Mac/Linux:**
```bash
scp /path/to/file.txt pi@YOUR_PI_IP:/home/pi/HealthDairy/
```

### Copy Files from Pi to Laptop

**On Windows:**
```powershell
scp pi@YOUR_PI_IP:/home/pi/HealthDairy/file.txt D:\HealthDairy\
```

**On Mac/Linux:**
```bash
scp pi@YOUR_PI_IP:/home/pi/HealthDairy/file.txt ~/Downloads/
```

### Copy Entire Folder

**On Windows:**
```powershell
scp -r D:\HealthDairy\backend pi@YOUR_PI_IP:/home/pi/HealthDairy/
```

**On Mac/Linux:**
```bash
scp -r ~/HealthDairy/backend pi@YOUR_PI_IP:/home/pi/HealthDairy/
```

---

## Method 5: Use WinSCP (Windows GUI Tool)

### Step 1: Download WinSCP

Download from: https://winscp.net/

### Step 2: Connect

1. Open WinSCP
2. Enter:
   - Host name: `YOUR_PI_IP`
   - User name: `pi`
   - Password: (your Pi password)
3. Click Login

### Step 3: Drag and Drop Files

- Left side: Your laptop files
- Right side: Raspberry Pi files
- Just drag and drop!

---

## Method 6: Sync Code to Pi via Git (Detailed Steps)

Use this to get the **latest code from your laptop onto the Pi** so the Pi runs the same version as your laptop.

### Prerequisites

- Your project is in a Git repo and you have a **remote** (e.g. GitHub): run `git remote -v` on the laptop and you see something like `origin  https://github.com/youruser/HealthDairy.git`.
- On the Pi you already have the repo cloned (e.g. `~/HealthDairy`). If not, see "First-time: clone on the Pi" below.

### Step 1: On your laptop — commit and push

Open a terminal in your project folder (e.g. `D:\HealthDairy`).

1. **See what changed:** `git status`
2. **Stage files:** `git add .` (or `git add backend/` to stage only backend)
3. **Commit:** `git commit -m "Sync latest changes to Pi"`
4. **Push:** `git push origin main` (use your branch name if different, e.g. `master`)

### Step 2: On the Pi — pull the latest code

SSH into the Pi from the laptop: `ssh xmoke@YOUR_PI_IP` (use your Pi username and IP).

Then on the Pi:

1. **Go to the project folder:** `cd ~/HealthDiary` (or `cd ~/HealthDairy` — use the folder name you cloned)
2. **Pull:** `git fetch origin` then `git pull origin main` (or your branch name)
3. **Reinstall deps if requirements changed:** `source .venv/bin/activate` then `pip install -r backend/requirements.txt`
4. **Restart the app:** stop with Ctrl+C if running manually, then start again; or `sudo systemctl restart healthdiary.service` if using systemd

### First-time: clone on the Pi (if the repo isn't there yet)

On the Pi: `cd ~` then `git clone https://github.com/YOUR_USERNAME/YOUR_REPO.git HealthDiary` (replace with your repo URL and desired folder name). Then `cd HealthDiary`, `python3 -m venv .venv`, `source .venv/bin/activate`, `pip install -r backend/requirements.txt`.

### Summary

| Where   | What to do |
|--------|------------|
| Laptop | `git add .` → `git commit -m "message"` → `git push origin main` |
| Pi     | `cd ~/HealthDiary` → `git pull origin main` → (optional) `pip install -r backend/requirements.txt` → restart app |

---

## Method 7: Shared Clipboard (Advanced)

### Option A: Use SSH X11 Forwarding (Linux/Mac)

```bash
ssh -X pi@YOUR_PI_IP
```

Then you can copy/paste between systems.

### Option B: Use tmux/screen with shared clipboard

Install on Pi:
```bash
sudo apt install xclip
```

Then you can copy/paste between SSH sessions.

---

## Quick Reference Commands

### SSH Commands (Run from Laptop)

```bash
# Connect to Pi
ssh pi@YOUR_PI_IP

# Run single command on Pi (without full SSH session)
ssh pi@YOUR_PI_IP "cd ~/HealthDairy && python3 --version"

# Copy file to Pi
scp file.txt pi@YOUR_PI_IP:/home/pi/

# Copy folder to Pi
scp -r folder pi@YOUR_PI_IP:/home/pi/

# Copy file from Pi
scp pi@YOUR_PI_IP:/home/pi/file.txt ./
```

### VS Code Remote SSH

1. F1 → "Remote-SSH: Connect to Host"
2. Enter: `pi@YOUR_PI_IP`
3. Open folder: `/home/pi/HealthDairy`

---

## Recommended Setup

**For Development:**
1. Set up SSH key authentication (Method 2) - no password needed
2. Use VS Code Remote SSH (Method 3) - edit files directly
3. Use Git (Method 6) - sync changes easily

**For Quick Commands:**
1. SSH from laptop (Method 1) - type commands faster
2. Set up SSH keys (Method 2) - no password prompts

**For File Transfer:**
1. Use Git (Method 6) - best for code
2. Use WinSCP (Method 5) - best for GUI drag-drop
3. Use SCP (Method 4) - best for command line

---

## Example Workflow

**Daily workflow:**

1. **On Laptop:**
   ```bash
   # Edit code in VS Code
   # Test locally
   git add .
   git commit -m "Update"
   git push
   ```

2. **On Pi (via SSH from laptop):**
   ```bash
   ssh pi@YOUR_PI_IP
   cd ~/HealthDairy
   git pull
   source .venv/bin/activate
   uvicorn backend.app.main:app --host 0.0.0.0 --port 8000
   ```

3. **Or use VS Code Remote SSH:**
   - Connect via VS Code
   - Edit files directly
   - Open integrated terminal
   - Run commands there

---

## Troubleshooting

### How to fix Voice Input on the Pi
1. **Open the demo as localhost** (so the browser allows the microphone):  
   On the Pi, in the browser, go to **`http://127.0.0.1:8000/demo`** (not `http://<Pi-IP>:8000/demo`).
2. **If you still get "network" error:** Chromium on the Pi often has this bug. Install Firefox and use that for the demo:
   ```bash
   sudo apt update
   sudo apt install -y firefox-esr
   ```
   Then open **`http://127.0.0.1:8000/demo`** in Firefox and try Voice Input again.
3. **Grant microphone permission** when the browser asks (Allow for this site).
4. **Alternative (no browser speech API):** Use **section 4 (Visit Capture)** in the demo – "Start Recording" or "Upload / Select Audio" – which sends audio to your backend and uses your Qwen API; works in any browser.

### Issue: "Voice capture error: network" (demo voice input on Pi)
**Cause:** The demo's **Voice Input** uses the **browser's built-in speech recognition** (e.g. Chrome's SpeechRecognition API), which sends audio to the **internet** (e.g. Google's servers). It does **not** go to your HealthDiary backend.

**So yes — this is usually a network issue:** the device where the browser is open (Pi or laptop) cannot reach the speech service.

**What to do:**
1. **Check internet on that device:** On the Pi, run `ping -c 3 google.com`. If it fails, fix Wi‑Fi or Ethernet and DNS.
2. **If the browser is on the Pi:** Ensure the Pi has internet (and isn’t behind a firewall that blocks HTTPS to Google). Try opening `https://www.google.com` in the Pi’s browser.
3. **If the browser is on your laptop** but you open `http://<pi-ip>:8000/demo`: the speech recognition still runs in **your laptop’s browser**, so your **laptop** needs internet, not the Pi.
4. **Firewall:** If you use a firewall on the Pi, allow outbound HTTPS (port 443). The voice API does not use your HealthDiary server; it uses the browser vendor’s cloud.

### Issue: "Connection refused"
**Solution**: Make sure SSH is enabled on Pi:
```bash
sudo systemctl status ssh
sudo systemctl enable ssh
```

### Issue: "Permission denied"
**Solution**: Check username (usually `pi`), or try:
```bash
ssh pi@YOUR_PI_IP
```

### Issue: Can't find Pi IP
**Solution**: On Pi, run:
```bash
hostname -I
```

Or check your router's connected devices list.

---

**Best Practice**: Set up SSH key authentication (Method 2) + VS Code Remote SSH (Method 3) for the smoothest workflow!

