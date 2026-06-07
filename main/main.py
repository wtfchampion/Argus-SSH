"""
Argus ssh (PyQt5)

Features:
- Full English UI (With Python App features)
- Integrated interactive terminal (type directly inside)
- Custom Toast Notifications with animations
- SFTP File Manager with New Folder functionality
- Clean settings dialog with color picker
- Donate support with QR Code generation
- Buy Host button (opens Telegram purchase channel)
- [NEW] Cross-Platform Documents folder support
- [NEW] Python App menu for background execution and process monitoring
"""

from __future__ import annotations

import json
import os
import posixpath
import stat
import sys
import re
import io
import webbrowser
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import List, Optional

import paramiko
from PyQt5.QtCore import QEvent, QObject, QPoint, QThread, Qt, QSize, pyqtSignal, QPropertyAnimation, QTimer
from PyQt5.QtGui import QFont, QTextCursor, QColor, QPixmap, QImage, QIcon
from PyQt5.QtWidgets import (
    QApplication,
    QCheckBox,
    QDialog,
    QFileDialog,
    QFormLayout,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QPlainTextEdit,
    QSpinBox,
    QSplitter,
    QStackedWidget,
    QStyle,
    QTableWidget,
    QTableWidgetItem,
    QToolBar,
    QVBoxLayout,
    QWidget,
    QHeaderView,
    QColorDialog,
    QGraphicsOpacityEffect,
    QInputDialog,
    QMenu,
    QToolButton
)

# --- Configuration Variables ---
APP_NAME = "Argus SSH"
APP_ORG = "WTFChampion Studio"
APP_VERSION = "1.4.0"

TETHER_WALLET_ADDRESS = "TYourTetherTRC20WalletAddressHereXYZ"

# 1. FIXED DIRECTORY ISSUE: Cross-platform Documents directory mapping
DOCS_DIR = Path.home() / "Documents" / "ssh_manager"
DOCS_DIR.mkdir(parents=True, exist_ok=True)

HOSTS_FILE = DOCS_DIR / "hosts.json"
SETTINGS_FILE = DOCS_DIR / "settings.json"

try:
    import qrcode
    HAS_QRCODE = True
except ImportError:
    HAS_QRCODE = False


@dataclass
class HostEntry:
    name: str
    host: str
    port: int
    username: str
    password: str = ""
    use_key: bool = False
    key_path: str = ""


@dataclass
class AppSettings:
    background_color: str = "#0b0b0b"
    panel_color: str = "#131313"
    text_color: str = "#e6d27a"
    accent_color: str = "#c9a63a"
    border_color: str = "#2a2410"
    font_size: int = 10
    show_hidden_files: bool = False


class HostStore:
    @staticmethod
    def load() -> List[HostEntry]:
        if not HOSTS_FILE.exists():
            return []
        try:
            data = json.loads(HOSTS_FILE.read_text(encoding="utf-8"))
            return [HostEntry(**item) for item in data]
        except Exception:
            return []

    @staticmethod
    def save(hosts: List[HostEntry]) -> None:
        HOSTS_FILE.write_text(
            json.dumps([asdict(h) for h in hosts], indent=2),
            encoding="utf-8",
        )


class SettingsStore:
    @staticmethod
    def load() -> AppSettings:
        if not SETTINGS_FILE.exists():
            return AppSettings()
        try:
            data = json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
            return AppSettings(**data)
        except Exception:
            return AppSettings()

    @staticmethod
    def save(settings: AppSettings) -> None:
        SETTINGS_FILE.write_text(json.dumps(asdict(settings), indent=2), encoding="utf-8")


class ToastNotification(QWidget):
    def __init__(self, parent, message, type_="success"):
        super().__init__(parent)
        colors = {
            "success": "#2e7d32",
            "error": "#8b1e1e",
            "info": "#355c7d"
        }
        icons = {
            "success": "✅",
            "error": "❌",
            "info": "ℹ️"
        }
        bg_color = colors.get(type_, "#4CAF50")
        icon = icons.get(type_, "✅")
        
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.ToolTip | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        
        frame = QFrame(self)
        frame.setStyleSheet(f"""
            QFrame {{
                background-color: {bg_color};
                border-radius: 8px;
            }}
            QLabel {{
                color: #f5e6a0;
                font-family: 'Segoe UI';
                font-weight: 600;
                font-size: 13px;
                padding: 6px;
            }}
        """)
        
        frame_layout = QHBoxLayout(frame)
        frame_layout.addWidget(QLabel(icon))
        frame_layout.addWidget(QLabel(message))
        frame_layout.addStretch(1)
        
        layout.addWidget(frame)
        self.adjustSize()
        
        if parent:
            parent_rect = parent.geometry()
            x = parent_rect.x() + parent_rect.width() - self.width() - 30
            y = parent_rect.y() + parent_rect.height() - self.height() - 30
            self.move(x, y)
        
        self.opacity_effect = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(self.opacity_effect)
        self.anim_in = QPropertyAnimation(self.opacity_effect, b"opacity")
        self.anim_in.setDuration(300)
        self.anim_in.setStartValue(0)
        self.anim_in.setEndValue(1)
        
        self.anim_out = QPropertyAnimation(self.opacity_effect, b"opacity")
        self.anim_out.setDuration(400)
        self.anim_out.setStartValue(1)
        self.anim_out.setEndValue(0)
        self.anim_out.finished.connect(self.deleteLater)
        
        self.show()
        self.anim_in.start()
        
        QTimer.singleShot(3500, self.anim_out.start)


