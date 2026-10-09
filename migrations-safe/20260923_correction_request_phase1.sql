BEGIN;

CREATE TABLE IF NOT EXISTS correction_request (
    id SERIAL PRIMARY KEY,
    order_id INTEGER NOT NULL,
    branch_id INTEGER,
    request_type VARCHAR(40) NOT NULL,
    status VARCHAR(30) NOT NULL DEFAULT 'NEW',
    reason TEXT NOT NULL,
    requested_by INTEGER NOT NULL,
    assigned_to INTEGER,
    review_note TEXT DEFAULT '',
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    reviewed_at TIMESTAMP,
    closed_at TIMESTAMP,
    CONSTRAINT ck_correction_request_type CHECK (
        request_type IN ('WRONG_IMAGES','WRONG_DEMOGRAPHICS','WRONG_ORDER','WRONG_ACCESSION','DUPLICATE_CASE','CANCEL_ORDER','WRONG_REPORT','OTHER')
    ),
    CONSTRAINT ck_correction_request_status CHECK (
        status IN ('NEW','UNDER_REVIEW','NEED_INFO','APPROVED','REJECTED','COMPLETED')
    ),
    CONSTRAINT fk_correction_request_order FOREIGN KEY (order_id) REFERENCES "order"(id),
    CONSTRAINT fk_correction_request_branch FOREIGN KEY (branch_id) REFERENCES branch(id),
    CONSTRAINT fk_correction_request_requested_by FOREIGN KEY (requested_by) REFERENCES "user"(id),
    CONSTRAINT fk_correction_request_assigned_to FOREIGN KEY (assigned_to) REFERENCES "user"(id)
);

CREATE INDEX IF NOT EXISTS ix_correction_request_order_id ON correction_request(order_id);
CREATE INDEX IF NOT EXISTS ix_correction_request_branch_id ON correction_request(branch_id);
CREATE INDEX IF NOT EXISTS ix_correction_request_request_type ON correction_request(request_type);
CREATE INDEX IF NOT EXISTS ix_correction_request_status ON correction_request(status);
CREATE INDEX IF NOT EXISTS ix_correction_request_requested_by ON correction_request(requested_by);
CREATE INDEX IF NOT EXISTS ix_correction_request_assigned_to ON correction_request(assigned_to);
CREATE INDEX IF NOT EXISTS ix_correction_request_created_at ON correction_request(created_at);

-- Exactly one open request of the same type may exist for an order.
-- Closed requests remain historical and do not block a later request.
CREATE UNIQUE INDEX IF NOT EXISTS uq_correction_request_open_order_type
ON correction_request(order_id, request_type)
WHERE status IN ('NEW','UNDER_REVIEW','NEED_INFO','APPROVED');

COMMIT;
