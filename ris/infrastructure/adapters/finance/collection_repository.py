"""Explicit branch lookup for reception collection settings."""


class SqlAlchemyCollectionRepository:
    def __init__(self, session, Branch):
        self.session, self.Branch = session, Branch

    def branch(self, branch_id):
        return self.session.get(self.Branch, branch_id)
