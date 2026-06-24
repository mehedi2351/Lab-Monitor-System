"""
==============================================================
  File: client/client_app.py
  Purpose: PyQt6 GUI for the Student PC Agent
  Run this on EVERY CLIENT PC in the lab
==============================================================

FIXES IN THIS VERSION
─────────────────────
  - "Connecting…" spinner shown while background thread connects
  - Connect button disabled during the attempt (no double-click)
  - Auto-connect waits 1.5 s so user can change the IP first
  - All GUI updates come through pyqtSignal (thread-safe)
  - "connecting" event greys out the button + shows spinner text
"""

import sys, os, platform
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QTextEdit, QLineEdit, QGroupBox,
    QProgressBar, QFrame, QMessageBox
)
from PyQt6.QtCore  import Qt, QTimer, pyqtSignal, QObject
from PyQt6.QtGui   import QFont
from datetime      import datetime
import psutil

from client_backend import LabClient
from config import *


# ── thread-safe signal bridge ───────────────────────────────
class ClientSignals(QObject):
    """
    PyQt6 rule: never update the GUI from a background thread.
    We emit a signal from the thread → Qt delivers it safely
    to the main (GUI) thread.
    """
    event = pyqtSignal(str, dict)


# ══════════════════════════════════════════════════════════
#  METRIC BAR WIDGET
# ══════════════════════════════════════════════════════════
class MetricBar(QFrame):
    def __init__(self, label, color="#3498DB"):
        super().__init__()
        self.setStyleSheet("QFrame{background:#1E2D3D; border-radius:8px; padding:4px;}")
        lay = QVBoxLayout(self); lay.setSpacing(4)

        top = QHBoxLayout()
        self.name_lbl = QLabel(label)
        self.name_lbl.setStyleSheet("color:#BDC3C7; font-size:11px; font-weight:bold;")
        self.val_lbl  = QLabel("— %")
        self.val_lbl.setStyleSheet(f"color:{color}; font-size:14px; font-weight:bold;")
        top.addWidget(self.name_lbl); top.addStretch(); top.addWidget(self.val_lbl)

        self.bar = QProgressBar()
        self.bar.setRange(0, 100); self.bar.setTextVisible(False)
        self.bar.setFixedHeight(10)
        self.bar.setStyleSheet(f"""
            QProgressBar       {{ background:#2C3E50; border-radius:5px; }}
            QProgressBar::chunk{{ background:{color};  border-radius:5px; }}
        """)
        lay.addLayout(top); lay.addWidget(self.bar)

    def set_value(self, pct):
        self.bar.setValue(int(pct))
        self.val_lbl.setText(f"{pct:.1f} %")


