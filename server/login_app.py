"""
==============================================================
  File: server/login_app.py
  Purpose: Modern Login + Registration window for Admin
  THIS IS THE ENTRY POINT — run this instead of server_app.py
==============================================================

  python server/login_app.py

  Flow:
    1. Login window opens
    2. Admin enters username + password  (or registers first time)
    3. On success → ServerWindow opens, LoginWindow closes
    4. Client PCs run client_app.py separately (no login needed)
"""

import sys, os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QFrame, QStackedWidget,
    QGraphicsDropShadowEffect, QMessageBox
)
from PyQt6.QtCore  import Qt, QPropertyAnimation, QEasingCurve, QRect, QTimer, pyqtSignal
from PyQt6.QtGui   import QFont, QColor, QLinearGradient, QPainter, QPalette, QIcon

from auth       import register_admin, login_admin, admin_count
from config     import VERSION


# ══════════════════════════════════════════════════════════
#  HELPER WIDGETS
# ══════════════════════════════════════════════════════════

class ModernInput(QFrame):
    """
    A styled input field with a floating icon label on the left.
    Glows blue when focused.
    """
    def __init__(self, placeholder, icon="", password=False):
        super().__init__()
        self.setFixedHeight(52)
        self.setStyleSheet("""
            QFrame {
                background: rgba(255,255,255,0.07);
                border: 1.5px solid rgba(255,255,255,0.15);
                border-radius: 12px;
            }
            QFrame:hover {
                border: 1.5px solid rgba(100,180,255,0.4);
            }
        """)
        lay = QHBoxLayout(self); lay.setContentsMargins(14,0,14,0); lay.setSpacing(10)

        if icon:
            ico = QLabel(icon)
            ico.setStyleSheet("color:rgba(255,255,255,0.5); font-size:16px; background:transparent; border:none;")
            lay.addWidget(ico)

        self.field = QLineEdit()
        self.field.setPlaceholderText(placeholder)
        if password:
            self.field.setEchoMode(QLineEdit.EchoMode.Password)
        self.field.setStyleSheet("""
            QLineEdit {
                background: transparent;
                border: none;
                color: white;
                font-size: 13px;
                font-family: 'Segoe UI';
            }
            QLineEdit::placeholder { color: rgba(255,255,255,0.35); }
        """)
        lay.addWidget(self.field)

        if password:
            self.toggle_btn = QPushButton("👁")
            self.toggle_btn.setFixedSize(28, 28)
            self.toggle_btn.setStyleSheet(
                "QPushButton{background:transparent;border:none;"
                "color:rgba(255,255,255,0.4);font-size:14px;}"
                "QPushButton:hover{color:white;}")
            self.toggle_btn.clicked.connect(self._toggle_visibility)
            lay.addWidget(self.toggle_btn)
            self._hidden = True

    def _toggle_visibility(self):
        self._hidden = not self._hidden
        self.field.setEchoMode(
            QLineEdit.EchoMode.Password if self._hidden
            else QLineEdit.EchoMode.Normal)
        self.toggle_btn.setText("👁" if self._hidden else "🙈")

    def text(self):    return self.field.text()
    def clear(self):   self.field.clear()
    def setFocus(self): self.field.setFocus()

    def returnPressed_connect(self, fn):
        self.field.returnPressed.connect(fn)


class GradientFrame(QFrame):
    """Dark gradient background panel."""
    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        grad = QLinearGradient(0, 0, self.width(), self.height())
        grad.setColorAt(0.0, QColor("#0F1923"))
        grad.setColorAt(0.5, QColor("#1A2535"))
        grad.setColorAt(1.0, QColor("#0D1B2A"))
        p.fillRect(self.rect(), grad)


class ActionButton(QPushButton):
    """Glowing primary action button."""
    def __init__(self, text, color_start="#4A90E2", color_end="#357ABD"):
        super().__init__(text)
        self.setFixedHeight(48)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._c1 = color_start; self._c2 = color_end
        self._apply_style(False)

    def _apply_style(self, hovered):
        opacity = "1.0" if hovered else "0.92"
        self.setStyleSheet(f"""
            QPushButton {{
                background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
                    stop:0 {self._c1}, stop:1 {self._c2});
                color: white;
                border: none;
                border-radius: 12px;
                font-size: 14px;
                font-weight: bold;
                font-family: 'Segoe UI';
                opacity: {opacity};
            }}
            QPushButton:hover {{
                background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
                    stop:0 #5BA3F5, stop:1 #4A90E2);
            }}
            QPushButton:pressed {{
                background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
                    stop:0 #2E6DB4, stop:1 #245A9A);
            }}
        """)


