"""
Network engine and database access for the admin server.

The GUI runs on the main thread. Socket accept/read work runs in daemon
threads, and all UI updates are sent through the callback registered by
server_app.py.
"""
# পাইথন সকেট প্রোগ্রামিং (TCP/IP Sockets)
#২. মাল্টি-থ্রেডিং (Python Threading)
 #আপনার ল্যাবে যদি ২০টি পিসি থাকে, তবে সার্ভারকে একসাথে ২০টি পিসির তথ্য রিসিভ করতে হয়।
 #মাই-এসকিউএল ডাটাবেস (MySQL)
#৫. থ্রেড-সেফ সিগন্যালিং (PyQt6 Signals)
#ব্যাকএন্ড থেকে ফ্রন্টএন্ডে (ড্যাশবোর্ড) মেসেজ পাঠানোর জন্য এটি একটি বিশেষ টেকনিক।
import json
import os
import socket
import sys
import threading
from datetime import datetime

import mysql.connector
from mysql.connector import Error

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import *  # noqa: F403
from database.schema import ensure_schema


class DatabaseManager:
    """Small database helper used by the server GUI and networking layer."""

    def __init__(self):
        ensure_schema(verbose=False)

    def _conn(self):
        return mysql.connector.connect(**DB_CONFIG)  # noqa: F405

    def upsert_client(self, pc_name, ip, cpu, ram, os_info):
        """Insert a new client or refresh the existing row."""
        try:
            c = self._conn()
            cur = c.cursor()
            cur.execute(
                """
                INSERT INTO clients (pc_name, ip, status, cpu_usage, ram_usage, os_info, last_seen)
                VALUES (%s, %s, 'online', %s, %s, %s, NOW())
                ON DUPLICATE KEY UPDATE
                  ip = VALUES(ip),
                  status = 'online',
                  cpu_usage = VALUES(cpu_usage),
                  ram_usage = VALUES(ram_usage),
                  os_info = VALUES(os_info),
                  last_seen = NOW()
                """,
                (pc_name, ip, float(cpu or 0), float(ram or 0), os_info or ""),
            )
            c.commit()
            cur.close()
            c.close()
        except Error as e:
            print(f"[DB] upsert_client: {e}")

    def set_offline(self, pc_name):
        try:
            c = self._conn()
            cur = c.cursor()
            cur.execute(
                "UPDATE clients SET status = 'offline', last_seen = NOW() WHERE pc_name = %s",
                (pc_name,),
            )
            c.commit()
            cur.close()
            c.close()
        except Error as e:
            print(f"[DB] set_offline: {e}")

    def all_clients(self):
        try:
            c = self._conn()
            cur = c.cursor(dictionary=True)
            cur.execute(
                """
                SELECT
                    pc_name,
                    ip,
                    COALESCE(status, 'offline') AS status,
                    COALESCE(cpu_usage, 0.0) AS cpu_usage,
                    COALESCE(ram_usage, 0.0) AS ram_usage,
                    COALESCE(os_info, '') AS os_info,
                    last_seen
                FROM clients
                ORDER BY pc_name
                """
            )
            rows = cur.fetchall()
            cur.close()
            c.close()
            return rows
        except Error as e:
            print(f"[DB] all_clients: {e}")
            return []

    def save_msg(self, sender, receiver, text):
        try:
            c = self._conn()
            cur = c.cursor()
            cur.execute(
                "INSERT INTO messages(sender, receiver, message) VALUES(%s, %s, %s)",
                (sender, receiver, text),
            )
            c.commit()
            cur.close()
            c.close()
        except Error as e:
            print(f"[DB] save_msg: {e}")

    def all_messages(self, limit=100):
        try:
            c = self._conn()
            cur = c.cursor(dictionary=True)
            cur.execute(
                "SELECT * FROM messages ORDER BY time DESC LIMIT %s",
                (int(limit),),
            )
            rows = cur.fetchall()
            cur.close()
            c.close()
            return rows
        except Error as e:
            print(f"[DB] all_messages: {e}")
            return []

    def log(self, pc_name, action):
        try:
            c = self._conn()
            cur = c.cursor()
            cur.execute(
                "INSERT INTO activity_logs(pc_name, action) VALUES(%s, %s)",
                (pc_name, action),
            )
            c.commit()
            cur.close()
            c.close()
        except Error as e:
            print(f"[DB] log: {e}")

    def all_logs(self, limit=200):
        try:
            c = self._conn()
            cur = c.cursor(dictionary=True)
            cur.execute(
                "SELECT * FROM activity_logs ORDER BY time DESC LIMIT %s",
                (int(limit),),
            )
            rows = cur.fetchall()
            cur.close()
            c.close()
            return rows
        except Error as e:
            print(f"[DB] all_logs: {e}")
            return []


