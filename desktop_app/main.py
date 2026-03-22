#!/usr/bin/env python3
"""HealthDairy desktop app – native UI (PySide6). Uses backend for all features."""
import io
import os
import queue
import shutil
import subprocess
import sys
import threading
import time
import wave
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional

import numpy as np
import pyttsx3
import sounddevice as sd
from PySide6.QtCore import QObject, QSettings, QThread, QTimer, Signal
from PySide6.QtWidgets import (
    QApplication,
    QGroupBox,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from api import BackendClient


class TtsWorker:
    """TTS on a background thread.

    - **Windows:** ``pyttsx3`` (SAPI) with COM init + fresh engine per phrase.
    - **Linux / Pi:** ``pyttsx3`` if it initializes; otherwise **eSpeak-NG** or **spd-say**
      (subprocess). GUI launches often have a minimal ``PATH``; we also check ``/usr/bin/...``
      directly. Install: ``sudo apt install espeak-ng`` and/or ``speech-dispatcher``.
    """

    _STOP = "__tts_stop__"
    _SHUTDOWN = None  # sentinel to end worker loop

    def __init__(self) -> None:
        self._q: "queue.Queue[Any]" = queue.Queue()
        self._thread: Optional[threading.Thread] = None
        self._started = threading.Event()
        self._init_ok = False
        self._backend = "none"  # "pyttsx3" | "espeak" | "spd_say"
        self._linux_tts_bin: Optional[str] = None
        self._active_lock = threading.Lock()
        self._active_eng: Any = None
        self._active_proc: Optional[subprocess.Popen] = None

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

    def _interrupt_playback(self) -> None:
        with self._active_lock:
            eng = self._active_eng
            proc = self._active_proc
            self._active_eng = None
            self._active_proc = None
        if eng is not None:
            try:
                eng.stop()
            except Exception:
                pass
        if proc is not None:
            try:
                proc.terminate()
            except Exception:
                pass
            try:
                proc.kill()
            except Exception:
                pass

    def _speak_linux_cli(self, text: str, lang: str) -> None:
        if not self._linux_tts_bin:
            return
        lc = (lang or "en").lower().strip()
        proc: Optional[subprocess.Popen] = None
        try:
            if self._backend == "espeak":
                cmd: List[str] = [self._linux_tts_bin, "-s", "150"]
                if lc.startswith("zh"):
                    cmd.extend(["-v", "zh"])
                else:
                    cmd.extend(["-v", "en"])
                cmd.append(text)
                proc = subprocess.Popen(
                    cmd,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
            elif self._backend == "spd_say":
                lang_tag = "zh" if lc.startswith("zh") else "en"
                proc = subprocess.Popen(
                    [self._linux_tts_bin, "-l", lang_tag, text],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
            else:
                return
            with self._active_lock:
                self._active_proc = proc
            proc.wait()
        except Exception:
            pass
        finally:
            with self._active_lock:
                if self._active_proc is proc:
                    self._active_proc = None

    def _loop(self) -> None:
        try:
            if sys.platform == "win32":
                try:
                    import pythoncom  # type: ignore[import-untyped]

                    pythoncom.CoInitialize()
                except Exception:
                    pass

            self._backend = "none"
            try:
                probe = pyttsx3.init()
                del probe
                self._backend = "pyttsx3"
                self._init_ok = True
            except Exception:
                kind, path = self._pick_linux_cli_tts()
                if kind != "none" and path:
                    self._backend = kind
                    self._linux_tts_bin = path
                    self._init_ok = True
                else:
                    self._init_ok = False

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
        # Give more space so bilingual tab labels fit without immediate resizing
        self.setMinimumSize(900, 650)
        self.resize(1100, 750)

        # State
        self._messages: List[Dict[str, str]] = []
        self._fields: Dict[str, Any] = {}
        self._client: Optional[BackendClient] = None
        self._visit_audio: Optional[bytes] = None
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

        # Probe once: real playback uses TtsWorker thread + runAndWait()
        try:
            self._tts_supported = self._tts_worker.ensure_started()
        except Exception:
            self._tts_supported = False

        # Tabs – settings as a tab at the end
        tabs = QTabWidget()
        tabs.addTab(self._chat_tab(), "Symptom entry / 症状记录")
        tabs.addTab(self._recommendations_tab(), "Recommendations / 建议")
        tabs.addTab(self._doctor_pack_tab(), "Doctor pack / 就诊摘要")
        tabs.addTab(self._visit_tab(), "Visit capture / 门诊录音")
        tabs.addTab(self._meals_tab(), "Meals / 饮食记录")
        tabs.addTab(self._settings_tab(), "Settings / 设置")
        self._load_settings()
        self.setCentralWidget(tabs)
        self._apply_style()

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
        self._visit_record_btn = QPushButton("Record (5 s) / 录音 5 秒")
        self._visit_record_btn.clicked.connect(self._on_visit_record)
        layout.addWidget(self._visit_record_btn)
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

        def fn():
            c = BackendClient(url)
            return c.chat_step(user_id=user_id, messages=messages, fields=fields, ts=ts)

        def on_ok(result):
            self._on_chat_result(result)
            self._set_busy(False)

        def on_err(e: Exception):
            QMessageBox.critical(self, "Error", str(e))
            self._set_busy(False)

        self._run_in_background(fn, on_ok, on_err)

    def _on_chat_result(self, result: Dict[str, Any]):
        self._fields = result.get("fields") or {}
        reply_lang = result.get("reply_lang") or "en"
        for c in result.get("clarifiers") or []:
            q = c.get("question", "")
            self._messages.append({"role": "assistant", "text": q})
            self._append_chat(f"Assistant: {q}")
            self._speak(q, reply_lang, source="chat")
        if result.get("saved_id"):
            saved_line = (
                result.get("saved_message")
                or "Thanks. I've saved this entry for you."
            )
            self._messages.append({"role": "assistant", "text": saved_line})
            self._append_chat(f"Assistant: {saved_line}")
            self._speak(saved_line, reply_lang, source="chat")
        if result.get("ready") and not result.get("clarifiers"):
            self._messages = []
            self._fields = {}

    def _on_chat_record_start(self):
        """Like web demo: record until Stop or max duration, then transcribe and send."""
        if self._chat_recording or self._app_busy:
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
        self._chat_log.clear()
        self._chat_input.clear()

    def _on_fetch_recs(self):
        client = self._client_or_prompt()
        if not client:
            return
        self._set_busy(True)
        url = self._backend_edit.text().strip()
        user_id = self._user_edit.text().strip() or "demo-user-1"

        def fn():
            c = BackendClient(url)
            return c.recommendations(user_id=user_id, window_days=30)

        def on_ok(result):
            self._set_busy(False)
            suggestions = result.get("suggestions") or []
            lines = [s.get("text", str(s)) for s in suggestions]
            self._recs_text.setPlainText("\n".join(lines) if lines else "(No suggestions)")
            spoken = ". ".join(
                s.get("text") if isinstance(s, dict) and s.get("text") else str(s)
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
                dates = g.get("dates") or []
                if not isinstance(dates, list):
                    dates = [dates]
                dates_str = ", ".join(str(d) for d in dates if d)
                if dates_str:
                    lines.append(f"  Dates / 日期: {dates_str}")
                sum_en = g.get("summary_english") or g.get("summary", "") or ""
                sum_zh = g.get("summary_chinese") or ""
                if sum_en:
                    lines.append(f"  EN: {sum_en}")
                if sum_zh:
                    lines.append(f"  中文: {sum_zh}")
                lines.append("")
        else:
            lines.append("No symptom groups returned.\n本时间段内没有可用的症状分组。")

        self._pack_text.setPlainText("\n".join(lines))

    def _on_visit_record(self):
        self._set_busy(True)

        def fn():
            return record_wav_seconds(5.0)

        def on_ok(wav: bytes):
            self._set_busy(False)
            self._visit_audio = wav
            self._visit_transcript.setPlainText("(Recorded. Click 'Transcribe recording & get summary' to get transcript and summary.)")

        def on_err(e: Exception):
            QMessageBox.critical(self, "Error", str(e))
            self._set_busy(False)

        self._run_in_background(fn, on_ok, on_err)

    def _on_visit_summary(self):
        client = self._client_or_prompt()
        if not client:
            return
        if not getattr(self, "_visit_audio", None):
            QMessageBox.warning(self, "Visit", "Record first (Record 5 s).")
            return
        self._set_busy(True)
        wav = self._visit_audio
        url = self._backend_edit.text().strip()
        user_id = self._user_edit.text().strip() or "demo-user-1"
        lang = "en"

        def fn():
            c = BackendClient(url)
            trans = c.transcribe(user_id=user_id, audio_bytes=wav, lang=lang)
            transcript = trans.get("transcript") or trans.get("text") or ""
            if transcript:
                summary = c.visit_summary(user_id=user_id, transcript=transcript, lang=lang)
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
            # TTS worker: pyttsx3 (Windows) or espeak-ng (Linux/Pi); pass lang for voice selection.
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
        self._chat_record_start_btn.setEnabled(not busy and not self._chat_recording)
        self._chat_record_stop_btn.setEnabled(self._chat_recording and not busy)
        if hasattr(self, "_chat_refresh_btn"):
            self._chat_refresh_btn.setEnabled(not busy and not self._chat_recording)
        self._recs_btn.setEnabled(not busy)
        self._pack_btn.setEnabled(not busy)
        self._visit_record_btn.setEnabled(not busy)
        self._visit_summary_btn.setEnabled(not busy)
        if hasattr(self, "_meal_save_btn"):
            self._meal_save_btn.setEnabled(not busy)
        if hasattr(self, "_meal_analyze_btn"):
            self._meal_analyze_btn.setEnabled(not busy)

def main():
    app = QApplication(sys.argv)
    win = MainWindow()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
