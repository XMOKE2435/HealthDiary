#!/usr/bin/env python3
"""
Pi client: record from default microphone and send to HealthDairy backend for transcription.
Uses the Pi's default audio device (no browser speech API). Backend must be running.
"""
import argparse
import io
import sys
import tempfile
import wave

import numpy as np
import requests
import sounddevice as sd


SAMPLE_RATE = 16000
CHANNELS = 1
DTYPE = np.int16
DEFAULT_BACKEND = "http://127.0.0.1:8000"


def record_seconds(seconds: float) -> np.ndarray:
    """Record from default input device. Returns mono int16 array."""
    duration_sec = max(0.5, float(seconds))
    print(f"Recording for {duration_sec:.1f} seconds... (speak now)")
    data = sd.rec(
        int(duration_sec * SAMPLE_RATE),
        samplerate=SAMPLE_RATE,
        channels=CHANNELS,
        dtype=DTYPE,
    )
    sd.wait()
    print("Recording done.")
    return data.squeeze()


def wav_bytes(samples: np.ndarray) -> bytes:
    """Convert int16 mono samples to WAV file bytes."""
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(CHANNELS)
        w.setsampwidth(2)  # 16-bit
        w.setframerate(SAMPLE_RATE)
        w.writeframes(samples.tobytes())
    return buf.getvalue()


def transcribe(
    backend_url: str,
    audio_bytes: bytes,
    user_id: str = "pi-user",
    lang: str = "en",
) -> dict:
    """POST audio to backend /visit/transcribe. Returns JSON response."""
    url = f"{backend_url.rstrip('/')}/visit/transcribe"
    files = {"audio": ("audio.wav", audio_bytes, "audio/wav")}
    data = {"user_id": user_id, "lang": lang}
    resp = requests.post(url, files=files, data=data, timeout=60)
    resp.raise_for_status()
    return resp.json()


def main():
    ap = argparse.ArgumentParser(description="Record from mic and transcribe via HealthDairy backend")
    ap.add_argument("--backend", default=DEFAULT_BACKEND, help=f"Backend base URL (default: {DEFAULT_BACKEND})")
    ap.add_argument("--seconds", "-s", type=float, default=5.0, help="Recording duration in seconds")
    ap.add_argument("--user", "-u", default="pi-user", help="user_id for the backend")
    ap.add_argument("--lang", "-l", choices=("en", "zh"), default="en", help="Language for transcription")
    args = ap.parse_args()

    try:
        samples = record_seconds(args.seconds)
    except Exception as e:
        print(f"Recording error: {e}", file=sys.stderr)
        sys.exit(1)

    if samples.size < SAMPLE_RATE // 2:
        print("Audio too short. Say something longer.", file=sys.stderr)
        sys.exit(1)

    wav = wav_bytes(samples)
    print(f"Sending {len(wav)} bytes to {args.backend}...")
    try:
        out = transcribe(args.backend, wav, user_id=args.user, lang=args.lang)
    except requests.RequestException as e:
        print(f"Request error: {e}", file=sys.stderr)
        if hasattr(e, "response") and e.response is not None:
            try:
                print(e.response.text, file=sys.stderr)
            except Exception:
                pass
        sys.exit(1)

    transcript = out.get("transcript") or out.get("text") or ""
    print("\n--- Transcript ---")
    print(transcript if transcript else "(no transcript)")
    print("------------------")
    return 0


if __name__ == "__main__":
    sys.exit(main())
