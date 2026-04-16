#!/usr/bin/env python3
"""HealthDairy desktop app – native UI (PySide6). Uses backend for all features."""
import io
import os
import queue
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import wave
from pathlib import Path
from datetime import date, datetime, timezone
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

import numpy as np
import pyttsx3
import sounddevice as sd
from PySide6.QtCore import QObject, QSettings, QThread, QTime, QTimer, Signal
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QFileDialog,
    QAbstractSpinBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QTabWidget,
    QTimeEdit,
    QVBoxLayout,
    QWidget,
)

from api import BackendClient
from companion_pool import load_question_pool, pick_question


def _infer_lang_from_text(text: str) -> str:
    t = (text or "").strip()
    if not t:
        return "en"
    cjk_count = sum(1 for ch in t if "\u4e00" <= ch <= "\u9fff")
    latin_count = sum(1 for ch in t if ("A" <= ch <= "Z") or ("a" <= ch <= "z"))
    if cjk_count > latin_count:
        return "zh"
    return "en"


def load_desktop_tts_env() -> None:
    """Load KEY=value pairs into os.environ so Pi touch terminals don't need ~/.bashrc.

    Search order:
    1) HEALTHDAIRY_TTS_ENV_FILE (explicit path)
    2) <repo>/desktop_app/tts.env
    3) ~/.config/healthdiary/tts.env

    Later files do not override keys already set in the process environment.
    """
    paths: List[Path] = []
    custom = (os.environ.get("HEALTHDAIRY_TTS_ENV_FILE") or "").strip()
    if custom:
        paths.append(Path(custom))
    here = Path(__file__).resolve().parent
    paths.append(here / "tts.env")
    cfg_home = Path.home() / ".config" / "healthdiary" / "tts.env"
    paths.append(cfg_home)

    for p in paths:
        if not p.is_file():
            continue
        try:
            for raw in p.read_text(encoding="utf-8", errors="replace").splitlines():
                line = raw.strip()
                if not line or line.startswith("#"):
                    continue
                if "=" not in line:
                    continue
                k, v = line.split("=", 1)
                k, v = k.strip(), v.strip().strip("'\"")
                if not k or k in os.environ:
                    continue
                os.environ[k] = v
            print(f"[TTS] Loaded env from {p}", flush=True)
        except OSError as e:
            print(f"[TTS] Could not read {p}: {e}", flush=True)


