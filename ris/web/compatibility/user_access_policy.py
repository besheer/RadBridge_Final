"""User contact storage and access review without sending messages."""
import ast,json,re
from domain.identity.contact_policy import CONTACT_FIELDS,NO_REPORT_EDIT,parse_contacts,page_access
from domain.identity.user_management import can_manage_target
from application.services.identity.user_contacts import UserContacts
from infrastructure.adapters.identity.contact_repository import SqlAlchemyContactRepository
from functools import lru_cache
from pathlib import Path
def _contact_service(m):
    return UserContacts(SqlAlchemyContactRepository(m.db.session,m.UserProfile),m.user_profile_settings)


def contacts(user):
    from application.legacy_runtime import resolve_runtime
    return _contact_service(resolve_runtime()).contacts(user)
def save_contacts(user,data,form):
    from application.legacy_runtime import resolve_runtime
    return _contact_service(resolve_runtime()).save(user,data,form)
def require_manage_target(user=None,role=None):
    from application.legacy_runtime import resolve_runtime
    m=resolve_runtime()
    if not can_manage_target(m.current_user(),user,role):m.abort(403)
@lru_cache(maxsize=1)
def route_catalog():
    from application.legacy_runtime import resolve_runtime as _rb_runtime; m = _rb_runtime()
    from web.source_contract import app_source
    tree=ast.parse(app_source())
    gates={}
    for fn in tree.body:
        if not isinstance(fn,(ast.FunctionDef,ast.AsyncFunctionDef)):continue
        perms=[];login=False
        for dec in fn.decorator_list:
            if isinstance(dec,ast.Name) and dec.id=='login_required':login=True
            if isinstance(dec,ast.Call) and isinstance(dec.func,ast.Name) and dec.func.id=='require_perm' and dec.args and isinstance(dec.args[0],ast.Constant):
                perms.append(dec.args[0].value);login=True
        gates[fn.name]=(perms,login)
    rows=[]
    for rule in m.app.url_map.iter_rules():
        if rule.endpoint=='static' or 'GET' not in rule.methods:continue
        perms,login=gates.get(rule.endpoint,([],False))
        rows.append({'path':rule.rule,'endpoint':rule.endpoint,'permissions':perms,'login':login,'section':rule.rule.strip('/').split('/')[0] or 'dashboard','direct':'<' not in rule.rule})
    return sorted(rows,key=lambda x:(x['section'],x['path']))


def permission_catalog():
    from application.legacy_runtime import resolve_runtime as _rb_runtime; m = _rb_runtime()
    names=set(m.ALL_PERMISSIONS)
    for values in m.ROLE_PERMS.values():names.update(values)
    for role in m.Role.query.all():names.update(role.permissions())
    from web.source_contract import app_source
    tree=ast.parse(app_source())
    for node in ast.walk(tree):
        if isinstance(node,ast.Call) and isinstance(node.func,ast.Name) and node.func.id=='require_perm' and node.args and isinstance(node.args[0],ast.Constant):
            names.add(node.args[0].value)
    return sorted(name for name in names if isinstance(name,str) and name!='*')
