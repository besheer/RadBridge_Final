from datetime import datetime
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, StringConstraints
from typing_extensions import Annotated

SafeIdentifier=Annotated[str,StringConstraints(pattern=r'^[A-Za-z0-9._-]{1,64}$')]

class EvaluateRequest(BaseModel):
    model_config=ConfigDict(extra='forbid')
    request_id: Annotated[str,StringConstraints(min_length=8,max_length=80,pattern=r'^[A-Za-z0-9._:-]+$')]
    task_code: Literal['DICOM_ROUTER_ERROR']
    task_version: Literal['1.0']
    source_id: SafeIdentifier
    destination_id: SafeIdentifier
    error_code: Annotated[str,StringConstraints(min_length=2,max_length=64,pattern=r'^[A-Za-z0-9_]+$')]
    retry_count: int=Field(ge=0,le=100)

class DecisionResponse(BaseModel):
    decision_id: str
    request_id: str
    task_code: str
    status: str
    category: str
    suggested_action: str
    reason_code: str
    provider: str
    model_suggestion: str | None = None
    model_confidence: float | None = None
    model_name: str | None = None
    policy_version: str
    review_required: bool
    execution_allowed: Literal[False] = False
    evidence: dict[str, str | int]
    created_at: datetime

class ReviewRequest(BaseModel):
    model_config=ConfigDict(extra='forbid')
    outcome: Literal['ACCEPTED','REJECTED']
    reason_code: Literal['CONFIRMED_CATEGORY','CORRECTED_CATEGORY','NOT_ACTIONABLE']

class ReviewResponse(BaseModel):
    decision_id: str
    status: str
    outcome: str
    reason_code: str
    reviewed_by: str
    reviewed_at: datetime
