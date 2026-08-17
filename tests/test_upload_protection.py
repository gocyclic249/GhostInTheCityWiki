"""Media lives only on Neocities. The uploader must never delete it."""

import hashlib
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


REMOTE_LISTING = [
    {"path": "index.html", "is_directory": False, "sha1_hash": "aaa"},
    {"path": "media", "is_directory": True},
    {"path": "media/art1.png", "is_directory": False, "sha1_hash": "bbb"},
    {"path": "media/art2.jpg", "is_directory": False, "sha1_hash": "ccc"},
]


class TestPlanRestore(unittest.TestCase):
    def test_plans_only_missing_media(self):
        plan = upload.plan_restore(REMOTE_LISTING, {"media/art1.png"})
        self.assertEqual(plan, [("media/art2.jpg", "ccc")])

    def test_ignores_non_media_even_when_missing(self):
        plan = upload.plan_restore(REMOTE_LISTING, set())
        self.assertEqual([p for p, _ in plan], ["media/art1.png", "media/art2.jpg"])

    def test_ignores_directories(self):
        plan = upload.plan_restore(REMOTE_LISTING, set())
        self.assertNotIn("media", [p for p, _ in plan])

    def test_nothing_to_do_when_all_present(self):
        plan = upload.plan_restore(REMOTE_LISTING, {"media/art1.png", "media/art2.jpg"})
        self.assertEqual(plan, [])


class TestVerifyDownload(unittest.TestCase):
    def setUp(self):
        self.content = b"\x89PNG\r\n\x1a\n fake image bytes"
        self.sha1 = hashlib.sha1(self.content).hexdigest()

    def test_accepts_matching_image(self):
        self.assertTrue(upload.verify_download(self.content, "image/png", self.sha1))

    def test_accepts_content_type_with_charset(self):
        self.assertTrue(
            upload.verify_download(self.content, "image/png; charset=binary", self.sha1)
        )

    def test_rejects_html_error_page(self):
        self.assertFalse(
            upload.verify_download(b"<html>Not found</html>", "text/html", "")
        )

    def test_rejects_sha1_mismatch(self):
        self.assertFalse(upload.verify_download(self.content, "image/png", "deadbeef"))

    def test_rejects_empty_body(self):
        self.assertFalse(upload.verify_download(b"", "image/png", ""))

    def test_accepts_when_remote_reports_no_sha1(self):
        self.assertTrue(upload.verify_download(self.content, "image/jpeg", ""))
