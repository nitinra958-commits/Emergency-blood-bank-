"""Emergency Blood Bank Resource Management and Process Scheduling System.
Academic DBMS + OS PBL. Uses Tkinter and SQLite; no third-party packages.
Not a real clinical or transfusion decision system.
"""
import csv
import hashlib
import hmac
import os
import secrets
import shutil
import sqlite3
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from datetime import datetime

APP_TITLE = "Emergency Blood Bank Resource Management and Process Scheduling System"
DB_NAME = "emergency_blood_bank.db"
BLOOD_GROUPS = ["A+", "A-", "B+", "B-", "AB+", "AB-", "O+", "O-"]
URGENCIES = ["Critical", "High", "Normal"]
ROLES = ["Admin", "Staff", "Requester"]
PBKDF2_ROUNDS = 240_000


def now_text():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def hash_password(password, salt=None):
    salt = salt or secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, PBKDF2_ROUNDS)
    return salt.hex() + "$" + digest.hex()


def verify_password(password, stored):
    try:
        salt_hex, digest_hex = stored.split("$", 1)
        digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), bytes.fromhex(salt_hex), PBKDF2_ROUNDS)
        return hmac.compare_digest(digest.hex(), digest_hex)
    except (ValueError, TypeError):
        return False


def schedule_processes(burst_times, algorithm="FCFS", priorities=None, quantum=2):
    """Return (rows, gantt, averages) for processes with arrival time 0.
    rows are dicts with pid, bt, ct, tat, wt, priority. RR supports a positive quantum.
    """
    if not burst_times or any(not isinstance(b, int) or b <= 0 for b in burst_times):
        raise ValueError("Burst times must be positive integers.")
    n = len(burst_times)
    priorities = priorities or [1 + (i % 3) for i in range(n)]
    processes = [{"pid": i + 1, "bt": b, "priority": priorities[i]} for i, b in enumerate(burst_times)]
    gantt = []
    completion = {}
    if algorithm == "FCFS":
        order = processes
        t = 0
        for p in order:
            t += p["bt"]
            completion[p["pid"]] = t
            gantt.append((p["pid"], t - p["bt"], t))
    elif algorithm in ("SJF", "Priority"):
        key = (lambda p: (p["bt"], p["pid"])) if algorithm == "SJF" else (lambda p: (p["priority"], p["pid"]))
        order = sorted(processes, key=key)
        t = 0
        for p in order:
            start = t
            t += p["bt"]
            completion[p["pid"]] = t
            gantt.append((p["pid"], start, t))
    elif algorithm == "Round Robin":
        if not isinstance(quantum, int) or quantum <= 0:
            raise ValueError("Time quantum must be a positive integer.")
        remaining = {p["pid"]: p["bt"] for p in processes}
        t = 0
        queue = [p["pid"] for p in processes]
        while queue:
            pid = queue.pop(0)
            run = min(quantum, remaining[pid])
            start = t
            t += run
            remaining[pid] -= run
            gantt.append((pid, start, t))
            if remaining[pid] == 0:
                completion[pid] = t
            else:
                queue.append(pid)
    else:
        raise ValueError("Unknown scheduling algorithm.")
    rows = []
    for p in processes:
        ct = completion[p["pid"]]
        rows.append({"pid": p["pid"], "bt": p["bt"], "ct": ct, "tat": ct, "wt": ct - p["bt"], "priority": p["priority"]})
    avg_wt = sum(r["wt"] for r in rows) / n
    avg_tat = sum(r["tat"] for r in rows) / n
    return rows, gantt, {"waiting": avg_wt, "turnaround": avg_tat}


