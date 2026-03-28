#!/usr/bin/env python3
"""
Scraper for Ghost in the City side stories from SpaceBattles.
Fetches the threadmarks index pages directly and extracts title, URL, and author.

Usage:
  python3 scrape_sidestories.py                # build/refresh the sidestory index
  python3 scrape_sidestories.py --status       # show index stats
"""

import json
import os
import re
import sys
import time

import requests
from bs4 import BeautifulSoup

# ── Config ────────────────────────────────────────────────────────────────

SB_BASE = "https://forums.spacebattles.com"
SB_THREAD = f"{SB_BASE}/threads/ghost-in-the-city-cyberpunk-gamer-si.1046809"
SIDESTORY_CATEGORY = 16
THREADMARKS_URL = f"{SB_THREAD}/threadmarks?threadmark_category={SIDESTORY_CATEGORY}"
PER_PAGE = 25

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
INDEX_PATH = os.path.join(BASE_DIR, "sidestories_index.json")

HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}
DELAY = 1.0  # seconds between requests


# ── Scraping ──────────────────────────────────────────────────────────────

def fetch_page(page_num):
    """Fetch a single threadmarks index page and return parsed entries."""
    url = f"{THREADMARKS_URL}&per_page={PER_PAGE}&page={page_num}"

    for attempt in range(3):
        try:
            r = requests.get(url, headers=HEADERS, timeout=30)
            r.raise_for_status()
            break
        except requests.RequestException as e:
            print(f"  Attempt {attempt + 1} failed for page {page_num}: {e}")
            if attempt < 2:
                time.sleep(5 * (attempt + 1))
            else:
                print(f"  ERROR: Could not fetch page {page_num}")
                return [], 1

    soup = BeautifulSoup(r.text, "lxml")

    # Detect total pages from pagination
    total_pages = 1
    page_nav = soup.select_one(".pageNav-main")
    if page_nav:
        page_links = page_nav.select("a")
        if page_links:
            last = page_links[-1].text.strip()
            if last.isdigit():
                total_pages = int(last)

    # Parse threadmark entries
    entries = []
    for item in soup.select(".structItem--threadmark"):
        title_el = item.select_one(".structItem-title a")
        if not title_el:
            continue

        title = title_el.text.strip()
        href = title_el.get("href", "")
        if href and not href.startswith("http"):
            href = SB_BASE + href

        author = item.get("data-content-author", "")

        # Extract post_id from URL fragment
        post_m = re.search(r"#post-(\d+)", href)
        post_id = post_m.group(1) if post_m else None

        # Word count from meta cell
        wc_el = item.select_one(".structItem-cell--meta dd")
        word_count = wc_el.text.strip() if wc_el else ""

        # Date from latest cell
        date_el = item.select_one(".structItem-cell--latest time")
        date = date_el.get("data-date-string", "") if date_el else ""

        entries.append({
            "title": title,
            "sb_url": href,
            "post_id": post_id,
            "author": author,
            "word_count": word_count,
            "date": date,
        })

    return entries, total_pages


def fetch_all_threadmarks():
    """Fetch all threadmark index pages and return the complete list."""
    print("Fetching sidestory threadmarks index...")

    entries, total_pages = fetch_page(1)
    print(f"  Page 1/{total_pages}: {len(entries)} entries")

    for page_num in range(2, total_pages + 1):
        time.sleep(DELAY)
        page_entries, _ = fetch_page(page_num)
        print(f"  Page {page_num}/{total_pages}: {len(page_entries)} entries")
        entries.extend(page_entries)

    # Number them
    for i, entry in enumerate(entries, 1):
        entry["index"] = i

    print(f"\n  Total sidestory threadmarks: {len(entries)}")
    return entries


# ── Commands ──────────────────────────────────────────────────────────────

def cmd_build_index():
    """Build or refresh the sidestory index."""
    entries = fetch_all_threadmarks()

    with open(INDEX_PATH, "w", encoding="utf-8") as f:
        json.dump(entries, f, indent=2, ensure_ascii=False)
    print(f"  Saved index to {INDEX_PATH}")
    return entries


def cmd_status():
    """Show index stats."""
    if not os.path.exists(INDEX_PATH):
        print("No index file found. Run the scraper first to build it.")
        return

    with open(INDEX_PATH, encoding="utf-8") as f:
        index = json.load(f)

    print("=" * 60)
    print("  GHOST IN THE CITY — SIDESTORY INDEX STATUS")
    print("=" * 60)
    print(f"  Sidestories in index:  {len(index)}")

    # Count unique authors
    authors = set(e.get("author", "") for e in index if e.get("author"))
    print(f"  Unique authors:        {len(authors)}")

    # Entries missing data
    no_url = sum(1 for e in index if not e.get("sb_url"))
    no_author = sum(1 for e in index if not e.get("author"))
    if no_url:
        print(f"  Missing URL:           {no_url}")
    if no_author:
        print(f"  Missing author:        {no_author}")
    print("=" * 60)


# ── Entry point ───────────────────────────────────────────────────────────

def main():
    args = sys.argv[1:]

    if "--help" in args or "-h" in args:
        print(__doc__)
        return

    if "--status" in args:
        cmd_status()
        return

    cmd_build_index()


if __name__ == "__main__":
    main()
