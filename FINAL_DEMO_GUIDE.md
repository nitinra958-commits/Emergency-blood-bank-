# Final Submission Demonstration Guide

## 1. Opening explanation (30 seconds)
“Our project is an academic Emergency Blood Bank Resource Management and Process Scheduling System. It combines DBMS concepts for managing structured donor, inventory, user and request records with OS concepts for comparing CPU scheduling algorithms. It includes role-based interfaces for Admin, Staff and Requester users.”

## 2. Login and role-based access (2 minutes)
- Sign in as `admin` / `Admin@123`.
- Show the Admin dashboard, User Management and Audit Log.
- Create a Staff account and a Requester account with temporary passwords.
- Sign out and sign in as Staff. Show donor management, sample inventory, request processing and OS scheduling.
- Sign out and sign in as Requester. Show the separate dashboard and My Blood Requests screen. Explain that requesters can see only their own requests and do not see donor contacts, inventory controls, fulfilment actions, reports, or scheduling.

## 3. DBMS demonstration (2–3 minutes)
- Add a clearly fictional donor record.
- Search for that record.
- Show the eight blood-group sample inventory rows.
- Add a fictional request and show its status.
- As Staff/Admin, fulfil it using the demo action. Explain that inventory deduction and request status update are committed together in one transaction; validation failures cause rollback.
- Show the audit log and CSV export. Explain primary keys, foreign keys, UNIQUE/CHECK constraints, indexes and parameterized queries.

## 4. OS demonstration (2 minutes)
- Use burst times `5,3,8`.
- Run FCFS, SJF, Priority and Round Robin.
- For Round Robin, use quantum `2` and then `3` to compare the Gantt timeline.
- Explain CT, TAT and WT. State that all arrival times are assumed to be zero in this simulator.

## 5. Closing explanation (30 seconds)
“The final version extends our Phase 2 prototype with authentication, separate role-specific screens, audit logging, request tracking, database migration, reports, backup and four scheduling algorithms. The program is a classroom simulation using fabricated inventory values, not a clinical decision system.”

## Demo credentials
- Admin: `admin` / `Admin@123`
- Staff: `staff` / `Staff@123`
- Requester: `requester` / `Request@123`

Change these demo passwords on the presentation machine if possible. Use fictional names and contact details only.

## Important note
Do not claim that this app finds medically compatible blood or connects to real blood banks. Inventory is fabricated sample data and fulfilment is a software demonstration only.
