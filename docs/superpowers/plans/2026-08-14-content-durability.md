# Content Durability Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the wiki tooling incapable of destroying content that is deliberately kept out of git — fan art on Neocities, chapter text on AO3, and the scraped metadata indexes.

**Architecture:** Three independent changes sharing one principle: every content type that cannot be committed gets an authoritative external store and a tested recovery path. Risky logic is extracted into pure functions (`compute_changes`, `plan_restore`, `verify_download`, `classify_chapter`) that are unit-tested without network access; the network glue around them stays thin enough to verify by hand.

**Tech Stack:** Python 3, standard library only for the code under test (`urllib`, `hashlib`, `json`, `tempfile`). Tests use stdlib `unittest`. `requests`/`beautifulsoup4`/`lxml` are already required by the SpaceBattles scrapers and are only needed to import `scrape_media.py`.

**Spec:** `docs/superpowers/specs/2026-08-14-content-durability-design.md`

## Global Constraints

- Do not add a third-party test dependency. Tests run with `python3 -m unittest discover -s tests -v` from the repo root.
- `wiki/build/media/`, `chapters/`, and `sidestories/` stay gitignored. No task commits story text or images.
- Build/upload and `scrape.py` remain standard-library only. `lib/safe_index.py` must be stdlib only, because `scrape.py` and `upload.py` may import it.
- Diagnostics (refusals, warnings, errors) go to `stderr`. Progress and data go to `stdout`. This is the project's Unix-philosophy rule from `~/.claude/CLAUDE.md`.
- Every loop over a fetched collection has a provable ceiling; retry loops are bounded to 3 attempts.
- Scrapers keep their existing 3s (AO3) and 1s (SpaceBattles) politeness delays.
- Exit codes: `0` success, `2` refused-by-guard. `update_wiki.py` already reports any non-zero scraper exit as a warning.
- Protected prefix is exactly `("media/",)`. No flag in any script may delete a protected path.
- Neocities public base URL: `https://ghostinthecity.neocities.org` (no auth needed for downloads; the API key is only for `/api/list`).
- Run tests inside the project venv (`source .venv/bin/activate`) so `requests` is importable for the `scrape_media.py` tests.

## File Structure

**Created:**
- `lib/safe_index.py` — atomic and guarded JSON index writes. Stdlib only. Consumed by both scrapers.
- `tests/__init__.py` — empty, makes `tests` a package.
- `tests/helpers.py` — loads top-level scripts (`scrape.py`, `wiki/scripts/upload.py`) as importable modules.
- `tests/test_safe_index.py` — Task 1.
- `tests/test_index_guards.py` — Tasks 2 and 3.
- `tests/test_upload_protection.py` — Tasks 4 and 5.
- `tests/test_chapter_restore.py` — Task 8.

**Modified:**
- `scrape_sidestories.py` — `cmd_build_index` uses the guard; `--force`; `main` returns an exit code.
- `scrape_media.py` — `cmd_build_index` uses the guard; `--force`; four mutation writes become atomic.
- `wiki/scripts/upload.py` — `PROTECTED_PREFIXES`, `compute_changes`, `plan_restore`, `verify_download`, `restore_media`, `--restore-media`.
- `wiki/scripts/build.py` — `--restore-media` passthrough.
- `scrape.py` — `write_chapter` extraction, `classify_chapter`, `cmd_restore`, `--restore`.
- `CLAUDE.md` — hazards section replaced with guarantees and recovery commands.
- `sidestories_index.json` — restored from HEAD (Task 2).

---

### Task 1: Guarded index writes

**Files:**
- Create: `lib/safe_index.py`
- Create: `tests/__init__.py` (empty file)
- Create: `tests/test_safe_index.py`

**Interfaces:**
- Consumes: nothing.
- Produces:
  - `read_index_count(path) -> int`
  - `write_index_atomic(path, data) -> True` (raises on failure)
  - `write_index_guarded(path, entries, force=False, min_ratio=0.9) -> bool` — `True` written, `False` refused

- [ ] **Step 1: Write the failing tests**

Create `tests/__init__.py` as an empty file, then `tests/test_safe_index.py`:

```python
"""Tests for lib.safe_index — the guard that stops a failed scrape blanking an index."""

import json
import os
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
```

- [ ] **Step 2: Run the tests to verify they fail**

```bash
cd /home/gocyclic249/GhostInTheCityWiki
source .venv/bin/activate
python3 -m unittest tests.test_safe_index -v
```

Expected: `ModuleNotFoundError: No module named 'lib.safe_index'`

- [ ] **Step 3: Write the implementation**

Create `lib/safe_index.py`:

