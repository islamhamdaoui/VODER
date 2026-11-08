import sys
import os
import subprocess
import platform
import re
import time
import wave


def audio_seconds(path):
    """Length of a WAV file in seconds, or 0 when it cannot be read."""
    try:
        with wave.open(path, "rb") as handle:
            rate = handle.getframerate() or 0
            if not rate:
                return 0.0
            return handle.getnframes() / float(rate)
    except Exception:
        return 0.0

def _q(v):
    if not v:
        return '""'
    if re.match(r'^[a-zA-Z0-9_\.\-/]+$', v):
        return v
    return '"' + v.replace('"', '\\"') + '"'

from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
                             QHBoxLayout, QLabel, QPushButton, QFileDialog,
                             QMessageBox, QProgressBar, QFrame, QComboBox,
                             QTextEdit, QListWidget, QListWidgetItem, QLineEdit,
                             QSpinBox, QScrollArea, QCheckBox, QRadioButton,
                             QStackedWidget, QDoubleSpinBox, QShortcut, QSlider,
                             QSizePolicy, QGridLayout, QInputDialog)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QTimer, QSize
from PyQt5.QtGui import QColor, QPainter, QPalette, QKeySequence, QFont

try:
    import numpy as np
    HAS_NUMPY = True
except Exception:
    HAS_NUMPY = False

try:
    import torchaudio
    HAS_TORCHAUDIO = True
except Exception:
    HAS_TORCHAUDIO = False

_src_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _src_dir not in sys.path:
    sys.path.insert(0, _src_dir)

# VODER lives in <repo>/app/src; the repo folder is where voices/ and results/
# are kept by the launcher (voder.bat), so always use it as the working folder.
VODER_ROOT = os.path.dirname(os.path.dirname(_src_dir))

from voders import voice_library as vlib


def voice_kind_tag(kinds):
    """Readable label for the engines a voice name has a profile for."""
    labels = []
    if vlib.KIND_STANDARD in kinds:
        labels.append("Standard")
    if vlib.KIND_ENHANCED in kinds:
        labels.append("Enhanced")
    if vlib.KIND_DARIJA in kinds:
        labels.append("Darija")
    return " + ".join(labels) or "Standard"


THEME = {
    'background': '#0D0D0D',
    'surface': '#151515',
    'surface_hover': '#1E1E1E',
    'surface_active': '#282828',
    'text': '#F0F0F0',
    'text_secondary': '#808080',
    'accent': '#FFFFFF',
    'accent_hover': '#E8E8E8',
    'accent_pressed': '#D0D0D0',
    'accent_disabled': '#555555',
    'border': '#2A2A2A',
    'border_light': '#3A3A3A',
    'border_disabled': '#222222',
    'error': '#FF4444',
    'warning': '#FF9800',
    'success': '#FFFFFF',
    'panel_background': '#111111',
    'panel_border': '#2A2A2A',
    'sidebar_background': '#0A0A0A',
    'sidebar_item_hover': '#1A1A1A',
    'sidebar_item_active': '#FFFFFF',
}

def contrast_color(bg_hex):
    hex_clean = bg_hex.lstrip('#')
    if len(hex_clean) != 6:
        return '#000000'
    r = int(hex_clean[0:2], 16)
    g = int(hex_clean[2:4], 16)
    b = int(hex_clean[4:6], 16)
    luminance = (0.299 * r + 0.587 * g + 0.114 * b) / 255
    return '#000000' if luminance > 0.5 else '#FFFFFF'

def get_main_button_style():
    return f"""
        QPushButton {{
            background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                stop:0 {THEME['surface']}, stop:0.3 {THEME['surface']}, stop:0.7 {THEME['surface_hover']}, stop:1 {THEME['surface']});
            border: 2px solid {THEME['accent']};
            border-radius: 8px;
            font-size: 14px;
            font-weight: bold;
            color: {THEME['accent']};
            padding: 8px 16px;
        }}
        QPushButton:hover {{
            background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                stop:0 {THEME['surface']}, stop:0.3 {THEME['surface_hover']}, stop:0.7 {THEME['surface_active']}, stop:1 {THEME['surface']});
            border: 2px solid {THEME['accent']};
        }}
        QPushButton:pressed {{
            background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                stop:0 {THEME['surface_hover']}, stop:0.3 {THEME['surface_active']}, stop:0.7 {THEME['surface_hover']}, stop:1 {THEME['surface_hover']});
            border: 2px solid {THEME['accent_hover']};
        }}
        QPushButton:disabled {{
            background-color: {THEME['surface']};
            border: 2px solid {THEME['border_disabled']};
            color: {THEME['accent_disabled']};
        }}
    """

def get_secondary_button_style():
    return get_main_button_style()

def get_surface_button_style():
    return f"""
        QPushButton {{
            background-color: {THEME['surface']};
            color: {THEME['text']};
            border: 1px solid {THEME['border_light']};
            border-radius: 6px;
            font-size: 12px;
            padding: 6px 12px;
        }}
        QPushButton:hover {{
            background-color: {THEME['surface_hover']};
            border: 1px solid {THEME['accent']};
        }}
        QPushButton:pressed {{
            background-color: {THEME['surface_active']};
            border: 1px solid {THEME['accent']};
        }}
        QPushButton:disabled {{
            background-color: {THEME['surface']};
            border: 1px solid {THEME['border_disabled']};
            color: {THEME['accent_disabled']};
        }}
    """

def get_panel_style():
    return f"""
        QFrame {{
            background-color: {THEME['panel_background']};
            border: 1px solid {THEME['panel_border']};
            border-radius: 8px;
        }}
    """

def get_title_label_style():
    return f"""
        color: {THEME['text']};
        font-weight: bold;
        font-size: 16px;
    """

def get_subtitle_label_style():
    return f"""
        color: {THEME['text_secondary']};
        font-size: 12px;
    """

def get_status_bar_style():
    return f"""
        color: {THEME['text_secondary']};
        padding: 6px 12px;
        font-size: 12px;
    """

def get_progress_bar_style():
    return f"""
        QProgressBar {{
            border: 1px solid {THEME['border']};
            background-color: {THEME['surface']};
            height: 8px;
            border-radius: 4px;
            text-align: center;
            color: {THEME['text_secondary']};
        }}
        QProgressBar::chunk {{
            background-color: {THEME['accent']};
            border-radius: 3px;
        }}
    """

def get_window_style():
    return f"""
        background-color: {THEME['background']};
        color: {THEME['text']};
    """

def get_text_edit_style():
    return f"""
        QTextEdit {{
            background-color: {THEME['surface']};
            color: {THEME['text']};
            border: 1px solid {THEME['border']};
            border-radius: 6px;
            font-family: 'Consolas', 'Monaco', monospace;
            font-size: 13px;
            padding: 8px;
        }}
        QTextEdit:focus {{
            border: 1px solid {THEME['accent']};
        }}
    """

def get_combo_box_style():
    return f"""
        QComboBox {{
            background-color: {THEME['surface']};
            color: {THEME['text']};
            border: 1px solid {THEME['border_light']};
            border-radius: 6px;
            padding: 6px 12px;
            min-width: 80px;
            font-size: 13px;
            selection-background-color: {THEME['surface_hover']};
            selection-color: {THEME['text']};
        }}
        QComboBox::drop-down {{
            border: none;
            subcontrol-origin: padding;
            subcontrol-position: right center;
            width: 24px;
        }}
        QComboBox::down-arrow {{
            image: none();
            width: 0px;
            height: 0px;
        }}
        QComboBox:hover {{
            border: 1px solid {THEME['accent']};
        }}
        QComboBox:disabled {{
            background-color: {THEME['surface']};
            border: 1px solid {THEME['border_disabled']};
            color: {THEME['accent_disabled']};
        }}
        QComboBox QAbstractItemView {{
            background-color: {THEME['surface']};
            color: {THEME['text']};
            border: 1px solid {THEME['border_light']};
            border-radius: 4px;
            selection-background-color: {THEME['surface_hover']};
            selection-color: {THEME['text']};
        }}
    """

def get_line_edit_style():
    return f"""
        QLineEdit {{
            background-color: {THEME['surface']};
            color: {THEME['text']};
            border: 1px solid {THEME['border']};
            border-radius: 6px;
            padding: 6px 8px;
            font-size: 13px;
        }}
        QLineEdit:focus {{
            border: 1px solid {THEME['accent']};
        }}
        QLineEdit:disabled {{
            background-color: {THEME['surface']};
            border: 1px solid {THEME['border_disabled']};
            color: {THEME['accent_disabled']};
        }}
    """

def get_list_widget_style():
    return f"""
        QListWidget {{
            background-color: {THEME['surface']};
            color: {THEME['text']};
            border: 1px solid {THEME['border']};
            border-radius: 4px;
            font-size: 12px;
        }}
        QListWidget::item {{
            padding: 4px;
            border-bottom: 1px solid {THEME['border']};
        }}
        QListWidget::item:selected {{
            background-color: {THEME['sidebar_item_active']};
            color: {contrast_color(THEME['sidebar_item_active'])};
        }}
        QListWidget::item:hover {{
            background-color: {THEME['surface_hover']};
        }}
    """

def get_checkbox_style():
    return f"""
        QCheckBox {{
            color: {THEME['text']};
            font-size: 13px;
            spacing: 8px;
        }}
        QCheckBox::indicator {{
            width: 18px;
            height: 18px;
            border: 2px solid {THEME['border_light']};
            border-radius: 4px;
            background-color: {THEME['surface']};
        }}
        QCheckBox::indicator:checked {{
            background-color: {THEME['accent']};
            border: 2px solid {THEME['accent']};
            color: {contrast_color(THEME['accent'])};
        }}
        QCheckBox::indicator:hover {{
            border: 2px solid {THEME['accent']};
        }}
    """

def get_group_box_style():
    return f"""
        QGroupBox {{
            color: {THEME['text']};
            font-weight: bold;
            font-size: 13px;
            border: 1px solid {THEME['border']};
            border-radius: 6px;
            margin-top: 12px;
            padding-top: 16px;
        }}
        QGroupBox::title {{
            subcontrol-origin: margin;
            left: 12px;
            padding: 0 6px;
        }}
    """

def get_radio_button_style():
    return f"""
        QRadioButton {{
            color: {THEME['text']};
            font-size: 13px;
            spacing: 8px;
        }}
        QRadioButton::indicator {{
            width: 18px;
            height: 18px;
            border: 2px solid {THEME['border_light']};
            border-radius: 9px;
            background-color: {THEME['surface']};
        }}
        QRadioButton::indicator:checked {{
            background-color: {THEME['accent']};
            border: 2px solid {THEME['accent']};
            color: {contrast_color(THEME['accent'])};
        }}
    """

def get_spin_box_style():
    return f"""
        QSpinBox, QDoubleSpinBox {{
            background-color: {THEME['surface']};
            color: {THEME['text']};
            border: 1px solid {THEME['border']};
            border-radius: 6px;
            padding: 4px 8px;
            font-size: 13px;
        }}
        QSpinBox:focus, QDoubleSpinBox:focus {{
            border: 1px solid {THEME['accent']};
        }}
        QSpinBox::up-button, QSpinBox::down-button,
        QDoubleSpinBox::up-button, QDoubleSpinBox::down-button {{
            background-color: {THEME['surface_hover']};
            border: 1px solid {THEME['border']};
            width: 16px;
        }}
    """

def get_slider_style():
    return f"""
        QSlider::groove:horizontal {{
            border: 1px solid {THEME['border']};
            height: 6px;
            background: {THEME['surface']};
            border-radius: 3px;
        }}
        QSlider::handle:horizontal {{
            background: {THEME['accent']};
            border: none;
            width: 14px;
            margin: -5px 0;
            border-radius: 7px;
        }}
        QSlider::sub-page:horizontal {{
            background: {THEME['accent']};
            border-radius: 3px;
        }}
    """