class StatusLabel(QLabel):
    """Inline error/success message under the form."""
    def show_error(self, msg):
        self.setText(f"⚠  {msg}")
        self.setStyleSheet(
            "color:#FF6B6B; font-size:11px; font-family:'Segoe UI';"
            "background:rgba(255,80,80,0.1); border-radius:6px; padding:6px 10px;")
        self.show()

    def show_success(self, msg):
        self.setText(f"✓  {msg}")
        self.setStyleSheet(
            "color:#51CF66; font-size:11px; font-family:'Segoe UI';"
            "background:rgba(80,200,80,0.1); border-radius:6px; padding:6px 10px;")
        self.show()


# ══════════════════════════════════════════════════════════
#  LOGIN PANEL
# ══════════════════════════════════════════════════════════
class LoginPanel(QWidget):
    switch_to_register = pyqtSignal()
    login_success      = pyqtSignal(dict)   # emits admin info dict

    def __init__(self):
        super().__init__()
        lay = QVBoxLayout(self); lay.setSpacing(14); lay.setContentsMargins(0,0,0,0)

        # Title
        title = QLabel("Welcome Back")
        title.setFont(QFont("Segoe UI", 22, QFont.Weight.Bold))
        title.setStyleSheet("color:white;")
        subtitle = QLabel("Sign in to Admin Dashboard")
        subtitle.setStyleSheet("color:rgba(255,255,255,0.45); font-size:12px;")
        lay.addWidget(title); lay.addWidget(subtitle)
        lay.addSpacing(10)

        # Fields
        self.inp_user = ModernInput("Username", "👤")
        self.inp_pass = ModernInput("Password", "🔒", password=True)
        lay.addWidget(self.inp_user); lay.addWidget(self.inp_pass)

        # Status
        self.status = StatusLabel(); self.status.hide()
        lay.addWidget(self.status)

        # Login button
        self.btn_login = ActionButton("Sign In")
        self.btn_login.clicked.connect(self._do_login)
        self.inp_pass.returnPressed_connect(self._do_login)
        self.inp_user.returnPressed_connect(self._do_login)
        lay.addWidget(self.btn_login)
        lay.addSpacing(6)

        # Switch to register
        bottom = QHBoxLayout()
        lbl = QLabel("Don't have an account?")
        lbl.setStyleSheet("color:rgba(255,255,255,0.4); font-size:11px;")
        btn_reg = QPushButton("Register here")
        btn_reg.setStyleSheet(
            "QPushButton{background:transparent;border:none;"
            "color:#4A90E2;font-size:11px;font-weight:bold;}"
            "QPushButton:hover{color:#5BA3F5;}")
        btn_reg.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_reg.clicked.connect(self.switch_to_register)
        bottom.addWidget(lbl); bottom.addWidget(btn_reg); bottom.addStretch()
        lay.addLayout(bottom)
        lay.addStretch()

    def _do_login(self):
        self.status.hide()
        self.btn_login.setText("Signing in…")
        self.btn_login.setEnabled(False)
        QTimer.singleShot(80, self._perform_login)

    def _perform_login(self):
        ok, msg, admin = login_admin(self.inp_user.text(), self.inp_pass.text())
        self.btn_login.setText("Sign In"); self.btn_login.setEnabled(True)
        if ok:
            self.status.show_success(msg)
            QTimer.singleShot(400, lambda: self.login_success.emit(admin))
        else:
            self.status.show_error(msg)
            self.inp_pass.clear()


