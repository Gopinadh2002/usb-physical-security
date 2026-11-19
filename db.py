import sqlite3
import hashlib
import hmac
import os
from datetime import datetime
import sys

if getattr(sys, "frozen", False):          # running as an exe
    BASE = os.path.dirname(sys.executable)
else:
    BASE = os.path.dirname(os.path.abspath(__file__))
DB_FILE = os.path.join(BASE, "usb_security.db")


def connect():
    return sqlite3.connect(DB_FILE)


def init_db():
    """Create the tables the first time the program runs."""
    with connect() as con:
        con.execute("""
            CREATE TABLE IF NOT EXISTS admin (
                username TEXT PRIMARY KEY,
                salt BLOB NOT NULL,
                password_hash BLOB NOT NULL
            )""")
        con.execute("""
            CREATE TABLE IF NOT EXISTS devices (
                vendor_id TEXT NOT NULL,
                product_id TEXT NOT NULL,
                serial TEXT NOT NULL,
                name TEXT,
                status TEXT NOT NULL,      -- whitelist, blacklist or pending
                added_on TEXT,
                PRIMARY KEY (vendor_id, product_id, serial)
            )""")
        con.execute("""
            CREATE TABLE IF NOT EXISTS log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                time TEXT,
                vendor_id TEXT,
                product_id TEXT,
                serial TEXT,
                name TEXT,
                action TEXT,
                details TEXT
            )""")


# ---------- Admin account (password is never stored as plain text) ----------

def _hash_password(password, salt):
    return hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 200_000)


def admin_exists():
    with connect() as con:
        return con.execute("SELECT COUNT(*) FROM admin").fetchone()[0] > 0


def create_admin(username, password):
    """Only works if no admin exists yet, so nobody can add a second one."""
    if admin_exists():
        return False
    salt = os.urandom(16)
    with connect() as con:
        con.execute("INSERT INTO admin VALUES (?, ?, ?)",
                    (username, salt, _hash_password(password, salt)))
    return True


def check_login(username, password):
    with connect() as con:
        row = con.execute("SELECT salt, password_hash FROM admin WHERE username=?",
                          (username,)).fetchone()
    if row is None:
        return False
    return hmac.compare_digest(_hash_password(password, row[0]), row[1])

def change_password(username, old_password, new_password):
    if not check_login(username, old_password):
        return False
    salt = os.urandom(16)
    with connect() as con:
        con.execute("UPDATE admin SET salt=?, password_hash=? WHERE username=?",
                    (salt, _hash_password(new_password, salt), username))
    return True


# ---------- Device lists ----------

def get_status(vendor_id, product_id, serial):
    """Returns 'whitelist', 'blacklist', 'pending' or None if never seen."""
    with connect() as con:
        row = con.execute(
            "SELECT status FROM devices WHERE vendor_id=? AND product_id=? AND serial=?",
            (vendor_id, product_id, serial)).fetchone()
    return row[0] if row else None


def set_status(vendor_id, product_id, serial, name, status):
    """Add a device to a list, or move it from one list to another."""
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with connect() as con:
        con.execute("""
            INSERT INTO devices VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(vendor_id, product_id, serial)
            DO UPDATE SET status=excluded.status, name=excluded.name""",
            (vendor_id, product_id, serial, name, status, now))


def remove_device(vendor_id, product_id, serial):
    with connect() as con:
        con.execute(
            "DELETE FROM devices WHERE vendor_id=? AND product_id=? AND serial=?",
            (vendor_id, product_id, serial))


def list_devices(status):
    with connect() as con:
        return con.execute(
            "SELECT vendor_id, product_id, serial, name, added_on FROM devices WHERE status=?",
            (status,)).fetchall()


# ---------- Log ----------

def add_log(action, vendor_id="", product_id="", serial="", name="", details=""):
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with connect() as con:
        con.execute(
            "INSERT INTO log (time, vendor_id, product_id, serial, name, action, details) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (now, vendor_id, product_id, serial, name, action, details))


def get_log(limit=100):
    with connect() as con:
        return con.execute(
            "SELECT time, name, vendor_id, product_id, action, details "
            "FROM log ORDER BY id DESC LIMIT ?", (limit,)).fetchall()