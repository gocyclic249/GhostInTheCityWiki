#!/usr/bin/env python3
"""
Scraper for Ghost in the City side stories from SpaceBattles.
Uses the Tavily Extract API to bypass Cloudflare protection.
Downloads sidestory threadmarks and saves them as markdown.

Usage:
  python3 scrape_sidestories.py                    # build index + download all (skips existing)
  python3 scrape_sidestories.py --index-only        # just build/refresh the threadmark index
  python3 scrape_sidestories.py --from N            # start downloading from entry N
  python3 scrape_sidestories.py --from N --to M     # download entries N to M
  python3 scrape_sidestories.py --redownload        # force re-download of all
  python3 scrape_sidestories.py --status            # show index stats
"""

import urllib.request
import html.parser
import re
import os
import time
import json
import sys

# ── Config ────────────────────────────────────────────────────────────────

SB_THREAD = "https://forums.spacebattles.com/threads/ghost-in-the-city-cyberpunk-gamer-si.1046809"
SIDESTORY_CATEGORY = 16
THREADMARKS_URL = f"{SB_THREAD}/threadmarks?threadmark_category={SIDESTORY_CATEGORY}"
READER_URL = f"{SB_THREAD}/reader/page-{{page}}?threadmark_category={SIDESTORY_CATEGORY}"
PER_PAGE = 25  # SpaceBattles threadmark index pagination

BASE_DIR   = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.join(BASE_DIR, "sidestories")
INDEX_PATH = os.path.join(BASE_DIR, "sidestories_index.json")

from lib.tavily_utils import tavily_extract, get_tavily_key

# Validate key on startup
get_tavily_key()

DELAY = 1.0  # seconds between Tavily API calls


# ── Index building ────────────────────────────────────────────────────────

def parse_threadmark_entries(text):
    """Parse threadmark titles, word counts, and dates from Tavily-extracted text."""
    entries = []

    # The Tavily text output has entries like:
    #   Title
    # Words Nk
    # Date
    #
    # We look for the pattern after "Reader modeRSS" or similar markers
    # Split by "Words" occurrences

    # Find the threadmarks listing section — after "Reader modeRSS" marker
    marker_idx = text.find("Reader mode")
    if marker_idx == -1:
        marker_idx = text.find("Per page:")
    if marker_idx == -1:
        marker_idx = 0
    listing = text[marker_idx:]

    # Find entries: title line followed by "Words X" line followed by date line
    # Tavily returns markdown links like: *   [Title](URL)
    lines = [l.strip() for l in listing.split("\n") if l.strip()]

    i = 0
    while i < len(lines) - 1:
        line = lines[i]

        # Look ahead for a "Words" line, skipping award badge lines between
        # the title and the word count (badges look like "[![Image ...")
        words_offset = None
        for peek in range(1, 4):
            if i + peek >= len(lines):
                break
            if lines[i + peek].startswith("Words "):
                words_offset = peek
                break
            # Only skip award/image lines between title and Words
            if "![Image" not in lines[i + peek] and "Award" not in lines[i + peek]:
                break

        if words_offset:
            raw_title = line
            word_line = lines[i + words_offset]
            date_idx = i + words_offset + 1
            date_line = lines[date_idx] if date_idx < len(lines) else ""

            # Skip navigation/boilerplate
            skip_titles = {
                "Next", "Prev", "Last", "First", "Go", "Per page:",
                "Reader mode", "RSS", "Threadmarks", "Loading…",
                "Statistics", "Remove this ad space",
            }
            if raw_title in skip_titles or raw_title.startswith("Image "):
                i += 1
                continue

            # Parse markdown link: *   [Title](URL)
            # Use a greedy match for the link text to handle nested brackets
            # like [UR'S ANGELS [BABYLONIAN DEVILS]]
            link_m = re.search(
                r'\[(.+)\]\((https://forums\.spacebattles\.com/[^)]+)\)$',
                raw_title
            )
            if link_m:
                title = link_m.group(1).strip()
                sb_url = link_m.group(2).strip()
                # Extract post_id from URL
                post_m = re.search(r'(?:post-|#post-)(\d+)', sb_url)
                post_id = post_m.group(1) if post_m else None
            else:
                # No link found — check if it's an award badge (skip it)
                if "Image" in raw_title or "Award" in raw_title:
                    i += 1
                    continue
                # Plain title without URL
                title = raw_title.lstrip("* \t")
                sb_url = None
                post_id = None

            # Skip award entries that slipped through
            if not title or "Award" in title or title.startswith("!["):
                i += 1
                continue

            # Extract word count
            wc_m = re.search(r'Words\s+([\d.,]+k?)', word_line)
            word_count = wc_m.group(1) if wc_m else "?"

            # Date is typically like "Oct 16, 2022"
            date = date_line if re.match(r'[A-Z][a-z]{2}\s+\d', date_line) else ""

            entries.append({
                "title": title,
                "word_count": word_count,
                "date": date,
                "sb_url": sb_url,
                "post_id": post_id,
            })
            i += words_offset + (2 if date else 1)
            continue

        i += 1

    return entries


