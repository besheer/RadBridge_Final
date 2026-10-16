"""Delegated user-management hierarchy; route permissions remain separate."""


def can_manage_target(actor, user=None, role=None):
    if not actor or not actor.active:return False
    if actor.role and actor.role.code=='SUPER_ADMIN':return True
    if user and user.role and (user.role.code=='SUPER_ADMIN' or '*' in user.role.permissions()):return False
    if role:
        owned=set(actor.role.permissions() if actor.role else [])
        if role.code=='SUPER_ADMIN' or not set(role.permissions()).issubset(owned):return False
    return True
