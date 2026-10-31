"""Copy one stopped local workspace into an empty Turso schema, preserving row order.

Run with --apply to write. Local files are retained and backed up first.
"""
import argparse
import json
import sqlite3
from datetime import datetime, timezone

from trendforge.config import DATA
from trendforge.db import Database


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    source_path = DATA / 'trendforge.sqlite3'
    # Existing login sessions are deliberately not exported. Sign in again after switching.
    tables = ('projects', 'documents', 'jobs', 'events')
    if not source_path.is_file():
        print('No local database to migrate.')
        return
    source = sqlite3.connect(source_path.as_uri() + '?mode=ro', uri=True)
    target = Database(source_path, backend='turso')
    try:
        counts = {t: source.execute(f'SELECT COUNT(*) FROM {t}').fetchone()[0] for t in tables}
        with target.connect() as c:
            remote = {t: c.execute(f'SELECT COUNT(*) AS n FROM {t}').fetchone()['n'] for t in tables}
        print(json.dumps({'local_rows': counts, 'turso_rows': remote, 'apply': args.apply}))
        if not args.apply:
            return
        if any(remote.values()):
            raise RuntimeError('Turso is not empty. Migration stopped without merging or replacing data.')
        if source.execute("SELECT COUNT(*) FROM jobs WHERE status IN ('queued','running','cancelling')").fetchone()[0]:
            raise RuntimeError('Local jobs are active. Stop or finish them before migration.')
        backup_dir = DATA / 'backups'
        backup_dir.mkdir(exist_ok=True)
        backup_path = backup_dir / ('before-turso-' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%f') + '.sqlite3')
        with sqlite3.connect(backup_path) as backup:
            source.backup(backup)
        with target.connect() as c:
            c.execute('BEGIN IMMEDIATE')
            for table in tables:
                # Check again under the writer transaction before inserting anything.
                if c.execute(f'SELECT COUNT(*) AS n FROM {table}').fetchone()['n']:
                    raise RuntimeError('Turso changed during migration. Rolled back.')
                columns = [row[1] for row in source.execute(f'PRAGMA table_info({table})')]
                placeholders = ','.join('?' for _ in columns)
                for row in source.execute(f'SELECT * FROM {table} ORDER BY rowid'):
                    c.execute(f'INSERT INTO {table} VALUES ({placeholders})', row)
                if c.execute(f'SELECT COUNT(*) AS n FROM {table}').fetchone()['n'] != counts[table]:
                    raise RuntimeError('Migration row counts did not match. Rolled back.')
        print('Migration committed; local database and backup retained. Video files stay in the same data folder.')
    finally:
        source.close()


if __name__ == '__main__':
    main()
