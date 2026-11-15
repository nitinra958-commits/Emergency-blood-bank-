# Emergency Blood Bank Resource Management and Process Scheduling System

**Final-phase PBL | DBMS + Operating Systems | Python Tkinter + SQLite**

This is an expanded desktop application based on the Phase 2 prototype. It uses only the Python standard library.

## Features

### Authentication and role permissions
- Login screen with PBKDF2-HMAC-SHA256 password hashing and per-password random salts.
- Three roles: **Admin**, **Staff**, and **Requester**.
- Admin: all modules, create users, enable/disable accounts, view audit log, export reports, and back up the database.
- Staff: manage donor records, update sample inventory, submit/fulfil/cancel demo requests, run scheduling, and export reports.
- Requester: a separate, simplified workspace to submit requests and view only requests created by their own account. Requesters cannot browse donors or inventory, process requests, export staff reports, manage users, or run the OS simulator.
- Disabled accounts cannot sign in; failed and successful login attempts are recorded.

### DBMS
- SQLite relational schema: `users`, `donors`, `inventory`, `requests`, and `audit_log`.
- Primary keys, foreign keys, UNIQUE constraints, CHECK constraints, and indexes.
- Parameterized SQL queries, transactional request fulfilment, guarded inventory counts, request status history, CSV exports, and SQLite online backup.
- Donor search and request status filters.
- Automatic, repeat-safe migration from the Phase 2 SQLite schema while preserving existing records.

### Operating Systems
- FCFS, non-preemptive SJF, non-preemptive Priority, and Round Robin scheduling.
- Completion time (CT), turnaround time (TAT), waiting time (WT), average WT/TAT, and a Gantt timeline.
- Scheduling example uses arrival time 0 for every process. Demo priorities repeat 1 (highest), 2, 3.

## Requirements
- Python 3.9 or newer
- Tkinter (normally bundled with Python on Windows)
- SQLite (bundled with Python)
- No pip packages are required

## Run on Windows
1. Extract the project folder.
2. Open Command Prompt in the extracted folder.
3. Run `py emergency_blood_bank.py` (or `python emergency_blood_bank.py`).
4. The SQLite database `emergency_blood_bank.db` is created automatically in the same working folder. If an older Phase 2 database is present, startup adds the missing columns required by this version and backfills missing timestamps without deleting existing donors, inventory, or requests.

## Local demonstration accounts
These are seeded for classroom demonstration. **Change them or create your own accounts before presenting the project on a shared machine.**

| Role | Username | Password |
|---|---|---|
| Admin | `admin` | `Admin@123` |
| Staff | `staff` | `Staff@123` |
| Requester | `requester` | `Request@123` |

Log in as Admin and open **User Management** to create additional accounts or disable accounts. Passwords are stored as salted PBKDF2 hashes, not plaintext. This is a local academic app; it is not hardened for internet-facing deployment.

## Tests
Open a terminal in the extracted project folder and run:

```powershell
py -m unittest discover -s tests -v
```

The suite tests password hashing, all four scheduling algorithms, invalid scheduling inputs, and migration from the original Phase 2 database schema. It does not automate visual GUI interactions, so launch the app and check the screens on your computer before presenting.

## Suggested final-phase demo
1. Sign in as `admin`; show Dashboard, User Management, Audit Log, and Reports.
2. Create a new Staff account, log out, and sign in with that account.
3. Add a sample donor, search for the donor, and show the donor table.
4. Update a sample inventory count. Try a negative update that would make the count below zero and show the validation.
5. Submit a request, select it, and use **Fulfil Selected (Demo)**. Explain that inventory deduction and request status update occur in one database transaction.
6. Log in as `requester`; show its separate dashboard and My Blood Requests screen. Submit a request and show that only that account’s requests are visible. Point out that inventory and staff controls are absent.
7. Log in as Staff or Admin. Run burst times `5,3,8` with FCFS, SJF, Priority, and Round Robin. Change the quantum for Round Robin and explain CT, TAT, WT, and the Gantt timeline.
8. As Admin, export CSV reports, create a database backup, and inspect the Audit Log.

## Database schema summary
- `users(user_id, username, password_hash, role, active, created_at)`
- `donors(donor_id, donor_name, blood_group, phone, city, created_at)`
- `inventory(blood_group, units, updated_at)`
- `requests(request_id, patient_name, blood_group, units, urgency, request_time, status, created_by, handled_by, handled_at)`
- `audit_log(log_id, username, action, details, event_time)`

## Scheduling formulas
With all arrival times assumed to be zero:
- `CT = cumulative finish time of the process`
- `TAT = CT - AT` (so with AT = 0, TAT = CT)
- `WT = TAT - BT`
- `Average WT = sum(WT) / number of processes`
- `Average TAT = sum(TAT) / number of processes`

## Limitations and safety
This is an academic software simulation, **not a real blood-bank or clinical system**. Inventory is seeded with fabricated sample counts. The app does not assess donor eligibility, blood compatibility, component types, clinical priority, or transfusion suitability. Do not enter real patient data or use this software to make medical decisions. Real blood handling must follow qualified clinical and blood-bank procedures. Local demo passwords are publicly documented here, so they must not be reused for real accounts.

All signed-in users can select **Change Password** in the top-right corner to replace the seeded/demo password with a personal password. The app verifies the current password and confirmation before saving the new salted hash.

`schema.sql` is included as a readable DBMS schema reference for your report/viva. The application itself creates and indexes the tables automatically at startup.
