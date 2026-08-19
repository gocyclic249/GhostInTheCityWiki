"""Tests for wiki/scripts/pack_media.py — the encrypted media archive.

The archive is the fallback when a bad file has already been pushed over the
Neocities original, so a silent round-trip failure would be invisible until it
mattered. These tests exercise pack -> verify -> extract on scratch dirs.
"""

import importlib.util
import json
import os
import pathlib
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

PACK_PATH = (pathlib.Path(__file__).resolve().parent.parent
             / "wiki" / "scripts" / "pack_media.py")

try:
    import pyzipper  # noqa: F401
    HAVE_PYZIPPER = True
except ImportError:
    HAVE_PYZIPPER = False


def load_pack_media():
    """pack_media.py is a script, not a package member; load it by path."""
    spec = importlib.util.spec_from_file_location("gitc_pack_media", PACK_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


PASSPHRASE = "test-passphrase-not-a-real-secret"

# Minimal valid image headers, so fixtures look like the real payloads.
PNG_HEADER = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64
JPEG_HEADER = b"\xff\xd8\xff\xe0" + b"\x00" * 64


@unittest.skipUnless(HAVE_PYZIPPER, "pyzipper not installed")
class TestPackMedia(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        base = pathlib.Path(self.tmp.name)
        self.media = base / "media"
        self.archive = base / "media-archive"
        self.media.mkdir()

        self.mod = load_pack_media()
        self.mod.MEDIA = self.media
        self.mod.ARCHIVE_DIR = self.archive
        self.mod.MANIFEST = self.archive / "manifest.json"

        self.payloads = {
            "0001_1.png": PNG_HEADER + b"alpha" * 500,
            "0002_1.jpg": JPEG_HEADER + b"bravo" * 500,
            "0003_1.png": PNG_HEADER + b"charlie" * 500,
        }
        for name, data in self.payloads.items():
            (self.media / name).write_bytes(data)

        os.environ["MEDIA_ARCHIVE_PASSPHRASE"] = PASSPHRASE

    def tearDown(self):
        os.environ.pop("MEDIA_ARCHIVE_PASSPHRASE", None)
        self.tmp.cleanup()

    def test_pack_then_verify_roundtrips(self):
        self.mod.do_pack(self.mod.DEFAULT_MAX_PART)
        self.assertTrue(self.mod.MANIFEST.is_file())
        self.mod.do_verify()  # raises SystemExit on mismatch

    def test_extract_restores_exact_bytes(self):
        self.mod.do_pack(self.mod.DEFAULT_MAX_PART)
        for name in self.payloads:
            (self.media / name).unlink()
        self.mod.do_extract()
        for name, data in self.payloads.items():
            self.assertEqual((self.media / name).read_bytes(), data, name)

    def test_wrong_passphrase_cannot_read(self):
        self.mod.do_pack(self.mod.DEFAULT_MAX_PART)
        os.environ["MEDIA_ARCHIVE_PASSPHRASE"] = "wrong-passphrase-entirely"
        # pyzipper reports a bad AES password as RuntimeError("Bad password").
        with self.assertRaisesRegex(RuntimeError, "[Bb]ad password"):
            self.mod.do_verify()

    def test_volumes_split_on_size_cap(self):
        # A cap below the per-file size forces one volume per file.
        self.mod.do_pack(1024)
        manifest = json.loads(self.mod.MANIFEST.read_text())
        self.assertEqual(len(manifest["volumes"]), len(self.payloads))

    def test_manifest_records_every_file(self):
        self.mod.do_pack(self.mod.DEFAULT_MAX_PART)
        manifest = json.loads(self.mod.MANIFEST.read_text())
        self.assertEqual(set(manifest["contents"]), set(self.payloads))
        self.assertEqual(manifest["source_files"], len(self.payloads))

    def test_tampered_manifest_is_caught(self):
        self.mod.do_pack(self.mod.DEFAULT_MAX_PART)
        manifest = json.loads(self.mod.MANIFEST.read_text())
        name = next(iter(manifest["contents"]))
        manifest["contents"][name]["sha256"] = "0" * 64
        self.mod.MANIFEST.write_text(json.dumps(manifest))
        with self.assertRaises(SystemExit):
            self.mod.do_verify()

    def test_empty_media_dir_refuses(self):
        for name in self.payloads:
            (self.media / name).unlink()
        with self.assertRaises(SystemExit):
            self.mod.do_pack(self.mod.DEFAULT_MAX_PART)

    def test_short_passphrase_refused(self):
        os.environ["MEDIA_ARCHIVE_PASSPHRASE"] = ""
        # An empty env var falls through to the tty path, which is absent here.
        with self.assertRaises(SystemExit):
            self.mod.do_pack(self.mod.DEFAULT_MAX_PART)


if __name__ == "__main__":
    unittest.main()
