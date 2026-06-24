"""
==============================================================
  CENTRALIZED COMPUTER LAB MONITORING SYSTEM
  File: config.py  (shared by BOTH server and client)
==============================================================
STUDENT NOTE — Before running on two PCs:
  1. Find the SERVER PC's hotspot IP:
       Windows: open CMD → type  ipconfig
                look for "Wireless LAN adapter" or "Mobile Hotspot"
                copy the IPv4 Address  (e.g. 192.168.137.1)
  2. Paste that IP into SERVER_IP below on the CLIENT PC copy
  3. Run server_app.py on SERVER first, then client_app.py on CLIENT
"""

# ── NETWORK ────────────────────────────────────────────────
SERVER_HOST = "0.0.0.0"        # Server binds to ALL interfaces
SERVER_IP   = "10.167.0.240"  # ← CHANGE THIS to your server's hotspot IP
SERVER_PORT = 5000

CLIENT_TIMEOUT  = 30   # seconds of silence before client marked offline
UPDATE_INTERVAL = 5    # how often clients send CPU/RAM updates (seconds)
REMOTE_SHUTDOWN_DELAY_SECONDS = 5

# ── DATABASE ───────────────────────────────────────────────
DB_CONFIG = {
    "host"    : "localhost",
    "user"    : "root",
    "password": "mehedi",  # ← CHANGE THIS
    "database": "lab_monitor",
    "port"    : 3306,
}

# ── MESSAGE TYPES ──────────────────────────────────────────
MSG_REGISTER   = "REGISTER"
MSG_STATUS     = "STATUS"
MSG_CLIENT_MSG = "CLIENT_MSG"
MSG_DISCONNECT = "DISCONNECT"
MSG_SERVER_MSG = "SERVER_MSG"
MSG_ACK        = "ACK"
MSG_PING       = "PING"
MSG_PONG       = "PONG"
MSG_SHUTDOWN   = "SHUTDOWN"

# ── GUI ────────────────────────────────────────────────────
SERVER_TITLE = "Lab Monitor — Admin Dashboard"
CLIENT_TITLE = "Lab Monitor — Student PC Agent"
VERSION      = "1.0 DEMO"
COLOR_ONLINE  = "#2ECC71"
COLOR_OFFLINE = "#E74C3C"
COLOR_ACCENT  = "#3498DB"
COLOR_WARNING = "#F39C12"
