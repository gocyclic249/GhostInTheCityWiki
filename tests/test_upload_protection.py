"""Media lives only on Neocities. The uploader must never delete it."""

import unittest

from tests.helpers import load_script

upload = load_script("wiki/scripts/upload.py", "upload_under_test")


class TestIsProtected(unittest.TestCase):
    def test_media_paths_are_protected(self):
        self.assertTrue(upload.is_protected("media/87702034_1.jpg"))

    def test_html_paths_are_not(self):
        self.assertFalse(upload.is_protected("index.html"))
        self.assertFalse(upload.is_protected("characters/motoko.html"))

    def test_lookalike_path_is_not_protected(self):
        self.assertFalse(upload.is_protected("mediaeval.html"))

    def test_rejects_non_string(self):
        with self.assertRaises(TypeError):
            upload.is_protected(None)


class TestComputeChanges(unittest.TestCase):
    def test_missing_media_is_never_deleted(self):
        manifest = {"index.html": "a1", "media/art.png": "b2"}
        local = {"index.html": "a1"}
        to_upload, to_delete, missing_protected = upload.compute_changes(manifest, local)
        self.assertEqual(to_upload, [])
        self.assertEqual(to_delete, [])
        self.assertEqual(missing_protected, ["media/art.png"])

    def test_missing_html_is_deleted(self):
        manifest = {"index.html": "a1", "old.html": "c3"}
        local = {"index.html": "a1"}
        _, to_delete, missing_protected = upload.compute_changes(manifest, local)
        self.assertEqual(to_delete, ["old.html"])
        self.assertEqual(missing_protected, [])

    def test_changed_and_new_files_upload(self):
        manifest = {"index.html": "a1"}
        local = {"index.html": "CHANGED", "new.html": "d4"}
        to_upload, to_delete, _ = upload.compute_changes(manifest, local)
        self.assertEqual(to_upload, ["index.html", "new.html"])
        self.assertEqual(to_delete, [])

    def test_unchanged_files_are_skipped(self):
        manifest = {"index.html": "a1"}
        local = {"index.html": "a1"}
        to_upload, to_delete, missing_protected = upload.compute_changes(manifest, local)
        self.assertEqual((to_upload, to_delete, missing_protected), ([], [], []))

    def test_empty_local_tree_deletes_no_media(self):
        manifest = {f"media/{i}.png": str(i) for i in range(126)}
        to_upload, to_delete, missing_protected = upload.compute_changes(manifest, {})
        self.assertEqual(to_delete, [])
        self.assertEqual(len(missing_protected), 126)