```python
"""Atomic and guarded writes for the project's JSON index files.

A scraper that gets rate-limited or blocked returns zero entries. Writing that
result over a good index silently empties a wiki page, so index writes go
through write_index_guarded, which refuses to shrink an index without --force.

Standard library only: scrape.py and upload.py must stay dependency-free.
"""

import json
import os
import shutil
import sys
import tempfile

MIN_RATIO_DEFAULT = 0.9


def _entry_count(data):
    """Entry count of a list- or dict-shaped index. Raises TypeError otherwise."""
    if isinstance(data, (list, dict)):
        return len(data)
    raise TypeError(f"index must be a list or dict, got {type(data).__name__}")


def read_index_count(path):
    """Return the entry count of an existing index file, or 0 if it is absent."""
    if not path:
        raise ValueError("path must be non-empty")
    if not os.path.exists(path):
        return 0
    with open(path, encoding="utf-8") as f:
        return _entry_count(json.load(f))


def write_index_atomic(path, data):
    """Write data as JSON to path via a temp file in the same directory.

    os.replace is atomic within a filesystem, so an interrupted write leaves the
    previous file intact rather than a truncated one.
    """
    if not path:
        raise ValueError("path must be non-empty")
    _entry_count(data)  # reject scalars before touching the filesystem

    directory = os.path.dirname(os.path.abspath(path))
    os.makedirs(directory, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(dir=directory, prefix=".idx-", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_path, path)
    except BaseException:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)
        raise
    return True


def write_index_guarded(path, entries, force=False, min_ratio=MIN_RATIO_DEFAULT):
    """Write entries to path unless that would shrink the index.

    Returns True if written, False if refused. Refusal never raises and never
    touches the target file, so the caller can exit non-zero and leave the good
    index in place.
    """
    if not 0 < min_ratio <= 1:
        raise ValueError(f"min_ratio must be in (0, 1], got {min_ratio}")
    new_count = _entry_count(entries)
    old_count = read_index_count(path)

    if not force and old_count > 0:
        if new_count == 0:
            print(f"  REFUSED: scrape returned 0 entries; existing index has {old_count}.",
                  file=sys.stderr)
            print(f"  {path} left untouched. Re-run when the source is reachable,"
                  " or pass --force.", file=sys.stderr)
            return False
        if new_count < old_count * min_ratio:
            dropped = old_count - new_count
            pct = 100.0 * dropped / old_count
            print(f"  REFUSED: index would shrink {old_count} -> {new_count}"
                  f" (-{dropped}, {pct:.1f}%).", file=sys.stderr)
            print(f"  {path} left untouched. Pass --force if the drop is real.",
                  file=sys.stderr)
            return False

    if old_count > 0:
        shutil.copy2(path, path + ".bak")
    write_index_atomic(path, entries)
    return True
```

- [ ] **Step 4: Run the tests to verify they pass**

```bash
python3 -m unittest tests.test_safe_index -v
```

Expected: PASS, 16 tests.

- [ ] **Step 5: Commit**

```bash
git add lib/safe_index.py tests/__init__.py tests/test_safe_index.py
git commit -m "Add guarded, atomic index writes"
```

---

### Task 2: Sidestories scraper cannot blank its index

**Files:**
- Modify: `scrape_sidestories.py` — `cmd_build_index` (line ~130), `main` (line ~170), imports
- Create: `tests/helpers.py`
- Create: `tests/test_index_guards.py`
- Modify: `sidestories_index.json` — restore from HEAD

**Interfaces:**
- Consumes: `lib.safe_index.write_index_guarded`
- Produces: `cmd_build_index(force=False) -> list | None` — the entries on success, `None` if the guard refused; `main() -> int` (0 written, 2 refused)

The `list | None` return matches `scrape_media.py`'s same-named function in Task 3, whose caller needs the entries back.

- [ ] **Step 1: Restore the blanked index**

The working tree copy is empty (0 entries); HEAD has 960. Restore it before touching the code, so the guard has a real index to protect:

```bash
git checkout HEAD -- sidestories_index.json
python3 -c "import json; print(len(json.load(open('sidestories_index.json'))), 'entries')"
```

Expected: `960 entries`

- [ ] **Step 2: Write the failing test**

Create `tests/helpers.py`:

```python
"""Load top-level scripts as importable modules.

scrape.py, scrape_sidestories.py, and wiki/scripts/upload.py are scripts, not
package modules, so tests import them by path — the same importlib approach
wiki/scripts/build.py already uses.
"""

import importlib.util
import os
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def load_script(rel_path, module_name):
    """Import a top-level script by file path and return the module."""
    if REPO_ROOT not in sys.path:
        sys.path.insert(0, REPO_ROOT)
    abs_path = os.path.join(REPO_ROOT, rel_path)
    if not os.path.exists(abs_path):
        raise FileNotFoundError(abs_path)
    spec = importlib.util.spec_from_file_location(module_name, abs_path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module
```

Create `tests/test_index_guards.py`:

```python
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
```

- [ ] **Step 3: Run the test to verify it fails**

```bash
python3 -m unittest tests.test_index_guards -v
```

Expected: FAIL — `test_empty_scrape_is_refused` errors with `TypeError: cmd_build_index() takes 0 positional arguments` or asserts `None is not False`, because the current `cmd_build_index` returns the entries list and always writes.

- [ ] **Step 4: Write the implementation**

In `scrape_sidestories.py`, add the import next to the existing ones:

```python
from lib.safe_index import write_index_guarded
```

Replace `cmd_build_index` (currently lines ~130-138) with:

```python
def cmd_build_index(force=False):
    """Build or refresh the sidestory index.

    Returns the entries on success, or None if the guard refused the write.
    """
    entries = fetch_all_threadmarks()
    if not write_index_guarded(INDEX_PATH, entries, force=force):
        return None
    print(f"  Saved index to {INDEX_PATH} ({len(entries)} entries)")
    return entries
```

Replace `main` (currently lines ~170-183) with:

```python
def main():
    args = sys.argv[1:]

    if "--help" in args or "-h" in args:
        print(__doc__)
        return 0

    if "--status" in args:
        cmd_status()
        return 0

    return 0 if cmd_build_index(force="--force" in args) is not None else 2


if __name__ == "__main__":
    sys.exit(main())
```

Add `--force` to the usage docstring at the top of the file:

```
  python3 scrape_sidestories.py --force     # write even if the index shrinks
```

- [ ] **Step 5: Run the test to verify it passes**

```bash
python3 -m unittest tests.test_index_guards -v
```

Expected: PASS, 4 tests.

- [ ] **Step 6: Verify the real index is intact and the script still runs**

```bash
python3 scrape_sidestories.py --status
```

