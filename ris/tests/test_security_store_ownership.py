from types import SimpleNamespace
import pytest

from infrastructure.adapters.operations import security_store


def test_readonly_connection_is_closed_on_success_and_failure(tmp_path, monkeypatch):
    closed, calls = [], []

    def connect(database, **options):
        calls.append((database, options))
        return SimpleNamespace(row_factory=None, close=lambda: closed.append(True))

    monkeypatch.setattr(security_store.sqlite3, 'connect', connect)
    with security_store.readonly_database(tmp_path / 'events.sqlite') as connection:
        assert connection.row_factory is security_store.sqlite3.Row
    assert len(closed) == 1
    with pytest.raises(ValueError, match='synthetic query failure'):
        with security_store.readonly_database(tmp_path / 'events.sqlite'):
            raise ValueError('synthetic query failure')
    assert len(closed) == 2
    assert all(uri.endswith('?mode=ro') and options == {'uri': True, 'timeout': 3} for uri, options in calls)
