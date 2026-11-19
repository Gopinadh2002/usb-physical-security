import db
import scanner

db.init_db()

LISTS = ["pending", "whitelist", "blacklist"]

all_devices = []
for status in LISTS:
    for d in db.list_devices(status):
        all_devices.append((status, d))

if not all_devices:
    print("No devices saved yet.")
else:
    for i, (status, d) in enumerate(all_devices, 1):
        print(f"{i}. [{status.upper():9}] {d[3]}  (VID {d[0]}, PID {d[1]}, serial {d[2]})")

    choice = input("\nNumber of the device to change (Enter to quit): ").strip()
    if choice.isdigit() and 1 <= int(choice) <= len(all_devices):
        old_status, d = all_devices[int(choice) - 1]
        answer = input("Type S to scan first, W for whitelist, B for blacklist: ").strip().upper()

        if answer == "S":
            scanner.scan_device(d[0], d[1], d[2], d[3])
            answer = input("\nNow type W, B, or press Enter to leave it as it is: ").strip().upper()

        if answer in ("W", "B"):
            new_status = "whitelist" if answer == "W" else "blacklist"
            db.set_status(d[0], d[1], d[2], d[3], new_status)
            db.add_log("ADMIN_DECISION", d[0], d[1], d[2], d[3],
                       f"moved from {old_status} to {new_status}")
            print(f"Done: {d[3]} moved from {old_status} to {new_status}.")