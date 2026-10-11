"""Legacy branch collection checks composed at the web edge."""
from application.services.finance.collection_access import CollectionAccess
from infrastructure.adapters.finance.collection_repository import SqlAlchemyCollectionRepository


def _service(m):
    return CollectionAccess(SqlAlchemyCollectionRepository(m.db.session,m.Branch))


def reception_collection_allowed(user):
    from application.legacy_runtime import resolve_runtime
    return _service(resolve_runtime()).reception_allowed(user)


def require_collection_branch(branch_id):
    from application.legacy_runtime import resolve_runtime
    m=resolve_runtime()
    if not _service(m).branch_allowed(m.current_user(),branch_id):
        m.abort(403)
