"""Verify signed identity assertions issued by the trusted RadBridge gateway."""
import os
from dataclasses import dataclass
from pathlib import Path
import jwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

bearer=HTTPBearer(auto_error=False)

@dataclass(frozen=True)
class Actor:
    user_id: str
    branch_id: str | None
    roles: frozenset[str]

def current_actor(credentials: HTTPAuthorizationCredentials | None = Depends(bearer)) -> Actor:
    if not credentials or credentials.scheme.lower() != 'bearer':
        raise HTTPException(status_code=401, detail='Authentication required', headers={'WWW-Authenticate':'Bearer'})
    key_path=os.environ.get('JWT_PUBLIC_KEY_FILE','')
    if not key_path:
        raise HTTPException(status_code=503, detail='Identity verification is not configured')
    try:
        public_key=Path(key_path).read_text(encoding='utf-8')
        claims=jwt.decode(credentials.credentials, public_key, algorithms=['RS256'],
            audience=os.environ['JWT_AUDIENCE'], issuer=os.environ['JWT_ISSUER'],
            options={'require':['exp','sub','iss','aud']})
        user_id=str(claims['sub'])
        branch=str(claims['branch_id']) if claims.get('branch_id') is not None else None
        roles=frozenset(str(role).upper() for role in claims.get('roles',[]))
        if not user_id or not roles:
            raise ValueError('missing identity claims')
        return Actor(user_id,branch,roles)
    except (OSError, KeyError, ValueError, jwt.PyJWTError):
        raise HTTPException(status_code=401, detail='Invalid identity assertion', headers={'WWW-Authenticate':'Bearer'}) from None

def require_roles(*allowed):
    def dependency(actor: Actor = Depends(current_actor)):
        if not actor.roles.intersection(allowed):
            raise HTTPException(status_code=403, detail='Insufficient role')
        if 'SUPER_ADMIN' not in actor.roles and not actor.branch_id:
            raise HTTPException(status_code=403, detail='Branch scope required')
        return actor
    return dependency
