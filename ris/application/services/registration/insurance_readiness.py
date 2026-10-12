"""Insurance readiness with an explicit latest-decision repository."""
from domain.registration.insurance import approval_blocker


class InsuranceReadiness:
    def __init__(self, repository):
        self.repository = repository

    def blocker(self, order):
        required=bool(getattr(getattr(order,'contract',None),'approval_required',False))
        return approval_blocker(required,self.repository.latest(order.id))

    def assert_ready(self, order):
        blocker=self.blocker(order)
        if blocker:
            raise ValueError(blocker)
