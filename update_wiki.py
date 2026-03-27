#!/usr/bin/env python3
"""
update_wiki.py — Unified wiki update script.
Runs all scrapers, rebuilds HTML, uploads to Neocities, and reports
what manual steps remain.

Usage:
  python3 update_wiki.py              # full update: scrape + build + upload
  python3 update_wiki.py --scrape     # scrape only (no build/upload)
  python3 update_wiki.py --build      # build + upload only (no scraping)
  python3 update_wiki.py --dry-run    # show what would change, don't upload

Requires environment variables:
  TAVILY_API_KEY     — for SpaceBattles scraping
  NEOCITIES_API_KEY  — for Neocities upload
"""

import json
import os
import subprocess
import sys

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
WIKI_DIR = os.path.join(BASE_DIR, "wiki")

# Paths for before/after comparison
THREADMARKS_INDEX = os.path.join(BASE_DIR, "threadmarks_index.json")
SIDESTORIES_INDEX = os.path.join(BASE_DIR, "sidestories_index.json")
MEDIA_INDEX = os.path.join(BASE_DIR, "media_index.json")
SUMMARIES_JSON = os.path.join(WIKI_DIR, "cache", "chapter_summaries.json")


def load_json(path, default):
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    return default


def count_index(path):
    data = load_json(path, [])
    return len(data) if isinstance(data, list) else len(data.keys())


def run_script(label, cmd):
    """Run a script and return True if it succeeded."""
    print(f"\n{'=' * 60}")
    print(f"  {label}")
    print(f"{'=' * 60}\n", flush=True)
    result = subprocess.run(cmd, cwd=BASE_DIR)
    if result.returncode != 0:
        print(f"\n  WARNING: {label} exited with code {result.returncode}")
        return False
    return True


def main():
    args = sys.argv[1:]
    dry_run = "--dry-run" in args
    scrape_only = "--scrape" in args
    build_only = "--build" in args

    # Check environment
    missing_env = []
    if not build_only:
        if not os.environ.get("TAVILY_API_KEY"):
            missing_env.append("TAVILY_API_KEY")
    if not os.environ.get("NEOCITIES_API_KEY"):
        missing_env.append("NEOCITIES_API_KEY")
    if missing_env:
        print(f"ERROR: Missing environment variables: {', '.join(missing_env)}")
        print("  Run: source .env")
        sys.exit(1)

    # ── Snapshot before counts ────────────────────────────────────────
    ch_before = count_index(THREADMARKS_INDEX)
    ss_before = count_index(SIDESTORIES_INDEX)
    media_before = count_index(MEDIA_INDEX)
    summaries_before = count_index(SUMMARIES_JSON)

    # ── Scrape ────────────────────────────────────────────────────────
    if not build_only:
        # 1. Chapters from AO3
        run_script(
            "Scraping chapters from AO3",
            [sys.executable, os.path.join(BASE_DIR, "scrape.py"), "--update"]
        )

        # 2. Sidestory threadmarks from SpaceBattles (index only — no downloads)
        run_script(
            "Scraping sidestory index from SpaceBattles",
            [sys.executable, os.path.join(BASE_DIR, "scrape_sidestories.py"), "--index-only"]
        )

        # 3. Media threadmarks + images from SpaceBattles
        run_script(
            "Scraping media index + images from SpaceBattles",
            [sys.executable, os.path.join(BASE_DIR, "scrape_media.py")]
        )

    if scrape_only:
        print("\n  Scrape complete. Run 'python3 update_wiki.py --build' to rebuild.")
        return

    # ── Build + Upload ────────────────────────────────────────────────
    build_args = ["--all"]
    if dry_run:
        build_args = ["--build"]  # build but don't upload

    run_script(
        "Building HTML and uploading to Neocities",
        [sys.executable, os.path.join(WIKI_DIR, "scripts", "build.py")] + build_args
    )

    # ── After counts ──────────────────────────────────────────────────
    ch_after = count_index(THREADMARKS_INDEX)
    ss_after = count_index(SIDESTORIES_INDEX)
    media_after = count_index(MEDIA_INDEX)
    summaries_after = count_index(SUMMARIES_JSON)

    new_chapters = ch_after - ch_before
    new_sidestories = ss_after - ss_before
    new_media = media_after - media_before

    # Figure out unsummarized chapters
    threadmarks = load_json(THREADMARKS_INDEX, [])
    summaries = load_json(SUMMARIES_JSON, {})
    unsummarized = []
    for i, ch in enumerate(threadmarks, 1):
        cid = ch.get("chapter_id", "")
        if cid not in summaries or not summaries[cid].get("summary"):
            unsummarized.append(i)

    # ── Report ────────────────────────────────────────────────────────
    print(f"\n{'=' * 60}")
    print(f"  UPDATE COMPLETE")
    print(f"{'=' * 60}")
    print(f"  Chapters:      {ch_after} total ({'+' + str(new_chapters) if new_chapters else 'no change'})")
    print(f"  Side stories:  {ss_after} total ({'+' + str(new_sidestories) if new_sidestories else 'no change'})")
    print(f"  Media posts:   {media_after} total ({'+' + str(new_media) if new_media else 'no change'})")
    print(f"  Summarized:    {summaries_after}/{ch_after} chapters")
    print(f"{'=' * 60}")

    # ── Manual TODO reminder ──────────────────────────────────────────
    todos = []

    if unsummarized:
        if len(unsummarized) <= 5:
            ch_list = ", ".join(str(c) for c in unsummarized)
        else:
            ch_list = f"{unsummarized[0]}-{unsummarized[-1]} ({len(unsummarized)} chapters)"
        todos.append(f"Summarize chapters: /process-chapter {ch_list}")
        todos.append(f"  (kill counts won't update until chapters are summarized)")

    if new_chapters > 0:
        todos.append(f"Review {new_chapters} new chapter(s) for braindance or character updates")
        todos.append(f"  - Check wiki/cache/braindances.json")
        todos.append(f"  - Check wiki/cache/characters.json")

    if new_chapters > 0 or new_sidestories > 0 or new_media > 0:
        todos.append(f"Rebuild after manual updates: python3 wiki/scripts/build.py --all")

    if todos:
        print(f"\n  // MANUAL TODO — DON'T FORGET, CHOOM")
        print(f"  {'─' * 50}")
        for todo in todos:
            print(f"  ▸ {todo}")
        print(f"  {'─' * 50}")
    else:
        print(f"\n  Everything is up to date. Nova.")

    print()


if __name__ == "__main__":
    main()