class LabServer:
    def __init__(self):
        self.db = DatabaseManager()
        self.clients = {}  # pc_name -> {"socket", "ip", "cpu", "ram", "os", "last_seen"}
        self.lock = threading.Lock()
        self.running = False
        self._sock = None
        self._cb = None

    def set_callback(self, fn):
        self._cb = fn

    def notify(self, event, data=None):
        if self._cb:
            self._cb(event, data or {})

    def start(self):
        if self.running:
            return True
        try:
            self._sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self._sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self._sock.bind((SERVER_HOST, SERVER_PORT))  # noqa: F405
            self._sock.listen(20)
            self.running = True
            threading.Thread(target=self._accept_loop, daemon=True).start()
            print(f"[SERVER] Listening on port {SERVER_PORT}")  # noqa: F405
            self.notify("started", {"port": SERVER_PORT})  # noqa: F405
            return True
        except Exception as e:
            self.notify("error", {"msg": str(e)})
            return False

    def stop(self):
        self.running = False
        try:
            if self._sock:
                self._sock.close()
        except OSError:
            pass

        with self.lock:
            clients = list(self.clients.items())
            self.clients.clear()

        for pc_name, info in clients:
            conn = info.get("socket")
            try:
                if conn:
                    conn.close()
            except OSError:
                pass
            self.db.set_offline(pc_name)
            self.db.log(pc_name, "SERVER STOPPED")

    def send_all(self, text):
        payload = {"type": MSG_SERVER_MSG, "from": "SERVER", "message": text}  # noqa: F405
        self.db.save_msg("SERVER", "ALL", text)
        count = 0
        with self.lock:
            clients = list(self.clients.items())
        for name, info in clients:
            if self._push(info.get("socket"), payload):
                count += 1
            else:
                self._remove(name, info.get("socket"))
        self.notify("msg_sent", {"to": "ALL", "text": text, "count": count})

    def send_one(self, pc_name, text):
        with self.lock:
            info = self.clients.get(pc_name)
        if not info:
            return False

        ok = self._push(
            info.get("socket"),
            {"type": MSG_SERVER_MSG, "from": "SERVER", "message": text},  # noqa: F405
        )
        if ok:
            self.db.save_msg("SERVER", pc_name, text)
        else:
            self._remove(pc_name, info.get("socket"))
        return ok

    def send_shutdown(self, pc_name):
        """Send a real shutdown command to one connected client PC."""
        with self.lock:
            info = self.clients.get(pc_name)
        if not info:
            return False

        ok = self._push(
            info.get("socket"),
            {
                "type": MSG_SHUTDOWN,  # noqa: F405
                "from": "SERVER",
                "delay": REMOTE_SHUTDOWN_DELAY_SECONDS,  # noqa: F405
            },
        )
        if ok:
            self.db.log(pc_name, "SHUTDOWN COMMAND SENT")
            self.notify("shutdown_sent", {"pc_name": pc_name})
        else:
            self._remove(pc_name, info.get("socket"))
        return ok

    def connected_names(self):
        with self.lock:
            return list(self.clients.keys())

    def _accept_loop(self):
        while self.running:
            try:
                conn, addr = self._sock.accept()
                threading.Thread(target=self._handle, args=(conn, addr[0]), daemon=True).start()
            except OSError:
                break
            except Exception as e:
                print(f"[SERVER] accept error: {e}")

    def _handle(self, conn, ip):
        pc_name = None
        buf = ""
        try:
            while self.running:
                chunk = conn.recv(4096)
                if not chunk:
                    break
                buf += chunk.decode("utf-8", errors="replace")
                while "\n" in buf:
                    line, buf = buf.split("\n", 1)
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        msg = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    if isinstance(msg, dict):
                        pc_name = self._process(conn, ip, pc_name, msg)
        except OSError:
            pass
        except Exception as e:
            print(f"[SERVER] client handler error: {e}")
        finally:
            self._remove(pc_name, conn)

    def _process(self, conn, ip, pc_name, msg):
        msg_type = msg.get("type", "")

        if msg_type == MSG_REGISTER:  # noqa: F405
            pc_name = msg.get("pc_name") or f"PC-{ip}"
            cpu = msg.get("cpu", 0)
            ram = msg.get("ram", 0)
            os_info = msg.get("os", "")

            with self.lock:
                old = self.clients.get(pc_name)
                self.clients[pc_name] = {
                    "socket": conn,
                    "ip": ip,
                    "cpu": cpu,
                    "ram": ram,
                    "os": os_info,
                    "last_seen": datetime.now(),
                }
            if old and old.get("socket") is not conn:
                try:
                    old["socket"].close()
                except OSError:
                    pass

            self.db.upsert_client(pc_name, ip, cpu, ram, os_info)
            self.db.log(pc_name, "CONNECTED")
            self._push(conn, {"type": MSG_ACK, "message": f"Welcome {pc_name}!"})  # noqa: F405
            self.notify(
                "connected",
                {"pc_name": pc_name, "ip": ip, "cpu": cpu, "ram": ram, "os": os_info},
            )

        elif msg_type == MSG_STATUS:  # noqa: F405
            pc_name = pc_name or msg.get("pc_name")
            if not pc_name:
                return pc_name

            cpu = msg.get("cpu", 0)
            ram = msg.get("ram", 0)
            os_info = msg.get("os", "")
            self.db.upsert_client(pc_name, ip, cpu, ram, os_info)
            with self.lock:
                if pc_name in self.clients and self.clients[pc_name].get("socket") is conn:
                    self.clients[pc_name].update(
                        {"cpu": cpu, "ram": ram, "os": os_info, "last_seen": datetime.now()}
                    )
            self.notify("status", {"pc_name": pc_name, "cpu": cpu, "ram": ram})

        elif msg_type == MSG_CLIENT_MSG and pc_name:  # noqa: F405
            text = msg.get("message", "")
            self.db.save_msg(pc_name, "SERVER", text)
            self.db.log(pc_name, f"MSG: {text[:60]}")
            self.notify(
                "msg_in",
                {"from": pc_name, "text": text, "time": datetime.now().strftime("%H:%M:%S")},
            )

        elif msg_type == MSG_DISCONNECT and pc_name:  # noqa: F405
            self.db.log(pc_name, "DISCONNECT REQUESTED")

        elif msg_type == MSG_PONG and pc_name:  # noqa: F405
            with self.lock:
                if pc_name in self.clients and self.clients[pc_name].get("socket") is conn:
                    self.clients[pc_name]["last_seen"] = datetime.now()

        return pc_name

    def _push(self, conn, data):
        if not conn:
            return False
        try:
            conn.sendall((json.dumps(data) + "\n").encode("utf-8"))
            return True
        except OSError:
            return False

    def _remove(self, pc_name, conn):
        try:
            if conn:
                conn.close()
        except OSError:
            pass

        if not pc_name:
            return

        removed = False
        with self.lock:
            current = self.clients.get(pc_name)
            if current and current.get("socket") is conn:
                self.clients.pop(pc_name, None)
                removed = True

        if removed:
            self.db.set_offline(pc_name)
            self.db.log(pc_name, "DISCONNECTED")
            self.notify("disconnected", {"pc_name": pc_name})
