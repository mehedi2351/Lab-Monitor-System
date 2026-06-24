"""
Network engine for the student PC agent.

The GUI calls connect()/disconnect()/send_message(); this class keeps all
socket work in background threads and reports events back through a callback.
"""

import json
import os
import platform
import socket
import subprocess
import sys
import threading
import time

import psutil

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import *  # noqa: F403


class LabClient:
    def __init__(self):
        self._sock = None
        self.running = False
        self._connecting = False
        self._shutdown_started = False
        self._connect_seq = 0
        self.pc_name = platform.node() or "Unknown-PC"
        self.os_info = f"{platform.system()} {platform.release()}"
        self._cb = None
        self._buf = ""

    def set_callback(self, fn):
        self._cb = fn

    def notify(self, event, data=None):
        if self._cb:
            self._cb(event, data or {})

    def cpu(self):
        return psutil.cpu_percent(interval=None)

    def ram(self):
        return psutil.virtual_memory().percent

    def connect(self, server_ip=SERVER_IP, port=SERVER_PORT):  # noqa: F405
        if self.running or self._connecting:
            return

        self._connecting = True
        self._connect_seq += 1
        token = self._connect_seq
        self.notify("connecting", {"server": server_ip, "port": port})
        threading.Thread(target=self._connect_worker, args=(server_ip, port, token), daemon=True).start()

    def _connect_worker(self, server_ip, port, token):
        timeout = 8
        sock = None
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(timeout)
            sock.connect((server_ip, port))
            sock.settimeout(None)

            if token != self._connect_seq or not self._connecting:
                sock.close()
                return

            self._sock = sock
            self.running = True
            self._connecting = False
            self._shutdown_started = False
            self._buf = ""

            psutil.cpu_percent(interval=None)
            self._push(
                {
                    "type": MSG_REGISTER,  # noqa: F405
                    "pc_name": self.pc_name,
                    "cpu": self.cpu(),
                    "ram": self.ram(),
                    "os": self.os_info,
                }
            )

            threading.Thread(target=self._recv_loop, daemon=True).start()
            threading.Thread(target=self._status_loop, daemon=True).start()
            self.notify("connected", {"server": server_ip, "port": port})

        except socket.timeout:
            if token == self._connect_seq and self._connecting:
                self._connect_failed(
                    sock,
                    (
                        f"Connection timed out after {timeout}s.\n\n"
                        "Checklist:\n"
                        "  1. Is server_app.py running on the server PC?\n"
                        "  2. Is the IP address correct?\n"
                        "  3. Are both PCs on the same WiFi/hotspot?\n"
                        "  4. Windows Firewall: allow port 5000 on the server PC."
                    ),
                )
        except ConnectionRefusedError:
            if token == self._connect_seq and self._connecting:
                self._connect_failed(
                    sock,
                    "Connection refused. Make sure the server app is running first.",
                )
        except OSError as e:
            if token == self._connect_seq and self._connecting:
                self._connect_failed(sock, f"Network error: {e}")
        except Exception as e:
            if token == self._connect_seq and self._connecting:
                self._connect_failed(sock, f"Unexpected error: {e}")

    def _connect_failed(self, sock, message):
        self.running = False
        self._connecting = False
        try:
            if sock:
                sock.close()
        except OSError:
            pass
        if self._sock is sock:
            self._sock = None
        self.notify("error", {"msg": message})

    def disconnect(self):
        was_active = self.running or self._connecting
        self.running = False
        self._connecting = False
        self._connect_seq += 1
        try:
            self._push({"type": MSG_DISCONNECT, "pc_name": self.pc_name})  # noqa: F405
        except OSError:
            pass
        try:
            if self._sock:
                self._sock.close()
        except OSError:
            pass
        self._sock = None
        if was_active:
            self.notify("disconnected")

    def send_message(self, text):
        ok = self._push(
            {
                "type": MSG_CLIENT_MSG,  # noqa: F405
                "pc_name": self.pc_name,
                "message": text,
            }
        )
        if ok:
            self.notify("msg_sent", {"text": text})
        return ok

    def _recv_loop(self):
        while self.running:
            try:
                chunk = self._sock.recv(4096)
                if not chunk:
                    break
                self._buf += chunk.decode("utf-8", errors="replace")
                while "\n" in self._buf:
                    line, self._buf = self._buf.split("\n", 1)
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        msg = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    if isinstance(msg, dict):
                        self._process(msg)
            except OSError:
                break
            except Exception as e:
                print(f"[CLIENT] recv error: {e}")
                break

        if self.running:
            self.running = False
            self.notify("disconnected")

    def _status_loop(self):
        time.sleep(UPDATE_INTERVAL)  # noqa: F405
        while self.running:
            cpu = self.cpu()
            ram = self.ram()
            ok = self._push(
                {
                    "type": MSG_STATUS,  # noqa: F405
                    "pc_name": self.pc_name,
                    "cpu": cpu,
                    "ram": ram,
                    "os": self.os_info,
                }
            )
            if ok:
                self.notify("status_sent", {"cpu": cpu, "ram": ram})
            else:
                self.running = False
                self.notify("disconnected")
                break
            time.sleep(UPDATE_INTERVAL)  # noqa: F405

    def _process(self, msg):
        msg_type = msg.get("type", "")
        if msg_type == MSG_ACK:  # noqa: F405
            self.notify("ack", {"message": msg.get("message", "")})
        elif msg_type == MSG_SERVER_MSG:  # noqa: F405
            self.notify(
                "msg_in",
                {
                    "from": msg.get("from", "SERVER"),
                    "message": msg.get("message", ""),
                },
            )
        elif msg_type == MSG_PING:  # noqa: F405
            self._push({"type": MSG_PONG, "pc_name": self.pc_name})  # noqa: F405
        elif msg_type == MSG_SHUTDOWN:  # noqa: F405
            self._handle_shutdown(msg)

    def _handle_shutdown(self, msg):
        if self._shutdown_started:
            return
        self._shutdown_started = True
        delay = int(msg.get("delay") or REMOTE_SHUTDOWN_DELAY_SECONDS)  # noqa: F405

        self.notify("shutdown_requested", {"delay": delay})
        self._push(
            {
                "type": MSG_CLIENT_MSG,  # noqa: F405
                "pc_name": self.pc_name,
                "message": f"Shutdown command received. Shutting down in {delay}s.",
            }
        )
        threading.Thread(target=self._shutdown_worker, args=(delay,), daemon=True).start()

    def _shutdown_worker(self, delay):
        system = platform.system().lower()
        if system == "windows":
            cmd = [
                "shutdown",
                "/s",
                "/t",
                str(max(delay, 0)),
                "/c",
                "Remote shutdown requested by Lab Monitor admin",
            ]
        elif system == "linux":
            cmd = ["shutdown", "-h", "now" if delay < 60 else f"+{delay // 60}"]
        elif system == "darwin":
            cmd = ["osascript", "-e", 'tell application "System Events" to shut down']
        else:
            self.notify("error", {"msg": f"Remote shutdown is not supported on {platform.system()}."})
            return

        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            if result.returncode != 0:
                err = (result.stderr or result.stdout or "Shutdown command failed.").strip()
                self.notify("error", {"msg": err})
                self._shutdown_started = False
                return
            self.notify("shutdown_started", {"delay": delay})
            time.sleep(min(max(delay, 1), 3))
            self.disconnect()
        except Exception as e:
            self._shutdown_started = False
            self.notify("error", {"msg": f"Could not start shutdown: {e}"})

    def _push(self, data):
        try:
            if not self._sock:
                return False
            self._sock.sendall((json.dumps(data) + "\n").encode("utf-8"))
            return True
        except OSError:
            return False
