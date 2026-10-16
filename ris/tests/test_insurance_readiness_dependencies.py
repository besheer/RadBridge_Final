from types import SimpleNamespace as Row
import pytest
from application.services.registration.insurance_readiness import InsuranceReadiness


class Repository:
    def __init__(self, decision): self.decision=decision;self.calls=[]
    def latest(self, order_id): self.calls.append(order_id);return self.decision


@pytest.mark.parametrize('required,status,reference,blocked',[
    (True,None,'',True),(False,None,'',False),
    (True,'APPROVED','',True),(True,'APPROVED','synthetic-reference',False),
    (True,'NOT_REQUIRED','',True),(False,'NOT_REQUIRED','',False),
    (False,'PENDING','',True),
])
def test_latest_explicit_evidence_controls_worklist(required,status,reference,blocked):
    repo=Repository(Row(status=status,approval_no=reference) if status else None)
    service=InsuranceReadiness(repo)
    order=Row(id=1,contract=Row(approval_required=required),paid_amount=100,approval_no='LEGACY-ONLY')
    assert bool(service.blocker(order))==blocked
    assert repo.calls==[1]
    if blocked:
        with pytest.raises(ValueError,match='Insurance approval is incomplete'):service.assert_ready(order)
    else:service.assert_ready(order)


def test_independent_repositories_do_not_share_latest_decisions():
    order=Row(id=1,contract=Row(approval_required=True))
    approved=InsuranceReadiness(Repository(Row(status='APPROVED',approval_no='synthetic')))
    pending=InsuranceReadiness(Repository(Row(status='PENDING',approval_no='')))
    assert not approved.blocker(order) and pending.blocker(order)
