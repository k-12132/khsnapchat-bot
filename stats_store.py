"""Minimal local counters. Never stores message contents, links, or media."""
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from datetime import datetime, timezone, timedelta

RIYADH = timezone(timedelta(hours=3))

def day_key(now=None):
    return (now or datetime.now(timezone.utc)).astimezone(RIYADH).date().isoformat()

class StatsStore:
    def __init__(self, path):
        self.path = str(path)
        Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            db.executescript('''
                CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY, first_day TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS activity (user_id INTEGER NOT NULL, day TEXT NOT NULL, PRIMARY KEY(user_id, day));
                CREATE TABLE IF NOT EXISTS downloads (request_id TEXT PRIMARY KEY, day TEXT NOT NULL, files INTEGER NOT NULL);
            ''')
    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.path, timeout=10)
        try:
            with db:
                yield db
        finally:
            db.close()
    def touch(self, user_id, now=None):
        day = day_key(now)
        with self.connect() as db:
            db.execute('INSERT OR IGNORE INTO users VALUES (?, ?)', (user_id, day))
            db.execute('INSERT OR IGNORE INTO activity VALUES (?, ?)', (user_id, day))
    def downloaded(self, request_id, files, now=None):
        if files < 1:
            return
        with self.connect() as db:
            db.execute('INSERT OR IGNORE INTO downloads VALUES (?, ?, ?)', (str(request_id), day_key(now), files))
    def summary(self, now=None):
        day = day_key(now)
        with self.connect() as db:
            return {
                'users': db.execute('SELECT COUNT(*) FROM users').fetchone()[0],
                'active_today': db.execute('SELECT COUNT(*) FROM activity WHERE day=?', (day,)).fetchone()[0],
                'requests': db.execute('SELECT COUNT(*) FROM downloads').fetchone()[0],
                'files': db.execute('SELECT COALESCE(SUM(files),0) FROM downloads').fetchone()[0],
                'since': db.execute('SELECT MIN(first_day) FROM users').fetchone()[0] or day,
            }
