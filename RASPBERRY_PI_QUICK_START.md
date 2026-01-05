# Raspberry Pi Quick Start Guide

## One-Time Setup (First Time Only)

1. **Flash Raspberry Pi OS** using Raspberry Pi Imager
   - Enable SSH
   - Set username/password
   - Configure WiFi (if using)

2. **Transfer HealthDairy folder** to Raspberry Pi (Git, USB, or SCP)

3. **Run setup script**:
   ```bash
   cd ~/HealthDairy
   chmod +x setup_raspberry_pi.sh
   ./setup_raspberry_pi.sh
   ```

4. **Configure API keys**:
   ```bash
   nano .env
   # Add your QWEN_API_KEY
   ```

5. **Test audio**:
   ```bash
   arecord -f cd -t wav test.wav    # Record
   aplay test.wav                    # Play back
   ```

## Starting the Server

**Option 1: Manual start**
```bash
cd ~/HealthDairy
source .venv/bin/activate
uvicorn backend.app.main:app --host 0.0.0.0 --port 8000
```

**Option 2: Using startup script**
```bash
cd ~/HealthDairy
./start_healthdiary.sh
```

**Option 3: As system service** (auto-start on boot)
```bash
# See RASPBERRY_PI_SETUP.md Part 9 for detailed instructions
sudo systemctl start healthdiary.service
sudo systemctl enable healthdiary.service  # Enable on boot
```

## Testing

**Health check:**
```bash
curl http://localhost:8000/healthz
```

**From another device:**
```bash
curl http://<raspberry-pi-ip>:8000/healthz
```

**Find IP address:**
```bash
hostname -I
```

## Common Commands

**Check service status:**
```bash
sudo systemctl status healthdiary.service
```

**View logs:**
```bash
sudo journalctl -u healthdiary.service -f
```

**Restart service:**
```bash
sudo systemctl restart healthdiary.service
```

**Check audio devices:**
```bash
arecord -l    # Input devices
aplay -l      # Output devices
```

**Adjust volume:**
```bash
alsamixer     # Interactive mixer
amixer set Master 80%  # Set to 80%
```

## Troubleshooting

**Server won't start:**
- Check logs: `sudo journalctl -u healthdiary.service -n 50`
- Verify virtual environment: `source .venv/bin/activate && python3 -c "import fastapi"`
- Check port: `sudo lsof -i :8000`

**Audio not working:**
- Test devices: `arecord -l` and `aplay -l`
- Check volume: `alsamixer`
- Restart audio: `pulseaudio -k && pulseaudio --start`

**Can't connect from other devices:**
- Check firewall: `sudo ufw status`
- Verify server is running: `curl http://localhost:8000/healthz`
- Check IP address: `hostname -I`

---

**For detailed instructions, see: RASPBERRY_PI_SETUP.md**