# ══════════════════════════════════════════════════════════
#  MAIN WINDOW
# ══════════════════════════════════════════════════════════
class ClientWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.client  = LabClient()
        self.signals = ClientSignals()
        self.signals.event.connect(self._on_event)

        # Wire backend → signal (this lambda runs in background thread,
        # but emit() is thread-safe in PyQt6)
        self.client.set_callback(
            lambda ev, data: self.signals.event.emit(ev, data)
        )

        self._setup_ui()
        self._apply_theme()

        # Warm up psutil so first reading isn't 0
        psutil.cpu_percent(interval=None)

        # Live gauge timer (updates every 2 seconds, local only)
        self.gauge_timer = QTimer()
        self.gauge_timer.timeout.connect(self._update_gauges)
        self.gauge_timer.start(2000)

        # Auto-connect after 1.5 s — gives user time to change IP
        QTimer.singleShot(1500, self._auto_connect)

    # ── UI construction ─────────────────────────────────────
    def _setup_ui(self):
        self.setWindowTitle(CLIENT_TITLE + f"  —  v{VERSION}")
        self.setMinimumSize(540, 620)

        central = QWidget(); self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setSpacing(12); root.setContentsMargins(16, 16, 16, 16)

        # ── header row ──
        hdr = QHBoxLayout()
        icon = QLabel("🖥")
        icon.setFont(QFont("Segoe UI", 22))
        icon.setStyleSheet("color:#3498DB;")

        info_col = QVBoxLayout()
        self.lbl_pc = QLabel(self.client.pc_name)
        self.lbl_pc.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
        self.lbl_pc.setStyleSheet("color:#ECF0F1;")
        self.lbl_os = QLabel(
            f"{platform.system()} {platform.release()}  |  "
            f"Python {platform.python_version()}"
        )
        self.lbl_os.setStyleSheet("color:#7F8C8D; font-size:10px;")
        info_col.addWidget(self.lbl_pc); info_col.addWidget(self.lbl_os)

        hdr.addWidget(icon); hdr.addLayout(info_col); hdr.addStretch()
        root.addLayout(hdr)

        # ── status badge ──
        self.badge = QLabel("⬤  Disconnected")
        self.badge.setStyleSheet(
            f"color:{COLOR_OFFLINE}; font-weight:bold; font-size:13px;")
        root.addWidget(self.badge)

        # ── connection box ──
        conn_box = QGroupBox("Server Connection")
        conn_lay = QHBoxLayout(conn_box)

        conn_lay.addWidget(QLabel("Server IP:"))

        self.ip_input = QLineEdit(SERVER_IP)
        self.ip_input.setPlaceholderText("e.g. 192.168.137.1")
        conn_lay.addWidget(self.ip_input)

        self.btn_connect = QPushButton("🔌  Connect")
        self.btn_connect.setFixedWidth(140)
        self.btn_connect.clicked.connect(self._toggle_connect)
        self._style_btn_connect()
        conn_lay.addWidget(self.btn_connect)

        root.addWidget(conn_box)

        # ── metrics ──
        metrics_box = QGroupBox("System Metrics  (sent to server every 5 s)")
        m_lay = QVBoxLayout(metrics_box)
        self.cpu_bar = MetricBar("CPU Usage", "#E74C3C")
        self.ram_bar = MetricBar("RAM Usage", "#F39C12")
        m_lay.addWidget(self.cpu_bar); m_lay.addWidget(self.ram_bar)
        root.addWidget(metrics_box)

        # ── messages ──
        msg_box = QGroupBox("Messages")
        msg_lay = QVBoxLayout(msg_box)

        self.msg_log = QTextEdit()
        self.msg_log.setReadOnly(True)
        self.msg_log.setStyleSheet(
            "font-family:Consolas,monospace; font-size:11px;")
        self.msg_log.setMinimumHeight(160)

        send_row = QHBoxLayout()
        self.msg_input = QLineEdit()
        self.msg_input.setPlaceholderText("Type a message to send to the server…")
        self.msg_input.returnPressed.connect(self._send_msg)

        self.btn_send = QPushButton("Send  ➤")
        self.btn_send.setFixedWidth(90)
        self.btn_send.clicked.connect(self._send_msg)
        self.btn_send.setStyleSheet(
            "background:#2980B9; color:white; padding:6px 12px;"
            "border-radius:5px; font-weight:bold;")

        send_row.addWidget(self.msg_input); send_row.addWidget(self.btn_send)
        msg_lay.addWidget(self.msg_log); msg_lay.addLayout(send_row)
        root.addWidget(msg_box)

        # ── bottom status line ──
        self.status_lbl = QLabel("Waiting to connect…")
        self.status_lbl.setStyleSheet("color:#7F8C8D; font-size:10px;")
        root.addWidget(self.status_lbl)

    def _apply_theme(self):
        self.setStyleSheet("""
            QMainWindow, QWidget {
                background: #1A2535; color: #ECF0F1;
            }
            QGroupBox {
                border: 1px solid #2C3E50; border-radius: 8px;
                margin-top: 8px; padding: 10px;
                color: #BDC3C7; font-weight: bold;
            }
            QGroupBox::title {
                subcontrol-origin: margin; left: 10px; padding: 0 4px;
            }
            QPushButton {
                background: #2C3E50; color: #ECF0F1;
                border-radius: 5px; padding: 6px 12px;
            }
            QPushButton:hover  { background: #34495E; }
            QPushButton:disabled { background: #1A2535; color: #4A5568; }
            QLineEdit {
                background: #2C3E50; color: #ECF0F1;
                border: 1px solid #3D5166; border-radius: 4px; padding: 5px;
            }
            QTextEdit {
                background: #1E2D3D; color: #ECF0F1;
                border: 1px solid #2C3E50; border-radius: 4px;
            }
        """)

    # ── button styling helpers ──────────────────────────────
    def _style_btn_connect(self):
        self.btn_connect.setStyleSheet(
            "background:#27AE60; color:white; padding:6px 16px;"
            "border-radius:5px; font-weight:bold;")

    def _style_btn_connecting(self):
        self.btn_connect.setStyleSheet(
            "background:#7F8C8D; color:white; padding:6px 16px;"
            "border-radius:5px; font-weight:bold;")

    def _style_btn_disconnect(self):
        self.btn_connect.setStyleSheet(
            "background:#C0392B; color:white; padding:6px 16px;"
            "border-radius:5px; font-weight:bold;")

    # ── actions ─────────────────────────────────────────────
    def _auto_connect(self):
        """Auto-connect on startup (only if user hasn't clicked anything)."""
        if not self.client.running and not self.client._connecting:
            self._start_connect()

    def _toggle_connect(self):
        if self.client.running:
            self.client.disconnect()
        elif self.client._connecting:
            # Cancel: just reset state; the background thread will time out
            self.client._connecting = False
            self._reset_connect_ui()
            self._log("Connection attempt cancelled.", COLOR_WARNING)
        else:
            self._start_connect()

    def _start_connect(self):
        ip = self.ip_input.text().strip() or SERVER_IP
        self._log(f"Connecting to {ip}:{SERVER_PORT} …  (timeout 8 s)", "#BDC3C7")

        # Disable controls while connecting
        self.btn_connect.setText("⏳  Connecting…")
        self._style_btn_connecting()
        self.btn_connect.setEnabled(True)   # keep enabled so user can cancel
        self.ip_input.setEnabled(False)

        # This returns immediately — actual connect happens in background thread
        self.client.connect(ip, SERVER_PORT)

    def _reset_connect_ui(self):
        self.ip_input.setEnabled(True)
        self.btn_connect.setText("🔌  Connect")
        self._style_btn_connect()
        self.badge.setText("⬤  Disconnected")
        self.badge.setStyleSheet(
            f"color:{COLOR_OFFLINE}; font-weight:bold; font-size:13px;")

    def _send_msg(self):
        text = self.msg_input.text().strip()
        if not text:
            return
        if not self.client.running:
            QMessageBox.warning(self, "Not Connected",
                "You are not connected to the server.\n"
                "Please connect first.")
            return
        self.client.send_message(text)
        self.msg_input.clear()

    def _update_gauges(self):
        """Updates the local CPU/RAM display every 2 seconds."""
        cpu = psutil.cpu_percent(interval=None)
        ram = psutil.virtual_memory().percent
        self.cpu_bar.set_value(cpu)
        self.ram_bar.set_value(ram)

    def _log(self, text, color="#BDC3C7"):
        t = datetime.now().strftime("%H:%M:%S")
        self.msg_log.append(
            f'<span style="color:{color};">[{t}]  {text}</span>')
        self.status_lbl.setText(text[:80])

    # ── event handler (called from pyqtSignal — safe on GUI thread) ──
    def _on_event(self, event, data):
        if event == "connecting":
            pass  # UI already updated in _start_connect

        elif event == "connected":
            self.ip_input.setEnabled(False)
            self.btn_connect.setText("⏹  Disconnect")
            self._style_btn_disconnect()
            self.badge.setText("⬤  Connected")
            self.badge.setStyleSheet(
                f"color:{COLOR_ONLINE}; font-weight:bold; font-size:13px;")
            self._log(
                f"✅  Connected to server  {data.get('server')}:{data.get('port')}",
                COLOR_ONLINE)

        elif event == "disconnected":
            self._reset_connect_ui()
            self._log("Disconnected from server.", COLOR_OFFLINE)

        elif event == "ack":
            self._log(f"Server says: {data.get('message','')}", COLOR_ACCENT)

        elif event == "msg_in":
            self._log(
                f"📨  {data.get('from','SERVER')}: {data.get('message','')}",
                COLOR_WARNING)

        elif event == "msg_sent":
            self._log(f"You  →  Server: {data.get('text','')}", "#9B59B6")

        elif event == "status_sent":
            self.status_lbl.setText(
                f"Status sent  —  CPU {data.get('cpu',0):.1f}%  "
                f"RAM {data.get('ram',0):.1f}%")

        elif event == "shutdown_requested":
            delay = data.get("delay", REMOTE_SHUTDOWN_DELAY_SECONDS)
            self._log(
                f"Remote shutdown requested by admin. Shutting down in {delay}s.",
                COLOR_WARNING)
            QMessageBox.warning(
                self,
                "Remote Shutdown",
                f"Admin requested shutdown for this PC.\nThis computer will shut down in {delay} seconds.")

        elif event == "shutdown_started":
            delay = data.get("delay", REMOTE_SHUTDOWN_DELAY_SECONDS)
            self._log(f"Shutdown command started ({delay}s delay).", COLOR_OFFLINE)

        elif event == "error":
            # Re-enable UI so user can correct the IP and retry
            self._reset_connect_ui()
            self._log(f"❌  {data.get('msg','Connection failed')}", COLOR_OFFLINE)
            QMessageBox.warning(
                self, "Connection Failed",
                data.get("msg", "Could not connect to server."))

    def closeEvent(self, e):
        self.client.disconnect()
        e.accept()


# ── entry point ──────────────────────────────────────────────
def main():
    app = QApplication(sys.argv)
    app.setFont(QFont("Segoe UI", 10))
    win = ClientWindow()
    win.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
