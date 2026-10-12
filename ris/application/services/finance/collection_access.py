"""Branch collection checks over explicit evidence; route permissions remain authoritative."""


class CollectionAccess:
    def __init__(self, repository):
        self.repository = repository

    def reception_allowed(self, user):
        if not user or not user.active or not user.branch_id:
            return False
        branch = self.repository.branch(user.branch_id)
        return bool(branch and branch.active and branch.reception_collection_enabled)

    def branch_allowed(self, user, branch_id):
        if not user or not user.active:
            return False
        code = user.role.code if user.role else ''
        if code in ('RECEPTION','CASHIER'):
            if not user.branch_id or user.branch_id != branch_id:
                return False
            if code == 'RECEPTION' and not self.reception_allowed(user):
                return False
        return True
