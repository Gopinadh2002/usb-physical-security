import sys
import time
import subprocess
import threading
import db
from usb_scan import get_usb_devices

ENFORCE = True
SAFE_MODE = True
SAFE_CLASSES = ("HIDClass", "Keyboard", "Mouse")

paused = threading.Event()     # the scanner sets this so the monitor does not interfere
blocked_by_us = {}


def ps(command):
    subprocess.run(["powershell", "-NoProfile", "-Command", command],
                   capture_output=True, text=True)


def block(instance_id, dev=None, say=print):
    if not ENFORCE:
        return
    if SAFE_MODE and dev and dev["type"] in SAFE_CLASSES:
        say(f"   (safe mode: not blocking {dev['name']})")
        return
    ps(f"Disable-PnpDevice -InstanceId '{instance_id}' -Confirm:$false")


def unblock(instance_id):
    if ENFORCE:
        ps(f"Enable-PnpDevice -InstanceId '{instance_id}' -Confirm:$false")


def handle(instance_id, dev, say=print):
    vid, pid, ser, name = dev["vendor_id"], dev["product_id"], dev["serial"], dev["name"]
    status = db.get_status(vid, pid, ser)

    if status == "whitelist":
        action, details = "ALLOWED", "device is on whitelist"
        unblock(instance_id)
    elif status == "blacklist":
        action, details = "BLOCKED", "device is on blacklist"
        block(instance_id, dev, say)
    else:
        db.set_status(vid, pid, ser, name, "pending")
        action, details = "BLOCKED", "unknown device, waiting for admin"
        block(instance_id, dev, say)
        blocked_by_us[instance_id] = dev

    db.add_log(action, vid, pid, ser, name, details)
    say(f"[{action}] {name}  ({vid}:{pid})  - {details}")


def baseline(say=print):
    for dev in get_usb_devices().values():
        db.set_status(dev["vendor_id"], dev["product_id"], dev["serial"],
                      dev["name"], "whitelist")
        db.add_log("BASELINE", dev["vendor_id"], dev["product_id"],
                   dev["serial"], dev["name"], "trusted at setup")
        say(f"Trusted: {dev['name']}")


def run(stop_event, say=print):
    """Watches USB devices until stop_event is set."""
    say("Protection started.")
    db.add_log("PROTECTION_STARTED", details="monitor started")
    known = {}

    try:
        for key, dev in get_usb_devices().items():
            handle(key, dev, say)
        known = get_usb_devices()
    except Exception as e:
        say(f"Startup error: {e}")

    while not stop_event.wait(2):          # waits 2 seconds, stops at once if asked
        if paused.is_set():
            continue
        try:
            current = get_usb_devices()

            for key, dev in current.items():              # newly plugged in
                if key not in known:
                    handle(key, dev, say)

            for key, dev in current.items():              # moved to blacklist by admin
                if key in known and key not in blocked_by_us:
                    if db.get_status(dev["vendor_id"], dev["product_id"],
                                     dev["serial"]) == "blacklist":
                        block(key, dev, say)
                        blocked_by_us[key] = dev
                        db.add_log("BLOCKED", dev["vendor_id"], dev["product_id"],
                                   dev["serial"], dev["name"],
                                   "moved to blacklist by admin")
                        say(f"[BLOCKED] {dev['name']} - moved to blacklist by admin")

            for key in list(blocked_by_us):               # approved by admin
                if key not in current:
                    del blocked_by_us[key]
                    continue
                dev = blocked_by_us[key]
                if db.get_status(dev["vendor_id"], dev["product_id"],
                                 dev["serial"]) == "whitelist":
                    unblock(key)
                    db.add_log("ALLOWED", dev["vendor_id"], dev["product_id"],
                               dev["serial"], dev["name"], "approved by admin")
                    say(f"[ALLOWED] {dev['name']} - approved by admin")
                    del blocked_by_us[key]

            known = current
        except Exception as e:
            say(f"Monitor error: {e}")

    db.add_log("PROTECTION_STOPPED", details="monitor stopped")
    say("Protection stopped.")


if __name__ == "__main__":
    db.init_db()
    if "--baseline" in sys.argv:
        baseline()
    else:
        stop = threading.Event()
        try:
            run(stop)
        except KeyboardInterrupt:
            stop.set()