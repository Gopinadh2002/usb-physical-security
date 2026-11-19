import db

db.init_db()

if db.create_admin("admin", "MyStrongPass@123"):
    print("Admin created.")
else:
    print("Admin already exists.")

print("Correct password:", db.check_login("admin", "MyStrongPass@123"))
print("Wrong password  :", db.check_login("admin", "wrongpass"))

db.set_status("1234", "ABCD", "SERIAL001", "Test Pendrive", "whitelist")
db.set_status("9999", "FFFF", "BAD001", "Banned Device", "blacklist")
db.add_log("TEST", "1234", "ABCD", "SERIAL001", "Test Pendrive", "database test")

print("Status of test pendrive:", db.get_status("1234", "ABCD", "SERIAL001"))
print("Whitelist:", db.list_devices("whitelist"))
print("Blacklist:", db.list_devices("blacklist"))
print("Log:", db.get_log())