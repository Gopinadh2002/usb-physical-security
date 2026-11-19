import db
for status in ("whitelist", "blacklist", "pending"):
    print(status.upper())
    for d in db.list_devices(status):
        print("   ", d)