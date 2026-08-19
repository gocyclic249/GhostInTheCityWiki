"""AO3 is the store of record for chapter text; chapters/ is gitignored."""

import os
import tempfile
import unittest

from tests.helpers import load_script

scrape = load_script("scrape.py", "scrape_under_test")

VALID = "# 42. Chapter 42\n\n*Source: https://example.invalid*\n\n---\n\n" + ("word " * 400)


class TestClassifyChapter(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)

    def write(self, name, text):
        path = os.path.join(self.tmp.name, name)
        with open(path, "w", encoding="utf-8") as f:
            f.write(text)
        return path

    def test_missing_file(self):
        path = os.path.join(self.tmp.name, "nope.md")
        self.assertEqual(scrape.classify_chapter(path), "missing")

    def test_valid_file(self):
        self.assertEqual(scrape.classify_chapter(self.write("ok.md", VALID)), "present")

    def test_truncated_file_is_suspect(self):
        self.assertEqual(scrape.classify_chapter(self.write("t.md", "# 42\n")), "suspect")

    def test_file_without_title_line_is_suspect(self):
        body = "no heading here\n" + ("word " * 400)
        self.assertEqual(scrape.classify_chapter(self.write("n.md", body)), "suspect")

    def test_empty_file_is_suspect(self):
        self.assertEqual(scrape.classify_chapter(self.write("e.md", "")), "suspect")

    def test_rejects_empty_path(self):
        with self.assertRaises(ValueError):
            scrape.classify_chapter("")


class TestChapterFilename(unittest.TestCase):
    def test_zero_pads_to_four_digits(self):
        name = scrape.chapter_filename(42, {"title": "42. Chapter 42"})
        self.assertEqual(name, "0042_42._Chapter_42.md")

    def test_rejects_chapter_zero(self):
        with self.assertRaises(ValueError):
            scrape.chapter_filename(0, {"title": "x"})

    def test_rejects_missing_title(self):
        with self.assertRaises(ValueError):
            scrape.chapter_filename(1, {})


class TestCmdRestore(unittest.TestCase):
    """cmd_restore must fetch only what is missing or damaged."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)

        self.index = [
            {"chapter_id": "1", "title": "1. Chapter 1",
             "ao3_url": "https://example.invalid/1", "date": "2022-10-15"},
            {"chapter_id": "2", "title": "2. Chapter 2",
             "ao3_url": "https://example.invalid/2", "date": "2022-10-16"},
            {"chapter_id": "3", "title": "3. Chapter 3",
             "ao3_url": "https://example.invalid/3", "date": "2022-10-17"},
        ]

        self.original_output = scrape.OUTPUT_DIR
        self.original_get_index = scrape.get_chapter_index
        self.original_write = scrape.write_chapter
        self.original_delay = scrape.DELAY

        scrape.OUTPUT_DIR = self.tmp.name
        scrape.get_chapter_index = lambda: self.index
        scrape.DELAY = 0  # no politeness sleep in tests
        self.written = []

        def fake_write(chapter_num, chapter, filepath):
            self.written.append(chapter_num)
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(VALID)
            return True

        scrape.write_chapter = fake_write
        self.addCleanup(self.restore)

    def restore(self):
        scrape.OUTPUT_DIR = self.original_output
        scrape.get_chapter_index = self.original_get_index
        scrape.write_chapter = self.original_write
        scrape.DELAY = self.original_delay

    def place(self, chapter_num, text):
        name = scrape.chapter_filename(chapter_num, self.index[chapter_num - 1])
        with open(os.path.join(self.tmp.name, name), "w", encoding="utf-8") as f:
            f.write(text)

    def test_fetches_everything_when_empty(self):
        self.assertEqual(scrape.cmd_restore(), 0)
        self.assertEqual(self.written, [1, 2, 3])

    def test_skips_present_chapters(self):
        self.place(2, VALID)
        scrape.cmd_restore()
        self.assertEqual(self.written, [1, 3])

    def test_refetches_truncated_chapter(self):
        self.place(1, VALID)
        self.place(2, "# 2\n")  # under MIN_CHAPTER_BYTES
        self.place(3, VALID)
        scrape.cmd_restore()
        self.assertEqual(self.written, [2])

    def test_nothing_to_restore_when_all_present(self):
        for n in (1, 2, 3):
            self.place(n, VALID)
        self.assertEqual(scrape.cmd_restore(), 0)
        self.assertEqual(self.written, [])

    def test_range_bounds_are_honoured(self):
        scrape.cmd_restore(start_num=2, end_num=3)
        self.assertEqual(self.written, [2, 3])

    def test_counts_failures(self):
        scrape.write_chapter = lambda num, ch, path: False
        self.assertEqual(scrape.cmd_restore(start_num=1, end_num=2), 2)

    def test_rejects_bad_start(self):
        with self.assertRaises(ValueError):
            scrape.cmd_restore(start_num=0)


if __name__ == "__main__":
    unittest.main()