Expected: `Sidestories in index: 960`

- [ ] **Step 7: Commit**

```bash
git add scrape_sidestories.py sidestories_index.json tests/helpers.py tests/test_index_guards.py
git commit -m "Guard the sidestory index against failed scrapes"
```

---

### Task 3: Media scraper cannot blank its index

**Files:**
- Modify: `scrape_media.py` — `cmd_build_index` (line ~661), `cmd_download` (line ~1068), four mutation writes (lines ~631, ~805, ~855, ~1020), `main` (line ~1086), imports
- Modify: `tests/test_index_guards.py` — add a media test class

**Interfaces:**
- Consumes: `lib.safe_index.write_index_guarded`, `lib.safe_index.write_index_atomic`
- Produces: `cmd_build_index(force=False) -> list | None` — the merged entries on success, `None` if the guard refused; `cmd_download(...) -> int` (exit code); `main() -> int`

This index carries `images`, `artist`, and `context` merged forward from previous scrapes, so a zero-entry write loses hand-recovered image metadata, not just the listing.

**Caller contract — do not skip.** `cmd_download` (line 1071) calls `cmd_build_index()` and uses the returned list as the index it downloads into:

```python
    index = cmd_build_index()
    print(f"Loaded index with {len(index)} media entries.")
```

`cmd_build_index` must therefore keep returning the entries, not a bool — returning `True` would make `len(index)` raise `TypeError`. On refusal it returns `None` and `cmd_download` aborts: a zero-entry scrape means SpaceBattles is unreachable, so the downloads that follow would fail anyway.

- [ ] **Step 1: Write the failing test**

Append to `tests/test_index_guards.py`:

```python
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
```

- [ ] **Step 2: Run the test to verify it fails**

```bash
python3 -m unittest tests.test_index_guards.TestMediaGuard -v
```

Expected: FAIL — `cmd_build_index` currently returns the entries list, so `assertFalse` fails, and the empty write destroys the index.

- [ ] **Step 3: Write the implementation**

In `scrape_media.py`, add to the imports:

```python
from lib.safe_index import write_index_atomic, write_index_guarded
```

In `cmd_build_index`, replace the final write (currently lines ~682-685):

```python
    with open(INDEX_PATH, "w", encoding="utf-8") as f:
        json.dump(entries, f, indent=2, ensure_ascii=False)
    print(f"  Saved index to {INDEX_PATH}")
    return entries
```

with:

```python
    if not write_index_guarded(INDEX_PATH, entries, force=force):
        return None
    print(f"  Saved index to {INDEX_PATH} ({len(entries)} entries)")
    return entries
```

and change its signature to `def cmd_build_index(force=False):`, with the docstring `"""Refresh the media index. Returns the merged entries, or None if refused."""`.

Then make `cmd_download` handle the refusal. Replace its first two lines (~1070-1072):

```python
    index = cmd_build_index()
    print(f"Loaded index with {len(index)} media entries.")
```

with:

```python
    index = cmd_build_index(force=force)
    if index is None:
        print("  Aborting download: the index refresh was refused.", file=sys.stderr)
        return 2
    print(f"Loaded index with {len(index)} media entries.")
```

Add `force=False` to the `cmd_download` signature, and `return 0` at the end of the function.

Replace each of the four mutation writes — the post-download index update (~line 631), `cmd_mark_manual` (~805), `cmd_unmark_manual` (~855), and `cmd_grab_sb` (~1020) — which all look like:

```python
    with open(INDEX_PATH, "w", encoding="utf-8") as f:
        json.dump(index, f, indent=2, ensure_ascii=False)
```

with:

```python
    write_index_atomic(INDEX_PATH, index)
```

Keep each surrounding `print` exactly as it is. These paths edit an already-loaded index and never shrink it, so they take the atomic write without the count guard.

In `main`, pass the flag through and return an exit code. Every early `return` in `main` becomes `return 0`. The `--index-only` branch becomes:

```python
    if "--index-only" in args:
        return 0 if cmd_build_index(force="--force" in args) is not None else 2
```

and the final `cmd_download` call becomes:

```python
    return cmd_download(start_num=start_num, end_num=end_num,
                        redownload=redownload, retry_empty=retry_empty,
                        force="--force" in args)
```

Change the entry point to:

```python
if __name__ == "__main__":
    sys.exit(main())
```

Add `--force` to the usage docstring at the top of the file.

- [ ] **Step 4: Run the tests to verify they pass**

```bash
python3 -m unittest tests.test_index_guards -v
```

Expected: PASS, 8 tests.

- [ ] **Step 5: Verify the real index is untouched**

```bash
python3 scrape_media.py --status
git diff --stat media_index.json
```

Expected: status prints the existing 89 entries; `git diff` shows no change.

- [ ] **Step 6: Commit**

```bash
git add scrape_media.py tests/test_index_guards.py
git commit -m "Guard the media index and make its writes atomic"
```

---

### Task 4: Uploads can never delete media

**Files:**
- Modify: `wiki/scripts/upload.py` — add `PROTECTED_PREFIXES`, `is_protected`, `compute_changes`; rewrite the diff block in `run_upload` (lines 184-208)
- Create: `tests/test_upload_protection.py`

**Interfaces:**
- Consumes: nothing.
- Produces:
  - `PROTECTED_PREFIXES = ("media/",)`
  - `is_protected(rel_path) -> bool`
  - `compute_changes(manifest, local_hashes) -> (to_upload, to_delete, missing_protected)` — three sorted lists of path strings

- [ ] **Step 1: Write the failing test**

Create `tests/test_upload_protection.py`:

```python
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
```

- [ ] **Step 2: Run the test to verify it fails**