class PythonMonitorDialog(QDialog):
    """
    New Dialog for Python Process Monitoring
    Shows a clean list of running python apps with Stop and Restart capabilities.
    """
    def __init__(self, parent, ssh_client):
        super().__init__(parent)
        self.ssh_client = ssh_client
        self.setWindowTitle("Python Apps Monitoring")
        self.setMinimumSize(850, 450)
        
        self.layout = QVBoxLayout(self)
        
        header_layout = QHBoxLayout()
        title = QLabel("Running Python Processes")
        title.setObjectName("sectionTitle")
        
        self.refresh_btn = QPushButton("🔄 Refresh List")
        self.refresh_btn.setCursor(Qt.PointingHandCursor)
        self.refresh_btn.clicked.connect(self.refresh_data)
        
        header_layout.addWidget(title)
        header_layout.addStretch(1)
        header_layout.addWidget(self.refresh_btn)
        
        self.layout.addLayout(header_layout)
        
        # Table setup
        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(["PID", "CPU%", "RAM%", "Command", "Actions"])
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.Stretch)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        
        self.layout.addWidget(self.table)
        
        # Load data initially
        self.refresh_data()

    def refresh_data(self):
        if not self.ssh_client:
            return
            
        self.table.setRowCount(0)
        self.refresh_btn.setText("⏳ Refreshing...")
        self.refresh_btn.setEnabled(False)
        QApplication.processEvents()
        
        try:
            # Using grep '[p]ython' is a trick to exclude the grep process itself
            command = "ps aux | grep '[p]ython'"
            stdin, stdout, stderr = self.ssh_client.exec_command(command)
            output = stdout.read().decode('utf-8').strip()
            
            lines = output.split('\n')
            for line in lines:
                if not line.strip():
                    continue
                parts = line.split(None, 10)
                if len(parts) >= 11:
                    user, pid, cpu, mem, vsz, rss, tty, stat, start, time, cmd = parts
                    
                    row = self.table.rowCount()
                    self.table.insertRow(row)
                    
                    self.table.setItem(row, 0, QTableWidgetItem(pid))
                    self.table.setItem(row, 1, QTableWidgetItem(f"{cpu}%"))
                    self.table.setItem(row, 2, QTableWidgetItem(f"{mem}%"))
                    self.table.setItem(row, 3, QTableWidgetItem(cmd))
                    
                    # Action buttons
                    action_widget = QWidget()
                    action_layout = QHBoxLayout(action_widget)
                    action_layout.setContentsMargins(4, 2, 4, 2)
                    action_layout.setSpacing(6)
                    
                    stop_btn = QPushButton("⏹ Stop")
                    stop_btn.setCursor(Qt.PointingHandCursor)
                    stop_btn.setStyleSheet("background-color: #8b1e1e; color: white;")
                    stop_btn.clicked.connect(lambda checked, p=pid: self.kill_process(p))
                    
                    restart_btn = QPushButton("🔄 Restart")
                    restart_btn.setCursor(Qt.PointingHandCursor)
                    restart_btn.setStyleSheet("background-color: #2e7d32; color: white;")
                    restart_btn.clicked.connect(lambda checked, p=pid, c=cmd: self.restart_process(p, c))
                    
                    action_layout.addWidget(stop_btn)
                    action_layout.addWidget(restart_btn)
                    self.table.setCellWidget(row, 4, action_widget)
                    
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Failed to fetch processes:\n{e}")
            
        self.refresh_btn.setText("🔄 Refresh List")
        self.refresh_btn.setEnabled(True)

    def kill_process(self, pid):
        if QMessageBox.question(self, "Stop Process", f"Are you sure you want to stop PID {pid}?", QMessageBox.Yes | QMessageBox.No) == QMessageBox.Yes:
            try:
                self.ssh_client.exec_command(f"kill -9 {pid}")
                QTimer.singleShot(500, self.refresh_data) # wait half a sec then refresh
                if self.parent() and hasattr(self.parent(), "show_toast"):
                    self.parent().show_toast(f"Process {pid} stopped.", "info")
            except Exception as e:
                QMessageBox.warning(self, "Error", f"Could not kill process:\n{e}")

    def restart_process(self, pid, cmd):
        if QMessageBox.question(self, "Restart Process", f"Restart this Python app?\nPID: {pid}", QMessageBox.Yes | QMessageBox.No) == QMessageBox.Yes:
            try:
                # 1. Find the working directory of the process before killing it
                stdin, stdout, _ = self.ssh_client.exec_command(f"readlink -e /proc/{pid}/cwd")
                cwd = stdout.read().decode('utf-8').strip()
                
                # 2. Kill current process
                self.ssh_client.exec_command(f"kill -9 {pid}")
                
                # 3. Re-run from the exact same directory in background
                if cwd:
                    run_cmd = f"cd {cwd} && nohup {cmd} >/dev/null 2>&1 &"
                else:
                    run_cmd = f"nohup {cmd} >/dev/null 2>&1 &"
                    
                self.ssh_client.exec_command(run_cmd)
                
                if self.parent() and hasattr(self.parent(), "show_toast"):
                    self.parent().show_toast("App restarted successfully!", "success")
                    
                QTimer.singleShot(1000, self.refresh_data)
            except Exception as e:
                QMessageBox.warning(self, "Error", f"Could not restart process:\n{e}")


# --- All other dialogs remain unchanged ---

class AddHostDialog(QDialog):
    def __init__(self, parent=None, host: Optional[HostEntry] = None):
        super().__init__(parent)
        self.setWindowTitle("Add Host" if host is None else "Edit Host")
        self.setModal(True)
        self.setMinimumWidth(440)

        self.name_edit = QLineEdit()
        self.host_edit = QLineEdit()
        self.port_edit = QLineEdit("22")
        self.username_edit = QLineEdit()
        self.password_edit = QLineEdit()
        self.password_edit.setEchoMode(QLineEdit.Password)
        self.use_key_check = QCheckBox("Use SSH Key")
        self.key_path_edit = QLineEdit()
        self.key_browse_btn = QPushButton("Browse...")

        self.name_edit.setPlaceholderText("Friendly Name")
        self.host_edit.setPlaceholderText("IP Address or Domain")
        self.username_edit.setPlaceholderText("Username")
        self.password_edit.setPlaceholderText("Password")
        self.key_path_edit.setPlaceholderText("Private Key Path")

        self.key_browse_btn.clicked.connect(self.browse_key)
        self.use_key_check.stateChanged.connect(self.update_key_state)

        form = QFormLayout()
        form.addRow("Name:", self.name_edit)
        form.addRow("Host / IP:", self.host_edit)
        form.addRow("Port:", self.port_edit)
        form.addRow("Username:", self.username_edit)
        form.addRow("Password:", self.password_edit)
        form.addRow(self.use_key_check)

        key_row = QHBoxLayout()
        key_row.addWidget(self.key_path_edit)
        key_row.addWidget(self.key_browse_btn)
        key_wrap = QWidget()
        key_wrap.setLayout(key_row)
        key_wrap.setContentsMargins(0, 0, 0, 0)
        form.addRow("Key Path:", key_wrap)

        btn_row = QHBoxLayout()
        btn_row.addStretch(1)
        cancel = QPushButton("Cancel")
        save = QPushButton("Save")
        save.setObjectName("primaryButton")
        cancel.clicked.connect(self.reject)
        save.clicked.connect(self.accept)
        btn_row.addWidget(cancel)
        btn_row.addWidget(save)

        root = QVBoxLayout(self)
        title = QLabel("Host Details")
        title.setObjectName("sectionTitle")
        root.addWidget(title)
        root.addLayout(form)
        root.addStretch(1)
        root.addLayout(btn_row)

        if host:
            self.name_edit.setText(host.name)
            self.host_edit.setText(host.host)
            self.port_edit.setText(str(host.port))
            self.username_edit.setText(host.username)
            self.password_edit.setText(host.password)
            self.use_key_check.setChecked(host.use_key)
            self.key_path_edit.setText(host.key_path)
        self.update_key_state()

    def browse_key(self):
        path, _ = QFileDialog.getOpenFileName(self, "Select Private Key File")
        if path:
            self.key_path_edit.setText(path)

    def update_key_state(self):
        enabled = self.use_key_check.isChecked()
        self.password_edit.setEnabled(not enabled)
        self.key_path_edit.setEnabled(enabled)
        self.key_browse_btn.setEnabled(enabled)

    def get_data(self) -> HostEntry:
        return HostEntry(
            name=self.name_edit.text().strip(),
            host=self.host_edit.text().strip(),
            port=int(self.port_edit.text().strip() or "22"),
            username=self.username_edit.text().strip(),
            password=self.password_edit.text(),
            use_key=self.use_key_check.isChecked(),
            key_path=self.key_path_edit.text().strip(),
        )


