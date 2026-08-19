# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Fan wiki for *Ghost in the City*, a Cyberpunk 2077 / Ghost in the Shell crossover SI fanfic by **Seras** on SpaceBattles and AO3. Static site, Neocities-hosted. Workflow: scrape → hand-write summaries into JSON caches → build HTML → upload.

Always confirm which branch and which script the user wants before running anything. Never run a download/scrape when the user only asked for index/metadata generation (`scrape_media.py --index-only` is the index-only path).

## Architecture

It is a single-pass static site generator with no framework, no templates, and no test suite. Data flows one direction:

```
AO3 / SpaceBattles ──scrapers──> root *_index.json  ─┐
                                                     ├─> build_html.py ──> wiki/build/*.html ──upload.py──> Neocities
Claude (manual summaries) ──> wiki/cache/*.json  ────┘
```

- **Scrapers write indexes, never HTML.** `scrape.py` → `threadmarks_index.json` + `chapters/*.md`; `scrape_sidestories.py` → `sidestories_index.json`; `scrape_media.py` → `media_index.json` + `wiki/build/media/`.
- **`wiki/cache/*.json` is the hand-authored layer.** Summaries, characters, braindances, and rockerboy entries are written by Claude/the user, not scraped. This is the only content you should ever edit by hand.
- **`build_html.py` is the whole renderer** (~1100 lines, stdlib only). One `build_*()` function per page, all wrapped by `page_shell()`, all called from `main()`. HTML strings are built inline; escape through `e()` and route every href through `safe_url()`.
- **`build.py` is a thin CLI** that loads `build_html.py` and `upload.py` via `importlib.util.spec_from_file_location` rather than importing them — they are scripts, not a package.
- **`wiki/build/` is 100% generated.** Every file there is overwritten on build; never edit it directly.
- All scripts resolve paths from `__file__`, so they run from any cwd, but `wiki/` must stay a sibling of the root `*_index.json` files.

### Which file drives which page