```bash
python3 -m unittest tests.test_upload_protection -v
```

Expected: FAIL — `AttributeError: module has no attribute 'is_protected'`

- [ ] **Step 3: Write the implementation**

In `wiki/scripts/upload.py`, add below the `NEOCITIES_API` constant (line ~28):

```python
SITE_BASE = "https://ghostinthecity.neocities.org"

# Paths under these prefixes exist only on Neocities — wiki/build/media/ is
# gitignored, so a fresh clone has none of them locally. Deleting them because
# they are "missing" would wipe the fan art off the live site.
PROTECTED_PREFIXES = ("media/",)


def is_protected(rel_path):
    """True if rel_path must never be deleted from the live site."""
    if not isinstance(rel_path, str):
        raise TypeError(f"rel_path must be str, got {type(rel_path).__name__}")
    return rel_path.startswith(PROTECTED_PREFIXES)


def compute_changes(manifest, local_hashes):
    """Diff the manifest against local files.

    Returns (to_upload, to_delete, missing_protected). Protected paths that are
    missing locally are reported, never deleted.
    """
    if not isinstance(manifest, dict) or not isinstance(local_hashes, dict):
        raise TypeError("manifest and local_hashes must both be dicts")

    to_upload = sorted(rel for rel, sha in local_hashes.items()
                       if manifest.get(rel) != sha)
    missing = [rel for rel in manifest if rel not in local_hashes]
    to_delete = sorted(rel for rel in missing if not is_protected(rel))
    missing_protected = sorted(rel for rel in missing if is_protected(rel))
    return to_upload, to_delete, missing_protected
```

Then replace the diff block in `run_upload` (lines 184-196):

```python
    to_upload = []
    for rel, sha1 in local_hashes.items():
        if manifest.get(rel) != sha1:
            to_upload.append(rel)

    to_delete = [rel for rel in manifest if rel not in local_hashes]

    print(f"  Files to upload: {len(to_upload)}")
    print(f"  Files to delete: {len(to_delete)}")

    if not to_upload and not to_delete:
        print("  Nothing to do — site is up to date.")
        return
```

with:

```python
    to_upload, to_delete, missing_protected = compute_changes(manifest, local_hashes)

    print(f"  Files to upload: {len(to_upload)}")
    print(f"  Files to delete: {len(to_delete)}")
    if missing_protected:
        print(f"  Protected from deletion: {len(missing_protected)} media file(s)"
              " missing locally", file=sys.stderr)
        print("  Run: python3 wiki/scripts/upload.py --restore-media",
              file=sys.stderr)

    if not to_upload and not to_delete:
        print("  Nothing to do — site is up to date.")
        return
```

- [ ] **Step 4: Run the test to verify it passes**

```bash
python3 -m unittest tests.test_upload_protection -v
```

Expected: PASS, 9 tests.

- [ ] **Step 5: Verify against the live manifest**

This checkout has no local media, which is the exact dangerous state:

```bash
source .env
python3 wiki/scripts/build.py --upload --dry-run
```

Expected: `Files to delete: 0`, and a stderr line reporting 126 protected media files. Before this task it would have listed 126 deletions.

- [ ] **Step 6: Commit**

```bash
git add wiki/scripts/upload.py tests/test_upload_protection.py
git commit -m "Never delete media from the live site"
```

---

### Task 5: Restore planning and download verification

**Files:**
- Modify: `wiki/scripts/upload.py` — add `plan_restore`, `verify_download`
- Modify: `tests/test_upload_protection.py` — add test classes

**Interfaces:**
- Consumes: `is_protected` from Task 4.
- Produces:
  - `plan_restore(remote_files, local_paths) -> [(path, sha1), ...]` sorted by path. `remote_files` is the `files` list from `/api/list`; `local_paths` is any container supporting `in`.
  - `verify_download(content, content_type, expected_sha1) -> bool`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_upload_protection.py`:

```python
import hashlib


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
```

- [ ] **Step 2: Run the test to verify it fails**

```bash
python3 -m unittest tests.test_upload_protection -v
```

Expected: FAIL — `AttributeError: module has no attribute 'plan_restore'`

- [ ] **Step 3: Write the implementation**

Add to `wiki/scripts/upload.py`, below `compute_changes`:

```python
def plan_restore(remote_files, local_paths):
    """Which protected files exist remotely but not locally.

    remote_files: the "files" list from GET /api/list.
    Returns a sorted list of (path, sha1_hash) tuples.
    """
    if not isinstance(remote_files, list):
        raise TypeError(f"remote_files must be a list, got {type(remote_files).__name__}")

    wanted = []
    for entry in remote_files:
        path = entry.get("path", "")
        if entry.get("is_directory"):
            continue
        if not path or not is_protected(path):
            continue
        if path in local_paths:
            continue
        wanted.append((path, entry.get("sha1_hash", "")))
    return sorted(wanted)


def verify_download(content, content_type, expected_sha1):
    """True if content is a real image matching the remote hash.

    A Neocities miss returns an HTML error page. Writing that to media/foo.png
    would look like a successful restore and render as a broken image.
    """
    if content is None:
        raise TypeError("content must be bytes")
    if not content:
        return False
    mime = content_type.split(";")[0].strip().lower()
    if not mime.startswith("image/"):
        return False
    if expected_sha1 and hashlib.sha1(content).hexdigest() != expected_sha1:
        return False
    return True
