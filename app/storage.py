"""SQLite demo case store. Synthetic data only; single-instance local development."""
import json
import os
import sqlite3
import threading
from contextlib import contextmanager
from pathlib import Path
from .core import Case

DEFAULT_PATH = Path(__file__).resolve().parents[1] / 'data' / 'cases.sqlite3'

class CaseMissing(Exception):
    pass

class StaleCase(Exception):
    pass

class SQLiteCaseStore:
    def __init__(self, path=None):
        self.path = str(path or os.getenv('CASE_DB_PATH') or DEFAULT_PATH)
        self.lock = threading.RLock()
        Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        with self._db() as conn:
            conn.execute('CREATE TABLE IF NOT EXISTS cases (id TEXT PRIMARY KEY, version INTEGER NOT NULL, body TEXT NOT NULL)')

    @contextmanager
    def _db(self):
        conn = sqlite3.connect(self.path, timeout=10)
        try:
            conn.execute('PRAGMA busy_timeout=10000')
            with conn:
                yield conn
        finally:
            conn.close()

    @staticmethod
    def _encode(c):
        return json.dumps({k:getattr(c,k) for k in ('id','transcript','fields','version',
                   'confirmation_digest','confirmed_version','submitted','referral_id','events',
                   'reviewed_digest','reviewed_version','submission_key','conflicts','sources','resolutions')},
                   ensure_ascii=False)

    @staticmethod
    def _decode(raw):
        return Case(**json.loads(raw))

    def create(self, c):
        with self.lock, self._db() as conn:
            conn.execute('INSERT INTO cases (id,version,body) VALUES (?,?,?)', (c.id,c.version,self._encode(c)))
        return c

    def get(self, id):
        with self.lock, self._db() as conn:
            row=conn.execute('SELECT body FROM cases WHERE id=?',(id,)).fetchone()
        if row is None: raise CaseMissing()
        return self._decode(row[0])

    def mutate(self, id, operation, expected_version=None):
        with self.lock:
            with self._db() as conn:
                conn.execute('BEGIN IMMEDIATE')
                row=conn.execute('SELECT body FROM cases WHERE id=?',(id,)).fetchone()
                if row is None: raise CaseMissing()
                c=self._decode(row[0])
                if expected_version is not None and c.version != expected_version:
                    raise StaleCase('This case has changed. Reload before saving.')
                result=operation(c)
                conn.execute('UPDATE cases SET version=?,body=? WHERE id=?', (c.version,self._encode(c),id))
        return c, result

    def clear(self):
        with self.lock, self._db() as conn:
            conn.execute('DELETE FROM cases')

    def count(self):
        with self.lock, self._db() as conn:
            return conn.execute('SELECT COUNT(*) FROM cases').fetchone()[0]
