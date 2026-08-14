"""The scrapers must not overwrite a good index with a failed scrape."""

import json
import os
import tempfile
import unittest

from tests.helpers import load_script

sidestories = load_script("scrape_sidestories.py", "scrape_sidestories_under_test")


class TestSidestoriesGuard(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = os.path.join(self.tmp.name, "sidestories_index.json")
        self.good = [{"index": i, "title": f"Story {i}"} for i in range(1, 101)]
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump(self.good, f)

        self.original_index_path = sidestories.INDEX_PATH
        self.original_fetch = sidestories.fetch_all_threadmarks
        sidestories.INDEX_PATH = self.path
        self.addCleanup(self.restore)

    def restore(self):
        sidestories.INDEX_PATH = self.original_index_path
        sidestories.fetch_all_threadmarks = self.original_fetch

    def set_scrape_result(self, entries):
        sidestories.fetch_all_threadmarks = lambda: entries

    def current(self):
        with open(self.path, encoding="utf-8") as f:
            return json.load(f)

    def test_empty_scrape_is_refused(self):
        self.set_scrape_result([])
        self.assertIsNone(sidestories.cmd_build_index())
        self.assertEqual(len(self.current()), 100)

    def test_large_drop_is_refused(self):
        self.set_scrape_result(self.good[:50])
        self.assertIsNone(sidestories.cmd_build_index())
        self.assertEqual(len(self.current()), 100)

    def test_growth_is_written(self):
        grown = self.good + [{"index": 101, "title": "Story 101"}]
        self.set_scrape_result(grown)
        self.assertEqual(len(sidestories.cmd_build_index()), 101)
        self.assertEqual(len(self.current()), 101)

    def test_force_overrides(self):
        self.set_scrape_result([])
        self.assertEqual(sidestories.cmd_build_index(force=True), [])
        self.assertEqual(self.current(), [])
