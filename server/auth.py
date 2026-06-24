"""
==============================================================
  File: server/auth.py
  Purpose: Admin authentication — register, login, password hash
==============================================================

SECURITY NOTE (for learning):
  We use SHA-256 + salt to store passwords.
  The real password is NEVER saved — only its hash.
  Even if someone reads the database, they cannot get the password.

  How hashing works:
    "mypassword" + "randomsalt"  →  sha256()  →  "a3f9bc..."
    You cannot reverse this to get "mypassword" back.
"""

import hashlib, os, sys
import mysql.connector
from mysql.connector import Error

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import DB_CONFIG
from database.schema import ensure_schema


def _hash_password(password: str, salt: str = "") -> str:
    """
    Combines password + salt and returns SHA-256 hex string.
    Salt makes identical passwords produce different hashes.
    """
    combined = password + salt + "lab_monitor_secret_pepper"
    return hashlib.sha256(combined.encode("utf-8")).hexdigest()


def _make_salt() -> str:
    """Generates 16 random hex characters as a salt."""
    return os.urandom(8).hex()


def _conn():
    ensure_schema(verbose=False)
    return mysql.connector.connect(**DB_CONFIG)


# ── public API ───────────────────────────────────────────────

def register_admin(full_name: str, username: str, password: str) -> tuple[bool, str]:
    """
    Creates a new admin account.
    Returns (True, "success message") or (False, "error message").
    """
    if not full_name.strip() or not username.strip() or not password.strip():
        return False, "All fields are required."
    if len(password) < 4:
        return False, "Password must be at least 4 characters."
    if len(username) < 3:
        return False, "Username must be at least 3 characters."

    salt = _make_salt()
    hashed = _hash_password(password, salt)
    # We store:  salt$hash  so we can verify later
    stored = f"{salt}${hashed}"

    try:
        c = _conn(); cur = c.cursor()
        cur.execute(
            "INSERT INTO admins (full_name, username, password) VALUES (%s, %s, %s)",
            (full_name.strip(), username.strip().lower(), stored)
        )
        c.commit(); c.close()
        return True, f"Account created! Welcome, {full_name}."
    except Error as e:
        if "Duplicate entry" in str(e):
            return False, f"Username '{username}' is already taken."
        return False, f"Database error: {e}"


def login_admin(username: str, password: str) -> tuple[bool, str, dict]:
    """
    Verifies login credentials.
    Returns (True, "welcome msg", {id, full_name, username})
         or (False, "error msg", {})
    """
    if not username.strip() or not password.strip():
        return False, "Please enter username and password.", {}

    try:
        c = _conn(); cur = c.cursor(dictionary=True)
        cur.execute(
            "SELECT * FROM admins WHERE username = %s",
            (username.strip().lower(),)
        )
        row = cur.fetchone(); c.close()

        if not row:
            return False, "Username not found.", {}

        # Split stored value back into salt and hash
        stored = row.get("password") or ""
        if "$" not in stored:
            return False, "Account data corrupted. Please re-register.", {}

        salt, saved_hash = stored.split("$", 1)
        if _hash_password(password, salt) == saved_hash:
            full_name = row.get("full_name") or row.get("username") or "Admin"
            return True, f"Welcome back, {full_name}!", {
                "id"       : row.get("id"),
                "full_name": full_name,
                "username" : row.get("username"),
            }
        else:
            return False, "Incorrect password.", {}

    except Error as e:
        return False, f"Database error: {e}", {}


def admin_count() -> int:
    """Returns how many admin accounts exist (used to show/hide Register tab)."""
    try:
        c = _conn(); cur = c.cursor()
        cur.execute("SELECT COUNT(*) FROM admins")
        n = cur.fetchone()[0]; c.close()
        return n
    except:
        return 0
