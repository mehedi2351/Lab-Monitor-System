import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PyQt6.QtCore import QObject, Qt, QTimer, pyqtSignal
from PyQt6.QtWidgets import (
    QApplication,
    QAbstractItemView,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QStackedWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from config import *
from server_backend import LabServer


class ServerSignals(QObject):
    event = pyqtSignal(str, dict)


class ServerWindow(QMainWindow):
    def __init__(self, admin_info=None):
        super().__init__()
        self.admin_info = admin_info or {"full_name": "Admin"}
        self.server = LabServer()
        self.db = self.server.db
        self.signals = ServerSignals()
        self.signals.event.connect(self._on_server_event)
        self.server.set_callback(lambda ev, data: self.signals.event.emit(ev, data or {}))

        self.setWindowTitle("Lab Monitor Pro - Admin")
        self.setMinimumSize(1120, 720)
        self._apply_global_style()
        self._build_ui()

        self.server.start()

        self.refresh_timer = QTimer(self)
        self.refresh_timer.timeout.connect(self._refresh_all)
        self.refresh_timer.start(2000)
        self._refresh_all()

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QHBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        self.sidebar = QFrame()
        self.sidebar.setFixedWidth(220)
        self.sidebar.setObjectName("Sidebar")
        sidebar_layout = QVBoxLayout(self.sidebar)
        sidebar_layout.setContentsMargins(12, 18, 12, 14)
        sidebar_layout.setSpacing(8)

        logo = QLabel("LAB MONITOR")
        logo.setStyleSheet("font-size:18px;font-weight:bold;color:#3498DB;margin:14px 8px;")
        sidebar_layout.addWidget(logo)

        self.menu_buttons = [
            self._create_menu_btn("Dashboard"),
            self._create_menu_btn("Power Control"),
            self._create_menu_btn("Messages"),
            self._create_menu_btn("Logs"),
            self._create_menu_btn("Pendrive Blocker"),
            self._create_menu_btn("Browser Blocker"),
        ]
        for idx, btn in enumerate(self.menu_buttons):
            btn.clicked.connect(lambda checked=False, i=idx: self._show_page(i))
            sidebar_layout.addWidget(btn)
        sidebar_layout.addStretch()

        logout = QPushButton("Logout")
        logout.setObjectName("LogoutBtn")
        logout.clicked.connect(self.close)
        sidebar_layout.addWidget(logout)

        self.pages = QStackedWidget() # eita main page er jnno use hobe ja sudhu rigt side er jnis pati chneg kre 
        self.page_dash = self._build_dashboard()
        self.page_power = self._build_power_control()
        self.page_messages = self._build_messages_page()
        self.page_logs = self._build_logs_page()

        for page in (self.page_dash, self.page_power, self.page_messages, self.page_logs):
            self.pages.addWidget(page)

        main_layout.addWidget(self.sidebar)
        main_layout.addWidget(self.pages)
        self._show_page(0)

    def _create_menu_btn(self, text):
        btn = QPushButton(text)
        btn.setCheckable(True)
        btn.setFixedHeight(48)
        return btn

    def _show_page(self, index):
        self.pages.setCurrentIndex(index)
        for i, btn in enumerate(self.menu_buttons):
            btn.setChecked(i == index)
        self._refresh_all()
    
    #eikhne amraa acta deshborad toiri krtesi 
    def _build_dashboard(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        title = QLabel(f"Overview - {self.admin_info.get('full_name', 'Admin')}")
        title.setObjectName("PageTitle")
        layout.addWidget(title)

        grid = QGridLayout()
        grid.setSpacing(14)
        self.stat_total = StatCard("Total PCs", "0", "#2980B9")
        self.stat_online = StatCard("Online", "0", "#27AE60")
        self.stat_offline = StatCard("Offline", "0", "#C0392B")
        grid.addWidget(self.stat_total, 0, 0)
        grid.addWidget(self.stat_online, 0, 1)
        grid.addWidget(self.stat_offline, 0, 2)
        layout.addLayout(grid)

        self.dash_table = QTableWidget(0, 5)
        self.dash_table.setHorizontalHeaderLabels(["PC Name", "IP", "Status", "CPU", "RAM"])
        self.dash_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.dash_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        layout.addWidget(self.dash_table)
        return page
# power buton er jnno page toiri krtesi
    def _build_power_control(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(14)

        title = QLabel("Remote Power Management")
        title.setObjectName("PageTitle")
        layout.addWidget(title)

        self.power_table = QTableWidget(0, 6)
        self.power_table.setHorizontalHeaderLabels(["PC Name", "IP", "Status", "CPU", "RAM", "Action"])
        self.power_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.power_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        layout.addWidget(self.power_table)

        refresh = QPushButton("Refresh")
        refresh.clicked.connect(self._refresh_all)
        layout.addWidget(refresh)
        return page

    def _build_messages_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(14)

        title = QLabel("Messages")
        title.setObjectName("PageTitle")
        layout.addWidget(title)

        send_box = QGroupBox("Broadcast Message")
        send_layout = QHBoxLayout(send_box)
        self.broadcast_input = QLineEdit()
        self.broadcast_input.setPlaceholderText("Type message for all connected PCs")
        self.broadcast_input.returnPressed.connect(self._send_broadcast)
        send_btn = QPushButton("Send to All")
        send_btn.clicked.connect(self._send_broadcast)
        send_layout.addWidget(self.broadcast_input)
        send_layout.addWidget(send_btn)
        layout.addWidget(send_box)

        self.messages_table = QTableWidget(0, 4)
        self.messages_table.setHorizontalHeaderLabels(["Time", "Sender", "Receiver", "Message"])
        self.messages_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.messages_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        layout.addWidget(self.messages_table)
        return page
# log button
    def _build_logs_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(14)

        title = QLabel("Activity Logs")
        title.setObjectName("PageTitle")
        layout.addWidget(title)

        self.logs_table = QTableWidget(0, 3)
        self.logs_table.setHorizontalHeaderLabels(["Time", "PC Name", "Action"])
        self.logs_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.logs_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        layout.addWidget(self.logs_table)
        return page

    def _refresh_all(self):
        rows = self.db.all_clients()
        self._refresh_client_tables(rows)
        self._refresh_messages()
        self._refresh_logs()

    def _refresh_client_tables(self, rows):
        connected = set(self.server.connected_names())
        total = len(rows)
        online = 0

        dash_rows = []
        for row in rows:
            name = row.get("pc_name") or "Unknown"
            status = "online" if name in connected else (row.get("status") or "offline").lower()
            if status == "online":
                online += 1
            dash_rows.append((row, status))

        self.stat_total.update_value(str(total))
        self.stat_online.update_value(str(online))
        self.stat_offline.update_value(str(max(total - online, 0)))

        self._fill_client_table(self.dash_table, dash_rows, include_action=False)
        self._fill_client_table(self.power_table, dash_rows, include_action=True)

    def _fill_client_table(self, table, rows, include_action):
        table.setRowCount(0)
        connected = set(self.server.connected_names())
        for row_data, status in rows:
            name = row_data.get("pc_name") or "Unknown"
            row = table.rowCount()
            table.insertRow(row)
            values = [
                name,
                row_data.get("ip") or "",
                status.title(),
                f"{self._as_float(row_data.get('cpu_usage')):.1f}%",
                f"{self._as_float(row_data.get('ram_usage')):.1f}%",
            ]
            for col, value in enumerate(values):
                item = QTableWidgetItem(value)
                if col == 2:
                    item.setForeground(Qt.GlobalColor.green if status == "online" else Qt.GlobalColor.red)
                table.setItem(row, col, item)

            if include_action:
                btn = QPushButton("Shutdown")
                btn.setObjectName("DangerBtn")
                btn.setEnabled(name in connected and status == "online")
                btn.clicked.connect(lambda checked=False, pc=name: self._handle_shutdown(pc))
                table.setCellWidget(row, 5, btn)

    def _refresh_messages(self):
        if not hasattr(self, "messages_table"):
            return
        rows = self.db.all_messages(limit=100)
        self.messages_table.setRowCount(0)
        for data in rows:
            row = self.messages_table.rowCount()
            self.messages_table.insertRow(row)
            values = [
                self._fmt_time(data.get("time")),
                data.get("sender") or "",
                data.get("receiver") or "",
                data.get("message") or "",
            ]
            for col, value in enumerate(values):
                self.messages_table.setItem(row, col, QTableWidgetItem(str(value)))

    def _refresh_logs(self):
        if not hasattr(self, "logs_table"):
            return
        rows = self.db.all_logs(limit=200)
        self.logs_table.setRowCount(0)
        for data in rows:
            row = self.logs_table.rowCount()
            self.logs_table.insertRow(row)
            values = [
                self._fmt_time(data.get("time")),
                data.get("pc_name") or "",
                data.get("action") or "",
            ]
            for col, value in enumerate(values):
                self.logs_table.setItem(row, col, QTableWidgetItem(str(value)))

    def _send_broadcast(self):
        text = self.broadcast_input.text().strip()
        if not text:
            return
        self.server.send_all(text)
        self.broadcast_input.clear()
        self._refresh_messages()

    def _handle_shutdown(self, name):
        reply = QMessageBox.question(
            self,
            "Confirm Shutdown",
            f"Really shutdown {name}?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        if self.server.send_shutdown(name):
            QMessageBox.information(self, "Shutdown Sent", f"Shutdown command sent to {name}.")
        else:
            QMessageBox.warning(self, "Not Connected", f"{name} is not connected right now.")
        self._refresh_all()

    def _on_server_event(self, event, data):
        if event == "started":
            self.statusBar().showMessage(f"Server listening on port {data.get('port', SERVER_PORT)}")
        elif event == "error":
            msg = data.get("msg", "Unknown server error")
            self.statusBar().showMessage(msg)
            QMessageBox.warning(self, "Server Error", msg)
        elif event == "connected":
            self.statusBar().showMessage(f"{data.get('pc_name', 'PC')} connected")
            self._refresh_all()
        elif event == "disconnected":
            self.statusBar().showMessage(f"{data.get('pc_name', 'PC')} disconnected")
            self._refresh_all()
        elif event == "shutdown_sent":
            self.statusBar().showMessage(f"Shutdown sent to {data.get('pc_name', 'PC')}")
            self._refresh_logs()
        elif event in {"status", "msg_in", "msg_sent"}:
            self._refresh_all()

    def _apply_global_style(self):
        self.setStyleSheet(
            """
            QMainWindow, QWidget { background-color:#0D1B2A; color:#ECF0F1; }
            #Sidebar { background-color:#1B263B; border-right:1px solid #3498DB; }
            QPushButton {
                color:white; background:#2C3E50; border:none; border-radius:5px;
                padding:8px 12px; font-size:14px; text-align:left;
            }
            QPushButton:hover { background-color:#415A77; }
            QPushButton:checked { background-color:#3498DB; font-weight:bold; }
            QPushButton:disabled { background-color:#263445; color:#7F8C8D; }
            QPushButton#DangerBtn { background-color:#C0392B; text-align:center; }
            QPushButton#DangerBtn:hover { background-color:#E74C3C; }
            QLabel { color:#ECF0F1; font-size:14px; }
            QLabel#PageTitle { font-size:20px; font-weight:bold; }
            #LogoutBtn { background-color:#C0392B; text-align:center; margin-top:10px; }
            QTableWidget {
                background:#162235; color:#ECF0F1; border:1px solid #2C3E50;
                gridline-color:#2C3E50; selection-background-color:#34495E;
            }
            QHeaderView::section {
                background:#1B263B; color:#ECF0F1; padding:7px;
                border:1px solid #2C3E50; font-weight:bold;
            }
            QLineEdit {
                background:#162235; color:#ECF0F1; border:1px solid #2C3E50;
                border-radius:5px; padding:8px;
            }
            QGroupBox {
                border:1px solid #2C3E50; border-radius:7px; margin-top:8px;
                padding:10px; color:#BDC3C7; font-weight:bold;
            }
            QStatusBar { background:#0D1B2A; color:#BDC3C7; }
            """
        )

    @staticmethod
    def _as_float(value):
        try:
            return float(value or 0)
        except (TypeError, ValueError):
            return 0.0

    @staticmethod
    def _fmt_time(value):
        if hasattr(value, "strftime"):
            return value.strftime("%Y-%m-%d %H:%M:%S")
        return "" if value is None else str(value)

    def closeEvent(self, event):
        self.refresh_timer.stop()
        self.server.stop()
        event.accept()


class StatCard(QFrame):
    def __init__(self, title, value, color):
        super().__init__()
        self.setStyleSheet(f"QFrame{{background-color:{color};border-radius:8px;min-height:100px;}}")
        layout = QVBoxLayout(self)
        self.value_label = QLabel(value)
        self.value_label.setStyleSheet("font-size:30px;font-weight:bold;")
        self.value_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title_label = QLabel(title)
        title_label.setStyleSheet("font-size:13px;")
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.value_label)
        layout.addWidget(title_label)

    def update_value(self, value):
        self.value_label.setText(str(value))


if __name__ == "__main__":
    app = QApplication(sys.argv)
    win = ServerWindow()
    win.show()
    sys.exit(app.exec())
