#!/usr/bin/env python3
"""
build.py — Orchestrator for the Ghost in the City wiki pipeline.

Usage:
  python3 scripts/build.py --status               # cache completeness + kill count
  python3 scripts/build.py --build                # render HTML from cache
  python3 scripts/build.py --upload               # push changed files to Neocities
  python3 scripts/build.py --upload --dry-run     # show what would change
  python3 scripts/build.py --all                  # build + upload
"""

import json
import os
import sys

WIKI_DIR  = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE_DIR = os.path.join(WIKI_DIR, "cache")
GITC_DIR  = os.path.dirname(WIKI_DIR)  # GhostInTheCity/

SUMMARIES_JSON   = os.path.join(CACHE_DIR, "chapter_summaries.json")
BRAINDANCES_JSON = os.path.join(CACHE_DIR, "braindances.json")
CHARACTERS_JSON  = os.path.join(CACHE_DIR, "characters.json")
THREADMARKS      = os.path.join(GITC_DIR, "threadmarks_index.json")


# ── Helpers ────────────────────────────────────────────────────────────────

def load_json(path, default):
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    return default


# ── --status ───────────────────────────────────────────────────────────────

def cmd_status():
    index      = load_json(THREADMARKS, [])
    summaries  = load_json(SUMMARIES_JSON, {})
    bds        = load_json(BRAINDANCES_JSON, [])
    characters = load_json(CHARACTERS_JSON, {})

    total      = len(index)
    summarized = sum(1 for ch in summaries.values() if ch.get("summary"))
    kill_total = sum(int(ch.get("kills", 0)) for ch in summaries.values())

    # Find first unsummarized chapter
    first_missing = None
    for i, chapter in enumerate(index, start=1):
        cid = chapter["chapter_id"]
        if cid not in summaries or not summaries[cid].get("summary"):
            first_missing = i
            break

    print("=" * 60)
    print("  GHOST IN THE CITY WIKI — CACHE STATUS")
    print("=" * 60)
    print(f"  Chapters in index:    {total}")
    print(f"  Chapters summarised:  {summarized} / {total}"
          + (f"  ({100*summarized//total}%)" if total else ""))
    print(f"  Running kill count:   {kill_total}")
    print(f"  Braindances logged:   {len(bds)}")
    print(f"  Characters profiled:  {len(characters)}")
    if first_missing:
        print(f"  Next to summarise:    Chapter {first_missing}")
    else:
        print("  All chapters summarised!")
    print("=" * 60)

    # List characters
    if characters:
        print("\n  Characters:")
        for slug, char in characters.items():
            print(f"    [{slug}]  {char.get('name', '?')}  ({char.get('role', '?')})")

    # List braindances
    if bds:
        print("\n  Braindances:")
        for bd in bds:
            print(f"    [{bd.get('bd_id','?')}]  Ch.{bd.get('chapter_number','?')}  {bd.get('title','?')}")


# ── --build ────────────────────────────────────────────────────────────────

def cmd_build():
    print("Building HTML from cache...")
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "build_html",
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "build_html.py")
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    mod.main()


# ── --upload ───────────────────────────────────────────────────────────────

def cmd_upload(dry_run=False):
    print("Uploading to Neocities...")
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "upload",
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "upload.py")
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    mod.run_upload(dry_run=dry_run)


# ── main ───────────────────────────────────────────────────────────────────

def main():
    args = sys.argv[1:]

    if not args or "--help" in args or "-h" in args:
        print(__doc__)
        return

    dry_run = "--dry-run" in args

    if "--status" in args:
        cmd_status()

    if "--build" in args or "--all" in args:
        cmd_build()

    if "--upload" in args or "--all" in args:
        cmd_upload(dry_run=dry_run)


if __name__ == "__main__":
    main()
