import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
import pytest
import jwt
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

os.environ.setdefault('DATABASE_URL','sqlite://')
os.environ.setdefault('JWT_ISSUER','radbridge-test-identity')
os.environ.setdefault('JWT_AUDIENCE','radbridge-decision-engine')
from app.database import get_db
from app.main import app
from app.models import Base

@pytest.fixture
def api(tmp_path,monkeypatch):
    private=rsa.generate_private_key(public_exponent=65537,key_size=2048)
    public=private.public_key()
    public_path=tmp_path/'public.pem'
    public_path.write_bytes(public.public_bytes(serialization.Encoding.PEM,
        serialization.PublicFormat.SubjectPublicKeyInfo))
    monkeypatch.setenv('JWT_PUBLIC_KEY_FILE',str(public_path))
    monkeypatch.setenv('JWT_ISSUER','radbridge-test-identity')
    monkeypatch.setenv('JWT_AUDIENCE','radbridge-decision-engine')
    engine=create_engine('sqlite://',connect_args={'check_same_thread':False},poolclass=StaticPool)
    Base.metadata.create_all(engine)
    Session=sessionmaker(bind=engine,expire_on_commit=False)
    def override_db():
        db=Session()
        try:yield db
        finally:db.close()
    app.dependency_overrides[get_db]=override_db
    with TestClient(app) as client:
        yield client,private,Session
    app.dependency_overrides.clear()
    Base.metadata.drop_all(engine)
    engine.dispose()

def bearer(private,sub='helpdesk-1',branch='branch-1',roles=None):
    token=jwt.encode({'iss':'radbridge-test-identity','aud':'radbridge-decision-engine',
        'sub':sub,'branch_id':branch,'roles':roles or ['HELPDESK'],
        'exp':datetime.now(timezone.utc)+timedelta(minutes=2)},private,algorithm='RS256')
    return {'Authorization':'Bearer '+token}