```

`hashlib` is already imported at the top of the file.

- [ ] **Step 4: Run the test to verify it passes**

```bash
python3 -m unittest tests.test_upload_protection -v
```

Expected: PASS, 19 tests.

- [ ] **Step 5: Commit**

```bash
git add wiki/scripts/upload.py tests/test_upload_protection.py
git commit -m "Add restore planning and download verification"
```

---

### Task 6: Media restore, wired into the uploader

**Files:**
- Modify: `wiki/scripts/upload.py` — add `neocities_list`, `download_file`, `restore_media`; call from `run_upload`; extend the `__main__` block
- Modify: `wiki/scripts/build.py` — add `--restore-media`

**Interfaces:**
- Consumes: `plan_restore`, `verify_download`, `is_protected`, the existing `api_request`, `sha1_file`, `load_manifest`, `save_manifest`, `scan_build_dir`.
- Produces:
  - `neocities_list(api_key) -> list` (the `files` array, `[]` on error)
  - `download_file(url, attempts=3) -> (content_bytes, content_type)` — `(None, "")` on failure
  - `restore_media(api_key, dry_run=False) -> int` (count restored)

- [ ] **Step 1: Implement restore**

There is no unit test step here: this task is network glue over the functions tested in Task 5, and it is verified live in Step 3. Add to `wiki/scripts/upload.py`:

```python
def neocities_list(api_key):
    """Every file on the live site, with sha1 hashes. Returns [] on error."""
    result = api_request("list", api_key=api_key)
    if result.get("result") != "success":
        print(f"  ERROR: could not list remote files: {result.get('message', '?')}",
              file=sys.stderr)
        return []
    return result.get("files", [])


def download_file(url, attempts=3):
    """Fetch a public URL. Returns (content, content_type) or (None, "")."""
    if attempts < 1:
        raise ValueError("attempts must be >= 1")
    for attempt in range(attempts):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "gitc-wiki-restore/1.0"})
            with urllib.request.urlopen(req, timeout=60) as resp:
                return resp.read(), resp.headers.get("Content-Type", "")
        except Exception as ex:
            if attempt == attempts - 1:
                print(f"  ERROR: {url} -> {ex}", file=sys.stderr)
            else:
                time.sleep(2 * (attempt + 1))
    return None, ""


def restore_media(api_key, dry_run=False):
    """Download protected files that exist on Neocities but not locally.

    Neocities is the store of record for media: wiki/build/media/ is gitignored
    because the artists asked to stay out of the repo, so a fresh clone restores
    from the live site. Returns the number of files restored.
    """
    local_paths = set(scan_build_dir())
    remote_files = neocities_list(api_key)
    wanted = plan_restore(remote_files, local_paths)

    if not wanted:
        return 0

    print(f"  Missing locally: {len(wanted)} media file(s)")
    if dry_run:
        for path, _ in wanted:
            print(f"    would restore {path}")
        return 0

    manifest = load_manifest()
    restored = 0
    failed = []
    for path, expected_sha1 in wanted:
        url = f"{SITE_BASE}/{urllib.parse.quote(path)}"
        content, content_type = download_file(url)
        if content is None or not verify_download(content, content_type, expected_sha1):
            failed.append(path)
            continue
        dest = os.path.join(BUILD_DIR, path)
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        with open(dest, "wb") as f:
            f.write(content)
        manifest[path] = hashlib.sha1(content).hexdigest()
        restored += 1
        if restored % 10 == 0:
            print(f"    restored {restored}/{len(wanted)}")

    save_manifest(manifest)
    print(f"  Restored {restored}/{len(wanted)} media file(s)")
    if failed:
        print(f"  WARNING: {len(failed)} could not be restored and stay protected"
              f" from deletion: {failed[:5]}{'...' if len(failed) > 5 else ''}",
              file=sys.stderr)
    return restored
```

Add `import time` to the imports. `hashlib`, `json`, `os`, `sys`, `urllib.error`, `urllib.parse`, and `urllib.request` are already imported at lines 11-17; `time` is the only one missing.

- [ ] **Step 2: Call it from `run_upload` and add the CLI**

At the top of `run_upload`, immediately after `api_key = get_api_key()`, insert:

```python
    restore_media(api_key, dry_run=dry_run)
```

Then re-scan, so restored files count as local. The existing lines:

```python
    manifest = load_manifest()
    local    = scan_build_dir()
```

must come *after* the `restore_media` call, since restore updates the manifest on disk. Final order in `run_upload`:

```python
def run_upload(dry_run=False):
    api_key = get_api_key()
    restore_media(api_key, dry_run=dry_run)
    manifest = load_manifest()
    local    = scan_build_dir()
    ...
```

Extend the `__main__` block at the bottom of the file:

```python
if __name__ == "__main__":
    if "--restore-media" in sys.argv:
        restore_media(get_api_key(), dry_run="--dry-run" in sys.argv)
    elif "--dry-run" in sys.argv:
        run_upload(dry_run=True)
    elif "--status" in sys.argv:
        run_status()
    else:
        run_upload()
```

In `wiki/scripts/build.py`, add a command function next to `cmd_upload`:

```python
def cmd_restore_media(dry_run=False):
    print("Restoring media from Neocities...")
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "upload",
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "upload.py")
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    mod.restore_media(mod.get_api_key(), dry_run=dry_run)
```

and dispatch it in `main`, before the `--build` branch:

```python
    if "--restore-media" in args:
        cmd_restore_media(dry_run=dry_run)
