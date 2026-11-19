import os
import re
import json
import time
import subprocess
import db

DEFENDER = r"C:\Program Files\Windows Defender\MpCmdRun.exe"

SUSPICIOUS_EXT = {".exe", ".bat", ".cmd", ".ps1", ".vbs", ".js", ".lnk",
                  ".scr", ".msi", ".com", ".jar", ".hta", ".dll"}
DOUBLE_EXT = re.compile(
    r"\.(pdf|docx?|xlsx?|pptx?|txt|jpe?g|png|mp4|zip)\.(exe|bat|cmd|scr|vbs|js|lnk|ps1)$",
    re.IGNORECASE)


def ps(command, timeout=60):
    r = subprocess.run(["powershell", "-NoProfile", "-Command", command],
                       capture_output=True, text=True, timeout=timeout)
    return r.stdout.strip()


# ---------- Check 1: what kind of device is it? ----------

def check_device_type(vid, pid):
    """Looks for a 'storage device that also acts like a keyboard' (BadUSB sign)."""
    out = ps("Get-PnpDevice -PresentOnly | Where-Object { $_.InstanceId -like "
             f"'*VID_{vid}&PID_{pid}*' }} | Select-Object FriendlyName, Class | ConvertTo-Json"
             .replace("}}", "}"))
    if not out:
        return ["Could not read device details"]
    data = json.loads(out)
    if isinstance(data, dict):
        data = [data]

    classes = {(d["Class"] or "") for d in data}
    names = " ".join((d["FriendlyName"] or "") for d in data).lower()
    has_storage = "mass storage" in names
    has_input = bool(classes & {"HIDClass", "Keyboard"})

    problems = []
    if has_storage and has_input:
        problems.append("Storage device that ALSO acts as keyboard/input (possible BadUSB)")
    return problems


# ---------- Check 2: find the drive and scan with Windows Defender ----------

def find_usb_drives():
    out = ps("Get-Disk | Where-Object { $_.BusType -eq 'USB' } | Get-Partition | "
             "Get-Volume | Where-Object { $_.DriveLetter } | "
             "Select-Object -ExpandProperty DriveLetter")
    return [line.strip() + ":\\" for line in out.splitlines() if line.strip()]


def defender_scan(path):
    """Returns (True/False/None, message). None means the scan could not finish."""
    if not os.path.exists(DEFENDER):
        return None, "Windows Defender command-line tool not found"
    try:
        r = subprocess.run([DEFENDER, "-Scan", "-ScanType", "3", "-File", path],
                           capture_output=True, text=True, timeout=600)
    except subprocess.TimeoutExpired:
        return None, "Defender scan timed out"
    if r.returncode == 0:
        return True, "no threats found"
    if r.returncode == 2:
        return False, "THREAT FOUND"
    return None, f"scan could not finish (code {r.returncode})"


# ---------- Check 3: suspicious files ----------

def file_check(path, max_files=5000):
    flags, count = [], 0
    for root, dirs, files in os.walk(path):
        dirs[:] = [d for d in dirs if d != "System Volume Information"]
        for name in files:
            count += 1
            if count > max_files:
                flags.append(f"Stopped after {max_files} files")
                return flags
            full = os.path.join(root, name)
            ext = os.path.splitext(name)[1].lower()
            try:
                hidden = os.stat(full).st_file_attributes & 2
            except OSError:
                hidden = 0
            if name.lower() == "autorun.inf":
                flags.append(f"autorun.inf found: {full}")
            elif DOUBLE_EXT.search(name):
                flags.append(f"Double extension: {full}")
            elif ext in SUSPICIOUS_EXT:
                flags.append(f"Program/script/shortcut: {full}")
            elif hidden:
                flags.append(f"Hidden file: {full}")
            if len(flags) >= 50:
                flags.append("More than 50 flags, list shortened")
                return flags
    return flags


# ---------- Put it together ----------

def scan_device(vid, pid, serial, name):
    instance_id = f"USB\\VID_{vid}&PID_{pid}\\{serial}"
    print(f"\nScanning {name} ...")

    problems = check_device_type(vid, pid)
    print("Check 1 (device type):", problems or "OK")

    flags, defender_msg = [], "not run"
    ps(f"Enable-PnpDevice -InstanceId '{instance_id}' -Confirm:$false")
    print("Device switched on temporarily, waiting for the drive...")
    time.sleep(8)

    try:
        drives = find_usb_drives()
        if not drives:
            print("No drive letter found (it may not be a storage device).")
        for drive in drives:
            print(f"Scanning drive {drive} with Windows Defender (can take a while)...")
            ok, msg = defender_scan(drive)
            defender_msg = msg
            if ok is False:
                problems.append("Windows Defender: THREAT FOUND")
            elif ok is None:
                problems.append("Windows Defender scan incomplete: " + msg)
            print("Check 2 (Defender):", msg)

            flags += file_check(drive)
        print("Check 3 (suspicious files):", flags or "none found")
    finally:
        ps(f"Disable-PnpDevice -InstanceId '{instance_id}' -Confirm:$false")
        print("Device switched off again.")

    verdict = "SUSPICIOUS" if (problems or flags) else "CLEAN"
    details = f"{verdict}; defender: {defender_msg}; flags: {len(flags)}; problems: {problems}"
    db.add_log("SCAN", vid, pid, serial, name, details)
    print(f"\nRESULT: {verdict}")
    return verdict