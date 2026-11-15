# Final Phase PBL Report

## Title
Emergency Blood Bank Resource Management and Process Scheduling System

## Abstract
The project is a desktop academic simulation that combines database management and operating-system scheduling concepts. It provides role-based sign-in, donor record management, sample inventory tracking, emergency request registration, request fulfilment simulation, audit logging, report export, database backup, and four CPU scheduling algorithms. Python Tkinter provides the graphical interface and SQLite provides persistent relational storage.

## Problem statement
A classroom model is needed to demonstrate how structured records, data validation, transaction safety, user permissions, and process scheduling can be combined in one application. The application uses fabricated inventory counts and reference records; it is not intended for real healthcare operations.

## Objectives
1. Implement persistent relational data storage with integrity constraints.
2. Demonstrate authentication and role-based access control.
3. Track sample donor, inventory, and request records.
4. Use a transaction when demo fulfilment updates both inventory and request status.
5. Demonstrate FCFS, SJF, non-preemptive Priority, and Round Robin scheduling.
6. Calculate CT, TAT, WT, average metrics, and display a Gantt timeline.
7. Record key actions in an audit log and support CSV/database exports.

## Technology stack
- Language: Python 3.9+
- GUI: Tkinter / ttk
- Database: SQLite
- Data exports: Python `csv` module
- Testing: Python `unittest`

## Module description
- **Login and users:** salted PBKDF2-HMAC-SHA256 password hashes, account roles, account activation state, failed-login recording, and user creation by Admin.
- **Dashboard:** Admin/Staff see aggregate donor, sample inventory, pending request, and critical request counts. Requesters see only their own request totals and statuses.
- **Donors:** insert and search donor records.
- **Inventory:** view seeded demo counts and make guarded adjustments.
- **Requests:** Admin/Staff can register, filter, fulfil (simulation), and cancel requests. Requesters have a separate screen and can submit and track only requests associated with their own account.
- **Scheduling:** Admin/Staff can compare FCFS, SJF, Priority, and Round Robin, with metrics and timeline. This module is not shown to Requester accounts.
- **Audit log:** record important actions and login events.
- **Reports and backup:** export CSV and use SQLite's backup API.

## DBMS concepts demonstrated
The database uses primary keys, foreign keys, UNIQUE constraints, CHECK constraints, indexes, parameterized queries, aggregate functions, joins, and transactions. Request fulfilment begins an immediate transaction, checks the current request and inventory, and updates inventory and status together. If a validation or database error occurs, the transaction is rolled back.

## OS concepts demonstrated
A request is conceptually represented as a process for scheduling demonstration. The algorithms are FCFS, non-preemptive SJF, non-preemptive Priority, and Round Robin. Arrival time is assumed to be zero for all processes. For each process, completion time is calculated from the schedule; turnaround time is `CT - AT`; waiting time is `TAT - BT`. Average waiting and turnaround times are the arithmetic means across all processes.

## Test plan
Run `python -m unittest discover -s tests -v`. The included tests cover password hashing and verification, random salt use, FCFS metrics, SJF ordering, priority ordering, Round Robin completion, and invalid scheduler input. GUI flows should additionally be demonstrated manually using the steps in README.md.

## Limitations
The software is a local educational prototype. Demo credentials are documented for assessment convenience. It does not include a production-grade password reset workflow, external identity provider, networked deployment, multi-user server sessions, clinical validation, blood-component tracking, or real-time integration with licensed blood banks. Sample inventory is fabricated and cannot be used to guide patient care.

## Conclusion
The final-phase application extends the Phase 2 prototype with distinct Admin, Staff, and Requester workspaces; login and role permissions; audit history; request filtering; four scheduling algorithms; exports; database backup; backward-compatible schema migration; and automated unit tests. It demonstrates core DBMS and OS concepts through a runnable graphical application while explicitly limiting the scope to classroom simulation.


## Backward-compatible database migration

The application now inspects existing SQLite table definitions during startup. If a database was created by the Phase 2 prototype, it adds the Final Phase columns that are missing from the `donors`, `inventory`, and `requests` tables. It backfills missing timestamps and preserves existing donor, inventory, and request rows. This avoids the `sqlite3.OperationalError: table inventory has no column named updated_at` error caused by reusing an older database. The migration is designed to be safe to run repeatedly.

## Verification

Automated tests cover salted password hashing and verification, FCFS/SJF/Priority/Round Robin scheduling, invalid scheduling inputs, and an in-memory upgrade test built from the Phase 2 table definitions. GUI rendering and interaction should also be manually checked on the presentation computer.
