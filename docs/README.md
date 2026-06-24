# Centralized Computer Lab Monitoring System — Beginner Guide

## STEP 1 — Install dependencies (BOTH PCs)
    pip install -r requirements.txt
Also install MySQL and start the MySQL service.

## STEP 2 — Set up the database (SERVER PC only)
1. Open config.py, change "your_password" to your MySQL password
2. Run:  python database/setup_db.py

## STEP 3 — Find the server hotspot IP (SERVER PC)
Windows: open CMD → type ipconfig
Look for "Wireless LAN Adapter" or "Mobile Hotspot" → copy IPv4 Address
Example: 192.168.137.1

## STEP 4 — Edit config.py on the CLIENT PC
Change:   SERVER_IP = "192.168.137.1"   ← paste server's IP here

## STEP 5 — Run in this order
1st → SERVER PC:   python server/server_app.py
2nd → CLIENT PC:   python client/client_app.py

## Windows Firewall (if clients cannot connect)
Windows Firewall → Advanced Settings → Inbound Rules → New Rule
→ Port → TCP → 5000 → Allow the connection

## Self-test on ONE PC
Change SERVER_IP = "127.0.0.1" in config.py, run both apps on the same machine.

## Troubleshooting
Connection refused  → Server not running, or wrong IP in config.py
MySQL error         → Check password, check MySQL service is running
Port in use         → Change SERVER_PORT in config.py (try 5001)
