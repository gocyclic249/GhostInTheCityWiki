"""The scrapers must not overwrite a good index with a failed scrape."""

import json
import os
import tempfile
import unittest
from unittest import mock

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


media = load_script("scrape_media.py", "scrape_media_under_test")


class TestMediaGuard(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = os.path.join(self.tmp.name, "media_index.json")
        self.good = [
            {"post_id": str(i), "title": f"Post {i}",
             "images": [{"local_file": f"{i}_1.png"}]}
            for i in range(1, 101)
        ]
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump(self.good, f)

        self.original_index_path = media.INDEX_PATH
        self.original_fetch = media.fetch_threadmark_index
        media.INDEX_PATH = self.path
        self.addCleanup(self.restore)

    def restore(self):
        media.INDEX_PATH = self.original_index_path
        media.fetch_threadmark_index = self.original_fetch

    def set_scrape_result(self, entries):
        media.fetch_threadmark_index = lambda: entries

    def current(self):
        with open(self.path, encoding="utf-8") as f:
            return json.load(f)

    def test_empty_scrape_is_refused(self):
        self.set_scrape_result([])
        self.assertIsNone(media.cmd_build_index())
        self.assertEqual(len(self.current()), 100)

    def test_large_drop_is_refused(self):
        self.set_scrape_result([{"post_id": str(i)} for i in range(1, 51)])
        self.assertIsNone(media.cmd_build_index())
        self.assertEqual(len(self.current()), 100)

    def test_written_scrape_preserves_image_metadata(self):
        fresh = [{"post_id": str(i), "title": f"Post {i}"} for i in range(1, 101)]
        self.set_scrape_result(fresh)
        returned = media.cmd_build_index()
        self.assertEqual(len(returned), 100)
        self.assertEqual(self.current()[0]["images"], [{"local_file": "1_1.png"}])

    def test_returns_a_list_for_cmd_download(self):
        # cmd_download does len() on this return value — a bool would raise.
        self.set_scrape_result([{"post_id": str(i)} for i in range(1, 101)])
        self.assertIsInstance(media.cmd_build_index(), list)


class TestMediaTavilyOptional(unittest.TestCase):
    """get_tavily_key() calls sys.exit(1) when TAVILY_API_KEY is unset. That's
    a SystemExit, not an Exception, so it must never escape scrape_media's
    module-level probe — Tavily is documented as optional with a direct-HTTP
    fallback, and the module must stay importable without the key.
    """

    def test_imports_with_has_tavily_false_when_key_absent(self):
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("TAVILY_API_KEY", None)
            module = load_script("scrape_media.py", "scrape_media_no_tavily_key")
        self.assertFalse(module.HAS_TAVILY)
