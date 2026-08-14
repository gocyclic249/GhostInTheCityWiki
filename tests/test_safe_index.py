"""Tests for lib.safe_index — the guard that stops a failed scrape blanking an index."""

import json
import os
import stat
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lib.safe_index import (
    read_index_count,
    write_index_atomic,
    write_index_guarded,
)


def make_entries(n):
    return [{"index": i, "title": f"Entry {i}"} for i in range(1, n + 1)]


class TestReadIndexCount(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = os.path.join(self.tmp.name, "index.json")
        self.addCleanup(self.tmp.cleanup)

    def test_missing_file_counts_zero(self):
        self.assertEqual(read_index_count(self.path), 0)

    def test_counts_list_entries(self):
        write_index_atomic(self.path, make_entries(7))
        self.assertEqual(read_index_count(self.path), 7)

    def test_counts_dict_keys(self):
        write_index_atomic(self.path, {"a": 1, "b": 2})
        self.assertEqual(read_index_count(self.path), 2)


class TestWriteIndexAtomic(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = os.path.join(self.tmp.name, "index.json")
        self.addCleanup(self.tmp.cleanup)

    def test_writes_readable_json(self):
        write_index_atomic(self.path, make_entries(3))
        with open(self.path, encoding="utf-8") as f:
            self.assertEqual(len(json.load(f)), 3)

    def test_preserves_unicode_unescaped(self):
        write_index_atomic(self.path, [{"title": "Motoko — モトコ"}])
        with open(self.path, encoding="utf-8") as f:
            raw = f.read()
        self.assertIn("モトコ", raw)

    def test_leaves_no_temp_files(self):
        write_index_atomic(self.path, make_entries(3))
        self.assertEqual(os.listdir(self.tmp.name), ["index.json"])

    def test_rejects_non_collection(self):
        with self.assertRaises(TypeError):
            write_index_atomic(self.path, "not an index")


class TestWriteIndexGuarded(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = os.path.join(self.tmp.name, "index.json")
        self.addCleanup(self.tmp.cleanup)
        write_index_atomic(self.path, make_entries(100))
        with open(self.path, "rb") as f:
            self.original_bytes = f.read()

    def current_bytes(self):
        with open(self.path, "rb") as f:
            return f.read()

    def test_refuses_zero_entries(self):
        self.assertFalse(write_index_guarded(self.path, []))
        self.assertEqual(self.current_bytes(), self.original_bytes)

    def test_refuses_large_shrink(self):
        self.assertFalse(write_index_guarded(self.path, make_entries(80)))
        self.assertEqual(self.current_bytes(), self.original_bytes)

    def test_allows_small_shrink(self):
        self.assertTrue(write_index_guarded(self.path, make_entries(95)))
        self.assertEqual(read_index_count(self.path), 95)

    def test_allows_growth(self):
        self.assertTrue(write_index_guarded(self.path, make_entries(120)))
        self.assertEqual(read_index_count(self.path), 120)

    def test_backs_up_previous_index(self):
        write_index_guarded(self.path, make_entries(120))
        with open(self.path + ".bak", "rb") as f:
            self.assertEqual(f.read(), self.original_bytes)

    def test_force_overrides_refusal(self):
        self.assertTrue(write_index_guarded(self.path, [], force=True))
        self.assertEqual(read_index_count(self.path), 0)

    def test_writes_when_no_existing_index(self):
        fresh = os.path.join(self.tmp.name, "new.json")
        self.assertTrue(write_index_guarded(fresh, []))
        self.assertEqual(read_index_count(fresh), 0)

    def test_rejects_bad_min_ratio(self):
        with self.assertRaises(ValueError):
            write_index_guarded(self.path, make_entries(50), min_ratio=0)

    def test_preserves_file_mode_on_update(self):
        # Existing file starts at 0o644
        os.chmod(self.path, 0o644)
        original_mode = stat.S_IMODE(os.stat(self.path).st_mode)
        self.assertEqual(original_mode, 0o644)
        # After guarded write, mode should still be 0o644
        write_index_guarded(self.path, make_entries(120))
        new_mode = stat.S_IMODE(os.stat(self.path).st_mode)
        self.assertEqual(new_mode, 0o644)

    def test_new_file_gets_default_mode(self):
        fresh = os.path.join(self.tmp.name, "new.json")
        write_index_guarded(fresh, make_entries(5))
        mode = stat.S_IMODE(os.stat(fresh).st_mode)
        self.assertEqual(mode, 0o644)