class BloodBankApp:
    def __init__(self, root):
        self.root = root
        self.root.title(APP_TITLE)
        self.root.geometry("1180x760")
        self.root.minsize(980, 650)
        self.root.configure(bg="#f5f7fb")
        self.conn = sqlite3.connect(DB_NAME)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys = ON")
        self.conn.execute("PRAGMA journal_mode = WAL")
        self.current_user = None
        self.create_tables()
        self.seed_inventory()
        self.seed_accounts()
        self.show_login()
        self.root.protocol("WM_DELETE_WINDOW", self.close)

    def create_tables(self):
        self.conn.executescript("""
        CREATE TABLE IF NOT EXISTS users(
          user_id INTEGER PRIMARY KEY AUTOINCREMENT,
          username TEXT NOT NULL UNIQUE COLLATE NOCASE,
          password_hash TEXT NOT NULL,
          role TEXT NOT NULL CHECK(role IN ('Admin','Staff','Requester')),
          active INTEGER NOT NULL DEFAULT 1 CHECK(active IN (0,1)),
          created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS donors(
          donor_id INTEGER PRIMARY KEY AUTOINCREMENT,
          donor_name TEXT NOT NULL,
          blood_group TEXT NOT NULL CHECK(blood_group IN ('A+','A-','B+','B-','AB+','AB-','O+','O-')),
          phone TEXT NOT NULL,
          city TEXT NOT NULL,
          created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS inventory(
          blood_group TEXT PRIMARY KEY CHECK(blood_group IN ('A+','A-','B+','B-','AB+','AB-','O+','O-')),
          units INTEGER NOT NULL DEFAULT 0 CHECK(units >= 0),
          updated_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS requests(
          request_id INTEGER PRIMARY KEY AUTOINCREMENT,
          patient_name TEXT NOT NULL,
          blood_group TEXT NOT NULL CHECK(blood_group IN ('A+','A-','B+','B-','AB+','AB-','O+','O-')),
          units INTEGER NOT NULL CHECK(units > 0),
          urgency TEXT NOT NULL CHECK(urgency IN ('Critical','High','Normal')),
          request_time TEXT NOT NULL,
          status TEXT NOT NULL DEFAULT 'Pending' CHECK(status IN ('Pending','Fulfilled','Cancelled')),
          created_by INTEGER REFERENCES users(user_id),
          handled_by TEXT,
          handled_at TEXT
        );
        CREATE TABLE IF NOT EXISTS audit_log(
          log_id INTEGER PRIMARY KEY AUTOINCREMENT,
          username TEXT NOT NULL,
          action TEXT NOT NULL,
          details TEXT NOT NULL,
          event_time TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_requests_status_time ON requests(status, request_time);
        CREATE INDEX IF NOT EXISTS idx_requests_urgency ON requests(urgency);
        CREATE INDEX IF NOT EXISTS idx_donors_group ON donors(blood_group);
        CREATE INDEX IF NOT EXISTS idx_audit_time ON audit_log(event_time);
        """)
        # Upgrade databases created by Phase 2 or an earlier Final Phase build.
        # CREATE TABLE IF NOT EXISTS does not add columns to existing tables.
        self._migrate_legacy_schema()
        self.conn.commit()

    def _migrate_legacy_schema(self):
        """Add columns required by the current app without deleting existing records."""
        migrations = {
            "donors": {
                "created_at": "TEXT",
            },
            "inventory": {
                "updated_at": "TEXT",
            },
            "requests": {
                "created_by": "INTEGER REFERENCES users(user_id)",
                "handled_by": "TEXT",
                "handled_at": "TEXT",
            },
        }
        for table, columns in migrations.items():
            existing = {row[1] for row in self.conn.execute(f"PRAGMA table_info({table})")}
            for column, definition in columns.items():
                if column not in existing:
                    self.conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")
        # Existing Phase 2 records predate these timestamp fields. Backfill them
        # with a migration timestamp so the UI never displays NULL timestamps.
        stamp = now_text()
        self.conn.execute("UPDATE donors SET created_at=? WHERE created_at IS NULL OR created_at=''", (stamp,))
        self.conn.execute("UPDATE inventory SET updated_at=? WHERE updated_at IS NULL OR updated_at=''", (stamp,))
        self.conn.execute("UPDATE requests SET handled_by='Legacy record' WHERE handled_by IS NULL AND status <> 'Pending'")

    def seed_inventory(self):
        demo = {"A+": 8, "A-": 3, "B+": 6, "B-": 2, "AB+": 4, "AB-": 1, "O+": 10, "O-": 3}
        with self.conn:
            for group, units in demo.items():
                self.conn.execute("INSERT OR IGNORE INTO inventory(blood_group,units,updated_at) VALUES(?,?,?)", (group, units, now_text()))

    def seed_accounts(self):
        # These accounts are for a local classroom demo. Change passwords after first login.
        defaults = [("admin", "Admin@123", "Admin"), ("staff", "Staff@123", "Staff"), ("requester", "Request@123", "Requester")]
        with self.conn:
            for username, password, role in defaults:
                self.conn.execute("INSERT OR IGNORE INTO users(username,password_hash,role,created_at) VALUES(?,?,?,?)",
                                  (username, hash_password(password), role, now_text()))

    def audit(self, action, details):
        username = self.current_user["username"] if self.current_user else "SYSTEM"
        with self.conn:
            self.conn.execute("INSERT INTO audit_log(username,action,details,event_time) VALUES(?,?,?,?)",
                              (username, action, str(details), now_text()))

    def clear(self):
        for child in self.root.winfo_children():
            child.destroy()

    def show_login(self):
        self.clear()
        outer = tk.Frame(self.root, bg="#f5f7fb")
        outer.pack(fill="both", expand=True)
        banner = tk.Frame(outer, bg="#7f1d1d", padx=35, pady=30)
        banner.pack(fill="x")
        tk.Label(banner, text="EMERGENCY BLOOD BANK", font=("Arial", 23, "bold"), fg="white", bg="#7f1d1d").pack()
        tk.Label(banner, text="Resource Management & Process Scheduling System", font=("Arial", 12), fg="#fee2e2", bg="#7f1d1d").pack(pady=(8, 0))
        card = ttk.LabelFrame(outer, text="Secure Sign In", padding=24)
        card.pack(pady=35, ipadx=30, ipady=15)
        self.login_username = tk.StringVar(value="")
        self.login_password = tk.StringVar(value="")
        ttk.Label(card, text="Username").grid(row=0, column=0, sticky="w", pady=7)
        username_entry = ttk.Entry(card, textvariable=self.login_username, width=32)
        username_entry.grid(row=0, column=1, padx=(15, 0), pady=7)
        ttk.Label(card, text="Password").grid(row=1, column=0, sticky="w", pady=7)
        password_entry = ttk.Entry(card, textvariable=self.login_password, show="•", width=32)
        password_entry.grid(row=1, column=1, padx=(15, 0), pady=7)
        ttk.Button(card, text="Login", command=self.login).grid(row=2, column=0, columnspan=2, sticky="ew", pady=(16, 8))
        password_entry.bind("<Return>", lambda _e: self.login())
        username_entry.bind("<Return>", lambda _e: password_entry.focus_set())
        ttk.Label(card, text="Local demo accounts are listed in README.md.", foreground="#555").grid(row=3, column=0, columnspan=2, pady=(6, 0))
        tk.Label(outer, text="ACADEMIC SIMULATION ONLY — sample inventory, not for clinical decisions", bg="#f5f7fb", fg="#7f1d1d", font=("Arial", 10, "bold")).pack(side="bottom", pady=18)
        username_entry.focus_set()

    def login(self):
        username = self.login_username.get().strip()
        password = self.login_password.get()
        row = self.conn.execute("SELECT * FROM users WHERE username=? COLLATE NOCASE AND active=1", (username,)).fetchone()
        if not row or not verify_password(password, row["password_hash"]):
            self.audit("LOGIN_FAILED", f"Failed login attempt for username '{username[:50]}'")
            messagebox.showerror("Login failed", "Invalid username or password, or account is disabled.")
            return
        self.current_user = dict(row)
        self.audit("LOGIN_SUCCESS", f"Signed in with role {row['role']}")
        self.build_main_ui()

    def build_main_ui(self):
        self.clear()
        role = self.current_user["role"]
        header = tk.Frame(self.root, bg="#7f1d1d", padx=18, pady=13)
        header.pack(fill="x")
        left = tk.Frame(header, bg="#7f1d1d")
        left.pack(side="left", fill="x", expand=True)
        tk.Label(left, text="EMERGENCY BLOOD BANK RESOURCE MANAGEMENT", bg="#7f1d1d", fg="white", font=("Arial", 16, "bold")).pack(anchor="w")
        tk.Label(left, text="AND PROCESS SCHEDULING SYSTEM  |  DBMS + OS PBL", bg="#7f1d1d", fg="#fee2e2", font=("Arial", 9)).pack(anchor="w", pady=(3, 0))
        right = tk.Frame(header, bg="#7f1d1d")
        right.pack(side="right")
        tk.Label(right, text=f"{self.current_user['username']}  •  {role}", bg="#7f1d1d", fg="white", font=("Arial", 10, "bold")).pack(pady=(0, 6))
        actions = tk.Frame(right, bg="#7f1d1d")
        actions.pack(anchor="e")
        ttk.Button(actions, text="Change Password", command=self.change_password).pack(side="left", padx=(0, 5))
        ttk.Button(actions, text="Logout", command=self.logout).pack(side="left")
        self.tabs = ttk.Notebook(self.root)
        self.tabs.pack(fill="both", expand=True, padx=12, pady=10)
        self.tab_map = {}
        self.add_tab("Dashboard", self.build_dashboard)
        if role in ("Admin", "Staff"):
            self.add_tab("Donor Management", self.build_donors)
            self.add_tab("Blood Inventory", self.build_inventory)
            self.add_tab("Emergency Requests", self.build_requests)
            self.add_tab("OS Scheduling", self.build_scheduling)
            self.add_tab("Reports", self.build_reports)
        else:
            # Requesters can only submit and track requests created by their own account.
            self.add_tab("My Blood Requests", self.build_requests)
        if role == "Admin":
            self.add_tab("User Management", self.build_users)
            self.add_tab("Audit Log", self.build_audit)
        footer = tk.Label(self.root, text="Academic prototype • All inventory is sample/demo data • Never use for real clinical decisions", anchor="w", padx=14, pady=5, fg="#7f1d1d")
        footer.pack(fill="x")
        self.refresh_all()

    def add_tab(self, name, builder):
        frame = ttk.Frame(self.tabs, padding=12)
        self.tabs.add(frame, text=name)
        self.tab_map[name] = frame
        builder(frame)

    def build_dashboard(self, frame):
        ttk.Label(frame, text="System Dashboard", font=("Arial", 17, "bold")).pack(anchor="w", pady=(0, 12))
        cards = ttk.Frame(frame); cards.pack(fill="x")
        self.stats = {}
        role = self.current_user["role"]
        if role == "Requester":
            card_defs = [("my_total", "My Requests"), ("my_pending", "Pending"), ("my_fulfilled", "Fulfilled"), ("my_cancelled", "Cancelled")]
        else:
            card_defs = [("donors", "Registered Donors"), ("units", "Sample Units"), ("pending", "Pending Requests"), ("critical", "Critical Requests")]
        for key, title in card_defs:
            box = ttk.LabelFrame(cards, text=title, padding=18); box.pack(side="left", fill="both", expand=True, padx=5)
            val = ttk.Label(box, text="0", font=("Arial", 22, "bold")); val.pack(); self.stats[key] = val
        if role == "Requester":
            own = self.conn.execute("SELECT COUNT(*) AS total, SUM(CASE WHEN status='Pending' THEN 1 ELSE 0 END) AS pending FROM requests WHERE created_by=?", (self.current_user["user_id"],)).fetchone()
            ttk.Label(frame, text=f"Welcome, {self.current_user['username']}.", font=("Arial", 13, "bold")).pack(anchor="w", pady=(18, 6))
            ttk.Label(frame, text=f"Your requests: {own['total'] or 0}    |    Pending: {own['pending'] or 0}", font=("Arial", 11)).pack(anchor="w")
            info = "REQUESTER WORKSPACE\n• Submit a blood request in My Blood Requests\n• Track the status of requests submitted by your account\n• Contact authorized blood-bank staff for real-world assistance\n\nYour account cannot browse donor contact records, change sample inventory, fulfil requests, manage users, or access staff reports."
        else:
            info = ("FINAL PHASE MODULES\n• DBMS: relational tables, primary/foreign keys, CHECK constraints, indexes, parameterized SQL, transactions, audit trail, CSV reports and backup\n• OS: FCFS, non-preemptive SJF, non-preemptive Priority and Round Robin scheduling\n• Metrics: completion time, turnaround time, waiting time and Gantt timeline\n\nROLE-BASED ACCESS\n• Admin: user management, audit log, reports, backup and staff functions\n• Staff: donor, inventory, request processing and OS scheduling\n• Requester: isolated workspace to submit and track only their own requests\n\nSafety: classroom simulation only; it does not establish compatibility or clinical suitability.")
        ttk.Label(frame, text=info, justify="left", font=("Arial", 10), wraplength=950).pack(anchor="w", pady=20)

    def make_tree(self, parent, columns, widths=None, height=12):
        box = ttk.Frame(parent); box.pack(fill="both", expand=True, pady=(8, 0))
        tree = ttk.Treeview(box, columns=columns, show="headings", height=height)
        for i, col in enumerate(columns):
            tree.heading(col, text=col); tree.column(col, width=(widths[i] if widths else 120), anchor="center")
        sy = ttk.Scrollbar(box, orient="vertical", command=tree.yview); sx = ttk.Scrollbar(box, orient="horizontal", command=tree.xview)
        tree.configure(yscrollcommand=sy.set, xscrollcommand=sx.set)
        tree.grid(row=0, column=0, sticky="nsew"); sy.grid(row=0, column=1, sticky="ns"); sx.grid(row=1, column=0, sticky="ew")
        box.rowconfigure(0, weight=1); box.columnconfigure(0, weight=1)
        return tree

    def build_donors(self, frame):
        ttk.Label(frame, text="Donor Records", font=("Arial", 15, "bold")).pack(anchor="w")
        form = ttk.LabelFrame(frame, text="Register donor", padding=9); form.pack(fill="x", pady=8)
        self.donor_name = tk.StringVar(); self.donor_group = tk.StringVar(value="O+"); self.donor_phone = tk.StringVar(); self.donor_city = tk.StringVar(value="Dehradun")
        for col, (label, var) in enumerate([("Name", self.donor_name), ("Blood group", self.donor_group), ("Phone", self.donor_phone), ("City", self.donor_city)]):
            ttk.Label(form, text=label).grid(row=0, column=col, sticky="w", padx=4)
            if label == "Blood group": ttk.Combobox(form, textvariable=var, values=BLOOD_GROUPS, state="readonly", width=16).grid(row=1, column=col, padx=4)
            else: ttk.Entry(form, textvariable=var, width=21).grid(row=1, column=col, padx=4)
        ttk.Button(form, text="Add Donor", command=self.add_donor).grid(row=1, column=4, padx=8)
        bar = ttk.Frame(frame); bar.pack(fill="x", pady=4)
        self.donor_search = tk.StringVar(); ttk.Label(bar, text="Search name/group/city/phone:").pack(side="left")
        ttk.Entry(bar, textvariable=self.donor_search, width=30).pack(side="left", padx=6)
        ttk.Button(bar, text="Search", command=self.refresh_donors).pack(side="left"); ttk.Button(bar, text="Clear", command=lambda: (self.donor_search.set(""), self.refresh_donors())).pack(side="left", padx=4)
        self.donor_tree = self.make_tree(frame, ("ID", "Name", "Blood Group", "Phone", "City", "Registered"), (55, 190, 100, 140, 140, 160))

    def build_inventory(self, frame):
        ttk.Label(frame, text="Blood Inventory (Sample Data)", font=("Arial", 15, "bold")).pack(anchor="w")
        ttk.Label(frame, text="Updates are for demonstration only and are restricted to Admin/Staff roles.").pack(anchor="w", pady=5)
        bar = ttk.Frame(frame); bar.pack(fill="x", pady=8)
        self.inv_group = tk.StringVar(value="O+"); self.inv_delta = tk.StringVar(value="1")
        ttk.Label(bar, text="Blood group").pack(side="left", padx=4); ttk.Combobox(bar, textvariable=self.inv_group, values=BLOOD_GROUPS, state="readonly", width=9).pack(side="left")
        ttk.Label(bar, text="Change units (+/-)").pack(side="left", padx=(12, 4)); ttk.Entry(bar, textvariable=self.inv_delta, width=10).pack(side="left")
        ttk.Button(bar, text="Update Inventory", command=self.update_inventory).pack(side="left", padx=8)
        self.inventory_tree = self.make_tree(frame, ("Blood Group", "Sample Units", "Last Updated"), (180, 180, 220))

    def build_requests(self, frame):
        heading = "My Blood Requests" if self.current_user["role"] == "Requester" else "Emergency Request Management"
        ttk.Label(frame, text=heading, font=("Arial", 15, "bold")).pack(anchor="w")
        form = ttk.LabelFrame(frame, text="Create request", padding=9); form.pack(fill="x", pady=8)
        self.patient_name = tk.StringVar(); self.request_group = tk.StringVar(value="O+"); self.request_units = tk.StringVar(value="1"); self.request_urgency = tk.StringVar(value="Critical")
        for col, (label, var, vals) in enumerate([("Patient/reference", self.patient_name, None), ("Blood group", self.request_group, BLOOD_GROUPS), ("Units", self.request_units, None), ("Urgency", self.request_urgency, URGENCIES)]):
            ttk.Label(form, text=label).grid(row=0, column=col, sticky="w", padx=4)
            if vals: ttk.Combobox(form, textvariable=var, values=vals, state="readonly", width=16).grid(row=1, column=col, padx=4)
            else: ttk.Entry(form, textvariable=var, width=21).grid(row=1, column=col, padx=4)
        ttk.Button(form, text="Submit Request", command=self.add_request).grid(row=1, column=4, padx=6)
        role = self.current_user["role"]
        if role in ("Admin", "Staff"):
            ttk.Button(form, text="Fulfil Selected (Demo)", command=self.fulfil_request).grid(row=1, column=5, padx=6)
            ttk.Button(form, text="Cancel Selected", command=self.cancel_request).grid(row=1, column=6, padx=6)
        bar = ttk.Frame(frame); bar.pack(fill="x", pady=4)
        self.request_filter = tk.StringVar(value="All")
        ttk.Label(bar, text="Status filter:").pack(side="left"); ttk.Combobox(bar, textvariable=self.request_filter, values=["All", "Pending", "Fulfilled", "Cancelled"], state="readonly", width=12).pack(side="left", padx=5)
        ttk.Button(bar, text="Apply Filter", command=self.refresh_requests).pack(side="left")
        self.request_tree = self.make_tree(frame, ("ID", "Patient/Ref", "Group", "Units", "Urgency", "Created", "Status", "Created By", "Handled By"), (45, 145, 70, 55, 80, 145, 80, 95, 95))

    def build_scheduling(self, frame):
        ttk.Label(frame, text="OS Process Scheduling Simulator", font=("Arial", 15, "bold")).pack(anchor="w")
        ttk.Label(frame, text="Processes are academic examples; all arrival times are assumed to be zero.").pack(anchor="w", pady=4)
        bar = ttk.Frame(frame); bar.pack(fill="x", pady=8)
        self.burst_times = tk.StringVar(value="5,3,8"); self.algorithm = tk.StringVar(value="FCFS"); self.quantum = tk.StringVar(value="2")
        ttk.Label(bar, text="Burst times:").pack(side="left"); ttk.Entry(bar, textvariable=self.burst_times, width=25).pack(side="left", padx=5)
        ttk.Label(bar, text="Algorithm:").pack(side="left", padx=(8, 4)); ttk.Combobox(bar, textvariable=self.algorithm, values=["FCFS", "SJF", "Priority", "Round Robin"], state="readonly", width=15).pack(side="left")
        ttk.Label(bar, text="RR quantum:").pack(side="left", padx=(8, 4)); ttk.Entry(bar, textvariable=self.quantum, width=5).pack(side="left")
        ttk.Button(bar, text="Run Scheduler", command=self.run_scheduler).pack(side="left", padx=8)
        self.schedule_output = tk.Text(frame, height=20, wrap="none", font=("Consolas", 10)); self.schedule_output.pack(fill="both", expand=True)
        self.schedule_output.insert("end", "Enter burst times such as 5,3,8 and choose an algorithm.\n")

    def build_users(self, frame):
        ttk.Label(frame, text="User Management (Admin Only)", font=("Arial", 15, "bold")).pack(anchor="w")
        form = ttk.LabelFrame(frame, text="Create account", padding=10); form.pack(fill="x", pady=8)
        self.new_username = tk.StringVar(); self.new_password = tk.StringVar(); self.new_role = tk.StringVar(value="Staff")
        for col, (label, var) in enumerate([("Username", self.new_username), ("Temporary password", self.new_password), ("Role", self.new_role)]):
            ttk.Label(form, text=label).grid(row=0, column=col, sticky="w", padx=5)
            if label == "Role": ttk.Combobox(form, textvariable=var, values=ROLES, state="readonly", width=16).grid(row=1, column=col, padx=5)
            else: ttk.Entry(form, textvariable=var, width=23, show="•" if label == "Temporary password" else "").grid(row=1, column=col, padx=5)
        ttk.Button(form, text="Create User", command=self.create_user).grid(row=1, column=3, padx=10)
        ttk.Button(form, text="Enable/Disable Selected", command=self.toggle_user).grid(row=1, column=4, padx=5)
        self.users_tree = self.make_tree(frame, ("ID", "Username", "Role", "Active", "Created"), (60, 180, 120, 80, 200))

    def build_audit(self, frame):
        ttk.Label(frame, text="Audit Log (Admin Only)", font=("Arial", 15, "bold")).pack(anchor="w")
        ttk.Button(frame, text="Refresh Log", command=self.refresh_audit).pack(anchor="w", pady=6)
        self.audit_tree = self.make_tree(frame, ("ID", "Username", "Action", "Details", "Time"), (50, 120, 130, 520, 170))

    def build_reports(self, frame):
        ttk.Label(frame, text="Reports & Database Backup", font=("Arial", 15, "bold")).pack(anchor="w")
        ttk.Label(frame, text="Export request history or donor records to CSV, or make a consistent SQLite backup.").pack(anchor="w", pady=8)
        row = ttk.Frame(frame); row.pack(anchor="w", pady=8)
        ttk.Button(row, text="Export Requests CSV", command=lambda: self.export_csv("requests")).pack(side="left", padx=5)
        if self.current_user["role"] in ("Admin", "Staff"):
            ttk.Button(row, text="Export Donors CSV", command=lambda: self.export_csv("donors")).pack(side="left", padx=5)
        if self.current_user["role"] == "Admin":
            ttk.Button(row, text="Backup Database", command=self.backup_database).pack(side="left", padx=5)
        ttk.Label(frame, text="Included database concepts: constraints, indexes, foreign keys, parameterized queries, transaction rollback on failed fulfilment, and audit history.", wraplength=850, justify="left").pack(anchor="w", pady=20)
        ttk.Label(frame, text="Reminder: never enter real patient identifiers or use the sample counts to make medical decisions.", foreground="#7f1d1d", wraplength=850).pack(anchor="w")

    def add_donor(self):
        if self.current_user["role"] not in ("Admin", "Staff"): return self.denied()
        name, group, phone, city = self.donor_name.get().strip(), self.donor_group.get(), self.donor_phone.get().strip(), self.donor_city.get().strip()
        if not all([name, group, phone, city]): return messagebox.showwarning("Missing data", "Fill in all donor fields.")
        if len(phone) > 30: return messagebox.showerror("Invalid phone", "Phone field is too long.")
        try:
            with self.conn:
                self.conn.execute("INSERT INTO donors(donor_name,blood_group,phone,city,created_at) VALUES(?,?,?,?,?)", (name, group, phone, city, now_text()))
            self.audit("DONOR_CREATED", f"Donor record added for {name}")
            self.donor_name.set(""); self.donor_phone.set(""); self.refresh_all()
        except sqlite3.Error as exc: messagebox.showerror("Database error", str(exc))

    def update_inventory(self):
        if self.current_user["role"] not in ("Admin", "Staff"): return self.denied()
        try: delta = int(self.inv_delta.get())
        except ValueError: return messagebox.showerror("Invalid value", "Enter a whole-number unit change.")
        group = self.inv_group.get()
        try:
            with self.conn:
                row = self.conn.execute("SELECT units FROM inventory WHERE blood_group=?", (group,)).fetchone()
                new_units = row["units"] + delta
                if new_units < 0: raise ValueError("Inventory cannot be negative.")
                self.conn.execute("UPDATE inventory SET units=?, updated_at=? WHERE blood_group=?", (new_units, now_text(), group))
            self.audit("INVENTORY_UPDATED", f"{group}: change {delta:+d}, new sample count {new_units}")
            self.refresh_all()
        except ValueError as exc: messagebox.showerror("Invalid update", str(exc))
        except sqlite3.Error as exc: messagebox.showerror("Database error", str(exc))

    def add_request(self):
        patient, group, urgency = self.patient_name.get().strip(), self.request_group.get(), self.request_urgency.get()
        try:
            units = int(self.request_units.get())
            if units <= 0: raise ValueError
        except ValueError: return messagebox.showerror("Invalid units", "Units must be a positive whole number.")
        if not patient: return messagebox.showwarning("Missing data", "Enter a patient/reference name.")
        if len(patient) > 100: return messagebox.showerror("Invalid name", "Reference name must be 100 characters or fewer.")
        try:
            with self.conn:
                cur = self.conn.execute("INSERT INTO requests(patient_name,blood_group,units,urgency,request_time,status,created_by) VALUES(?,?,?,?,?,'Pending',?)", (patient, group, units, urgency, now_text(), self.current_user["user_id"]))
                rid = cur.lastrowid
            self.audit("REQUEST_CREATED", f"Request #{rid}: {group}, {units} unit(s), {urgency}")
            self.patient_name.set(""); self.refresh_all()
            messagebox.showinfo("Request submitted", f"Request #{rid} was added to the demo queue.")
        except sqlite3.Error as exc: messagebox.showerror("Database error", str(exc))

    def selected_request_id(self):
        selected = self.request_tree.selection()
        if not selected: messagebox.showwarning("Select request", "Select a request row first."); return None
        return int(self.request_tree.item(selected[0], "values")[0])

    def fulfil_request(self):
        if self.current_user["role"] not in ("Admin", "Staff"): return self.denied()
        rid = self.selected_request_id()
        if rid is None: return
        if not messagebox.askyesno("Demo confirmation", "This consumes SAMPLE inventory and marks the request fulfilled. Continue?"): return
        try:
            # Single transaction prevents inventory and request status getting out of sync.
            self.conn.execute("BEGIN IMMEDIATE")
            req = self.conn.execute("SELECT * FROM requests WHERE request_id=?", (rid,)).fetchone()
            if not req or req["status"] != "Pending": raise ValueError("Only pending requests can be fulfilled.")
            inv = self.conn.execute("SELECT units FROM inventory WHERE blood_group=?", (req["blood_group"],)).fetchone()
            if not inv or inv["units"] < req["units"]: raise ValueError(f"Insufficient sample units. Available: {inv['units'] if inv else 0}.")
            self.conn.execute("UPDATE inventory SET units=units-?, updated_at=? WHERE blood_group=?", (req["units"], now_text(), req["blood_group"]))
            self.conn.execute("UPDATE requests SET status='Fulfilled', handled_by=?, handled_at=? WHERE request_id=?", (self.current_user["username"], now_text(), rid))
            self.conn.commit()
            self.audit("REQUEST_FULFILLED_DEMO", f"Request #{rid}; consumed {req['units']} sample unit(s) of {req['blood_group']}")
            self.refresh_all(); messagebox.showinfo("Completed", "Demo request marked fulfilled and sample inventory updated.")
        except (ValueError, sqlite3.Error) as exc:
            self.conn.rollback(); messagebox.showerror("Cannot fulfil request", str(exc))

    def cancel_request(self):
        if self.current_user["role"] not in ("Admin", "Staff"): return self.denied()
        rid = self.selected_request_id()
        if rid is None: return
        try:
            with self.conn:
                cur = self.conn.execute("UPDATE requests SET status='Cancelled', handled_by=?, handled_at=? WHERE request_id=? AND status='Pending'", (self.current_user["username"], now_text(), rid))
                if cur.rowcount == 0: raise ValueError("Only pending requests can be cancelled.")
            self.audit("REQUEST_CANCELLED", f"Request #{rid} cancelled")
            self.refresh_all()
        except (ValueError, sqlite3.Error) as exc: messagebox.showerror("Cannot cancel request", str(exc))

    def run_scheduler(self):
        if self.current_user["role"] not in ("Admin", "Staff"):
            return self.denied()
        try:
            bursts = [int(x.strip()) for x in self.burst_times.get().split(",") if x.strip()]
            quantum = int(self.quantum.get())
            rows, gantt, averages = schedule_processes(bursts, self.algorithm.get(), quantum=quantum)
        except ValueError as exc: return messagebox.showerror("Scheduling input", str(exc))
        lines = [f"{self.algorithm.get()} SCHEDULING RESULTS", "=" * 68, "PID   BT   Priority   CT   TAT   WT", "-" * 68]
        for r in rows: lines.append(f"P{r['pid']:<4} {r['bt']:<4} {r['priority']:<10} {r['ct']:<4} {r['tat']:<5} {r['wt']:<4}")
        lines += ["-" * 68, f"Average waiting time:    {averages['waiting']:.2f}", f"Average turnaround time: {averages['turnaround']:.2f}", "", "GANTT TIMELINE"]
        for pid, start, end in gantt: lines.append(f"[{start} - {end}]  P{pid}")
        lines.append("\nNote: all arrival times are 0; priority values repeat 1 (highest), 2, 3 for demo purposes.")
        self.schedule_output.delete("1.0", "end"); self.schedule_output.insert("end", "\n".join(lines))
        self.audit("SCHEDULER_RUN", f"{self.algorithm.get()} with bursts {bursts}")

    def create_user(self):
        if self.current_user["role"] != "Admin": return self.denied()
        username, password, role = self.new_username.get().strip(), self.new_password.get(), self.new_role.get()
        if len(username) < 3 or len(username) > 40: return messagebox.showerror("Invalid username", "Username must contain 3–40 characters.")
        if len(password) < 8: return messagebox.showerror("Weak password", "Use at least 8 characters for the password.")
        try:
            with self.conn: self.conn.execute("INSERT INTO users(username,password_hash,role,created_at) VALUES(?,?,?,?)", (username, hash_password(password), role, now_text()))
            self.audit("USER_CREATED", f"Created account {username} with role {role}")
            self.new_username.set(""); self.new_password.set(""); self.refresh_users()
            messagebox.showinfo("User created", f"Account '{username}' created.")
        except sqlite3.IntegrityError: messagebox.showerror("Duplicate username", "That username already exists.")

    def toggle_user(self):
        if self.current_user["role"] != "Admin": return self.denied()
        selected = self.users_tree.selection()
        if not selected: return messagebox.showwarning("Select user", "Select a user row first.")
        vals = self.users_tree.item(selected[0], "values"); uid, username, role, active = int(vals[0]), vals[1], vals[2], vals[3]
        if uid == self.current_user["user_id"]: return messagebox.showerror("Not allowed", "You cannot disable your own active account.")
        new_active = 0 if active == "Yes" else 1
        with self.conn: self.conn.execute("UPDATE users SET active=? WHERE user_id=?", (new_active, uid))
        self.audit("USER_STATUS_CHANGED", f"Account {username} active={new_active}"); self.refresh_users()

    def refresh_users(self):
        if "User Management" not in self.tab_map: return
        rows = self.conn.execute("SELECT user_id,username,role,active,created_at FROM users ORDER BY user_id").fetchall()
        self.fill_tree(self.users_tree, [(r["user_id"], r["username"], r["role"], "Yes" if r["active"] else "No", r["created_at"]) for r in rows])

    def refresh_audit(self):
        if "Audit Log" not in self.tab_map: return
        rows = self.conn.execute("SELECT log_id,username,action,details,event_time FROM audit_log ORDER BY log_id DESC LIMIT 500").fetchall()
        self.fill_tree(self.audit_tree, [tuple(r) for r in rows])

    def refresh_donors(self):
        if "Donor Management" not in self.tab_map: return
        q = getattr(self, "donor_search", tk.StringVar()).get().strip()
        pattern = f"%{q}%"
        rows = self.conn.execute("SELECT donor_id,donor_name,blood_group,phone,city,created_at FROM donors WHERE donor_name LIKE ? OR blood_group LIKE ? OR phone LIKE ? OR city LIKE ? ORDER BY donor_id DESC", (pattern, pattern, pattern, pattern)).fetchall()
        self.fill_tree(self.donor_tree, [tuple(r) for r in rows])

    def refresh_requests(self):
        if "Emergency Requests" not in self.tab_map and "My Blood Requests" not in self.tab_map: return
        status = getattr(self, "request_filter", tk.StringVar(value="All")).get()
        query = "SELECT r.request_id,r.patient_name,r.blood_group,r.units,r.urgency,r.request_time,r.status,COALESCE(u.username,'unknown'),COALESCE(r.handled_by,'—') FROM requests r LEFT JOIN users u ON u.user_id=r.created_by"
        args = ()
        if status != "All": query += " WHERE r.status=?"; args = (status,)
        query += " ORDER BY CASE r.urgency WHEN 'Critical' THEN 1 WHEN 'High' THEN 2 ELSE 3 END, r.request_time ASC"
        rows = self.conn.execute(query, args).fetchall()
        if self.current_user["role"] == "Requester":
            rows = [r for r in rows if r[7] == self.current_user["username"]]
        self.fill_tree(self.request_tree, [tuple(r) for r in rows])

    def refresh_all(self):
        if "Dashboard" in self.tab_map:
            if self.current_user["role"] == "Requester":
                uid = self.current_user["user_id"]
                stats = {
                    "my_total": self.conn.execute("SELECT COUNT(*) FROM requests WHERE created_by=?", (uid,)).fetchone()[0],
                    "my_pending": self.conn.execute("SELECT COUNT(*) FROM requests WHERE created_by=? AND status='Pending'", (uid,)).fetchone()[0],
                    "my_fulfilled": self.conn.execute("SELECT COUNT(*) FROM requests WHERE created_by=? AND status='Fulfilled'", (uid,)).fetchone()[0],
                    "my_cancelled": self.conn.execute("SELECT COUNT(*) FROM requests WHERE created_by=? AND status='Cancelled'", (uid,)).fetchone()[0],
                }
            else:
                stats = {"donors": self.conn.execute("SELECT COUNT(*) FROM donors").fetchone()[0], "units": self.conn.execute("SELECT COALESCE(SUM(units),0) FROM inventory").fetchone()[0], "pending": self.conn.execute("SELECT COUNT(*) FROM requests WHERE status='Pending'").fetchone()[0], "critical": self.conn.execute("SELECT COUNT(*) FROM requests WHERE status='Pending' AND urgency='Critical'").fetchone()[0]}
            for key, value in stats.items(): self.stats[key].config(text=str(value))
        self.refresh_donors(); self.refresh_inventory(); self.refresh_requests(); self.refresh_users(); self.refresh_audit()

    def refresh_inventory(self):
        if "Blood Inventory" not in self.tab_map: return
        rows = self.conn.execute("SELECT blood_group,units,updated_at FROM inventory ORDER BY blood_group").fetchall()
        self.fill_tree(self.inventory_tree, [tuple(r) for r in rows])

    @staticmethod
    def fill_tree(tree, rows):
        tree.delete(*tree.get_children())
        for row in rows: tree.insert("", "end", values=row)

    def export_csv(self, kind):
        if self.current_user["role"] not in ("Admin", "Staff"):
            return self.denied()
        path = filedialog.asksaveasfilename(title="Export CSV", defaultextension=".csv", filetypes=[("CSV files", "*.csv")], initialfile=f"{kind}_report.csv")
        if not path: return
        if kind == "requests":
            if self.current_user["role"] == "Requester":
                rows = self.conn.execute("SELECT request_id,patient_name,blood_group,units,urgency,request_time,status,created_by,handled_by,handled_at FROM requests WHERE created_by=? ORDER BY request_id", (self.current_user["user_id"],)).fetchall()
            else:
                rows = self.conn.execute("SELECT request_id,patient_name,blood_group,units,urgency,request_time,status,created_by,handled_by,handled_at FROM requests ORDER BY request_id").fetchall()
        else: rows = self.conn.execute("SELECT donor_id,donor_name,blood_group,phone,city,created_at FROM donors ORDER BY donor_id").fetchall()
        try:
            with open(path, "w", newline="", encoding="utf-8-sig") as f:
                writer = csv.writer(f); writer.writerow(rows[0].keys() if rows else (["request_id","patient_name","blood_group","units","urgency","request_time","status","created_by","handled_by","handled_at"] if kind == "requests" else ["donor_id","donor_name","blood_group","phone","city","created_at"]))
                writer.writerows([tuple(r) for r in rows])
            self.audit("CSV_EXPORTED", f"Exported {kind} report to {os.path.basename(path)}")
            messagebox.showinfo("Export complete", f"Report saved to:\n{path}")
        except OSError as exc: messagebox.showerror("Export failed", str(exc))

    def backup_database(self):
        if self.current_user["role"] != "Admin": return self.denied()
        path = filedialog.asksaveasfilename(title="Save database backup", defaultextension=".db", filetypes=[("SQLite database", "*.db")], initialfile="emergency_blood_bank_backup.db")
        if not path: return
        try:
            target = sqlite3.connect(path)
            with target: self.conn.backup(target)
            target.close(); self.audit("DATABASE_BACKUP", f"Backup saved to {os.path.basename(path)}")
            messagebox.showinfo("Backup complete", f"Database backup saved to:\n{path}")
        except sqlite3.Error as exc: messagebox.showerror("Backup failed", str(exc))

    def denied(self):
        messagebox.showerror("Access denied", "Your role does not have permission to perform this action.")

    def change_password(self):
        dialog = tk.Toplevel(self.root)
        dialog.title("Change Password")
        dialog.transient(self.root)
        dialog.grab_set()
        dialog.resizable(False, False)
        frame = ttk.Frame(dialog, padding=18)
        frame.pack(fill="both", expand=True)
        old_var, new_var, confirm_var = tk.StringVar(), tk.StringVar(), tk.StringVar()
        for row, (label, var) in enumerate((("Current password", old_var), ("New password (8+ characters)", new_var), ("Confirm new password", confirm_var))):
            ttk.Label(frame, text=label).grid(row=row, column=0, sticky="w", pady=6)
            ttk.Entry(frame, textvariable=var, show="•", width=30).grid(row=row, column=1, padx=(12, 0), pady=6)
        def save():
            user = self.conn.execute("SELECT password_hash FROM users WHERE user_id=?", (self.current_user["user_id"],)).fetchone()
            if not user or not verify_password(old_var.get(), user["password_hash"]):
                messagebox.showerror("Password error", "Current password is incorrect.", parent=dialog); return
            if len(new_var.get()) < 8:
                messagebox.showerror("Weak password", "New password must be at least 8 characters.", parent=dialog); return
            if new_var.get() != confirm_var.get():
                messagebox.showerror("Mismatch", "New password and confirmation do not match.", parent=dialog); return
            with self.conn:
                self.conn.execute("UPDATE users SET password_hash=? WHERE user_id=?", (hash_password(new_var.get()), self.current_user["user_id"]))
            self.audit("PASSWORD_CHANGED", "User changed their password")
            messagebox.showinfo("Password changed", "Your password has been updated.", parent=dialog)
            dialog.destroy()
        ttk.Button(frame, text="Save Password", command=save).grid(row=3, column=0, columnspan=2, sticky="ew", pady=(12, 0))

    def logout(self):
        self.audit("LOGOUT", "Signed out")
        self.current_user = None
        self.show_login()

    def close(self):
        try:
            if self.current_user: self.audit("APPLICATION_CLOSED", "Application closed")
            self.conn.close()
        finally: self.root.destroy()


def main():
    root = tk.Tk()
    BloodBankApp(root)
    root.mainloop()

if __name__ == "__main__":
    main()
