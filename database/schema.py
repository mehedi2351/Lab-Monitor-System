"""Database schema creation and light migrations for Lab Monitor."""

import os
import sys

import mysql.connector
from mysql.connector import Error

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import DB_CONFIG


_SCHEMA_READY = False


def _db_name():
    return DB_CONFIG["database"]


def _quote_identifier(name):
    return "`" + str(name).replace("`", "``") + "`"


def _server_config():
    return {k: v for k, v in DB_CONFIG.items() if k != "database"}


def _column_exists(cur, table, column):
    cur.execute(
        """
        SELECT COUNT(*)
        FROM information_schema.columns
        WHERE table_schema = %s AND table_name = %s AND column_name = %s
        """,
        (_db_name(), table, column),
    )
    return cur.fetchone()[0] > 0


def _index_exists(cur, table, index_name):
    cur.execute(
        """
        SELECT COUNT(*)
        FROM information_schema.statistics
        WHERE table_schema = %s AND table_name = %s AND index_name = %s
        """,
        (_db_name(), table, index_name),
    )
    return cur.fetchone()[0] > 0


def _unique_index_on_column_exists(cur, table, column):
    cur.execute(
        """
        SELECT COUNT(*)
        FROM information_schema.statistics
        WHERE table_schema = %s
          AND table_name = %s
          AND column_name = %s
          AND non_unique = 0
        """,
        (_db_name(), table, column),
    )
    return cur.fetchone()[0] > 0


def _add_column_if_missing(cur, table, column, definition, verbose):
    if not _column_exists(cur, table, column):
        cur.execute(f"ALTER TABLE {_quote_identifier(table)} ADD COLUMN {column} {definition}")
        if verbose:
            print(f"  OK  added {table}.{column}")


def _ensure_columns(cur, verbose):
    specs = {
        "admins": {
            "id": "INT AUTO_INCREMENT PRIMARY KEY",
            "full_name": "VARCHAR(100) NOT NULL DEFAULT ''",
            "username": "VARCHAR(50) NOT NULL",
            "password": "VARCHAR(255) NOT NULL DEFAULT ''",
            "created_at": "DATETIME DEFAULT CURRENT_TIMESTAMP",
        },
        "clients": {
            "id": "INT AUTO_INCREMENT PRIMARY KEY",
            "pc_name": "VARCHAR(100) NOT NULL DEFAULT ''",
            "ip": "VARCHAR(50)",
            "status": "VARCHAR(20) DEFAULT 'offline'",
            "cpu_usage": "FLOAT DEFAULT 0",
            "ram_usage": "FLOAT DEFAULT 0",
            "os_info": "VARCHAR(200) DEFAULT ''",
            "last_seen": "DATETIME DEFAULT CURRENT_TIMESTAMP",
        },
        "messages": {
            "id": "INT AUTO_INCREMENT PRIMARY KEY",
            "sender": "VARCHAR(100)",
            "receiver": "VARCHAR(100)",
            "message": "TEXT",
            "time": "DATETIME DEFAULT CURRENT_TIMESTAMP",
        },
        "activity_logs": {
            "id": "INT AUTO_INCREMENT PRIMARY KEY",
            "pc_name": "VARCHAR(100)",
            "action": "VARCHAR(200)",
            "time": "DATETIME DEFAULT CURRENT_TIMESTAMP",
        },
    }

    for table, columns in specs.items():
        for column, definition in columns.items():
            _add_column_if_missing(cur, table, column, definition, verbose)


def _ensure_indexes(cur, verbose):
    if not _unique_index_on_column_exists(cur, "admins", "username"):
        cur.execute("ALTER TABLE admins ADD UNIQUE KEY username (username)")
        if verbose:
            print("  OK  admins.username unique index")

    if not _index_exists(cur, "clients", "uq_pc") and not _unique_index_on_column_exists(
        cur, "clients", "pc_name"
    ):
        cur.execute(
            """
            DELETE c1 FROM clients c1
            INNER JOIN clients c2
                ON c1.pc_name = c2.pc_name AND c1.id > c2.id
            WHERE c1.pc_name <> ''
            """
        )
        cur.execute("ALTER TABLE clients ADD UNIQUE KEY uq_pc (pc_name)")
        if verbose:
            print("  OK  clients.pc_name unique index")


def ensure_schema(verbose=False):
    """Create the database/tables and patch common old-schema issues."""
    global _SCHEMA_READY
    if _SCHEMA_READY:
        return True

    con = None
    try:
        con = mysql.connector.connect(**_server_config())
        cur = con.cursor()
        db = _quote_identifier(_db_name())

        if verbose:
            print(f"Creating database '{_db_name()}' ...")
        cur.execute(
            f"CREATE DATABASE IF NOT EXISTS {db} "
            "CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
        )
        cur.execute(f"USE {db}")

        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS admins (
                id INT AUTO_INCREMENT PRIMARY KEY,
                full_name VARCHAR(100) NOT NULL,
                username VARCHAR(50) NOT NULL UNIQUE,
                password VARCHAR(255) NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS clients (
                id INT AUTO_INCREMENT PRIMARY KEY,
                pc_name VARCHAR(100) NOT NULL,
                ip VARCHAR(50),
                status VARCHAR(20) DEFAULT 'offline',
                cpu_usage FLOAT DEFAULT 0,
                ram_usage FLOAT DEFAULT 0,
                os_info VARCHAR(200) DEFAULT '',
                last_seen DATETIME DEFAULT CURRENT_TIMESTAMP,
                UNIQUE KEY uq_pc (pc_name)
            )
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS messages (
                id INT AUTO_INCREMENT PRIMARY KEY,
                sender VARCHAR(100),
                receiver VARCHAR(100),
                message TEXT,
                time DATETIME DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS activity_logs (
                id INT AUTO_INCREMENT PRIMARY KEY,
                pc_name VARCHAR(100),
                action VARCHAR(200),
                time DATETIME DEFAULT CURRENT_TIMESTAMP
            )
            """
        )

        _ensure_columns(cur, verbose)
        _ensure_indexes(cur, verbose)
        con.commit()
        cur.close()
        _SCHEMA_READY = True

        if verbose:
            print("  OK  admins table")
            print("  OK  clients table")
            print("  OK  messages table")
            print("  OK  activity_logs table")
            print("\nAll tables ready! Now run: python server/login_app.py")
        return True
    except Error as e:
        if verbose:
            print(f"\nERROR: {e}")
            print("Check MySQL is running and DB_CONFIG password is correct.")
        else:
            print(f"[DB] schema: {e}")
        return False
    finally:
        try:
            if con:
                con.close()
        except Error:
            pass