class TtsWorker:
    """TTS on a background thread.

    - **Windows:** ``pyttsx3`` (SAPI) with COM init + fresh engine per phrase.
    - **Linux / Pi:** Prefer **Piper** (offline neural TTS) when model path is configured,
      then **edge-tts** (Microsoft neural voices; needs network + ``mpg123`` or ``ffmpeg`` for
      playback), then **eSpeak-NG** piped to **aplay** (see ``_linux_playback_device``), then
      ``spd-say``, then ``pyttsx3``.
      Set ``HEALTHDAIRY_TTS_BACKEND`` to one of ``piper|edge_tts|espeak|spd_say|pyttsx3`` to force
      a backend. GUI launches often have a minimal ``PATH``; we also check ``/usr/bin/...`` directly.
    """

    _STOP = "__tts_stop__"
    _SHUTDOWN = None  # sentinel to end worker loop

    def __init__(self) -> None:
        self._q: "queue.Queue[Any]" = queue.Queue()
        self._thread: Optional[threading.Thread] = None
        self._started = threading.Event()
        self._init_ok = False
        self._backend = "none"  # "pyttsx3" | "piper" | "edge_tts" | "espeak" | "spd_say"
        self._linux_tts_bin: Optional[str] = None
        self._linux_espeak_fallback: Optional[Tuple[str, str]] = None
        self._piper_model_en = os.environ.get("HEALTHDAIRY_TTS_PIPER_MODEL_EN", "").strip()
        self._piper_model_zh = os.environ.get("HEALTHDAIRY_TTS_PIPER_MODEL_ZH", "").strip()
        self._piper_config_en = os.environ.get("HEALTHDAIRY_TTS_PIPER_CONFIG_EN", "").strip()
        self._piper_config_zh = os.environ.get("HEALTHDAIRY_TTS_PIPER_CONFIG_ZH", "").strip()
        # ALSA plug device for Pi I2S (e.g. MAX98357A); adjust if aplay -l shows a different card.
        self._linux_playback_device = "plughw:2,0"
        self._active_lock = threading.Lock()
        self._active_eng: Any = None
        self._active_proc: Optional[subprocess.Popen] = None
        # When espeak --stdout | aplay, keep the writer so stop() can kill both ends.
        self._active_pipe_src: Optional[subprocess.Popen] = None

    def ensure_started(self) -> bool:
        if self._thread is not None:
            return self._init_ok
        self._thread = threading.Thread(target=self._loop, daemon=True, name="HealthDairy-TTS")
        self._thread.start()
        self._started.wait(timeout=10.0)
        return self._init_ok

    @staticmethod
    def _ensure_unix_path() -> None:
        """Desktop .desktop launches on Pi often omit /usr/bin; espeak-ng lives there."""
        if sys.platform == "win32":
            return
        path = os.environ.get("PATH", "")
        parts = path.split(os.pathsep) if path else []
        for extra in ("/usr/local/bin", "/usr/bin", "/bin"):
            if extra not in parts:
                os.environ["PATH"] = extra + os.pathsep + os.environ.get("PATH", "")

    @staticmethod
    def _is_executable(path: str) -> bool:
        return bool(path) and os.path.isfile(path) and os.access(path, os.X_OK)

    def _pick_linux_cli_tts(self) -> tuple[str, str]:
        """Return (backend, abspath) or ('none', '')."""
        self._ensure_unix_path()
        candidates: List[tuple[str, List[str]]] = [
            (
                "espeak",
                [
                    shutil.which("espeak-ng") or "",
                    shutil.which("espeak") or "",
                    "/usr/bin/espeak-ng",
                    "/usr/bin/espeak",
                    "/bin/espeak-ng",
                ],
            ),
            (
                "spd_say",
                [
                    shutil.which("spd-say") or "",
                    "/usr/bin/spd-say",
                ],
            ),
        ]
        for kind, paths in candidates:
            for p in paths:
                if self._is_executable(p):
                    return (kind, p)
        return ("none", "")

    def _resolve_piper_model(self, lang: str) -> Tuple[str, str]:
        lc = (lang or "en").lower().strip()
        if lc.startswith("zh"):
            return (self._piper_model_zh, self._piper_config_zh)
        return (self._piper_model_en, self._piper_config_en)

    def _probe_piper_linux(self) -> bool:
        forced = os.environ.get("HEALTHDAIRY_TTS_BACKEND", "").strip().lower()
        if forced and forced != "piper":
            return False
        self._ensure_unix_path()
        piper_bin = ""
        for cand in (
            shutil.which("piper") or "",
            "/usr/bin/piper",
            "/usr/local/bin/piper",
        ):
            if self._is_executable(cand):
                piper_bin = cand
                break
        if not piper_bin:
            return False
        model_en, _ = self._resolve_piper_model("en")
        model_zh, _ = self._resolve_piper_model("zh")
        if not (model_en or model_zh):
            # No model configured yet; do not fail startup, just skip Piper.
            print(
                "[TTS] Piper found but no model path set. "
                "Set HEALTHDAIRY_TTS_PIPER_MODEL_EN and/or HEALTHDAIRY_TTS_PIPER_MODEL_ZH.",
                flush=True,
            )
            return False
        self._linux_tts_bin = piper_bin
        print(f"[TTS] Piper binary resolved to {piper_bin}", flush=True)
        return True

    @staticmethod
    def _linux_mp3_player_cmd() -> Optional[List[str]]:
        """Return a command prefix that can play ``file.mp3`` (last arg), or None."""
        mpg = shutil.which("mpg123")
        if mpg:
            return [mpg, "-q", "-o", "alsa"]
        if shutil.which("ffmpeg") and shutil.which("aplay"):
            return ["__ffmpeg_aplay__"]
        return None

    def _probe_edge_tts_linux(self) -> bool:
        forced = os.environ.get("HEALTHDAIRY_TTS_BACKEND", "").strip().lower()
        if forced and forced != "edge_tts":
            return False
        try:
            import edge_tts  # noqa: F401
        except ImportError:
            return False
        if self._linux_mp3_player_cmd() is None:
            print(
                "[TTS] edge-tts needs mpg123 or (ffmpeg + aplay) for playback; "
                "install: sudo apt install -y mpg123",
                flush=True,
            )
            return False
        return True

    @staticmethod
    def _edge_voice_for_lang(lang: str) -> str:
        lc = (lang or "en").lower().strip()
        if lc.startswith("zh"):
            return os.environ.get("HEALTHDAIRY_TTS_EDGE_VOICE_ZH", "").strip() or "zh-CN-XiaoxiaoNeural"
        return os.environ.get("HEALTHDAIRY_TTS_EDGE_VOICE_EN", "").strip() or "en-US-AriaNeural"

    def _play_mp3_linux(self, path: str) -> None:
        dev = self._linux_playback_device
        prefix = self._linux_mp3_player_cmd()
        if not prefix:
            raise RuntimeError("no mp3 player (mpg123 or ffmpeg+aplay)")
        proc: Optional[subprocess.Popen] = None
        wav_path: Optional[str] = None
        try:
            if prefix[0] == "__ffmpeg_aplay__":
                ffmpeg = shutil.which("ffmpeg")
                if not ffmpeg:
                    raise RuntimeError("ffmpeg not found")
                wav_path = path + ".wav.tmp"
                subprocess.run(
                    [ffmpeg, "-nostdin", "-loglevel", "error", "-y", "-i", path, "-f", "wav", wav_path],
                    check=True,
                    timeout=120,
                )
                proc = subprocess.Popen(
                    ["aplay", "-q", "-D", dev, wav_path],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
            else:
                proc = subprocess.Popen(
                    prefix + ["-a", dev, path],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
            with self._active_lock:
                self._active_proc = proc
            proc.wait()
        finally:
            with self._active_lock:
                if self._active_proc is proc:
                    self._active_proc = None
            if wav_path:
                try:
                    os.remove(wav_path)
                except OSError:
                    pass
            if proc is not None and proc.poll() is None:
                try:
                    proc.terminate()
                except Exception:
                    pass

    def _play_wav_linux(self, path: str) -> None:
        proc: Optional[subprocess.Popen] = None
        try:
            proc = subprocess.Popen(
                ["aplay", "-q", "-D", self._linux_playback_device, path],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
            )
            with self._active_lock:
                self._active_proc = proc
            _, err = proc.communicate()
            if proc.returncode != 0:
                msg = (err or b"").decode("utf-8", errors="replace").strip()
                raise RuntimeError(f"aplay failed (device {self._linux_playback_device!r}): {msg or proc.returncode}")
        finally:
            with self._active_lock:
                if self._active_proc is proc:
                    self._active_proc = None
            if proc is not None and proc.poll() is None:
                try:
                    proc.terminate()
                except Exception:
                    pass

    def _speak_edge_tts(self, text: str, lang: str) -> None:
        import asyncio

        import edge_tts

        voice = self._edge_voice_for_lang(lang)

        async def _synth(out_path: str) -> None:
            communicate = edge_tts.Communicate(text, voice)
            with open(out_path, "wb") as out_f:
                async for chunk in communicate.stream():
                    if chunk["type"] == "audio":
                        out_f.write(chunk["data"])

        fd, mp3_path = tempfile.mkstemp(suffix=".mp3")
        os.close(fd)
        try:
            asyncio.run(_synth(mp3_path))
            self._play_mp3_linux(mp3_path)
        finally:
            try:
                os.remove(mp3_path)
            except OSError:
                pass

    def _speak_edge_with_espeak_fallback(self, text: str, lang: str) -> None:
        try:
            self._speak_edge_tts(text, lang)
        except Exception as e:
            print(f"[TTS] edge-tts failed, falling back to eSpeak: {e}", flush=True)
            fb = self._linux_espeak_fallback
            if not fb:
                return
            kind, path = fb
            prev_b = self._backend
            prev_bin = self._linux_tts_bin
            try:
                self._backend = kind
                self._linux_tts_bin = path
                self._speak_linux_cli(text, lang)
            finally:
                self._backend = prev_b
                self._linux_tts_bin = prev_bin

    def _speak_piper(self, text: str, lang: str) -> None:
        if not self._linux_tts_bin:
            raise RuntimeError("piper binary is not configured")
        model_path, config_path = self._resolve_piper_model(lang)
        if not model_path:
            # Fallback by language if only one model is configured.
            model_path = self._piper_model_en or self._piper_model_zh
            config_path = self._piper_config_en or self._piper_config_zh
        if not model_path:
            raise RuntimeError("piper model path not configured")
        if not os.path.isfile(model_path):
            raise RuntimeError(f"piper model file not found: {model_path}")
        if not config_path:
            auto_cfg = model_path + ".json"
            if os.path.isfile(auto_cfg):
                config_path = auto_cfg

        fd, wav_path = tempfile.mkstemp(suffix=".wav")
        os.close(fd)
        try:
            cmd: List[str] = [self._linux_tts_bin, "--model", model_path, "--output_file", wav_path]
            if config_path and os.path.isfile(config_path):
                cmd.extend(["--config", config_path])
            # Piper reads input text from stdin.
            pr = subprocess.run(
                cmd,
                input=text.encode("utf-8", errors="replace"),
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
                timeout=90,
            )
            if pr.returncode != 0:
                err = (pr.stderr or b"").decode("utf-8", errors="replace").strip()
                raise RuntimeError(f"piper exited {pr.returncode}: {err}")
            self._play_wav_linux(wav_path)
        finally:
            try:
                os.remove(wav_path)
            except OSError:
                pass

    def _interrupt_playback(self) -> None:
        with self._active_lock:
            eng = self._active_eng
            proc = self._active_proc
            pipe_src = self._active_pipe_src
            self._active_eng = None
            self._active_proc = None
            self._active_pipe_src = None
        if eng is not None:
            try:
                eng.stop()
            except Exception:
                pass
        for p in (pipe_src, proc):
            if p is not None:
                try:
                    p.terminate()
                except Exception:
                    pass
                try:
                    p.kill()
                except Exception:
                    pass

    def _speak_linux_cli(self, text: str, lang: str) -> None:
        if not self._linux_tts_bin:
            return

        lc = (lang or "en").lower().strip()
        espeak_proc: Optional[subprocess.Popen] = None
        aplay_proc: Optional[subprocess.Popen] = None

        try:
            if self._backend == "espeak":
                cmd: List[str] = [self._linux_tts_bin, "--stdout", "-s", "170"]
                if lc.startswith("zh"):
                    cmd.extend(["-v", "zh"])
                else:
                    cmd.extend(["-v", "en-us"])
                cmd.append(text)

                espeak_proc = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                )

                aplay_proc = subprocess.Popen(
                    ["aplay", "-D", self._linux_playback_device],
                    stdin=espeak_proc.stdout,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )

                with self._active_lock:
                    self._active_proc = aplay_proc
                    self._active_pipe_src = espeak_proc

                if espeak_proc.stdout is not None:
                    espeak_proc.stdout.close()

                aplay_proc.wait()
                espeak_proc.wait()

            elif self._backend == "spd_say":
                lang_tag = "zh" if lc.startswith("zh") else "en"
                aplay_proc = subprocess.Popen(
                    [self._linux_tts_bin, "-l", lang_tag, text],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
                with self._active_lock:
                    self._active_proc = aplay_proc
                aplay_proc.wait()

            else:
                return

        except Exception as e:
            print(f"[TTS] Linux CLI playback failed: {e}", flush=True)

        finally:
            with self._active_lock:
                if self._active_proc is aplay_proc:
                    self._active_proc = None
                if self._active_pipe_src is espeak_proc:
                    self._active_pipe_src = None

            for proc in (aplay_proc, espeak_proc):
                if proc is not None and proc.poll() is None:
                    try:
                        proc.terminate()
                    except Exception:
                        pass

    def _loop(self) -> None:
        try:
            if sys.platform == "win32":
                try:
                    import pythoncom  # type: ignore[import-untyped]

                    pythoncom.CoInitialize()
                except Exception:
                    pass

            self._backend = "none"
            if sys.platform != "win32":
                kind, path = self._pick_linux_cli_tts()
                self._linux_espeak_fallback = (kind, path) if kind != "none" and path else None
                forced = os.environ.get("HEALTHDAIRY_TTS_BACKEND", "").strip().lower()
                if forced == "piper" and self._probe_piper_linux():
                    self._backend = "piper"
                    self._init_ok = True
                elif forced == "edge_tts" and self._probe_edge_tts_linux():
                    self._backend = "edge_tts"
                    self._linux_tts_bin = None
                    self._init_ok = True
                elif forced in ("espeak", "spd_say") and kind == forced and path:
                    self._backend = kind
                    self._linux_tts_bin = path
                    self._init_ok = True
                elif forced == "pyttsx3":
                    try:
                        probe = pyttsx3.init()
                        del probe
                        self._backend = "pyttsx3"
                        self._init_ok = True
                    except Exception:
                        self._init_ok = False
                elif self._probe_piper_linux():
                    self._backend = "piper"
                    self._init_ok = True
                elif self._probe_edge_tts_linux():
                    self._backend = "edge_tts"
                    self._linux_tts_bin = None
                    self._init_ok = True
                elif kind != "none" and path:
                    self._backend = kind
                    self._linux_tts_bin = path
                    self._init_ok = True
                else:
                    try:
                        probe = pyttsx3.init()
                        del probe
                        self._backend = "pyttsx3"
                        self._init_ok = True
                    except Exception:
                        self._init_ok = False
            else:
                try:
                    probe = pyttsx3.init()
                    del probe
                    self._backend = "pyttsx3"
                    self._init_ok = True
                except Exception:
                    self._init_ok = False

            print(
                f"[TTS] backend={self._backend}, bin={self._linux_tts_bin!r}, "
                f"device={getattr(self, '_linux_playback_device', '')!r}",
                flush=True,
            )

            # Wake GUI immediately after probe (success or failure). Must always run.
            self._started.set()
            if not self._init_ok:
                return

            while True:
                item = self._q.get()
                if item is self._SHUTDOWN:
                    break
                if item == self._STOP:
                    self._interrupt_playback()
                    continue

                text: str
                lang: str = "en"
                if isinstance(item, tuple) and len(item) >= 2 and item[0] == "say":
                    text = str(item[1])
                    lang = str(item[2]) if len(item) > 2 else "en"
                else:
                    text = str(item)

                if self._backend == "piper":
                    try:
                        self._speak_piper(text, lang)
                    except Exception as e:
                        print(f"[TTS] Piper failed, falling back to edge/espeak: {e}", flush=True)
                        if self._probe_edge_tts_linux():
                            self._speak_edge_with_espeak_fallback(text, lang)
                        elif self._linux_espeak_fallback:
                            fb_kind, fb_path = self._linux_espeak_fallback
                            prev_b = self._backend
                            prev_bin = self._linux_tts_bin
                            try:
                                self._backend = fb_kind
                                self._linux_tts_bin = fb_path
                                self._speak_linux_cli(text, lang)
                            finally:
                                self._backend = prev_b
                                self._linux_tts_bin = prev_bin
                    continue

                if self._backend == "edge_tts":
                    self._speak_edge_with_espeak_fallback(text, lang)
                    continue

                if self._backend in ("espeak", "spd_say"):
                    self._speak_linux_cli(text, lang)
                    continue

                eng = None
                try:
                    eng = pyttsx3.init()
                    with self._active_lock:
                        self._active_eng = eng
                    eng.say(text)
                    eng.runAndWait()
                except Exception:
                    pass
                finally:
                    with self._active_lock:
                        self._active_eng = None
                    if eng is not None:
                        try:
                            eng.stop()
                        except Exception:
                            pass
                        try:
                            del eng
                        except Exception:
                            pass
        finally:
            if not self._started.is_set():
                self._started.set()

    def speak(self, text: str, lang: str = "en") -> bool:
        if not text.strip():
            return False
        if not self.ensure_started():
            return False
        self._q.put(("say", text, lang or "en"))
        return True

    def stop(self) -> None:
        if self._thread is not None and self._init_ok:
            self._q.put(self._STOP)


class Worker(QObject):
    """Runs a callable in a background thread and emits result or error."""
    finished = Signal(object)
    error = Signal(Exception)

    def __init__(self, fn: Callable[[], Any]):
        super().__init__()
        self._fn = fn

    def run(self) -> None:
        try:
            result = self._fn()
            self.finished.emit(result)
        except Exception as e:
            self.error.emit(e)


SAMPLE_RATE = 16000
CHANNELS = 1
DTYPE = np.int16


def record_wav_seconds(seconds: float) -> bytes:
    """Record from default mic, return WAV bytes."""
    duration = max(0.5, float(seconds))
    data = sd.rec(int(duration * SAMPLE_RATE), samplerate=SAMPLE_RATE, channels=CHANNELS, dtype=DTYPE)
    sd.wait()
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(CHANNELS)
        w.setsampwidth(2)
        w.setframerate(SAMPLE_RATE)
        w.writeframes(data.squeeze().tobytes())
    return buf.getvalue()


CHAT_RECORD_MAX_SEC = 3.0
# Visit / doctor–patient conversation: cap to avoid runaway memory; user stops earlier.
VISIT_RECORD_MAX_SEC = 7200.0


def _maybe_boost_wav_int16_mono(wav_bytes: bytes, peak_below: int = 2800, target_peak: int = 11000) -> bytes:
    """Gently boost very quiet mic capture so ASR matches browser levels (web demo often louder).

    Does not change audio that already has reasonable peak (avoids clipping normal speech).
    """
    try:
        buf = io.BytesIO(wav_bytes)
        with wave.open(buf, "rb") as w:
            if w.getnchannels() != 1 or w.getsampwidth() != 2:
                return wav_bytes
            fr = w.getframerate()
            raw = w.readframes(w.getnframes())
        if not raw:
            return wav_bytes
        arr = np.frombuffer(raw, dtype=np.int16)
        peak = int(np.max(np.abs(arr)))
        if peak >= peak_below or peak < 1:
            return wav_bytes
        gain = min(target_peak / float(peak), 8.0)
        out = np.clip(arr.astype(np.float64) * gain, -32768, 32767).astype(np.int16)
        out_buf = io.BytesIO()
        with wave.open(out_buf, "wb") as wo:
            wo.setnchannels(1)
            wo.setsampwidth(2)
            wo.setframerate(fr)
            wo.writeframes(out.tobytes())
        return out_buf.getvalue()
    except Exception:
        return wav_bytes


def record_wav_max_seconds_or_stop(max_sec: float, stop_event: threading.Event) -> bytes:
    """Record from default mic for at most ``max_sec`` seconds, or until ``stop_event`` is set.

    Uses one continuous ``InputStream`` (same as web MediaRecorder: no gaps between chunks).
    Repeated ``sd.rec()`` blocks were unreliable on Windows and often confused ASR.
    """
    chunks: List[np.ndarray] = []
    deadline = time.monotonic() + max(0.2, float(max_sec))
    blocksize = max(1, int(SAMPLE_RATE * 0.05))

    def callback(indata: np.ndarray, frames: int, time_info: Any, status: Any) -> None:
        if status:
            pass
        chunks.append(indata.copy())

    try:
        with sd.InputStream(
            samplerate=SAMPLE_RATE,
            channels=CHANNELS,
            dtype=DTYPE,
            callback=callback,
            blocksize=blocksize,
            latency="low",
        ):
            while time.monotonic() < deadline and not stop_event.is_set():
                time.sleep(0.03)
    except Exception:
        # Fallback: one long take (no manual stop granularity)
        try:
            n = int(min(float(max_sec), 3.0) * SAMPLE_RATE)
            data = sd.rec(n, samplerate=SAMPLE_RATE, channels=CHANNELS, dtype=DTYPE)
            sd.wait()
            buf = io.BytesIO()
            with wave.open(buf, "wb") as w:
                w.setnchannels(CHANNELS)
                w.setsampwidth(2)
                w.setframerate(SAMPLE_RATE)
                w.writeframes(data.squeeze().tobytes())
            return buf.getvalue()
        except Exception:
            return record_wav_seconds(0.2)

    if not chunks:
        return record_wav_seconds(0.2)
    data = np.concatenate(chunks, axis=0)
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(CHANNELS)
        w.setsampwidth(2)
        w.setframerate(SAMPLE_RATE)
        w.writeframes(data.squeeze().tobytes())
    return buf.getvalue()


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("HealthDairy / 健康日记")
        # Wider default so bilingual tab labels fit without horizontal scrolling
        self.setMinimumSize(1280, 700)
        self.resize(1520, 880)

        # State
        self._messages: List[Dict[str, str]] = []
        self._fields: Dict[str, Any] = {}
        self._client: Optional[BackendClient] = None
        self._visit_audio: Optional[bytes] = None
        self._visit_upload_filename: str = "audio.wav"
        self._visit_upload_content_type: str = "audio/wav"
        self._visit_recording: bool = False
        self._visit_rec_stop_event = threading.Event()
        self._worker_threads: List[tuple] = []  # (QThread, Worker) refs so they aren't GC'd
        self._tts_worker = TtsWorker()
        self._tts_supported = False
        self._tts_enabled = True
        self._tts_active_source: Optional[str] = None
        self._recs_spoken_text: str = ""
        self._meal_spoken_text: str = ""
        self._app_busy: bool = False
        self._chat_recording: bool = False
        self._chat_rec_stop_event = threading.Event()
        self._chat_pathway: str = "abdominal_pain"
        self._companion_plan_date: Optional[date] = None
        self._companion_fired_slots: Set[int] = set()
        self._companion_schedule: List[Tuple[int, int]] = []
        self._companion_pool: List[str] = []
        self._companion_last_question: str = ""
        self._companion_cfg_widgets: List[QWidget] = []
        self._companion_defer_counts: Dict[int, int] = {}

        # Probe once: real playback uses TtsWorker thread + runAndWait()
        try:
            self._tts_supported = self._tts_worker.ensure_started()
        except Exception:
            self._tts_supported = False

        # Tabs – settings as a tab at the end
        tabs = QTabWidget()
        self._tabs = tabs
        tabs.addTab(self._chat_tab(), "Symptom entry / 症状记录")
        tabs.addTab(self._recommendations_tab(), "Recommendations / 建议")
        tabs.addTab(self._doctor_pack_tab(), "Doctor pack / 就诊摘要")
        tabs.addTab(self._visit_tab(), "Visit capture / 门诊录音")
        tabs.addTab(self._meals_tab(), "Meals / 饮食记录")
        tabs.addTab(self._companion_tab(), "Companion check-ins / 陪伴问候")
        tabs.addTab(self._settings_tab(), "Settings / 设置")
        self._load_settings()
        self._load_companion_settings()
        self._load_companion_pool()
        self.setCentralWidget(tabs)
        self._apply_style()
        self._companion_timer = QTimer(self)
        self._companion_timer.setInterval(30_000)
        self._companion_timer.timeout.connect(self._companion_timer_tick)
        self._companion_timer.start()

    def _client_or_prompt(self) -> Optional[BackendClient]:
        """Get client from settings; show message and return None if not configured."""
        url = self._backend_edit.text().strip()
        if not url:
            QMessageBox.warning(self, "Settings", "Enter Backend URL (e.g. http://127.0.0.1:8000)")
            return None
        return BackendClient(url)

    def _settings_tab(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(12)
        g = QGroupBox("Backend / 后端")
        gl = QVBoxLayout(g)
        gl.addWidget(QLabel("Backend URL / 后端地址："))
        self._backend_edit = QLineEdit()
        self._backend_edit.setPlaceholderText("http://127.0.0.1:8000")
        self._backend_edit.setText("http://127.0.0.1:8000")
        gl.addWidget(self._backend_edit)
        gl.addWidget(QLabel("User ID / 用户 ID："))
        self._user_edit = QLineEdit()
        self._user_edit.setPlaceholderText("demo-user-1")
        self._user_edit.setText("demo-user-1")
        gl.addWidget(self._user_edit)
        self._backend_edit.editingFinished.connect(self._save_settings)
        self._user_edit.editingFinished.connect(self._save_settings)
        layout.addWidget(g)
        layout.addStretch()
        return w

    def _companion_tab(self) -> QWidget:
        w = QWidget()
        outer = QVBoxLayout(w)
        outer.setContentsMargins(24, 24, 24, 24)
        outer.setSpacing(12)
        title = QLabel("Companion check-ins / 陪伴问候")
        title.setObjectName("SectionTitle")
        outer.addWidget(title)

        self._companion_master_cb = QCheckBox(
            "Enable daily companion check-ins / 开启每日陪伴问候（自动在 symptoms 聊天里发起简短聊天）"
        )
        self._companion_master_cb.setChecked(False)
        self._companion_master_cb.toggled.connect(self._on_companion_master_toggled)
        outer.addWidget(self._companion_master_cb)
        # Keep Companion tab compact on small Pi screens:
        # instructions are omitted here so the schedule widgets have more vertical space.
        outer.addWidget(
            QLabel(
                "Enable if you want automatic companion check-ins. / "
                "需要自动陪伴问候时请开启。"
            )
        )

        sched_g = QGroupBox("Schedule / 时间安排")
        sched_l = QVBoxLayout(sched_g)
        row_count = QHBoxLayout()
        row_count.addWidget(QLabel("Check-ins per day (max 3) / 每天次数："))
        self._companion_num = QComboBox()
        self._companion_num.addItems(["1", "2", "3"])
        self._companion_num.setCurrentIndex(0)
        row_count.addWidget(self._companion_num)
        row_count.addStretch()
        sched_l.addLayout(row_count)

        win_row = QHBoxLayout()
        win_row.addWidget(QLabel("Random time window / 随机时段："))
        self._companion_win_start = QTimeEdit()
        self._companion_win_start.setDisplayFormat("HH:mm")
        self._companion_win_start.setTime(QTime(9, 0))
        # Touch-friendly: show up/down arrows for time adjustment.
        self._companion_win_start.setButtonSymbols(QAbstractSpinBox.UpDownArrows)
        win_row.addWidget(self._companion_win_start)
        win_row.addWidget(QLabel("–"))
        self._companion_win_end = QTimeEdit()
        self._companion_win_end.setDisplayFormat("HH:mm")
        self._companion_win_end.setTime(QTime(21, 0))
        # Touch-friendly: show up/down arrows for time adjustment.
        self._companion_win_end.setButtonSymbols(QAbstractSpinBox.UpDownArrows)
        win_row.addWidget(self._companion_win_end)
        win_row.addStretch()
        sched_l.addLayout(win_row)

        self._companion_random_chk: List[QCheckBox] = []
        self._companion_time_edits: List[QTimeEdit] = []
        for i in range(3):
            g2 = QGroupBox(f"Check-in {i + 1} / 第 {i + 1} 次")
            f2 = QFormLayout(g2)
            rb = QCheckBox("Use random time in window above / 在上面时段内随机")
            rb.setChecked(True)
            self._companion_random_chk.append(rb)
            te = QTimeEdit()
            te.setDisplayFormat("HH:mm")
            te.setTime(QTime(10 + i * 4, 0))
            # Touch-friendly: show up/down arrows for time adjustment.
            te.setButtonSymbols(QAbstractSpinBox.UpDownArrows)
            self._companion_time_edits.append(te)
            f2.addRow(rb)
            f2.addRow("Fixed time / 固定时间：", te)
            sched_l.addWidget(g2)

        outer.addWidget(sched_g)
        save_row = QHBoxLayout()
        self._companion_save_btn = QPushButton("Save settings / 保存设置")
        self._companion_save_btn.clicked.connect(self._on_companion_save_clicked)
        save_row.addWidget(self._companion_save_btn)
        save_row.addStretch()
        outer.addLayout(save_row)
        outer.addStretch()

        for cw in (
            self._companion_num,
            self._companion_win_start,
            self._companion_win_end,
            *self._companion_random_chk,
            *self._companion_time_edits,
        ):
            self._companion_cfg_widgets.append(cw)

        self._update_companion_controls_enabled()
        return w

    def _on_companion_master_toggled(self, _checked: bool) -> None:
        self._update_companion_controls_enabled()

    def _on_companion_save_clicked(self) -> None:
        self._persist_companion_settings(show_confirmation=True)

    def _update_companion_controls_enabled(self) -> None:
        on = self._companion_master_cb.isChecked()
        for cw in self._companion_cfg_widgets:
            cw.setEnabled(on)
        for i in range(3):
            if on:
                fixed_enable = not self._companion_random_chk[i].isChecked()
                self._companion_time_edits[i].setEnabled(fixed_enable)
            else:
                self._companion_time_edits[i].setEnabled(False)

    def _persist_companion_settings(self, *, show_confirmation: bool = False) -> None:
        s = QSettings("HealthDairy", "HealthDairy")
        s.setValue("companion_enabled", self._companion_master_cb.isChecked())
        s.setValue("companion_num", self._companion_num.currentIndex() + 1)
        s.setValue("companion_win_start", self._companion_win_start.time().toString("HH:mm"))
        s.setValue("companion_win_end", self._companion_win_end.time().toString("HH:mm"))
        for i in range(3):
            s.setValue(f"companion_slot{i}_random", self._companion_random_chk[i].isChecked())
            s.setValue(f"companion_slot{i}_time", self._companion_time_edits[i].time().toString("HH:mm"))
        s.sync()
        self._companion_schedule = []
        self._update_companion_controls_enabled()
        if show_confirmation:
            QMessageBox.information(
                self,
                "Companion check-ins / 陪伴问候",
                "Settings saved successfully. / 设置已成功保存。",
            )

    def _load_companion_settings(self) -> None:
        s = QSettings("HealthDairy", "HealthDairy")
        self._companion_master_cb.blockSignals(True)
        try:
            # Start OFF on each app launch; user enables manually for current session.
            self._companion_master_cb.setChecked(False)
            n = int(s.value("companion_num", 1))
            self._companion_num.setCurrentIndex(max(0, min(2, n - 1)))
            ws = s.value("companion_win_start", "09:00")
            we = s.value("companion_win_end", "21:00")
            if isinstance(ws, str) and QTime.fromString(ws, "HH:mm").isValid():
                self._companion_win_start.setTime(QTime.fromString(ws, "HH:mm"))
            if isinstance(we, str) and QTime.fromString(we, "HH:mm").isValid():
                self._companion_win_end.setTime(QTime.fromString(we, "HH:mm"))
            defaults = ("10:00", "14:00", "18:00")
            for i in range(3):
                r = s.value(f"companion_slot{i}_random", True)
                self._companion_random_chk[i].setChecked(bool(r))
                tt = s.value(f"companion_slot{i}_time", defaults[i])
                if isinstance(tt, str):
                    q = QTime.fromString(tt, "HH:mm")
                    if q.isValid():
                        self._companion_time_edits[i].setTime(q)
        finally:
            self._companion_master_cb.blockSignals(False)
        self._update_companion_controls_enabled()

    def _load_companion_pool(self) -> None:
        self._companion_pool = load_question_pool()

    def _window_minutes_pair(self) -> Tuple[int, int]:
        ws = self._companion_win_start.time()
        we = self._companion_win_end.time()
        wsm = ws.hour() * 60 + ws.minute()
        wem = we.hour() * 60 + we.minute()
        if wem <= wsm:
            wem += 24 * 60
        return wsm, wem

    def _companion_ensure_schedule(self) -> None:
        import random

        today = date.today()
        if self._companion_plan_date != today:
            self._companion_plan_date = today
            self._companion_fired_slots.clear()
            self._companion_schedule = []

        if self._companion_schedule:
            return

        n = self._companion_num.currentIndex() + 1
        wsm, wem = self._window_minutes_pair()
        picks: List[Tuple[int, int]] = []
        for i in range(n):
            if self._companion_random_chk[i].isChecked():
                span = max(0, wem - wsm)
                if span <= 0:
                    m = wsm
                else:
                    m = wsm + random.randint(0, span - 1) if span > 1 else wsm
                m = m % (24 * 60)
            else:
                t = self._companion_time_edits[i].time()
                m = t.hour() * 60 + t.minute()
            picks.append((i, m))
        picks.sort(key=lambda x: x[1])
        adjusted: List[Tuple[int, int]] = []
        last = -10_000
        for slot_i, m in picks:
            mm = m
            if mm - last < 25:
                mm = (last + 25) % (24 * 60)
            adjusted.append((slot_i, mm))
            last = mm
        self._companion_schedule = adjusted
        # Skip missed slots at app launch/day reset (no immediate catch-up).
        now = datetime.now().time()
        now_m = now.hour * 60 + now.minute
        for slot_i, target_m in self._companion_schedule:
            if target_m < now_m:
                self._companion_fired_slots.add(slot_i)

    def _companion_timer_tick(self) -> None:
        if not self._companion_master_cb.isChecked():
            return
        self._companion_ensure_schedule()
        now = datetime.now().time()
        now_m = now.hour * 60 + now.minute
        for slot_i, target_m in self._companion_schedule:
            if slot_i in self._companion_fired_slots:
                continue
            if now_m < target_m:
                continue
            self._companion_try_deliver(slot_i)
            break

    def _companion_try_deliver(self, slot_i: int) -> None:
        if self._app_busy or self._chat_recording:
            c = self._companion_defer_counts.get(slot_i, 0) + 1
            self._companion_defer_counts[slot_i] = c
            if c > 20:
                self._companion_fired_slots.add(slot_i)
                self._companion_defer_counts.pop(slot_i, None)
            return
        self._companion_defer_counts.pop(slot_i, None)
        self._companion_fired_slots.add(slot_i)
        self._deliver_companion_checkin(slot_i)

    def _infer_lines_tts_lang(self, text: str) -> str:
        t = (text or "").strip()
        if not t:
            return "en"
        first_line = t.split("\n", 1)[0]
        for ch in first_line:
            if "\u4e00" <= ch <= "\u9fff":
                return "zh"
        return "en"

    def _deliver_companion_checkin(self, slot_i: int) -> None:
        if not self._companion_pool:
            self._load_companion_pool()
        qtext = pick_question(self._companion_pool, avoid_last=self._companion_last_question or None)
        self._companion_last_question = qtext
        self._chat_pathway = "companion"
        self._messages = []
        self._fields = {}
        self._messages.append({"role": "assistant", "text": qtext})
        self._append_chat(f"Companion (check-in {slot_i + 1}) / 陪伴问候：\n{qtext}")
        if self._tts_enabled and self._tts_supported:
            line0 = qtext.split("\n", 1)[0].strip() or qtext
            self._speak(line0, self._infer_lines_tts_lang(qtext), source="chat")
        if hasattr(self, "_tabs"):
            self._tabs.setCurrentIndex(0)

    def _load_settings(self) -> None:
        s = QSettings("HealthDairy", "HealthDairy")
        url = s.value("backend_url", "http://127.0.0.1:8000")
        user = s.value("user_id", "demo-user-1")
        self._backend_edit.blockSignals(True)
        self._user_edit.blockSignals(True)
        try:
            self._backend_edit.setText(url if isinstance(url, str) else "")
            self._user_edit.setText(user if isinstance(user, str) else "")
        finally:
            self._backend_edit.blockSignals(False)
            self._user_edit.blockSignals(False)

    def _save_settings(self) -> None:
        s = QSettings("HealthDairy", "HealthDairy")
        s.setValue("backend_url", self._backend_edit.text().strip() or "http://127.0.0.1:8000")
        s.setValue("user_id", self._user_edit.text().strip() or "demo-user-1")

    def _apply_style(self) -> None:
        """Apply a simple, modern light theme similar to the web demo."""
        self.setStyleSheet(
            """
            QMainWindow {
                background-color: #f5f7fa;
            }
            QTabWidget::pane {
                border: 0;
                background: transparent;
            }
            QTabBar::tab {
                padding: 10px 20px;
                margin-right: 4px;
                border-radius: 10px;
                background: transparent;
                color: #4b5563;
                font-size: 14px;
                font-weight: 600;
            }
            QTabBar::tab:selected {
                background: #ffffff;
                color: #0f172a;
            }
            QTabBar::tab:!selected {
                background: transparent;
            }
            QGroupBox {
                background-color: #ffffff;
                border: 1px solid #e5e7eb;
                border-radius: 12px;
                margin-top: 16px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 12px;
                padding: 0 4px;
                color: #111827;
                font-weight: 600;
            }
            QLabel#SectionTitle {
                font-size: 18px;
                font-weight: 600;
                margin-bottom: 4px;
                color: #0f172a;
            }
            QLabel {
                color: #111827;
                font-size: 14px;
            }
            QLineEdit, QPlainTextEdit {
                background-color: #ffffff;
                border: 1px solid #d1d5db;
                border-radius: 8px;
                padding: 6px 8px;
                font-size: 13px;
            }
            QPushButton {
                background-color: #0b6efd;
                color: #ffffff;
                border-radius: 10px;
                padding: 8px 14px;
                border: none;
            }
            QPushButton:hover {
                background-color: #0955c1;
            }
            QPushButton:disabled {
                background-color: #e5e7eb;
                color: #9ca3af;
            }
            """
        )

    def _run_in_background(
        self,
        fn: Callable[[], Any],
        on_success: Callable[[Any], None],
        on_error: Callable[[Exception], None],
    ) -> None:
        """Run fn() in a background thread; call on_success/on_error on the GUI thread.

        Plain Python callables connected to worker signals can run on the worker thread in PySide6,
        which breaks UI updates. Marshal results onto the main thread with QTimer.singleShot(..., self, ...).
        """
        thread = QThread(self)
        worker = Worker(fn)
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.finished.connect(
            lambda r: QTimer.singleShot(0, self, lambda r=r: self._finish_worker_success(on_success, r))
        )
        worker.finished.connect(thread.quit)
        worker.error.connect(
            lambda e: QTimer.singleShot(0, self, lambda e=e: self._finish_worker_error(on_error, e))
        )
        worker.error.connect(thread.quit)
        thread.finished.connect(thread.deleteLater)
        thread.finished.connect(worker.deleteLater)
        self._worker_threads.append((thread, worker))
        thread.start()

    def _finish_worker_success(self, on_success: Callable[[Any], None], result: Any) -> None:
        on_success(result)

    def _finish_worker_error(self, on_error: Callable[[Exception], None], exc: Exception) -> None:
        on_error(exc)

    def _chat_tab(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(12)
        title = QLabel("Symptom chat / 症状记录（与网页相同）")
        title.setObjectName("SectionTitle")
        layout.addWidget(title)
        self._chat_log = QPlainTextEdit()
        self._chat_log.setReadOnly(True)
        layout.addWidget(self._chat_log)
        layout.addWidget(QLabel("Your message / 您的描述："))
        self._chat_input = QLineEdit()
        self._chat_input.setPlaceholderText("Describe your symptom / 描述症状（中英文皆可）")
        layout.addWidget(self._chat_input)
        row = QWidget()
        row_layout = QVBoxLayout(row)
        row_layout.setContentsMargins(0, 0, 0, 0)
        h = QVBoxLayout()
        self._chat_send_btn = QPushButton("Send / 发送")
        self._chat_send_btn.clicked.connect(self._on_chat_send)
        self._chat_record_start_btn = QPushButton(
            f"Start recording (max {int(CHAT_RECORD_MAX_SEC)} s) / 开始录音（最长 {int(CHAT_RECORD_MAX_SEC)} 秒）"
        )
        self._chat_record_start_btn.clicked.connect(self._on_chat_record_start)
        self._chat_record_stop_btn = QPushButton("Stop & transcribe / 停止并转写")
        self._chat_record_stop_btn.setEnabled(False)
        self._chat_record_stop_btn.clicked.connect(self._on_chat_record_stop)
        self._chat_tts_btn = QPushButton("🔊 Voice On / 语音朗读")
        self._chat_tts_btn.clicked.connect(self._on_toggle_tts)
        self._chat_refresh_btn = QPushButton("New symptom / 新症状（清空会话）")
        self._chat_refresh_btn.setToolTip(
            "Clear this chat and start another symptom entry without changing tabs.\n"
            "清空当前对话，开始记录另一个症状。"
        )
        self._chat_refresh_btn.clicked.connect(self._on_chat_refresh)
        h.addWidget(self._chat_send_btn)
        h.addWidget(self._chat_record_start_btn)
        h.addWidget(self._chat_record_stop_btn)
        h.addWidget(self._chat_tts_btn)
        h.addWidget(self._chat_refresh_btn)
        row_layout.addLayout(h)
        layout.addWidget(row)
        return w

    def _recommendations_tab(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(12)
        title = QLabel("Recommendations / 建议")
        title.setObjectName("SectionTitle")
        layout.addWidget(title)
        self._recs_btn = QPushButton("Fetch recommendations / 获取建议")
        self._recs_btn.clicked.connect(self._on_fetch_recs)
        layout.addWidget(self._recs_btn)
        self._recs_tts_btn = QPushButton("🔊 Play recommendations / 朗读建议")
        self._recs_tts_btn.setEnabled(False)
        self._recs_tts_btn.clicked.connect(self._on_recs_tts)
        layout.addWidget(self._recs_tts_btn)
        self._recs_text = QPlainTextEdit()
        self._recs_text.setReadOnly(True)
        layout.addWidget(self._recs_text)
        return w

    def _doctor_pack_tab(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(12)
        title = QLabel("Doctor pack / 就诊摘要")
        title.setObjectName("SectionTitle")
        layout.addWidget(title)
        self._pack_btn = QPushButton("Generate doctor pack / 生成就诊摘要")
        self._pack_btn.clicked.connect(self._on_doctor_pack)
        layout.addWidget(self._pack_btn)
        layout.addWidget(QLabel("Doctor pack preview / 就诊摘要预览："))
        self._pack_text = QPlainTextEdit()
        self._pack_text.setReadOnly(True)
        layout.addWidget(self._pack_text)
        return w

    def _visit_tab(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(12)
        title = QLabel("Visit capture / 门诊录音")
        title.setObjectName("SectionTitle")
        layout.addWidget(title)
        layout.addWidget(
            QLabel(
                "Record until you press Stop (long consultations), or upload an audio file. "
                "Then transcribe and get a summary.\n"
                "录音时请按“停止”结束（适合较长医患对话）；也可上传音频后转写并生成摘要。"
            )
        )
        row = QWidget()
        rh = QHBoxLayout(row)
        rh.setContentsMargins(0, 0, 0, 0)
        self._visit_record_start_btn = QPushButton(
            f"Start recording (max {int(VISIT_RECORD_MAX_SEC // 60)} min) / 开始录音"
        )
        self._visit_record_start_btn.clicked.connect(self._on_visit_record_start)
        self._visit_record_stop_btn = QPushButton("Stop recording / 停止录音")
        self._visit_record_stop_btn.setEnabled(False)
        self._visit_record_stop_btn.clicked.connect(self._on_visit_record_stop)
        rh.addWidget(self._visit_record_start_btn)
        rh.addWidget(self._visit_record_stop_btn)
        layout.addWidget(row)
        self._visit_upload_btn = QPushButton(
            "Upload audio file… / 上传音频文件…"
        )
        self._visit_upload_btn.clicked.connect(self._on_visit_upload_audio)
        layout.addWidget(self._visit_upload_btn)
        layout.addWidget(QLabel("Transcript / 文字转写："))
        self._visit_transcript = QPlainTextEdit()
        self._visit_transcript.setReadOnly(True)
        layout.addWidget(self._visit_transcript)
        self._visit_summary_btn = QPushButton("Transcribe & get summary / 转写并生成摘要")
        self._visit_summary_btn.clicked.connect(self._on_visit_summary)
        layout.addWidget(self._visit_summary_btn)
        layout.addWidget(QLabel("Summary / 摘要："))
        self._visit_summary_text = QPlainTextEdit()
        self._visit_summary_text.setReadOnly(True)
        layout.addWidget(self._visit_summary_text)
        return w

    def _meals_tab(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(12)
        title = QLabel("Meal recording / nutrition overview / 饮食记录与营养概览：")
        title.setObjectName("SectionTitle")
        layout.addWidget(title)

        self._meal_input = QPlainTextEdit()
        self._meal_input.setPlaceholderText("Describe what you ate / 描述饮食内容（中英文皆可）...")
        layout.addWidget(self._meal_input)

        self._meal_save_btn = QPushButton("Save meal / 保存饮食记录")
        self._meal_save_btn.clicked.connect(self._on_meal_save)
        layout.addWidget(self._meal_save_btn)

        self._meal_record_btn = QPushButton("Record meal (5 s) then save / 录音 5 秒并保存")
        self._meal_record_btn.clicked.connect(self._on_meal_record_and_save)
        layout.addWidget(self._meal_record_btn)

        self._meal_analyze_btn = QPushButton("Analyze last 30 days / 分析近 30 天饮食")
        self._meal_analyze_btn.clicked.connect(self._on_meal_analyze)
        layout.addWidget(self._meal_analyze_btn)

        self._meal_tts_btn = QPushButton("🔊 Play meal analysis / 朗读饮食分析")
        self._meal_tts_btn.setEnabled(False)
        self._meal_tts_btn.clicked.connect(self._on_meal_tts)
        layout.addWidget(self._meal_tts_btn)

        layout.addWidget(QLabel("Analysis / 分析结果："))
        self._meal_output = QPlainTextEdit()
        self._meal_output.setReadOnly(True)
        layout.addWidget(self._meal_output)

        return w

    def _ts_iso(self) -> str:
        now = datetime.now(timezone.utc)
        return now.strftime("%Y-%m-%dT%H:%M:%SZ")

    def _on_chat_send(self):
        text = self._chat_input.text().strip()
        if not text:
            return
        client = self._client_or_prompt()
        if not client:
            return
        self._messages.append({"role": "user", "text": text})
        self._chat_input.clear()
        self._append_chat(f"You: {text}")
        self._set_busy(True)

        url = self._backend_edit.text().strip()
        user_id = self._user_edit.text().strip() or "demo-user-1"
        messages = list(self._messages)
        fields = dict(self._fields)
        ts = self._ts_iso()
        pathway = self._chat_pathway

        def fn():
            c = BackendClient(url)
            return c.chat_step(
                user_id=user_id,
                messages=messages,
                fields=fields,
                ts=ts,
                pathway=pathway,
            )

        def on_ok(result):
            self._on_chat_result(result)
            self._set_busy(False)

        def on_err(e: Exception):
            QMessageBox.critical(self, "Error", str(e))
            self._set_busy(False)

        self._run_in_background(fn, on_ok, on_err)

    def _on_chat_result(self, result: Dict[str, Any]):
        is_companion = self._chat_pathway == "companion"
        if not is_companion:
            self._fields = result.get("fields") or {}
        reply_lang = result.get("reply_lang") or "en"
        for c in result.get("clarifiers") or []:
            q = c.get("question", "")
            self._messages.append({"role": "assistant", "text": q})
            self._append_chat(f"Assistant: {q}")
            self._speak(q, reply_lang, source="chat")
        if not is_companion and result.get("saved_id"):
            saved_line = (
                result.get("saved_message")
                or "Thanks. I've saved this entry for you."
            )
            self._messages.append({"role": "assistant", "text": saved_line})
            self._append_chat(f"Assistant: {saved_line}")
            self._speak(saved_line, reply_lang, source="chat")
        if not is_companion and result.get("ready") and not result.get("clarifiers"):
            self._messages = []
            self._fields = {}
        if is_companion and result.get("companion_done"):
            self._append_chat(
                "--- Companion check-in ended / 本轮陪伴问候已结束（可随时继续记录症状）。 ---"
            )
            self._messages = []
            self._fields = {}
            self._chat_pathway = "abdominal_pain"

    def _on_chat_record_start(self):
        """Like web demo: record until Stop or max duration, then transcribe and send."""
        if self._chat_recording or self._app_busy or self._visit_recording:
            return
        client = self._client_or_prompt()
        if not client:
            return
        self._chat_rec_stop_event.clear()
        self._chat_recording = True
        self._set_busy(False)
        url = self._backend_edit.text().strip()
        user_id = self._user_edit.text().strip() or "demo-user-1"

        def fn_record() -> bytes:
            return record_wav_max_seconds_or_stop(CHAT_RECORD_MAX_SEC, self._chat_rec_stop_event)

        def on_record_done(wav: bytes) -> None:
            self._chat_recording = False
            self._set_busy(False)
            if not wav or len(wav) < 500:
                QMessageBox.information(self, "Record", "Recording too short. Try again.")
                return
            # Match browser levels: quiet PC mics were rejected or ASR-hallucinated ("Thank you") before.
            wav = _maybe_boost_wav_int16_mono(wav)
            self._set_busy(True)
            messages_snapshot = list(self._messages)
            fields_snapshot = dict(self._fields)
            pathway_snapshot = self._chat_pathway
            ts = self._ts_iso()

            def fn_transcribe_and_chat() -> Dict[str, Any]:
                # One worker: ASR then chat step (avoids extra thread + GUI round-trip vs transcribe → _on_chat_send).
                c = BackendClient(url)
                trans = c.diary_transcribe(user_id=user_id, audio_bytes=wav, lang=None)
                transcript = (trans.get("transcript") or trans.get("text") or "").strip()
                if not transcript:
                    return {"ok": False}
                msgs = messages_snapshot + [{"role": "user", "text": transcript}]
                result = c.chat_step(
                    user_id=user_id,
                    messages=msgs,
                    fields=fields_snapshot,
                    ts=ts,
                    pathway=pathway_snapshot,
                )
                return {"ok": True, "transcript": transcript, "result": result}

            def on_tc_ok(payload: Dict[str, Any]) -> None:
                if not payload.get("ok"):
                    self._set_busy(False)
                    QMessageBox.information(self, "Record", "No speech detected. Try again.")
                    return
                t = payload["transcript"]
                self._messages.append({"role": "user", "text": t})
                self._chat_input.clear()
                self._append_chat(f"You: {t}")
                self._on_chat_result(payload["result"])
                self._set_busy(False)

            def on_tc_err(e: Exception) -> None:
                self._set_busy(False)
                QMessageBox.critical(self, "Error", str(e))

            self._run_in_background(fn_transcribe_and_chat, on_tc_ok, on_tc_err)

        def on_record_err(e: Exception) -> None:
            self._chat_recording = False
            self._set_busy(False)
            QMessageBox.critical(self, "Record", str(e))

        self._run_in_background(fn_record, on_record_done, on_record_err)

    def _on_chat_record_stop(self):
        """End recording early (same as web 'Stop & transcribe')."""
        self._chat_rec_stop_event.set()

    def _on_chat_refresh(self):
        """Clear symptom chat state so the user can log another symptom (same session)."""
        if self._app_busy or self._chat_recording:
            QMessageBox.information(
                self,
                "Symptom chat",
                "Wait until the current request or recording finishes.\n请等待当前发送或录音结束后再清空。",
            )
            return
        self._messages = []
        self._fields = {}
        self._chat_pathway = "abdominal_pain"
        self._chat_log.clear()
        self._chat_input.clear()

    def _on_fetch_recs(self):
        client = self._client_or_prompt()
        if not client:
            return
        self._set_busy(True)
        url = self._backend_edit.text().strip()
        user_id = self._user_edit.text().strip() or "demo-user-1"
        latest_user_text = ""
        for m in reversed(self._messages):
            if (m.get("role") or "") == "user":
                latest_user_text = m.get("text", "") or ""
                break
        rec_lang = _infer_lang_from_text(latest_user_text)

        def fn():
            c = BackendClient(url)
            return c.recommendations(user_id=user_id, window_days=30, lang=rec_lang)

        def on_ok(result):
            self._set_busy(False)
            suggestions = result.get("suggestions") or []
            lines = []
            for s in suggestions:
                if not isinstance(s, dict):
                    lines.append(str(s))
                    continue
                en = (s.get("text_english") or "").strip()
                zh = (s.get("text_chinese") or "").strip()
                txt = (s.get("text") or "").strip()
                if en or zh:
                    if en:
                        lines.append(f"EN: {en}")
                    if zh:
                        lines.append(f"中文: {zh}")
                    lines.append("")
                else:
                    lines.append(txt or str(s))
            self._recs_text.setPlainText("\n".join(lines) if lines else "(No suggestions)")
            spoken = ". ".join(
                (
                    f"{(s.get('text_english') or '').strip()}。{(s.get('text_chinese') or '').strip()}".strip("。")
                    if isinstance(s, dict) and ((s.get("text_english") or s.get("text_chinese")))
                    else (s.get("text") if isinstance(s, dict) and s.get("text") else str(s))
                )
                for s in suggestions
                if s
            )
            self._recs_spoken_text = spoken
            self._update_recs_tts_button()

        def on_err(e: Exception):
            QMessageBox.critical(self, "Error", str(e))
            self._set_busy(False)

        self._run_in_background(fn, on_ok, on_err)

    def _on_doctor_pack(self):
        client = self._client_or_prompt()
        if not client:
            return
        self._set_busy(True)
        user_id = self._user_edit.text().strip() or "demo-user-1"

        try:
            result = client.doctor_pack(user_id=user_id, window_days=30)
        except Exception as e:
            self._set_busy(False)
            QMessageBox.critical(self, "Doctor pack", str(e))
            return

        self._set_busy(False)
        en = result.get("english_summary") or ""
        zh = result.get("chinese_summary") or ""
        groups = result.get("symptom_groups") or []
        timeline = result.get("symptom_timeline") or []
        entry_count = result.get("entry_count")

        lines: list[str] = []
        if en:
            lines.append("Doctor-facing Summary (EN):")
            lines.append(en)
            lines.append("")
        if zh:
            lines.append("就诊概要（中文）：")
            lines.append(zh)
            lines.append("")

        if groups:
            lines.append("Symptoms by type / 按症状分类：")
            for g in groups:
                label_en = g.get("symptom_label_english") or g.get("symptom_label", "")
                label_zh = g.get("symptom_label_chinese") or ""
                title = f"{label_en} / {label_zh}" if label_zh else label_en
                lines.append(f"- {title}")
                source_labels = g.get("source_labels") or []
                if isinstance(source_labels, list) and source_labels:
                    lines.append(f"  Merged labels / 合并来源: {', '.join(str(x) for x in source_labels if x)}")
                dates = g.get("dates") or []
                if not isinstance(dates, list):
                    dates = [dates]
                clean_dates = [str(d) for d in dates if d]
                if clean_dates:
                    lines.append("  Dates / 日期:")
                    for d in clean_dates:
                        lines.append(f"    - {d}")
                sum_en = g.get("summary_english") or g.get("summary", "") or ""
                sum_zh = g.get("summary_chinese") or ""
                if sum_en:
                    lines.append(f"  EN: {sum_en}")
                if sum_zh:
                    lines.append(f"  中文: {sum_zh}")
                lines.append("")
        else:
            lines.append("No symptom groups returned.\n本时间段内没有可用的症状分组。")

        if timeline:
            lines.append("")
            if entry_count is not None:
                lines.append(f"Detailed symptom timeline / 详细症状时间线（共 {entry_count} 条）:")
            else:
                lines.append("Detailed symptom timeline / 详细症状时间线：")
            for row in timeline:
                ts = row.get("ts", "")
                label = (row.get("symptom_label") or "symptom").replace("_", " ")
                sev = row.get("severity")
                loc = row.get("location") or "-"
                char = row.get("character") or "-"
                lines.append(
                    f"- {ts} | {label} | severity={sev if sev is not None else '-'} | location={loc} | character={char}"
                )
        else:
            lines.append("")
            lines.append("No detailed timeline returned / 未返回详细时间线")

        self._pack_text.setPlainText("\n".join(lines))

    @staticmethod
    def _visit_audio_filename_and_mime(path: str) -> Tuple[str, str]:
        ext = os.path.splitext(path)[1].lower()
        mime = {
            ".wav": "audio/wav",
            ".webm": "audio/webm",
            ".mp3": "audio/mpeg",
            ".m4a": "audio/mp4",
            ".ogg": "audio/ogg",
        }.get(ext, "application/octet-stream")
        name = os.path.basename(path) or "audio"
        return name, mime

    def _on_visit_record_start(self) -> None:
        if self._visit_recording or self._app_busy or self._chat_recording:
            return
        self._visit_rec_stop_event.clear()
        self._visit_recording = True
        self._visit_upload_filename = "audio.wav"
        self._visit_upload_content_type = "audio/wav"
        self._set_busy(False)

        def fn_record() -> bytes:
            return record_wav_max_seconds_or_stop(VISIT_RECORD_MAX_SEC, self._visit_rec_stop_event)

        def on_record_done(wav: bytes) -> None:
            self._visit_recording = False
            self._set_busy(False)
            if not wav or len(wav) < 500:
                QMessageBox.information(self, "Visit", "Recording too short. Try again.\n录音太短。")
                return
            wav = _maybe_boost_wav_int16_mono(wav)
            self._visit_audio = wav
            self._visit_transcript.setPlainText(
                "(Recording saved. Click “Transcribe & get summary”.)\n（录音已保存，可按“转写并生成摘要”。）"
            )

        def on_record_err(e: Exception) -> None:
            self._visit_recording = False
            self._set_busy(False)
            QMessageBox.critical(self, "Visit", str(e))

        self._run_in_background(fn_record, on_record_done, on_record_err)

    def _on_visit_record_stop(self) -> None:
        self._visit_rec_stop_event.set()

    def _on_visit_upload_audio(self) -> None:
        if self._visit_recording or self._app_busy or self._chat_recording:
            return
        path, _filter = QFileDialog.getOpenFileName(
            self,
            "Open audio file / 选择音频",
            "",
            "Audio (*.wav *.WAV *.webm *.WEBM *.mp3 *.MP3 *.m4a *.M4A *.ogg *.OGG);;All files (*.*)",
        )
        if not path:
            return
        try:
            with open(path, "rb") as f:
                data = f.read()
        except OSError as e:
            QMessageBox.critical(self, "Visit", f"Could not read file.\n{e}")
            return
        if not data or len(data) < 100:
            QMessageBox.warning(self, "Visit", "File is empty or too small.\n文件为空或过小。")
            return
        name, mime = self._visit_audio_filename_and_mime(path)
        self._visit_upload_filename = name
        self._visit_upload_content_type = mime
        self._visit_audio = data
        self._visit_transcript.setPlainText(
            f"(Loaded {name}. Click “Transcribe & get summary”.)\n（已加载 {name} ，可按“转写并生成摘要”。）"
        )

    def _on_visit_summary(self):
        client = self._client_or_prompt()
        if not client:
            return
        if not getattr(self, "_visit_audio", None):
            QMessageBox.warning(self, "Visit", "Record or upload audio first.\n请先录音或上传音频。")
            return
        self._set_busy(True)
        wav = self._visit_audio
        url = self._backend_edit.text().strip()
        user_id = self._user_edit.text().strip() or "demo-user-1"
        lang: Optional[str] = None
        fname = self._visit_upload_filename
        ctype = self._visit_upload_content_type
        tmo = max(120, min(3600, 60 + len(wav) // 3000))

        def fn():
            c = BackendClient(url)
            trans = c.transcribe(
                user_id=user_id,
                audio_bytes=wav,
                lang=lang,
                filename=fname,
                content_type=ctype,
                timeout=tmo,
            )
            transcript = trans.get("transcript") or trans.get("text") or ""
            if transcript:
                summary = c.visit_summary(user_id=user_id, transcript=transcript, lang="en")
                return {"transcript": transcript, "summary": summary}
            return {"transcript": "", "summary": {}}

        def on_ok(result: Dict):
            self._set_busy(False)
            self._visit_transcript.setPlainText(result.get("transcript", ""))
            s = result.get("summary") or {}
            summary_text = s.get("summary_md") or s.get("summary") or s.get("doctor_instructions") or str(s)
            self._visit_summary_text.setPlainText(summary_text)

        def on_err(e: Exception):
            QMessageBox.critical(self, "Error", str(e))
            self._set_busy(False)

        self._run_in_background(fn, on_ok, on_err)

    def _on_meal_record_and_save(self):
        client = self._client_or_prompt()
        if not client:
            return
        self._set_busy(True)
        url = self._backend_edit.text().strip()
        user_id = self._user_edit.text().strip() or "demo-user-1"

        def fn():
            wav = record_wav_seconds(5.0)
            c = BackendClient(url)
            trans = c.diary_transcribe(user_id=user_id, audio_bytes=wav, lang=None)
            return trans.get("transcript") or trans.get("text") or ""

        def on_ok(transcript: str):
            self._set_busy(False)
            if transcript:
                self._meal_input.setPlainText(transcript)
                self._on_meal_save()
            else:
                QMessageBox.information(self, "Meals", "No speech detected. Try again.")

        def on_err(e: Exception):
            QMessageBox.critical(self, "Meals", str(e))
            self._set_busy(False)

        self._run_in_background(fn, on_ok, on_err)

    def _on_meal_save(self):
        client = self._client_or_prompt()
        if not client:
            return
        text = self._meal_input.toPlainText().strip()
        if not text:
            QMessageBox.information(self, "Meals", "Describe what you ate before saving.")
            return

        self._set_busy(True)
        url = self._backend_edit.text().strip()
        user_id = self._user_edit.text().strip() or "demo-user-1"
        meal_text = text

        def fn():
            c = BackendClient(url)
            return c.log_meal(user_id=user_id, text=meal_text)

        def on_ok(result: Dict[str, Any]):
            self._set_busy(False)
            meal_type = result.get("meal_type", "")
            items = result.get("items") or []
            lines = []
            if meal_type:
                lines.append(f"Meal type: {meal_type}")
            if items:
                lines.append("Items: " + ", ".join(str(it) for it in items))
            if not lines:
                lines.append("Meal saved.")
            self._meal_output.setPlainText("\n".join(lines))
            self._meal_input.clear()

        def on_err(e: Exception):
            QMessageBox.critical(self, "Meals", str(e))
            self._set_busy(False)

        self._run_in_background(fn, on_ok, on_err)

    def _on_meal_analyze(self):
        client = self._client_or_prompt()
        if not client:
            return

        self._set_busy(True)
        url = self._backend_edit.text().strip()
        user_id = self._user_edit.text().strip() or "demo-user-1"

        def fn():
            c = BackendClient(url)
            return c.meal_summary(user_id=user_id, window_days=30)

        def on_ok(result: Dict[str, Any]):
            self._set_busy(False)
            analysis = result.get("analysis") or {}
            summary = analysis.get("summary") or ""
            if not summary:
                summary = str(analysis or result)
            self._meal_output.setPlainText(summary)
            suggestions = analysis.get("suggestions") or []
            spoken = ". ".join(
                (s.get("text") if isinstance(s, dict) and s.get("text") else str(s))
                for s in suggestions
                if s
            )
            if summary:
                spoken = (summary + ". " + spoken).strip()
            self._meal_spoken_text = spoken
            self._update_meal_tts_button()

        def on_err(e: Exception):
            QMessageBox.critical(self, "Meals", str(e))
            self._set_busy(False)

        self._run_in_background(fn, on_ok, on_err)

    def _on_toggle_tts(self):
        if not self._tts_supported:
            QMessageBox.information(self, "Voice", "Voice playback is not supported on this system.")
            return
        self._tts_enabled = not self._tts_enabled
        if not self._tts_enabled:
            self._tts_worker.stop()
            self._tts_active_source = None
        self._update_tts_button()

    def _on_recs_tts(self):
        if not self._tts_supported or not self._recs_spoken_text:
            return
        if self._tts_active_source == "recs":
            self._stop_tts()
            return
        self._speak(self._recs_spoken_text, "en", source="recs")

    def _on_meal_tts(self):
        if not self._tts_supported or not self._meal_spoken_text:
            return
        if self._tts_active_source == "meal":
            self._stop_tts()
            return
        self._speak(self._meal_spoken_text, "en", source="meal")

    def _speak(self, text: str, lang: str = "en", source: Optional[str] = None):
        if not text or not self._tts_supported or not self._tts_enabled:
            return
        try:
            print(f"[TTS] speaking: lang={lang}, text={text[:60]!r}", flush=True)
            # TTS worker: pyttsx3 (Windows) or espeak→aplay (Linux/Pi); pass lang for voice selection.
            if self._tts_worker.speak(text, lang):
                self._tts_active_source = source
            self._update_recs_tts_button()
            self._update_meal_tts_button()
            self._update_tts_button()
        except Exception:
            self._tts_active_source = None

    def _stop_tts(self):
        self._tts_worker.stop()
        self._tts_active_source = None
        self._update_recs_tts_button()
        self._update_meal_tts_button()
        self._update_tts_button()

    def _update_tts_button(self):
        if hasattr(self, "_chat_tts_btn"):
            if not self._tts_supported:
                self._chat_tts_btn.setText("🔈 Voice not supported / 不支持语音播放")
                self._chat_tts_btn.setEnabled(False)
            else:
                self._chat_tts_btn.setText("🔊 Voice On / 语音朗读" if self._tts_enabled else "🔇 Voice Off / 关闭朗读")

    def _update_recs_tts_button(self):
        if hasattr(self, "_recs_tts_btn"):
            has_text = bool(self._recs_spoken_text)
            self._recs_tts_btn.setEnabled(self._tts_supported and has_text)
            if self._tts_active_source == "recs":
                self._recs_tts_btn.setText("⏹ Stop audio / 停止朗读")
            else:
                self._recs_tts_btn.setText("🔊 Play recommendations / 朗读建议")

    def _update_meal_tts_button(self):
        if hasattr(self, "_meal_tts_btn"):
            has_text = bool(self._meal_spoken_text)
            self._meal_tts_btn.setEnabled(self._tts_supported and has_text)
            if self._tts_active_source == "meal":
                self._meal_tts_btn.setText("⏹ Stop meal audio / 停止朗读")
            else:
                self._meal_tts_btn.setText("🔊 Play meal analysis / 朗读饮食分析")

    def _append_chat(self, line: str):
        self._chat_log.appendPlainText(line)

    def _set_busy(self, busy: bool):
        self._app_busy = busy
        self._chat_send_btn.setEnabled(not busy and not self._chat_recording)
        self._chat_record_start_btn.setEnabled(
            not busy and not self._chat_recording and not self._visit_recording
        )
        self._chat_record_stop_btn.setEnabled(self._chat_recording and not busy)
        if hasattr(self, "_chat_refresh_btn"):
            self._chat_refresh_btn.setEnabled(not busy and not self._chat_recording)
        self._recs_btn.setEnabled(not busy)
        self._pack_btn.setEnabled(not busy)
        if hasattr(self, "_visit_record_start_btn"):
            self._visit_record_start_btn.setEnabled(not busy and not self._visit_recording)
        if hasattr(self, "_visit_record_stop_btn"):
            self._visit_record_stop_btn.setEnabled(self._visit_recording and not busy)
        if hasattr(self, "_visit_upload_btn"):
            self._visit_upload_btn.setEnabled(not busy and not self._visit_recording)
        if hasattr(self, "_visit_summary_btn"):
            self._visit_summary_btn.setEnabled(not busy)
        if hasattr(self, "_meal_save_btn"):
            self._meal_save_btn.setEnabled(not busy)
        if hasattr(self, "_meal_analyze_btn"):
            self._meal_analyze_btn.setEnabled(not busy)

def main():
    load_desktop_tts_env()
    app = QApplication(sys.argv)
    win = MainWindow()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
