import subprocess
import json 
import time
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
    if isinstance(data, dict):      # only one device found
        data = [data]

    devices = {}
    for item in data:
        instance_id = item["InstanceId"]
        if "&MI_" in instance_id.upper():   # skip sub-parts of a device
            continue

        parts = instance_id.split("\\")     # e.g. USB \ VID_xxxx&PID_xxxx \ serial
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

def show(label, device):
    print(f"\n[{label}] {device['name']}")
    print(f"   Type      : {device['type']}")
    print(f"   Vendor ID : {device['vendor_id']}")
    print(f"   Product ID: {device['product_id']}")
    print(f"   Serial    : {device['serial']}")

print("Watching for USB devices... (press Ctrl+C to stop)")
known = get_usb_devices()
for dev in known.values():
    show("ALREADY CONNECTED", dev)

try:
    while True:
        time.sleep(2)
        current = get_usb_devices()
        for key in current:
            if key not in known:
                show("PLUGGED IN", current[key])
        for key in known:
            if key not in current:
                show("REMOVED", known[key])
        known = current
except KeyboardInterrupt:
    print("\nStopped.")