# ══════════════════════════════════════════════════════════
#  REGISTER PANEL
# ══════════════════════════════════════════════════════════
class RegisterPanel(QWidget):
    switch_to_login   = pyqtSignal()
    register_success  = pyqtSignal()

    def __init__(self):
        super().__init__()
        lay = QVBoxLayout(self); lay.setSpacing(12); lay.setContentsMargins(0,0,0,0)

        title = QLabel("Create Account")
        title.setFont(QFont("Segoe UI", 22, QFont.Weight.Bold))
        title.setStyleSheet("color:white;")
        subtitle = QLabel("Register a new admin account")
        subtitle.setStyleSheet("color:rgba(255,255,255,0.45); font-size:12px;")
        lay.addWidget(title); lay.addWidget(subtitle)
        lay.addSpacing(8)

        self.inp_name = ModernInput("Full Name", "🧑")
        self.inp_user = ModernInput("Username", "👤")
        self.inp_pass = ModernInput("Password", "🔒", password=True)
        self.inp_conf = ModernInput("Confirm Password", "🔒", password=True)
        for w in (self.inp_name, self.inp_user, self.inp_pass, self.inp_conf):
            lay.addWidget(w)

        self.status = StatusLabel(); self.status.hide()
        lay.addWidget(self.status)

        self.btn_reg = ActionButton("Create Account", "#27AE60", "#1E8449")
        self.btn_reg.clicked.connect(self._do_register)
        self.inp_conf.returnPressed_connect(self._do_register)
        lay.addWidget(self.btn_reg)
        lay.addSpacing(4)

        bottom = QHBoxLayout()
        lbl = QLabel("Already have an account?")
        lbl.setStyleSheet("color:rgba(255,255,255,0.4); font-size:11px;")
        btn_login = QPushButton("Sign in")
        btn_login.setStyleSheet(
            "QPushButton{background:transparent;border:none;"
            "color:#4A90E2;font-size:11px;font-weight:bold;}"
            "QPushButton:hover{color:#5BA3F5;}")
        btn_login.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_login.clicked.connect(self.switch_to_login)
        bottom.addWidget(lbl); bottom.addWidget(btn_login); bottom.addStretch()
        lay.addLayout(bottom)
        lay.addStretch()

    def _do_register(self):
        self.status.hide()
        if self.inp_pass.text() != self.inp_conf.text():
            self.status.show_error("Passwords do not match.")
            self.inp_conf.clear(); return

        self.btn_reg.setText("Creating…"); self.btn_reg.setEnabled(False)
        QTimer.singleShot(80, self._perform_register)

    def _perform_register(self):
        ok, msg = register_admin(
            self.inp_name.text(), self.inp_user.text(), self.inp_pass.text())
        self.btn_reg.setText("Create Account"); self.btn_reg.setEnabled(True)
        if ok:
            self.status.show_success(msg)
            for f in (self.inp_name, self.inp_user, self.inp_pass, self.inp_conf):
                f.clear()
            QTimer.singleShot(1200, self.register_success.emit)
        else:
            self.status.show_error(msg)


