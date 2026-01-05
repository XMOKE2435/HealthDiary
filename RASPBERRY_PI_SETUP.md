# Raspberry Pi Setup Guide for HealthDiary

This guide will walk you through setting up your HealthDiary application on a Raspberry Pi from scratch, including audio configuration for microphones and speakers.

---

## Prerequisites

- Raspberry Pi (3B+ or newer recommended, 4B+ preferred for better performance)
- MicroSD card (16GB minimum, 32GB+ recommended, Class 10 or better)
- Microphone(s) connected (USB or 3.5mm jack)
- Speaker(s) connected (USB, HDMI, 3.5mm jack, or Bluetooth)
- Power supply for Raspberry Pi
- Ethernet cable or WiFi connection
- Access to your computer to transfer files (USB drive, SCP, or Git)

---

## Part 1: Initial Raspberry Pi OS Setup

### Step 1.1: Flash Raspberry Pi OS

1. **Download Raspberry Pi Imager** from https://www.raspberrypi.com/software/
   - Available for Windows, macOS, and Linux

2. **Insert your microSD card** into your computer

3. **Open Raspberry Pi Imager** and:
   - Click "Choose OS" → Select "Raspberry Pi OS (64-bit)" (recommended) or "Raspberry Pi OS (Legacy)" (32-bit)
   - Click "Choose Storage" → Select your microSD card
   - Click the gear icon (⚙️) to configure:
     - **Enable SSH**: Check this box
     - **Set username and password**: Choose a secure password
     - **Configure WiFi** (if using WiFi): Enter your network SSID and password
     - **Set locale settings**: Timezone, keyboard layout, etc.
   - Click "Save" then "Write"

4. **Wait for the write to complete**, then safely eject the microSD card

### Step 1.2: First Boot and Initial Setup

1. **Insert the microSD card** into your Raspberry Pi

2. **Connect your peripherals**:
   - Monitor (via HDMI)
   - Keyboard and mouse (USB)
   - Ethernet cable (if not using WiFi)
   - Power supply (connect last)

3. **Power on the Raspberry Pi**

4. **If using GUI**: Complete the initial setup wizard
   - Update system if prompted
   - Set timezone, keyboard layout, etc.

5. **Open Terminal** (or SSH from your computer if enabled)

6. **Update the system**:
   ```bash
   sudo apt update
   sudo apt upgrade -y
   sudo reboot
   ```

---

## Part 2: System Configuration

### Step 2.1: Enable Required Interfaces

1. **Run raspi-config**:
   ```bash
   sudo raspi-config
   ```

2. **Configure settings**:
   - **Interface Options → SSH**: Enable if not already enabled
   - **Interface Options → I2C**: Enable (may be needed for some audio devices)
   - **Interface Options → SPI**: Enable if needed
   - **System Options → Boot / Auto Login**: Choose "Console Autologin" (optional, for headless setup)
   - **Localisation Options**: Set locale, timezone, keyboard if needed
   - Select "Finish" and reboot when prompted

3. **Enable I2S Interface** (Required for ICS-43434 and MAX98357A):
   
   **Note**: On newer Raspberry Pi OS versions (Bullseye and later), the config file is at `/boot/firmware/config.txt`. On older versions, it's at `/boot/config.txt`. Check which one exists:
   ```bash
   ls -la /boot/firmware/config.txt /boot/config.txt 2>/dev/null
   ```
   
   Edit the config file (use the one that exists):
   ```bash
   # Try newer location first
   sudo nano /boot/firmware/config.txt
   # OR if that doesn't exist, use:
   # sudo nano /boot/config.txt
   ```
   
   Add these lines at the end of the file:
   ```
   # Enable I2S
   dtparam=i2s=on
   dtoverlay=i2s-mmap
   ```
   
   Save and exit (Ctrl+X, then Y, then Enter), then reboot:
   ```bash
   sudo reboot
   ```
   
   **Note**: After enabling I2S and rebooting, your ICS-43434 and MAX98357A should appear in `arecord -l` and `aplay -l` (if properly wired).
   
   **If devices don't appear after reboot**, see `I2S_DEBUG_GUIDE.md` for comprehensive debugging steps.

### Step 2.2: Install System Dependencies

