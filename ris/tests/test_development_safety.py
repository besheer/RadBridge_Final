import importlib.util
from pathlib import Path
import pytest

ROOT=Path(__file__).resolve().parents[2]
def load(name,path):
    spec=importlib.util.spec_from_file_location(name,ROOT/path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module

@pytest.mark.parametrize("dsn",[
    "", "postgresql+psycopg2://radbridge_test:dummy@example.invalid/radbridge_dev_test",
    "postgresql+psycopg2://radbridge_test:dummy@localhost/production",
    "postgresql+psycopg2://root:dummy@localhost/radbridge_dev_test",
    "postgresql://radbridge_test:dummy@localhost/radbridge_dev_test",
])
def test_pg_runner_rejects_non_test_targets(dsn):
    runner=load("development_test_runner","tools/run_tests.py")
    with pytest.raises(ValueError):runner.checked_pg_url(dsn)

def test_pg_runner_allows_dedicated_synthetic_db():
    runner=load("development_test_runner","tools/run_tests.py")
    dsn="postgresql+psycopg2://radbridge_test:synthetic-only@localhost/radbridge_dev_test"
    assert runner.checked_pg_url(dsn)==dsn

def test_initializer_requires_opt_in(monkeypatch):
    module=load("development_initializer","development/initialize.py")
    monkeypatch.delenv("RADBRIDGE_DEVELOPMENT",raising=False)
    with pytest.raises(RuntimeError):module.validate()

@pytest.mark.parametrize("dsn",[
    "postgresql+psycopg2://radbridge_dev:dummy@example.invalid/radbridge_dev",
    "postgresql+psycopg2://radbridge_dev:dummy@db/production",
    "postgresql+psycopg2://production:dummy@db/radbridge_dev",
])
def test_initializer_rejects_non_development_db(monkeypatch,dsn):
    module=load("development_initializer","development/initialize.py")
    monkeypatch.setenv("RADBRIDGE_DEVELOPMENT","1")
    monkeypatch.setenv("RADBRIDGE_BOOTSTRAP_ON_IMPORT","0")
    monkeypatch.setenv("DATABASE_URL",dsn)
    with pytest.raises(RuntimeError):module.validate()

def test_initializer_accepts_only_explicit_compose_target(monkeypatch):
    module=load("development_initializer","development/initialize.py")
    monkeypatch.setenv("RADBRIDGE_DEVELOPMENT","1")
    monkeypatch.setenv("RADBRIDGE_BOOTSTRAP_ON_IMPORT","0")
    monkeypatch.setenv("DATABASE_URL","postgresql+psycopg2://radbridge_dev:synthetic-only@db/radbridge_dev")
    module.validate()
    monkeypatch.setenv("RADBRIDGE_BOOTSTRAP_ON_IMPORT","1")
    with pytest.raises(RuntimeError):module.validate()
