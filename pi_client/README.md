# HealthDairy Pi Client

Thin client for **Raspberry Pi** that records from the **Pi’s default microphone** and sends audio to your HealthDairy backend for transcription. No browser or cloud speech API needed.

The **web app is unchanged** and still has all the same features for testing; this client is an extra way to use the backend from the Pi with local audio.

---

## What it does

1. Records audio from the default sound input (e.g. USB mic or Pi’s mic).
2. Sends the recording to your backend `POST /visit/transcribe`.
3. Prints the transcript returned by the backend.

You can then use that transcript in the web app (e.g. paste into symptom chat) or in a future script that calls the diary/chat API.

---

## Prerequisites on the Pi

- **Python 3** (e.g. 3.9+)
- **Backend running** on the same Pi or another machine (e.g. `uvicorn backend.app.main:app --host 0.0.0.0 --port 8000`)
- **Microphone** set as default and working (test with `arecord` or system settings)

---

## Step 1: Open a terminal on the Pi

SSH from your laptop:

```bash
ssh xmoke@YOUR_PI_IP
```

Or use the Pi’s desktop terminal.

---

## Step 2: Go to the project and create a virtualenv for the client

Use the same repo you use for the backend (e.g. after `git pull`). The client lives in the `pi_client` folder at the project root.

```bash
cd ~/HealthDairy
# Or:  cd ~/HealthDiary   if your folder is named that way
```

Create a **separate** virtualenv for the Pi client (so it doesn’t mix with the backend’s venv):

```bash
python3 -m venv pi_client/.venv
source pi_client/.venv/bin/activate
```

Your prompt should show `(.venv)` (you’re inside `pi_client`’s venv). Install the client’s dependencies:

```bash
pip install -r pi_client/requirements.txt
```

---

## Step 3: Make sure the backend is running

The client only **calls** the backend; it does not start it.

- **Same Pi:** In another terminal (or before you run the client), start the backend from the project root, e.g.:

  ```bash
  cd ~/HealthDairy
  source .venv/bin/activate
  uvicorn backend.app.main:app --host 0.0.0.0 --port 8000
  ```

  Leave this running. The client will use `http://127.0.0.1:8000` by default.

- **Backend on another machine:** Start the backend there, then use `--backend http://THAT_IP:8000` when you run the client (see Step 5).

---

## Step 4: (Optional) Set default microphone

If you have more than one input device, set the one you want as default (e.g. in Raspberry Pi OS sound settings, or with `pulseaudio`/`alsamixer`). The client uses whatever is the **default input** for the system; it does not list or choose devices.

---

## Step 5: Run the client

From the **project root** on the Pi, with the **client’s** venv activated:

```bash
cd ~/HealthDairy
source pi_client/.venv/bin/activate
python pi_client/record_and_transcribe.py
```

This will:

- Record for **5 seconds** (default) from the default mic.
- Send the audio to `http://127.0.0.1:8000/visit/transcribe`.
- Print the transcript.

**Options:**

- **Duration (seconds):**  
  `python pi_client/record_and_transcribe.py --seconds 8`
- **Backend URL** (if backend is on another machine):  
  `python pi_client/record_and_transcribe.py --backend http://192.168.1.100:8000`
- **User and language:**  
  `python pi_client/record_and_transcribe.py --user demo-user-1 --lang zh`

Full example:

```bash
python pi_client/record_and_transcribe.py --backend http://127.0.0.1:8000 --seconds 6 --user pi-user --lang en
```

---

## Step 6: Use the transcript

- The script prints the transcript to the terminal. You can copy it and paste it into the **web app** (e.g. symptom chat) in the browser.
- The **web app** (including all current features) is unchanged: open `http://YOUR_PI_IP:8000/demo` and use it as before. The Pi client is only an extra way to get a transcript using the Pi’s default audio.

---

## Troubleshooting

| Problem | What to do |
|--------|------------|
| `No module named 'sounddevice'` | Activate the **client** venv and run `pip install -r pi_client/requirements.txt` again. |
| `Recording error: ...` or no sound | Check default mic (e.g. `arecord -l`, system sound settings). Try a different mic or set it as default. |
| `Request error: Connection refused` | Backend is not running or wrong URL. Start backend and/or use `--backend http://IP:8000`. |
| `502` or `Transcription failed` | Backend is up but transcription failed (e.g. LLM/ASR config). Check backend logs and `.env` (QWEN_* etc.) on the machine that runs the backend. |
| Transcript empty | Speak clearly and long enough; try `--seconds 8`. Check backend logs for ASR errors. |

---

## Summary

- **Pi client:** `pi_client/` – record from default mic → POST to backend → print transcript.
- **Web app:** Unchanged; full features at `http://PI_IP:8000/demo` for testing.
- **Flow:** Run backend → run `record_and_transcribe.py` on the Pi → use transcript in the web app or later in an extended client.