def fetch_threadmark_index():
    """Fetch all threadmark index pages and build the complete index."""
    print("Fetching sidestory threadmarks index...")

    # Fetch first page to detect total pages
    results = tavily_extract(f"{THREADMARKS_URL}&per_page={PER_PAGE}&page=1")
    if not results:
        print("ERROR: Could not fetch first threadmarks page")
        sys.exit(1)

    text = results[0]["raw_content"]

    # Detect total pages from "X of Y" pattern
    pages_m = re.search(r'(\d+)\s+of\s+(\d+)', text)
    total_pages = int(pages_m.group(2)) if pages_m else 1
    print(f"  Found {total_pages} pages of threadmarks")

    all_entries = parse_threadmark_entries(text)
    print(f"  Page 1/{total_pages}: {len(all_entries)} entries")

    # Fetch remaining pages in batches of 5
    for batch_start in range(2, total_pages + 1, 5):
        batch_end = min(batch_start + 5, total_pages + 1)
        urls = [
            f"{THREADMARKS_URL}&per_page={PER_PAGE}&page={p}"
            for p in range(batch_start, batch_end)
        ]
        print(f"  Fetching pages {batch_start}-{batch_end - 1}...")
        time.sleep(DELAY)

        results = tavily_extract(urls)
        for r in results:
            entries = parse_threadmark_entries(r["raw_content"])
            page_num = re.search(r'page=(\d+)', r["url"])
            pn = page_num.group(1) if page_num else "?"
            print(f"    Page {pn}: {len(entries)} entries")
            all_entries.extend(entries)

    # Deduplicate by title (preserving order)
    seen = set()
    unique = []
    for entry in all_entries:
        key = entry["title"]
        if key not in seen:
            seen.add(key)
            unique.append(entry)

    # Number them
    for i, entry in enumerate(unique, 1):
        entry["index"] = i

    print(f"\n  Total unique sidestory threadmarks: {len(unique)}")
    return unique


# ── Reader mode content extraction ────────────────────────────────────────

def parse_reader_page(text):
    """
    Parse a reader mode page to extract individual post content.
    Returns list of {title, author, date, content}.
    """
    posts = []

    # Reader mode shows posts sequentially. Each post has:
    # - A "Sidestory Title" line (threadmark label)
    # - Author name
    # - Date
    # - Post content
    #
    # We split on "Sidestory " prefix or "View content" / "View discussion" markers

    # Look for threadmark headers — "Sidestory TITLE" pattern
    # Also: posts are separated by author attribution blocks

    # Strategy: split by "View discussion" which appears between posts
    sections = re.split(r'View discussion\s*', text)

    for section in sections:
        # Look for "Sidestory TITLE" or threadmark title marker
        # Then "View content" followed by the actual content
        tm_m = re.search(r'Sidestory\s+(.+?)(?:\n|$)', section)
        
        if not tm_m:
            # Try alternate: just look for a title before "View content"
            tm_m = re.search(r'(?:^|\n)\s*([A-Z][^\n]{3,80})\s*\n\s*View content', section)

        if not tm_m:
            continue

        title = tm_m.group(1).strip()

        # Find author — pattern like "username\nDate"
        author_m = re.search(
            r'####\s+(\w[\w\s]*)\n\s*([A-Z][a-z]{2}\s+\d{1,2},\s+\d{4})',
            section
        )
        if not author_m:
            author_m = re.search(r'\n\s{2,}(\w+)\s*\n\s*([A-Z][a-z]{2}\s+\d)', section)

        author = author_m.group(1).strip() if author_m else "Unknown"
        date = author_m.group(2).strip() if author_m else ""

        # Content comes after "View content" marker
        vc_idx = section.find("View content")
        if vc_idx >= 0:
            content = section[vc_idx + len("View content"):].strip()
        else:
            # Take everything after the title
            content = section[tm_m.end():].strip()

        # Clean up content — remove trailing navigation/boilerplate
        # Cut at next threadmark marker or page nav
        for cutoff in ["Sidestory ", "#### Go to page", "Loading…",
                       "Statistics (", "Creative Works", "Creative Writing"]:
            cut_idx = content.find(cutoff)
            if cut_idx > 0:
                content = content[:cut_idx].strip()

        if content and len(content) > 20:
            posts.append({
                "title": title,
                "author": author,
                "date": date,
                "content": content,
            })

    return posts


