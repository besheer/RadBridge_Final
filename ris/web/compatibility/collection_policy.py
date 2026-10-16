"""Legacy branch collection checks composed at the web edge."""
from application.services.finance.collection_access import CollectionAccess
from infrastructure.adapters.finance.collection_repository import SqlAlchemyCollectionRepository


def _service(m):
    return CollectionAccess(SqlAlchemyCollectionRepository(m.db.session,m.Branch))


def reception_collection_allowed(user, *, runtime):
    return _service(runtime).reception_allowed(user)


def require_collection_branch(branch_id, *, runtime):
    m=runtime
    if not _service(m).branch_allowed(m.current_user(),branch_id):
        m.abort(403)