# ══════════════════════════════════════════════════════════
#  MAIN LOGIN WINDOW
# ══════════════════════════════════════════════════════════
class LoginWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"Lab Monitor  —  Admin Login  v{VERSION}")
        self.setFixedSize(820, 520)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        self._drag_pos = None
        self._build_ui()

    def _build_ui(self):
        root = QHBoxLayout(self); root.setContentsMargins(0,0,0,0); root.setSpacing(0)

        # ── LEFT: decorative branding panel ─────────────────
        left = GradientFrame()
        left.setFixedWidth(320)
        left_lay = QVBoxLayout(left)
        left_lay.setContentsMargins(36, 48, 36, 36)
        left_lay.setSpacing(0)

        # App logo / icon area
        logo_circle = QFrame()
        logo_circle.setFixedSize(72, 72)
        logo_circle.setStyleSheet("""
            QFrame {
                background: qlineargradient(x1:0,y1:0,x2:1,y2:1,
                    stop:0 #4A90E2, stop:1 #357ABD);
                border-radius: 36px;
            }
        """)
        logo_lay = QVBoxLayout(logo_circle)
        logo_icon = QLabel("🖥")
        logo_icon.setFont(QFont("Segoe UI", 28))
        logo_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        logo_icon.setStyleSheet("background:transparent; color:white;")
        logo_lay.addWidget(logo_icon)

        # Drop shadow on logo
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(30); shadow.setColor(QColor("#4A90E2"))
        shadow.setOffset(0, 0)
        logo_circle.setGraphicsEffect(shadow)

        left_lay.addWidget(logo_circle)
        left_lay.addSpacing(24)

        app_name = QLabel("Lab Monitor")
        app_name.setFont(QFont("Segoe UI", 20, QFont.Weight.Bold))
        app_name.setStyleSheet("color:white;")

        tagline = QLabel("Centralized Computer Lab\nMonitoring System")
        tagline.setStyleSheet("color:rgba(255,255,255,0.5); font-size:12px; line-height:1.6;")
        tagline.setWordWrap(True)

        left_lay.addWidget(app_name)
        left_lay.addSpacing(10)
        left_lay.addWidget(tagline)
        left_lay.addStretch()

        # Bottom features list
        for feat in ("Real-time PC monitoring", "Live CPU & RAM stats",
                     "Broadcast messaging", "Activity logging"):
            row = QHBoxLayout()
            dot = QLabel("●")
            dot.setStyleSheet("color:#4A90E2; font-size:8px;")
            dot.setFixedWidth(16)
            lbl = QLabel(feat)
            lbl.setStyleSheet("color:rgba(255,255,255,0.55); font-size:11px;")
            row.addWidget(dot); row.addWidget(lbl); row.addStretch()
            fl = QFrame(); fl.setLayout(row)
            fl.setStyleSheet("background:transparent;")
            left_lay.addWidget(fl)
            left_lay.addSpacing(4)

        left_lay.addSpacing(20)
        ver = QLabel(f"Version {VERSION}")
        ver.setStyleSheet("color:rgba(255,255,255,0.2); font-size:10px;")
        left_lay.addWidget(ver)

        # ── RIGHT: form panel ────────────────────────────────
        right = GradientFrame()
        right_lay = QVBoxLayout(right)
        right_lay.setContentsMargins(48, 36, 48, 36)

        # Close button (top right, since we removed title bar)
        top_bar = QHBoxLayout()
        top_bar.addStretch()
        btn_close = QPushButton("✕")
        btn_close.setFixedSize(32, 32)
        btn_close.setStyleSheet("""
            QPushButton {
                background: rgba(255,255,255,0.07);
                color: rgba(255,255,255,0.5);
                border: none; border-radius: 16px;
                font-size: 13px;
            }
            QPushButton:hover { background: #E74C3C; color: white; }
        """)
        btn_close.clicked.connect(self.close)
        top_bar.addWidget(btn_close)
        right_lay.addLayout(top_bar)

        # Stacked widget switches between Login and Register
        self.stack = QStackedWidget()
        self.login_panel = LoginPanel()
        self.reg_panel   = RegisterPanel()
        self.stack.addWidget(self.login_panel)   # index 0
        self.stack.addWidget(self.reg_panel)     # index 1

        self.login_panel.switch_to_register.connect(lambda: self.stack.setCurrentIndex(1))
        self.reg_panel.switch_to_login.connect(lambda: self.stack.setCurrentIndex(0))
        self.reg_panel.register_success.connect(self._on_register_success)
        self.login_panel.login_success.connect(self._on_login_success)

        right_lay.addWidget(self.stack)

        # Assemble left + right
        # Vertical separator line
        sep = QFrame()
        sep.setFixedWidth(1)
        sep.setStyleSheet("background:rgba(255,255,255,0.07);")

        root.addWidget(left)
        root.addWidget(sep)
        root.addWidget(right)

        # Outer rounded border
        self.setStyleSheet("""
            QWidget#outer {
                background: transparent;
                border-radius: 18px;
            }
        """)

    # ── drag to move (since no title bar) ───────────────────
    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = e.globalPosition().toPoint() - self.frameGeometry().topLeft()

    def mouseMoveEvent(self, e):
        if self._drag_pos and e.buttons() == Qt.MouseButton.LeftButton:
            self.move(e.globalPosition().toPoint() - self._drag_pos)

    def mouseReleaseEvent(self, e):
        self._drag_pos = None

    def paintEvent(self, e):
        """Draw rounded window with subtle border."""
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        grad = QLinearGradient(0, 0, self.width(), self.height())
        grad.setColorAt(0, QColor("#0F1923"))
        grad.setColorAt(1, QColor("#0D1B2A"))
        from PyQt6.QtGui import QPainterPath
        path = __import__('PyQt6.QtGui', fromlist=['QPainterPath']).QPainterPath()
        path.addRoundedRect(0, 0, self.width(), self.height(), 18, 18)
        p.fillPath(path, grad)
        from PyQt6.QtGui import QPen
        p.setPen(QPen(QColor("rgba(255,255,255,0.08)"), 1))
        p.drawPath(path)

    # ── callbacks ────────────────────────────────────────────
    def _on_register_success(self):
        self.stack.setCurrentIndex(0)
        self.login_panel.status.show_success("Account created! Please sign in.")

    def _on_login_success(self, admin_info):
        """Login succeeded — open the main dashboard."""
        # Import here to avoid circular imports
        from server_app import ServerWindow
        self.dashboard = ServerWindow(admin_info=admin_info)
        self.dashboard.show()
        self.close()


# ── entry point ──────────────────────────────────────────────
def main():
    app = QApplication(sys.argv)
    app.setFont(QFont("Segoe UI", 10))

    # Add drop shadow to entire window
    win = LoginWindow()

    # Center on screen
    screen = app.primaryScreen().geometry()
    win.move(
        (screen.width()  - win.width())  // 2,
        (screen.height() - win.height()) // 2
    )
    win.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
