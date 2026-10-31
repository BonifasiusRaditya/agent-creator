import sqlite3
import sys

import pytest

from scripts import migrate_to_turso
from trendforge.db import Database


def test_migration_preserves_project_data_and_excludes_sessions(tmp_path, monkeypatch):
    folder = tmp_path / 'source'
    folder.mkdir()
    source = Database(folder / 'trendforge.sqlite3', backend='sqlite')
    p = source.create_project({'niche': 'Synthetic migration test'})
    source.add_doc(p['id'], 'posting_caption', {'text': 'Synthetic test caption'})
    with source.connect() as c:
        c.execute('INSERT INTO sessions VALUES (?,?,?)', ('test-only-session-hash', 1, 'test-csrf'))
    target = Database(tmp_path / 'target.sqlite3', backend='sqlite')
    monkeypatch.setattr(migrate_to_turso, 'DATA', folder)
    monkeypatch.setattr(migrate_to_turso, 'Database', lambda *a, **kw: target)
    monkeypatch.setattr(sys, 'argv', ['migration', '--apply'])
    migrate_to_turso.main()
    assert target.project(p['id'])['niche'] == 'Synthetic migration test'
    assert target.docs(p['id'], 'posting_caption')[0]['text'] == 'Synthetic test caption'
    assert len(target.events(p['id'])) == 1
    with target.connect() as c:
        assert c.execute('SELECT COUNT(*) AS n FROM sessions').fetchone()['n'] == 0
    backup_path = next((folder / 'backups').glob('*.sqlite3'))
    with sqlite3.connect(backup_path) as c:
        assert c.execute('SELECT COUNT(*) FROM projects').fetchone()[0] == 1
    with pytest.raises(RuntimeError, match='not empty'):
        migrate_to_turso.main()
