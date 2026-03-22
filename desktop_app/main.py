#!/usr/bin/env python3
"""HealthDairy desktop app – native UI (PySide6). Uses backend for all features."""
import io
import sys
import wave
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

import numpy as np
import pyttsx3
import sounddevice as sd
from PySide6.QtCore import QObject, QSettings, QThread, Signal
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
        self._tts_engine = None
        self._tts_supported = False
        self._tts_enabled = True
        self._tts_active_source: Optional[str] = None
        self._recs_spoken_text: str = ""
        self._meal_spoken_text: str = ""

        try:
            self._tts_engine = pyttsx3.init()
            self._tts_supported = True
        except Exception:
            self._tts_engine = None
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
        """Run fn() in a background thread; call on_success(result) or on_error(exc) in main thread."""
        thread = QThread(self)
        worker = Worker(fn)
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.finished.connect(on_success)
        worker.finished.connect(thread.quit)
        worker.error.connect(on_error)
        worker.error.connect(thread.quit)
        thread.finished.connect(thread.deleteLater)
        thread.finished.connect(worker.deleteLater)
        self._worker_threads.append((thread, worker))
        thread.start()

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
        self._chat_record_btn = QPushButton("Record (5 s) then send / 录音 5 秒并发送")
        self._chat_record_btn.clicked.connect(self._on_chat_record)
        self._chat_tts_btn = QPushButton("🔊 Voice On / 语音朗读")
        self._chat_tts_btn.clicked.connect(self._on_toggle_tts)
        h.addWidget(self._chat_send_btn)
        h.addWidget(self._chat_record_btn)
        h.addWidget(self._chat_tts_btn)
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
        now = datetime.utcnow()
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
        self._set_busy(False)
        self._fields = result.get("fields") or {}
        for c in result.get("clarifiers") or []:
            q = c.get("question", "")
            self._messages.append({"role": "assistant", "text": q})
            self._append_chat(f"Assistant: {q}")
            self._speak(q, "en")
        if result.get("saved_id"):
            self._messages.append({
                "role": "assistant",
                "text": "Thanks. I've saved this entry for you.",
            })
            self._append_chat("Assistant: Thanks. I've saved this entry for you.")
            self._speak("Thanks. I've saved this entry for you.", "en")
        if result.get("ready") and not result.get("clarifiers"):
            self._messages = []
            self._fields = {}

    def _on_chat_record(self):
        client = self._client_or_prompt()
        if not client:
            return
        self._set_busy(True)
        url = self._backend_edit.text().strip()
        user_id = self._user_edit.text().strip() or "demo-user-1"
        lang = None

        def fn():
            wav = record_wav_seconds(5.0)
            c = BackendClient(url)
            trans = c.transcribe(user_id=user_id, audio_bytes=wav, lang="en")
            return trans.get("transcript") or trans.get("text") or ""

        def on_ok(transcript: str):
            self._set_busy(False)
            if transcript:
                self._chat_input.setText(transcript)
                self._on_chat_send()
            else:
                QMessageBox.information(self, "Record", "No speech detected. Try again.")

        def on_err(e: Exception):
            QMessageBox.critical(self, "Error", str(e))
            self._set_busy(False)

        self._run_in_background(fn, on_ok, on_err)

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
        if not self._tts_enabled and self._tts_engine:
            try:
                self._tts_engine.stop()
            except Exception:
                pass
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
        if not text or not self._tts_supported or not self._tts_enabled or not self._tts_engine:
            return
        try:
            # pyttsx3 does not support language codes directly everywhere; best-effort.
            if "zh" in lang.lower():
                # Some installs may have a Chinese voice; we don't enforce voice selection here.
                pass
            self._tts_engine.stop()
            self._tts_engine.say(text)
            self._tts_engine.startLoop(False)
            self._tts_active_source = source
            self._update_recs_tts_button()
            self._update_meal_tts_button()
            self._update_tts_button()
        except Exception:
            self._tts_active_source = None

    def _stop_tts(self):
        if self._tts_engine:
            try:
                self._tts_engine.stop()
            except Exception:
                pass
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

        def on_err(e: Exception):
            QMessageBox.critical(self, "Meals", str(e))
            self._set_busy(False)

        self._run_in_background(fn, on_ok, on_err)

    def _append_chat(self, line: str):
        self._chat_log.appendPlainText(line)

    def _set_busy(self, busy: bool):
        self._chat_send_btn.setEnabled(not busy)
        self._chat_record_btn.setEnabled(not busy)
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
