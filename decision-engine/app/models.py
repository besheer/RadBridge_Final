from datetime import datetime, timezone
from sqlalchemy import DateTime, ForeignKey, Index, Integer, JSON, String, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

class Base(DeclarativeBase):
    pass

class Decision(Base):
    __tablename__='decisions'
    __table_args__=(UniqueConstraint('branch_id','request_id',name='uq_decision_branch_request'),
                    Index('ix_decisions_branch_status_created','branch_id','status','created_at'))
    id: Mapped[str]=mapped_column(String(36),primary_key=True)
    request_id: Mapped[str]=mapped_column(String(80),nullable=False)
    task_code: Mapped[str]=mapped_column(String(64),nullable=False)
    task_version: Mapped[str]=mapped_column(String(32),nullable=False)
    branch_id: Mapped[str]=mapped_column(String(80),nullable=False)
    actor_id: Mapped[str]=mapped_column(String(80),nullable=False)
    evidence: Mapped[dict]=mapped_column(JSON,nullable=False)
    evidence_sha256: Mapped[str]=mapped_column(String(64),nullable=False)
    status: Mapped[str]=mapped_column(String(24),nullable=False)
    category: Mapped[str]=mapped_column(String(40),nullable=False)
    suggested_action: Mapped[str]=mapped_column(String(40),nullable=False)
    reason_code: Mapped[str]=mapped_column(String(64),nullable=False)
    provider: Mapped[str]=mapped_column(String(24),nullable=False)
    model_suggestion: Mapped[str|None]=mapped_column(String(40))
    model_confidence: Mapped[float|None]=mapped_column()
    model_name: Mapped[str|None]=mapped_column(String(80))
    model_probabilities: Mapped[dict|None]=mapped_column(JSON)
    policy_version: Mapped[str]=mapped_column(String(32),nullable=False)
    created_at: Mapped[datetime]=mapped_column(DateTime(timezone=True),default=lambda:datetime.now(timezone.utc),nullable=False)
    reviewed_by: Mapped[str|None]=mapped_column(String(80))
    reviewed_at: Mapped[datetime|None]=mapped_column(DateTime(timezone=True))
    review_outcome: Mapped[str|None]=mapped_column(String(16))
    review_reason: Mapped[str|None]=mapped_column(String(1000))

class DecisionAuditEvent(Base):
    __tablename__='decision_audit_events'
    __table_args__=(Index('ix_decision_audit_branch_time','branch_id','occurred_at'),)
    id: Mapped[int]=mapped_column(Integer,primary_key=True,autoincrement=True)
    decision_id: Mapped[str]=mapped_column(ForeignKey('decisions.id',ondelete='RESTRICT'),nullable=False)
    branch_id: Mapped[str]=mapped_column(String(80),nullable=False)
    actor_id: Mapped[str]=mapped_column(String(80),nullable=False)
    event_type: Mapped[str]=mapped_column(String(32),nullable=False)
    occurred_at: Mapped[datetime]=mapped_column(DateTime(timezone=True),default=lambda:datetime.now(timezone.utc),nullable=False)
    details: Mapped[dict]=mapped_column(JSON,nullable=False,default=dict)
