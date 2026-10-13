"""Clinical scope access decisions through a supplied order-match repository."""


class ClinicalScopeAccess:
    def __init__(self, repository):
        self.repository = repository

    def allowed(self, user, order, scope):
        if not scope:
            return True
        if not user or not user.active or not order or scope.get('invalid'):
            return False
        return self.repository.order_matches(order.id, scope)
