from datetime import datetime, timezone
import hashlib
import json
import os
from uuid import uuid4
from fastapi import Depends, FastAPI, HTTPException, Query
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import Decision, DecisionAuditEvent
from app.rules import POLICY_VERSION, classify
from app.schemas import DecisionResponse, EvaluateRequest, ReviewRequest, ReviewResponse
from app.security import Actor, require_roles
from app.providers.jev import JevUnavailable, suggest_category
from app.providers.openai_decisions import OpenAIUnavailable, suggest_category as suggest_openai_category
from app.providers.selection import select_provider

app=FastAPI(title='RadBridge Decision Engine',version='0.1.0',docs_url='/api/docs',redoc_url=None)

@app.get('/health/live',include_in_schema=False)
def live():
    return {'status':'alive'}

@app.get('/health/ready',include_in_schema=False)
def ready(db:Session=Depends(get_db)):
    db.execute(text('SELECT 1'))
    return {'status':'ready'}

def render(decision:Decision):
    return DecisionResponse(decision_id=decision.id,request_id=decision.request_id,
        task_code=decision.task_code,status=decision.status,category=decision.category,
        suggested_action=decision.suggested_action,reason_code=decision.reason_code,
        provider=decision.provider,policy_version=decision.policy_version,
        model_suggestion=decision.model_suggestion,model_confidence=decision.model_confidence,
        model_name=decision.model_name,
        review_required=decision.status=='NEEDS_REVIEW',evidence=decision.evidence,
        created_at=decision.created_at)

@app.post('/api/v1/decisions/evaluate',response_model=DecisionResponse)
def evaluate(request:EvaluateRequest,actor:Actor=Depends(require_roles('HELPDESK','HELPDESK_SUPERVISOR','ADMIN','SUPER_ADMIN')),
             db:Session=Depends(get_db)):
    branch_id=actor.branch_id or 'GLOBAL'
    normalized={'source_id':request.source_id,'destination_id':request.destination_id,
                'error_code':request.error_code.strip().upper(),'retry_count':request.retry_count}
    digest=hashlib.sha256(json.dumps(normalized,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    prior=db.scalar(select(Decision).where(Decision.branch_id==branch_id,Decision.request_id==request.request_id))
    if prior:
        if prior.evidence_sha256!=digest or prior.actor_id!=actor.user_id:
            raise HTTPException(status_code=409,detail='Request id already used with different evidence or actor')
        return render(prior)
    result=classify(normalized['error_code'],request.retry_count)
    decision=Decision(id=str(uuid4()),request_id=request.request_id,task_code=request.task_code,
        task_version=request.task_version,branch_id=branch_id,actor_id=actor.user_id,
        evidence=normalized,evidence_sha256=digest,status=result.status,category=result.category,
        suggested_action=result.suggested_action,reason_code=result.reason_code,provider='RULES',
        policy_version=POLICY_VERSION)
    db.add(decision)
    db.add(DecisionAuditEvent(decision_id=decision.id,branch_id=branch_id,actor_id=actor.user_id,
        event_type='DECISION_CLASSIFIED',details={'provider':'RULES','reason_code':result.reason_code}))
    try:
        db.flush()
        db.commit()
    except IntegrityError:
        db.rollback()
        prior=db.scalar(select(Decision).where(Decision.branch_id==branch_id,Decision.request_id==request.request_id))
        if prior and prior.evidence_sha256==digest and prior.actor_id==actor.user_id:
            return render(prior)
        raise HTTPException(status_code=409,detail='Request id conflict') from None
    db.refresh(decision)
    # External inference is explicitly opt-in and restricted to fixed, non-PHI rule codes.
    # Commit the idempotency reservation first so duplicate HTTP retries cannot fan out calls.
    provider=select_provider()
    if (decision.status=='NEEDS_REVIEW' and provider
            and normalized['error_code'] in {'C_STORE_FAILURE','INVALID_DICOM_DATA'}):
        provider_name='JEV' if provider == 'jev' else 'OPENAI_DECISIONS'
        db.add(DecisionAuditEvent(decision_id=decision.id,branch_id=branch_id,actor_id=actor.user_id,
            event_type='PROVIDER_REQUESTED',details={'provider':provider_name,'policy_mode':os.environ.get('DECISION_PROVIDER','rules').strip().lower()}))
        db.commit()
        try:
            if provider == 'jev':
                suggestion=suggest_category(normalized['error_code'],request.retry_count)
            else:
                suggestion=suggest_openai_category(normalized['error_code'],request.retry_count)
        except (JevUnavailable, OpenAIUnavailable):
            db.add(DecisionAuditEvent(decision_id=decision.id,branch_id=branch_id,actor_id=actor.user_id,
                event_type=f'{provider_name}_UNAVAILABLE',details={'provider':provider_name,'reason_code':'PROVIDER_UNAVAILABLE'}))
            db.commit()
            suggestion=None
        if suggestion:
            decision.provider=provider_name
            decision.model_suggestion=suggestion.category
            decision.model_confidence=suggestion.confidence
            decision.model_name=suggestion.model_name
            db.add(DecisionAuditEvent(decision_id=decision.id,branch_id=branch_id,actor_id=actor.user_id,
                event_type=f'{provider_name}_SUGGESTION',details={'provider':provider_name,'model':suggestion.model_name,
                'category':suggestion.category,'confidence':suggestion.confidence,
                'input_tokens':suggestion.input_tokens,'output_tokens':suggestion.output_tokens}))
            db.commit()
            db.refresh(decision)
    return render(decision)

@app.get('/api/v1/reviews',response_model=list[DecisionResponse])
def review_queue(limit:int=Query(100,ge=1,le=500),actor:Actor=Depends(require_roles('HELPDESK_SUPERVISOR','ADMIN','SUPER_ADMIN')),
                 db:Session=Depends(get_db)):
    stmt=select(Decision).where(Decision.status=='NEEDS_REVIEW').order_by(Decision.created_at,Decision.id).limit(limit)
    if 'SUPER_ADMIN' not in actor.roles:
        stmt=stmt.where(Decision.branch_id==actor.branch_id)
    return [render(row) for row in db.scalars(stmt).all()]

@app.post('/api/v1/reviews/{decision_id}',response_model=ReviewResponse)
def review(decision_id:str,request:ReviewRequest,actor:Actor=Depends(require_roles('HELPDESK_SUPERVISOR','ADMIN','SUPER_ADMIN')),
           db:Session=Depends(get_db)):
    stmt=select(Decision).where(Decision.id==decision_id).with_for_update()
    decision=db.scalar(stmt)
    if not decision or ('SUPER_ADMIN' not in actor.roles and decision.branch_id!=actor.branch_id):
        raise HTTPException(status_code=404,detail='Decision not found')
    if decision.status!='NEEDS_REVIEW':
        raise HTTPException(status_code=409,detail='Decision is no longer awaiting review')
    now=datetime.now(timezone.utc)
    decision.status='REVIEWED'
    decision.reviewed_by=actor.user_id
    decision.reviewed_at=now
    decision.review_outcome=request.outcome
    decision.review_reason=request.reason_code
    db.add(DecisionAuditEvent(decision_id=decision.id,branch_id=decision.branch_id,actor_id=actor.user_id,
        event_type='HUMAN_REVIEWED',details={'outcome':request.outcome,'reason_code':request.reason_code}))
    db.commit()
    return ReviewResponse(decision_id=decision.id,status=decision.status,outcome=request.outcome,
                          reason_code=request.reason_code,reviewed_by=actor.user_id,reviewed_at=now)
