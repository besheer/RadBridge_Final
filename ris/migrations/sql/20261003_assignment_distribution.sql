CREATE TABLE IF NOT EXISTS assignment_visit (
 sequence_id SERIAL PRIMARY KEY, id VARCHAR(36) NOT NULL UNIQUE,
 patient_id INTEGER NOT NULL REFERENCES patient(id), branch_id INTEGER REFERENCES branch(id),
 visit_date DATE NOT NULL, preferred_doctor_id INTEGER REFERENCES "user"(id)
);
ALTER TABLE "order" ADD COLUMN IF NOT EXISTS assignment_visit_id VARCHAR(36) REFERENCES assignment_visit(id);
ALTER TABLE "order" ADD COLUMN IF NOT EXISTS assignment_special_code VARCHAR(80) DEFAULT '';
ALTER TABLE appointment ADD COLUMN IF NOT EXISTS assignment_visit_id VARCHAR(36) REFERENCES assignment_visit(id);
ALTER TABLE appointment ADD COLUMN IF NOT EXISTS assignment_special_code VARCHAR(80) DEFAULT '';
CREATE INDEX IF NOT EXISTS ix_order_assignment_visit_id ON "order"(assignment_visit_id);
CREATE INDEX IF NOT EXISTS ix_appointment_assignment_visit_id ON appointment(assignment_visit_id);
CREATE TABLE IF NOT EXISTS assignment_distribution_policy (
 id INTEGER PRIMARY KEY CHECK (id = 1), selection_mode VARCHAR(30) NOT NULL,
 max_active_cases INTEGER NOT NULL CHECK (max_active_cases BETWEEN 1 AND 1000),
 reclaim_enabled BOOLEAN NOT NULL, urgent_percent INTEGER NOT NULL CHECK (urgent_percent BETWEEN 1 AND 100),
 stat_percent INTEGER NOT NULL CHECK (stat_percent BETWEEN 1 AND 100), rules_json TEXT NOT NULL,
 special_rules_json TEXT NOT NULL DEFAULT '[]', version_no INTEGER NOT NULL, updated_by INTEGER REFERENCES "user"(id), updated_at TIMESTAMP
);
ALTER TABLE case_assignment ADD COLUMN IF NOT EXISTS start_deadline_at TIMESTAMP;
ALTER TABLE case_assignment ADD COLUMN IF NOT EXISTS start_timeout_seconds INTEGER;
ALTER TABLE case_assignment ADD COLUMN IF NOT EXISTS reading_started_at TIMESTAMP;
ALTER TABLE case_assignment ADD COLUMN IF NOT EXISTS distribution_snapshot_json TEXT;
CREATE INDEX IF NOT EXISTS ix_case_assignment_start_deadline_at ON case_assignment(start_deadline_at);