**Option 1: Multi-line format (easier to read)**
```bash
sudo apt update
sudo apt install -y \
    python3 \
    python3-pip \
    python3-venv \
    git \
    build-essential \
    portaudio19-dev \
    python3-dev \
    alsa-utils \
    pulseaudio \
    pulseaudio-utils \
    sox \
    libasound2-dev \
    ffmpeg
```

**Option 2: Single-line format (easier to type manually)**
```bash
sudo apt update
sudo apt install -y python3 python3-pip python3-venv git build-essential portaudio19-dev python3-dev alsa-utils pulseaudio pulseaudio-utils sox libasound2-dev ffmpeg
```

**Note**: For the multi-line version, make sure to include the backslashes (`\`) at the end of each line (except the last). The backslash tells bash to continue reading the command on the next line.

**Explanation**:
- `python3`, `python3-pip`, `python3-venv`: Python runtime and package management
- `git`: For cloning repositories (if using Git)
- `build-essential`: Compilation tools for Python packages
- `portaudio19-dev`, `libasound2-dev`: Audio library development files
- `alsa-utils`: ALSA audio system utilities
- `pulseaudio`, `pulseaudio-utils`: PulseAudio audio server
- `sox`: Audio processing utilities
- `ffmpeg`: Audio/video codec support

### Step 2.3: Verify Python Version

```bash
python3 --version
# Should be Python 3.9 or higher (Raspberry Pi OS usually comes with 3.9+)
```

---

## Part 3: Audio Setup

### Step 3.1: List Available Audio Devices

**Check input devices (microphones)**:
```bash
arecord -l
# Lists all recording devices
```

**Check output devices (speakers)**:
```bash
aplay -l
# Lists all playback devices
```

**Check PulseAudio devices**:
```bash
pulseaudio --check -v
pactl list short sources  # Input devices
pactl list short sinks    # Output devices
```

### Step 3.2: Test Microphone

**Record a test file** (5 seconds):
```bash
arecord -D plughw:0,0 -f cd -t wav test_recording.wav
# Press Ctrl+C after a few seconds
# If card 0,0 doesn't work, try: arecord -l to find your device, then use -D plughw:1,0 (or appropriate card,device)
```

**Play back the recording**:
```bash
aplay test_recording.wav
```

**Alternative using PulseAudio**:
```bash
parecord --file-format=wav test_pulse.wav
# Press Ctrl+C after a few seconds
paplay test_pulse.wav
```

**Check recording levels**:
```bash
alsamixer
# Press F4 to switch to capture devices
# Use arrow keys to adjust volume
# Press Esc to exit
```

### Step 3.3: Test Speaker

**Play a test tone**:
```bash
speaker-test -t wav -c 2
# Press Ctrl+C to stop
```

**Or test with a WAV file**:
```bash
aplay /usr/share/sounds/alsa/Front_Left.wav
```

**Adjust speaker volume**:
```bash
alsamixer
# Press F3 for playback devices
# Use arrow keys to adjust volume
# Press Esc to exit
```

**Or use amixer**:
```bash
amixer set Master 80%    # Set master volume to 80%
amixer set PCM 80%       # Set PCM volume to 80%
```

### Step 3.4: Set Default Audio Devices (Optional)

If you have multiple audio devices and want to set defaults:

**Edit ALSA configuration** (for ALSA-level defaults):
```bash
sudo nano /etc/asound.conf
```

Add (adjust card/device numbers based on `aplay -l`):
```
pcm.!default {
    type hw
    card 0
    device 0
}

ctl.!default {
    type hw
    card 0
}
```

**For PulseAudio**, set default sink/source:
```bash
# List devices
pactl list short sinks
pactl list short sources

# Set default sink (speaker)
pactl set-default-sink <sink_name_or_index>

# Set default source (microphone)
pactl set-default-source <source_name_or_index>
```

### Step 3.5: Verify Audio Persistence

Reboot and test again to ensure settings persist:
```bash
sudo reboot
# After reboot, test microphone and speaker again
```

---

## Part 4: Transfer Your HealthDiary Code

### Option A: Using Git (Recommended)

1. **Install Git** (if not already installed):
   ```bash
   sudo apt install -y git
   ```

2. **Clone your repository**:
   ```bash
   cd ~
   git clone <your-repository-url> HealthDairy
   # OR if using GitHub with SSH:
   # git clone git@github.com:yourusername/HealthDairy.git
   ```

### Option B: Using USB Drive

1. **Insert USB drive** into your computer, copy the entire `HealthDairy` folder

2. **Insert USB drive** into Raspberry Pi

3. **Mount and copy**:
   ```bash
   # Find USB drive (usually /media/pi/DRIVE_NAME or /dev/sda1)
   lsblk
   
   # If not auto-mounted:
   sudo mkdir -p /mnt/usb
   sudo mount /dev/sda1 /mnt/usb  # Adjust /dev/sda1 as needed
   
   # Copy files
   cp -r /mnt/usb/HealthDairy ~/
   
   # Unmount
   sudo umount /mnt/usb
   ```

### Option C: Using SCP (from your computer)

**From your Windows/Mac/Linux computer**:
```bash
scp -r D:\HealthDairy pi@<raspberry-pi-ip>:/home/pi/
# Or use WinSCP (Windows) or FileZilla (cross-platform) GUI tools
```

**Find your Raspberry Pi's IP address**:
```bash
# On Raspberry Pi, run:
hostname -I
# Or
ip addr show
```

---

## Part 5: Python Environment Setup

### Step 5.1: Create Virtual Environment

```bash
cd ~/HealthDairy
python3 -m venv .venv
```

### Step 5.2: Activate Virtual Environment

```bash
source .venv/bin/activate
# Your prompt should now show (.venv)
```

### Step 5.3: Upgrade pip

```bash
pip install --upgrade pip setuptools wheel
```

### Step 5.4: Install Dependencies

```bash
pip install -r backend/requirements.txt
```

**This installs**:
- FastAPI
- Uvicorn (ASGI server)
- Pydantic
- HTTPX (HTTP client)
- SQLAlchemy (database ORM)
- python-multipart (file uploads)

### Step 5.5: Verify Installation

```bash
python3 -c "import fastapi, uvicorn, sqlalchemy; print('All packages installed successfully!')"
```

---

## Part 6: Environment Configuration

### Step 6.1: Create Environment File

```bash
cd ~/HealthDairy
nano .env
```

**Add your configuration** (adjust values as needed):
```bash
# Qwen LLM Configuration (Required for transcription and NLU features)
QWEN_ENDPOINT=https://dashscope-intl.aliyuncs.com/compatible-mode/v1/chat/completions
QWEN_API_KEY=your_api_key_here
QWEN_MODEL=qwen2.5-7b-instruct
QWEN_SPEECH_MODEL=qwen2.5-omni-7b

# Optional: Custom ports or settings
# PORT=8000
```

**Save and exit** (Ctrl+X, then Y, then Enter)

### Step 6.2: Create Startup Script

Create a shell script to load environment variables and start the server:

```bash
nano ~/HealthDairy/start_healthdiary.sh
```

**Add the following**:
```bash
#!/bin/bash

# Navigate to project directory
cd ~/HealthDairy

# Activate virtual environment
source .venv/bin/activate

# Load environment variables (if using .env file, install python-dotenv first)
# pip install python-dotenv  # Uncomment if using .env file
# export $(cat .env | xargs)  # Uncomment if using .env file

# Or set environment variables directly:
export QWEN_ENDPOINT="https://dashscope-intl.aliyuncs.com/compatible-mode/v1/chat/completions"
export QWEN_API_KEY="your_api_key_here"
export QWEN_MODEL="qwen2.5-7b-instruct"
export QWEN_SPEECH_MODEL="qwen2.5-omni-7b"

# Start the server
uvicorn backend.app.main:app --host 0.0.0.0 --port 8000
```

**Make it executable**:
```bash
chmod +x ~/HealthDairy/start_healthdiary.sh
```

---

## Part 7: Database Setup

The application uses SQLite, which will be created automatically. However, you should create the data directory:

```bash
mkdir -p ~/HealthDairy/backend/app/data
# The database will be created automatically on first run
```

---

## Part 8: Testing the Installation

### Step 8.1: Start the Server Manually

```bash
cd ~/HealthDairy
source .venv/bin/activate
export QWEN_ENDPOINT="your_endpoint"
export QWEN_API_KEY="your_key"
uvicorn backend.app.main:app --host 0.0.0.0 --port 8000
```

**You should see output like**:
```
INFO:     Started server process [xxxxx]
INFO:     Waiting for application startup.
INFO:     Application startup complete.
INFO:     Uvicorn running on http://0.0.0.0:8000 (Press CTRL+C to quit)
```

### Step 8.2: Test the API

**From another computer on the same network** (or on the Pi itself):
```bash
# Test health endpoint
curl http://<raspberry-pi-ip>:8000/healthz
# Should return: {"ok":true}

# Test demo UI (if available)
# Open browser: http://<raspberry-pi-ip>:8000/demo
```

**Find your Raspberry Pi's IP address**:
```bash
hostname -I
```

### Step 8.3: Test Audio Endpoints

**Record a test audio file** (if you need to test transcription):
```bash
# Record 5 seconds
arecord -f cd -t wav test_audio.wav
# Press Ctrl+C after recording
```

**Test transcription endpoint** (from another terminal or computer):
```bash
curl -X POST "http://<raspberry-pi-ip>:8000/visit/transcribe" \
  -F "user_id=test-user" \
  -F "lang=en" \
  -F "audio=@test_audio.wav"
```

---

## Part 9: Running as a System Service (Auto-Start on Boot)

### Step 9.1: Create Systemd Service File

```bash
sudo nano /etc/systemd/system/healthdiary.service
```

**Add the following** (adjust paths and environment variables as needed):
```ini
[Unit]
Description=HealthDiary FastAPI Application
After=network.target sound.target

[Service]
Type=simple
User=pi
WorkingDirectory=/home/pi/HealthDairy
Environment="PATH=/home/pi/HealthDairy/.venv/bin:/usr/local/bin:/usr/bin:/bin"
Environment="QWEN_ENDPOINT=https://dashscope-intl.aliyuncs.com/compatible-mode/v1/chat/completions"
Environment="QWEN_API_KEY=your_api_key_here"
Environment="QWEN_MODEL=qwen2.5-7b-instruct"
Environment="QWEN_SPEECH_MODEL=qwen2.5-omni-7b"
ExecStart=/home/pi/HealthDairy/.venv/bin/uvicorn backend.app.main:app --host 0.0.0.0 --port 8000
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

**Save and exit** (Ctrl+X, Y, Enter)

### Step 9.2: Enable and Start the Service

```bash
# Reload systemd to recognize the new service
sudo systemctl daemon-reload

# Enable the service to start on boot
sudo systemctl enable healthdiary.service

# Start the service now
sudo systemctl start healthdiary.service

# Check status
sudo systemctl status healthdiary.service
```

### Step 9.3: View Logs

```bash
# View logs
sudo journalctl -u healthdiary.service -f

# View last 100 lines
sudo journalctl -u healthdiary.service -n 100

# View logs since boot
sudo journalctl -u healthdiary.service -b
```

### Step 9.4: Service Management Commands

```bash
# Stop the service
sudo systemctl stop healthdiary.service

# Start the service
sudo systemctl start healthdiary.service

# Restart the service
sudo systemctl restart healthdiary.service

# Disable auto-start on boot
sudo systemctl disable healthdiary.service

# Check if service is enabled
sudo systemctl is-enabled healthdiary.service
```

---

## Part 10: Additional Configuration

### Step 10.1: Firewall Configuration (if using UFW)

If you have a firewall enabled:

```bash
# Allow port 8000
sudo ufw allow 8000/tcp

# Check status
sudo ufw status
```

### Step 10.2: Static IP Address (Optional)

To set a static IP address for easier access:

```bash
sudo nano /etc/dhcpcd.conf
```

Add at the end (adjust for your network):
```
interface eth0  # or wlan0 for WiFi
static ip_address=192.168.1.100/24
static routers=192.168.1.1
static domain_name_servers=192.168.1.1 8.8.8.8
```

**Reboot**:
```bash
sudo reboot
```

### Step 10.3: Audio Device Permissions

If you encounter permission issues with audio devices:

```bash
# Add your user to audio group (usually already done)
sudo usermod -a -G audio $USER

# You may need to logout and login again for this to take effect
```

---

## Part 11: Troubleshooting

### Audio Issues

**Microphone not working**:
```bash
# Check if microphone is detected
arecord -l

# Test with different device
arecord -D plughw:1,0 -f cd test.wav  # Try different card numbers

# Check ALSA configuration
cat /proc/asound/cards

# Restart PulseAudio
pulseaudio -k
pulseaudio --start
```

**Speaker not working**:
```bash
# Check if speaker is detected
aplay -l

# Test audio output
speaker-test -t wav

# Check volume
alsamixer

# Restart audio services
sudo systemctl restart alsa-state
```

### Python/Package Issues

**Virtual environment not activating**:
```bash
# Recreate virtual environment
cd ~/HealthDairy
rm -rf .venv
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r backend/requirements.txt
```

**Import errors**:
```bash
# Ensure virtual environment is activated
source .venv/bin/activate

# Reinstall packages
pip install --force-reinstall -r backend/requirements.txt
```

### Server Issues

**Port already in use**:
```bash
# Find process using port 8000
sudo lsof -i :8000
# or
sudo netstat -tulpn | grep 8000

# Kill the process (replace PID with actual process ID)
sudo kill -9 <PID>

# Or use a different port
uvicorn backend.app.main:app --host 0.0.0.0 --port 8001
```

**Cannot connect to server from other devices**:
- Check firewall: `sudo ufw status`
- Verify server is listening on 0.0.0.0: `netstat -tulpn | grep 8000`
- Check Raspberry Pi's IP address: `hostname -I`
- Test from Raspberry Pi itself: `curl http://localhost:8000/healthz`

### Service Issues

**Service fails to start**:
```bash
# Check logs
sudo journalctl -u healthdiary.service -n 50

# Check service file syntax
sudo systemd-analyze verify /etc/systemd/system/healthdiary.service

# Test manually
cd ~/HealthDairy
source .venv/bin/activate
uvicorn backend.app.main:app --host 0.0.0.0 --port 8000
```

---

## Part 12: Security Recommendations

1. **Change default password**: Use `passwd` to change the default Raspberry Pi password

2. **Use SSH keys instead of passwords**:
   ```bash
   # On your computer, generate SSH key pair
   ssh-keygen -t ed25519
   
   # Copy public key to Raspberry Pi
   ssh-copy-id pi@<raspberry-pi-ip>
   ```

3. **Disable password authentication in SSH** (after setting up keys):
   ```bash
   sudo nano /etc/ssh/sshd_config
   # Set: PasswordAuthentication no
   sudo systemctl restart ssh
   ```

4. **Keep system updated**:
   ```bash
   sudo apt update && sudo apt upgrade -y
   ```

5. **Use environment variables securely**: Don't commit `.env` files to Git. Consider using a secrets manager for production.

6. **Firewall**: Enable UFW and only allow necessary ports:
   ```bash
   sudo ufw enable
   sudo ufw allow 22/tcp  # SSH
   sudo ufw allow 8000/tcp  # HealthDiary API
   ```

---

## Quick Reference Commands

```bash
# Start server manually
cd ~/HealthDairy && source .venv/bin/activate && uvicorn backend.app.main:app --host 0.0.0.0 --port 8000

# Check service status
sudo systemctl status healthdiary.service

# View service logs
sudo journalctl -u healthdiary.service -f

# Restart service
sudo systemctl restart healthdiary.service

# Test audio input
arecord -f cd -t wav test.wav

# Test audio output
aplay test.wav

# Check IP address
hostname -I

# Test API health
curl http://localhost:8000/healthz
```

---

## Next Steps

1. **Configure your frontend/client** to point to `http://<raspberry-pi-ip>:8000`

2. **Test all endpoints** from your client application

3. **Set up backups** for the database:
   ```bash
   # Simple backup script
   cp ~/HealthDairy/backend/app/data/healthdiary.db ~/backups/healthdiary_$(date +%Y%m%d).db
   ```

4. **Monitor resource usage**:
   ```bash
   # CPU and memory
   top
   # or
   htop  # (install with: sudo apt install htop)
   
   # Disk usage
   df -h
   ```

5. **Consider adding a reverse proxy** (nginx) if you want HTTPS or multiple services

---

## Support

If you encounter issues not covered in this guide:
1. Check the application logs: `sudo journalctl -u healthdiary.service`
2. Check system logs: `dmesg | tail -50`
3. Verify all dependencies are installed: `pip list`
4. Test audio independently before testing the application

---

**Last Updated**: 2025-01-27
**Tested on**: Raspberry Pi OS (64-bit), Python 3.11

