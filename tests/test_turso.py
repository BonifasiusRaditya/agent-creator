import libsql
import pytest

from trendforge.db import Database
from trendforge.errors import AppError


def test_remote_driver_named_rows_and_nested_rollback(tmp_path, monkeypatch):
    actual = libsql.connect
    calls = []
    def connect(url, **kwargs):
        calls.append(url)
        return actual(str(tmp_path / 'remote.sqlite3'))
    monkeypatch.setattr(libsql, 'connect', connect)
    db = Database(tmp_path / 'unused.sqlite3', backend='turso', url='libsql://test.turso.io', token='test-secret')
    p = db.create_project({'niche': 'Database test'})
    assert db.project(p['id'])['niche'] == 'Database test'
    with pytest.raises(RuntimeError):
        with db.connect() as c:
            db.update_project(p['id'], {'niche': 'Must roll back'})
            assert c.execute('SELECT data FROM projects').fetchone()['data']
            raise RuntimeError('Test rollback')
    assert db.project(p['id'])['niche'] == 'Database test'
    assert len(db.events(p['id'])) == 1
    assert calls and all(u == 'libsql://test.turso.io' for u in calls)
    assert not (tmp_path / 'unused.sqlite3').exists()


def test_incomplete_remote_configuration_never_falls_back(tmp_path, monkeypatch):
    monkeypatch.setenv('TURSO_DATABASE_URL', 'libsql://test.turso.io')
    with pytest.raises(AppError) as error:
        Database(tmp_path / 'unused.sqlite3')
    assert error.value.code == 'DATABASE_CONFIG'
    assert not (tmp_path / 'unused.sqlite3').exists()


def test_remote_errors_hide_connection_secrets(tmp_path, monkeypatch):
    def failed(*args, **kwargs):
        raise libsql.Error('private-url private-token')
    monkeypatch.setattr(libsql, 'connect', failed)
    with pytest.raises(AppError) as error:
        Database(tmp_path / 'unused.sqlite3', backend='turso', url='libsql://private.turso.io', token='private-token')
    assert error.value.status == 503
    assert 'private' not in str(error.value)