| Source | Page |
|---|---|
| `wiki/cache/chapter_summaries.json` | `chapters.html` + the kill counter on `index.html` |
| `wiki/cache/characters.json` | `characters/index.html`, `characters/<slug>.html`, `charsheet.html` (from Motoko's `cp_stats`) |
| `wiki/cache/braindances.json` | `braindances.html` |
| `wiki/cache/rockerboy.json` | `rockerboy.html` |
| `sidestories_index.json` (repo root) | `sidestories.html` |
| `media_index.json` (repo root) | `photomode.html` |
| `threadmarks_index.json` (repo root) | chapter totals / progress percentages |

To add a page: write `build_<page>()`, call it from `main()`, and add the path to `STATIC_PAGES` in `build_html.py` so it lands in the sitemap.

## Common Commands

```bash
source .env                                 # NEOCITIES_API_KEY, SB_USER, SB_PASS, TAVILY_API_KEY

# Full pipeline orchestrator (scrape → build → upload, then prints a manual-TODO list)
python3 update_wiki.py                      # full update
python3 update_wiki.py --scrape             # scrape only
python3 update_wiki.py --build              # build + upload only
python3 update_wiki.py --dry-run            # build, no upload

# Individual scrapers
python3 scrape.py --update                  # pull new AO3 chapters (incremental; 3s/request)
python3 scrape.py --from N [--to M] [--redownload]
python3 scrape.py --restore [--from N --to M]   # rebuild missing/damaged chapters
python3 scrape_sidestories.py [--status] [--force]   # refresh SB side story index
python3 scrape_media.py [--index-only] [--force]    # media index (+ images unless --index-only)

# Build / deploy
python3 wiki/scripts/build.py --status      # cache completeness, kill count, character/BD list
python3 wiki/scripts/build.py --build       # render JSON caches → HTML
python3 wiki/scripts/build.py --upload --dry-run
python3 wiki/scripts/build.py --all         # build + upload
python3 wiki/scripts/build.py --restore-media       # pull media back from Neocities

# Maintenance
python3 wiki/scripts/cleanup_summaries.py   # strip AI patterns (em-dashes, XP numbers, "However")
python3 -m unittest discover -s tests -v    # test suite (stdlib, no env vars needed)
```

Prefer `build.py --status` over counting files: chapter/summary/kill totals change constantly and any number written into docs goes stale fast.

Build/upload and the AO3 scraper are stdlib-only. The SpaceBattles scrapers need `requirements.txt` (`requests`, `beautifulsoup4`, `lxml`); `selenium` is only used by `scripts/debug/`. `install-deps.sh` (depgen-maintained) installs everything.

## Content Durability

Story text and fan art are deliberately kept out of git — chapter text is not redistributed, and the artists asked to stay out of a public GitHub repo. Neither GitHub nor the local disk is the store of record for that content, so each type has an external source and a restore command:

| Content | Store of record | Restore |
|---|---|---|
| `wiki/build/media/` | Neocities | `python3 wiki/scripts/upload.py --restore-media` |
| `chapters/*.md` | AO3 | `python3 scrape.py --restore` |

Media cannot use the AO3-style re-scrape path: its original sources include dead imgur URLs, expired Discord CDN links, Cloudflare-blocked SB attachments, and hand-placed manual replacements. Neocities is the live store of record. Chapters are the reverse — AO3 always has them, and republishing them on Neocities would be the redistribution the project avoids.

**Two media fallbacks exist behind Neocities.** Neither is complete, and both matter when a bad local file has already been pushed over the Neocities original — at that point Neocities is no longer a recovery source.

1. **`media-archive/media-archive.part*.zip`** — AES-256 encrypted volumes holding the full `wiki/build/media/` tree, committed to git so the art is durable without being scrapable. Rebuild or extract with `wiki/scripts/pack_media.py` (see "Encrypted Media Archive" below).
2. **Git history, commit `577f2a7`** — media was tracked until `072e2cd` ("Remove chapters, sidestories, and media from git tracking"). That commit still holds **121 images** as real blobs:
   ```sh
   git show 577f2a7:wiki/build/media/<name> > wiki/build/media/<name>
   ```
   It predates the untracking, so it does **not** cover anything added since.

Some images are gone from every store. As of 2026-08-19 these 11 are referenced by `photomode.html` but exist nowhere — their SpaceBattles posts were deleted upstream, and they postdate `577f2a7`: `91754121_{1,2,3}.png`, `91765497_{1,2,3}.png`, `91788975_{1,2,3,4}.png`, `92611121_1.jpg`.

Guarantees the tooling now enforces:

- **`upload.py` never deletes `media/`.** Paths under `PROTECTED_PREFIXES` are excluded from the delete set even when missing locally, and `run_upload` restores them from Neocities before diffing. Downloads are verified against the SHA1 from `/api/list` and rejected unless the `Content-Type` is an image, so a 404 page cannot land as a broken file. Restoring all 126 images takes about 75 seconds.
- **Scrapers never blank an index.** `scrape_sidestories.py` and `scrape_media.py` write through `lib/safe_index.py`, which refuses a zero-entry result or a shrink beyond 10% and exits 2. Pass `--force` when a drop is real. Writes are atomic with a `.bak` copy and preserve the file's mode.
- **`scrape.py --restore`** re-downloads missing chapters and re-fetches damaged ones (under 500 bytes, or missing the `# ` title line), bounded by `--from` / `--to`.

Run `python3 -m unittest discover -s tests -v` after touching any of this — it needs no environment variables. After deploying, verify the deployed files match the local build; stale deployed files have caused bugs before.

### Encrypted Media Archive

`wiki/build/media/` is gitignored, but `media-archive/` is **tracked**. It holds the same images as AES-256 encrypted zip volumes, so the art rides along in git without being readable by anyone who clones or scrapes the repo.

```bash
python3 wiki/scripts/pack_media.py --status    # compare media/ to the archive (no passphrase)
python3 wiki/scripts/pack_media.py --pack      # rebuild volumes (prompts for passphrase)
python3 wiki/scripts/pack_media.py --verify    # sha256 every entry against the manifest
python3 wiki/scripts/pack_media.py --extract   # restore media/ from the volumes
```

- **Volumes, not one file.** GitHub hard-rejects anything over 100 MiB and warns above 50 MiB; the media set is ~94 MiB. Files are packed in sorted-name order into volumes capped at 45 MiB (`--max-part-bytes`), currently 3 parts. Sorted order means new art usually rewrites only the last volume rather than every blob.
- **The passphrase is never stored.** `pack_media.py` prompts via `getpass`, or reads `MEDIA_ARCHIVE_PASSPHRASE` for non-interactive runs. It is never an argv value, so it stays out of shell history and `ps`. Keep it in a password manager — **git history is permanent, so a weak or leaked passphrase cannot be walked back.**
- **Filenames are not encrypted.** WinZip AES encrypts entry contents, not the central directory, so the post-ID filenames are visible in a tracked volume. That leaks nothing new — `media_index.json` already maps those IDs to their SB URLs and artists in the clear.
- `manifest.json` sits beside the volumes with a sha256 per file. `--verify` is what proves the archive is actually restorable; run it after every `--pack`.
- Repack whenever `--status` reports `STALE`, i.e. after any `scrape_media.py` run that adds images.

## Repo Layout Notes

- `chapters/` and `sidestories/` are **gitignored** (copyrighted story text) and usually near-empty in a checkout. `/process-chapter` and `/fact-check` need the raw chapter file present, so restore first: `scrape.py --restore` for everything, or `scrape.py --restore --from N --to M` for a range.
- Chapter files: `chapters/{NNNN}_{N}._Chapter_{N}.md` — `NNNN` zero-padded to 4 digits (Chapter 42 → `chapters/0042_42._Chapter_42.md`).
- Chapter number → `chapter_id`: index into `threadmarks_index.json` (array position + 1 = chapter number); `chapter_id` is the AO3 chapter id and is the key used in `chapter_summaries.json`.
- `wiki/cache/ss_batch_*.json` hold side-story summaries that nothing in the build reads — they are dormant data, not build inputs.
- `.bak` files (`chapter_summaries.json.bak`, `media_index.json.bak`) are written automatically by `cleanup_summaries.py` / the media scraper.
- Slash commands live in `.claude/commands/` (`process-chapter.md`, `fact-check.md`); `lib/` holds shared scraper helpers (Selenium, SB login, Tavily, image download).

## JSON Schemas

Field-by-field docs for `characters.json`, `braindances.json`, and `rockerboy.json` are in README.md ("How to Edit Wiki Content"). The one not documented there:

### chapter_summaries.json — keyed by `chapter_id` (string)
```json
{
  "12345678": {
    "chapter_num": 1,
    "title": "1. Chapter 1",
    "date": "2022-10-15",
    "summary": ["Paragraph 1...", "Paragraph 2...", "Paragraph 3..."],
    "kills": 0,
    "kill_notes": "No kills -- description of what happened"
  }
}
```

A chapter counts as unsummarized when its `chapter_id` is absent *or* `summary` is empty — that is what `build.py --status` and `update_wiki.py` report on.

## Manual Steps After a Scrape

`update_wiki.py` automates steps 1–5 and then prints what is left:

1. `/process-chapter N` — generate summaries for new chapters (kill counts do not move until this runs)
2. `/fact-check N` — verify summaries against source text
3. Review new chapters for braindance entries (`braindances.json`) and rockerboy performances (`rockerboy.json`)
4. `cleanup_summaries.py` — AI-pattern safety net
5. `python3 wiki/scripts/build.py --all` — rebuild + redeploy

## Manual Image Workflow

Some media images can't be scraped: dead imgur URLs returning placeholder PNGs (fake-success downloads), SB-served logo fallbacks, parser misses, Discord CDN expirations, Cloudflare-blocked SB attachments. Full procedure in [`docs/manual-images.md`](docs/manual-images.md).

- `python3 scrape_media.py --show-manual` — list images needing attention
- `python3 scrape_media.py --mark-manual POST_ID [--count N]` — flag a post (creates placeholders if it has no images yet)
- `python3 scrape_media.py --unmark-manual POST_ID` — clear once a real file is in `wiki/build/media/`

## Writing Style Guide

Derived from Seras's own prose (sampled across chapters 1, 50, 100, 200, 242).

### Seras's Voice

First-person present-tense with these patterns:
- Short punchy fragments as standalone beats: "No thanks." / "Good enough." / "That wasn't my voice."
- Self-interrupting internal monologue: "I mean friends!" / "I definitely didn't cry though. Fuck you."
- Casual Night City slang: "preem", "choom", "chrome", "eddies", "chipped in", "gonk", "nova", "delta"
- Dry humor under pressure: joking during surgery, snarking at corpos mid-op
- Run-on conversational cadence: "It made me feel even more helpless. Realizing that these doctors taking care of me, they literally didn't care about me."
- Game system references woven casually: "I had a stat point" not "the system awarded +1 Body"

### Summary Style Rules

Summaries translate Seras's voice into third-person past-tense recaps:
- Match Seras's punchy, dry energy. Street slang, no literary filler.
- **Tone vocabulary** for "punchy, dry": short sentences, action verbs first, minimal adjectives, no hedging, no editorializing.
- **NO em-dashes** (`—` or ` — `). They read as AI-generated. Use periods, commas, or sentence breaks instead. The cleanup script strips them automatically; the goal is zero hits.
- Summaries should feel like Motoko would approve of how they read.
- **Slang density**: at least one piece of Night City slang per summary, no more than two per paragraph. Use "preem", "choom", "chrome", "eddies", "chipped in", "gonk", "nova", "delta", "scop". If a slang word feels forced, drop it.
- Keep the dark humor. If the chapter is funny, the summary should be too.
- **Never include**: XP values, stat numbers, level-up announcements, perk names, "Meanwhile", "However", "Furthermore", "Additionally".
- When a game mechanic matters to the plot, describe the capability gained, not the number.
- Vary paragraph openers. Not every paragraph starts with "Motoko".
- 2-4 paragraphs per chapter, each covering a distinct scene beat.
- 2-4 sentences per paragraph.

### Kill Counting Rules

- Only count kills Motoko directly causes.
- Confirmed kills only. Unconscious or incapacitated targets do not count unless the text says they died.
- Write a `kill_notes` string explaining the count or explaining why there were no kills.
- When in doubt, undercount and note the ambiguity in kill_notes.
