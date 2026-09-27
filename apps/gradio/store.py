"""Consent-based local SQLite snapshots and an append-only assessment history."""
import json
import sqlite3
import time
from contextlib import contextmanager
from settings import DATA_DIR

class Store:
    def __init__(self, path=None):
        self.path = path or DATA_DIR / 'learners.sqlite3'
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            db.execute('CREATE TABLE IF NOT EXISTS profiles (id TEXT PRIMARY KEY, state TEXT NOT NULL, updated REAL NOT NULL)')
            db.execute('CREATE TABLE IF NOT EXISTS events (profile TEXT NOT NULL, id TEXT NOT NULL, payload TEXT NOT NULL, created REAL NOT NULL, PRIMARY KEY(profile,id))')

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.path, timeout=10)
        try:
            db.execute('PRAGMA journal_mode=DELETE')
            db.execute('PRAGMA secure_delete=ON')
            with db:
                yield db
        finally:
            db.close()

    def load(self, profile):
        with self.connect() as db:
            row = db.execute('SELECT state FROM profiles WHERE id=?', (profile,)).fetchone()
        return json.loads(row[0]) if row else None

    def save(self, profile, state, event=None):
        if not state.get('consent'):
            return False
        # State contains educational facts, never recordings or raw transcripts.
        with self.connect() as db:
            if event:
                inserted = db.execute('INSERT OR IGNORE INTO events VALUES (?,?,?,?)',
                                      (profile, event['id'], json.dumps(event, ensure_ascii=False), time.time()))
                if not inserted.rowcount:
                    return False
            db.execute('INSERT INTO profiles VALUES (?,?,?) ON CONFLICT(id) DO UPDATE SET state=excluded.state,updated=excluded.updated',
                       (profile, json.dumps(state, ensure_ascii=False), time.time()))
        return True

    def forget(self, profile):
        with self.connect() as db:
            db.execute('DELETE FROM events WHERE profile=?', (profile,))
            db.execute('DELETE FROM profiles WHERE id=?', (profile,))