```

Add both new flags to the module docstring usage block in `build.py`.

- [ ] **Step 3: Verify live**

```bash
source .env
python3 -m unittest discover -s tests -v          # regressions
python3 wiki/scripts/upload.py --restore-media --dry-run
```

Expected: lists 126 media files it would restore, downloads nothing.

```bash
python3 wiki/scripts/upload.py --restore-media
ls wiki/build/media | wc -l
```

Expected: `Restored 126/126`, and 126 files on disk.

```bash
python3 wiki/scripts/build.py --upload --dry-run
```

Expected: `Files to upload: 0`, `Files to delete: 0`, no protected-missing warning. This proves restored hashes landed in the manifest and nothing re-uploads.

- [ ] **Step 4: Confirm nothing is staged for git**

```bash
git status --short wiki/build/media | head
```

Expected: no output — `wiki/build/media/` is gitignored and must stay that way.

- [ ] **Step 5: Commit**

```bash
git add wiki/scripts/upload.py wiki/scripts/build.py
git commit -m "Restore missing media from Neocities before uploading"
```

---

### Task 7: Extract the chapter writer

**Files:**
- Modify: `scrape.py` — add `write_chapter`; rewrite the duplicated blocks in `cmd_update` (lines ~329-378) and `main` (lines ~438-492)

**Interfaces:**
- Consumes: existing `fetch`, `extract_chapter_content`, `extract_author_notes`, `html_to_markdown`, `sanitize_filename`.
- Produces: `write_chapter(chapter_num, chapter, filepath) -> bool` (True on success), `chapter_filename(chapter_num, chapter) -> str`

This is a pure refactor with no behaviour change. `cmd_restore` in Task 8 would otherwise be a third copy of the same block.

- [ ] **Step 1: Add the helpers**

Add to `scrape.py`, above `cmd_update`:

```python
def chapter_filename(chapter_num, chapter):
    """The on-disk filename for a chapter: 0042_42._Chapter_42.md"""
    if chapter_num < 1:
        raise ValueError(f"chapter_num must be >= 1, got {chapter_num}")
    title = chapter.get("title", "")
    if not title:
        raise ValueError(f"chapter {chapter_num} has no title")
    return f"{chapter_num:04d}_{sanitize_filename(title)}.md"


