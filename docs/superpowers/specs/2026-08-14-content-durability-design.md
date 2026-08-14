# Content Durability Design

**Date:** 2026-08-14
**Status:** Approved (design), pending implementation

## Problem

Story text and fan art are deliberately kept out of git: chapter text is Seras's
work and is not redistributed, and the artists whose work appears in `media/`
have asked not to have their images sit in a public GitHub repo. `.gitignore`
therefore excludes `chapters/`, `sidestories/`, and `wiki/build/media/`.

That choice creates three failure modes, all currently live in this checkout:

1. **The deploy deletes fan art.** `upload.py` treats the local `wiki/build/`
   tree as the source of truth and deletes any remote file listed in
   `wiki/cache/upload_manifest.json` but missing locally. `wiki/build/media/` is
   gitignored, so a fresh clone has none of the 126 `media/*` files the manifest
   lists. The first upload from that clone deletes every image from the live
   site. This checkout is in exactly that state right now.

2. **A failed scrape blanks an index.** `scrape_sidestories.py` and
   `scrape_media.py` both overwrite their index file unconditionally with
   whatever the scrape returned, including zero entries when SpaceBattles
   rate-limits or blocks the request. `sidestories_index.json` has already been
   blanked this way: 960 entries at HEAD, 0 in the working tree. A build on top
   of that renders an empty side stories page. For `media_index.json` the damage
   is worse, because `cmd_build_index` merges the preserved `images`, `artist`,
   and `context` fields into the fresh scrape, so a zero-entry result discards
   all image metadata, not just the listing.

3. **Switching computers loses chapter text.** `chapters/` is gitignored, so a
   new machine starts empty. `/process-chapter` and `/fact-check` both need the
   raw chapter file, and nothing documents how to get it back.

## Principle

Neither GitHub nor the local disk is the store of record for content that can't
be committed. Each content type gets an authoritative external source, and the
tooling knows how to pull from it:

| Content | Store of record | Recovery |
|---|---|---|
| `wiki/build/media/` | Neocities (already public there) | download over HTTPS |
| `chapters/*.md` | AO3 | re-scrape |
| `sidestories_index.json` | git (metadata only, no story text) | guard against blanking |
| `media_index.json` | git (metadata only) | guard against blanking |

Media cannot use the AO3-style re-scrape path: the sources include dead imgur
URLs, expired Discord CDN links, Cloudflare-blocked SpaceBattles attachments,
and hand-placed manual replacements. Neocities holds the only complete copy.
Chapters are the reverse — AO3 always has them, and republishing them on
Neocities would be the redistribution the project avoids.

## A. `wiki/scripts/upload.py` — media protected and self-healing

### Never-delete rule

```python
PROTECTED_PREFIXES = ("media/",)

def is_protected(rel):
    return rel.startswith(PROTECTED_PREFIXES)
```

The delete set in `run_upload` becomes:

```python
to_delete = [rel for rel in manifest
             if rel not in local_hashes and not is_protected(rel)]
```

Protected paths that are still missing after restore are reported as skipped and
left in the manifest. Deletion of protected content is not reachable from this
script by any flag; removing an image from the live site is a deliberate manual
act against the Neocities API.

### Auto-restore

`run_upload` calls `restore_media(api_key)` before computing the diff:

1. `GET /api/list` once, via the existing `api_request` helper. This returns
   every remote file with a `sha1_hash`, and is authoritative in a way the local
   manifest is not — it also sees media uploaded from another machine.
2. For each listed `media/*` path with no local file: download
   `https://ghostinthecity.neocities.org/<path>`. This URL is public and needs
   no API key (verified: HTTP 200 on `media/100160767_1.png`). Three attempts
   with backoff; a failure is logged and the path stays protected.
3. Verify each download against the listed `sha1_hash`, and reject any response
   whose `Content-Type` is not an image type — a Neocities miss returns an HTML
   error page, and writing that to `media/foo.png` would produce a file that
   looks restored but renders as a broken image. A rejected download is
   discarded rather than written.
4. Write verified files to `wiki/build/media/` and record their hashes in the
   manifest, so restored files are not immediately re-uploaded.

Steady-state cost is one extra API call. A full restore is ~126 files, roughly
60 MB.

### CLI

- `python3 wiki/scripts/upload.py --restore-media` — steps 1–4 standalone.
- `python3 wiki/scripts/build.py --restore-media` — same, via the orchestrator.

`--dry-run` reports what restore would fetch and what it would skip, and
downloads nothing.

