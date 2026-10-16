import tempfile
import unittest
from pathlib import Path
from datetime import datetime, timezone
from stats_store import StatsStore, day_key

class StatsTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / 'data.sqlite3'
        self.store = StatsStore(self.path)
    def tearDown(self):
        self.tmp.cleanup()
    def test_dedup_and_reopen(self):
        self.store.touch(1)
        self.store.touch(1)
        self.store.touch(2)
        self.assertEqual(StatsStore(self.path).summary()['users'], 2)
    def test_riyadh_midnight(self):
        self.assertEqual(day_key(datetime(2026,10,16,22,tzinfo=timezone.utc)), '2026-10-17')
        self.store.touch(1, datetime(2026,10,16,20,tzinfo=timezone.utc))
        self.assertEqual(self.store.summary(datetime(2026,10,16,22,tzinfo=timezone.utc))['active_today'], 0)
    def test_successful_requests_only_once(self):
        self.store.downloaded('a', 0)
        self.store.downloaded('b', 3)
        self.store.downloaded('b', 3)
        self.assertEqual(self.store.summary()['requests'], 1)
        self.assertEqual(self.store.summary()['files'], 3)
