-- SecureFlow database (SQLite). Not used in the midterm slice. Matches the ERD in docs/reference/SecureFlow_ERD.png
PRAGMA foreign_keys = ON;

CREATE TABLE project (
  project_id INTEGER PRIMARY KEY,
  name TEXT NOT NULL,
  root_path TEXT NOT NULL,
  created_at TEXT NOT NULL
);
CREATE TABLE test_setup (
  setup_id INTEGER PRIMARY KEY,
  project_id INTEGER NOT NULL REFERENCES project(project_id) ON DELETE CASCADE,
  login_url TEXT, login_type TEXT CHECK (login_type IN ('cookie','token','api_key')),
  token_location TEXT, token_header_format TEXT,
  app_database_path TEXT, use_database_copy INTEGER NOT NULL DEFAULT 1,
  env_file_path TEXT, folders_to_skip TEXT, last_saved_at TEXT
);
CREATE TABLE test_account (
  account_id INTEGER PRIMARY KEY,
  setup_id INTEGER NOT NULL REFERENCES test_setup(setup_id) ON DELETE CASCADE,
  account_name TEXT NOT NULL, login_email TEXT NOT NULL, password_key_name TEXT NOT NULL
);
CREATE TABLE scan (
  scan_id INTEGER PRIMARY KEY,
  project_id INTEGER NOT NULL REFERENCES project(project_id) ON DELETE CASCADE,
  setup_id INTEGER REFERENCES test_setup(setup_id) ON DELETE SET NULL,
  scan_mode TEXT NOT NULL CHECK (scan_mode IN ('full','code_only')),
  scan_status TEXT NOT NULL CHECK (scan_status IN ('completed','cancelled','failed')),
  started_at TEXT NOT NULL, finished_at TEXT, docker_version TEXT,
  suspects_found INTEGER NOT NULL DEFAULT 0, problems_confirmed INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE route (
  route_id INTEGER PRIMARY KEY,
  scan_id INTEGER NOT NULL REFERENCES scan(scan_id) ON DELETE CASCADE,
  url_path TEXT NOT NULL, http_methods TEXT NOT NULL,
  file_path TEXT NOT NULL, line_number INTEGER NOT NULL, protections_found TEXT
);
CREATE TABLE finding (
  finding_id INTEGER PRIMARY KEY,
  scan_id INTEGER NOT NULL REFERENCES scan(scan_id) ON DELETE CASCADE,
  route_id INTEGER NOT NULL REFERENCES route(route_id) ON DELETE CASCADE,
  finding_match_key TEXT NOT NULL,
  problem_class TEXT NOT NULL CHECK (problem_class IN ('access_control','unsafe_input')),
  problem_type TEXT NOT NULL,
  severity TEXT NOT NULL CHECK (severity IN ('High','Medium','Low')),
  finding_status TEXT NOT NULL CHECK (finding_status IN ('suspect','unconfirmed','confirmed','discarded','unclear','fixed')),
  file_path TEXT NOT NULL, line_number INTEGER NOT NULL, explanation TEXT NOT NULL
);
CREATE INDEX idx_finding_match ON finding(finding_match_key);
CREATE TABLE evidence (
  evidence_id INTEGER PRIMARY KEY,
  finding_id INTEGER NOT NULL UNIQUE REFERENCES finding(finding_id) ON DELETE CASCADE,
  request_sent TEXT, response_received TEXT, database_change_seen TEXT
);
CREATE TABLE fix_proposal (
  fix_id INTEGER PRIMARY KEY,
  finding_id INTEGER NOT NULL REFERENCES finding(finding_id) ON DELETE CASCADE,
  fix_rule_name TEXT NOT NULL, proposed_change TEXT NOT NULL,
  fix_status TEXT NOT NULL CHECK (fix_status IN ('proposed','applied','cancelled','undone')),
  applied_at TEXT, retest_result TEXT CHECK (retest_result IN ('passed','failed','not_run'))
);
CREATE TABLE database_check (
  check_id INTEGER PRIMARY KEY,
  scan_id INTEGER NOT NULL UNIQUE REFERENCES scan(scan_id) ON DELETE CASCADE,
  file_hash_before TEXT, file_hash_after TEXT, file_unchanged INTEGER, file_size_bytes INTEGER
);
CREATE TABLE report (
  report_id INTEGER PRIMARY KEY,
  scan_id INTEGER NOT NULL REFERENCES scan(scan_id) ON DELETE CASCADE,
  report_format TEXT NOT NULL CHECK (report_format IN ('html','json')),
  saved_to_path TEXT NOT NULL, created_at TEXT NOT NULL
);
CREATE TABLE scan_log_entry (
  log_id INTEGER PRIMARY KEY,
  scan_id INTEGER NOT NULL REFERENCES scan(scan_id) ON DELETE CASCADE,
  logged_at TEXT NOT NULL, log_level TEXT NOT NULL CHECK (log_level IN ('info','warning','error')),
  scan_step TEXT, log_message TEXT NOT NULL
);