def write_chapter(chapter_num, chapter, filepath):
    """Fetch one chapter from AO3 and write it as markdown. True on success."""
    if not filepath:
        raise ValueError("filepath must be non-empty")
    title = chapter["title"]
    ao3_url = chapter["ao3_url"]

    html_content = fetch(ao3_url)
    if not html_content:
        print("  FAILED — could not fetch", file=sys.stderr)
        return False

    chapter_html = extract_chapter_content(html_content)
    if not chapter_html:
        print("  WARNING: could not extract chapter content", file=sys.stderr)
        return False

    notes_before = extract_author_notes(html_content, "before")
    notes_after = extract_author_notes(html_content, "after")
    chapter_md = html_to_markdown(chapter_html)

    lines = [f"# {title}\n"]
    lines.append(f"*Source: {ao3_url}*")
    if chapter.get("date"):
        lines.append(f"*Published: {chapter['date']}*")
    if chapter.get("sb_url"):
        lines.append(f"*SpaceBattles: {chapter['sb_url']}*")
    lines.append("\n---\n")
    if notes_before:
        lines.append("**Author's Note:**\n")
        lines.append(f"> {html_to_markdown(notes_before)}\n")
        lines.append("---\n")
    lines.append(chapter_md)
    if notes_after:
        lines.append("\n\n---\n")
        lines.append("**Author's End Note:**\n")
        lines.append(f"> {html_to_markdown(notes_after)}")

    with open(filepath, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    print(f"  Saved: {os.path.basename(filepath)} (~{len(chapter_md.split())} words)")
    return True
```

Note: the previous `cmd_update` block omitted the `sb_url` line that `main` emitted. `write_chapter` includes it for both, which is the correct behaviour — `sb_url` is null for every current index entry, so no existing file changes.

- [ ] **Step 2: Rewrite the `cmd_update` download loop**

Replace the body of the `for ch in new_chapters:` loop (lines ~329-378) with:

```python
    for ch in new_chapters:
        i = next(j + 1 for j, c in enumerate(updated) if c["chapter_id"] == ch["chapter_id"])
        filepath = os.path.join(OUTPUT_DIR, chapter_filename(i, ch))
        print(f"\nDownloading Ch.{i}: {ch['title']}")
        write_chapter(i, ch, filepath)
        time.sleep(DELAY)
```

- [ ] **Step 3: Rewrite the `main` download loop**

Replace the body of the `for i, chapter in enumerate(...)` loop (lines ~422-492) with:

```python
    for i, chapter in enumerate(index[start_num - 1:], start=start_num):
        if end_num and i > end_num:
            break

        filepath = os.path.join(OUTPUT_DIR, chapter_filename(i, chapter))
        if os.path.exists(filepath) and not redownload:
            size = os.path.getsize(filepath)
            if size > 500:
                print(f"[{i}/{total}] Skip (exists, {size} bytes): {chapter['title']}")
                success += 1
                continue

        print(f"[{i}/{total}] {chapter['title']}")
        print(f"  URL: {chapter['ao3_url']}")
        if write_chapter(i, chapter, filepath):
            success += 1
        else:
            failed.append(i)
        time.sleep(DELAY)
```

- [ ] **Step 4: Verify no behaviour change**

`chapters/0246_246._Chapter_246.md` is the one chapter present locally. Confirm the refactored skip path still recognises it, and that a re-download reproduces it byte for byte:

```bash
sha1sum chapters/0246_246._Chapter_246.md
python3 scrape.py --from 246 --to 246
sha1sum chapters/0246_246._Chapter_246.md
```

Expected: the first run prints `Skip (exists, ...)`, and the hash is unchanged.

```bash
cp chapters/0246_246._Chapter_246.md /tmp/ch246.before
python3 scrape.py --from 246 --to 246 --redownload
diff /tmp/ch246.before chapters/0246_246._Chapter_246.md && echo "IDENTICAL"
```

Expected: `IDENTICAL`. If it differs, the refactor changed output — stop and fix before continuing.

- [ ] **Step 5: Commit**

```bash
git add scrape.py
git commit -m "Extract write_chapter from the duplicated download loops"
```

---

### Task 8: Chapter restore from AO3

**Files:**
- Modify: `scrape.py` — add `classify_chapter`, `cmd_restore`; dispatch `--restore` in `main`; update the docstring
- Create: `tests/test_chapter_restore.py`

**Interfaces:**
- Consumes: `chapter_filename`, `write_chapter` from Task 7.
- Produces:
  - `classify_chapter(filepath) -> "present" | "missing" | "suspect"`
  - `cmd_restore(start_num=1, end_num=None) -> int` (count of failures)

- [ ] **Step 1: Write the failing test**

Create `tests/test_chapter_restore.py`:

```python
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
```

- [ ] **Step 2: Run the test to verify it fails**

```bash
python3 -m unittest tests.test_chapter_restore -v
```

Expected: FAIL — `AttributeError: module has no attribute 'classify_chapter'`. The `TestChapterFilename` cases should already pass from Task 7.

- [ ] **Step 3: Write the implementation**

Add to `scrape.py`, above `cmd_update`:

```python
MIN_CHAPTER_BYTES = 500


def classify_chapter(filepath):
    """Classify a chapter file as present, missing, or suspect.

    Suspect means the file exists but looks like a truncated or failed
    download — too small, or missing the markdown title line write_chapter
    always emits.
    """
    if not filepath:
        raise ValueError("filepath must be non-empty")
    if not os.path.exists(filepath):
        return "missing"
    if os.path.getsize(filepath) <= MIN_CHAPTER_BYTES:
        return "suspect"
    with open(filepath, encoding="utf-8") as f:
        first_line = f.readline()
    if not first_line.startswith("# "):
        return "suspect"
    return "present"


def cmd_restore(start_num=1, end_num=None):
    """Re-download every missing or damaged chapter. Returns the failure count.

    chapters/ is gitignored, so a new machine starts empty. AO3 is the store of
    record — this rebuilds the directory without ever storing story text in git.
    """
    if start_num < 1:
        raise ValueError(f"start_num must be >= 1, got {start_num}")
    index = get_chapter_index()
    if not index:
        print("ERROR: no chapter index. Run scrape.py --update first.", file=sys.stderr)
        return 1

    os.makedirs(OUTPUT_DIR, exist_ok=True)

    todo = []
    present = 0
    for i, chapter in enumerate(index, start=1):
        if i < start_num or (end_num and i > end_num):
            continue
        filepath = os.path.join(OUTPUT_DIR, chapter_filename(i, chapter))
        state = classify_chapter(filepath)
        if state == "present":
            present += 1
        else:
            todo.append((i, chapter, filepath, state))

    scope = f"{start_num}-{end_num}" if end_num else f"{start_num}-{len(index)}"
    print(f"Index: {len(index)} chapters. Range {scope}: "
          f"{present} present, {len(todo)} to restore.")
    if not todo:
        print("Nothing to restore.")
        return 0

    failed = []
    for n, (i, chapter, filepath, state) in enumerate(todo, start=1):
        label = "re-fetching damaged" if state == "suspect" else "fetching missing"
        print(f"[{n}/{len(todo)}] Ch.{i} ({label}): {chapter['title']}")
        if not write_chapter(i, chapter, filepath):
            failed.append(i)
        time.sleep(DELAY)

    print(f"\nRestored {len(todo) - len(failed)}/{len(todo)} chapters.")
    if failed:
        print(f"Failed: {failed}", file=sys.stderr)
        print(f"Retry with: python3 scrape.py --restore --from {min(failed)}",
              file=sys.stderr)
    return len(failed)
```

In `main`, dispatch `--restore` next to the existing `--update` branch, reusing the `--from` / `--to` parsing that already exists below it. Move the `--from` / `--to` parsing above both branches so `--restore` can use it:

```python
def main():
    start_num = 1
    if "--from" in sys.argv:
        idx = sys.argv.index("--from")
        if idx + 1 < len(sys.argv):
            start_num = int(sys.argv[idx + 1])
    end_num = None
    if "--to" in sys.argv:
        idx = sys.argv.index("--to")
        if idx + 1 < len(sys.argv):
            end_num = int(sys.argv[idx + 1])

    if "--update" in sys.argv:
        cmd_update()
        return 0

    if "--restore" in sys.argv:
        return 0 if cmd_restore(start_num, end_num) == 0 else 1

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    redownload = "--redownload" in sys.argv
    ...
```

Delete the now-duplicated `--from` / `--to` parsing further down in `main`, keep the rest of the function as Task 7 left it, add `return 0` at the end, and change the entry point to `sys.exit(main())`.

Update the module docstring at the top of `scrape.py` with the new usage:

```
  python3 scrape.py --restore              # re-download missing/damaged chapters
  python3 scrape.py --restore --from 100   # bound the range
```

- [ ] **Step 4: Run the tests to verify they pass**

```bash
python3 -m unittest tests.test_chapter_restore -v
```

Expected: PASS, 8 tests.

- [ ] **Step 5: Verify live on a two-chapter range**

```bash
python3 scrape.py --restore --from 245 --to 246
```

Expected: reports `1 present, 1 to restore`, fetches only chapter 245, leaves 246 alone.

```bash
ls chapters/
python3 scrape.py --restore --from 245 --to 246
```

Expected: both files present; the second run reports `2 present, 0 to restore` / `Nothing to restore.`

- [ ] **Step 6: Commit**

```bash
git add scrape.py tests/test_chapter_restore.py
git commit -m "Add scrape.py --restore for rebuilding chapters from AO3"
```

---

### Task 9: Documentation and full verification

**Files:**
- Modify: `CLAUDE.md` — replace the "Deployment Hazards" section
- Modify: `docs/superpowers/plans/2026-08-14-content-durability.md` — no change; this task closes it out

**Interfaces:**
- Consumes: every command added in Tasks 1-8.
- Produces: nothing code depends on.

- [ ] **Step 1: Replace the hazards section in `CLAUDE.md`**

Replace the whole `## Deployment Hazards` section with:

```markdown
## Content Durability

Story text and fan art are deliberately kept out of git — chapter text is not
redistributed, and the artists asked to stay out of a public GitHub repo. Each
type therefore has an external store of record and a restore command:

| Content | Store of record | Restore |
|---|---|---|
| `wiki/build/media/` | Neocities | `python3 wiki/scripts/upload.py --restore-media` |
| `chapters/*.md` | AO3 | `python3 scrape.py --restore` |

Guarantees the tooling now enforces:

- **`upload.py` never deletes `media/`.** Paths under `PROTECTED_PREFIXES` are
  excluded from the delete set even when missing locally, and `run_upload`
  restores them from Neocities first. Downloads are verified by SHA1 against
  `/api/list` and rejected unless the `Content-Type` is an image, so a 404 page
  can't land as a broken file.
- **Scrapers never blank an index.** `scrape_sidestories.py` and
  `scrape_media.py` write through `lib/safe_index.py`, which refuses a
  zero-entry result or a shrink beyond 10% and exits 2. Pass `--force` when a
  drop is real. Writes are atomic with a `.bak` copy.
- **`scrape.py --restore`** re-downloads missing chapters and re-fetches damaged
  ones (under 500 bytes or missing the `# ` title line), bounded by
  `--from` / `--to`.

Run `python3 -m unittest discover -s tests -v` after touching any of this.
After deploying, verify the deployed files match the local build — stale
deployed files have caused bugs before.
```

Also add the restore commands to the "Common Commands" block, under the existing scraper and build entries.

- [ ] **Step 2: Run the whole suite**

```bash
source .venv/bin/activate
python3 -m unittest discover -s tests -v
```

Expected: PASS, 36 tests, 0 failures.

- [ ] **Step 3: Run the spec's verification checklist end to end**

```bash
source .env
python3 wiki/scripts/build.py --upload --dry-run     # 0 deletions
python3 wiki/scripts/build.py --build                # renders 960 side stories
grep -c "ss-words" wiki/build/sidestories.html       # sanity check: ~960
python3 wiki/scripts/build.py --upload --dry-run     # only changed pages
```

Expected: no deletions at any point; `sidestories.html` is no longer the empty placeholder.

- [ ] **Step 4: Confirm no ignored content got staged**

```bash
git status --short
git check-ignore -v wiki/build/media/$(ls wiki/build/media | head -1) chapters/$(ls chapters | head -1)
```

Expected: no `media/` or `chapters/` paths in `git status`; `check-ignore` confirms both are still ignored.

- [ ] **Step 5: Commit**

```bash
git add CLAUDE.md
git commit -m "Document the content durability guarantees"
```

---

## Self-Review

**Spec coverage:**

| Spec section | Task |
|---|---|
| A: never-delete rule | 4 |
| A: auto-restore (list, download, verify, manifest) | 5, 6 |
| A: `--restore-media` CLI on both scripts | 6 |
| A: `--dry-run` downloads nothing | 6 |
| B: `write_index_atomic` / `write_index_guarded` | 1 |
| B: sidestories caller + exit 2 | 2 |
| B: media caller + mutation writes | 3 |
| B: restore `sidestories_index.json` from HEAD | 2 |
| C: `classify_chapter`, `cmd_restore`, `--from`/`--to` | 8 |
| C: `write_chapter` extraction | 7 |
| Docs: CLAUDE.md | 9 |
| Docs: README deferred | out of scope, stated in spec |
| Verification 1-6 | 4 (guard), 6 (restore, re-upload), 1 (index guard), 8 (chapters), 9 (build) |

No gaps.

**Placeholder scan:** no TBD/TODO, no "add error handling", no "similar to Task N". Every code step carries the actual code.

**Type consistency:** `is_protected(rel_path) -> bool`, `compute_changes -> (list, list, list)`, `plan_restore -> [(str, str)]`, `verify_download(bytes, str, str) -> bool`, `write_index_guarded -> bool`, `write_index_atomic -> True`, `read_index_count -> int`, `classify_chapter -> str`, `write_chapter -> bool`, `chapter_filename -> str`. Names used in Tasks 6, 8, and 9 match their definitions in Tasks 1, 4, 5, and 7. `PROTECTED_PREFIXES` is a tuple in both its definition and its `str.startswith` uses.

One defect found and fixed during this review: Tasks 2 and 3 originally had `cmd_build_index` return a bool, but `scrape_media.py:1071` consumes its return value as the index list (`len(index)`), so a bool would have raised `TypeError` on every `scrape_media.py` download run — the default no-argument invocation `update_wiki.py` uses. Both now return `list | None`, `cmd_download` aborts on `None`, and `test_returns_a_list_for_cmd_download` locks the contract in.

**Verified against the source while reviewing:** `fetch_threadmark_index` (`scrape_media.py:148`) and `fetch_all_threadmarks` (`scrape_sidestories.py:107`) exist under the names the tests monkeypatch; `scrape.py` already imports `sys`, `os`, and `time`; `upload.py` is missing only `time`; `get_chapter_index()` (`scrape.py:295`) reads the local index file, which is what `cmd_restore` needs.