## B. `lib/safe_index.py` — indexes that cannot be blanked

A new shared module, because `scrape_sidestories.py` and `scrape_media.py` need
identical behaviour and neither should own it.

```python
def write_index_atomic(path, data):
    """Write JSON to a temp file in the same directory, then os.replace()."""

def write_index_guarded(path, entries, force=False, min_ratio=0.9):
    """Refuse to shrink an index. Returns True on write, False on refusal."""
```

`write_index_guarded` rules, checked against the existing file's entry count:

- New count is 0 and the existing index is non-empty → refuse.
- New count is below `existing * min_ratio` → refuse, printing both counts and
  the delta. Threshold is 10%; these indexes essentially only grow, and a real
  drop that large deserves a human look.
- `force=True` skips both checks.
- On an accepted write: copy the current file to `<path>.bak`, then write
  atomically. `scrape_media.py` already keeps a `media_index.json.bak`, so this
  matches existing convention.

Refusal returns `False` and never raises, leaving the target file untouched.
Callers exit 2 on refusal. `update_wiki.py` already prints a warning for any
non-zero exit from a scraper, so a blocked scrape surfaces in the run report
instead of silently emptying a page.

Callers:

- `scrape_sidestories.py: cmd_build_index` — guarded write, `--force` flag.
- `scrape_media.py: cmd_build_index` — guarded write, `--force` flag. This is
  the merge path that carries `images`/`artist`/`context` forward.
- `scrape_media.py` mutation writes (post-download index update, `--mark-manual`,
  `--unmark-manual`, `--grab-sb`) — `write_index_atomic` only. These edit an
  already-loaded index and don't shrink it, but they should not leave a
  half-written file if interrupted.

`sidestories_index.json` is restored from HEAD (0 → 960 entries) as part of this
work.

## C. `scrape.py --restore` — chapters back from AO3

New `cmd_restore()`, alongside the existing `cmd_update()`:

1. Read `threadmarks_index.json`, derive the expected filename for every chapter
   (`{NNNN}_{sanitized title}.md`, index position + 1 = chapter number).
2. Classify each: **present**, **missing**, or **suspect**. Suspect means under
   500 bytes or missing the leading `# ` title line, which catches truncated or
   half-written downloads that the existing `main()` size check would silently
   accept.
3. Download missing and suspect chapters at the existing 3s delay.
4. Report restored, failed, and skipped counts, with a retry hint naming the
   failed chapter numbers.

`--restore` accepts `--from` / `--to` to bound the range, so a partial recovery
doesn't have to walk all 246 chapters. A full restore is roughly 13 minutes.

### Refactor

The chapter-file assembly block (title, source line, author notes, body,
end notes) is currently duplicated between `cmd_update` and `main`. `cmd_restore`
would be a third copy, so it gets extracted first:

```python
def write_chapter(chapter_num, chapter, path):
    """Fetch, convert, and write one chapter. Returns True on success."""
```

`cmd_update`, `cmd_restore`, and `main` all call it. This is the only
refactoring in scope.

## Documentation

- `CLAUDE.md`: the two "Deployment Hazards" bullets are replaced by the
  guarantees above plus the restore commands, and the recovery table is added.
- `README.md`: deferred to a separate pass, which also removes the Search row.
  No `search.html` exists in `build_html.py`, the manifest, or the deployed
  site; the header's Google site-search box is unrelated and stays.

## Verification

The project has no test suite, so verification is against live state.

1. **Delete guard** — this checkout has zero local media, the dangerous state.
   `build.py --upload --dry-run` must report 0 deletions and list 126 media
   files to restore.
2. **Restore** — a real `--restore-media`, then confirm the file count and spot-
   check a SHA1 against `/api/list`.
3. **Second upload** — an immediate re-run must report nothing to do, proving
   restored hashes landed in the manifest.
4. **Index guard** — call `write_index_guarded` with an empty list and with a
   20%-smaller list against a copy of the real index; both must refuse and leave
   the file byte-identical.
5. **Chapter restore** — `scrape.py --restore --from 245 --to 246` rather than a
   full run; confirm chapter 246 is left alone and 245 comes back intact.
6. **Build** — after the sidestories index is restored, `build.py --build` must
   render 960 side stories rather than the empty placeholder.

## Out of scope

- Any change to how `wiki/build/media/` relates to git. It stays ignored.
- Uploading chapter or side story text anywhere.
- Removing the header search box.
