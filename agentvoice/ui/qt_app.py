from __future__ import annotations

import sys
import threading
import time
from pathlib import Path

try:
    from PySide6.QtCore import QEvent, QObject, Qt, Signal
    from PySide6.QtGui import QKeyEvent, QShortcut
    from PySide6.QtWidgets import (
        QApplication,
        QCheckBox,
        QComboBox,
        QDialog,
        QDoubleSpinBox,
        QFileDialog,
        QFormLayout,
        QHBoxLayout,
        QLabel,
        QLineEdit,
        QListWidget,
        QMessageBox,
        QProgressBar,
        QPushButton,
        QPlainTextEdit,
        QSpinBox,
        QTabWidget,
        QVBoxLayout,
        QWidget,
    )

    QT_AVAILABLE = True
except ImportError:
    QT_AVAILABLE = False

from agentvoice.config import SettingsStore
from agentvoice.recorder import AudioRecorder
from agentvoice.service import AgentVoiceService


if QT_AVAILABLE:

    class UiBridge(QObject):
        volume_changed = Signal(float)
        transcript_ready = Signal(str)
        compile_chunk = Signal(str)
        compile_done = Signal(str)
        error = Signal(str)
        show_requested = Signal()
        stt_status = Signal(str)


    class SettingsBridge(QObject):
        mic_volume = Signal(float)
        mic_done = Signal(str)
        mic_error = Signal(str)
        transcript_done = Signal(str)
        transcript_error = Signal(str)
        stt_status = Signal(str)


    class SettingsDialog(QDialog):
        def __init__(self, service: AgentVoiceService, parent: QWidget | None = None) -> None:
            super().__init__(parent)
            self.service = service
            self.settings_store = SettingsStore()
            self.bridge = SettingsBridge()
            self.test_recorder: AudioRecorder | None = None
            self.last_test_wav: Path | None = None
            self.default_device_warning = ""
            self.setWindowTitle("AgentVoice 设置")
            self.resize(760, 560)

            self.bridge.mic_volume.connect(self._on_mic_volume)
            self.bridge.mic_done.connect(self._on_mic_done)
            self.bridge.mic_error.connect(self._on_mic_error)
            self.bridge.transcript_done.connect(self._on_transcript_done)
            self.bridge.transcript_error.connect(self._on_transcript_error)
            self.bridge.stt_status.connect(self._on_stt_status)

            tabs = QTabWidget()
            tabs.addTab(self._status_tab(), "状态")
            tabs.addTab(self._general_tab(), "快捷键/行为")
            tabs.addTab(self._speech_tab(), "语音转录")
            tabs.addTab(self._llm_tab(), "LLM")
            tabs.addTab(self._modes_tab(), "Modes")
            tabs.addTab(self._history_tab(), "历史")

            layout = QVBoxLayout(self)
            layout.addWidget(tabs)

        def _status_tab(self) -> QWidget:
            widget = QWidget()
            layout = QVBoxLayout(widget)
            layout.addWidget(QLabel(f"STT: {self.service.settings.stt_provider}"))
            layout.addWidget(QLabel(f"LLM: {self.service.compiler.llm.name}"))
            layout.addWidget(QLabel(f"模型缓存目录: {self.service.settings.model_cache_dir}"))
            layout.addWidget(QLabel(f"配置文件: {self.settings_store.path}"))
            layout.addWidget(QLabel(f"历史数据库: {self.service.settings.history_path}"))
            layout.addWidget(QLabel("调试顺序：先测试麦克风音量，再测试转录模型，最后回到浮窗按住 Space。"))
            layout.addStretch()
            return widget

        def _general_tab(self) -> QWidget:
            widget = QWidget()
            form = QFormLayout(widget)

            self.hotkey_input = QLineEdit(self.service.settings.hotkey)
            self.push_to_talk_input = QLineEdit(self.service.settings.push_to_talk_key)
            self.auto_copy_checkbox = QCheckBox("生成完成后自动复制到剪贴板")
            self.auto_copy_checkbox.setChecked(self.service.settings.auto_copy)
            self.save_history_checkbox = QCheckBox("保存本地历史")
            self.save_history_checkbox.setChecked(self.service.settings.save_history)

            save_button = QPushButton("保存快捷键和行为")
            save_button.clicked.connect(self._save_general)

            form.addRow("全局唤起快捷键", self.hotkey_input)
            form.addRow("按住录音键", self.push_to_talk_input)
            form.addRow("", self.auto_copy_checkbox)
            form.addRow("", self.save_history_checkbox)
            form.addRow("", QLabel("快捷键修改后需要重启应用才能重新注册全局监听。"))
            form.addRow("", save_button)
            return widget

        def _speech_tab(self) -> QWidget:
            widget = QWidget()
            layout = QVBoxLayout(widget)
            form = QFormLayout()

            self.stt_combo = QComboBox()
            self.stt_combo.addItem("SenseVoice-Small 本地（推荐）", "sensevoice-small")
            self.stt_combo.addItem("Whisper large-v3（大模型备用）", "whisper-large-v3")
            self.stt_combo.addItem("FunASR Paraformer（备用）", "funasr")
            index = self.stt_combo.findData(self.service.settings.stt_provider)
            if index >= 0:
                self.stt_combo.setCurrentIndex(index)

            self.device_combo = QComboBox()
            self._load_audio_devices()
            self.model_cache_input = QLineEdit(str(self.service.settings.model_cache_dir or ""))

            refresh_button = QPushButton("刷新设备")
            refresh_button.clicked.connect(self._load_audio_devices)
            browse_cache_button = QPushButton("选择目录")
            browse_cache_button.clicked.connect(self._choose_model_cache_dir)
            save_speech_button = QPushButton("保存语音设置")
            save_speech_button.clicked.connect(self._save_speech)

            device_row = QHBoxLayout()
            device_row.addWidget(self.device_combo, 1)
            device_row.addWidget(refresh_button)
            cache_row = QHBoxLayout()
            cache_row.addWidget(self.model_cache_input, 1)
            cache_row.addWidget(browse_cache_button)

            form.addRow("转录引擎", self.stt_combo)
            form.addRow("麦克风", device_row)
            form.addRow("模型缓存目录", cache_row)
            form.addRow("", save_speech_button)
            layout.addLayout(form)

            self.mic_status = QLabel(self.default_device_warning or "未测试")
            self.mic_volume_bar = QProgressBar()
            self.mic_volume_bar.setRange(0, 2000)
            self.mic_volume_bar.setValue(0)
            self.mic_volume_bar.setTextVisible(True)

            test_buttons = QHBoxLayout()
            self.test_mic_button = QPushButton("测试麦克风 3 秒")
            self.test_mic_button.clicked.connect(self._test_microphone)
            self.test_transcript_button = QPushButton("测试转录")
            self.test_transcript_button.clicked.connect(self._test_transcription)
            self.preload_stt_button = QPushButton("预加载转录模型")
            self.preload_stt_button.clicked.connect(self._preload_transcriber)
            test_buttons.addWidget(self.test_mic_button)
            test_buttons.addWidget(self.test_transcript_button)
            test_buttons.addWidget(self.preload_stt_button)

            self.transcript_test_output = QPlainTextEdit()
            self.transcript_test_output.setReadOnly(True)
            self.transcript_test_output.setPlaceholderText("麦克风测试和转录结果会显示在这里")

            layout.addWidget(QLabel("麦克风音量"))
            layout.addWidget(self.mic_volume_bar)
            layout.addWidget(self.mic_status)
            layout.addLayout(test_buttons)
            layout.addWidget(self.transcript_test_output, 1)
            return widget

        def _llm_tab(self) -> QWidget:
            widget = QWidget()
            form = QFormLayout(widget)
            self.llm_provider_combo = QComboBox()
            self.llm_provider_combo.addItem("OpenAI-compatible / DeepSeek", "openai_compatible")
            index = self.llm_provider_combo.findData(self.service.settings.llm_provider)
            if index >= 0:
                self.llm_provider_combo.setCurrentIndex(index)
            self.base_url_input = QLineEdit(self.service.settings.llm_base_url)
            self.model_input = QLineEdit(self.service.settings.llm_model)
            self.api_key_input = QLineEdit(self.service.settings.llm_api_key)
            self.api_key_input.setEchoMode(QLineEdit.EchoMode.Password)
            self.temperature_input = QDoubleSpinBox()
            self.temperature_input.setRange(0.0, 2.0)
            self.temperature_input.setSingleStep(0.1)
            self.temperature_input.setDecimals(2)
            self.temperature_input.setValue(float(self.service.settings.llm_temperature))
            self.timeout_input = QSpinBox()
            self.timeout_input.setRange(5, 600)
            self.timeout_input.setValue(int(self.service.settings.llm_timeout_seconds))

            save_button = QPushButton("保存 LLM 配置")
            save_button.clicked.connect(self._save_llm)

            form.addRow("Provider", self.llm_provider_combo)
            form.addRow("LLM Base URL", self.base_url_input)
            form.addRow("LLM Model", self.model_input)
            form.addRow("API Key", self.api_key_input)
            form.addRow("Temperature", self.temperature_input)
            form.addRow("Timeout 秒", self.timeout_input)
            form.addRow("", save_button)
            return widget

        def _history_tab(self) -> QWidget:
            widget = QWidget()
            layout = QVBoxLayout(widget)
            self.history_list = QListWidget()
            for session in self.service.history.recent_sessions():
                self.history_list.addItem(
                    f"{session['updated_at']}  [{session['mode_id']}]  {session['title']}"
                )
            clear_button = QPushButton("清空历史")
            clear_button.clicked.connect(self._clear_history)
            layout.addWidget(self.history_list)
            layout.addWidget(clear_button)
            return widget

        def _modes_tab(self) -> QWidget:
            widget = QWidget()
            layout = QVBoxLayout(widget)
            form = QFormLayout()
            self.default_mode_combo = QComboBox()
            for mode in self.service.modes.all():
                self.default_mode_combo.addItem(f"{mode.name} - {mode.description}", mode.id)
                if mode.id == self.service.settings.mode_id:
                    self.default_mode_combo.setCurrentIndex(self.default_mode_combo.count() - 1)
            save_button = QPushButton("保存默认模式")
            save_button.clicked.connect(self._save_default_mode)
            form.addRow("默认模式", self.default_mode_combo)
            form.addRow("", save_button)

            self.modes_list = QListWidget()
            for mode in self.service.modes.all():
                self.modes_list.addItem(f"{mode.id} | {mode.name} | {mode.target}")

            layout.addLayout(form)
            layout.addWidget(QLabel("已加载 Modes"))
            layout.addWidget(self.modes_list, 1)
            return widget

        def _load_audio_devices(self) -> None:
            self.device_combo.clear()
            self.device_combo.addItem("默认输入设备", None)
            default_warning = ""
            try:
                for device in AudioRecorder.list_input_devices():
                    label = (
                        f"{device.index}: {device.name} "
                        f"({device.max_input_channels}ch, {device.default_sample_rate}Hz)"
                    )
                    if device.is_default_input:
                        label += " 默认"
                        if "立体声混音" in device.name or "stereo mix" in device.name.lower():
                            label += "，可能不是麦克风"
                            default_warning = (
                                "当前系统默认输入设备像是立体声混音。"
                                "如果按 Space 没有录到人声，请选择具体的麦克风设备。"
                            )
                    self.device_combo.addItem(label, device.index)
                    if device.index == self.service.settings.input_device_index:
                        self.device_combo.setCurrentIndex(self.device_combo.count() - 1)
                if self.device_combo.count() == 1:
                    self.device_combo.addItem("未发现输入设备", None)
                self.default_device_warning = default_warning
                if hasattr(self, "mic_status") and default_warning:
                    self.mic_status.setText(default_warning)
            except Exception as exc:
                self.device_combo.addItem(f"无法读取设备: {exc}", None)

        def _choose_model_cache_dir(self) -> None:
            path = QFileDialog.getExistingDirectory(
                self,
                "选择模型缓存目录",
                self.model_cache_input.text().strip() or str(self.service.settings.model_cache_dir or ""),
            )
            if path:
                self.model_cache_input.setText(path)

        def _save_general(self) -> None:
            self.service.settings.hotkey = self.hotkey_input.text().strip() or self.service.settings.hotkey
            self.service.settings.push_to_talk_key = (
                self.push_to_talk_input.text().strip() or self.service.settings.push_to_talk_key
            )
            self.service.settings.auto_copy = self.auto_copy_checkbox.isChecked()
            self.service.settings.save_history = self.save_history_checkbox.isChecked()
            self.settings_store.save(self.service.settings)
            QMessageBox.information(self, "已保存", "快捷键和行为已保存。快捷键变更需要重启应用生效。")

        def _save_speech(self) -> None:
            self._apply_speech_settings()
            QMessageBox.information(self, "已保存", "语音转录设置已保存。")

        def _apply_speech_settings(self) -> None:
            self.service.settings.input_device_index = self.device_combo.currentData()
            cache_text = self.model_cache_input.text().strip()
            if cache_text:
                self.service.settings.model_cache_dir = Path(cache_text)
            self.service.set_stt_provider(self.stt_combo.currentData())
            self.settings_store.save(self.service.settings)

        def _save_llm(self) -> None:
            self.service.settings.llm_provider = self.llm_provider_combo.currentData()
            self.service.settings.llm_base_url = self.base_url_input.text().strip()
            self.service.settings.llm_model = self.model_input.text().strip()
            self.service.settings.llm_api_key = self.api_key_input.text().strip()
            self.service.settings.llm_temperature = float(self.temperature_input.value())
            self.service.settings.llm_timeout_seconds = int(self.timeout_input.value())
            self.service.compiler = self.service.compiler.__class__(self.service._build_llm())
            self.settings_store.save(self.service.settings)
            QMessageBox.information(self, "已保存", "LLM 配置已保存并已应用。")

        def _save_default_mode(self) -> None:
            mode_id = self.default_mode_combo.currentData()
            if mode_id:
                self.service.settings.mode_id = mode_id
                self.service.set_mode(mode_id)
                self.settings_store.save(self.service.settings)
            QMessageBox.information(self, "已保存", "默认模式已保存。")

        def _test_microphone(self) -> None:
            if self.test_recorder is not None:
                return
            self._apply_speech_settings()
            self.test_mic_button.setEnabled(False)
            self.mic_status.setText("正在录音 3 秒，请对着当前麦克风说话")
            self.transcript_test_output.clear()
            self.mic_volume_bar.setValue(0)

            def work() -> None:
                recorder: AudioRecorder | None = None
                try:
                    recorder = AudioRecorder(
                        input_device_index=self.service.settings.input_device_index,
                        volume_callback=self.bridge.mic_volume.emit,
                    )
                    self.test_recorder = recorder
                    recorder.start()
                    time.sleep(3)
                    result = recorder.stop(min_duration_seconds=0.1, min_average_volume=0)
                    self.last_test_wav = result.wav_path
                    message = (
                        f"麦克风测试完成\n"
                        f"时长: {result.duration_seconds:.2f}s\n"
                        f"平均音量: {result.average_volume:.0f}\n"
                        f"最大音量: {result.max_volume}\n"
                        f"测试音频: {result.wav_path}\n"
                    )
                    if result.average_volume < 40:
                        message += "\n音量很低：请检查系统麦克风权限、输入设备和音量。"
                    self.bridge.mic_done.emit(message)
                except Exception as exc:
                    self.bridge.mic_error.emit(str(exc))
                finally:
                    self.test_recorder = None

            threading.Thread(target=work, daemon=True).start()

        def _test_transcription(self) -> None:
            if not self.last_test_wav or not self.last_test_wav.exists():
                self.transcript_test_output.setPlainText("请先完成一次麦克风测试，再测试转录。")
                return
            self.test_transcript_button.setEnabled(False)
            self.transcript_test_output.setPlainText(
                "正在转录测试音频...\n首次加载模型可能需要下载和初始化，请等待。"
            )

            def work() -> None:
                try:
                    text = self.service.transcribe(
                        self.last_test_wav,
                        on_status=self.bridge.stt_status.emit,
                    )
                    self.bridge.transcript_done.emit(text or "SenseVoice-Small 未识别到有效语音。")
                except Exception as exc:
                    self.bridge.transcript_error.emit(str(exc))

            threading.Thread(target=work, daemon=True).start()

        def _preload_transcriber(self) -> None:
            self.preload_stt_button.setEnabled(False)
            self.transcript_test_output.setPlainText("正在预加载转录模型，首次可能需要下载和初始化...")

            def work() -> None:
                try:
                    self.service.warm_up_transcriber(on_status=self.bridge.stt_status.emit)
                    self.bridge.transcript_done.emit("转录模型已就绪。现在回到主窗口录音会更快。")
                except Exception as exc:
                    self.bridge.transcript_error.emit(str(exc))

            threading.Thread(target=work, daemon=True).start()

        def _on_mic_volume(self, volume: float) -> None:
            self.mic_volume_bar.setValue(min(int(volume), self.mic_volume_bar.maximum()))
            self.mic_volume_bar.setFormat(f"{volume:.0f}")

        def _on_mic_done(self, message: str) -> None:
            self.test_mic_button.setEnabled(True)
            self.mic_status.setText("麦克风测试完成")
            self.transcript_test_output.setPlainText(message)

        def _on_mic_error(self, message: str) -> None:
            self.test_mic_button.setEnabled(True)
            self.mic_status.setText("麦克风测试失败")
            self.transcript_test_output.setPlainText(message)

        def _on_transcript_done(self, text: str) -> None:
            self.test_transcript_button.setEnabled(True)
            self.preload_stt_button.setEnabled(True)
            self.transcript_test_output.setPlainText(f"转录结果：\n{text}")

        def _on_transcript_error(self, message: str) -> None:
            self.test_transcript_button.setEnabled(True)
            self.preload_stt_button.setEnabled(True)
            self.transcript_test_output.setPlainText(
                "转录失败：\n"
                f"{message}\n\n"
                "SenseVoice-Small 需要 funasr、modelscope 和 torch。"
            )

        def _on_stt_status(self, message: str) -> None:
            current = self.transcript_test_output.toPlainText().strip()
            if current:
                self.transcript_test_output.setPlainText(f"{current}\n{message}")
            else:
                self.transcript_test_output.setPlainText(message)

        def _clear_history(self) -> None:
            self.service.history.clear()
            self.history_list.clear()


    class FloatingWindow(QWidget):
        def __init__(self) -> None:
            super().__init__()
            self.service = AgentVoiceService()
            self.bridge = UiBridge()
            self.recorder: AudioRecorder | None = None
            self.compiled_text = ""
            self.hotkey_listener = None

            self.bridge.volume_changed.connect(self._on_volume)
            self.bridge.transcript_ready.connect(self._on_transcript)
            self.bridge.compile_chunk.connect(self._on_compile_chunk)
            self.bridge.compile_done.connect(self._on_compile_done)
            self.bridge.error.connect(self._on_error)
            self.bridge.show_requested.connect(self.toggle_visible)
            self.bridge.stt_status.connect(self._on_stt_status)

            self._build_ui()
            self._install_shortcuts()
            self._start_global_hotkey()
            self._install_space_capture()
            self.service.warm_up_transcriber_background(on_status=self.bridge.stt_status.emit)

        def _build_ui(self) -> None:
            self.setWindowFlags(Qt.WindowType.Window)
            self.setWindowTitle("AgentVoice")
            self.resize(620, 420)
            self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

            root = QVBoxLayout(self)
            root.setContentsMargins(10, 10, 10, 10)
            root.setSpacing(8)

            top = QHBoxLayout()
            self.mode_combo = QComboBox()
            for mode in self.service.modes.all():
                self.mode_combo.addItem(mode.name, mode.id)
                if mode.id == self.service.current_session.mode_id:
                    self.mode_combo.setCurrentIndex(self.mode_combo.count() - 1)
            self.mode_combo.currentIndexChanged.connect(self._mode_changed)

            settings_button = QPushButton("设置")
            settings_button.clicked.connect(self._open_settings)
            new_button = QPushButton("新会话")
            new_button.clicked.connect(self._new_session)
            quit_button = QPushButton("退出")
            quit_button.clicked.connect(self._quit_app)
            self.status_label = QLabel("准备就绪")

            top.addWidget(QLabel("模式"))
            top.addWidget(self.mode_combo, 1)
            top.addWidget(self.status_label)
            top.addWidget(settings_button)
            top.addWidget(new_button)
            top.addWidget(quit_button)
            root.addLayout(top)

            self.transcript_edit = QPlainTextEdit()
            self.transcript_edit.setPlaceholderText("原始转录")
            self.transcript_edit.setReadOnly(True)
            self.transcript_edit.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            self.compiled_edit = QPlainTextEdit()
            self.compiled_edit.setPlaceholderText("AI 编译结果")
            self.compiled_edit.setReadOnly(True)
            self.compiled_edit.setFocusPolicy(Qt.FocusPolicy.NoFocus)

            compiled_header = QHBoxLayout()
            compiled_header.addWidget(QLabel("AI 编译结果"))
            compiled_header.addStretch()
            self.copy_button = QPushButton("复制")
            self.copy_button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            self.copy_button.clicked.connect(self._copy_result)
            compiled_header.addWidget(self.copy_button)

            root.addWidget(QLabel("原始转录"))
            root.addWidget(self.transcript_edit, 1)
            root.addLayout(compiled_header)
            root.addWidget(self.compiled_edit, 1)

            hint = QLabel("Ctrl+Shift+Space 唤起 | 聚焦后长按 Space 录音 | Ctrl+N 新会话 | Ctrl+↑/↓ 切换模式 | Esc 隐藏")
            hint.setWordWrap(True)
            root.addWidget(hint)

            self.setStyleSheet(
                """
                QWidget { background: #f7f7f4; color: #1f2528; font-size: 13px; }
                QPlainTextEdit {
                    background: #ffffff;
                    border: 1px solid #d8ddd8;
                    border-radius: 6px;
                    padding: 8px;
                    selection-background-color: #b7d8cf;
                }
                QPushButton, QComboBox {
                    background: #ffffff;
                    border: 1px solid #cbd3cf;
                    border-radius: 6px;
                    padding: 5px 8px;
                }
                QPushButton:hover { background: #edf5f1; }
                QLabel { color: #2a3134; }
                """
            )

        def _install_space_capture(self) -> None:
            self.installEventFilter(self)
            self.transcript_edit.installEventFilter(self)
            self.transcript_edit.viewport().installEventFilter(self)
            self.compiled_edit.installEventFilter(self)
            self.compiled_edit.viewport().installEventFilter(self)
            self.mode_combo.installEventFilter(self)
            self.copy_button.installEventFilter(self)

        def _install_shortcuts(self) -> None:
            QShortcut("Ctrl+N", self, activated=self._new_session)
            QShortcut("Ctrl+Up", self, activated=lambda: self._shift_mode(-1))
            QShortcut("Ctrl+Down", self, activated=lambda: self._shift_mode(1))
            QShortcut("Ctrl+Q", self, activated=self._quit_app)
            QShortcut("Esc", self, activated=self.hide)
            QShortcut("Return", self, activated=lambda: (self._copy_result(), self.hide()))

        def _start_global_hotkey(self) -> None:
            try:
                from pynput import keyboard
            except ImportError:
                self.status_label.setText("准备就绪 (未安装 pynput，无法全局唤起)")
                return

            def on_show() -> None:
                self.bridge.show_requested.emit()

            self.hotkey_listener = keyboard.GlobalHotKeys({self.service.settings.hotkey: on_show})
            thread = threading.Thread(target=self.hotkey_listener.run, daemon=True)
            thread.start()

        def eventFilter(self, watched: QObject, event: QEvent) -> bool:
            if not self.isActiveWindow():
                return super().eventFilter(watched, event)
            if event.type() == QEvent.Type.KeyPress:
                if event.key() == Qt.Key.Key_Space and not event.isAutoRepeat():
                    self._start_recording()
                    return True
            if event.type() == QEvent.Type.KeyRelease:
                if event.key() == Qt.Key.Key_Space and not event.isAutoRepeat():
                    self._stop_recording()
                    return True
            return super().eventFilter(watched, event)

        def toggle_visible(self) -> None:
            if self.isVisible():
                self.hide()
            else:
                self.show()
                self.raise_()
                self.activateWindow()
                self.setFocus(Qt.FocusReason.ShortcutFocusReason)

        def keyPressEvent(self, event: QKeyEvent) -> None:
            if event.key() == Qt.Key.Key_Space and not event.isAutoRepeat():
                self._start_recording()
                event.accept()
                return
            super().keyPressEvent(event)

        def keyReleaseEvent(self, event: QKeyEvent) -> None:
            if event.key() == Qt.Key.Key_Space and not event.isAutoRepeat():
                self._stop_recording()
                event.accept()
                return
            super().keyReleaseEvent(event)

        def _start_recording(self) -> None:
            if self.recorder is not None:
                return
            self.status_label.setText("正在录音")
            self.copy_button.setText("复制")
            try:
                self.recorder = AudioRecorder(
                    input_device_index=self.service.settings.input_device_index,
                    volume_callback=self.bridge.volume_changed.emit,
                )
                self.recorder.start()
            except Exception as exc:
                self.recorder = None
                self._on_error(str(exc))

        def _stop_recording(self) -> None:
            if self.recorder is None:
                return
            recorder = self.recorder
            self.recorder = None
            self.status_label.setText("正在转录")

            def work() -> None:
                wav_path: Path | None = None
                try:
                    result = recorder.stop()
                    wav_path = result.wav_path
                    transcript = self.service.transcribe(
                        result.wav_path,
                        on_status=self.bridge.stt_status.emit,
                    )
                    self.bridge.transcript_ready.emit(transcript.strip())
                    self.bridge.stt_status.emit("正在整理")
                    compiled = self.service.compile_transcript(
                        transcript,
                        on_chunk=self.bridge.compile_chunk.emit,
                    )
                    self.bridge.compile_done.emit(compiled)
                except Exception as exc:
                    self.bridge.error.emit(str(exc))
                finally:
                    if wav_path and wav_path.exists():
                        wav_path.unlink(missing_ok=True)

            self.compiled_text = ""
            self.compiled_edit.clear()
            threading.Thread(target=work, daemon=True).start()

        def _on_volume(self, volume: float) -> None:
            self.status_label.setText(f"录音中 {volume:.0f}")

        def _on_transcript(self, text: str) -> None:
            self.transcript_edit.setPlainText(text)

        def _on_compile_chunk(self, chunk: str) -> None:
            if self.status_label.text() != "正在整理":
                self.status_label.setText("正在整理")
            self.compiled_text += chunk
            self.compiled_edit.setPlainText(self.compiled_text)
            self.compiled_edit.verticalScrollBar().setValue(self.compiled_edit.verticalScrollBar().maximum())

        def _on_compile_done(self, text: str) -> None:
            self.compiled_text = text
            self.compiled_edit.setPlainText(text)
            if self.service.settings.auto_copy:
                self._copy_result()
                self.status_label.setText("已复制")
            else:
                self.status_label.setText("整理完成")

        def _on_error(self, message: str) -> None:
            self.status_label.setText(message)

        def _on_stt_status(self, message: str) -> None:
            self.status_label.setText(message)

        def _copy_result(self) -> None:
            text = self.compiled_edit.toPlainText().strip()
            if not text:
                return
            QApplication.clipboard().setText(text)
            self.copy_button.setText("已复制")

        def _new_session(self) -> None:
            self.service.new_session(self.mode_combo.currentData())
            self.transcript_edit.clear()
            self.compiled_edit.clear()
            self.compiled_text = ""
            self.status_label.setText("新会话")
            self.copy_button.setText("复制")

        def _mode_changed(self) -> None:
            mode_id = self.mode_combo.currentData()
            if mode_id:
                self.service.set_mode(mode_id)
                self.status_label.setText(f"模式: {self.service.current_mode.name}")

        def _shift_mode(self, delta: int) -> None:
            count = self.mode_combo.count()
            if count == 0:
                return
            self.mode_combo.setCurrentIndex((self.mode_combo.currentIndex() + delta) % count)

        def _open_settings(self) -> None:
            if hasattr(self, "settings_dialog") and self.settings_dialog.isVisible():
                self.settings_dialog.raise_()
                self.settings_dialog.activateWindow()
                return
            self.settings_dialog = SettingsDialog(self.service)
            self.settings_dialog.show()

        def _quit_app(self) -> None:
            if self.hotkey_listener:
                try:
                    self.hotkey_listener.stop()
                except Exception:
                    pass
            QApplication.quit()

        def closeEvent(self, event) -> None:
            self._quit_app()
            event.accept()


def main() -> int:
    if not QT_AVAILABLE:
        print("PySide6 is not installed. Run: pip install PySide6")
        return 1
    app = QApplication(sys.argv)
    window = FloatingWindow()
    window.show()
    return app.exec()
