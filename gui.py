import queue
import threading
import contextlib
import time
import tkinter as tk
from tkinter import ttk, messagebox
import customtkinter as ctk
import db
import scanner
import monitor

ctk.set_appearance_mode("light")
ctk.set_default_color_theme("blue")
db.init_db()

MAX_TRIES = 5        # wrong passwords allowed before a short lock
LOCK_SECONDS = 30


class QueueWriter:
    """Lets us show scanner.py's print() output inside the window."""
    def __init__(self, q):
        self.q = q

    def write(self, text):
        if text:
            self.q.put(text)

    def flush(self):
        pass


# ======================= LOGIN WINDOW =======================

class LoginWindow(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("USB Physical Security - Login")
        self.geometry("420x470")
        self.resizable(False, False)
        self.username = None
        self.failed = 0
        self.locked_until = 0
        self.first_run = not db.admin_exists()

        title = "Create Administrator Account" if self.first_run else "Administrator Login"
        ctk.CTkLabel(self, text="USB Physical Security",
                     font=("Arial", 22, "bold")).pack(pady=(30, 4))
        ctk.CTkLabel(self, text=title, font=("Arial", 15)).pack(pady=(0, 20))

        self.user = ctk.CTkEntry(self, placeholder_text="Username", width=260)
        self.user.pack(pady=6)
        self.pw = ctk.CTkEntry(self, placeholder_text="Password", show="*", width=260)
        self.pw.pack(pady=6)
        if self.first_run:
            self.pw2 = ctk.CTkEntry(self, placeholder_text="Confirm password",
                                    show="*", width=260)
            self.pw2.pack(pady=6)

        self.msg = ctk.CTkLabel(self, text="", text_color="red", wraplength=300)
        self.msg.pack(pady=8)
        ctk.CTkButton(self, text="Create account" if self.first_run else "Log in",
                      width=260, command=self.submit).pack(pady=6)
        self.bind("<Return>", lambda e: self.submit())

    def say(self, text):
        self.msg.configure(text=text)

    def submit(self):
        u, p = self.user.get().strip(), self.pw.get()

        if self.first_run:
            if not u:
                return self.say("Enter a username.")
            if len(p) < 8:
                return self.say("Password must be at least 8 characters.")
            if p != self.pw2.get():
                return self.say("Passwords do not match.")
            db.create_admin(u, p)
            db.add_log("ADMIN_CREATED", details=f"admin account '{u}' created")
            return self.success(u)

        wait = int(self.locked_until - time.time())
        if wait > 0:
            return self.say(f"Too many wrong attempts. Wait {wait} seconds.")

        if db.check_login(u, p):
            db.add_log("LOGIN_OK", details=f"admin '{u}' logged in")
            self.success(u)
        else:
            self.failed += 1
            db.add_log("LOGIN_FAILED", details=f"failed login attempt for '{u}'")
            if self.failed >= MAX_TRIES:
                self.failed = 0
                self.locked_until = time.time() + LOCK_SECONDS
                self.say(f"Too many wrong attempts. Locked for {LOCK_SECONDS} seconds.")
            else:
                self.say("Wrong username or password.")

    def success(self, username):
        self.username = username
        self.destroy()


# ======================= MAIN WINDOW =======================

class MainWindow(ctk.CTk):
    def __init__(self, username):
        super().__init__()
        self.title("USB Physical Security")
        self.geometry("1000x680")
        self.username = username
        self.q = queue.Queue()
        self.scanning = False

        self.stop_event = threading.Event()
        threading.Thread(target=monitor.run,
                         args=(self.stop_event, self.monitor_say),
                         daemon=True).start()
        self.protocol("WM_DELETE_WINDOW", self.on_close)

        top = ctk.CTkFrame(self, fg_color="transparent")
        top.pack(fill="x", padx=15, pady=(10, 0))
        ctk.CTkLabel(top, text=f"Logged in as: {username}",
                     font=("Arial", 14, "bold")).pack(side="left")
        ctk.CTkLabel(top, text="   Protection: ACTIVE", text_color="green",
                     font=("Arial", 14, "bold")).pack(side="left")
        ctk.CTkButton(top, text="Change password", width=140,
                      command=self.change_password).pack(side="right")

        self.tabs = ctk.CTkTabview(self)
        self.tabs.pack(fill="both", expand=True, padx=15, pady=10)

        self.trees = {}
        for status, label in (("pending", "Pending"),
                              ("whitelist", "Whitelist"),
                              ("blacklist", "Blacklist")):
            tab = self.tabs.add(label)
            self.trees[status] = self.make_device_tab(tab, status)

        log_tab = self.tabs.add("Log")
        cols = ("time", "device", "vid", "pid", "action", "details")
        self.log_tree = ttk.Treeview(log_tab, columns=cols, show="headings", height=12)
        for c, t, w in zip(cols, ("Time", "Device", "Vendor ID", "Product ID",
                                  "Action", "Details"),
                           (140, 170, 80, 80, 120, 320)):
            self.log_tree.heading(c, text=t)
            self.log_tree.column(c, width=w, anchor="w")
        self.log_tree.pack(fill="both", expand=True, pady=5)
        ctk.CTkButton(log_tab, text="Refresh", width=90,
                      command=self.refresh).pack(anchor="w", padx=3)

        ctk.CTkLabel(self, text="Scan output:", anchor="w").pack(fill="x", padx=15)
        self.output = ctk.CTkTextbox(self, height=130)
        self.output.pack(fill="x", padx=15, pady=(0, 12))

        self.refresh()
        self.after(5000, self.auto_refresh)
        self.after(200, self.poll_output)

    def monitor_say(self, text):
        self.q.put(text + "\n")

    def on_close(self):
        self.stop_event.set()
        self.destroy()

    # ---------- building the device tabs ----------

    def make_device_tab(self, tab, status):
        cols = ("name", "vid", "pid", "serial", "added")
        tree = ttk.Treeview(tab, columns=cols, show="headings",
                            selectmode="browse", height=10)
        for c, t, w in zip(cols, ("Name", "Vendor ID", "Product ID", "Serial", "Added on"),
                           (250, 90, 90, 240, 160)):
            tree.heading(c, text=t)
            tree.column(c, width=w, anchor="w")
        tree.pack(fill="both", expand=True, pady=5)

        bar = ctk.CTkFrame(tab, fg_color="transparent")
        bar.pack(fill="x")
        ctk.CTkButton(bar, text="Scan", width=90,
                      command=lambda: self.scan(status)).pack(side="left", padx=3)
        if status != "whitelist":
            ctk.CTkButton(bar, text="Whitelist", width=90, fg_color="green",
                          command=lambda: self.move(status, "whitelist")).pack(side="left", padx=3)
        if status != "blacklist":
            ctk.CTkButton(bar, text="Blacklist", width=90, fg_color="red",
                          command=lambda: self.move(status, "blacklist")).pack(side="left", padx=3)
        ctk.CTkButton(bar, text="Remove", width=90, fg_color="gray",
                      command=lambda: self.remove(status)).pack(side="left", padx=3)
        ctk.CTkButton(bar, text="Refresh", width=90,
                      command=self.refresh).pack(side="left", padx=3)
        return tree

    # ---------- reading the selection ----------

    def selected(self, status):
        tree = self.trees[status]
        sel = tree.selection()
        if not sel:
            messagebox.showinfo("Select a device", "Click a device in the list first.")
            return None
        vid, pid, serial = sel[0].split("|", 2)
        name = tree.item(sel[0])["values"][0]
        return vid, pid, serial, str(name)

    # ---------- actions ----------

    def move(self, status, new_status):
        dev = self.selected(status)
        if not dev:
            return
        vid, pid, serial, name = dev
        db.set_status(vid, pid, serial, name, new_status)
        db.add_log("ADMIN_DECISION", vid, pid, serial, name,
                   f"{self.username} moved from {status} to {new_status}")
        self.refresh()

    def remove(self, status):
        dev = self.selected(status)
        if not dev:
            return
        vid, pid, serial, name = dev
        if messagebox.askyesno("Remove", f"Remove '{name}' from the {status}?"):
            db.remove_device(vid, pid, serial)
            db.add_log("ADMIN_DECISION", vid, pid, serial, name,
                       f"{self.username} removed device from {status}")
            self.refresh()

    def scan(self, status):
        dev = self.selected(status)
        if not dev:
            return
        if self.scanning:
            messagebox.showinfo("Please wait", "A scan is already running.")
            return
        self.scanning = True
        self.output.delete("1.0", "end")

        def work():
            try:
                with contextlib.redirect_stdout(QueueWriter(self.q)):
                    scanner.scan_device(*dev)
            except Exception as e:
                self.q.put(f"\nScan failed: {e}\n")
            finally:
                monitor.paused.clear()
                self.q.put("\n--- scan finished ---\n")
                self.q.put(None)

        threading.Thread(target=work, daemon=True).start()

    def change_password(self):
        win = ctk.CTkToplevel(self)
        win.title("Change password")
        win.geometry("340x340")
        win.after(150, win.grab_set)

        old = ctk.CTkEntry(win, placeholder_text="Current password", show="*", width=240)
        new = ctk.CTkEntry(win, placeholder_text="New password (8+ characters)",
                           show="*", width=240)
        new2 = ctk.CTkEntry(win, placeholder_text="Confirm new password",
                            show="*", width=240)
        msg = ctk.CTkLabel(win, text="", text_color="red", wraplength=280)
        for w in (old, new, new2):
            w.pack(pady=8)
        old.pack_configure(pady=(30, 8))
        msg.pack(pady=4)

        def save():
            if len(new.get()) < 8:
                return msg.configure(text="New password must be at least 8 characters.")
            if new.get() != new2.get():
                return msg.configure(text="New passwords do not match.")
            if db.change_password(self.username, old.get(), new.get()):
                db.add_log("PASSWORD_CHANGED", details=f"'{self.username}' changed password")
                win.destroy()
                messagebox.showinfo("Done", "Password changed.")
                self.refresh()
            else:
                msg.configure(text="Current password is wrong.")

        ctk.CTkButton(win, text="Save", width=240, command=save).pack(pady=10)

    # ---------- keeping the screen up to date ----------

    def refresh(self):
        for status, tree in self.trees.items():
            keep = tree.selection()
            tree.delete(*tree.get_children())
            for d in db.list_devices(status):      # vid, pid, serial, name, added
                iid = f"{d[0]}|{d[1]}|{d[2]}"
                tree.insert("", "end", iid=iid, values=(d[3], d[0], d[1], d[2], d[4]))
            for k in keep:
                if tree.exists(k):
                    tree.selection_set(k)

        self.log_tree.delete(*self.log_tree.get_children())
        for row in db.get_log(200):                # time, name, vid, pid, action, details
            self.log_tree.insert("", "end", values=row)

    def auto_refresh(self):
        self.refresh()
        self.after(5000, self.auto_refresh)

    def poll_output(self):
        try:
            while True:
                item = self.q.get_nowait()
                if item is None:
                    self.scanning = False
                    self.refresh()
                else:
                    self.output.insert("end", item)
                    self.output.see("end")
        except queue.Empty:
            pass
        self.after(200, self.poll_output)


if __name__ == "__main__":
    login = LoginWindow()
    login.mainloop()
    if login.username:
        MainWindow(login.username).mainloop()