class SettingsDialog(QDialog):
    def __init__(self, parent=None, settings: Optional[AppSettings] = None):
        super().__init__(parent)
        self.setWindowTitle("Settings")
        self.setModal(True)
        self.setMinimumWidth(400)
        self.settings = settings or AppSettings()

        form = QFormLayout()

        self.bg_btn = self.create_color_button(self.settings.background_color)
        self.panel_btn = self.create_color_button(self.settings.panel_color)
        self.text_btn = self.create_color_button(self.settings.text_color)
        self.accent_btn = self.create_color_button(self.settings.accent_color)
        self.border_btn = self.create_color_button(self.settings.border_color)
        
        self.font_spin = QSpinBox()
        self.font_spin.setRange(8, 20)
        self.font_spin.setValue(self.settings.font_size)
        
        self.hidden_check = QCheckBox("Show hidden files in SFTP")
        self.hidden_check.setChecked(self.settings.show_hidden_files)

        form.addRow("Background Color:", self.bg_btn)
        form.addRow("Panel Color:", self.panel_btn)
        form.addRow("Text Color:", self.text_btn)
        form.addRow("Accent Color:", self.accent_btn)
        form.addRow("Border Color:", self.border_btn)
        form.addRow("Font Size:", self.font_spin)
        form.addRow(self.hidden_check)

        btn_row = QHBoxLayout()
        btn_row.addStretch(1)
        reset = QPushButton("Reset")
        cancel = QPushButton("Cancel")
        save = QPushButton("Save")
        save.setObjectName("primaryButton")
        reset.clicked.connect(self.reset_defaults)
        cancel.clicked.connect(self.reject)
        save.clicked.connect(self.accept)
        btn_row.addWidget(reset)
        btn_row.addWidget(cancel)
        btn_row.addWidget(save)

        root = QVBoxLayout(self)
        title = QLabel("Customize Appearance")
        title.setObjectName("sectionTitle")
        root.addWidget(title)
        root.addLayout(form)
        root.addStretch(1)
        root.addLayout(btn_row)

    def create_color_button(self, hex_color: str) -> QPushButton:
        btn = QPushButton()
        btn.setFixedSize(60, 25)
        btn.setCursor(Qt.PointingHandCursor)
        self.set_button_color(btn, hex_color)
        btn.clicked.connect(lambda _, b=btn: self.pick_color(b))
        return btn

    def set_button_color(self, btn: QPushButton, hex_color: str):
        btn.color_hex = hex_color
        btn.setStyleSheet(f"background-color: {hex_color}; border: 1px solid #555; border-radius: 4px;")

    def pick_color(self, btn: QPushButton):
        initial_color = QColor(btn.color_hex)
        color = QColorDialog.getColor(initial_color, self, "Select Color")
        if color.isValid():
            self.set_button_color(btn, color.name())

    def reset_defaults(self):
        defaults = AppSettings()
        self.set_button_color(self.bg_btn, defaults.background_color)
        self.set_button_color(self.panel_btn, defaults.panel_color)
        self.set_button_color(self.text_btn, defaults.text_color)
        self.set_button_color(self.accent_btn, defaults.accent_color)
        self.set_button_color(self.border_btn, defaults.border_color)
        self.font_spin.setValue(defaults.font_size)
        self.hidden_check.setChecked(defaults.show_hidden_files)

    def get_settings(self) -> AppSettings:
        return AppSettings(
            background_color=self.bg_btn.color_hex,
            panel_color=self.panel_btn.color_hex,
            text_color=self.text_btn.color_hex,
            accent_color=self.accent_btn.color_hex,
            border_color=self.border_btn.color_hex,
            font_size=self.font_spin.value(),
            show_hidden_files=self.hidden_check.isChecked(),
        )


class DonateDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Donate")
        self.setModal(True)
        self.setFixedSize(360, 480)

        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignCenter)
        layout.setSpacing(15)

        title = QLabel("Support the Developer")
        title.setObjectName("sectionTitle")
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)

        desc = QLabel("If you like Argus ssh, consider donating\nusing the Tether (USDT-TRC20) address below.")
        desc.setAlignment(Qt.AlignCenter)
        layout.addWidget(desc)

        self.qr_label = QLabel()
        self.qr_label.setAlignment(Qt.AlignCenter)
        self.qr_label.setStyleSheet("background-color: #ffffff; border-radius: 10px; padding: 10px;")
        
        if HAS_QRCODE:
            try:
                qr = qrcode.QRCode(
                    version=1,
                    error_correction=qrcode.constants.ERROR_CORRECT_L,
                    box_size=8,
                    border=2,
                )
                qr.add_data(TETHER_WALLET_ADDRESS)
                qr.make(fit=True)
                img = qr.make_image(fill_color="black", back_color="white")
                
                buf = io.BytesIO()
                img.save(buf, format="PNG")
                pixmap = QPixmap()
                pixmap.loadFromData(buf.getvalue())
                self.qr_label.setPixmap(pixmap)
            except Exception as e:
                self.qr_label.setText(f"Error generating QR:\n{e}")
        else:
            self.qr_label.setText("QR Code feature requires 'qrcode' library.\n\nPlease install it using:\npip install qrcode[pil]")
            self.qr_label.setStyleSheet("color: red; background-color: #2a2a2a; padding: 10px;")

        layout.addWidget(self.qr_label)

        address_label = QLabel("Tether (USDT) Address:")
        address_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(address_label)

        self.address_edit = QLineEdit(TETHER_WALLET_ADDRESS)
        self.address_edit.setReadOnly(True)
        self.address_edit.setAlignment(Qt.AlignCenter)
        self.address_edit.setStyleSheet("padding: 8px; font-size: 11pt;")
        layout.addWidget(self.address_edit)

        copy_btn = QPushButton("Copy Wallet Address")
        copy_btn.setObjectName("primaryButton")
        copy_btn.setCursor(Qt.PointingHandCursor)
        copy_btn.clicked.connect(self.copy_address)
        layout.addWidget(copy_btn)

    def copy_address(self):
        clipboard = QApplication.clipboard()
        clipboard.setText(TETHER_WALLET_ADDRESS)
        if self.parent() and hasattr(self.parent(), "show_toast"):
            self.parent().show_toast("Wallet address copied to clipboard!", "success")
        else:
            QMessageBox.information(self, "Copied", "Wallet address copied to clipboard!")


