import subprocess
import json
import re


def get_usb_devices():
    """Ask Windows for all connected USB devices and return them as a dictionary."""
    command = [
        "powershell", "-NoProfile", "-Command",
        "Get-PnpDevice -PresentOnly | "
        "Where-Object { $_.InstanceId -like 'USB*VID_*' } | "
        "Select-Object FriendlyName, Class, InstanceId | ConvertTo-Json"
    ]
    result = subprocess.run(command, capture_output=True, text=True)
    output = result.stdout.strip()
    if not output:
        return {}

    data = json.loads(output)
    if isinstance(data, dict):
        data = [data]

    devices = {}
    for item in data:
        instance_id = item["InstanceId"]
        if "&MI_" in instance_id.upper():
            continue

        parts = instance_id.split("\\")
        if len(parts) < 3:
            continue

        ids = re.search(r"VID_([0-9A-Fa-f]{4})&PID_([0-9A-Fa-f]{4})", parts[1])
        if not ids:
            continue

        devices[instance_id] = {
            "name": item["FriendlyName"] or "Unknown device",
            "type": item["Class"] or "Unknown",
            "vendor_id": ids.group(1).upper(),
            "product_id": ids.group(2).upper(),
            "serial": parts[2],
        }
    return devices