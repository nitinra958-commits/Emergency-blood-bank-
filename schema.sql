-- Schema reference for DBMS viva/report. The application creates these tables on startup.
PRAGMA foreign_keys = ON;

CREATE TABLE users (
  user_id INTEGER PRIMARY KEY AUTOINCREMENT,
  username TEXT NOT NULL UNIQUE COLLATE NOCASE,
  password_hash TEXT NOT NULL,
  role TEXT NOT NULL CHECK(role IN ('Admin','Staff','Requester')),
  active INTEGER NOT NULL DEFAULT 1 CHECK(active IN (0,1)),
  created_at TEXT NOT NULL
);

CREATE TABLE donors (
  donor_id INTEGER PRIMARY KEY AUTOINCREMENT,
  donor_name TEXT NOT NULL,
  blood_group TEXT NOT NULL CHECK(blood_group IN ('A+','A-','B+','B-','AB+','AB-','O+','O-')),
  phone TEXT NOT NULL,
  city TEXT NOT NULL,
  created_at TEXT NOT NULL
);

CREATE TABLE inventory (
  blood_group TEXT PRIMARY KEY CHECK(blood_group IN ('A+','A-','B+','B-','AB+','AB-','O+','O-')),
  units INTEGER NOT NULL DEFAULT 0 CHECK(units >= 0),
  updated_at TEXT NOT NULL
);

CREATE TABLE requests (
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

CREATE TABLE audit_log (
  log_id INTEGER PRIMARY KEY AUTOINCREMENT,
  username TEXT NOT NULL,
  action TEXT NOT NULL,
  details TEXT NOT NULL,
  event_time TEXT NOT NULL
);

CREATE INDEX idx_requests_status_time ON requests(status, request_time);
CREATE INDEX idx_requests_urgency ON requests(urgency);
CREATE INDEX idx_donors_group ON donors(blood_group);
CREATE INDEX idx_audit_time ON audit_log(event_time);