class ShellReader(QThread):
    output = pyqtSignal(str)
    closed = pyqtSignal()
    error = pyqtSignal(str)

    def __init__(self, channel: paramiko.Channel):
        super().__init__()
        self.channel = channel
        self._running = True

    def clean_ansi(self, text: str) -> str:
        text = re.sub(r'\x1b\][^\x07\x1b]*(?:\x07|\x1b\\)', '', text)
        text = re.sub(r'\x1b\[[0-?]*[ -/]*[@-~]', '', text)
        text = re.sub(r'\x1b[@-_]', '', text)
        return text

    def run(self):
        try:
            while self._running:
                if self.channel.recv_ready():
                    data = self.channel.recv(4096)
                    if data:
                        text = data.decode("utf-8", errors="ignore")
                        self.output.emit(self.clean_ansi(text))
                if self.channel.recv_stderr_ready():
                    data = self.channel.recv_stderr(4096)
                    if data:
                        text = data.decode("utf-8", errors="ignore")
                        self.output.emit(self.clean_ansi(text))
                if self.channel.exit_status_ready():
                    break
                self.msleep(25)
        except Exception as e:
            self.error.emit(str(e))
        finally:
            self.closed.emit()

    def stop(self):
        self._running = False
        try:
            self.channel.close()
        except Exception:
            pass


class TerminalWidget(QPlainTextEdit):
    commandEntered = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setUndoRedoEnabled(False)
        self.setLineWrapMode(QPlainTextEdit.NoWrap)

        self.history: List[str] = []
        self.history_index = 0
        self._locked_pos = 0
        self._draft_input = ""
        self._pending_echoes: List[str] = []

    def _replace_current_input(self, text: str):
        before = self.toPlainText()[: self._locked_pos]
        self.setPlainText(before + text)
        cursor = self.textCursor()
        cursor.movePosition(QTextCursor.End)
        self.setTextCursor(cursor)
        self.ensureCursorVisible()

    def _current_input(self) -> str:
        return self.toPlainText()[self._locked_pos:]

    def expect_echo(self, cmd: str):
        cmd = cmd.strip()
        if cmd:
            self._pending_echoes.append(cmd)

    def _strip_first_echo(self, text: str) -> str:
        if not self._pending_echoes:
            return text

        pending = self._pending_echoes[0]
        normalized = text.replace("\r\n", "\n").replace("\r", "\n")
        lines = normalized.split("\n")

        for i, line in enumerate(lines):
            if pending not in line:
                continue

            stripped = line.strip()
            if stripped == pending:
                lines.pop(i)
                self._pending_echoes.pop(0)
                return "\n".join(lines)

            idx = line.rfind(pending)
            if idx != -1:
                new_line = line[:idx] + line[idx + len(pending):]
                lines[i] = new_line
                if not new_line.strip():
                    lines.pop(i)
                self._pending_echoes.pop(0)
                return "\n".join(lines)

        return text

    def append_remote_output(self, text: str):
        if not text:
            return

        text = self._strip_first_echo(text)
        text = text.replace('\r\n', '\n').replace('\r', '\n')
        if not text:
            return

        cursor = self.textCursor()
        cursor.movePosition(QTextCursor.End)
        self.setTextCursor(cursor)
        self.insertPlainText(text)

        self._locked_pos = self.textCursor().position()
        self.ensureCursorVisible()

    def clear_terminal(self):
        self.clear()
        self._locked_pos = 0
        self._draft_input = ""
        self._pending_echoes.clear()

    def keyPressEvent(self, event):
        cursor = self.textCursor()

        if event.isAutoRepeat() and event.key() in (Qt.Key_Up, Qt.Key_Down):
            return

        if cursor.position() < self._locked_pos:
            cursor.movePosition(QTextCursor.End)
            self.setTextCursor(cursor)

        if event.key() in (Qt.Key_Backspace, Qt.Key_Left):
            if self.textCursor().position() <= self._locked_pos:
                return

        if event.key() in (Qt.Key_Return, Qt.Key_Enter):
            cmd = self._current_input().rstrip("\n")

            cursor = self.textCursor()
            cursor.movePosition(QTextCursor.End)
            self.setTextCursor(cursor)
            self.insertPlainText("\n")

            if cmd.strip():
                self.history.append(cmd.strip())
                self.history_index = len(self.history)
                self._draft_input = ""
                self.expect_echo(cmd)

            self._locked_pos = self.textCursor().position()
            self.commandEntered.emit(cmd)
            event.accept()
            return

        if event.key() == Qt.Key_Up:
            if self.history:
                if self.history_index == len(self.history):
                    self._draft_input = self._current_input()
                self.history_index = max(0, self.history_index - 1)
                self._replace_current_input(self.history[self.history_index])
            return

        if event.key() == Qt.Key_Down:
            if self.history:
                self.history_index = min(len(self.history), self.history_index + 1)
                if self.history_index < len(self.history):
                    self._replace_current_input(self.history[self.history_index])
                else:
                    self._replace_current_input(self._draft_input)
            return

        super().keyPressEvent(event)


class SFTPWorker(QThread):
    loaded = pyqtSignal(list, str)
    error = pyqtSignal(str)

    def __init__(self, sftp: paramiko.SFTPClient, path: str, show_hidden: bool = False):
        super().__init__()
        self.sftp = sftp
        self.path = path
        self.show_hidden = show_hidden

    def run(self):
        try:
            items = []
            for attr in self.sftp.listdir_attr(self.path):
                if not self.show_hidden and attr.filename.startswith("."):
                    continue
                items.append(attr)
            self.loaded.emit(items, self.path)
        except Exception as e:
            self.error.emit(str(e))


def human_size(num: int) -> str:
    step = 1024.0
    units = ["B", "KB", "MB", "GB", "TB"]
    value = float(num)
    for unit in units:
        if value < step:
            return f"{value:.0f} {unit}" if unit == "B" else f"{value:.1f} {unit}"
        value /= step
    return f"{value:.1f} PB"


def human_time(epoch: float) -> str:
    from datetime import datetime
    try:
        return datetime.fromtimestamp(epoch).strftime("%Y-%m-%d %H:%M")
    except Exception:
        return "-"


