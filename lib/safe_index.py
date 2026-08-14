"""Atomic and guarded writes for the project's JSON index files.

A scraper that gets rate-limited or blocked returns zero entries. Writing that
result over a good index silently empties a wiki page, so index writes go
through write_index_guarded, which refuses to shrink an index without --force.

Standard library only: scrape.py and upload.py must stay dependency-free.
"""

import json
import os
import shutil
import stat
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
        # Preserve target file's mode, or use 0o644 for new files
        if os.path.exists(path):
            target_mode = stat.S_IMODE(os.stat(path).st_mode)
        else:
            target_mode = 0o644
        os.chmod(tmp_path, target_mode)
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
