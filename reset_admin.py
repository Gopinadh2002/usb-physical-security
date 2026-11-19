import ctypes
import os
import shutil
import sqlite3
from datetime import datetime
import db

# 1. Must be run as Windows Administrator
if not ctypes.windll.shell32.IsUserAnAdmin():
    print("Run this program as Windows Administrator.")
    raise SystemExit

db.init_db()

if not db.admin_exists():
    print("There is no admin account. Just start gui.py to create one.")
    raise SystemExit

print("OFFLINE ADMIN RESET")
print("This removes the admin account so a new one can be created.")
print("Device lists (whitelist, blacklist, pending) and the log are kept.\n")

if input("Type RESET to continue: ").strip() != "RESET":
    print("Cancelled.")
    raise SystemExit

# 2. Back up the database first
stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
backup = os.path.join(os.path.dirname(db.DB_FILE), f"usb_security_backup_{stamp}.db")
shutil.copy2(db.DB_FILE, backup)
print(f"Backup saved: {backup}")

# 3. Remove the admin account (and the recovery key, if that table exists)
with db.connect() as con:
    con.execute("DELETE FROM admin")
    try:
        con.execute("DELETE FROM recovery")
    except sqlite3.OperationalError:
        pass          # recovery table not added yet, nothing to delete

# 4. Record it in the log
db.add_log("ADMIN_RESET", details="admin account removed with reset_admin.py")
print("\nDone. Start gui.py and create a new administrator account.")