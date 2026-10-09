BEGIN;

CREATE TABLE IF NOT EXISTS correction_execution (
    id SERIAL PRIMARY KEY,

    correction_request_id INTEGER NOT NULL,
    order_id INTEGER NOT NULL,
    branch_id INTEGER,

    execution_type VARCHAR(40) NOT NULL,

    status VARCHAR(40) NOT NULL
        DEFAULT 'READY_FOR_EXECUTION',

    state_version INTEGER NOT NULL
        DEFAULT 1,

    claimed_by INTEGER,
    executed_by INTEGER,

    request_snapshot_json TEXT NOT NULL
        DEFAULT '{}',

    preflight_snapshot_json TEXT NOT NULL
        DEFAULT '{}',

    result_snapshot_json TEXT NOT NULL
        DEFAULT '{}',

    confirmation_token_hash VARCHAR(128),
    confirmation_expires_at TIMESTAMP,

    failure_code VARCHAR(80),
    failure_message TEXT,

    created_at TIMESTAMP NOT NULL
        DEFAULT CURRENT_TIMESTAMP,

    updated_at TIMESTAMP NOT NULL
        DEFAULT CURRENT_TIMESTAMP,

    claimed_at TIMESTAMP,
    started_at TIMESTAMP,
    executed_at TIMESTAMP,
    verified_at TIMESTAMP,
    failed_at TIMESTAMP,

    CONSTRAINT uq_correction_execution_request
        UNIQUE (correction_request_id),

    CONSTRAINT ck_correction_execution_type
        CHECK (
            execution_type IN (
                'WRONG_IMAGES',
                'WRONG_DEMOGRAPHICS',
                'WRONG_ORDER',
                'WRONG_ACCESSION',
                'DUPLICATE_CASE',
                'CANCEL_ORDER',
                'WRONG_REPORT',
                'OTHER'
            )
        ),

    CONSTRAINT ck_correction_execution_status
        CHECK (
            status IN (
                'READY_FOR_EXECUTION',
                'CLAIMED_FOR_EXECUTION',
                'ON_HOLD',
                'PREFLIGHT_PASSED',
                'PREFLIGHT_BLOCKED',
                'EXECUTING',
                'VERIFYING',
                'COMPLETED',
                'EXECUTION_FAILED',
                'VERIFICATION_FAILED',
                'EXPIRED',
                'CANCELLED_BEFORE_EXECUTION'
            )
        ),

    CONSTRAINT ck_correction_execution_state_version
        CHECK (state_version >= 1),

    CONSTRAINT fk_correction_execution_request
        FOREIGN KEY (correction_request_id)
        REFERENCES correction_request(id),

    CONSTRAINT fk_correction_execution_order
        FOREIGN KEY (order_id)
        REFERENCES "order"(id),

    CONSTRAINT fk_correction_execution_branch
        FOREIGN KEY (branch_id)
        REFERENCES branch(id),

    CONSTRAINT fk_correction_execution_claimed_by
        FOREIGN KEY (claimed_by)
        REFERENCES "user"(id),

    CONSTRAINT fk_correction_execution_executed_by
        FOREIGN KEY (executed_by)
        REFERENCES "user"(id)
);

CREATE INDEX IF NOT EXISTS
    ix_correction_execution_order_id
ON correction_execution(order_id);

CREATE INDEX IF NOT EXISTS
    ix_correction_execution_branch_id
ON correction_execution(branch_id);

CREATE INDEX IF NOT EXISTS
    ix_correction_execution_status
ON correction_execution(status);

CREATE INDEX IF NOT EXISTS
    ix_correction_execution_execution_type
ON correction_execution(execution_type);

CREATE INDEX IF NOT EXISTS
    ix_correction_execution_claimed_by
ON correction_execution(claimed_by);

CREATE INDEX IF NOT EXISTS
    ix_correction_execution_created_at
ON correction_execution(created_at);

COMMIT;