def download_via_reader(index, start_num=1, end_num=None, redownload=False):
    """Download sidestories via reader mode pages."""
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    total = len(index)
    target_end = end_num or total
    target_titles = {
        entry["title"]: entry
        for entry in index[start_num - 1 : target_end]
    }

    # Figure out which reader pages we need
    # Reader mode shows ~10 posts per page. We need to figure out
    # which reader page corresponds to which index entry.
    # Reader pages are sequential — page 1 has entries 1-10, page 2 has 11-20, etc.
    # But page size varies. We'll estimate and adjust.

    posts_per_page = 10  # SpaceBattles reader default
    start_reader_page = max(1, (start_num - 1) // posts_per_page + 1)
    # Fetch more pages than strictly needed to handle variable page sizes
    end_reader_page = (target_end // posts_per_page) + 2

    print(f"Downloading sidestories {start_num} to {target_end} via reader mode")
    print(f"  Estimated reader pages: {start_reader_page} to {end_reader_page}")
    print()

    saved = 0
    skipped = 0
    failed_titles = []
    matched_titles = set()

    for rp in range(start_reader_page, end_reader_page + 1):
        # Check if we've matched all target titles
        if len(matched_titles) >= len(target_titles):
            break

        url = READER_URL.format(page=rp)
        print(f"  Fetching reader page {rp}...")
        time.sleep(DELAY)

        results = tavily_extract(url)
        if not results:
            print(f"    WARNING: Failed to fetch reader page {rp}")
            continue

        posts = parse_reader_page(results[0]["raw_content"])
        print(f"    Found {len(posts)} posts on page {rp}")

        for post in posts:
            title = post["title"]
            if title not in target_titles:
                continue
            if title in matched_titles:
                continue

            matched_titles.add(title)
            entry = target_titles[title]
            idx = entry["index"]

            filename = f"{idx:04d}_{sanitize_filename(title)}.md"
            filepath = os.path.join(OUTPUT_DIR, filename)

            if os.path.exists(filepath) and not redownload:
                size = os.path.getsize(filepath)
                if size > 100:
                    skipped += 1
                    continue

            author = post.get("author", "Unknown")
            date = post.get("date", entry.get("date", ""))
            word_count = entry.get("word_count", "?")
            content = post["content"]

            lines = [f"# {title}\n"]
            lines.append(f"*Author: {author}*")
            lines.append(f"*Source: SpaceBattles — Ghost in the City sidestory*")
            if date:
                lines.append(f"*Date: {date}*")
            if word_count and word_count != "?":
                lines.append(f"*Words: ~{word_count}*")
            lines.append("\n---\n")
            lines.append(content)

            with open(filepath, "w", encoding="utf-8") as f:
                f.write("\n".join(lines) + "\n")

            actual_words = len(content.split())
            print(f"    [{idx}/{total}] Saved: {filename} (~{actual_words} words)")
            saved += 1

    # Report
    print(f"\nReader mode download complete.")
    print(f"  Saved: {saved}")
    print(f"  Skipped (existing): {skipped}")
    unmatched = set(target_titles.keys()) - matched_titles
    if unmatched:
        print(f"  Not found in reader pages: {len(unmatched)}")
        for t in sorted(unmatched):
            print(f"    - {t}")


def extract_post_from_tavily(raw_content, post_id=None):
    """Extract the relevant post content from a Tavily-fetched SB page.
    Removes SpaceBattles boilerplate/navigation and isolates the post text."""
    text = raw_content

    # If we have a post_id, find the post content block after it
    if post_id:
        pid_marker = f"post-{post_id})"
        pid_idx = text.find(pid_marker)
        if pid_idx >= 0:
            text = text[pid_idx + len(pid_marker):]

        # Cut off at the next post boundary. On SpaceBattles, each new post
        # is preceded by an author header like "#### [username](url)" with a
        # post number line like "*   [#61,503](url#post-XXXXXX)".
        # We detect the next post by looking for a "#post-" reference with a
        # DIFFERENT post ID than our target — that marks where our post ends
        # and someone else's begins. We also stop at the post footer block
        # which contains like counts, author attribution, and dates.
        lines = text.split("\n")
        cut_at = len(lines)
        # Track when we've passed actual content (not just leading boilerplate)
        seen_content = False
        for j, line in enumerate(lines):
            stripped = line.strip()
            if not seen_content:
                # Skip leading boilerplate to avoid false positives
                if stripped and not stripped.startswith("*") and not stripped.startswith("#"):
                    seen_content = True
                continue
            # Post footer: like count line e.g. "*   [300](url "Like")"
            if re.match(r'\*\s+\[\d+\]\(.*"Like"\)', stripped):
                cut_at = j
                break
            # Next post's number line e.g. "*   [#61,503](url#post-XXXXXX)"
            if re.match(r'\*\s+\[#[\d,]+\]', stripped):
                # Check it's a different post ID
                other_pid = re.search(r'#post-(\d+)', stripped)
                if other_pid and other_pid.group(1) != str(post_id):
                    # Back up to include nothing from the next post's header
                    # Look backwards for the start of the author block
                    while cut_at > 0 and j > 0:
                        j -= 1
                        prev = lines[j].strip()
                        if prev.startswith("#### [") or prev.startswith("[![Image"):
                            break
                    cut_at = j
                    break
            # Author header for a new post "#### [username](url)"
            # followed shortly by a different post-id reference
            if stripped.startswith("#### [") and j + 5 < len(lines):
                # Peek ahead to confirm this is a new post (has a #post- ref)
                lookahead = "\n".join(lines[j:j+6])
                other_pid = re.search(r'#post-(\d+)', lookahead)
                if other_pid and other_pid.group(1) != str(post_id):
                    cut_at = j
                    # Also trim any avatar image line before the header
                    if cut_at > 0 and lines[cut_at - 1].strip().startswith("[![Image"):
                        cut_at -= 1
                    break
        text = "\n".join(lines[:cut_at])

    # Remove leading boilerplate: post number links, empty bullets, etc.
    # Pattern: lines starting with * or # that are navigation
    lines = text.split("\n")
    content_start = 0
    for j, line in enumerate(lines):
        stripped = line.strip()
        # Skip empty lines, bullet-point nav links, post number refs
        if not stripped:
            continue
        # Only skip navigation-style post links (e.g. "*   [#12,345](url#post-...)")
        # but NOT quote attributions (e.g. "*   [username said:](url#post-...)")
        if stripped.startswith("*   [") and ("#post-" in stripped or "page-" in stripped):
            # Navigation links have a post number like [#12,345] or [12,345]
            link_text_m = re.match(r'\*\s+\[#?[\d,]+\]', stripped)
            if link_text_m:
                continue
            # Also skip bare page nav links like [Prev] [Next] [1] [2]
            link_text_m2 = re.match(r'\*\s+\[(Prev|Next|First|Last|\d+)\]', stripped)
            if link_text_m2:
                continue
            # Otherwise it's likely a quote attribution — stop skipping
        if stripped.startswith("#") and len(stripped) < 10:
            continue
        # Found actual content
        content_start = j
        break

    text = "\n".join(lines[content_start:])

    # Remove trailing boilerplate — anything after the post
    trail_markers = [
        "\nReply\n", "\nLoading…", "\nCreative Works\n",
        "\nCreative Writing\n", "\nRemove this ad space",
        "\nContact us\n", "\nTerms and rules\n",
        "\n#### Go to page", "\nReport\n",
        "\nShare:\n", "\nYou must log in",
    ]
    for marker in trail_markers:
        idx = text.find(marker)
        if idx > 0:
            text = text[:idx].strip()

    # Remove "Click to expand/shrink" artifacts
    text = re.sub(r'\[Click to expand\.\.\.\]\([^)]*\)', '', text)
    text = re.sub(r'\[Click to shrink\.\.\.\]\([^)]*\)', '', text)

    # Clean up excessive blank lines
    text = re.sub(r'\n{4,}', '\n\n\n', text)

    return text.strip()


def download_individually(index, start_num=1, end_num=None, redownload=False):
    """Download sidestories one at a time via individual post URLs."""
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    total = len(index)
    success = 0
    skipped = 0
    failed = []

    for i, entry in enumerate(index[start_num - 1:], start=start_num):
        if end_num and i > end_num:
            break

        title = entry["title"]
        word_count = entry.get("word_count", "?")
        date = entry.get("date", "")
        sb_url = entry.get("sb_url", "")
        post_id = entry.get("post_id", "")

        filename = f"{i:04d}_{sanitize_filename(title)}.md"
        filepath = os.path.join(OUTPUT_DIR, filename)

        if os.path.exists(filepath) and not redownload:
            size = os.path.getsize(filepath)
            if size > 100:
                skipped += 1
                continue

        if not sb_url:
            print(f"[{i}/{total}] SKIP (no URL): {title}")
            failed.append(i)
            continue

        print(f"[{i}/{total}] {title} (~{word_count} words)")
        time.sleep(DELAY)

        results = tavily_extract(sb_url)
        if not results:
            print(f"  FAILED to fetch")
            failed.append(i)
            continue

        content = extract_post_from_tavily(results[0]["raw_content"], post_id)

        if not content or len(content) < 20:
            print(f"  WARNING: Empty or too short content, skipping")
            failed.append(i)
            continue

        # Save
        lines = [f"# {title}\n"]
        lines.append(f"*Source: {sb_url}*")
        if date:
            lines.append(f"*Date: {date}*")
        if word_count and word_count != "?":
            lines.append(f"*Words: ~{word_count}*")
        lines.append("\n---\n")
        lines.append(content)

        with open(filepath, "w", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")

        actual_words = len(content.split())
        print(f"  Saved: {filename} (~{actual_words} words)")
        success += 1

    print(f"\nDone! {success} sidestories saved, {skipped} skipped (existing).")
    if failed:
        print(f"Failed entries ({len(failed)}): {failed}")
    print(f"Output directory: {OUTPUT_DIR}")


# ── Utility ───────────────────────────────────────────────────────────────

def sanitize_filename(s):
    s = re.sub(r'[^\w\s\-\.]', '', s)
    s = re.sub(r'\s+', '_', s.strip())
    return s[:80]


# ── Commands ──────────────────────────────────────────────────────────────

def cmd_build_index():
    """Build or refresh the sidestory index."""
    entries = fetch_threadmark_index()

    with open(INDEX_PATH, "w", encoding="utf-8") as f:
        json.dump(entries, f, indent=2, ensure_ascii=False)
    print(f"  Saved index to {INDEX_PATH}")
    return entries


def cmd_status():
    """Show index stats."""
    if not os.path.exists(INDEX_PATH):
        print("No index file found. Run without --status first to build it.")
        return

    with open(INDEX_PATH, encoding="utf-8") as f:
        index = json.load(f)

    downloaded = 0
    total_words = 0
    if os.path.exists(OUTPUT_DIR):
        for fname in os.listdir(OUTPUT_DIR):
            if fname.endswith(".md"):
                downloaded += 1
                fpath = os.path.join(OUTPUT_DIR, fname)
                with open(fpath, encoding="utf-8") as f:
                    total_words += len(f.read().split())

    print("=" * 60)
    print("  GHOST IN THE CITY — SIDESTORY STATUS")
    print("=" * 60)
    print(f"  Sidestories in index:   {len(index)}")
    print(f"  Downloaded:             {downloaded} / {len(index)}")
    print(f"  Total words downloaded: ~{total_words:,}")
    print("=" * 60)


def cmd_download(start_num=1, end_num=None, redownload=False):
    """Download sidestory content."""
    # Load or build index
    if os.path.exists(INDEX_PATH):
        with open(INDEX_PATH, encoding="utf-8") as f:
            index = json.load(f)
        print(f"Loaded index with {len(index)} sidestory entries.")
    else:
        index = cmd_build_index()

    # Count how many have URLs
    with_urls = sum(1 for e in index if e.get("sb_url"))
    print(f"  {with_urls}/{len(index)} entries have direct URLs")

    # Download individually using post URLs
    download_individually(index, start_num, end_num, redownload)


# ── Entry point ───────────────────────────────────────────────────────────

def main():
    args = sys.argv[1:]

    if "--help" in args or "-h" in args:
        print(__doc__)
        return

    if "--status" in args:
        cmd_status()
        return

    if "--index-only" in args:
        cmd_build_index()
        return

    redownload = "--redownload" in args

    start_num = 1
    if "--from" in args:
        idx = args.index("--from")
        if idx + 1 < len(args):
            start_num = int(args[idx + 1])

    end_num = None
    if "--to" in args:
        idx = args.index("--to")
        if idx + 1 < len(args):
            end_num = int(args[idx + 1])

    cmd_download(start_num=start_num, end_num=end_num, redownload=redownload)


if __name__ == "__main__":
    main()