class RemotePanel(QWidget):
    def __init__(self, settings: AppSettings, parent=None):
        super().__init__(parent)
        self.client: Optional[paramiko.SSHClient] = None
        self.sftp: Optional[paramiko.SFTPClient] = None
        self.shell_channel: Optional[paramiko.Channel] = None
        self.shell_reader: Optional[ShellReader] = None
        self.current_path = "."
        self.settings = settings
        self._sftp_request_id = 0

        self.path_label = QLabel("Disconnected")
        self.path_label.setObjectName("pathLabel")

        self.back_btn = QPushButton("Up")
        self.refresh_btn = QPushButton("Refresh")
        self.new_folder_btn = QPushButton("New Folder")
        self.upload_btn = QPushButton("Upload")
        self.download_btn = QPushButton("Download")
        self.delete_btn = QPushButton("Delete")
        
        # --- Python App Menu Button Setup ---
        self.python_app_btn = QPushButton("🐍 Python App")
        self.python_app_btn.setObjectName("pythonMenuButton")
        self.python_app_btn.setCursor(Qt.PointingHandCursor)
        self.python_app_btn.setStyleSheet("font-weight: bold;")
        
        self.python_menu = QMenu(self.python_app_btn)
        self.action_run_py = self.python_menu.addAction("▶️ Run Python Code (Selected File)")
        self.action_monitor = self.python_menu.addAction("📊 Monitoring")
        
        # Connect Actions
        self.action_run_py.triggered.connect(self.run_selected_python)
        self.action_monitor.triggered.connect(self.open_python_monitor)
        
        self.python_app_btn.setMenu(self.python_menu)
        # -------------------------------------
        
        for btn in [self.back_btn, self.refresh_btn, self.new_folder_btn, self.upload_btn, self.download_btn, self.delete_btn]:
            btn.setCursor(Qt.PointingHandCursor)

        self.back_btn.clicked.connect(self.go_up)
        self.refresh_btn.clicked.connect(self.refresh_sftp)
        self.new_folder_btn.clicked.connect(self.create_folder)
        self.upload_btn.clicked.connect(self.upload_file)
        self.download_btn.clicked.connect(self.download_selected)
        self.delete_btn.clicked.connect(self.delete_selected)

        top_bar = QVBoxLayout()
        top_bar.setContentsMargins(0, 0, 0, 4)
        top_bar.setSpacing(8)

        title_row = QHBoxLayout()
        title = QLabel("File & Terminal Manager")
        title.setObjectName("sectionTitle")
        title_row.addWidget(title)
        title_row.addStretch(1)
        
        # Add Python Menu to Top Right
        title_row.addWidget(self.python_app_btn)
        
        top_bar.addLayout(title_row)
        top_bar.addWidget(self.path_label)

        btn_row = QHBoxLayout()
        btn_row.addWidget(self.back_btn)
        btn_row.addWidget(self.refresh_btn)
        btn_row.addWidget(self.new_folder_btn)
        btn_row.addWidget(self.upload_btn)
        btn_row.addWidget(self.download_btn)
        btn_row.addWidget(self.delete_btn)
        btn_row.addStretch(1)
        
        top_bar.addLayout(btn_row)

        self.file_table = QTableWidget(0, 4)
        self.file_table.setHorizontalHeaderLabels(["Name", "Type", "Size", "Modified"])
        self.file_table.horizontalHeader().setStretchLastSection(True)
        self.file_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.file_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.file_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.file_table.doubleClicked.connect(self.on_double_click)

        self.terminal_output = TerminalWidget()
        self.terminal_output.commandEntered.connect(self.send_command)

        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 3, 0)
        left_layout.addWidget(QLabel("Remote Files:"))
        left_layout.addWidget(self.file_table, 1)

        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(3, 0, 0, 0)
        right_layout.addWidget(QLabel("Live Terminal:"))
        right_layout.addWidget(self.terminal_output, 1)

        splitter = QSplitter(Qt.Horizontal)
        splitter.addWidget(left)
        splitter.addWidget(right)
        splitter.setSizes([500, 640])

        root = QVBoxLayout(self)
        root.setContentsMargins(6, 6, 6, 6)
        root.addLayout(top_bar)
        root.addWidget(splitter, 1)

        self.set_remote_state(False)

    def set_settings(self, settings: AppSettings):
        self.settings = settings
        if self.client:
            QTimer.singleShot(0, self.refresh_sftp)

    def set_remote_state(self, connected: bool):
        # Enable/Disable all action buttons based on connection
        for widget in [self.back_btn, self.refresh_btn, self.new_folder_btn, self.upload_btn, self.download_btn, self.delete_btn, self.python_app_btn]:
            widget.setEnabled(connected)
            
        self.terminal_output.setEnabled(True)
        if not connected:
            self.path_label.setText("Disconnected")
            self.file_table.setRowCount(0)
            self.terminal_output.clear_terminal()
            self.terminal_output.append_remote_output("No active connection.\n")

    # --- Python App Menu Actions ---
    def run_selected_python(self):
        if not self.sftp or not self.client:
            return
            
        name = self.selected_name()
        if not name or self.selected_is_dir() or not name.endswith('.py'):
            win = self.window()
            if win and hasattr(win, "show_toast"):
                win.show_toast("Please select a .py file from the SFTP list first.", "error")
            return

        remote_path = posixpath.join(self.current_path, name) if self.current_path != "." else name
        log_file = f"{name}.log"
        
        # Execute using nohup in background, redirecting output so GUI doesn't freeze
        cmd = f'cd "{self.current_path}" && nohup python3 "{name}" > "{log_file}" 2>&1 &'
        
        try:
            self.client.exec_command(cmd)
            win = self.window()
            if win and hasattr(win, "show_toast"):
                win.show_toast(f"Started '{name}' in background!", "success")
                
            # Refresh directory after 1.5 seconds to show the new .log file
            QTimer.singleShot(1500, self.refresh_sftp)
        except Exception as e:
            win = self.window()
            if win and hasattr(win, "show_toast"):
                win.show_toast(f"Failed to run script: {e}", "error")

    def open_python_monitor(self):
        if not self.client:
            return
        dialog = PythonMonitorDialog(self, self.client)
        dialog.exec_()
    # -------------------------------

    def connect_host(self, entry: HostEntry):
        self.disconnect_host()
        try:
            client = paramiko.SSHClient()
            client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

            connect_kwargs = dict(
                hostname=entry.host,
                port=entry.port,
                username=entry.username,
                timeout=15,
                banner_timeout=15,
                auth_timeout=15,
            )

            if entry.use_key and entry.key_path:
                key_path = os.path.expanduser(entry.key_path)
                key = None
                errors = []
                for key_loader in (
                    paramiko.RSAKey.from_private_key_file,
                    paramiko.Ed25519Key.from_private_key_file,
                    paramiko.ECDSAKey.from_private_key_file,
                ):
                    try:
                        key = key_loader(key_path)
                        break
                    except Exception as e:
                        errors.append(str(e))
                if key is None:
                    raise RuntimeError("Failed to load SSH Key.")
                connect_kwargs["pkey"] = key
            else:
                connect_kwargs["password"] = entry.password

            client.connect(**connect_kwargs)
            self.client = client
            self.sftp = client.open_sftp()
            
            self.shell_channel = client.invoke_shell(term="xterm") 
            try:
                self.shell_channel.send("stty -echo 2>/dev/null || true\n")
            except Exception:
                pass
            self.shell_reader = ShellReader(self.shell_channel)
            self.shell_reader.output.connect(self.terminal_output.append_remote_output)
            self.shell_reader.error.connect(self.terminal_output.append_remote_output)
            self.shell_reader.closed.connect(self.on_shell_closed)
            self.shell_reader.start()

            self.terminal_output.clear_terminal()
            self.set_remote_state(True)
            self.current_path = "."
            self.refresh_sftp()
            
            if self.window() and hasattr(self.window(), 'show_toast'):
                self.window().show_toast(f"Connected to {entry.name}", "success")
                
        except Exception as e:
            self.disconnect_host()
            raise RuntimeError(f"Connection Failed: {e}")

    def disconnect_host(self):
        try:
            if self.shell_reader:
                self.shell_reader.stop()
                self.shell_reader.wait(1000)
        except Exception:
            pass
        self.shell_reader = None
        try:
            if self.shell_channel:
                self.shell_channel.close()
        except Exception:
            pass
        self.shell_channel = None
        try:
            if self.sftp:
                self.sftp.close()
        except Exception:
            pass
        self.sftp = None
        try:
            if self.client:
                self.client.close()
        except Exception:
            pass
        self.client = None
        self.set_remote_state(False)

    def on_shell_closed(self):
        self.terminal_output.append_remote_output("\n[Terminal session closed]\n")

    def send_command(self, cmd: str):
        if not self.shell_channel:
            return
        try:
            self.shell_channel.send(cmd + "\n")
        except Exception as e:
            if self.window() and hasattr(self.window(), 'show_toast'):
                win = self.window()
                if win and hasattr(win, "show_toast"):
                    win.show_toast(f"Terminal Error: {e}", "error")

    def refresh_sftp(self):
        if not self.sftp:
            return
        self._sftp_request_id += 1
        request_id = self._sftp_request_id
        self.path_label.setText(f"Path: {self.current_path}")
        self.worker = SFTPWorker(self.sftp, self.current_path, self.settings.show_hidden_files)
        self.worker.loaded.connect(lambda items, path, rid=request_id: self._handle_sftp_loaded(rid, items, path))
        self.worker.error.connect(lambda msg, rid=request_id: self._handle_sftp_error(rid, msg))
        self.worker.start()

    def _handle_sftp_loaded(self, request_id: int, items, path: str):
        if request_id != self._sftp_request_id:
            return
        self.populate_files(items, path)

    def _handle_sftp_error(self, request_id: int, msg: str):
        if request_id != self._sftp_request_id:
            return
        win = self.window()
        if win and hasattr(win, 'show_toast'):
            win.show_toast(f"SFTP Error: {msg}", "error")

    def populate_files(self, items, path: str):
        self.current_path = path
        display_path = "/" if path in (".", "") else path
        self.path_label.setText(f"Path: {display_path}")
        self.file_table.setRowCount(0)

        if not items:
            self.file_table.setRowCount(1)
            self.file_table.setItem(0, 0, QTableWidgetItem("This folder is empty"))
            self.file_table.setItem(0, 1, QTableWidgetItem("-"))
            self.file_table.setItem(0, 2, QTableWidgetItem("-"))
            self.file_table.setItem(0, 3, QTableWidgetItem("-"))
            return

        def item_sort_key(attr):
            is_dir = stat.S_ISDIR(attr.st_mode)
            return (0 if is_dir else 1, attr.filename.lower())

        for attr in sorted(items, key=item_sort_key):
            row = self.file_table.rowCount()
            self.file_table.insertRow(row)

            is_dir = stat.S_ISDIR(attr.st_mode)
            name = attr.filename
            ftype = "Folder" if is_dir else "File"
            size = "<DIR>" if is_dir else human_size(attr.st_size)
            mtime = human_time(attr.st_mtime)

            cells = [name, ftype, size, mtime]
            for col, value in enumerate(cells):
                cell = QTableWidgetItem(value)
                if col == 0 and is_dir:
                    cell.setText("📁 " + value)
                elif col == 0:
                    cell.setText("📄 " + value)
                self.file_table.setItem(row, col, cell)

    def selected_name(self) -> Optional[str]:
        rows = self.file_table.selectionModel().selectedRows()
        if not rows:
            return None
        row = rows[0].row()
        item = self.file_table.item(row, 0)
        if not item:
            return None
        text = item.text().replace("📁 ", "").replace("📄 ", "")
        if text == "This folder is empty":
            return None
        return text

    def selected_is_dir(self) -> bool:
        rows = self.file_table.selectionModel().selectedRows()
        if not rows:
            return False
        row = rows[0].row()
        item = self.file_table.item(row, 1)
        return bool(item and item.text() == "Folder")

    def on_double_click(self):
        if self.selected_is_dir():
            name = self.selected_name()
            if not name:
                return
            new_path = posixpath.join(self.current_path, name) if self.current_path != "." else name
            self.current_path = new_path
            self.refresh_sftp()
        else:
            self.download_selected()

    def go_up(self):
        if self.current_path in (".", "/"):
            return
        parent = posixpath.dirname(self.current_path.rstrip("/"))
        self.current_path = parent if parent else "."
        self.refresh_sftp()

    def create_folder(self):
        if not self.sftp: return
        name, ok = QInputDialog.getText(self, "New Folder", "Enter folder name:")
        if ok and name:
            remote_path = posixpath.join(self.current_path, name) if self.current_path != "." else name
            try:
                self.sftp.mkdir(remote_path)
                self.refresh_sftp()
                win = self.window()
                if win and hasattr(win, "show_toast"):
                    win.show_toast(f"Folder '{name}' created successfully", "success")
            except Exception as e:
                win = self.window()
                if win and hasattr(win, "show_toast"):
                    win.show_toast(f"Failed to create folder: {e}", "error")

    def upload_file(self):
        if not self.sftp:
            return
        local_path, _ = QFileDialog.getOpenFileName(self, "Select File to Upload")
        if not local_path:
            return
        remote_name = os.path.basename(local_path)
        remote_path = posixpath.join(self.current_path, remote_name) if self.current_path != "." else remote_name
        try:
            self.sftp.put(local_path, remote_path)
            self.refresh_sftp()
            if hasattr(self.window(), 'show_toast'):
                win = self.window()
                if win and hasattr(win, "show_toast"):
                    win.show_toast(f"'{remote_name}' uploaded successfully!", "info")
        except Exception as e:
            if hasattr(self.window(), 'show_toast'):
                win = self.window()
                if win and hasattr(win, "show_toast"):
                    win.show_toast(f"Upload Error: {e}", "error")

    def download_selected(self):
        if not self.sftp:
            return
        name = self.selected_name()
        if not name:
            return
        if self.selected_is_dir():
            if hasattr(self.window(), 'show_toast'):
                win = self.window()
                if win and hasattr(win, "show_toast"):
                    win.show_toast("Folder download is not supported.", "error")
            return
        remote_path = posixpath.join(self.current_path, name) if self.current_path != "." else name
        local_path, _ = QFileDialog.getSaveFileName(self, "Save File", name)
        if not local_path:
            return
        try:
            self.sftp.get(remote_path, local_path)
            if hasattr(self.window(), 'show_toast'):
                win = self.window()
                if win and hasattr(win, "show_toast"):
                    win.show_toast(f"'{name}' downloaded successfully!", "info")
        except Exception as e:
            if hasattr(self.window(), 'show_toast'):
                win = self.window()
                if win and hasattr(win, "show_toast"):
                    win.show_toast(f"Download Error: {e}", "error")

    def delete_selected(self):
        if not self.sftp:
            return
        name = self.selected_name()
        if not name:
            return
        if QMessageBox.question(self, "Delete", f"Are you sure you want to delete '{name}'?", QMessageBox.Yes | QMessageBox.No) != QMessageBox.Yes:
            return
        remote_path = posixpath.join(self.current_path, name) if self.current_path != "." else name
        try:
            if self.selected_is_dir():
                self.sftp.rmdir(remote_path)
            else:
                self.sftp.remove(remote_path)
            self.refresh_sftp()
            if hasattr(self.window(), 'show_toast'):
                win = self.window()
                if win and hasattr(win, "show_toast"):
                    win.show_toast(f"'{name}' deleted successfully", "info")
        except Exception as e:
            if hasattr(self.window(), 'show_toast'):
                win = self.window()
                if win and hasattr(win, "show_toast"):
                    win.show_toast(f"Delete Error: {e}", "error")


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"{APP_NAME} v{APP_VERSION}")
        self.resize(1480, 880)

        self.hosts: List[HostEntry] = HostStore.load()
        self.settings: AppSettings = SettingsStore.load()
        self.current_index: Optional[int] = None
        self._toasts: List[QWidget] = []

        self.root = QWidget()
        self.setCentralWidget(self.root)
        self.layout = QHBoxLayout(self.root)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(0)

        self.sidebar = QFrame()
        self.sidebar.setObjectName("sidebar")
        self.sidebar.setMinimumWidth(300)
        self.sidebar_layout = QVBoxLayout(self.sidebar)
        self.sidebar_layout.setContentsMargins(14, 14, 14, 14)
        self.sidebar_layout.setSpacing(10)

        brand = QLabel(APP_NAME)
        brand.setObjectName("brandLabel")
        subtitle = QLabel("Manage your servers")
        subtitle.setObjectName("subtitleLabel")

        self.add_host_btn = QPushButton("+ Add New Host")
        self.add_host_btn.setObjectName("primaryButton")
        self.add_host_btn.clicked.connect(self.add_host)

        self.settings_btn = QPushButton("App Settings")
        self.settings_btn.clicked.connect(self.open_settings)

        self.edit_host_btn = QPushButton("Edit")
        self.remove_host_btn = QPushButton("Remove")
        self.connect_btn = QPushButton("Connect")
        self.connect_btn.setObjectName("connectButton")
        self.disconnect_btn = QPushButton("Disconnect")

        for btn in [self.edit_host_btn, self.remove_host_btn, self.connect_btn, self.disconnect_btn, self.settings_btn]:
            btn.setCursor(Qt.PointingHandCursor)

        self.edit_host_btn.clicked.connect(self.edit_host)
        self.remove_host_btn.clicked.connect(self.remove_host)
        self.connect_btn.clicked.connect(self.connect_selected)
        self.disconnect_btn.clicked.connect(self.disconnect_selected)

        action_row = QGridLayout()
        action_row.addWidget(self.connect_btn, 0, 0, 1, 2)
        action_row.addWidget(self.disconnect_btn, 1, 0, 1, 2)
        action_row.addWidget(self.edit_host_btn, 2, 0)
        action_row.addWidget(self.remove_host_btn, 2, 1)

        self.host_list = QListWidget()
        self.host_list.itemClicked.connect(self.on_host_clicked)
        self.host_list.itemDoubleClicked.connect(lambda _: self.connect_selected())

        credits = QLabel(
            "Developer:\n"
            "Telegram: champ_studio\n"
            "GitHub: wtfchampion"
        )
        credits.setObjectName("creditsLabel")

        self.status_label = QLabel("No host selected.")
        self.status_label.setObjectName("statusLabel")

        self.sidebar_layout.addWidget(brand)
        self.sidebar_layout.addWidget(subtitle)
        self.sidebar_layout.addWidget(self.add_host_btn)
        self.sidebar_layout.addWidget(self.settings_btn)
        self.sidebar_layout.addLayout(action_row)
        self.sidebar_layout.addWidget(QLabel("Saved Hosts:"))
        self.sidebar_layout.addWidget(self.host_list, 1)
        self.sidebar_layout.addWidget(self.status_label)
        self.sidebar_layout.addWidget(credits)

        self.stack = QStackedWidget()
        self.empty_page = self.build_empty_page()
        self.remote_panel = RemotePanel(self.settings)
        self.stack.addWidget(self.empty_page)
        self.stack.addWidget(self.remote_panel)
        self.stack.setCurrentWidget(self.empty_page)

        self.layout.addWidget(self.sidebar)
        self.layout.addWidget(self.stack, 1)

        self._toasts = []
        self.build_toolbar()
        self.apply_theme(self.settings)
        self.refresh_host_list()

    def show_toast(self, message, type_="success"):
        self.statusBar().showMessage(message, 2500)
        try:
            toast = ToastNotification(self, message, type_)
            self._toasts.append(toast)
            def _cleanup(*_):
                try:
                    self._toasts.remove(toast)
                except ValueError:
                    pass
            toast.destroyed.connect(_cleanup)
            toast.raise_()
        except Exception:
            pass

    def build_toolbar(self):
        tb = QToolBar()
        tb.setMovable(False)
        tb.setIconSize(QSize(18, 18))
        self.addToolBar(tb)

        about_btn = QPushButton("About")
        about_btn.setCursor(Qt.PointingHandCursor)
        about_btn.clicked.connect(self.show_about)
        tb.addWidget(about_btn)

        donate_btn = QPushButton("Donate")
        donate_btn.setCursor(Qt.PointingHandCursor)
        donate_btn.clicked.connect(self.show_donate)
        tb.addWidget(donate_btn)

        buy_host_btn = QPushButton("Buy Host")
        buy_host_btn.setCursor(Qt.PointingHandCursor)
        buy_host_btn.clicked.connect(self.open_buy_host)
        tb.addWidget(buy_host_btn)

    def open_buy_host(self):
        """Open the host purchase Telegram channel"""
        url = "https://t.me/Core_Host"
        try:
            webbrowser.open(url)
            self.show_toast("Opening Core_Host in browser...", "info")
        except Exception as e:
            QMessageBox.warning(
                self,
                "Browser Error",
                f"Could not open the link automatically.\n\nPlease visit:\n{url}\n\nError: {str(e)}"
            )

    def build_empty_page(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setAlignment(Qt.AlignCenter)

        title = QLabel("Welcome to Argus SSH")
        title.setObjectName("heroTitle")
        desc = QLabel("Select a host from the sidebar or add a new one to begin.")
        desc.setObjectName("heroDesc")
        desc.setAlignment(Qt.AlignCenter)

        layout.addWidget(title)
        layout.addWidget(desc)
        return widget

    def apply_theme(self, settings: AppSettings):
        self.settings = settings
        self.setFont(QFont("Segoe UI", settings.font_size))
        self.remote_panel.set_settings(settings)

        qss = f"""
            QMainWindow, QWidget {{
                background: {settings.background_color};
                color: {settings.text_color};
                font-family: 'Segoe UI';
                font-size: {settings.font_size}pt;
            }}
            QDialog, QMessageBox {{
                background: {settings.background_color};
                color: {settings.text_color};
            }}
            #sidebar {{
                background: {settings.panel_color};
                border-right: 1px solid {settings.border_color};
            }}
            #brandLabel {{
                font-size: 18pt;
                font-weight: 700;
                color: {settings.text_color};
            }}
            #subtitleLabel, #statusLabel, #creditsLabel, #heroDesc, #pathLabel {{
                color: {settings.text_color};
                opacity: 0.9;
            }}
            #heroTitle {{
                font-size: 28pt;
                font-weight: 700;
                color: {settings.text_color};
            }}
            QLabel#sectionTitle {{
                font-size: 14pt;
                font-weight: 700;
                color: {settings.text_color};
            }}
            QPushButton {{
                background: {settings.panel_color};
                border: 1px solid {settings.border_color};
                padding: 9px 14px;
                border-radius: 8px;
                color: {settings.text_color};
            }}
            QPushButton:hover {{
                background: #2a2d35;
            }}
            QPushButton:pressed {{
                background: #111;
            }}
            QPushButton#primaryButton, QPushButton#connectButton {{
                background: {settings.accent_color};
                border: none;
                color: #000000;
                font-weight: bold;
            }}
            QPushButton#primaryButton:hover, QPushButton#connectButton:hover {{
                background: #d9b84c;
            }}
            QPushButton#pythonMenuButton {{
                background: #2e7d32;
                color: white;
                border: none;
                padding: 6px 12px;
            }}
            QPushButton#pythonMenuButton::menu-indicator {{
                image: none;
            }}
            QPushButton#pythonMenuButton:hover {{
                background: #388e3c;
            }}
            QMenu {{
                background-color: {settings.panel_color};
                color: {settings.text_color};
                border: 1px solid {settings.border_color};
            }}
            QMenu::item {{
                padding: 6px 20px 6px 20px;
            }}
            QMenu::item:selected {{
                background-color: {settings.accent_color};
                color: #000;
            }}
            QListWidget, QTableWidget, QPlainTextEdit, QLineEdit, QSpinBox {{
                background: {settings.panel_color};
                border: 1px solid {settings.border_color};
                border-radius: 8px;
                selection-background-color: {settings.accent_color};
                selection-color: #000;
                color: {settings.text_color};
                padding: 4px;
            }}
            QTableWidget::item:selected, QListWidget::item:selected {{
                background: {settings.accent_color};
                color: #000000;
            }}
            QHeaderView::section {{
                background: {settings.panel_color};
                padding: 8px;
                border: none;
                border-bottom: 1px solid {settings.border_color};
                color: {settings.text_color};
                font-weight: 600;
            }}
            QToolBar {{
                background: {settings.panel_color};
                border-bottom: 1px solid {settings.border_color};
                spacing: 8px;
                padding: 6px;
            }}
            QSplitter::handle {{
                background: {settings.border_color};
                width: 2px;
            }}
        """
        QApplication.instance().setStyleSheet(qss)

    def refresh_host_list(self):
        self.host_list.clear()
        for host in self.hosts:
            item = QListWidgetItem(f"{host.name}   •   {host.host}:{host.port}")
            item.setData(Qt.UserRole, host)
            self.host_list.addItem(item)

    def selected_host(self) -> Optional[HostEntry]:
        item = self.host_list.currentItem()
        if not item:
            return None
        return item.data(Qt.UserRole)

    def selected_index(self) -> Optional[int]:
        row = self.host_list.currentRow()
        if row < 0:
            return None
        return row

    def add_host(self):
        dlg = AddHostDialog(self)
        if dlg.exec_() == QDialog.Accepted:
            host = dlg.get_data()
            if not host.name or not host.host or not host.username:
                QMessageBox.warning(self, "Missing Information", "Please fill Name, Host/IP, and Username.")
                return
            self.hosts.append(host)
            HostStore.save(self.hosts)
            self.refresh_host_list()

    def edit_host(self):
        idx = self.selected_index()
        if idx is None:
            return
        dlg = AddHostDialog(self, self.hosts[idx])
        if dlg.exec_() == QDialog.Accepted:
            host = dlg.get_data()
            if not host.name or not host.host or not host.username:
                QMessageBox.warning(self, "Missing Information", "Please fill Name, Host/IP, and Username.")
                return
            self.hosts[idx] = host
            HostStore.save(self.hosts)
            self.refresh_host_list()

    def remove_host(self):
        idx = self.selected_index()
        if idx is None:
            return
        host = self.hosts[idx]
        if QMessageBox.question(self, "Remove Host", f"Remove server '{host.name}'?", QMessageBox.Yes | QMessageBox.No) != QMessageBox.Yes:
            return
        self.hosts.pop(idx)
        HostStore.save(self.hosts)
        self.refresh_host_list()
        self.stack.setCurrentWidget(self.empty_page)
        self.status_label.setText("No host selected.")

    def on_host_clicked(self, item: QListWidgetItem):
        host = item.data(Qt.UserRole)
        self.status_label.setText(f"Selected: {host.name}")

    def connect_selected(self):
        host = self.selected_host()
        if not host:
            self.show_toast("Please select a host from the list first.", "error")
            return
        
        self.status_label.setText(f"Connecting to {host.name} ...")
        QApplication.processEvents() 

        try:
            self.remote_panel.connect_host(host)
            self.stack.setCurrentWidget(self.remote_panel)
            self.status_label.setText(f"✅ Connected to: {host.name}")
        except Exception as e:
            self.status_label.setText(f"❌ Failed to connect: {host.name}")
            self.show_toast(str(e), "error")

    def disconnect_selected(self):
        if self.stack.currentWidget() == self.remote_panel:
            self.remote_panel.disconnect_host()
            self.stack.setCurrentWidget(self.empty_page)
            self.status_label.setText("Disconnected.")
            self.show_toast("Connection closed.", "info")

    def open_settings(self):
        dlg = SettingsDialog(self, self.settings)
        if dlg.exec_() == QDialog.Accepted:
            self.settings = dlg.get_settings()
            SettingsStore.save(self.settings)
            self.apply_theme(self.settings)
            self.remote_panel.set_settings(self.settings)
            QTimer.singleShot(0, lambda: self.show_toast("Settings saved successfully.", "success"))

    def show_about(self):
        QMessageBox.information(
            self,
            "About",
            f"{APP_NAME} v{APP_VERSION}\n\n"
            "Thank you for choosing my program. I hope you can manage your services well with this program and have a good time. If you have any problems, you can tell me using the communication channels provided in the program.",
        )

    def show_donate(self):
        dlg = DonateDialog(self)
        dlg.exec_()

    def closeEvent(self, event):
        try:
            self.remote_panel.disconnect_host()
        except Exception:
            pass
        HostStore.save(self.hosts)
        SettingsStore.save(self.settings)
        event.accept()


def main():
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setOrganizationName(APP_ORG)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()