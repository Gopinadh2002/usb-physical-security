# USB Physical Security Application

**Team Autobots**
P. Gopinadh, D. Viraj Mahi Paul, K. Leela Krishna, A. Murali Karthik

A Windows desktop application that controls which USB devices may be used on a computer. Each device is identified by its Vendor ID, Product ID and serial number, then allowed, blocked or held for approval using an administrator-managed whitelist and blacklist. Every event is recorded in a log. The application works fully offline.

## Features

- Detects USB devices when they are plugged in or removed
- Whitelist (allowed), blacklist (banned) and pending (unknown, blocked until the admin decides)
- Unknown devices are blocked by default
- Scan before approval: device type check (BadUSB sign), Windows Defender scan and suspicious-file check (programs, scripts, shortcuts, `autorun.inf`, hidden files, double extensions)
- Administrator-only access: the first run creates one admin account, with no public sign-up
- Passwords stored as salted hashes, never as plain text
- Login lock for 30 seconds after 5 wrong attempts
- Log of logins, device decisions, scans and admin actions
- Offline admin reset script
- Safe mode that never blocks keyboards and mice

## Requirements

- Windows 10 or 11
- Python 3.10 or newer
- Windows Defender enabled (needed for the Defender scan check)
- Administrator rights (needed to enable and disable devices)

## Download
 - The ready-to-run Windows executable is available under Releases.
 - Right-click it and run as Administrator on first use. Windows or your antivirus may warn
 - about it because it is unsigned and it changes device settings.

## Setup

```
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

## First run

1. Open Command Prompt **as Administrator** in the project folder and activate the venv.
2. With your normal mouse, keyboard and trusted devices plugged in, run:
   ```
   python monitor.py --baseline
   ```
   This puts the connected devices on the whitelist.
3. Start the application:
   ```
   python gui.py
   ```
4. On the first run, the **Create Administrator Account** screen appears. Choose a username and a password of at least 8 characters.

After that, protection starts whenever the application is open.

## How to use

| Tab | What it shows | What you can do |
|---|---|---|
| Pending | Unknown devices that were blocked | Scan, Whitelist, Blacklist, Remove |
| Whitelist | Approved devices | Scan, Blacklist, Remove |
| Blacklist | Banned devices | Scan, Whitelist, Remove |
| Log | All recorded events | Refresh |

Use **Change password** at the top of the main window to change the admin password.

## Project files

| File | Purpose |
|---|---|
| `gui.py` | Main application (login and main window) |
| `monitor.py` | Watches for devices and applies the rules |
| `usb_scan.py` | Reads the list of connected USB devices from Windows |
| `scanner.py` | Scan checks (device type, Windows Defender, suspicious files) |
| `db.py` | SQLite database: admin account, device lists, log |
| `reset_admin.py` | Offline admin reset (needs Windows Administrator) |
| `enable_all.py` | Recovery: switches all disabled USB devices back on |
| `manage.py` | Early command-line tool for managing devices |
| `USB_detect.py`, `test_db.py`, `check.py` | Early test scripts |
| `requirements.txt` | Python libraries needed |

## If something goes wrong

- **A device stays disabled** after closing the application: run `python enable_all.py` as Administrator, or enable it in Device Manager.
- **Forgot the admin password:** run `python reset_admin.py` as Administrator and type `RESET`. A backup of the database is made first, the device lists and the log are kept, and you can then create a new admin account.

## Building an executable (optional)

Inside the activated venv:

```
pip install pyinstaller
pyinstaller --onefile --noconsole --uac-admin --collect-all customtkinter gui.py
```

The `.exe` is created in the `dist` folder. The database file is created next to it.

## Limitations

- Protection works only while the application is running. Devices that were blocked stay blocked until the application runs again or `enable_all.py` is used.
- A user with Windows administrator rights on the computer can bypass the application or use the reset script.
- The log is stored in a local database file and could be edited or deleted by someone with access to the computer.
- Devices are identified by their IDs, which a skilled attacker could copy. Devices without a real serial number are less reliable to identify.
- The scan depends on Windows Defender's known signatures, so brand-new malware may not be detected.
- Works on a single computer and on Windows only.

## Future scope

- Run the monitor as a Windows service
- Recovery key for password reset
- Tamper-proof logging
- Support for other connections (Bluetooth, SD cards)
- Central management of several computers and alerts to the admin

## Safety notes

- Test blocking with a pendrive first, and keep `SAFE_MODE = True` in `monitor.py` while testing.
- Never commit or share `usb_security.db`. It contains the admin password hash and device details.
