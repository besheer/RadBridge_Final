"""Contact profile persistence with the original default department behavior."""


class SqlAlchemyContactRepository:
    def __init__(self, session, Profile):self.session,self.Profile=session,Profile

    def profile(self, user_id):
        return self.session.query(self.Profile).filter_by(user_id=user_id).first()

    def ensure_profile(self, user):
        row=self.profile(user.id)
        if row is None:
            row=self.Profile(user_id=user.id,department=user.role.name if user.role else '')
            self.session.add(row);self.session.flush()
        return row