class AudioWaveformWidget(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(60)
        self.setMaximumHeight(80)
        self.setStyleSheet(f"background-color: {THEME['surface']}; border: 1px solid {THEME['border']};")
        self.audio_data = None
        self.sample_rate = 44100

    def set_audio(self, audio_path):
        if audio_path and os.path.exists(audio_path) and HAS_TORCHAUDIO and HAS_NUMPY:
            try:
                waveform, sample_rate = torchaudio.load(audio_path)
                self.audio_data = waveform[0].numpy()
                self.sample_rate = sample_rate
                self.update()
            except Exception:
                self.audio_data = None
                self.update()
        else:
            self.audio_data = None
            self.update()

    def get_duration(self):
        if self.audio_data is not None and self.sample_rate > 0:
            return len(self.audio_data) / self.sample_rate
        return 0.0

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        width = self.width()
        height = self.height()
        painter.fillRect(self.rect(), QColor(THEME['surface']))
        if self.audio_data is None:
            painter.setPen(QColor(THEME['text_secondary']))
            painter.drawText(self.rect(), Qt.AlignCenter, "No Audio")
            return
        painter.setPen(QColor(THEME['accent']))
        samples = len(self.audio_data)
        if samples == 0:
            return
        step = max(1, samples // width)
        for x in range(width):
            start_idx = x * step
            end_idx = min(start_idx + step, samples)
            if start_idx < samples:
                chunk = self.audio_data[start_idx:end_idx]
                max_val = np.max(np.abs(chunk))
                y_center = height // 2
                y_offset = int(max_val * (height // 2) * 0.9)
                painter.drawLine(x, y_center - y_offset, x, y_center + y_offset)


class SubprocessThread(QThread):
    output_signal = pyqtSignal(str)
    finished_signal = pyqtSignal(int, str)

    def __init__(self, command_args):
        super().__init__()
        self.command_args = command_args
        self.process = None

    def run(self):
        python = sys.executable
        voder_path = os.path.join(_src_dir, 'voder.py')
        cmd = [python, "-u", voder_path] + self.command_args
        try:
            self.process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                cwd=VODER_ROOT,
                bufsize=1
            )
            output_lines = []
            for line in self.process.stdout:
                line = line.rstrip('\n')
                output_lines.append(line)
                self.output_signal.emit(line)
            self.process.wait()
            full_output = '\n'.join(output_lines)
            self.finished_signal.emit(self.process.returncode, full_output)
        except Exception as e:
            self.output_signal.emit(f"Error launching process: {e}")
            self.finished_signal.emit(1, str(e))

    def stop(self):
        if self.process:
            self.process.terminate()
            try:
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.process.kill()


class AudioPlayerThread(QThread):
    finished_signal = pyqtSignal()

    def __init__(self, path, speed=1.0):
        super().__init__()
        self.path = path
        self.speed = speed
        self.process = None

    def run(self):
        if not self.path or not os.path.exists(self.path):
            self.finished_signal.emit()
            return
        try:
            system = platform.system()
            if system == "Darwin":
                cmd = ["afplay", self.path]
                if self.speed != 1.0:
                    cmd.insert(1, "-r")
                    cmd.insert(2, str(self.speed))
                self.process = subprocess.Popen(cmd)
            elif system == "Windows":
                os.startfile(self.path)
                self.process = None
            else:
                self.process = subprocess.Popen(
                    ["aplay", self.path],
                    stderr=subprocess.DEVNULL
                )
            if self.process:
                self.process.wait()
        except Exception:
            pass
        self.finished_signal.emit()

    def stop(self):
        if self.process:
            self.process.terminate()
            try:
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.process.kill()


class AudioReferenceWidget(QWidget):
    path_changed = pyqtSignal(str)

    def __init__(self, label_text="Audio Reference", file_filter="Audio Files (*.wav *.mp3 *.flac *.ogg);;Video Files (*.mp4 *.avi *.mov *.mkv);;All Files (*)", parent=None):
        super().__init__(parent)
        self._file_filter = file_filter
        self._player_thread = None
        self._playing = False
        self._duration = 0.0
        self._setup_ui(label_text)

    def _setup_ui(self, label_text):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        path_row = QHBoxLayout()
        path_row.setSpacing(4)
        lbl = QLabel(label_text)
        lbl.setStyleSheet(f"color: {THEME['text']}; font-size: 13px; min-width: 100px;")
        self.path_edit = QLineEdit()
        self.path_edit.setPlaceholderText("Select audio file or enter URL...")
        self.path_edit.setStyleSheet(get_line_edit_style())
        self.path_edit.textChanged.connect(self._on_path_changed)
        browse_btn = QPushButton("Browse")
        browse_btn.setStyleSheet(get_surface_button_style())
        browse_btn.setCursor(Qt.PointingHandCursor)
        browse_btn.setFixedWidth(70)
        browse_btn.clicked.connect(self._browse)
        path_row.addWidget(lbl)
        path_row.addWidget(self.path_edit, stretch=1)
        path_row.addWidget(browse_btn)
        layout.addLayout(path_row)

        self.waveform = AudioWaveformWidget()
        self.waveform.setFixedHeight(40)
        self.waveform.setMaximumHeight(50)
        layout.addWidget(self.waveform)

        controls_row = QHBoxLayout()
        controls_row.setSpacing(6)
        self.play_btn = QPushButton("Play")
        self.play_btn.setStyleSheet(get_surface_button_style())
        self.play_btn.setCursor(Qt.PointingHandCursor)
        self.play_btn.setFixedWidth(60)
        self.play_btn.clicked.connect(self._toggle_play)
        controls_row.addWidget(self.play_btn)

        self.seek_slider = QSlider(Qt.Horizontal)
        self.seek_slider.setStyleSheet(get_slider_style())
        self.seek_slider.setRange(0, 1000)
        self.seek_slider.setValue(0)
        controls_row.addWidget(self.seek_slider, stretch=1)

        self.duration_label = QLabel("0:00")
        self.duration_label.setStyleSheet(f"color: {THEME['text_secondary']}; font-size: 11px;")
        self.duration_label.setFixedWidth(40)
        controls_row.addWidget(self.duration_label)

        speed_lbl = QLabel("Speed:")
        speed_lbl.setStyleSheet(f"color: {THEME['text_secondary']}; font-size: 11px;")
        controls_row.addWidget(speed_lbl)
        self.speed_combo = QComboBox()
        self.speed_combo.setStyleSheet(get_combo_box_style())
        self.speed_combo.addItems(["25%", "50%", "75%", "100%", "125%", "150%", "175%", "200%"])
        self.speed_combo.setCurrentIndex(3)
        self.speed_combo.setFixedWidth(75)
        controls_row.addWidget(self.speed_combo)
        layout.addLayout(controls_row)

    def _browse(self):
        path, _ = QFileDialog.getOpenFileName(None, "Select Audio File", "", self._file_filter)
        if path:
            self.path_edit.setText(path)

    def _on_path_changed(self, path):
        self.waveform.set_audio(path)
        self._duration = self.waveform.get_duration()
        if self._duration > 0:
            mins = int(self._duration // 60)
            secs = int(self._duration % 60)
            self.duration_label.setText(f"{mins}:{secs:02d}")
        else:
            self.duration_label.setText("0:00")
        self.path_changed.emit(path)

    def _toggle_play(self):
        if self._playing:
            self._stop_play()
        else:
            self._start_play()

    def _start_play(self):
        path = self.path_edit.text().strip()
        if not path or not os.path.exists(path):
            return
        self._stop_play()
        speed_text = self.speed_combo.currentText().replace("%", "")
        try:
            speed = float(speed_text) / 100.0
        except ValueError:
            speed = 1.0
        self._player_thread = AudioPlayerThread(path, speed)
        self._player_thread.finished_signal.connect(self._on_play_finished)
        self._player_thread.start()
        self._playing = True
        self.play_btn.setText("Stop")

    def _stop_play(self):
        if self._player_thread:
            self._player_thread.stop()
            self._player_thread = None
        self._playing = False
        self.play_btn.setText("Play")

    def _on_play_finished(self):
        self._player_thread = None
        self._playing = False
        self.play_btn.setText("Play")

    def get_path(self):
        return self.path_edit.text().strip()

    def set_path(self, path):
        self.path_edit.setText(path)

    def text(self):
        return self.path_edit.text()


class HelperWidgets:

    @staticmethod
    def make_file_picker(parent_layout, label_text, placeholder="", file_filter="Audio Files (*.wav *.mp3 *.flac *.ogg);;Video Files (*.mp4 *.avi *.mov *.mkv);;All Files (*)"):
        row = QHBoxLayout()
        label = QLabel(label_text)
        label.setStyleSheet(f"color: {THEME['text']}; font-size: 13px; min-width: 90px;")
        line_edit = QLineEdit()
        line_edit.setPlaceholderText(placeholder)
        line_edit.setStyleSheet(get_line_edit_style())
        browse_btn = QPushButton("Browse")
        browse_btn.setStyleSheet(get_surface_button_style())
        browse_btn.setCursor(Qt.PointingHandCursor)
        browse_btn.setFixedWidth(80)

        def pick_file():
            path, _ = QFileDialog.getOpenFileName(None, "Select File", "", file_filter)
            if path:
                line_edit.setText(path)

        browse_btn.clicked.connect(pick_file)
        row.addWidget(label)
        row.addWidget(line_edit, stretch=1)
        row.addWidget(browse_btn)
        parent_layout.addLayout(row)
        return line_edit

    @staticmethod
    def make_save_picker(parent_layout, label_text, placeholder=""):
        row = QHBoxLayout()
        label = QLabel(label_text)
        label.setStyleSheet(f"color: {THEME['text']}; font-size: 13px; min-width: 90px;")
        line_edit = QLineEdit()
        line_edit.setPlaceholderText(placeholder)
        line_edit.setStyleSheet(get_line_edit_style())
        browse_btn = QPushButton("Browse")
        browse_btn.setStyleSheet(get_surface_button_style())
        browse_btn.setCursor(Qt.PointingHandCursor)
        browse_btn.setFixedWidth(80)

        def pick_file():
            path, _ = QFileDialog.getSaveFileName(None, "Save To", "", "WAV Files (*.wav);;All Files (*)")
            if path:
                line_edit.setText(path)

        browse_btn.clicked.connect(pick_file)
        row.addWidget(label)
        row.addWidget(line_edit, stretch=1)
        row.addWidget(browse_btn)
        parent_layout.addLayout(row)
        return line_edit

    @staticmethod
    def make_label(parent_layout, text):
        label = QLabel(text)
        label.setStyleSheet(f"color: {THEME['text']}; font-size: 13px;")
        parent_layout.addWidget(label)
        return label

    @staticmethod
    def make_subtitle(parent_layout, text):
        label = QLabel(text)
        label.setStyleSheet(get_subtitle_label_style())
        parent_layout.addWidget(label)
        return label

    @staticmethod
    def make_line_edit(parent_layout, label_text, placeholder=""):
        row = QHBoxLayout()
        label = QLabel(label_text)
        label.setStyleSheet(f"color: {THEME['text']}; font-size: 13px; min-width: 90px;")
        line_edit = QLineEdit()
        line_edit.setPlaceholderText(placeholder)
        line_edit.setStyleSheet(get_line_edit_style())
        row.addWidget(label)
        row.addWidget(line_edit, stretch=1)
        parent_layout.addLayout(row)
        return line_edit

    @staticmethod
    def make_text_edit(parent_layout, label_text, placeholder="", min_height=80):
        label = QLabel(label_text)
        label.setStyleSheet(f"color: {THEME['text']}; font-size: 13px;")
        parent_layout.addWidget(label)
        text_edit = QTextEdit()
        text_edit.setPlaceholderText(placeholder)
        text_edit.setStyleSheet(get_text_edit_style())
        text_edit.setMinimumHeight(min_height)
        text_edit.setMaximumHeight(min_height * 2)
        parent_layout.addWidget(text_edit)
        return text_edit

    @staticmethod
    def make_checkbox(parent_layout, text):
        checkbox = QCheckBox(text)
        checkbox.setStyleSheet(get_checkbox_style())
        parent_layout.addWidget(checkbox)
        return checkbox

    @staticmethod
    def make_spinbox(parent_layout, label_text, min_val=0, max_val=300, default=30):
        row = QHBoxLayout()
        label = QLabel(label_text)
        label.setStyleSheet(f"color: {THEME['text']}; font-size: 13px; min-width: 90px;")
        spinbox = QSpinBox()
        spinbox.setRange(min_val, max_val)
        spinbox.setValue(default)
        spinbox.setStyleSheet(get_spin_box_style())
        row.addWidget(label)
        row.addWidget(spinbox)
        row.addStretch()
        parent_layout.addLayout(row)
        return spinbox

    @staticmethod
    def make_double_spinbox(parent_layout, label_text, min_val=0.0, max_val=100.0, default=4.5, step=0.5, decimals=1):
        row = QHBoxLayout()
        label = QLabel(label_text)
        label.setStyleSheet(f"color: {THEME['text']}; font-size: 13px; min-width: 90px;")
        spinbox = QDoubleSpinBox()
        spinbox.setRange(min_val, max_val)
        spinbox.setValue(default)
        spinbox.setSingleStep(step)
        spinbox.setDecimals(decimals)
        spinbox.setStyleSheet(get_spin_box_style())
        row.addWidget(label)
        row.addWidget(spinbox)
        row.addStretch()
        parent_layout.addLayout(row)
        return spinbox

    @staticmethod
    def make_combo_row(parent_layout, label_text, items, default_index=0):
        row = QHBoxLayout()
        label = QLabel(label_text)
        label.setStyleSheet(f"color: {THEME['text']}; font-size: 13px; min-width: 90px;")
        combo = QComboBox()
        combo.setStyleSheet(get_combo_box_style())
        combo.addItems(items)
        if default_index < len(items):
            combo.setCurrentIndex(default_index)
        row.addWidget(label)
        row.addWidget(combo, stretch=1)
        row.addStretch()
        parent_layout.addLayout(row)
        return combo

    @staticmethod
    def make_separator(parent_layout):
        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setStyleSheet(f"color: {THEME['border']};")
        parent_layout.addWidget(line)

    @staticmethod
    def make_button(parent_layout, text, style=None):
        btn = QPushButton(text)
        btn.setStyleSheet(style or get_surface_button_style())
        btn.setCursor(Qt.PointingHandCursor)
        parent_layout.addWidget(btn)
        return btn

    @staticmethod
    def make_button_row(parent_layout, buttons_data):
        row = QHBoxLayout()
        btns = []
        for text, style in buttons_data:
            btn = QPushButton(text)
            btn.setStyleSheet(style or get_surface_button_style())
            btn.setCursor(Qt.PointingHandCursor)
            row.addWidget(btn)
            btns.append(btn)
        row.addStretch()
        parent_layout.addLayout(row)
        return btns


class DirectivesWidget(QWidget):
    def __init__(self, show_duration=False, parent=None):
        super().__init__(parent)
        self._show_duration = show_duration
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 2, 4, 2)
        layout.setSpacing(4)

        toggle_row = QHBoxLayout()
        toggle_row.setSpacing(4)
        self.toggle_btn = QPushButton("Directives \u25b8")
        self.toggle_btn.setStyleSheet(get_surface_button_style())
        self.toggle_btn.setCursor(Qt.PointingHandCursor)
        self.toggle_btn.setFixedHeight(22)
        self.toggle_btn.setFixedWidth(110)
        self.toggle_btn.clicked.connect(self._toggle_panel)
        toggle_row.addWidget(self.toggle_btn)
        toggle_row.addStretch()
        layout.addLayout(toggle_row)

        self.panel = QWidget()
        self.panel.setStyleSheet("background: transparent;")
        panel_layout = QHBoxLayout(self.panel)
        panel_layout.setContentsMargins(8, 4, 8, 4)
        panel_layout.setSpacing(8)

        self.time_pos_spin = QDoubleSpinBox()
        self.time_pos_spin.setRange(0.0, 9999.0)
        self.time_pos_spin.setValue(0.0)
        self.time_pos_spin.setSingleStep(0.5)
        self.time_pos_spin.setDecimals(1)
        self.time_pos_spin.setPrefix("T:")
        self.time_pos_spin.setSuffix("s")
        self.time_pos_spin.setStyleSheet(get_spin_box_style())
        self.time_pos_spin.setFixedWidth(90)
        self.time_pos_spin.setToolTip("Timeline Position (seconds)")
        panel_layout.addWidget(self.time_pos_spin)

        self.cut_start_spin = QDoubleSpinBox()
        self.cut_start_spin.setRange(0.0, 9999.0)
        self.cut_start_spin.setValue(0.0)
        self.cut_start_spin.setSingleStep(0.5)
        self.cut_start_spin.setDecimals(1)
        self.cut_start_spin.setPrefix("+")
        self.cut_start_spin.setSuffix("s")
        self.cut_start_spin.setStyleSheet(get_spin_box_style())
        self.cut_start_spin.setFixedWidth(80)
        self.cut_start_spin.setToolTip("Cut from Start (seconds)")
        panel_layout.addWidget(self.cut_start_spin)

        self.cut_end_spin = QDoubleSpinBox()
        self.cut_end_spin.setRange(0.0, 9999.0)
        self.cut_end_spin.setValue(0.0)
        self.cut_end_spin.setSingleStep(0.5)
        self.cut_end_spin.setDecimals(1)
        self.cut_end_spin.setPrefix("-")
        self.cut_end_spin.setSuffix("s")
        self.cut_end_spin.setStyleSheet(get_spin_box_style())
        self.cut_end_spin.setFixedWidth(80)
        self.cut_end_spin.setToolTip("Cut from End (seconds)")
        panel_layout.addWidget(self.cut_end_spin)

        self.level_spin = QSpinBox()
        self.level_spin.setRange(0, 100)
        self.level_spin.setValue(100)
        self.level_spin.setPrefix("L:")
        self.level_spin.setSuffix("%")
        self.level_spin.setStyleSheet(get_spin_box_style())
        self.level_spin.setFixedWidth(75)
        self.level_spin.setToolTip("Volume Level (0-100)")
        panel_layout.addWidget(self.level_spin)

        self.duration_spin = QSpinBox()
        self.duration_spin.setRange(1, 30)
        self.duration_spin.setValue(5)
        self.duration_spin.setPrefix("D:")
        self.duration_spin.setSuffix("s")
        self.duration_spin.setStyleSheet(get_spin_box_style())
        self.duration_spin.setFixedWidth(70)
        self.duration_spin.setToolTip("SFX Duration (1-30 seconds)")
        self.duration_spin.setVisible(self._show_duration)
        panel_layout.addWidget(self.duration_spin)

        panel_layout.addStretch()
        self.panel.hide()
        layout.addWidget(self.panel)

    def _toggle_panel(self):
        visible = self.panel.isVisible()
        self.panel.setVisible(not visible)
        self.toggle_btn.setText("Directives \u25be" if not visible else "Directives \u25b8")

    def set_show_duration(self, show):
        self._show_duration = show
        self.duration_spin.setVisible(show)

    def get_directives_string(self):
        parts = []
        time_parts = []
        if self.time_pos_spin.value() > 0:
            v = self.time_pos_spin.value()
            time_parts.append(str(int(v)) if v == int(v) else str(v))
        if self.cut_end_spin.value() > 0:
            v = self.cut_end_spin.value()
            time_parts.append(f"-{int(v)}" if v == int(v) else f"-{v}")
        if self.cut_start_spin.value() > 0:
            v = self.cut_start_spin.value()
            time_parts.append(f"+{int(v)}" if v == int(v) else f"+{v}")
        if time_parts:
            parts.append("/time:" + "".join(time_parts))
        if self.level_spin.value() != 100:
            parts.append(f"/level:{self.level_spin.value()}")
        if self._show_duration and self.duration_spin.value() > 0:
            parts.append(f"/duration:{self.duration_spin.value()}")
        return " ".join(parts)

    def get_time_position(self):
        return self.time_pos_spin.value()

    def get_is_sfx(self):
        return self._show_duration


class DialogueLineEdit(QLineEdit):
    """A line edit that detects a pasted multi-line script.

    QLineEdit normally drops everything after the first newline, which made a
    pasted two-speaker conversation lose every speaker but the first one.
    """

    multi_line_pasted = pyqtSignal(str)

    def insertFromMimeData(self, source):
        text = source.text() if source is not None and source.hasText() else ""
        if text and ("\n" in text or "\r" in text):
            self.multi_line_pasted.emit(text)
            return
        super().insertFromMimeData(source)


class DialogueScriptWidget(QWidget):
    characters_changed = pyqtSignal(set)
    characters_committed = pyqtSignal(set)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.rows = []
        self.setup_ui()
        self.add_row()
        self.update_characters()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setStyleSheet("QScrollArea { background: transparent; }")
        scroll_widget = QWidget()
        scroll_widget.setStyleSheet("background: transparent;")
        self.rows_layout = QVBoxLayout(scroll_widget)
        self.rows_layout.setContentsMargins(0, 0, 0, 0)
        self.rows_layout.setSpacing(6)
        scroll.setWidget(scroll_widget)
        layout.addWidget(scroll)

    def add_row(self, character="", text=""):
        row_widget = QWidget()
        row_widget.setStyleSheet("background: transparent;")
        row_vlayout = QVBoxLayout(row_widget)
        row_vlayout.setContentsMargins(0, 0, 0, 0)
        row_vlayout.setSpacing(2)

        text_row = QHBoxLayout()
        text_row.setSpacing(8)

        char_edit = QLineEdit()
        char_edit.setPlaceholderText("Character")
        char_edit.setStyleSheet(get_line_edit_style())
        char_edit.setMinimumWidth(100)
        char_edit.setText(character)
        char_edit.textChanged.connect(self.on_text_changed)
        char_edit.editingFinished.connect(self._commit_characters)
        text_row.addWidget(char_edit)

        text_edit = DialogueLineEdit()
        text_edit.setPlaceholderText("Dialogue text")
        text_edit.setStyleSheet(get_line_edit_style())
        text_edit.setText(text)
        text_edit.textChanged.connect(self.on_text_changed)
        text_edit.multi_line_pasted.connect(
            lambda pasted, w=row_widget: self._on_multiline_paste(pasted, w)
        )
        text_row.addWidget(text_edit, stretch=1)

        delete_btn = QPushButton("\u00d7")
        delete_btn.setStyleSheet("""
            QPushButton {
                background-color: #3a3a3a;
                color: white;
                border: none;
                border-radius: 12px;
                font-size: 16px;
                font-weight: bold;
                padding: 4px 8px;
                min-width: 24px;
                max-width: 24px;
            }
            QPushButton:hover {
                background-color: #f44336;
            }
        """)
        delete_btn.setCursor(Qt.PointingHandCursor)
        delete_btn.clicked.connect(lambda: self.delete_row(row_widget))
        text_row.addWidget(delete_btn)

        row_vlayout.addLayout(text_row)

        is_sfx = character.lower().startswith("sfx")
        directives = DirectivesWidget(show_duration=is_sfx)
        char_edit.textChanged.connect(lambda t, d=directives: d.set_show_duration(t.lower().startswith("sfx")))
        row_vlayout.addWidget(directives)

        self.rows_layout.addWidget(row_widget)
        self.rows.append((char_edit, text_edit, delete_btn, row_widget, directives))

        if len(self.rows) == 1:
            delete_btn.setEnabled(False)
            delete_btn.setVisible(False)

    def delete_row(self, row_widget):
        for i, (_, _, _, w, _) in enumerate(self.rows):
            if w == row_widget:
                if len(self.rows) == 1:
                    return
                self.rows_layout.removeWidget(w)
                w.deleteLater()
                del self.rows[i]
                break
        for idx, (_, _, btn, _, _) in enumerate(self.rows):
            if idx == 0:
                btn.setEnabled(False)
                btn.setVisible(False)
            else:
                btn.setEnabled(True)
                btn.setVisible(True)
        self.update_characters(commit=True)

    def add_line(self):
        """Add one blank line and focus its text field."""
        self.add_row()
        row = self.rows[-1]
        row[1].setFocus()
        return row

    def _on_multiline_paste(self, pasted, row_widget):
        """Split a pasted conversation into one row per line."""
        lines = [
            line.strip()
            for line in pasted.replace("\r\n", "\n").replace("\r", "\n").split("\n")
            if line.strip()
        ]
        if not lines:
            return
        index = next((i for i, row in enumerate(self.rows) if row[3] is row_widget), 0)
        char_edit, text_edit = self.rows[index][0], self.rows[index][1]
        current_char = char_edit.text().strip()

        parsed = []
        for line in lines:
            if ":" in line:
                char, text = line.split(":", 1)
                parsed.append((char.strip() or current_char, text.strip()))
            else:
                parsed.append((current_char, line))

        first_char, first_text = parsed[0]
        if first_char:
            char_edit.setText(first_char)
        text_edit.setText(first_text)
        for char, text in parsed[1:]:
            self.add_row(char, text)
        self.update_characters(commit=True)

    def on_text_changed(self):
        if self.rows:
            last_char, last_text, _, _, _ = self.rows[-1]
            if last_char.text().strip() and last_text.text().strip():
                if not (len(self.rows) > 1 and not (self.rows[-2][0].text().strip() and self.rows[-2][1].text().strip())):
                    self.add_row()
        self.update_characters()

    def update_characters(self, commit=False):
        chars = set()
        seen = set()
        for char_edit, _, _, _, _ in self.rows:
            text = char_edit.text().strip()
            if text and text.lower() not in seen:
                chars.add(text.lower())
                seen.add(text.lower())
        self.characters_changed.emit(chars)
        if commit:
            self.characters_committed.emit(chars)

    def _commit_characters(self):
        self.update_characters(commit=True)

    def get_dialogue_items(self):
        items = []
        for idx, (char_edit, text_edit, _, _, directives) in enumerate(self.rows):
            char = char_edit.text().strip()
            text = text_edit.text().strip()
            dir_str = directives.get_directives_string()
            if char and text:
                items.append((idx + 1, char, text, dir_str))
        return items

    def validate(self):
        active_rows = 0
        for char_edit, text_edit, _, _, _ in self.rows:
            char = char_edit.text().strip()
            text = text_edit.text().strip()
            if char or text:
                if not char or not text:
                    return False, "Each active line must have both Character and Text."
                active_rows += 1
        if active_rows == 0:
            return False, "No dialogue entered."
        return True, ""

    def clear(self):
        while len(self.rows) > 1:
            _, _, _, w, _ = self.rows.pop()
            self.rows_layout.removeWidget(w)
            w.deleteLater()
        char_edit, text_edit, delete_btn, _, _ = self.rows[0]
        char_edit.clear()
        text_edit.clear()
        delete_btn.setEnabled(False)
        delete_btn.setVisible(False)
        self.update_characters(commit=True)

    def set_text(self, text):
        self.clear()
        for line in text.strip().split('\n'):
            line = line.strip()
            if not line:
                continue
            if ':' in line:
                char, dialogue = line.split(':', 1)
                self.rows[-1][0].setText(char.strip())
                self.rows[-1][1].setText(dialogue.strip())
                self.add_row()
            else:
                self.rows[-1][1].setText(line)
        self.update_characters(commit=True)

    def get_timeline_data(self):
        data = []
        for idx, (char_edit, text_edit, _, _, directives) in enumerate(self.rows):
            char = char_edit.text().strip()
            text = text_edit.text().strip()
            if char and text:
                time_pos = directives.get_time_position()
                is_sfx = directives.get_is_sfx()
                data.append({
                    'index': idx,
                    'character': char,
                    'text': text,
                    'time': time_pos,
                    'is_sfx': is_sfx,
                    'directives': directives.get_directives_string(),
                })
        return data


class DialogueTimelineWidget(QWidget):
    CHARACTER_COLORS = [
        '#4FC3F7', '#81C784', '#FFB74D', '#E57373', '#BA68C8',
        '#4DD0E1', '#AED581', '#FF8A65', '#F06292', '#7986CB',
    ]
    SFX_COLOR = '#FF9800'
    MUSIC_COLOR = '#66BB6A'

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(80)
        self.setMaximumHeight(120)
        self.items = []
        self.music_desc = ""
        self.total_duration = 30
        self.setStyleSheet(f"background-color: {THEME['surface']}; border: 1px solid {THEME['border']}; border-radius: 4px;")

    def set_data(self, items, music_desc="", total_duration=30):
        self.items = items if items else []
        self.music_desc = music_desc
        self.total_duration = max(total_duration, 10)
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        w = self.width()
        h = self.height()
        painter.fillRect(self.rect(), QColor(THEME['surface']))

        ruler_h = 20
        music_h = 16 if self.music_desc else 0
        block_area_top = ruler_h
        block_area_h = h - ruler_h - music_h

        painter.setPen(QColor(THEME['text_secondary']))
        painter.setFont(QFont("Consolas", 8))
        num_ticks = max(1, int(self.total_duration / 5))
        for i in range(num_ticks + 1):
            t = i * 5
            if t > self.total_duration:
                break
            x = int((t / self.total_duration) * (w - 20)) + 10
            painter.drawLine(x, ruler_h - 6, x, ruler_h)
            painter.drawText(x - 10, ruler_h - 8, f"{t}s")

        painter.setPen(QColor(THEME['border']))
        painter.drawLine(0, ruler_h, w, ruler_h)

        if self.music_desc:
            music_y = h - music_h
            painter.setPen(Qt.NoPen)
            painter.setBrush(QColor(self.MUSIC_COLOR))
            painter.setOpacity(0.3)
            painter.drawRect(10, music_y, w - 20, music_h)
            painter.setOpacity(1.0)
            painter.setPen(QColor(self.MUSIC_COLOR))
            painter.setFont(QFont("Consolas", 7))
            painter.drawText(14, music_y + 11, f"Music: {self.music_desc[:30]}")

        if not self.items:
            painter.setPen(QColor(THEME['text_secondary']))
            painter.drawText(self.rect(), Qt.AlignCenter, "No dialogue items")
            return

        char_color_map = {}
        color_idx = 0
        for item in self.items:
            c = item.get('character', '')
            if c and c.lower() not in char_color_map:
                char_color_map[c.lower()] = self.CHARACTER_COLORS[color_idx % len(self.CHARACTER_COLORS)]
                color_idx += 1

        block_h = max(12, min(20, block_area_h // max(len(self.items), 1)))
        for i, item in enumerate(self.items):
            t = item.get('time', 0)
            char = item.get('character', '')
            is_sfx = item.get('is_sfx', False)
            text_preview = item.get('text', '')[:20]

            x = int((t / self.total_duration) * (w - 20)) + 10
            block_w = max(40, int((5.0 / self.total_duration) * (w - 20)))
            y = block_area_top + 4 + (i % max(1, (block_area_h // (block_h + 2)))) * (block_h + 2)
            if y + block_h > h - music_h:
                y = block_area_top + 4

            color = self.SFX_COLOR if is_sfx else char_color_map.get(char.lower(), '#888888')
            painter.setPen(Qt.NoPen)
            painter.setBrush(QColor(color))
            painter.setOpacity(0.6)
            painter.drawRoundedRect(x, y, block_w, block_h, 3, 3)
            painter.setOpacity(1.0)
            painter.setPen(QColor(THEME['text']))
            painter.setFont(QFont("Consolas", 7))
            label = ("SFX:" if is_sfx else f"{char}:") + text_preview
            painter.drawText(x + 4, y + block_h - 3, label[:int(block_w / 5)])


class TTMReferenceEntry(QWidget):
    remove_signal = pyqtSignal(object)

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        path_row = QHBoxLayout()
        path_row.setSpacing(4)
        self.path_edit = QLineEdit()
        self.path_edit.setPlaceholderText("Reference audio path...")
        self.path_edit.setStyleSheet(get_line_edit_style())
        path_row.addWidget(self.path_edit, stretch=1)
        browse_btn = QPushButton("Browse")
        browse_btn.setStyleSheet(get_surface_button_style())
        browse_btn.setCursor(Qt.PointingHandCursor)
        browse_btn.setFixedWidth(70)
        browse_btn.clicked.connect(self._browse)
        path_row.addWidget(browse_btn)
        self.del_btn = QPushButton("\u00d7")
        self.del_btn.setFixedSize(24, 24)
        self.del_btn.setStyleSheet("""
            QPushButton { background-color: #3a3a3a; color: white; border: none; border-radius: 12px; font-size: 14px; font-weight: bold; min-width: 24px; max-width: 24px; }
            QPushButton:hover { background-color: #f44336; }
        """)
        self.del_btn.setCursor(Qt.PointingHandCursor)
        path_row.addWidget(self.del_btn)
        layout.addLayout(path_row)

        spec_row = QHBoxLayout()
        spec_row.setSpacing(6)
        prefix_lbl = QLabel("Prefix:")
        prefix_lbl.setStyleSheet(f"color: {THEME['text_secondary']}; font-size: 11px;")
        spec_row.addWidget(prefix_lbl)
        self.prefix_combo = QComboBox()
        self.prefix_combo.setStyleSheet(get_combo_box_style())
        self.prefix_combo.addItems(["none", "voice", "music"])
        self.prefix_combo.setFixedWidth(85)
        spec_row.addWidget(self.prefix_combo)
        time_lbl = QLabel("Time:")
        time_lbl.setStyleSheet(f"color: {THEME['text_secondary']}; font-size: 11px;")
        spec_row.addWidget(time_lbl)
        self.time_edit = QLineEdit()
        self.time_edit.setPlaceholderText("e.g. 20-30")
        self.time_edit.setStyleSheet(get_line_edit_style())
        self.time_edit.setFixedWidth(90)
        self.time_edit.setToolTip("Start-end seconds, e.g. 20-30 or 50 for start only")
        spec_row.addWidget(self.time_edit)
        stem_lbl = QLabel("Stem:")
        stem_lbl.setStyleSheet(f"color: {THEME['text_secondary']}; font-size: 11px;")
        spec_row.addWidget(stem_lbl)
        self.stem_edit = QLineEdit()
        self.stem_edit.setPlaceholderText("e.g. drums")
        self.stem_edit.setStyleSheet(get_line_edit_style())
        self.stem_edit.setFixedWidth(90)
        self.stem_edit.setToolTip("Extract specific stem, e.g. drums, bass-drums")
        spec_row.addWidget(self.stem_edit)
        spec_row.addStretch()
        layout.addLayout(spec_row)

    def _browse(self):
        path, _ = QFileDialog.getOpenFileName(None, "Select Reference", "", "Audio (*.wav *.mp3 *.flac *.ogg);;Video (*.mp4 *.avi *.mov *.mkv);;All (*)")
        if path:
            self.path_edit.setText(path)

    def get_ref_string(self):
        path = self.path_edit.text().strip()
        if not path:
            return None
        prefix = self.prefix_combo.currentText()
        time_spec = self.time_edit.text().strip()
        stem_spec = self.stem_edit.text().strip()
        ref_val = ""
        if stem_spec:
            ref_val += stem_spec + "/"
        if time_spec:
            ref_val += time_spec
        ref_val += "(" + path + ")"
        return prefix, ref_val

    def get_path(self):
        return self.path_edit.text().strip()


class TTMReferenceList(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.entries = []
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFrameShape(QFrame.NoFrame)
        self.scroll_area.setStyleSheet("QScrollArea { background: transparent; }")
        scroll_widget = QWidget()
        scroll_widget.setStyleSheet("background: transparent;")
        self.entries_layout = QVBoxLayout(scroll_widget)
        self.entries_layout.setContentsMargins(0, 0, 0, 0)
        self.entries_layout.setSpacing(4)
        self.scroll_area.setWidget(scroll_widget)
        layout.addWidget(self.scroll_area)
        add_btn = QPushButton("+ Add Reference")
        add_btn.setStyleSheet(get_surface_button_style())
        add_btn.setCursor(Qt.PointingHandCursor)
        add_btn.clicked.connect(lambda: self.add_entry())
        layout.addWidget(add_btn)
        self.add_entry()

    def add_entry(self):
        entry = TTMReferenceEntry()
        entry.remove_signal.connect(self.remove_entry)
        self.entries_layout.addWidget(entry)
        self.entries.append(entry)
        self._update_delete_buttons()

    def remove_entry(self, entry):
        if len(self.entries) <= 1:
            return
        self.entries_layout.removeWidget(entry)
        entry.deleteLater()
        if entry in self.entries:
            self.entries.remove(entry)
        self._update_delete_buttons()

    def _update_delete_buttons(self):
        for entry in self.entries:
            entry.del_btn.setEnabled(len(self.entries) > 1)
            entry.del_btn.setVisible(len(self.entries) > 1)

    def get_refs(self):
        refs = []
        for entry in self.entries:
            result = entry.get_ref_string()
            if result:
                refs.append(result)
        return refs

    def clear(self):
        for entry in list(self.entries):
            self.entries_layout.removeWidget(entry)
            entry.deleteLater()
        self.entries.clear()
        self.add_entry()


class KeyValueRow(QWidget):
    remove_signal = pyqtSignal(object)

    def __init__(self, key_label="Key", value_label="Value", key_placeholder="", value_placeholder="", parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
        self.key_edit = QLineEdit()
        self.key_edit.setPlaceholderText(key_placeholder or key_label)
        self.key_edit.setStyleSheet(get_line_edit_style())
        self.key_edit.setMinimumWidth(100)
        self.val_edit = QLineEdit()
        self.val_edit.setPlaceholderText(value_placeholder or value_label)
        self.val_edit.setStyleSheet(get_line_edit_style())
        self.browse_btn = None
        self.del_btn = QPushButton("x")
        self.del_btn.setFixedSize(24, 24)
        self.del_btn.setStyleSheet("""
            QPushButton { background-color: #3a3a3a; color: white; border: none; border-radius: 12px; font-size: 14px; font-weight: bold; min-width: 24px; max-width: 24px; }
            QPushButton:hover { background-color: #f44336; }
        """)
        self.del_btn.setCursor(Qt.PointingHandCursor)
        self.del_btn.clicked.connect(lambda: self.remove_signal.emit(self))
        layout.addWidget(self.key_edit)
        layout.addWidget(self.val_edit, stretch=1)
        layout.addWidget(self.del_btn)

    def set_browse(self, file_filter="Audio Files (*.wav *.mp3 *.flac *.ogg);;All Files (*)"):
        if self.browse_btn is None:
            self.browse_btn = QPushButton("Browse")
            self.browse_btn.setStyleSheet(get_surface_button_style())
            self.browse_btn.setCursor(Qt.PointingHandCursor)
            self.browse_btn.setFixedWidth(80)
            self.layout().insertWidget(2, self.browse_btn)

        def pick():
            path, _ = QFileDialog.getOpenFileName(None, "Select", "", file_filter)
            if path:
                self.val_edit.setText(path)

        self.browse_btn.clicked.connect(pick)

    def get_key(self):
        return self.key_edit.text().strip()

    def get_value(self):
        return self.val_edit.text().strip()


class KeyValueList(QWidget):
    def __init__(self, key_label="Key", value_label="Value", key_placeholder="", value_placeholder="", with_browse=False, file_filter="", parent=None):
        super().__init__(parent)
        self.key_label = key_label
        self.value_label = value_label
        self.key_placeholder = key_placeholder
        self.value_placeholder = value_placeholder
        self.with_browse = with_browse
        self.file_filter = file_filter
        self.rows = []
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(4)
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFrameShape(QFrame.NoFrame)
        self.scroll_area.setStyleSheet("QScrollArea { background: transparent; }")
        scroll_widget = QWidget()
        scroll_widget.setStyleSheet("background: transparent;")
        self.rows_layout = QVBoxLayout(scroll_widget)
        self.rows_layout.setContentsMargins(0, 0, 0, 0)
        self.rows_layout.setSpacing(4)
        self.scroll_area.setWidget(scroll_widget)
        self.layout.addWidget(self.scroll_area)
        spacer = QWidget()
        spacer.setFixedHeight(8)
        self.layout.addWidget(spacer)
        self.add_btn = QPushButton(f"+ Add {key_label}")
        self.add_btn.setStyleSheet(get_surface_button_style())
        self.add_btn.setCursor(Qt.PointingHandCursor)
        self.add_btn.clicked.connect(lambda: self.add_row())
        self.layout.addWidget(self.add_btn)
        self.add_row()

    def setMinimumHeight(self, h):
        super().setMinimumHeight(h)
        self.scroll_area.setMinimumHeight(h)

    def set_scroll_height(self, h):
        self.scroll_area.setMinimumHeight(h)

    def add_row(self, key="", value=""):
        row = KeyValueRow(self.key_label, self.value_label, self.key_placeholder, self.value_placeholder)
        row.remove_signal.connect(self.remove_row)
        if self.with_browse:
            row.set_browse(self.file_filter)
        row.key_edit.setText(key)
        row.val_edit.setText(value)
        if self.rows:
            prev = self.rows[-1]
            prev.key_edit.textChanged.disconnect()
            prev.val_edit.textChanged.disconnect()
            prev.key_edit.textChanged.connect(prev._kv_emit)
            prev.val_edit.textChanged.connect(prev._kv_emit)
        row._kv_emit = lambda: self._on_last_row_changed()
        row.key_edit.textChanged.connect(row._kv_emit)
        row.val_edit.textChanged.connect(row._kv_emit)
        self.rows_layout.addWidget(row)
        self.rows.append(row)
        self.update_delete_buttons()

    def _on_last_row_changed(self):
        if not self.rows:
            return
        last = self.rows[-1]
        if last.key_edit.text().strip() and last.val_edit.text().strip():
            if len(self.rows) > 1:
                prev = self.rows[-2]
                if not prev.key_edit.text().strip() and not prev.val_edit.text().strip():
                    return
            self.add_row()

    def remove_row(self, row_widget):
        if len(self.rows) <= 1:
            return
        self.rows_layout.removeWidget(row_widget)
        row_widget.deleteLater()
        if row_widget in self.rows:
            self.rows.remove(row_widget)
        self.update_delete_buttons()
        if self.rows:
            last = self.rows[-1]
            try:
                last.key_edit.textChanged.disconnect()
            except Exception:
                pass
            try:
                last.val_edit.textChanged.disconnect()
            except Exception:
                pass
            last._kv_emit = lambda: self._on_last_row_changed()
            last.key_edit.textChanged.connect(last._kv_emit)
            last.val_edit.textChanged.connect(last._kv_emit)

    def update_delete_buttons(self):
        for i, row in enumerate(self.rows):
            row.del_btn.setEnabled(len(self.rows) > 1)
            row.del_btn.setVisible(len(self.rows) > 1)

    def get_items(self):
        items = []
        for row in self.rows:
            k = row.get_key()
            v = row.get_value()
            if k and v:
                items.append((k, v))
        return items

    def ensure_keys(self, keys):
        key_list = sorted(keys, key=str.lower)
        existing_filled = []
        for row in self.rows:
            k = row.get_key()
            if k:
                existing_filled.append(row)
        filled_keys = [r.get_key().lower() for r in existing_filled]
        empty_rows = [r for r in self.rows if not r.get_key()]
        ei = 0
        for key in key_list:
            if key.lower() not in filled_keys:
                if ei < len(empty_rows):
                    empty_rows[ei].key_edit.setText(key)
                    filled_keys.append(key.lower())
                    ei += 1
                else:
                    self.add_row(key=key)
                    filled_keys.append(key.lower())

    def clear(self):
        for row in list(self.rows):
            self.rows_layout.removeWidget(row)
            row.deleteLater()
        self.rows.clear()
        self.add_row()


class FileListWidget(QWidget):
    def __init__(self, placeholder="Click + to add files", file_filter="Audio Files (*.wav *.mp3 *.flac *.ogg);;Video Files (*.mp4 *.avi *.mov *.mkv);;All Files (*)", parent=None):
        super().__init__(parent)
        self.file_filter = file_filter
        self.paths = []
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        self.list_widget = QListWidget()
        self.list_widget.setStyleSheet(get_list_widget_style())
        self.list_widget.setMinimumHeight(60)
        self.list_widget.setMaximumHeight(120)
        layout.addWidget(self.list_widget)
        btn_row = QHBoxLayout()
        add_btn = QPushButton("+ Add")
        add_btn.setStyleSheet(get_surface_button_style())
        add_btn.setCursor(Qt.PointingHandCursor)
        add_btn.setFixedWidth(80)
        add_btn.clicked.connect(self.add_file)
        del_btn = QPushButton("- Remove")
        del_btn.setStyleSheet(get_surface_button_style())
        del_btn.setCursor(Qt.PointingHandCursor)
        del_btn.setFixedWidth(80)
        del_btn.clicked.connect(self.remove_selected)
        btn_row.addWidget(add_btn)
        btn_row.addWidget(del_btn)
        btn_row.addStretch()
        layout.addLayout(btn_row)

    def add_file(self):
        paths, _ = QFileDialog.getOpenFileNames(None, "Select Files", "", self.file_filter)
        for p in paths:
            if p not in self.paths:
                self.paths.append(p)
                self.list_widget.addItem(os.path.basename(p))

    def remove_selected(self):
        for item in self.list_widget.selectedItems():
            idx = self.list_widget.row(item)
            self.list_widget.takeItem(idx)
            if idx < len(self.paths):
                self.paths.pop(idx)

    def get_paths(self):
        return list(self.paths)

    def clear(self):
        self.paths.clear()
        self.list_widget.clear()


VOICE_SOURCE_SAVED = "My saved voices (pick by name)"
VOICE_SOURCE_DESCRIBE = "AI voice description (create a voice style)"
VOICE_SOURCE_FILE = "Audio reference file (one-off)"


class SavedVoicePickerRow(QWidget):
    """One line: character name + a dropdown of the saved voices on this PC."""

    changed = pyqtSignal()

    def __init__(self, show_character=True, allow_file=False, parent=None):
        super().__init__(parent)
        self.show_character = show_character
        self.allow_file = allow_file
        self._expect_enhanced = False
        self._file_path = ""
        self._building = False
        self._previous_index = 0

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        self.char_edit = None
        if show_character:
            self.char_edit = QLineEdit()
            self.char_edit.setPlaceholderText("Character")
            self.char_edit.setStyleSheet(get_line_edit_style())
            self.char_edit.setFixedWidth(120)
            self.char_edit.setToolTip("Name used in the script for this voice")
            self.char_edit.textChanged.connect(self._emit_changed)
            layout.addWidget(self.char_edit)

        self.combo = QComboBox()
        self.combo.setStyleSheet(get_combo_box_style())
        self.combo.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.combo.setToolTip("Pick one of your saved voice clones")
        self.combo.activated[int].connect(self._on_activated)
        self.combo.currentIndexChanged.connect(self._on_index_changed)
        layout.addWidget(self.combo, stretch=1)

        self.status_label = QLabel("")
        self.status_label.setStyleSheet(f"color: {THEME['text_secondary']}; font-size: 11px;")
        self.status_label.setMinimumWidth(150)
        layout.addWidget(self.status_label)

        self.refresh()

    # ------------------------------------------------------------------ data
    def refresh(self):
        current = self.current_value()
        self._building = True
        self.combo.clear()
        self.combo.addItem("— pick a saved voice —", None)

        groups = vlib.group_voices()
        for key in sorted(groups, key=lambda k: groups[k]["name"].casefold()):
            group = groups[key]
            tag = voice_kind_tag(group["kinds"])
            name = group["name"]
            display = name[:1].upper() + name[1:]
            self.combo.addItem(f"{display}  ·  {tag}", ("saved", name))

        if self._file_path:
            self.combo.addItem(
                f"Audio file · {os.path.basename(self._file_path)}",
                ("file", self._file_path),
            )
        if self.allow_file:
            self.combo.addItem("Browse for an audio file…", ("browse", None))
        self._building = False

        if current:
            self.set_value(current)
        else:
            self.combo.setCurrentIndex(0)
        self._update_status()

    def current_value(self):
        data = self.combo.currentData()
        if isinstance(data, tuple) and len(data) == 2 and data[0] in ("saved", "file"):
            return data[1] or ""
        return ""

    def current_name(self):
        data = self.combo.currentData()
        if isinstance(data, tuple) and data[0] == "saved":
            return data[1] or ""
        return ""

    def set_value(self, value):
        if not value:
            self.combo.setCurrentIndex(0)
            self._update_status()
            return False
        for index in range(self.combo.count()):
            data = self.combo.itemData(index)
            if not isinstance(data, tuple):
                continue
            if data[0] == "saved" and data[1].casefold() == value.casefold():
                self.combo.setCurrentIndex(index)
                self._update_status()
                return True
            if data[0] == "file" and data[1] == value:
                self.combo.setCurrentIndex(index)
                self._update_status()
                return True
        if self.allow_file and os.path.isfile(value):
            self.set_file(value)
            return True
        return False

    def set_file(self, path):
        self._file_path = path
        self.refresh()
        for index in range(self.combo.count()):
            data = self.combo.itemData(index)
            if isinstance(data, tuple) and data[0] == "file" and data[1] == path:
                self.combo.setCurrentIndex(index)
                break
        self._update_status()

    def set_expect_enhanced(self, enhanced):
        self._expect_enhanced = bool(enhanced)
        self._update_status()

    # --------------------------------------------------------------- events
    def _on_activated(self, index):
        if self._building:
            return
        data = self.combo.itemData(index)
        if isinstance(data, tuple) and data[0] == "browse":
            path, _ = QFileDialog.getOpenFileName(
                self, "Select audio reference", "",
                "Audio Files (*.wav *.mp3 *.flac *.ogg);;Video Files (*.mp4 *.avi *.mov *.mkv);;All Files (*)"
            )
            if path:
                self.set_file(path)
                self.changed.emit()
            else:
                self.combo.setCurrentIndex(self._previous_index)
            return
        self._previous_index = index
        self._after_user_pick()

    def _on_index_changed(self, *_args):
        if self._building:
            return
        self._update_status()

    def _after_user_pick(self):
        name = self.current_name()
        if name and self.char_edit is not None:
            if not self.char_edit.text().strip():
                self.char_edit.setText(name)
        self._update_status()
        self.changed.emit()

    def _emit_changed(self, *_args):
        self.changed.emit()

    def _update_status(self):
        value = self.current_value()
        data = self.combo.currentData()
        if not value:
            self.status_label.setText("")
            self.combo.setToolTip("Pick one of the saved voices, or train a new one in Make Voice.")
            return

        if isinstance(data, tuple) and data[0] == "file":
            self.status_label.setText("Audio file")
            self.status_label.setStyleSheet(
                f"color: {THEME['text_secondary']}; font-size: 11px;"
            )
            self.combo.setToolTip(value)
            return

        profiles = vlib.profiles_for_name(value)
        kinds = {profile.kind for profile in profiles}
        self.combo.setToolTip("\n".join(
            f"{profile.kind_label}: {profile.path}" for profile in profiles
        ))
        if self._expect_enhanced:
            if vlib.KIND_ENHANCED in kinds:
                text, color = "Enhanced ready", THEME["accent"]
            else:
                text, color = "Standard only - untick Enhanced", THEME["warning"]
        else:
            if vlib.KIND_STANDARD in kinds:
                text, color = "Ready", THEME["accent"]
            elif vlib.KIND_DARIJA in kinds:
                text, color = "Darija - Arabic text only", THEME["accent"]
            elif vlib.KIND_ENHANCED in kinds:
                text, color = "Enhanced only - tick Enhanced", THEME["warning"]
            else:
                text, color = "", THEME["text_secondary"]
        self.status_label.setText(text)
        self.status_label.setStyleSheet(f"color: {color}; font-size: 11px;")


class CharacterVoiceList(QWidget):
    """A list of character/voice rows backed by the persistent voice library."""

    changed = pyqtSignal()
    train_requested = pyqtSignal()

    def __init__(self, allow_file=False, show_character=True, parent=None):
        super().__init__(parent)
        self.allow_file = allow_file
        self.show_character = show_character
        self.rows = []
        self._expect_enhanced = False

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        header = QHBoxLayout()
        header.setSpacing(6)
        self.count_label = QLabel("Saved voices")
        self.count_label.setStyleSheet(f"color: {THEME['text']}; font-size: 12px; font-weight: bold;")
        header.addWidget(self.count_label)
        header.addStretch()

        self.add_btn = QPushButton("+ Add Voice")
        self.add_btn.setStyleSheet(get_surface_button_style())
        self.add_btn.setCursor(Qt.PointingHandCursor)
        self.add_btn.setFixedHeight(26)
        self.add_btn.setToolTip("Add another character and pick a different saved voice for it")
        self.add_btn.clicked.connect(self.add_voice_row)
        header.addWidget(self.add_btn)

        self.refresh_btn = QPushButton("Refresh")
        self.refresh_btn.setStyleSheet(get_surface_button_style())
        self.refresh_btn.setCursor(Qt.PointingHandCursor)
        self.refresh_btn.setFixedHeight(26)
        self.refresh_btn.clicked.connect(self.refresh)
        header.addWidget(self.refresh_btn)

        self.open_btn = QPushButton("Open Folder")
        self.open_btn.setStyleSheet(get_surface_button_style())
        self.open_btn.setCursor(Qt.PointingHandCursor)
        self.open_btn.setFixedHeight(26)
        self.open_btn.clicked.connect(vlib.open_voices_folder)
        header.addWidget(self.open_btn)

        self.train_btn = QPushButton("+ Train New")
        self.train_btn.setStyleSheet(get_surface_button_style())
        self.train_btn.setCursor(Qt.PointingHandCursor)
        self.train_btn.setFixedHeight(26)
        self.train_btn.clicked.connect(self.train_requested.emit)
        header.addWidget(self.train_btn)
        layout.addLayout(header)

        self.rows_layout = QVBoxLayout()
        self.rows_layout.setContentsMargins(0, 0, 0, 0)
        self.rows_layout.setSpacing(4)
        layout.addLayout(self.rows_layout)

        self.hint_label = QLabel("")
        self.hint_label.setWordWrap(True)
        self.hint_label.setStyleSheet(
            f"color: {THEME['text_secondary']}; font-size: 11px; padding: 2px 0;"
        )
        layout.addWidget(self.hint_label)

        self.ensure_row()
        self.refresh()

    def ensure_row(self, character=""):
        row = SavedVoicePickerRow(show_character=self.show_character,
                                  allow_file=self.allow_file)
        row.changed.connect(self._on_row_changed)
        if character and row.char_edit is not None:
            row.char_edit.setText(character)
        self.rows_layout.addWidget(row)
        self.rows.append(row)
        return row

    def add_voice_row(self):
        """Add a blank character row so another voice can be picked."""
        row = self.ensure_row()
        if row.char_edit is not None:
            row.char_edit.setFocus()
        self._update_hint()
        return row

    def ensure_characters(self, characters):
        groups = vlib.group_voices()
        existing = {
            row.char_edit.text().strip().casefold()
            for row in self.rows if row.char_edit is not None
        }
        for character in sorted({c.strip() for c in characters if c and c.strip()}):
            key = character.casefold()
            if key in existing:
                continue
            row = self.ensure_row(character)
            existing.add(key)
            group = groups.get(key)
            if group is not None:
                row.set_value(group["name"])

    def refresh(self):
        voices = vlib.list_voices()
        names = {voice.name.casefold() for voice in voices}
        if names:
            self.count_label.setText(
                f"{len(names)} saved voice{'s' if len(names) != 1 else ''} found"
            )
        else:
            self.count_label.setText("No saved voices yet")
        for row in self.rows:
            row.refresh()
            row.set_expect_enhanced(self._expect_enhanced)
        self._update_hint()

    def _update_hint(self):
        voices = vlib.list_voices()
        names = len({voice.name.casefold() for voice in voices})
        if not names:
            self.hint_label.setText(
                "No saved voices yet. Train one in Make Voice, then it appears here "
                "automatically - even after you restart your PC."
            )
        else:
            self.hint_label.setText(
                "Pick a voice per character. Names are remembered on this PC, so you "
                "never need to paste a link or file path. A character whose name "
                "matches a saved voice is filled in automatically."
            )
        self.hint_label.setToolTip(vlib.voices_dir())

    def set_expect_enhanced(self, enhanced):
        self._expect_enhanced = bool(enhanced)
        for row in self.rows:
            row.set_expect_enhanced(self._expect_enhanced)
        self._update_hint()

    def get_items(self):
        items = []
        for row in self.rows:
            value = row.current_value()
            if not value:
                continue
            character = ""
            if row.char_edit is not None:
                character = row.char_edit.text().strip()
            items.append((character, value))
        return items

    def select_saved_voice(self, name):
        target = None
        for row in self.rows:
            if row.char_edit is not None and row.char_edit.text().strip().casefold() == name.casefold():
                target = row
                break
        if target is None:
            for row in self.rows:
                if not row.current_value():
                    target = row
                    break
        if target is None and self.rows:
            target = self.rows[0]
        if target is None:
            target = self.ensure_row()
        if target.char_edit is not None and not target.char_edit.text().strip():
            target.char_edit.setText(name)
        target.set_value(name)
        self._on_row_changed()

    def _on_row_changed(self):
        self._update_hint()
        self.changed.emit()


class VoiceLibraryPanel(QWidget):
    """List of the saved voices with rename / delete / use actions."""

    use_voice = pyqtSignal(str)
    voices_changed = pyqtSignal()
    train_requested = pyqtSignal()

    def __init__(self, show_train_button=True, parent=None):
        super().__init__(parent)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        self.count_label = QLabel("Saved voices")
        self.count_label.setStyleSheet(
            f"color: {THEME['text']}; font-size: 13px; font-weight: bold;"
        )
        layout.addWidget(self.count_label)

        self.list_widget = QListWidget()
        self.list_widget.setStyleSheet(get_list_widget_style())
        self.list_widget.setMinimumHeight(160)
        self.list_widget.itemDoubleClicked.connect(lambda *_: self.emit_use())
        layout.addWidget(self.list_widget)

        self.folder_label = QLabel(f"Folder: {vlib.voices_dir()}")
        self.folder_label.setWordWrap(True)
        self.folder_label.setStyleSheet(
            f"color: {THEME['text_secondary']}; font-size: 11px;"
        )
        layout.addWidget(self.folder_label)

        button_row = QHBoxLayout()
        button_row.setSpacing(6)
        for text, slot in (
            ("Refresh", self.refresh),
            ("Open Folder", vlib.open_voices_folder),
            ("Rename", self.rename_selected),
            ("Delete", self.delete_selected),
            ("Use in Speech", self.emit_use),
        ):
            button = QPushButton(text)
            button.setStyleSheet(get_surface_button_style())
            button.setCursor(Qt.PointingHandCursor)
            button.clicked.connect(slot)
            button_row.addWidget(button)
        if show_train_button:
            train_btn = QPushButton("Train New Voice")
            train_btn.setStyleSheet(get_main_button_style())
            train_btn.setCursor(Qt.PointingHandCursor)
            train_btn.clicked.connect(self.train_requested.emit)
            button_row.addWidget(train_btn)
        button_row.addStretch()
        layout.addLayout(button_row)

        self.refresh()

    def refresh(self):
        selected_path = self._selected_path()
        self.list_widget.clear()
        voices = vlib.list_voices()
        groups = vlib.group_voices(voices)
        for key in sorted(groups, key=lambda k: groups[k]["name"].casefold()):
            group = groups[key]
            tag = voice_kind_tag(group["kinds"])
            newest = max(group["profiles"], key=lambda p: p.modified)
            try:
                stamp = time.strftime("%Y-%m-%d %H:%M", time.localtime(newest.modified))
            except Exception:
                stamp = ""
            display = newest.display_name
            item = QListWidgetItem(f"{display}   ·   {tag}   ·   {stamp}")
            item.setData(Qt.UserRole, newest.path)
            item.setToolTip("\n".join(f"{p.kind_label}: {p.path}" for p in group["profiles"]))
            self.list_widget.addItem(item)
            if selected_path and os.path.normcase(newest.path) == os.path.normcase(selected_path):
                self.list_widget.setCurrentItem(item)

        names = len({voice.name.casefold() for voice in voices})
        if names:
            self.count_label.setText(
                f"{names} saved voice{'s' if names != 1 else ''} - double-click to use"
            )
        else:
            self.count_label.setText("No saved voices yet - train one below")

    def _selected_path(self):
        item = self.list_widget.currentItem()
        if item is None:
            return ""
        return item.data(Qt.UserRole) or ""

    def _selected_name(self):
        path = self._selected_path()
        if not path:
            return ""
        for profile in vlib.list_voices():
            if os.path.normcase(profile.path) == os.path.normcase(path):
                return profile.name
        return ""

    def emit_use(self):
        name = self._selected_name()
        if not name:
            QMessageBox.information(self, "Pick a voice", "Select a saved voice first.")
            return
        self.use_voice.emit(name)

    def rename_selected(self):
        path = self._selected_path()
        if not path:
            QMessageBox.information(self, "Pick a voice", "Select a saved voice first.")
            return
        current = self._selected_name()
        new_name, ok = QInputDialog.getText(
            self, "Rename Voice", "New voice name (this is the name you will pick later):",
            text=current
        )
        if not ok:
            return
        profiles = vlib.profiles_for_name(current) or [
            p for p in vlib.list_voices() if os.path.normcase(p.path) == os.path.normcase(path)
        ]
        renamed = 0
        for profile in profiles:
            if vlib.rename_voice(profile.path, new_name):
                renamed += 1
        if not renamed:
            QMessageBox.warning(
                self, "Rename failed",
                "That name is empty, unsafe, or already used by another copy of this voice."
            )
            return
        self.refresh()
        self.voices_changed.emit()

    def delete_selected(self):
        path = self._selected_path()
        if not path:
            QMessageBox.information(self, "Pick a voice", "Select a saved voice first.")
            return
        name = self._selected_name()
        profiles = vlib.profiles_for_name(name) or [
            p for p in vlib.list_voices() if os.path.normcase(p.path) == os.path.normcase(path)
        ]
        extra = ""
        if len(profiles) > 1:
            extra = f"\n\nThis deletes {len(profiles)} files (standard and enhanced versions)."
        answer = QMessageBox.question(
            self, "Delete voice",
            f"Delete the saved voice '{name}'?{extra}\n\n{path}\n\nThis cannot be undone.",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No
        )
        if answer != QMessageBox.Yes:
            return
        deleted = sum(1 for profile in profiles if vlib.delete_voice(profile.path))
        if not deleted:
            QMessageBox.warning(self, "Delete failed", "The voice file could not be deleted.")
            return
        self.refresh()
        self.voices_changed.emit()


class StemSelectorWidget(QWidget):
    stems_changed = pyqtSignal()

    AVAILABLE_STEMS = [
        ("vocals", "Vocals"),
        ("backing_vocals", "Backing Vocals"),
        ("drums", "Drums"),
        ("bass", "Bass"),
        ("guitar", "Guitar"),
        ("keyboard", "Keyboard"),
        ("strings", "Strings"),
        ("percussion", "Percussion"),
        ("brass", "Brass"),
        ("woodwinds", "Woodwinds"),
        ("synth", "Synth"),
        ("fx", "FX / Sound Effects"),
    ]

    def __init__(self, parent=None):
        super().__init__(parent)
        self.checkboxes = {}
        self.custom_edit = None
        self._expanded = False
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        self.toggle_btn = QPushButton("Select Stems")
        self.toggle_btn.setStyleSheet(get_surface_button_style())
        self.toggle_btn.setCursor(Qt.PointingHandCursor)
        self.toggle_btn.clicked.connect(self.toggle_panel)
        layout.addWidget(self.toggle_btn)

        self.panel = QFrame()
        self.panel.setStyleSheet(f"background-color: {THEME['surface']}; border: 1px solid {THEME['border']}; border-radius: 6px; padding: 8px;")
        self.panel_layout = QVBoxLayout(self.panel)
        self.panel_layout.setContentsMargins(8, 8, 8, 8)
        self.panel_layout.setSpacing(4)

        for stem_key, stem_label in self.AVAILABLE_STEMS:
            cb = QCheckBox(stem_label)
            cb.setStyleSheet(get_checkbox_style())
            cb.stateChanged.connect(self.on_changed)
            self.checkboxes[stem_key] = cb
            self.panel_layout.addWidget(cb)

        quick_row = QHBoxLayout()
        quick_row.setSpacing(4)
        for label_text, stems_list in [
            ("All", [s[0] for s in self.AVAILABLE_STEMS]),
            ("Inst", ["drums", "bass", "guitar", "keyboard", "strings", "percussion", "brass", "woodwinds", "synth", "fx"]),
            ("Voice", ["vocals", "backing_vocals"]),
            ("None", []),
        ]:
            btn = QPushButton(label_text)
            btn.setFixedHeight(28)
            btn.setStyleSheet(get_surface_button_style())
            btn.setCursor(Qt.PointingHandCursor)
            btn.clicked.connect(lambda checked, sl=stems_list: self.set_stems(sl))
            quick_row.addWidget(btn)
        quick_row.addStretch()
        self.panel_layout.addLayout(quick_row)

        custom_row = QHBoxLayout()
        custom_row.setSpacing(4)
        custom_label = QLabel("Custom:")
        custom_label.setStyleSheet(f"color: {THEME['text_secondary']}; font-size: 12px;")
        self.custom_edit = QLineEdit()
        self.custom_edit.setPlaceholderText("e.g. everything, instruments, voices")
        self.custom_edit.setStyleSheet(get_line_edit_style())
        self.custom_edit.textChanged.connect(self.on_changed)
        custom_row.addWidget(custom_label)
        custom_row.addWidget(self.custom_edit, stretch=1)
        self.panel_layout.addLayout(custom_row)

        self.panel.hide()
        layout.addWidget(self.panel)

    def toggle_panel(self):
        self._expanded = not self._expanded
        self.panel.setVisible(self._expanded)
        self.update_label()

    def set_stems(self, stems_list):
        for key, cb in self.checkboxes.items():
            cb.setChecked(key in stems_list)
        self.on_changed()

    def on_changed(self):
        self.update_label()
        self.stems_changed.emit()

    def update_label(self):
        selected = self.get_stems_list()
        custom = self.custom_edit.text().strip() if self.custom_edit else ""
        if custom:
            if selected:
                self.toggle_btn.setText(f"Select Stems ({len(selected)} + custom)")
            else:
                self.toggle_btn.setText(f"Select Stems (custom)")
        elif selected:
            display = ", ".join(selected[:3])
            if len(selected) > 3:
                display += f" +{len(selected)-3}"
            self.toggle_btn.setText(f"Select Stems: {display}")
        else:
            self.toggle_btn.setText("Select Stems")

    def get_stems_list(self):
        selected = [key for key, cb in self.checkboxes.items() if cb.isChecked()]
        return selected

    def get_stems_string(self):
        selected = self.get_stems_list()
        custom = self.custom_edit.text().strip() if self.custom_edit else ""
        if custom and selected:
            return " ".join(selected) + " " + custom
        elif custom:
            return custom
        elif selected:
            return " ".join(selected)
        return ""


class TTSTab(QWidget):
    run_signal = pyqtSignal(list)
    transcribe_signal = pyqtSignal(list)
    train_voice_requested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._importing_audio = False
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(8)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setStyleSheet("QScrollArea { background: transparent; }")
        scroll_widget = QWidget()
        scroll_widget.setStyleSheet("background: transparent;")
        self.inner = QVBoxLayout(scroll_widget)
        self.inner.setSpacing(8)

        self.sub_mode = QComboBox()
        self.sub_mode.setStyleSheet(get_combo_box_style())
        self.sub_mode.addItems(["Speech", "Modify Speech", "Language Convert", "Voice Change", "Dub"])
        self.sub_mode.currentTextChanged.connect(self.on_submode_changed)
        mode_row = QHBoxLayout()
        mode_label = QLabel("Task Type")
        mode_label.setStyleSheet(f"color: {THEME['text']}; font-size: 13px; min-width: 90px;")
        mode_row.addWidget(mode_label)
        mode_row.addWidget(self.sub_mode, stretch=1)
        mode_row.addStretch()
        self.inner.addLayout(mode_row)

        self.container = QWidget()
        self.container.setStyleSheet("background: transparent;")
        self.container_layout = QVBoxLayout(self.container)
        self.container_layout.setContentsMargins(0, 0, 0, 0)
        self.container_layout.setSpacing(8)
        self.inner.addWidget(self.container)

        self.overdose_cb = HelperWidgets.make_checkbox(self.inner, "Enhanced Analysis (VibeVoice ASR for dialogue source)")
        self.extreme_cb = HelperWidgets.make_checkbox(self.inner, "Enhanced Synthesis (Fish Speech S2Pro, .ttse voice files)")
        self.result_edit = HelperWidgets.make_save_picker(self.inner, "Result Path", "Optional: copy output to this path")

        self.run_btn = QPushButton("Run Speech")
        self.run_btn.setStyleSheet(get_main_button_style())
        self.run_btn.setCursor(Qt.PointingHandCursor)
        self.run_btn.clicked.connect(self.on_run)
        self.inner.addWidget(self.run_btn)

        self.tts_status_label = QLabel("Ready — choose a voice source, enter text, then click Run Speech.")
        self.tts_status_label.setWordWrap(True)
        self.tts_status_label.setStyleSheet(
            f"color: {THEME['text_secondary']}; font-size: 12px; padding: 4px 2px;"
        )
        self.inner.addWidget(self.tts_status_label)
        self.inner.addStretch()
        scroll.setWidget(scroll_widget)
        layout.addWidget(scroll)
        self.on_submode_changed("Speech")

    def set_generation_status(self, message, success=None):
        if not hasattr(self, "tts_status_label"):
            return
        self.tts_status_label.setText(message)
        if success is True:
            color = THEME.get("success", THEME["accent"])
        elif success is False:
            color = THEME.get("error", "#e05b5b")
        else:
            color = THEME["text_secondary"]
        self.tts_status_label.setStyleSheet(
            f"color: {color}; font-size: 12px; padding: 4px 2px;"
        )

    def clear_container(self):
        while self.container_layout.count():
            item = self.container_layout.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()
            elif item.layout():
                while item.layout().count():
                    sub = item.layout().takeAt(0)
                    sw = sub.widget()
                    if sw:
                        sw.deleteLater()

    def on_submode_changed(self, mode):
        self.clear_container()
        if mode == "Speech":
            self.build_tts_ui()
            pending = getattr(self, "_pending_adopt_name", "")
            if pending:
                self._pending_adopt_name = ""
                self.tts_saved_voices.select_saved_voice(pending)
        elif mode == "Modify Speech":
            self.build_modify_speech_ui()
        elif mode == "Language Convert":
            self.build_slc_ui()
        elif mode == "Voice Change":
            self.build_svc_ui()
        elif mode == "Dub":
            self.build_dub_ui()

    def build_tts_ui(self):
        mode_row = QHBoxLayout()
        self.tts_mode_single = QRadioButton("Single")
        self.tts_mode_single.setStyleSheet(get_radio_button_style())
        self.tts_mode_single.setChecked(True)
        self.tts_mode_dialogue = QRadioButton("Dialogue")
        self.tts_mode_dialogue.setStyleSheet(get_radio_button_style())
        mode_row.addWidget(self.tts_mode_single)
        mode_row.addWidget(self.tts_mode_dialogue)
        mode_row.addStretch()
        self.container_layout.addLayout(mode_row)

        self.tts_script_label = QLabel("Text / Dialogue")
        self.tts_script_label.setStyleSheet(f"color: {THEME['text']}; font-size: 13px;")
        self.container_layout.addWidget(self.tts_script_label)

        self.tts_script_text = QTextEdit()
        self.tts_script_text.setPlaceholderText("Enter text...")
        self.tts_script_text.setStyleSheet(get_text_edit_style())
        self.tts_script_text.setMinimumHeight(100)
        self.tts_script_text.setMaximumHeight(200)
        self.container_layout.addWidget(self.tts_script_text)

        self.single_directives = DirectivesWidget(show_duration=False)
        self.container_layout.addWidget(self.single_directives)

        self.tts_dialogue_container = QWidget()
        self.tts_dialogue_container.setStyleSheet("background: transparent;")
        dlg_layout = QVBoxLayout(self.tts_dialogue_container)
        dlg_layout.setContentsMargins(0, 0, 0, 0)
        dlg_layout.setSpacing(4)

        import_row = QHBoxLayout()
        import_script_btn = QPushButton("Import Script")
        import_script_btn.setStyleSheet(get_surface_button_style())
        import_script_btn.setCursor(Qt.PointingHandCursor)
        import_script_btn.clicked.connect(self.on_import_script)
        import_audio_btn = QPushButton("Import Audio")
        import_audio_btn.setStyleSheet(get_surface_button_style())
        import_audio_btn.setCursor(Qt.PointingHandCursor)
        import_audio_btn.clicked.connect(self.on_import_audio)
        paste_script_btn = QPushButton("Paste Script")
        paste_script_btn.setStyleSheet(get_surface_button_style())
        paste_script_btn.setCursor(Qt.PointingHandCursor)
        paste_script_btn.setToolTip("Paste a whole conversation, one 'Name: text' per line")
        paste_script_btn.clicked.connect(self.paste_dialogue_script)
        add_line_btn = QPushButton("+ Add Line")
        add_line_btn.setStyleSheet(get_surface_button_style())
        add_line_btn.setCursor(Qt.PointingHandCursor)
        add_line_btn.setToolTip("Add another speaker line")
        add_line_btn.clicked.connect(self.add_dialogue_line)
        import_row.addWidget(import_script_btn)
        import_row.addWidget(import_audio_btn)
        import_row.addWidget(paste_script_btn)
        import_row.addWidget(add_line_btn)
        import_row.addStretch()
        dlg_layout.addLayout(import_row)

        self.dialogue_hint = QLabel(
            "One line per speaker, e.g.  islam: Hello!  /  despina: Hi there!  "
            "Paste the whole script with the Paste Script button."
        )
        self.dialogue_hint.setWordWrap(True)
        self.dialogue_hint.setStyleSheet(
            f"color: {THEME['text_secondary']}; font-size: 11px; padding: 0 2px;"
        )
        dlg_layout.addWidget(self.dialogue_hint)

        self.dialogue_speakers_label = QLabel("")
        self.dialogue_speakers_label.setWordWrap(True)
        self.dialogue_speakers_label.setStyleSheet(
            f"color: {THEME['text']}; font-size: 11px; padding: 0 2px;"
        )
        dlg_layout.addWidget(self.dialogue_speakers_label)

        self.tts_dialogue_widget = DialogueScriptWidget()
        self.tts_dialogue_widget.setMinimumHeight(120)
        self.tts_dialogue_widget.setMaximumHeight(300)
        dlg_layout.addWidget(self.tts_dialogue_widget)

        self.timeline_widget = DialogueTimelineWidget()
        dlg_layout.addWidget(self.timeline_widget)

        self.container_layout.addWidget(self.tts_dialogue_container)
        self.tts_dialogue_container.hide()

        self.tts_mode_single.toggled.connect(self._on_tts_mode_changed)
        self.tts_dialogue_widget.characters_changed.connect(self._on_characters_changed)
        self.tts_dialogue_widget.characters_committed.connect(self._on_characters_committed)

        HelperWidgets.make_separator(self.container_layout)
        HelperWidgets.make_label(self.container_layout, "VOICE SOURCE — choose ONE")
        self.tts_voice_source = QComboBox()
        self.tts_voice_source.setStyleSheet(get_combo_box_style())
        sources = [VOICE_SOURCE_SAVED, VOICE_SOURCE_DESCRIBE, VOICE_SOURCE_FILE]
        if not vlib.list_voices():
            # Nothing trained yet: start on the description so the user is not
            # staring at an empty picker.
            sources = [VOICE_SOURCE_DESCRIBE, VOICE_SOURCE_SAVED, VOICE_SOURCE_FILE]
        self.tts_voice_source.addItems(sources)
        self.tts_voice_source.setToolTip(
            "Saved voices are picked from a list. You never need to paste a path or link."
        )
        self.container_layout.addWidget(self.tts_voice_source)

        self.tts_voice_help = QLabel("")
        self.tts_voice_help.setWordWrap(True)
        self.tts_voice_help.setStyleSheet(
            f"color: {THEME['text_secondary']}; font-size: 12px; padding: 2px 4px;"
        )
        self.container_layout.addWidget(self.tts_voice_help)

        # --- Saved voice clones (the everyday path) ---------------------
        self.tts_saved_container = QWidget()
        self.tts_saved_container.setStyleSheet("background: transparent;")
        saved_layout = QVBoxLayout(self.tts_saved_container)
        saved_layout.setContentsMargins(0, 0, 0, 0)
        saved_layout.setSpacing(4)
        self.tts_saved_voices = CharacterVoiceList(allow_file=False, show_character=True)
        self.tts_saved_voices.train_requested.connect(self.train_voice_requested.emit)
        self.tts_saved_voices.set_expect_enhanced(self.extreme_cb.isChecked())
        saved_layout.addWidget(self.tts_saved_voices)
        self.container_layout.addWidget(self.tts_saved_container)

        # --- AI voice description ---------------------------------------
        self.tts_description_container = QWidget()
        self.tts_description_container.setStyleSheet("background: transparent;")
        desc_layout = QVBoxLayout(self.tts_description_container)
        desc_layout.setContentsMargins(0, 0, 0, 0)
        desc_layout.setSpacing(4)
        self.tts_voice_prompt_label = QLabel("AI voice description (per character)")
        self.tts_voice_prompt_label.setStyleSheet(f"color: {THEME['text']}; font-size: 13px;")
        desc_layout.addWidget(self.tts_voice_prompt_label)
        self.tts_voice_list = KeyValueList(
            "Character", "Voice Description", "Character name", "e.g. warm, friendly female voice"
        )
        self.tts_voice_list.setMinimumHeight(80)
        self.tts_voice_list.add_btn.hide()
        desc_layout.addWidget(self.tts_voice_list)
        self.container_layout.addWidget(self.tts_description_container)

        # --- One-off audio reference ------------------------------------
        self.tts_reference_container = QWidget()
        self.tts_reference_container.setStyleSheet("background: transparent;")
        ref_layout = QVBoxLayout(self.tts_reference_container)
        ref_layout.setContentsMargins(0, 0, 0, 0)
        ref_layout.setSpacing(4)
        self.tts_reference_label = QLabel("Audio reference (per character)")
        self.tts_reference_label.setStyleSheet(f"color: {THEME['text']}; font-size: 13px;")
        ref_layout.addWidget(self.tts_reference_label)
        self.tts_clone_list = KeyValueList(
            "Character", "Audio Reference", "Character name", "path/to/voice.wav", with_browse=True
        )
        self.tts_clone_list.setMinimumHeight(80)
        self.tts_clone_list.add_btn.hide()
        ref_layout.addWidget(self.tts_clone_list)
        self.container_layout.addWidget(self.tts_reference_container)

        self.tts_voice_source.currentTextChanged.connect(self._on_voice_source_changed)
        self._on_voice_source_changed(self.tts_voice_source.currentText())

        self.tts_first_cb = HelperWidgets.make_checkbox(self.container_layout, "Use First as Speaker Template")

        self.tts_sts_prefix_cb = HelperWidgets.make_checkbox(self.container_layout, "Voice Refinement Pass (route target through voice conversion)")

        self._on_voice_source_changed(self.tts_voice_source.currentText())

        HelperWidgets.make_separator(self.container_layout)
        self.tts_music_edit = HelperWidgets.make_line_edit(self.container_layout, "Music Desc", "Background music description (dialogue mode)")
        self.tts_level_edit = HelperWidgets.make_line_edit(self.container_layout, "Music Level", 'e.g. "10:20-50 30:60-80"')
        self.tts_reference_audio = AudioReferenceWidget("Music Ref", file_filter="Audio Files (*.wav *.mp3 *.flac *.ogg);;Video Files (*.mp4 *.avi *.mov *.mkv);;All Files (*)")
        self.container_layout.addWidget(self.tts_reference_audio)
        self.tts_ocr_edit = HelperWidgets.make_file_picker(self.container_layout, "OCR Image", "Path to image for text extraction", "Images (*.png *.jpg *.jpeg *.bmp *.gif *.tiff *.webp)")

        self._update_timeline()

    def build_modify_speech_ui(self):
        self.ms_source_audio = AudioReferenceWidget("Source Audio", file_filter="Audio Files (*.wav *.mp3 *.flac *.ogg);;Video Files (*.mp4 *.avi *.mov *.mkv);;All Files (*)")
        self.container_layout.addWidget(self.ms_source_audio)
        self.ms_overdose_cb = HelperWidgets.make_checkbox(self.container_layout, "Enhanced Analysis (VibeVoice ASR)")
        HelperWidgets.make_label(self.container_layout, "Transcribed Text (editable):")
        self.ms_script_text = QTextEdit()
        self.ms_script_text.setPlaceholderText("Click Transcribe first, then edit the text here...")
        self.ms_script_text.setStyleSheet(get_text_edit_style())
        self.ms_script_text.setMinimumHeight(120)
        self.ms_script_text.setMaximumHeight(240)
        self.container_layout.addWidget(self.ms_script_text)
        HelperWidgets.make_label(self.container_layout, "Voice Target — pick a saved voice, or use a reference file")
        self.ms_saved_voice = SavedVoicePickerRow(show_character=False, allow_file=False)
        self.container_layout.addWidget(self.ms_saved_voice)
        self.ms_target_audio = AudioReferenceWidget("Voice Reference (optional)", file_filter="Audio Files (*.wav *.mp3 *.flac *.ogg);;All Files (*)")
        self.container_layout.addWidget(self.ms_target_audio)
        self.ms_extreme_cb = HelperWidgets.make_checkbox(self.container_layout, "Enhanced Synthesis (Fish Speech S2Pro)")
        self.ms_extreme_cb.stateChanged.connect(self._update_voice_mode_hints)
        self.ms_saved_voice.set_expect_enhanced(self.ms_extreme_cb.isChecked())
        self.ms_preserve_cb = HelperWidgets.make_checkbox(self.container_layout, "Preserve non-vocals (keep music/instruments)")
        ms_btn_row = QHBoxLayout()
        self.ms_transcribe_btn = QPushButton("Transcribe")
        self.ms_transcribe_btn.setStyleSheet(get_surface_button_style())
        self.ms_transcribe_btn.setCursor(Qt.PointingHandCursor)
        self.ms_transcribe_btn.clicked.connect(self.on_ms_transcribe)
        ms_btn_row.addWidget(self.ms_transcribe_btn)
        self.ms_synthesize_btn = QPushButton("Synthesize")
        self.ms_synthesize_btn.setStyleSheet(get_main_button_style())
        self.ms_synthesize_btn.setCursor(Qt.PointingHandCursor)
        self.ms_synthesize_btn.clicked.connect(self.on_ms_synthesize)
        ms_btn_row.addWidget(self.ms_synthesize_btn)
        ms_btn_row.addStretch()
        self.container_layout.addLayout(ms_btn_row)

    def on_ms_transcribe(self):
        source = self.ms_source_audio.get_path() if hasattr(self, 'ms_source_audio') else ""
        if not source:
            return
        args = ["stt", source]
        self.transcribe_signal.emit(args)

    def on_ms_synthesize(self):
        args = self.build_args()
        if args:
            self.run_signal.emit(args)

    def set_ms_transcription(self, text):
        if hasattr(self, 'ms_script_text'):
            self.ms_script_text.setText(text)

    def build_slc_ui(self):
        self.slc_input_audio = AudioReferenceWidget("Source Audio", file_filter="Audio Files (*.wav *.mp3 *.flac *.ogg);;Video Files (*.mp4 *.avi *.mov *.mkv);;All Files (*)")
        self.container_layout.addWidget(self.slc_input_audio)
        self.slc_target_audio = AudioReferenceWidget("Voice Reference", file_filter="Audio Files (*.wav *.mp3 *.flac *.ogg);;All Files (*)")
        self.container_layout.addWidget(self.slc_target_audio)
        self.slc_music_cb = HelperWidgets.make_checkbox(self.container_layout, "Preserve non-vocals (keep music)")
        self.slc_translate_cb = HelperWidgets.make_checkbox(self.container_layout, "Translate")
        self.slc_lang_source = HelperWidgets.make_line_edit(self.container_layout, "Source Lang", "Source language code (e.g. en, auto)")
        self.slc_lang_target = HelperWidgets.make_line_edit(self.container_layout, "Target Lang", "Target language code (e.g. ja, ar)")
        self.slc_extreme_cb = HelperWidgets.make_checkbox(self.container_layout, "Enhanced Synthesis (Fish Speech S2Pro)")

    def build_svc_ui(self):
        self.svc_input_audio = AudioReferenceWidget("Source Audio", file_filter="Audio Files (*.wav *.mp3 *.flac *.ogg);;Video Files (*.mp4 *.avi *.mov *.mkv);;All Files (*)")
        self.container_layout.addWidget(self.svc_input_audio)
        HelperWidgets.make_label(self.container_layout, "Voice Target — pick a saved voice, or use a reference file / description")
        self.svc_saved_voice = SavedVoicePickerRow(show_character=False, allow_file=False)
        self.container_layout.addWidget(self.svc_saved_voice)
        self.svc_target_audio = AudioReferenceWidget("Voice Reference (optional)", file_filter="Audio Files (*.wav *.mp3 *.flac *.ogg);;All Files (*)")
        self.container_layout.addWidget(self.svc_target_audio)
        self.svc_voice_edit = HelperWidgets.make_line_edit(self.container_layout, "Voice Desc", "e.g. deep male voice (alternative to reference file)")
        self.svc_extreme_cb = HelperWidgets.make_checkbox(self.container_layout, "Enhanced Synthesis (Fish Speech S2Pro)")
        self.svc_extreme_cb.stateChanged.connect(self._update_voice_mode_hints)
        self.svc_saved_voice.set_expect_enhanced(self.svc_extreme_cb.isChecked())

    def build_dub_ui(self):
        self.dub_source_audio = AudioReferenceWidget("Source Video/Audio", file_filter="Video Files (*.mp4 *.avi *.mov *.mkv);;Audio Files (*.wav *.mp3 *.flac *.ogg);;All Files (*)")
        self.container_layout.addWidget(self.dub_source_audio)
        self.dub_subtitle_cb = HelperWidgets.make_checkbox(self.container_layout, "Generate subtitles")
        self.dub_subtitle_original_cb = HelperWidgets.make_checkbox(self.container_layout, "Keep original language subtitles")
        self.dub_subtitle_lang_source = HelperWidgets.make_line_edit(self.container_layout, "Subtitle Lang", "Source-Target e.g. auto-ar (optional)")
        self.dub_translate_lang_source = HelperWidgets.make_line_edit(self.container_layout, "Translate Lang", "Source-Target e.g. auto-ar")
        self.dub_translate_cb = HelperWidgets.make_checkbox(self.container_layout, "Translate (enable with lang spec above)")
        self.dub_se_cb = HelperWidgets.make_checkbox(self.container_layout, "Apply sound enhancement during dub")
        self.dub_video_cb = HelperWidgets.make_checkbox(self.container_layout, "Output video file")
        self.dub_overdose_cb = HelperWidgets.make_checkbox(self.container_layout, "Enhanced Analysis (VibeVoice ASR)")

    def on_import_script(self):
        path, _ = QFileDialog.getOpenFileName(None, "Import Script", "", "Text Files (*.txt);;All Files (*)")
        if path:
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    content = f.read()
                if hasattr(self, 'tts_dialogue_widget'):
                    self.tts_dialogue_widget.set_text(content)
            except Exception:
                pass

    def on_import_audio(self):
        path, _ = QFileDialog.getOpenFileName(None, "Import Audio", "", "Audio (*.wav *.mp3 *.flac *.ogg);;Video (*.mp4 *.avi *.mov *.mkv);;All Files (*)")
        if path:
            self._importing_audio = True
            args = ["stt", path]
            self.transcribe_signal.emit(args)

    def paste_dialogue_script(self):
        """Paste a whole 'Name: text' conversation from the clipboard."""
        if not hasattr(self, "tts_dialogue_widget"):
            return
        text = QApplication.clipboard().text()
        if not text or not text.strip():
            self.set_generation_status("Clipboard is empty - copy the script first.", success=False)
            return
        self.tts_dialogue_widget.set_text(text)
        count = len(self.tts_dialogue_widget.get_dialogue_items())
        if count:
            self.set_generation_status(
                f"Pasted {count} dialogue line{'s' if count != 1 else ''}. "
                "Now check that every speaker has a voice below.",
                success=True,
            )
        else:
            self.set_generation_status(
                "That did not look like a script. Use one line per speaker: name: text",
                success=False,
            )

    def add_dialogue_line(self):
        if hasattr(self, "tts_dialogue_widget"):
            self.tts_dialogue_widget.add_line()
            self.set_generation_status("Added a line - choose its speaker and voice.")

    def _dialogue_missing_voices(self):
        """Characters in the script that have no voice assigned yet."""
        if not hasattr(self, "tts_dialogue_widget"):
            return []
        chars = {
            char.strip().casefold()
            for _, char, _, _ in self.tts_dialogue_widget.get_dialogue_items()
            if char.strip()
        }
        if not chars:
            return []
        source = self.tts_voice_source.currentText() if hasattr(self, "tts_voice_source") else ""
        assigned = set()
        if source.startswith(VOICE_SOURCE_SAVED):
            for char, name in self.tts_saved_voices.get_items():
                if char.strip() and name.strip():
                    assigned.add(char.strip().casefold())
        elif source.startswith(VOICE_SOURCE_DESCRIBE):
            for char, desc in self.tts_voice_list.get_items():
                if char.strip() and desc.strip():
                    assigned.add(char.strip().casefold())
        elif source.startswith(VOICE_SOURCE_FILE):
            for char, path in self.tts_clone_list.get_items():
                if char.strip() and path.strip():
                    assigned.add(char.strip().casefold())
        return sorted(chars - assigned)

    def handle_transcription_result(self, text):
        if self._importing_audio:
            self._importing_audio = False
            if hasattr(self, 'tts_dialogue_widget'):
                self.tts_dialogue_widget.set_text(text)
        else:
            self.set_ms_transcription(text)

    def _on_tts_mode_changed(self, checked):
        if checked:
            self.tts_script_text.show()
            self.tts_script_label.show()
            self.single_directives.show()
            self.tts_dialogue_container.hide()
        else:
            self.tts_script_text.hide()
            self.tts_script_label.hide()
            self.single_directives.hide()
            self.tts_dialogue_container.show()
        if hasattr(self, "dialogue_hint"):
            self.dialogue_hint.setVisible(not checked)
        if hasattr(self, "dialogue_speakers_label"):
            self.dialogue_speakers_label.setVisible(not checked)
        self._update_timeline()

    def _on_characters_changed(self, chars):
        # Fires on every keystroke: only refresh the labels/timeline here, so
        # typing "islam" does not create a picker row for "i", "is", "isl", ...
        self._update_speaker_label(chars)
        self._update_timeline()

    def _on_characters_committed(self, chars):
        # Fires when a character name is finished (focus lost / Enter) or when
        # a script is pasted, so the pickers get exactly one row per speaker.
        self.tts_voice_list.ensure_keys(chars)
        self.tts_clone_list.ensure_keys(chars)
        if hasattr(self, "tts_saved_voices"):
            self.tts_saved_voices.ensure_characters(chars)
        self._update_speaker_label(chars)
        self._update_timeline()

    def _update_speaker_label(self, chars):
        if not hasattr(self, "dialogue_speakers_label"):
            return
        names = sorted({c.strip() for c in chars if c and c.strip()}, key=str.casefold)
        single = hasattr(self, "tts_mode_single") and self.tts_mode_single.isChecked()
        self.dialogue_speakers_label.setVisible(not single)
        if names:
            self.dialogue_speakers_label.setText(
                f"{len(names)} speaker{'s' if len(names) != 1 else ''}: "
                + ", ".join(names)
                + "  -  each one picks a voice below."
            )
        else:
            self.dialogue_speakers_label.setText(
                "No speakers yet - type a line above or click Paste Script."
            )

    def _on_voice_source_changed(self, selection):
        """Show only the selected voice source so the fields are not confusing."""
        use_saved = selection.startswith(VOICE_SOURCE_SAVED)
        use_description = selection.startswith(VOICE_SOURCE_DESCRIBE)
        use_reference = selection.startswith(VOICE_SOURCE_FILE)

        self.tts_saved_container.setVisible(use_saved)
        self.tts_description_container.setVisible(use_description)
        self.tts_reference_container.setVisible(use_reference)
        if hasattr(self, "tts_first_cb"):
            self.tts_first_cb.setVisible(use_reference)
            self.tts_sts_prefix_cb.setVisible(use_reference)

        if use_saved:
            count = len({v.name.casefold() for v in vlib.list_voices()})
            if count:
                self.tts_voice_help.setText(
                    f"Pick one of your {count} saved voice{'s' if count != 1 else ''} by "
                    "name. Every character can use a different saved voice."
                )
            else:
                self.tts_voice_help.setText(
                    "You have no saved voices yet. Click '+ Train New' above (or use the "
                    "Make Voice tab), then the voice appears here automatically."
                )
        elif use_description:
            self.tts_voice_help.setText(
                "Describe the voice you want, e.g. warm, friendly female voice. "
                "This creates a voice style; it does NOT load a saved clone. "
                "Arabic can't be described - it is cloned from a saved Darija voice, "
                "so pick 'Saved voices' instead."
            )
        else:
            self.tts_voice_help.setText(
                "Choose a clean WAV/MP3 sample of the voice to use as a one-off "
                "reference. This is not a saved VODER voice profile."
            )

    def refresh_voice_library(self):
        """Re-scan the voices folder after training, renaming or deleting."""
        try:
            if hasattr(self, "tts_saved_voices"):
                self.tts_saved_voices.refresh()
            if self.sub_mode.currentText() == "Speech":
                self._on_voice_source_changed(self.tts_voice_source.currentText())
        except RuntimeError:
            # The current sub-mode was rebuilt and a stale widget is gone.
            pass

    def _update_voice_mode_hints(self):
        enhanced = self.extreme_cb.isChecked()
        try:
            if hasattr(self, "tts_saved_voices"):
                self.tts_saved_voices.set_expect_enhanced(enhanced)
        except RuntimeError:
            pass
        try:
            if hasattr(self, "ms_saved_voice"):
                self.ms_saved_voice.set_expect_enhanced(
                    self.ms_extreme_cb.isChecked() if hasattr(self, "ms_extreme_cb") else enhanced
                )
        except RuntimeError:
            pass
        try:
            if hasattr(self, "svc_saved_voice"):
                self.svc_saved_voice.set_expect_enhanced(
                    self.svc_extreme_cb.isChecked() if hasattr(self, "svc_extreme_cb") else enhanced
                )
        except RuntimeError:
            pass

    def adopt_saved_voice(self, name):
        """Called from the Voice Library: switch to saved voices and pick one."""
        if not name:
            return
        if self.sub_mode.currentText() != "Speech":
            # Speech UI is not built right now; remember it for later.
            self._pending_adopt_name = name
            return
        try:
            index = self.tts_voice_source.findText(VOICE_SOURCE_SAVED)
            if index >= 0:
                self.tts_voice_source.setCurrentIndex(index)
            self.tts_saved_voices.select_saved_voice(name)
            self._on_voice_source_changed(self.tts_voice_source.currentText())
        except RuntimeError:
            self._pending_adopt_name = name

    def _update_timeline(self):
        if hasattr(self, 'tts_dialogue_widget') and hasattr(self, 'timeline_widget'):
            items = self.tts_dialogue_widget.get_timeline_data()
            music_desc = self.tts_music_edit.text().strip() if hasattr(self, 'tts_music_edit') else ""
            max_time = 30
            for item in items:
                t = item.get('time', 0)
                if t > max_time:
                    max_time = t + 10
            self.timeline_widget.set_data(items, music_desc, max_time)

    def build_args(self):
        mode = self.sub_mode.currentText()
        args = ["tts"]

        if mode == "Speech":
            is_dialogue = not self.tts_mode_single.isChecked() if hasattr(self, 'tts_mode_single') else False

            ocr = self.tts_ocr_edit.text().strip() if hasattr(self, 'tts_ocr_edit') else ""
            if ocr:
                args.extend(["ocr", ocr])

            if is_dialogue:
                items = self.tts_dialogue_widget.get_dialogue_items()
                if not items and not ocr:
                    return None
                for idx, char, text, directives in items:
                    script_text = f"{char}: {text}"
                    if directives:
                        script_text += f" {directives}"
                    args.extend(["script", script_text])
            else:
                script = self.tts_script_text.toPlainText().strip() if hasattr(self, 'tts_script_text') else ""
                directives = self.single_directives.get_directives_string() if hasattr(self, 'single_directives') else ""
                if not script and not ocr:
                    return None
                if script:
                    if directives:
                        script += f" {directives}"
                    args.extend(["script", script])

            voice_source = self.tts_voice_source.currentText() if hasattr(self, 'tts_voice_source') else VOICE_SOURCE_DESCRIBE
            if voice_source.startswith(VOICE_SOURCE_SAVED):
                saved = []
                for char, name in self.tts_saved_voices.get_items():
                    char = (char or "").strip() or name
                    if name:
                        saved.append((char, name))
                if not is_dialogue:
                    # Single = one speaker: ignore any extra rows so the user
                    # cannot accidentally build an invalid two-voice command.
                    saved = saved[:1]
                for char, name in saved:
                    args.extend(["voice", f"{char}: {name}"])
                # Single-speaker TTS treats a named voice as a dialogue prompt,
                # so label the script with the character automatically.
                if not is_dialogue and len(saved) == 1 and script:
                    speaker = saved[0][0]
                    script_arg_index = next((i + 1 for i, value in enumerate(args[:-1]) if value == "script"), None)
                    if script_arg_index is not None:
                        current_script = args[script_arg_index]
                        if not current_script.lstrip().lower().startswith(speaker.lower() + ":"):
                            args[script_arg_index] = f"{speaker}: {current_script}"
            elif voice_source.startswith(VOICE_SOURCE_DESCRIBE):
                voice_items = [(char.strip(), desc.strip()) for char, desc in self.tts_voice_list.get_items() if char.strip() and desc.strip()]
                if not is_dialogue:
                    voice_items = voice_items[:1]
                for char, desc in voice_items:
                    args.extend(["voice", f"{char}: {desc}"])
                # The CLI parses character-labelled scripts whenever a named
                # voice prompt is supplied. Add the character automatically
                # in Single mode so users never have to type "name:".
                if not is_dialogue and len(voice_items) == 1 and script:
                    speaker = voice_items[0][0]
                    script_arg_index = next((i + 1 for i, value in enumerate(args[:-1]) if value == "script"), None)
                    if script_arg_index is not None:
                        current_script = args[script_arg_index]
                        if not current_script.lstrip().lower().startswith(speaker.lower() + ":"):
                            args[script_arg_index] = f"{speaker}: {current_script}"
            elif voice_source.startswith(VOICE_SOURCE_FILE):
                first_checked = hasattr(self, 'tts_first_cb') and self.tts_first_cb.isChecked()
                clone_items = [(char, path) for char, path in self.tts_clone_list.get_items() if path.strip()]
                if not is_dialogue:
                    clone_items = clone_items[:1]
                used_speaker = ""
                for char, path in clone_items:
                    if not path.strip():
                        continue
                    char = (char or "").strip() or "Speaker"
                    used_speaker = char
                    target_val = path.strip()
                    if hasattr(self, 'tts_sts_prefix_cb') and self.tts_sts_prefix_cb.isChecked():
                        target_val = "sts:" + target_val
                    if first_checked:
                        args.extend(["target", "first", f"{char}: {target_val}"])
                    else:
                        args.extend(["target", f"{char}: {target_val}"])
                if not is_dialogue and used_speaker and script:
                    script_arg_index = next((i + 1 for i, value in enumerate(args[:-1]) if value == "script"), None)
                    if script_arg_index is not None:
                        current_script = args[script_arg_index]
                        if not current_script.lstrip().lower().startswith(used_speaker.lower() + ":"):
                            args[script_arg_index] = f"{used_speaker}: {current_script}"

            music = self.tts_music_edit.text().strip() if hasattr(self, 'tts_music_edit') else ""
            if music:
                args.extend(["music", music])

            level = self.tts_level_edit.text().strip() if hasattr(self, 'tts_level_edit') else ""
            if level:
                args.extend(["level", level])

            reference = self.tts_reference_audio.get_path() if hasattr(self, 'tts_reference_audio') else ""
            if reference:
                args.extend(["reference", reference])

        elif mode == "Modify Speech":
            script = self.ms_script_text.toPlainText().strip() if hasattr(self, 'ms_script_text') else ""
            if not script:
                return None
            saved = ""
            if hasattr(self, 'ms_saved_voice'):
                saved = self.ms_saved_voice.current_value().strip()
            target = self.ms_target_audio.get_path() if hasattr(self, 'ms_target_audio') else ""
            source = self.ms_source_audio.get_path() if hasattr(self, 'ms_source_audio') else ""
            if saved:
                # Use the trained voice directly instead of a voice-conversion
                # reference: the script must carry the speaker label.
                args.extend(["script", f"{saved}: {script}"])
                args.extend(["voice", f"{saved}: {saved}"])
            else:
                reference = target or source
                args.extend(["script", f"Speaker: {script}"])
                if reference:
                    args.extend(["target", f"Speaker: {reference}"])

        elif mode == "Language Convert":
            input_path = self.slc_input_audio.get_path() if hasattr(self, 'slc_input_audio') else ""
            if not input_path:
                return None
            args.append("slc")
            if hasattr(self, 'slc_translate_cb') and self.slc_translate_cb.isChecked():
                args.append("translate")
                lang_src = self.slc_lang_source.text().strip() if hasattr(self, 'slc_lang_source') else ""
                lang_tgt = self.slc_lang_target.text().strip() if hasattr(self, 'slc_lang_target') else ""
                if lang_src or lang_tgt:
                    src = lang_src or "auto"
                    tgt = lang_tgt or "en"
                    args.append(f"({src}-{tgt})")
            if hasattr(self, 'slc_music_cb') and self.slc_music_cb.isChecked():
                args.append("music")
            args.append(input_path)
            if hasattr(self, 'slc_target_audio') and self.slc_target_audio.get_path():
                args.extend(["target", self.slc_target_audio.get_path()])

        elif mode == "Voice Change":
            input_path = self.svc_input_audio.get_path() if hasattr(self, 'svc_input_audio') else ""
            if not input_path:
                return None
            args.append("svc")
            args.append(input_path)
            saved = self.svc_saved_voice.current_value().strip() if hasattr(self, 'svc_saved_voice') else ""
            target = self.svc_target_audio.get_path() if hasattr(self, 'svc_target_audio') else ""
            voice = self.svc_voice_edit.text().strip() if hasattr(self, 'svc_voice_edit') else ""
            if saved:
                args.extend(["target", saved])
            elif target:
                args.extend(["target", target])
            elif voice:
                args.extend(["voice", voice])

        elif mode == "Dub":
            source = self.dub_source_audio.get_path() if hasattr(self, 'dub_source_audio') else ""
            if not source:
                return None
            args.append("dub")
            args.append(source)
            if hasattr(self, 'dub_subtitle_cb') and self.dub_subtitle_cb.isChecked():
                args.append("subtitle")
                if hasattr(self, 'dub_subtitle_original_cb') and self.dub_subtitle_original_cb.isChecked():
                    args.append("original")
                sub_lang = self.dub_subtitle_lang_source.text().strip() if hasattr(self, 'dub_subtitle_lang_source') else ""
                if sub_lang:
                    args.append(f"({sub_lang})")
            if hasattr(self, 'dub_translate_cb') and self.dub_translate_cb.isChecked():
                args.append("translate")
                trans_lang = self.dub_translate_lang_source.text().strip() if hasattr(self, 'dub_translate_lang_source') else ""
                if trans_lang:
                    args.append(f"({trans_lang})")
                else:
                    args.append("(auto-en)")
            if hasattr(self, 'dub_se_cb') and self.dub_se_cb.isChecked():
                args.append("se")
            if hasattr(self, 'dub_video_cb') and self.dub_video_cb.isChecked():
                args.append("video")
            if hasattr(self, 'dub_overdose_cb') and self.dub_overdose_cb.isChecked():
                args.append("overdose")

        if self.overdose_cb.isChecked() and mode not in ("Dub", "Modify Speech"):
            args.append("overdose")
        if mode == "Modify Speech" and hasattr(self, 'ms_overdose_cb') and self.ms_overdose_cb.isChecked():
            args.append("overdose")
        if mode == "Language Convert" and hasattr(self, 'slc_extreme_cb') and self.slc_extreme_cb.isChecked():
            args.append("extreme")
        elif mode == "Voice Change" and hasattr(self, 'svc_extreme_cb') and self.svc_extreme_cb.isChecked():
            args.append("extreme")
        elif mode == "Modify Speech" and hasattr(self, 'ms_extreme_cb') and self.ms_extreme_cb.isChecked():
            args.append("extreme")
        elif self.extreme_cb.isChecked() and mode not in ("Dub", "Language Convert", "Voice Change", "Modify Speech"):
            args.append("extreme")
        if self.result_edit.text().strip():
            args.extend(["result", self.result_edit.text().strip()])
        return args

    def on_run(self):
        if self.sub_mode.currentText() == "Speech" and hasattr(self, "tts_mode_single"):
            if not self.tts_mode_single.isChecked():
                if not self.tts_dialogue_widget.get_dialogue_items():
                    self.set_generation_status(
                        "Add at least one 'Name: text' line, or click Paste Script.",
                        success=False,
                    )
                    return
                missing = self._dialogue_missing_voices()
                if missing:
                    self.set_generation_status(
                        "Pick a voice for: " + ", ".join(missing)
                        + ". Use the voice picker below the script.",
                        success=False,
                    )
                    return
        args = self.build_args()
        if args:
            self.run_signal.emit(args)


class STSTab(QWidget):
    run_signal = pyqtSignal(list)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(8)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setStyleSheet("QScrollArea { background: transparent; }")
        scroll_widget = QWidget()
        scroll_widget.setStyleSheet("background: transparent;")
        inner = QVBoxLayout(scroll_widget)
        inner.setSpacing(8)

        self.base_audio = AudioReferenceWidget("Source Audio", file_filter="Audio Files (*.wav *.mp3 *.flac *.ogg);;Video Files (*.mp4 *.avi *.mov *.mkv);;All Files (*)")
        inner.addWidget(self.base_audio)
        self.target_audio = AudioReferenceWidget("Voice Reference", file_filter="Audio Files (*.wav *.mp3 *.flac *.ogg);;All Files (*)")
        inner.addWidget(self.target_audio)
        self.music_cb = HelperWidgets.make_checkbox(inner, "Music mode (Seed-VC v1, 44.1kHz)")
        self.mimic_cb = HelperWidgets.make_checkbox(inner, "Style + Voice Transfer")
        self.nomusic_cb = HelperWidgets.make_checkbox(inner, "Voice Only (No Music)")
        self.original_cb = HelperWidgets.make_checkbox(inner, "Skip Source Separation")
        self.overdose_cb = HelperWidgets.make_checkbox(inner, "Enhanced Analysis (VibeVoice ASR)")
        self.extreme_cb = HelperWidgets.make_checkbox(inner, "Enhanced Synthesis (Fish Speech S2Pro)")

        self.music_cb.toggled.connect(lambda checked: self.mimic_cb.setChecked(False) if checked else None)
        self.mimic_cb.toggled.connect(lambda checked: self.music_cb.setChecked(False) if checked else None)
        self.music_cb.toggled.connect(lambda checked: self.nomusic_cb.setChecked(False) if checked else None)
        self.nomusic_cb.toggled.connect(lambda checked: self.music_cb.setChecked(False) if checked else None)
        self.original_cb.toggled.connect(lambda checked: self.music_cb.setChecked(False) if checked else None)
        self.music_cb.toggled.connect(lambda checked: self.original_cb.setChecked(False) if checked else None)

        self.sts_first_cb = HelperWidgets.make_checkbox(inner, "Use First as Speaker Template")

        HelperWidgets.make_label(inner, "Additional Voice References")
        self.sts_extra_refs = FileListWidget(inner, file_filter="Audio (*.wav *.mp3 *.flac *.ogg);;All Files (*)")
        inner.addWidget(self.sts_extra_refs)

        self.result_edit = HelperWidgets.make_save_picker(inner, "Result Path", "Optional: copy output to this path")

        self.run_btn = QPushButton("Run Voice Conversion")
        self.run_btn.setStyleSheet(get_main_button_style())
        self.run_btn.setCursor(Qt.PointingHandCursor)
        self.run_btn.clicked.connect(self.on_run)
        inner.addWidget(self.run_btn)
        inner.addStretch()
        scroll.setWidget(scroll_widget)
        layout.addWidget(scroll)

    def build_args(self):
        base_path = self.base_audio.get_path()
        target_path = self.target_audio.get_path()
        if not base_path or not target_path:
            return None
        target_val = target_path
        if hasattr(self, 'sts_extra_refs') and self.sts_extra_refs.get_paths():
            extra_paths = self.sts_extra_refs.get_paths()
            target_val = "(" + target_path + ")" + "".join(f"({ep})" for ep in extra_paths)
        first_checked = hasattr(self, 'sts_first_cb') and self.sts_first_cb.isChecked()
        args = ["sts"]
        if first_checked:
            args.extend(["target", "first", target_val])
            args.extend(["base", base_path])
        else:
            args.extend(["base", base_path, "target", target_val])
        if self.music_cb.isChecked():
            args.append("music")
        if self.mimic_cb.isChecked():
            args.append("mimic")
        if self.nomusic_cb.isChecked():
            args.append("nomusic")
        if self.original_cb.isChecked():
            args.append("original")
        if self.overdose_cb.isChecked():
            args.append("overdose")
        if self.extreme_cb.isChecked():
            args.append("extreme")
        if self.result_edit.text().strip():
            args.extend(["result", self.result_edit.text().strip()])
        return args

    def on_run(self):
        args = self.build_args()
        if args:
            self.run_signal.emit(args)


class TTMTab(QWidget):
    run_signal = pyqtSignal(list)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(8)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setStyleSheet("QScrollArea { background: transparent; }")
        scroll_widget = QWidget()
        scroll_widget.setStyleSheet("background: transparent;")
        self.inner = QVBoxLayout(scroll_widget)
        self.inner.setSpacing(8)

        self.sub_mode = QComboBox()
        self.sub_mode.setStyleSheet(get_combo_box_style())
        self.sub_mode.addItems(["Generate", "Voice", "Voice Clone (VC)", "Remix", "Repaint", "Complete", "Lego", "Extract", "BGM"])
        self.sub_mode.currentTextChanged.connect(self.on_submode_changed)
        mode_row = QHBoxLayout()
        mode_label = QLabel("Task Type")
        mode_label.setStyleSheet(f"color: {THEME['text']}; font-size: 13px; min-width: 90px;")
        mode_row.addWidget(mode_label)
        mode_row.addWidget(self.sub_mode, stretch=1)
        mode_row.addStretch()
        self.inner.addLayout(mode_row)

        self.container = QWidget()
        self.container.setStyleSheet("background: transparent;")
        self.container_layout = QVBoxLayout(self.container)
        self.container_layout.setContentsMargins(0, 0, 0, 0)
        self.container_layout.setSpacing(8)
        self.inner.addWidget(self.container)

        self.overdose_cb = HelperWidgets.make_checkbox(self.inner, "Enhanced tier (ACE-Step XL-Turbo)")
        self.result_edit = HelperWidgets.make_save_picker(self.inner, "Result Path", "Optional: copy output to this path")

        self.run_btn = QPushButton("Run Music")
        self.run_btn.setStyleSheet(get_main_button_style())
        self.run_btn.setCursor(Qt.PointingHandCursor)
        self.run_btn.clicked.connect(self.on_run)
        self.inner.addWidget(self.run_btn)
        self.inner.addStretch()
        scroll.setWidget(scroll_widget)
        layout.addWidget(scroll)
        self.on_submode_changed("Generate")

    def clear_container(self):
        while self.container_layout.count():
            item = self.container_layout.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()
            elif item.layout():
                while item.layout().count():
                    sub = item.layout().takeAt(0)
                    sw = sub.widget()
                    if sw:
                        sw.deleteLater()

    def on_submode_changed(self, mode):
        self.clear_container()
        method_name = f'build_{mode.lower().replace(" ", "_").replace("(vc)", "vc")}_ui'
        getattr(self, method_name, self.build_generate_ui)()

    def build_generate_ui(self):
        self.gen_lyrics = HelperWidgets.make_text_edit(self.container_layout, "Lyrics", "Song lyrics (use \\n for line breaks)", 100)
        self.gen_styling = HelperWidgets.make_text_edit(self.container_layout, "Styling", "Style/mood prompt", 80)
        self.gen_duration = HelperWidgets.make_spinbox(self.container_layout, "Duration (s)", 10, 300, 30)
        HelperWidgets.make_label(self.container_layout, "Reference Audio (optional, up to 3)")
        self.gen_ref_list = self._make_ttm_ref_list()
        self.container_layout.addWidget(self.gen_ref_list)

    def build_voice_ui(self):
        self.voice_lyrics = HelperWidgets.make_text_edit(self.container_layout, "Lyrics", "Song lyrics (use \\n for line breaks)", 100)
        self.voice_styling = HelperWidgets.make_text_edit(self.container_layout, "Styling", "Style/mood prompt", 80)
        self.voice_duration = HelperWidgets.make_spinbox(self.container_layout, "Duration (s)", 10, 300, 30)
        HelperWidgets.make_label(self.container_layout, "Reference Audio (optional, up to 3)")
        self.voice_ref_list = self._make_ttm_ref_list()
        self.container_layout.addWidget(self.voice_ref_list)

    def build_voice_clone_vc_ui(self):
        self.vc_lyrics = HelperWidgets.make_text_edit(self.container_layout, "Lyrics", "Song lyrics (use \\n for line breaks)", 100)
        self.vc_styling = HelperWidgets.make_text_edit(self.container_layout, "Styling", "Style/mood prompt", 80)
        self.vc_duration = HelperWidgets.make_spinbox(self.container_layout, "Duration (s)", 10, 300, 30)
        self.vc_clone_audio = AudioReferenceWidget("Clone Voice", file_filter="Audio Files (*.wav *.mp3 *.flac *.ogg);;All Files (*)")
        self.container_layout.addWidget(self.vc_clone_audio)
        self.vc_clone_first_cb = HelperWidgets.make_checkbox(self.container_layout, "Use First as Speaker Template")
        HelperWidgets.make_label(self.container_layout, "Additional Clone References")
        self.vc_clone_extra = FileListWidget(self.container_layout, file_filter="Audio (*.wav *.mp3 *.flac *.ogg);;All Files (*)")
        self.container_layout.addWidget(self.vc_clone_extra)
        HelperWidgets.make_label(self.container_layout, "Reference Audio (optional, up to 3)")
        self.vc_ref_list = self._make_ttm_ref_list()
        self.container_layout.addWidget(self.vc_ref_list)

    def build_remix_ui(self):
        self.remix_source = HelperWidgets.make_file_picker(self.container_layout, "Source", "Source audio/video or URL to remix")
        self.remix_styling = HelperWidgets.make_text_edit(self.container_layout, "Styling", "New style for the remix", 80)
        self.remix_lyrics = HelperWidgets.make_text_edit(self.container_layout, "Lyrics (opt)", "Optional new lyrics", 80)
        self.remix_bias = HelperWidgets.make_spinbox(self.container_layout, "Bias (0-100)", 0, 100, 40)
        HelperWidgets.make_label(self.container_layout, "Reference Audio (up to 3, optional)")
        self.remix_ref_list = self._make_ttm_ref_list()
        self.container_layout.addWidget(self.remix_ref_list)

    def build_repaint_ui(self):
        self.repaint_source_prefix = QComboBox()
        self.repaint_source_prefix.setStyleSheet(get_combo_box_style())
        self.repaint_source_prefix.addItems(["None", "voice", "music"])
        r = QHBoxLayout()
        rl = QLabel("Source Prefix")
        rl.setStyleSheet(f"color: {THEME['text']}; font-size: 13px; min-width: 90px;")
        r.addWidget(rl)
        r.addWidget(self.repaint_source_prefix, stretch=1)
        r.addStretch()
        self.container_layout.addLayout(r)
        self.repaint_source = HelperWidgets.make_file_picker(self.container_layout, "Source", "Source audio/video or URL to repaint")
        self.repaint_styling = HelperWidgets.make_text_edit(self.container_layout, "Styling", "New style for the repainted section", 80)
        self.repaint_time = HelperWidgets.make_line_edit(self.container_layout, "Time Range", "e.g. 20-80 or 20.5-80.5")
        self.repaint_lyrics = HelperWidgets.make_text_edit(self.container_layout, "Lyrics (opt)", "Optional lyrics for repainted section", 80)
        self.repaint_bias = HelperWidgets.make_spinbox(self.container_layout, "Bias (0-100)", 0, 100, 40)
        self.repaint_multipass = HelperWidgets.make_line_edit(self.container_layout, "Multipass", 'e.g. "20-80/orchestral" "80-100/cinematic" (optional)')
        HelperWidgets.make_label(self.container_layout, "Reference Audio (up to 3, optional)")
        self.repaint_ref_list = self._make_ttm_ref_list()
        self.container_layout.addWidget(self.repaint_ref_list)

    def build_complete_ui(self):
        self.complete_source = HelperWidgets.make_file_picker(self.container_layout, "Source", "Source audio/video or URL")
        HelperWidgets.make_label(self.container_layout, "Instruments to Add")
        self.complete_stems_selector = StemSelectorWidget()
        self.container_layout.addWidget(self.complete_stems_selector)
        self.complete_add = HelperWidgets.make_line_edit(self.container_layout, "Custom Stems", "e.g. everything, or additional stems not listed above")
        self.complete_voice_cb = HelperWidgets.make_checkbox(self.container_layout, "Pre-extract vocals (voice)")
        self.complete_music_cb = HelperWidgets.make_checkbox(self.container_layout, "Pre-extract instruments (music)")
        self.complete_voice_cb.toggled.connect(lambda checked: self.complete_music_cb.setChecked(False) if checked else None)
        self.complete_music_cb.toggled.connect(lambda checked: self.complete_voice_cb.setChecked(False) if checked else None)
        self.complete_noblend_cb = HelperWidgets.make_checkbox(self.container_layout, "No blending")
        self.complete_usrc_cb = HelperWidgets.make_checkbox(self.container_layout, "Blend with original source (usrc)")
        self.complete_video_cb = HelperWidgets.make_checkbox(self.container_layout, "Preserve video")
        self.complete_sfx_edit = HelperWidgets.make_line_edit(self.container_layout, "SFX Specs", 'e.g. "sfx:thunder/5-30/50" (optional, multiple separated by space)')
        HelperWidgets.make_label(self.container_layout, "Reference Audio (up to 3, optional)")
        self.complete_ref_list = self._make_ttm_ref_list()
        self.container_layout.addWidget(self.complete_ref_list)

    def build_lego_ui(self):
        self.lego_source = HelperWidgets.make_file_picker(self.container_layout, "Source", "Source audio/video or URL")
        HelperWidgets.make_label(self.container_layout, "Instruments to Make")
        self.lego_stems_selector = StemSelectorWidget()
        self.container_layout.addWidget(self.lego_stems_selector)
        self.lego_make = HelperWidgets.make_line_edit(self.container_layout, "Custom Stems", "e.g. everything, or additional stems not listed above")
        self.lego_voice_cb = HelperWidgets.make_checkbox(self.container_layout, "Pre-extract vocals (voice)")
        self.lego_music_cb = HelperWidgets.make_checkbox(self.container_layout, "Pre-extract instruments (music)")
        self.lego_voice_cb.toggled.connect(lambda checked: self.lego_music_cb.setChecked(False) if checked else None)
        self.lego_music_cb.toggled.connect(lambda checked: self.lego_voice_cb.setChecked(False) if checked else None)
        self.lego_mix_cb = HelperWidgets.make_checkbox(self.container_layout, "Mix all tracks into one file")
        self.lego_blend_cb = HelperWidgets.make_checkbox(self.container_layout, "Mix and blend with original")
        self.lego_mix_cb.toggled.connect(lambda checked: self.lego_blend_cb.setChecked(False) if checked else None)
        self.lego_blend_cb.toggled.connect(lambda checked: self.lego_mix_cb.setChecked(False) if checked else None)
        HelperWidgets.make_label(self.container_layout, "Reference Audio (up to 3, optional)")
        self.lego_ref_list = KeyValueList("Stem or fallback", "Audio Path", "e.g. drums or leave empty", "path/to/ref.wav", with_browse=True)
        self.lego_ref_list.setMinimumHeight(120)
        self.lego_ref_list.add_btn.hide()
        self.container_layout.addWidget(self.lego_ref_list)

    def build_extract_ui(self):
        self.extract_source = HelperWidgets.make_file_picker(self.container_layout, "Source", "Source audio/video or URL")
        HelperWidgets.make_label(self.container_layout, "Stems")
        self.extract_stems_selector = StemSelectorWidget()
        self.container_layout.addWidget(self.extract_stems_selector)
        self.extract_only_cb = HelperWidgets.make_checkbox(self.container_layout, "Only (extract everything EXCEPT specified)")
        self.extract_mix_cb = HelperWidgets.make_checkbox(self.container_layout, "Mix all extracted stems into one file")
        self.extract_only_cb.toggled.connect(lambda checked: self.extract_mix_cb.setChecked(False) if checked else None)
        self.extract_mix_cb.toggled.connect(lambda checked: self.extract_only_cb.setChecked(False) if checked else None)

    def build_bgm_ui(self):
        self.bgm_source = HelperWidgets.make_file_picker(self.container_layout, "Source", "Audio/video file or URL to add background music on")
        self.bgm_music = HelperWidgets.make_text_edit(self.container_layout, "Music Desc", "Background music style/description", 80)
        self.bgm_level = HelperWidgets.make_spinbox(self.container_layout, "Music Level", 0, 100, 35)
        self.bgm_video_cb = HelperWidgets.make_checkbox(self.container_layout, "Output video file")
        self.bgm_reference = HelperWidgets.make_file_picker(self.container_layout, "Reference (opt)", "Reference audio/video or URL for music style")
        self.bgm_sfx_edit = HelperWidgets.make_line_edit(self.container_layout, "SFX Specs", 'e.g. "sfx:rain/10-0/30" (optional, multiple by space)')

    def _make_ttm_ref_list(self):
        ref_list = TTMReferenceList()
        ref_list.setMinimumHeight(80)
        return ref_list

    def _add_ttm_refs(self, args, ref_list):
        for prefix, ref_val in ref_list.get_refs():
            if prefix and prefix != "none":
                args.extend(["reference", prefix, ref_val])
            else:
                args.extend(["reference", ref_val])

    def build_args(self):
        mode = self.sub_mode.currentText().lower()
        args = ["ttm"]
        if self.overdose_cb.isChecked():
            args.append("overdose")

        if mode == "generate":
            lyrics = self.gen_lyrics.toPlainText().strip()
            styling = self.gen_styling.toPlainText().strip()
            if not lyrics or not styling:
                return None
            args.extend(["lyrics", lyrics, "styling", styling])
            args.append(str(self.gen_duration.value()))
            if hasattr(self, 'gen_ref_list'):
                self._add_ttm_refs(args, self.gen_ref_list)

        elif mode == "voice":
            lyrics = self.voice_lyrics.toPlainText().strip()
            styling = self.voice_styling.toPlainText().strip()
            if not lyrics or not styling:
                return None
            args.extend(["lyrics", lyrics, "styling", styling])
            args.append(str(self.voice_duration.value()))
            args.append("voice")
            if hasattr(self, 'voice_ref_list'):
                self._add_ttm_refs(args, self.voice_ref_list)

        elif mode == "voice clone (vc)":
            lyrics = self.vc_lyrics.toPlainText().strip()
            styling = self.vc_styling.toPlainText().strip()
            clone = self.vc_clone_audio.get_path() if hasattr(self, 'vc_clone_audio') else ""
            if not lyrics or not styling or not clone:
                return None
            args.append("vc")
            args.extend(["lyrics", lyrics, "styling", styling])
            args.append(str(self.vc_duration.value()))
            clone_val = clone
            if hasattr(self, 'vc_clone_extra') and self.vc_clone_extra.get_paths():
                extra = self.vc_clone_extra.get_paths()
                clone_val = "(" + clone + ")" + "".join(f"({ep})" for ep in extra)
            if hasattr(self, 'vc_clone_first_cb') and self.vc_clone_first_cb.isChecked():
                args.extend(["clone", "first", clone_val])
            else:
                args.extend(["clone", clone_val])
            if hasattr(self, 'vc_ref_list'):
                self._add_ttm_refs(args, self.vc_ref_list)

        elif mode == "remix":
            source = self.remix_source.text().strip()
            styling = self.remix_styling.toPlainText().strip()
            if not source or not styling:
                return None
            args.extend(["remix", source, "styling", styling, "bias", str(self.remix_bias.value())])
            lyrics = self.remix_lyrics.toPlainText().strip() if hasattr(self, 'remix_lyrics') else ""
            if lyrics:
                args.extend(["lyrics", lyrics])
            if hasattr(self, 'remix_ref_list'):
                self._add_ttm_refs(args, self.remix_ref_list)

        elif mode == "repaint":
            source = self.repaint_source.text().strip()
            styling = self.repaint_styling.toPlainText().strip()
            time_range = self.repaint_time.text().strip()
            if not source or not styling or not time_range:
                return None
            prefix = self.repaint_source_prefix.currentText() if hasattr(self, 'repaint_source_prefix') else "None"
            if prefix != "None":
                args.extend(["repaint", prefix, source])
            else:
                args.extend(["repaint", source])
            args.extend(["styling", styling, f"time:{time_range}", "bias", str(self.repaint_bias.value())])
            lyrics = self.repaint_lyrics.toPlainText().strip() if hasattr(self, 'repaint_lyrics') else ""
            if lyrics:
                args.extend(["lyrics", lyrics])
            multipass = self.repaint_multipass.text().strip() if hasattr(self, 'repaint_multipass') else ""
            if multipass:
                for spec in multipass.split():
                    args.append(spec)
            if hasattr(self, 'repaint_ref_list'):
                self._add_ttm_refs(args, self.repaint_ref_list)

        elif mode == "complete":
            source = self.complete_source.text().strip()
            selector_stems = self.complete_stems_selector.get_stems_string()
            custom_stems = self.complete_add.text().strip()
            combined = " ".join(filter(None, [selector_stems, custom_stems])).strip()
            if not source or not combined:
                return None
            args.append("complete")
            if self.complete_voice_cb.isChecked():
                args.append("voice")
            if self.complete_music_cb.isChecked():
                args.append("music")
            if hasattr(self, 'complete_noblend_cb') and self.complete_noblend_cb.isChecked():
                args.append("noblend")
            if hasattr(self, 'complete_usrc_cb') and self.complete_usrc_cb.isChecked():
                args.append("usrc")
            if self.complete_video_cb.isChecked():
                args.append("video")
            args.append(source)
            args.extend(["add", combined])
            sfx = self.complete_sfx_edit.text().strip() if hasattr(self, 'complete_sfx_edit') else ""
            if sfx:
                for spec in sfx.split():
                    if spec.startswith("sfx:"):
                        args.append(spec)
            if hasattr(self, 'complete_ref_list'):
                self._add_ttm_refs(args, self.complete_ref_list)

        elif mode == "lego":
            source = self.lego_source.text().strip()
            selector_stems = self.lego_stems_selector.get_stems_string()
            custom_stems = self.lego_make.text().strip()
            combined = " ".join(filter(None, [selector_stems, custom_stems])).strip()
            if not source or not combined:
                return None
            args.append("lego")
            if self.lego_mix_cb.isChecked():
                args.append("mix")
            if self.lego_blend_cb.isChecked():
                args.append("blend")
            if self.lego_voice_cb.isChecked():
                args.append("voice")
            if self.lego_music_cb.isChecked():
                args.append("music")
            args.append(source)
            args.extend(["make", combined])
            for stem, path in self.lego_ref_list.get_items():
                if stem.strip():
                    args.extend(["reference", f"{stem.strip()}:{path.strip()}"])
                else:
                    args.extend(["reference", path.strip()])

        elif mode == "extract":
            source = self.extract_source.text().strip()
            stems = self.extract_stems_selector.get_stems_string()
            if not source or not stems:
                return None
            args.append("extract")
            if self.extract_only_cb.isChecked():
                args.append("only")
            if self.extract_mix_cb.isChecked():
                args.append("mix")
            args.append(source)
            args.extend(["stems", stems])

        elif mode == "bgm":
            source = self.bgm_source.text().strip()
            music_desc = self.bgm_music.toPlainText().strip()
            if not source or not music_desc:
                return None
            args.extend(["bgm", source, "music", music_desc])
            args.extend(["level", str(self.bgm_level.value())])
            if hasattr(self, 'bgm_video_cb') and self.bgm_video_cb.isChecked():
                args.append("video")
            ref = self.bgm_reference.text().strip() if hasattr(self, 'bgm_reference') else ""
            if ref:
                args.extend(["reference", ref])
            sfx = self.bgm_sfx_edit.text().strip() if hasattr(self, 'bgm_sfx_edit') else ""
            if sfx:
                for spec in sfx.split():
                    if spec.startswith("sfx:"):
                        args.append(spec)

        if self.result_edit.text().strip():
            args.extend(["result", self.result_edit.text().strip()])
        return args

    def on_run(self):
        args = self.build_args()
        if args:
            self.run_signal.emit(args)


class STTTab(QWidget):
    run_signal = pyqtSignal(list)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(8)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setStyleSheet("QScrollArea { background: transparent; }")
        scroll_widget = QWidget()
        scroll_widget.setStyleSheet("background: transparent;")
        self.inner = QVBoxLayout(scroll_widget)
        self.inner.setSpacing(8)

        self.stt_sub_mode = QComboBox()
        self.stt_sub_mode.setStyleSheet(get_combo_box_style())
        self.stt_sub_mode.addItems(["Transcribe", "Subtitle"])
        sub_row = QHBoxLayout()
        sub_label = QLabel("Task Type")
        sub_label.setStyleSheet(f"color: {THEME['text']}; font-size: 13px; min-width: 90px;")
        sub_row.addWidget(sub_label)
        sub_row.addWidget(self.stt_sub_mode, stretch=1)
        sub_row.addStretch()
        self.inner.addLayout(sub_row)

        self.stt_container = QWidget()
        self.stt_container.setStyleSheet("background: transparent;")
        self.stt_container_layout = QVBoxLayout(self.stt_container)
        self.stt_container_layout.setContentsMargins(0, 0, 0, 0)
        self.stt_container_layout.setSpacing(8)
        self.inner.addWidget(self.stt_container)

        self.stt_sub_mode.currentTextChanged.connect(self.on_submode_changed)

        self.result_edit = HelperWidgets.make_save_picker(self.inner, "Result Path", "Optional: copy output to this path")

        self.run_btn = QPushButton("Run Transcription")
        self.run_btn.setStyleSheet(get_main_button_style())
        self.run_btn.setCursor(Qt.PointingHandCursor)
        self.run_btn.clicked.connect(self.on_run)
        self.inner.addWidget(self.run_btn)
        self.inner.addStretch()
        scroll.setWidget(scroll_widget)
        layout.addWidget(scroll)
        self.on_submode_changed("Transcribe")

    def clear_stt_container(self):
        while self.stt_container_layout.count():
            item = self.stt_container_layout.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()
            elif item.layout():
                while item.layout().count():
                    sub = item.layout().takeAt(0)
                    sw = sub.widget()
                    if sw:
                        sw.deleteLater()

    def on_submode_changed(self, mode):
        self.clear_stt_container()
        if mode == "Transcribe":
            self.build_transcribe_ui()
        elif mode == "Subtitle":
            self.build_subtitle_ui()

    def build_transcribe_ui(self):
        HelperWidgets.make_label(self.stt_container_layout, "Input Files (audio, video, image, or URLs)")
        self.file_list = FileListWidget(self.stt_container_layout, file_filter="Audio (*.wav *.mp3 *.flac *.ogg);;Video (*.mp4 *.avi *.mov *.mkv);;Images (*.png *.jpg *.jpeg *.bmp *.gif);;All Files (*)")
        self.stt_container_layout.addWidget(self.file_list)
        self.timestamp_cb = HelperWidgets.make_checkbox(self.stt_container_layout, "Timestamp (keep word-level timestamps)")
        self.dialogue_cb = HelperWidgets.make_checkbox(self.stt_container_layout, "Dialogue (speaker diarization, requires HF_TOKEN)")
        self.se_cb = HelperWidgets.make_checkbox(self.stt_container_layout, "Audio Enhancement (denoise/dereverb before transcription)")
        self.overdose_cb = HelperWidgets.make_checkbox(self.stt_container_layout, "Enhanced Analysis (VibeVoice ASR, requires 24GB+ VRAM or 48GB+ RAM)")
        HelperWidgets.make_separator(self.stt_container_layout)
        HelperWidgets.make_label(self.stt_container_layout, "Translation (optional)")
        self.translate_cb = HelperWidgets.make_checkbox(self.stt_container_layout, "Translate")
        self.translate_source_edit = HelperWidgets.make_line_edit(self.stt_container_layout, "Source Lang", "Source language code or auto (e.g. ja, auto)")
        self.translate_target_edit = HelperWidgets.make_line_edit(self.stt_container_layout, "Target Lang", "Target language code (e.g. en, ar)")

    def build_subtitle_ui(self):
        self.sub_source_audio = AudioReferenceWidget("Source Video/Audio", file_filter="Video Files (*.mp4 *.avi *.mov *.mkv);;Audio Files (*.wav *.mp3 *.flac *.ogg);;All Files (*)")
        self.stt_container_layout.addWidget(self.sub_source_audio)
        self.sub_format_combo = HelperWidgets.make_combo_row(self.stt_container_layout, "Format", ["srt", "vtt"], 0)
        self.sub_se_cb = HelperWidgets.make_checkbox(self.stt_container_layout, "Audio Enhancement (denoise before subtitle)")
        HelperWidgets.make_separator(self.stt_container_layout)
        HelperWidgets.make_label(self.stt_container_layout, "Translation (optional)")
        self.sub_translate_cb = HelperWidgets.make_checkbox(self.stt_container_layout, "Translate")
        self.sub_translate_spec = HelperWidgets.make_line_edit(self.stt_container_layout, "Lang Spec", "e.g. auto-ar or ja-en")

    def build_args(self):
        mode = self.stt_sub_mode.currentText()
        args = ["stt"]

        if mode == "Transcribe":
            paths = self.file_list.get_paths() if hasattr(self, 'file_list') else []
            if not paths:
                return None
            args.extend(paths)
            if hasattr(self, 'timestamp_cb') and self.timestamp_cb.isChecked():
                args.append("timestamp")
            if hasattr(self, 'dialogue_cb') and self.dialogue_cb.isChecked():
                args.append("dialogue")
            if hasattr(self, 'se_cb') and self.se_cb.isChecked():
                args.append("se")
            if hasattr(self, 'overdose_cb') and self.overdose_cb.isChecked():
                args.append("overdose")
            if hasattr(self, 'translate_cb') and self.translate_cb.isChecked():
                args.append("translate")
                source = self.translate_source_edit.text().strip() if hasattr(self, 'translate_source_edit') else ""
                target = self.translate_target_edit.text().strip() if hasattr(self, 'translate_target_edit') else ""
                if source or target:
                    src = source or "auto"
                    tgt = target or "en"
                    args.append(f"({src}-{tgt})")

        elif mode == "Subtitle":
            source_path = self.sub_source_audio.get_path() if hasattr(self, 'sub_source_audio') else ""
            if not source_path:
                return None
            args.append("overdose")
            args.append("subtitle")
            if hasattr(self, 'sub_translate_cb') and self.sub_translate_cb.isChecked():
                args.append("translate")
                spec = self.sub_translate_spec.text().strip() if hasattr(self, 'sub_translate_spec') else ""
                if spec:
                    args.append(f"({spec})")
            if hasattr(self, 'sub_se_cb') and self.sub_se_cb.isChecked():
                args.append("se")
            args.append(source_path)

        if self.result_edit.text().strip():
            args.extend(["result", self.result_edit.text().strip()])
        return args

    def on_run(self):
        args = self.build_args()
        if args:
            self.run_signal.emit(args)


class SETab(QWidget):
    run_signal = pyqtSignal(list)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(8)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setStyleSheet("QScrollArea { background: transparent; }")
        scroll_widget = QWidget()
        scroll_widget.setStyleSheet("background: transparent;")
        inner = QVBoxLayout(scroll_widget)
        inner.setSpacing(8)

        HelperWidgets.make_label(inner, "Input Files (audio, video, or URLs)")
        self.file_list = FileListWidget(inner, file_filter="Audio (*.wav *.mp3 *.flac *.ogg);;Video (*.mp4 *.avi *.mov *.mkv);;All Files (*)")
        inner.addWidget(self.file_list)

        HelperWidgets.make_separator(inner)
        HelperWidgets.make_label(inner, "Enhancement Mode")

        self.se_mode = QComboBox()
        self.se_mode.setStyleSheet(get_combo_box_style())
        self.se_mode.addItems([
            "Basic Enhancement",
            "Voice (extract/enhance voice only)",
            "SR (super-resolution)",
            "SR + Voice",
            "SR + Music",
            "SR + Voice + Music",
        ])
        mode_row = QHBoxLayout()
        mode_label = QLabel("Mode")
        mode_label.setStyleSheet(f"color: {THEME['text']}; font-size: 13px; min-width: 90px;")
        mode_row.addWidget(mode_label)
        mode_row.addWidget(self.se_mode, stretch=1)
        mode_row.addStretch()
        inner.addLayout(mode_row)

        self.blend_cb = HelperWidgets.make_checkbox(inner, "Blend (mix enhanced with original)")

        self.result_edit = HelperWidgets.make_save_picker(inner, "Result Path", "Optional: copy output to this path")

        self.run_btn = QPushButton("Run Audio Enhancement")
        self.run_btn.setStyleSheet(get_main_button_style())
        self.run_btn.setCursor(Qt.PointingHandCursor)
        self.run_btn.clicked.connect(self.on_run)
        inner.addWidget(self.run_btn)
        inner.addStretch()
        scroll.setWidget(scroll_widget)
        layout.addWidget(scroll)

    def build_args(self):
        paths = self.file_list.get_paths()
        if not paths:
            return None
        args = ["se"]
        mode = self.se_mode.currentText()
        if mode.startswith("Voice"):
            args.append("voice")
        elif mode.startswith("SR + Voice + Music"):
            args.append("sr")
            args.append("voice")
            args.append("music")
        elif mode.startswith("SR + Voice"):
            args.append("sr")
            args.append("voice")
        elif mode.startswith("SR + Music"):
            args.append("sr")
            args.append("music")
        elif mode.startswith("SR"):
            args.append("sr")
        if self.blend_cb.isChecked():
            args.append("blend")
        args.extend(paths)
        if self.result_edit.text().strip():
            args.extend(["result", self.result_edit.text().strip()])
        return args

    def on_run(self):
        args = self.build_args()
        if args:
            self.run_signal.emit(args)


class SFXTab(QWidget):
    run_signal = pyqtSignal(list)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(8)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setStyleSheet("QScrollArea { background: transparent; }")
        scroll_widget = QWidget()
        scroll_widget.setStyleSheet("background: transparent;")
        inner = QVBoxLayout(scroll_widget)
        inner.setSpacing(8)

        self.sound_edit = HelperWidgets.make_line_edit(inner, "Sound Prompt", "e.g. thunder cracking, rain on a tin roof")
        self.duration_spin = HelperWidgets.make_spinbox(inner, "Duration (s)", 1, 30, 5)
        self.steps_spin = HelperWidgets.make_spinbox(inner, "Steps", 1, 100, 30)
        self.guide_spin = HelperWidgets.make_double_spinbox(inner, "Guidance", 1.0, 10.0, 4.5, 0.5)
        self.result_edit = HelperWidgets.make_save_picker(inner, "Result Path", "Optional: copy output to this path")

        self.run_btn = QPushButton("Run Sound Effects")
        self.run_btn.setStyleSheet(get_main_button_style())
        self.run_btn.setCursor(Qt.PointingHandCursor)
        self.run_btn.clicked.connect(self.on_run)
        inner.addWidget(self.run_btn)
        inner.addStretch()
        scroll.setWidget(scroll_widget)
        layout.addWidget(scroll)

    def build_args(self):
        sound = self.sound_edit.text().strip()
        if not sound:
            return None
        args = ["sfx", "sound", sound, "duration", str(self.duration_spin.value())]
        args.extend(["steps", str(self.steps_spin.value())])
        args.extend(["guide", str(self.guide_spin.value())])
        if self.result_edit.text().strip():
            args.extend(["result", self.result_edit.text().strip()])
        return args

    def on_run(self):
        args = self.build_args()
        if args:
            self.run_signal.emit(args)


class SVSTab(QWidget):
    run_signal = pyqtSignal(list)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(8)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setStyleSheet("QScrollArea { background: transparent; }")
        scroll_widget = QWidget()
        scroll_widget.setStyleSheet("background: transparent;")
        inner = QVBoxLayout(scroll_widget)
        inner.setSpacing(8)

        self.input_audio = AudioReferenceWidget("Input File", file_filter="Audio Files (*.wav *.mp3 *.flac *.ogg);;Video Files (*.mp4 *.avi *.mov *.mkv);;All Files (*)")
        inner.addWidget(self.input_audio)
        self.voice_cb = HelperWidgets.make_checkbox(inner, "Extract vocals (remove instruments)")
        self.music_cb = HelperWidgets.make_checkbox(inner, "Extract instruments (remove vocals)")
        self.both_cb = HelperWidgets.make_checkbox(inner, "Extract both vocals and instruments")
        self.voice_cb.toggled.connect(lambda checked: (self.music_cb.setChecked(False), self.both_cb.setChecked(False)) if checked else None)
        self.music_cb.toggled.connect(lambda checked: (self.voice_cb.setChecked(False), self.both_cb.setChecked(False)) if checked else None)
        self.both_cb.toggled.connect(lambda checked: (self.voice_cb.setChecked(False), self.music_cb.setChecked(False)) if checked else None)
        self.result_edit = HelperWidgets.make_save_picker(inner, "Result Path", "Optional: copy output to this path")

        self.run_btn = QPushButton("Run Audio Isolation")
        self.run_btn.setStyleSheet(get_main_button_style())
        self.run_btn.setCursor(Qt.PointingHandCursor)
        self.run_btn.clicked.connect(self.on_run)
        inner.addWidget(self.run_btn)
        inner.addStretch()
        scroll.setWidget(scroll_widget)
        layout.addWidget(scroll)

    def build_args(self):
        path = self.input_audio.get_path()
        if not path:
            return None
        if not self.voice_cb.isChecked() and not self.music_cb.isChecked() and not self.both_cb.isChecked():
            return None
        args = ["svs"]
        if self.voice_cb.isChecked():
            args.append("voice")
        if self.music_cb.isChecked():
            args.append("music")
        if self.both_cb.isChecked():
            args.append("both")
        args.append(path)
        if self.result_edit.text().strip():
            args.extend(["result", self.result_edit.text().strip()])
        return args

    def on_run(self):
        args = self.build_args()
        if args:
            self.run_signal.emit(args)


class SSTab(QWidget):
    run_signal = pyqtSignal(list)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(8)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setStyleSheet("QScrollArea { background: transparent; }")
        scroll_widget = QWidget()
        scroll_widget.setStyleSheet("background: transparent;")
        inner = QVBoxLayout(scroll_widget)
        inner.setSpacing(8)

        self.source_audio = AudioReferenceWidget("Source", file_filter="Audio Files (*.wav *.mp3 *.flac *.ogg);;Video Files (*.mp4 *.avi *.mov *.mkv);;All Files (*)")
        inner.addWidget(self.source_audio)
        self.target_audio = AudioReferenceWidget("Voice Reference", file_filter="Audio Files (*.wav *.mp3 *.flac *.ogg);;All Files (*)")
        inner.addWidget(self.target_audio)
        self.se_cb = HelperWidgets.make_checkbox(inner, "Audio Enhancement (before separation)")
        self.overdose_cb = HelperWidgets.make_checkbox(inner, "Enhanced Analysis (VibeVoice ASR)")
        self.blend_cb = HelperWidgets.make_checkbox(inner, "Blend (mix each speaker with non-vocals)")
        self.video_cb = HelperWidgets.make_checkbox(inner, "Video (mux audio with original video)")
        self.result_edit = HelperWidgets.make_save_picker(inner, "Result Path", "Optional: copy output to this path")

        self.run_btn = QPushButton("Run Speakers Separation")
        self.run_btn.setStyleSheet(get_main_button_style())
        self.run_btn.setCursor(Qt.PointingHandCursor)
        self.run_btn.clicked.connect(self.on_run)
        inner.addWidget(self.run_btn)
        inner.addStretch()
        scroll.setWidget(scroll_widget)
        layout.addWidget(scroll)

    def build_args(self):
        source = self.source_audio.get_path()
        if not source:
            return None
        args = ["ss"]
        target = self.target_audio.get_path()
        if target:
            args.extend(["target", target])
        if self.se_cb.isChecked():
            args.append("se")
        if self.overdose_cb.isChecked():
            args.append("overdose")
        if self.blend_cb.isChecked():
            args.append("blend")
        if self.video_cb.isChecked():
            args.append("video")
        args.append(source)
        if self.result_edit.text().strip():
            args.extend(["result", self.result_edit.text().strip()])
        return args

    def on_run(self):
        args = self.build_args()
        if args:
            self.run_signal.emit(args)


class TrainTab(QWidget):
    run_signal = pyqtSignal(list)
    voices_changed = pyqtSignal()
    use_voice_signal = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.pending_voice_name = ""
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(8)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setStyleSheet("QScrollArea { background: transparent; }")
        scroll_widget = QWidget()
        scroll_widget.setStyleSheet("background: transparent;")
        inner = QVBoxLayout(scroll_widget)
        inner.setSpacing(8)

        HelperWidgets.make_label(inner, "CREATE A REUSABLE VOICE CLONE")
        self.voice_name_edit = HelperWidgets.make_line_edit(inner, "Voice Name", "e.g. rym, despina, alice")
        self.voice_name_edit.setToolTip(
            "This is the name you will pick later in the Speech tab. "
            "It is saved on this PC and stays after a restart."
        )
        HelperWidgets.make_label(inner, "Add one or more clean recordings of this voice (WAV, MP3, FLAC or OGG).")
        self.ref_list = FileListWidget(inner, file_filter="Audio (*.wav *.mp3 *.flac *.ogg);;All Files (*)")
        inner.addWidget(self.ref_list)
        self.test_cb = HelperWidgets.make_checkbox(inner, "Test after training")
        self.test_script_edit = HelperWidgets.make_line_edit(inner, "Test Script", "Custom test script text (optional, uses default if empty)")
        self.first_cb = HelperWidgets.make_checkbox(inner, "Use First as Speaker Template")
        self.extreme_cb = HelperWidgets.make_checkbox(inner, "Enhanced Synthesis (train for .ttse file, Fish Speech S2Pro)")

        self.save_info = QLabel(
            "Your voice is saved as a file in the VODER voices folder and appears "
            "automatically in Speech, Voice Change and Voice Library - even after you "
            "restart your PC. No links or paths to remember.\n\n"
            "Arabic recordings automatically become Algerian Darija voices (.ttsdz), "
            "which speak Arabic text with the KasbahTTS engine.\n\n"
            "Tip: if you like a voice you just generated, press 'Save as Voice' under "
            "the player instead of adding the file here."
        )
        self.save_info.setWordWrap(True)
        self.save_info.setStyleSheet(
            f"color: {THEME['text_secondary']}; font-size: 12px; padding: 4px 2px;"
        )
        inner.addWidget(self.save_info)

        self.run_btn = QPushButton("Train & Save Voice Clone")
        self.run_btn.setStyleSheet(get_main_button_style())
        self.run_btn.setCursor(Qt.PointingHandCursor)
        self.run_btn.clicked.connect(self.on_run)
        inner.addWidget(self.run_btn)

        self.train_status = QLabel("Ready — name your voice, add recordings, then train.")
        self.train_status.setWordWrap(True)
        self.train_status.setStyleSheet(
            f"color: {THEME['text_secondary']}; font-size: 12px; padding: 2px;"
        )
        inner.addWidget(self.train_status)

        HelperWidgets.make_separator(inner)
        HelperWidgets.make_label(inner, "YOUR SAVED VOICES")
        self.library_panel = VoiceLibraryPanel(show_train_button=False)
        self.library_panel.use_voice.connect(self.use_voice_signal.emit)
        self.library_panel.voices_changed.connect(self._on_voices_changed)
        inner.addWidget(self.library_panel)
        inner.addStretch()
        scroll.setWidget(scroll_widget)
        layout.addWidget(scroll)

    def refresh_voice_library(self):
        if hasattr(self, "library_panel"):
            self.library_panel.refresh()

    def set_training_status(self, message, success=None):
        if not hasattr(self, "train_status"):
            return
        if success is True:
            color = THEME.get("success", THEME["accent"])
        elif success is False:
            color = THEME.get("error", "#e05b5b")
        else:
            color = THEME["text_secondary"]
        self.train_status.setText(message)
        self.train_status.setStyleSheet(f"color: {color}; font-size: 12px; padding: 2px;")

    def _on_voices_changed(self):
        self.refresh_voice_library()
        self.voices_changed.emit()

    def build_args(self):
        voice_name = vlib.sanitize_voice_name(self.voice_name_edit.text())
        paths = self.ref_list.get_paths()
        if not voice_name or not paths:
            return None
        if voice_name != self.voice_name_edit.text().strip():
            # Keep the field and the saved file name in sync so the user can
            # find the voice by the name shown after training.
            self.voice_name_edit.setText(voice_name)
        self.pending_voice_name = voice_name
        args = ["train"]
        if self.extreme_cb.isChecked():
            args.append("extreme")
        args.append(f"voice:{voice_name}")
        if self.first_cb.isChecked():
            args.append("first")
        args.extend(paths)
        if self.test_cb.isChecked():
            test_script = self.test_script_edit.text().strip()
            args.append("test")
            if test_script:
                args.append(test_script)
        return args

    def on_run(self):
        args = self.build_args()
        if args:
            self.run_signal.emit(args)


class VoiceLibraryTab(QWidget):
    use_voice_signal = pyqtSignal(str)
    voices_changed = pyqtSignal()
    train_requested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setSpacing(8)
        HelperWidgets.make_label(layout, "SAVED VOICES ON THIS PC")
        intro = QLabel(
            "Every voice you train is kept here. Pick one by name in Speech, Voice "
            "Change or Modify Speech - no links and no file paths needed. Voices stay "
            "available after you restart the PC."
        )
        intro.setWordWrap(True)
        intro.setStyleSheet(
            f"color: {THEME['text_secondary']}; font-size: 12px; padding: 2px;"
        )
        layout.addWidget(intro)
        self.panel = VoiceLibraryPanel(show_train_button=True)
        self.panel.use_voice.connect(self.use_voice_signal.emit)
        self.panel.voices_changed.connect(self._on_voices_changed)
        self.panel.train_requested.connect(self.train_requested.emit)
        layout.addWidget(self.panel)

    def refresh_voice_library(self):
        self.panel.refresh()

    def _on_voices_changed(self):
        self.refresh_voice_library()
        self.voices_changed.emit()


MODE_DISPLAY_NAMES = [
    "Speech",
    "Voice Conversion",
    "Music",
    "Transcription",
    "Audio Enhancement",
    "Sound Effects",
    "Audio Isolation",
    "Speakers Separation",
    "Make Voice",
    "Voice Library",
]

MODE_INTERNAL_KEYS = ["tts", "sts", "ttm", "stt", "se", "sfx", "svs", "ss", "train", "voices"]


class VoderGUI(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("VODER")
        self.setMinimumSize(960, 700)
        self.setStyleSheet(get_window_style())
        self.current_thread = None
        self.audio_player = None
        self.last_output_path = None
        self.last_command = ""
        self.terminal_visible = False
        self.running = False
        self.player_thread = None
        self.setup_ui()

    def setup_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        top_bar = QFrame()
        top_bar.setFixedHeight(48)
        top_bar.setStyleSheet(f"background-color: {THEME['background']}; border-bottom: 1px solid {THEME['border']};")
        top_layout = QHBoxLayout(top_bar)
        top_layout.setContentsMargins(16, 0, 16, 0)

        title = QLabel("VODER")
        title.setStyleSheet(f"color: {THEME['text']}; font-size: 18px; font-weight: bold; letter-spacing: 2px;")
        top_layout.addWidget(title)
        top_layout.addStretch()

        self.terminal_btn = QPushButton(">_<")
        self.terminal_btn.setFixedSize(36, 36)
        self.terminal_btn.setCursor(Qt.PointingHandCursor)
        self.terminal_btn.setStyleSheet("""
            QPushButton {
                background-color: #1a1a1a;
                color: #FFFFFF;
                border: 1px solid #3a3a3a;
                border-radius: 6px;
                font-family: 'Consolas', monospace;
                font-size: 12px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #2a2a2a;
                border: 1px solid #FFFFFF;
            }
            QPushButton:pressed {
                background-color: #FFFFFF;
                color: #000000;
            }
        """)
        self.terminal_btn.clicked.connect(self.toggle_terminal)
        top_layout.addWidget(self.terminal_btn)

        self.status_label = QLabel("")
        self.status_label.setStyleSheet(f"color: {THEME['text_secondary']}; font-size: 11px; margin-left: 12px;")
        top_layout.addWidget(self.status_label)

        main_layout.addWidget(top_bar)

        body = QHBoxLayout()
        body.setSpacing(0)
        body.setContentsMargins(0, 0, 0, 0)

        sidebar = QFrame()
        sidebar.setFixedWidth(180)
        sidebar.setStyleSheet(f"background-color: {THEME['sidebar_background']}; border-right: 1px solid {THEME['border']};")
        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setContentsMargins(0, 0, 0, 0)
        sidebar_layout.setSpacing(0)

        self.mode_list = QListWidget()
        self.mode_list.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.mode_list.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.mode_list.setVerticalScrollMode(QListWidget.ScrollPerPixel)
        self.mode_list.setToolTip("Scroll to see all VODER tools, including Make Voice.")
        self.mode_list.setStyleSheet(f"""
            QListWidget {{
                background-color: {THEME['sidebar_background']};
                border: none;
                outline: none;
                padding: 8px 0;
            }}
            QListWidget::item {{
                color: {THEME['text']};
                padding: 14px 16px;
                font-size: 13px;
                border: none;
                border-radius: 0;
            }}
            QListWidget::item:hover {{
                background-color: {THEME['sidebar_item_hover']};
            }}
            QListWidget::item:selected {{
                background-color: {THEME['sidebar_item_active']};
                color: {contrast_color(THEME['sidebar_item_active'])};
            }}
        """)
        self.mode_list.addItems(MODE_DISPLAY_NAMES)
        for i in range(self.mode_list.count()):
            item = self.mode_list.item(i)
            item.setSizeHint(QSize(0, 44))
        self.mode_list.setCurrentRow(0)
        self.mode_list.currentRowChanged.connect(self.on_mode_changed)
        sidebar_layout.addWidget(self.mode_list)

        sidebar_layout.addStretch()

        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setStyleSheet(f"color: {THEME['border']};")
        sidebar_layout.addWidget(sep)

        self.ready_label = QLabel("Ready")
        self.ready_label.setStyleSheet(f"color: {THEME['text_secondary']}; font-size: 11px; padding: 8px 16px;")
        sidebar_layout.addWidget(self.ready_label)

        body.addWidget(sidebar)

        self.content_stack = QStackedWidget()

        self.tts_tab = TTSTab()
        self.sts_tab = STSTab()
        self.ttm_tab = TTMTab()
        self.stt_tab = STTTab()
        self.se_tab = SETab()
        self.sfx_tab = SFXTab()
        self.svs_tab = SVSTab()
        self.ss_tab = SSTab()
        self.train_tab = TrainTab()
        self.voice_library_tab = VoiceLibraryTab()

        self.content_stack.addWidget(self.tts_tab)
        self.content_stack.addWidget(self.sts_tab)
        self.content_stack.addWidget(self.ttm_tab)
        self.content_stack.addWidget(self.stt_tab)
        self.content_stack.addWidget(self.se_tab)
        self.content_stack.addWidget(self.sfx_tab)
        self.content_stack.addWidget(self.svs_tab)
        self.content_stack.addWidget(self.ss_tab)
        self.content_stack.addWidget(self.train_tab)
        self.content_stack.addWidget(self.voice_library_tab)

        content_wrapper = QWidget()
        content_layout = QVBoxLayout(content_wrapper)
        content_layout.setContentsMargins(8, 8, 8, 0)
        content_layout.setSpacing(0)
        content_layout.addWidget(self.content_stack, stretch=1)

        audio_frame = QFrame()
        audio_frame.setStyleSheet(f"background-color: {THEME['panel_background']}; border-top: 1px solid {THEME['border']};")
        audio_layout = QVBoxLayout(audio_frame)
        audio_layout.setContentsMargins(12, 8, 12, 8)
        audio_layout.setSpacing(4)

        self.waveform = AudioWaveformWidget()
        self.waveform.setFixedHeight(48)
        audio_layout.addWidget(self.waveform)

        audio_row = QHBoxLayout()
        audio_row.setSpacing(8)
        self.audio_path_edit = QLineEdit()
        self.audio_path_edit.setReadOnly(True)
        self.audio_path_edit.setPlaceholderText("Output audio")
        self.audio_path_edit.setStyleSheet(get_line_edit_style())
        audio_row.addWidget(self.audio_path_edit, stretch=1)

        self.play_btn = QPushButton("Play")
        self.play_btn.setStyleSheet(get_surface_button_style())
        self.play_btn.setCursor(Qt.PointingHandCursor)
        self.play_btn.setFixedWidth(60)
        self.play_btn.setEnabled(False)
        self.play_btn.clicked.connect(self.play_audio)
        audio_row.addWidget(self.play_btn)

        self.audio_stop_btn = QPushButton("Stop")
        self.audio_stop_btn.setStyleSheet(get_surface_button_style())
        self.audio_stop_btn.setCursor(Qt.PointingHandCursor)
        self.audio_stop_btn.setFixedWidth(60)
        self.audio_stop_btn.setEnabled(False)
        self.audio_stop_btn.clicked.connect(self.stop_audio)
        audio_row.addWidget(self.audio_stop_btn)

        self.open_output_btn = QPushButton("Open Folder")
        self.open_output_btn.setStyleSheet(get_surface_button_style())
        self.open_output_btn.setCursor(Qt.PointingHandCursor)
        self.open_output_btn.setFixedWidth(90)
        self.open_output_btn.setToolTip("Open the results folder in Explorer")
        self.open_output_btn.clicked.connect(self.open_output_folder)
        audio_row.addWidget(self.open_output_btn)

        self.save_voice_btn = QPushButton("Save as Voice")
        self.save_voice_btn.setStyleSheet(get_surface_button_style())
        self.save_voice_btn.setCursor(Qt.PointingHandCursor)
        self.save_voice_btn.setFixedWidth(110)
        self.save_voice_btn.setEnabled(False)
        self.save_voice_btn.setToolTip(
            "Like the voice in this result? Save it as a named voice you can "
            "pick again in Speech, forever."
        )
        self.save_voice_btn.clicked.connect(self.save_output_as_voice)
        audio_row.addWidget(self.save_voice_btn)

        audio_layout.addLayout(audio_row)
        content_layout.addWidget(audio_frame)

        body.addWidget(content_wrapper, stretch=1)
        main_layout.addLayout(body)

        self.terminal_panel = QFrame(self.content_stack)
        self.terminal_panel.setStyleSheet(f"""
            QFrame {{
                background-color: {THEME['panel_background']};
                border: 1px solid {THEME['border_light']};
                border-radius: 8px;
            }}
        """)
        terminal_layout = QVBoxLayout(self.terminal_panel)
        terminal_layout.setContentsMargins(12, 8, 12, 8)
        terminal_layout.setSpacing(6)

        term_header = QHBoxLayout()
        term_title = QLabel("Terminal")
        term_title.setStyleSheet(f"color: {THEME['text']}; font-size: 13px; font-weight: bold;")
        term_header.addWidget(term_title)
        term_header.addStretch()

        self.term_deps_btn = QPushButton("Deps")
        self.term_deps_btn.setStyleSheet(get_surface_button_style())
        self.term_deps_btn.setCursor(Qt.PointingHandCursor)
        self.term_deps_btn.setFixedWidth(60)
        self.term_deps_btn.setToolTip("Check and install any missing Python packages")
        self.term_deps_btn.clicked.connect(self.run_dependencies)
        term_header.addWidget(self.term_deps_btn)

        self.term_copy_btn = QPushButton("Copy")
        self.term_copy_btn.setStyleSheet(get_surface_button_style())
        self.term_copy_btn.setCursor(Qt.PointingHandCursor)
        self.term_copy_btn.setFixedWidth(60)
        self.term_copy_btn.clicked.connect(self.copy_output)
        term_header.addWidget(self.term_copy_btn)

        self.term_clear_btn = QPushButton("Clear")
        self.term_clear_btn.setStyleSheet(get_surface_button_style())
        self.term_clear_btn.setCursor(Qt.PointingHandCursor)
        self.term_clear_btn.setFixedWidth(60)
        self.term_clear_btn.clicked.connect(self.clear_console)
        term_header.addWidget(self.term_clear_btn)

        self.term_close_btn = QPushButton("\u00d7")
        self.term_close_btn.setFixedSize(24, 24)
        self.term_close_btn.setCursor(Qt.PointingHandCursor)
        self.term_close_btn.setStyleSheet("""
            QPushButton { background-color: #3a3a3a; color: white; border: none; border-radius: 12px; font-size: 14px; font-weight: bold; }
            QPushButton:hover { background-color: #f44336; }
        """)
        self.term_close_btn.clicked.connect(self.toggle_terminal)
        term_header.addWidget(self.term_close_btn)
        terminal_layout.addLayout(term_header)

        self.console = QTextEdit()
        self.console.setReadOnly(True)
        self.console.setStyleSheet(get_text_edit_style())
        self.console.setMinimumHeight(150)
        self.console.setMaximumHeight(300)
        terminal_layout.addWidget(self.console)

        self.progress_bar = QProgressBar()
        self.progress_bar.setStyleSheet(get_progress_bar_style())
        self.progress_bar.setRange(0, 0)
        self.progress_bar.setVisible(False)
        self.progress_bar.setFixedHeight(4)
        terminal_layout.addWidget(self.progress_bar)

        term_btn_row = QHBoxLayout()
        term_btn_row.setSpacing(6)

        self.copy_cmd_btn = QPushButton("Copy Command")
        self.copy_cmd_btn.setStyleSheet(get_surface_button_style())
        self.copy_cmd_btn.setCursor(Qt.PointingHandCursor)
        self.copy_cmd_btn.clicked.connect(self.copy_command)
        term_btn_row.addWidget(self.copy_cmd_btn)

        self.stop_btn = QPushButton("Stop Process")
        self.stop_btn.setStyleSheet(get_surface_button_style())
        self.stop_btn.setCursor(Qt.PointingHandCursor)
        self.stop_btn.setEnabled(False)
        self.stop_btn.clicked.connect(self.stop_process)
        term_btn_row.addWidget(self.stop_btn)

        term_btn_row.addStretch()
        terminal_layout.addLayout(term_btn_row)

        self.terminal_panel.hide()

        self.tts_tab.run_signal.connect(self.run_command)
        self.tts_tab.transcribe_signal.connect(self.run_transcribe)
        self.sts_tab.run_signal.connect(self.run_command)
        self.ttm_tab.run_signal.connect(self.run_command)
        self.stt_tab.run_signal.connect(self.run_command)
        self.se_tab.run_signal.connect(self.run_command)
        self.sfx_tab.run_signal.connect(self.run_command)
        self.svs_tab.run_signal.connect(self.run_command)
        self.ss_tab.run_signal.connect(self.run_command)
        self.train_tab.run_signal.connect(self.run_command)

        # Voice library wiring: training finishes -> list refreshes; "Use" and
        # "+ Train New" cross-navigate without hunting through tabs.
        self.tts_tab.train_voice_requested.connect(self.goto_train_tab)
        self.voice_library_tab.train_requested.connect(self.goto_train_tab)
        self.train_tab.voices_changed.connect(self.refresh_voice_library)
        self.voice_library_tab.voices_changed.connect(self.refresh_voice_library)
        self.train_tab.use_voice_signal.connect(self.use_saved_voice)
        self.voice_library_tab.use_voice_signal.connect(self.use_saved_voice)
        self.tts_tab.extreme_cb.stateChanged.connect(self.tts_tab._update_voice_mode_hints)

        self.run_shortcut = QShortcut(QKeySequence("Ctrl+Return"), self)
        self.run_shortcut.activated.connect(self.run_current_tab)

        self.ready_timer = QTimer()
        self.ready_timer.timeout.connect(self.update_readiness)
        self.ready_timer.start(500)

        self.refresh_voice_library()

    def refresh_voice_library(self):
        """Re-scan saved voices everywhere after training / rename / delete."""
        for widget in (self.tts_tab, self.train_tab, self.voice_library_tab):
            if hasattr(widget, "refresh_voice_library"):
                widget.refresh_voice_library()

    def goto_train_tab(self):
        index = MODE_DISPLAY_NAMES.index("Make Voice")
        self.mode_list.setCurrentRow(index)
        self.content_stack.setCurrentIndex(index)

    def use_saved_voice(self, name):
        """Voice Library -> Speech: switch mode and pick the saved voice."""
        index = MODE_DISPLAY_NAMES.index("Speech")
        self.mode_list.setCurrentRow(index)
        self.content_stack.setCurrentIndex(index)
        self.tts_tab.sub_mode.setCurrentText("Speech")
        self.tts_tab.adopt_saved_voice(name)
        if hasattr(self.tts_tab, "tts_status_label"):
            self.tts_tab.set_generation_status(f"Saved voice selected: {name}. Enter text and run.")

    def open_output_folder(self):
        folder = os.path.join(VODER_ROOT, "results")
        try:
            os.makedirs(folder, exist_ok=True)
            if self.last_output_path and os.path.exists(self.last_output_path):
                if os.name == "nt":
                    subprocess.Popen(["explorer", "/select,", os.path.normpath(self.last_output_path)])
                    return
            if os.name == "nt":
                os.startfile(folder)
            elif os.name == "posix":
                opener = "open" if os.uname().sysname == "Darwin" else "xdg-open"  # noqa
                subprocess.Popen([opener, folder])
        except Exception:
            pass

    def save_output_as_voice(self):
        """Turn the audio you just generated into a named, reusable voice.

        The clone is stored in the same voices folder as any other trained
        voice, so it stays available after a restart and can be picked by name
        in Speech, Voice Change and Voice Library.
        """
        path = self.last_output_path
        if not path or not os.path.exists(path):
            QMessageBox.information(
                self, "No audio yet",
                "Generate some speech first, then use this button to keep the voice."
            )
            return
        if self.running:
            QMessageBox.information(
                self, "Busy", "Wait for the current job to finish, then save the voice."
            )
            return

        seconds = audio_seconds(path)
        if seconds and seconds < 5:
            answer = QMessageBox.question(
                self, "Very short sample",
                f"This clip is only {seconds:.1f} seconds long, so the clone may sound "
                "unstable.\n\n10-30 seconds of one clean voice gives much better results. "
                "Try it anyway?",
                QMessageBox.Yes | QMessageBox.No, QMessageBox.No
            )
            if answer != QMessageBox.Yes:
                return
        elif seconds > 90:
            answer = QMessageBox.question(
                self, "Long sample",
                f"This clip is {seconds:.0f} seconds long. A clone only needs a short, "
                "clean piece of one speaker - extra music, other speakers or silence "
                "makes it worse.\n\nSave it anyway?",
                QMessageBox.Yes | QMessageBox.No, QMessageBox.No
            )
            if answer != QMessageBox.Yes:
                return

        if getattr(self, "last_command", "") in ("ttm", "sfx"):
            answer = QMessageBox.question(
                self, "This is music, not a clean voice",
                "This result is a song/effect, so the clone would also learn the "
                "instruments, the beat and every singer in the mix.\n\n"
                "For a real voice, separate the vocals first (Separate tab -> Voice), "
                "then save the singer's track.\n\nSave it anyway?",
                QMessageBox.Yes | QMessageBox.No, QMessageBox.No
            )
            if answer != QMessageBox.Yes:
                return

        name, ok = QInputDialog.getText(
            self, "Save as Voice",
            "Name for this voice (you will pick it by this name in Speech):"
        )
        if not ok:
            return
        name = vlib.sanitize_voice_name(name)
        if not name:
            QMessageBox.warning(
                self, "Invalid name",
                "Please type a name using letters or digits, for example 'emma'."
            )
            return
        if vlib.profiles_for_name(name):
            answer = QMessageBox.question(
                self, "Voice already exists",
                f"A voice named '{name}' already exists. Replace it with this audio?",
                QMessageBox.Yes | QMessageBox.No, QMessageBox.No
            )
            if answer != QMessageBox.Yes:
                return

        self.train_tab.pending_voice_name = name
        if not self.terminal_visible:
            self.toggle_terminal()
        self.console.append(
            f"\n[save] Creating voice '{name}' from {os.path.basename(path)} ..."
        )
        self.run_command(["train", f"voice:{name}", path])

    def toggle_terminal(self):
        self.terminal_visible = not self.terminal_visible
        if self.terminal_visible:
            self.terminal_panel.setGeometry(self.content_stack.rect())
            self.terminal_panel.raise_()
            self.terminal_panel.show()
        else:
            self.terminal_panel.hide()

    def on_mode_changed(self, row):
        self.content_stack.setCurrentIndex(row)

    def run_command(self, args):
        if self.running:
            return
        self.last_command = args[0] if args else ""
        if hasattr(self, "tts_tab") and self.content_stack.currentWidget() == self.tts_tab:
            self.tts_tab.set_generation_status("Starting VODER… live progress will appear here.")
        self.running = True
        self.stop_btn.setEnabled(True)
        self.progress_bar.setVisible(True)
        self.console.append(f"\n> python voder.py {' '.join(_q(a) for a in args)}\n")
        self.current_thread = SubprocessThread(args)
        self.current_thread.output_signal.connect(self.on_output)
        self.current_thread.finished_signal.connect(self.on_process_finished)
        self.current_thread.start()

    def run_transcribe(self, args):
        if self.running:
            return
        self.running = True
        self.stop_btn.setEnabled(True)
        self.progress_bar.setVisible(True)
        self.console.append(f"\n> python voder.py {' '.join(_q(a) for a in args)}\n")
        self.current_thread = SubprocessThread(args)
        self.current_thread.output_signal.connect(self.on_output)
        self.current_thread.finished_signal.connect(self.on_transcribe_finished)
        self.current_thread.start()

    def run_dependencies(self):
        """Check/install missing packages and show the full pip log."""
        if not self.terminal_visible:
            self.toggle_terminal()
        if self.running:
            self.console.append("[deps] Another job is running - try again when it finishes.")
            return
        self.console.clear()
        self.run_command(["deps"])

    def on_output(self, line):
        self.console.append(line)
        if hasattr(self, "tts_tab") and self.content_stack.currentWidget() == self.tts_tab:
            lower_line = line.lower()
            if any(word in lower_line for word in ("loading", "generating", "synthesizing", "separating", "progress")):
                self.tts_tab.set_generation_status(line.strip()[:180])
            elif "error" in lower_line or "traceback" in lower_line or "exception" in lower_line:
                self.tts_tab.set_generation_status("Generation error — see the log panel for details.", success=False)
            elif any(word in lower_line for word in ("success", "saved to", "output:")):
                self.tts_tab.set_generation_status(line.strip()[:180], success=True)
        detected = self.detect_output_path(line)
        if detected:
            self.last_output_path = detected
            self.audio_path_edit.setText(detected)
            self.play_btn.setEnabled(True)
            self.save_voice_btn.setEnabled(True)
            self.waveform.set_audio(detected)

    def on_process_finished(self, returncode, output):
        self.running = False
        self.stop_btn.setEnabled(False)
        self.progress_bar.setVisible(False)
        command_args = list(self.current_thread.command_args) if self.current_thread else []
        self.current_thread = None
        # A training run writes a new voice file: re-scan so it shows up
        # immediately in every voice picker.
        self.refresh_voice_library()
        if command_args and command_args[0] == "train":
            name = self.train_tab.pending_voice_name
            if returncode == 0:
                self.train_tab.set_training_status(
                    f"Saved '{name}'. It is now available in every voice list, "
                    "even after a restart.", success=True
                )
                if name:
                    self.tts_tab.adopt_saved_voice(name)
            else:
                self.train_tab.set_training_status(
                    f"Training failed (exit code {returncode}). Open the log panel to see why.",
                    success=False
                )
        if hasattr(self, "tts_tab") and self.content_stack.currentWidget() == self.tts_tab:
            if returncode == 0:
                self.tts_tab.set_generation_status("Completed. Check the output player below.", success=True)
            else:
                self.tts_tab.set_generation_status(
                    f"Failed (exit code {returncode}). Open the log panel to see the error.",
                    success=False
                )
        audio_path = self.detect_output_path(output)
        if audio_path:
            self.last_output_path = audio_path
            self.audio_path_edit.setText(audio_path)
            self.play_btn.setEnabled(True)
            self.save_voice_btn.setEnabled(True)
            self.waveform.set_audio(audio_path)

    def on_transcribe_finished(self, returncode, output):
        self.on_process_finished(returncode, output)
        if returncode == 0:
            text = self._extract_transcription(output)
            if text:
                self.tts_tab.handle_transcription_result(text)

    def _extract_transcription(self, output):
        lines = output.strip().split('\n')
        text_lines = []
        capture = False
        for line in lines:
            if 'Transcription' in line or 'transcription' in line or 'Result' in line:
                capture = True
                continue
            if capture:
                stripped = line.strip()
                if stripped and not stripped.startswith('[') and not stripped.startswith('===') and not stripped.startswith('---'):
                    text_lines.append(stripped)
        return '\n'.join(text_lines) if text_lines else output.strip()

    def detect_output_path(self, output):
        patterns = [
            r'(?:Saved|saved|Output|output|Result|result|Created|created|Written|written)\s*(?:to|at|:)?\s*["\']?([\w/\-\\\.]+\.(?:wav|mp3|flac|ogg))["\']?',
            r'["\']?([\w/\-\\\.]+\.(?:wav|mp3|flac|ogg))["\']?',
        ]
        for pattern in patterns:
            matches = re.findall(pattern, output)
            for match in reversed(matches):
                if os.path.exists(match):
                    return match
        for line in reversed(output.split('\n')):
            line = line.strip()
            for ext in ['.wav', '.mp3', '.flac', '.ogg']:
                if ext in line.lower():
                    for word in line.split():
                        word = word.strip('"\'.,;:')
                        if word.lower().endswith(ext) and os.path.exists(word):
                            return word
        return ""

    def play_audio(self):
        if self.last_output_path and os.path.exists(self.last_output_path):
            self.stop_audio()
            self.player_thread = AudioPlayerThread(self.last_output_path)
            self.player_thread.finished_signal.connect(self.on_play_finished)
            self.player_thread.start()
            self.play_btn.setEnabled(False)
            self.audio_stop_btn.setEnabled(True)

    def stop_audio(self):
        if self.player_thread:
            self.player_thread.stop()
            self.player_thread = None
        self.play_btn.setEnabled(bool(self.last_output_path and os.path.exists(self.last_output_path) if self.last_output_path else False))
        self.save_voice_btn.setEnabled(bool(self.last_output_path and os.path.exists(self.last_output_path) if self.last_output_path else False))
        self.audio_stop_btn.setEnabled(False)

    def on_play_finished(self):
        self.player_thread = None
        self.play_btn.setEnabled(bool(self.last_output_path and os.path.exists(self.last_output_path) if self.last_output_path else False))
        self.save_voice_btn.setEnabled(bool(self.last_output_path and os.path.exists(self.last_output_path) if self.last_output_path else False))
        self.audio_stop_btn.setEnabled(False)

    def stop_process(self):
        if self.current_thread:
            self.current_thread.stop()
            self.current_thread = None
        self.running = False
        self.stop_btn.setEnabled(False)
        self.progress_bar.setVisible(False)

    def clear_console(self):
        self.console.clear()

    def copy_command(self):
        tab = self.content_stack.currentWidget()
        args = None
        if hasattr(tab, 'build_args'):
            args = tab.build_args()
        if args:
            cmd = ' '.join(_q(a) for a in args)
            clipboard = QApplication.clipboard()
            clipboard.setText(f"python voder.py {cmd}")

    def copy_output(self):
        text = self.console.toPlainText()
        if text:
            clipboard = QApplication.clipboard()
            clipboard.setText(text)

    def run_current_tab(self):
        tab = self.content_stack.currentWidget()
        if hasattr(tab, 'on_run'):
            tab.on_run()

    def update_readiness(self):
        tab = self.content_stack.currentWidget()
        if hasattr(tab, 'build_args'):
            args = tab.build_args()
            if args is not None:
                self.ready_label.setText("Ready")
                self.ready_label.setStyleSheet(f"color: {THEME['accent']}; font-size: 11px; padding: 8px 16px; font-weight: bold;")
            else:
                self.ready_label.setText("Ready")
                self.ready_label.setStyleSheet(f"color: {THEME['text_secondary']}; font-size: 11px; padding: 8px 16px;")
        else:
            self.ready_label.setText("Ready")
            self.ready_label.setStyleSheet(f"color: {THEME['text_secondary']}; font-size: 11px; padding: 8px 16px;")


def launch():
    # Windows pipes default to the legacy ANSI code page; keep console output
    # from failing on the checkmarks used in progress messages.
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

    # Dependencies are normally checked by voder.py before this module is
    # imported; this also covers running the GUI module directly.
    try:
        from voders.bootstrap import ensure_dependencies
        ensure_dependencies()
        # Subprocesses started by the GUI do not need to check again.
        os.environ["VODER_SKIP_DEPS"] = "1"
    except Exception as exc:
        print(f"[deps] Warning: dependency check failed: {exc}", flush=True)

    try:
        from voders.media_tools import ensure_ffmpeg
        ensure_ffmpeg()
    except Exception as exc:
        print(f"[media] Warning: could not set up ffmpeg: {exc}", flush=True)

    app = QApplication(sys.argv)
    app.setStyle("Fusion")

    palette = QPalette()
    palette.setColor(QPalette.Window, QColor(THEME['background']))
    palette.setColor(QPalette.WindowText, QColor(THEME['text']))
    palette.setColor(QPalette.Base, QColor(THEME['surface']))
    palette.setColor(QPalette.AlternateBase, QColor(THEME['surface_hover']))
    palette.setColor(QPalette.ToolTipBase, QColor(THEME['surface']))
    palette.setColor(QPalette.ToolTipText, QColor(THEME['text']))
    palette.setColor(QPalette.Text, QColor(THEME['text']))
    palette.setColor(QPalette.Button, QColor(THEME['surface']))
    palette.setColor(QPalette.ButtonText, QColor(THEME['text']))
    palette.setColor(QPalette.BrightText, QColor(THEME['error']))
    palette.setColor(QPalette.Highlight, QColor(THEME['accent']))
    palette.setColor(QPalette.HighlightedText, QColor(contrast_color(THEME['accent'])))
    app.setPalette(palette)

    window = VoderGUI()
    window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    launch()
