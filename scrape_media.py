#!/usr/bin/env python3
"""
Scraper for Ghost in the City fan art/media from SpaceBattles.
Uses the Tavily Extract API to bypass Cloudflare protection.
Downloads media threadmarks, extracts image URLs, and saves images locally.

Usage:
  python3 scrape_media.py                     # build index + download all (skips existing)
  python3 scrape_media.py --index-only         # just build/refresh the threadmark index
  python3 scrape_media.py --from N             # start downloading from entry N
  python3 scrape_media.py --from N --to M      # download entries N to M
  python3 scrape_media.py --redownload         # force re-download of all
  python3 scrape_media.py --status             # show index stats
"""

import urllib.request
import urllib.error
import re
import os
import time
import json
import sys

# ── Config ────────────────────────────────────────────────────────────────

SB_THREAD = "https://forums.spacebattles.com/threads/ghost-in-the-city-cyberpunk-gamer-si.1046809"
MEDIA_CATEGORY = 10
THREADMARKS_URL = f"{SB_THREAD}/threadmarks?threadmark_category={MEDIA_CATEGORY}"
PER_PAGE = 25

BASE_DIR   = os.path.dirname(os.path.abspath(__file__))
IMAGE_DIR  = os.path.join(BASE_DIR, "wiki", "build", "media")
INDEX_PATH = os.path.join(BASE_DIR, "media_index.json")

# Tavily API
TAVILY_API_KEY = os.environ.get("TAVILY_API_KEY", "")
if not TAVILY_API_KEY:
    print("ERROR: TAVILY_API_KEY environment variable is required.")
    print("  Set it with: export TAVILY_API_KEY=your-key-here")
    sys.exit(1)
TAVILY_EXTRACT_URL = "https://api.tavily.com/extract"

DELAY = 1.0

# URLs to skip (avatars, forum UI, etc.)
SKIP_URL_PATTERNS = [
    r'forums\.spacebattles\.com/data/avatar/',
    r'forums\.spacebattles\.com/styles/',
    r'forums\.spacebattles\.com/data/assets/',
    r'smilies/',
]


# ── Tavily fetch helper ───────────────────────────────────────────────────

def tavily_extract(urls, extract_depth="advanced"):
    """Fetch one or more URLs via Tavily Extract API."""
    if isinstance(urls, str):
        urls = [urls]

    payload = json.dumps({
        "api_key": TAVILY_API_KEY,
        "urls": urls,
        "extract_depth": extract_depth,
    }).encode("utf-8")

    req = urllib.request.Request(
        TAVILY_EXTRACT_URL,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                results = data.get("results", [])
                return [
                    {"url": r.get("url", ""), "raw_content": r.get("raw_content", "")}
                    for r in results
                ]
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", errors="replace") if e.fp else ""
            print(f"  Tavily HTTP {e.code}, attempt {attempt+1}: {body[:200]}")
            if e.code == 429:
                time.sleep(30 * (attempt + 1))
            else:
                time.sleep(5)
        except Exception as e:
            print(f"  Tavily error: {e}, attempt {attempt+1}")
            time.sleep(5)
    return []


# ── Index building ────────────────────────────────────────────────────────

def parse_threadmark_entries(text):
    """Parse threadmark titles, word counts, and dates from Tavily-extracted text."""
    entries = []

    marker_idx = text.find("Reader mode")
    if marker_idx == -1:
        marker_idx = text.find("Per page:")
    if marker_idx == -1:
        marker_idx = 0
    listing = text[marker_idx:]

    lines = [l.strip() for l in listing.split("\n") if l.strip()]

    i = 0
    while i < len(lines) - 1:
        line = lines[i]

        # Look ahead for "Words" line, skipping award badge lines
        words_offset = None
        for peek in range(1, 4):
            if i + peek >= len(lines):
                break
            if lines[i + peek].startswith("Words "):
                words_offset = peek
                break
            if "![Image" not in lines[i + peek] and "Award" not in lines[i + peek]:
                break

        if words_offset:
            raw_title = line
            word_line = lines[i + words_offset]
            date_idx = i + words_offset + 1
            date_line = lines[date_idx] if date_idx < len(lines) else ""

            skip_titles = {
                "Next", "Prev", "Last", "First", "Go", "Per page:",
                "Reader mode", "RSS", "Threadmarks", "Loading…",
                "Statistics", "Remove this ad space",
            }
            if raw_title in skip_titles or raw_title.startswith("Image "):
                i += 1
                continue

            link_m = re.search(
                r'\[(.+)\]\((https://forums\.spacebattles\.com/[^)]+)\)$',
                raw_title
            )
            if link_m:
                title = link_m.group(1).strip()
                sb_url = link_m.group(2).strip()
                post_m = re.search(r'(?:post-|#post-)(\d+)', sb_url)
                post_id = post_m.group(1) if post_m else None
            else:
                if "Image" in raw_title or "Award" in raw_title:
                    i += 1
                    continue
                title = raw_title.lstrip("* \t")
                sb_url = None
                post_id = None

            if not title or "Award" in title or title.startswith("!["):
                i += 1
                continue

            wc_m = re.search(r'Words\s+([\d.,]+k?)', word_line)
            word_count = wc_m.group(1) if wc_m else "?"

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
    """Fetch all media threadmark index pages."""
    print("Fetching media threadmarks index...")

    results = tavily_extract(f"{THREADMARKS_URL}&per_page={PER_PAGE}&page=1")
    if not results:
        print("ERROR: Could not fetch first threadmarks page")
        sys.exit(1)

    text = results[0]["raw_content"]

    pages_m = re.search(r'(\d+)\s+of\s+(\d+)', text)
    total_pages = int(pages_m.group(2)) if pages_m else 1
    print(f"  Found {total_pages} pages of threadmarks")

    all_entries = parse_threadmark_entries(text)
    print(f"  Page 1/{total_pages}: {len(all_entries)} entries")

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

    # Deduplicate by title
    seen = set()
    unique = []
    for entry in all_entries:
        key = entry["title"]
        if key not in seen:
            seen.add(key)
            unique.append(entry)

    for i, entry in enumerate(unique, 1):
        entry["index"] = i

    print(f"\n  Total unique media threadmarks: {len(unique)}")
    return unique


# ── Post content extraction ───────────────────────────────────────────────

def is_skip_url(url):
    """Check if URL should be skipped (avatars, smilies, etc.)."""
    for pattern in SKIP_URL_PATTERNS:
        if re.search(pattern, url):
            return True
    return False


def extract_images_from_content(text):
    """Extract image URLs from markdown content. Returns list of {url, alt_text}."""
    images = []
    # Match ![alt](url) patterns
    for m in re.finditer(r'!\[([^\]]*)\]\((https?://[^)]+)\)', text):
        alt = m.group(1).strip()
        url = m.group(2).strip()
        if is_skip_url(url):
            continue
        # Skip if alt text suggests it's an avatar
        if alt and re.match(r'^Image \d+: \w+$', alt):
            # Could be "Image 5: Username" — check if URL is an avatar
            if 'avatar' in url.lower():
                continue
        images.append({"url": url, "alt_text": alt})

    # Also match plain image links like [caption](url) where URL ends in image extension
    for m in re.finditer(r'(?<!!)\[([^\]]+)\]\((https?://[^)]+\.(?:png|jpg|jpeg|gif|webp)[^)]*)\)', text):
        url = m.group(2).strip()
        if is_skip_url(url):
            continue
        alt = m.group(1).strip()
        # Avoid duplicates
        if not any(img["url"] == url for img in images):
            images.append({"url": url, "alt_text": alt})

    return images


def extract_post_content(raw_content, post_id):
    """Extract post text content, author, and images from a Tavily-fetched SB page."""
    text = raw_content

    # Find the post by its ID
    if post_id:
        pid_marker = f"post-{post_id})"
        pid_idx = text.find(pid_marker)
        if pid_idx >= 0:
            text = text[pid_idx + len(pid_marker):]

        # Cut at next post boundary
        lines = text.split("\n")
        cut_at = len(lines)
        seen_content = False
        for j, line in enumerate(lines):
            stripped = line.strip()
            if not seen_content:
                if stripped and not stripped.startswith("*") and not stripped.startswith("#"):
                    seen_content = True
                continue
            # Post footer: like count
            if re.match(r'\*\s+\[\d+\]\(.*"Like"\)', stripped):
                cut_at = j
                break
            # Next post's number line
            if re.match(r'\*\s+\[#[\d,]+\]', stripped):
                other_pid = re.search(r'#post-(\d+)', stripped)
                if other_pid and other_pid.group(1) != str(post_id):
                    while cut_at > 0 and j > 0:
                        j -= 1
                        prev = lines[j].strip()
                        if prev.startswith("#### [") or prev.startswith("[![Image"):
                            break
                    cut_at = j
                    break
            # Author header for new post
            if stripped.startswith("#### [") and j + 5 < len(lines):
                lookahead = "\n".join(lines[j:j+6])
                other_pid = re.search(r'#post-(\d+)', lookahead)
                if other_pid and other_pid.group(1) != str(post_id):
                    cut_at = j
                    if cut_at > 0 and lines[cut_at - 1].strip().startswith("[![Image"):
                        cut_at -= 1
                    break
        text = "\n".join(lines[:cut_at])

    # Extract author from the header area before our post
    # Look backwards in the original content for "#### [username](url)"
    author = "Unknown"
    if post_id:
        pre_text = raw_content[:raw_content.find(f"post-{post_id})") + 200] if post_id else ""
        # Find the last author header before our post
        author_matches = list(re.finditer(
            r'####\s+\[([^\]]+)\]\(https://forums\.spacebattles\.com/members/',
            pre_text
        ))
        if author_matches:
            author = author_matches[-1].group(1).strip()

    # Extract images
    images = extract_images_from_content(text)

    # Clean up text for context
    # Remove markdown image syntax to get just the text content
    context = re.sub(r'!\[[^\]]*\]\([^)]+\)', '', text)
    context = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', context)
    # Remove boilerplate lines
    context_lines = []
    for line in context.split("\n"):
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("*   ["):
            continue
        if stripped.startswith("[!["):
            continue
        if stripped.startswith("####"):
            continue
        context_lines.append(stripped)
    context = " ".join(context_lines).strip()
    # Truncate to reasonable length
    if len(context) > 500:
        context = context[:497] + "..."

    return {
        "author": author,
        "images": images,
        "context": context,
    }


# ── Image downloading ─────────────────────────────────────────────────────

def guess_extension(url, content_type=""):
    """Guess file extension from URL or content-type."""
    # Try URL first
    path = url.split("?")[0].split("#")[0]
    ext_m = re.search(r'\.(png|jpg|jpeg|gif|webp|svg)$', path, re.IGNORECASE)
    if ext_m:
        ext = ext_m.group(1).lower()
        return "jpg" if ext == "jpeg" else ext

    # Try content-type
    ct_map = {
        "image/png": "png",
        "image/jpeg": "jpg",
        "image/gif": "gif",
        "image/webp": "webp",
        "image/svg+xml": "svg",
    }
    for ct, ext in ct_map.items():
        if ct in content_type:
            return ext

    return "jpg"  # default


def download_image(url, filepath):
    """Download an image from a URL to a local file."""
    try:
        req = urllib.request.Request(url, headers={
            "User-Agent": "Mozilla/5.0 (compatible; GhostInTheCityWiki/1.0)",
        })
        with urllib.request.urlopen(req, timeout=30) as resp:
            content_type = resp.headers.get("Content-Type", "")
            data = resp.read()
            if len(data) < 100:
                return False
            with open(filepath, "wb") as f:
                f.write(data)
            return True
    except Exception as e:
        print(f"    Download failed: {e}")
        return False


# ── Main download logic ───────────────────────────────────────────────────

def download_media(index, start_num=1, end_num=None, redownload=False):
    """Download media posts and their images."""
    os.makedirs(IMAGE_DIR, exist_ok=True)

    total = len(index)
    success = 0
    skipped = 0
    failed = []
    total_images = 0

    for entry in index[start_num - 1:]:
        i = entry["index"]
        if end_num and i > end_num:
            break

        title = entry["title"]
        sb_url = entry.get("sb_url", "")
        post_id = entry.get("post_id", "")

        # Check if we already have images for this post
        if not redownload:
            existing = [f for f in os.listdir(IMAGE_DIR)
                        if f.startswith(f"{post_id}_")] if post_id and os.path.exists(IMAGE_DIR) else []
            if existing:
                skipped += 1
                continue

        if not sb_url:
            print(f"[{i}/{total}] SKIP (no URL): {title}")
            failed.append(i)
            continue

        print(f"[{i}/{total}] {title}")
        time.sleep(DELAY)

        results = tavily_extract(sb_url)
        if not results:
            print(f"  FAILED to fetch")
            failed.append(i)
            continue

        extracted = extract_post_content(results[0]["raw_content"], post_id)

        # Update entry with extracted data
        entry["artist"] = extracted["author"]
        entry["context"] = extracted["context"]
        entry["images"] = []

        if not extracted["images"]:
            print(f"  No images found in post")
            # Still save the entry with empty images
            continue

        for img_idx, img in enumerate(extracted["images"], 1):
            url = img["url"]
            ext = guess_extension(url)
            filename = f"{post_id}_{img_idx}.{ext}"
            filepath = os.path.join(IMAGE_DIR, filename)

            if os.path.exists(filepath) and not redownload:
                entry["images"].append({
                    "url": url,
                    "local_file": filename,
                    "alt_text": img["alt_text"],
                })
                continue

            ok = download_image(url, filepath)
            if ok:
                entry["images"].append({
                    "url": url,
                    "local_file": filename,
                    "alt_text": img["alt_text"],
                })
                total_images += 1
                print(f"  Downloaded: {filename}")
            else:
                print(f"  FAILED: {url[:80]}...")

        success += 1

    # Save updated index with image metadata
    with open(INDEX_PATH, "w", encoding="utf-8") as f:
        json.dump(index, f, indent=2, ensure_ascii=False)
    print(f"  Updated index at {INDEX_PATH}")

    print(f"\nDone! {success} posts processed, {skipped} skipped, {total_images} images downloaded.")
    if failed:
        print(f"Failed entries ({len(failed)}): {failed}")


# ── Utility ───────────────────────────────────────────────────────────────

def sanitize_filename(s):
    s = re.sub(r'[^\w\s\-\.]', '', s)
    s = re.sub(r'\s+', '_', s.strip())
    return s[:80]


# ── Commands ──────────────────────────────────────────────────────────────

def cmd_build_index():
    entries = fetch_threadmark_index()
    with open(INDEX_PATH, "w", encoding="utf-8") as f:
        json.dump(entries, f, indent=2, ensure_ascii=False)
    print(f"  Saved index to {INDEX_PATH}")
    return entries


def cmd_status():
    if not os.path.exists(INDEX_PATH):
        print("No index file found. Run without --status first to build it.")
        return

    with open(INDEX_PATH, encoding="utf-8") as f:
        index = json.load(f)

    downloaded = 0
    total_images = 0
    if os.path.exists(IMAGE_DIR):
        for fname in os.listdir(IMAGE_DIR):
            if not fname.startswith("."):
                total_images += 1
        # Count unique post_ids
        post_ids = set()
        for fname in os.listdir(IMAGE_DIR):
            parts = fname.split("_", 1)
            if parts:
                post_ids.add(parts[0])
        downloaded = len(post_ids)

    with_images = sum(1 for e in index if e.get("images"))

    print("=" * 60)
    print("  GHOST IN THE CITY — MEDIA STATUS")
    print("=" * 60)
    print(f"  Media posts in index:   {len(index)}")
    print(f"  Posts with image data:  {with_images}")
    print(f"  Images downloaded:      {total_images}")
    print(f"  Unique posts downloaded:{downloaded}")
    print("=" * 60)


def cmd_download(start_num=1, end_num=None, redownload=False):
    if os.path.exists(INDEX_PATH):
        with open(INDEX_PATH, encoding="utf-8") as f:
            index = json.load(f)
        print(f"Loaded index with {len(index)} media entries.")
    else:
        index = cmd_build_index()

    with_urls = sum(1 for e in index if e.get("sb_url"))
    print(f"  {with_urls}/{len(index)} entries have direct URLs")

    download_media(index, start_num, end_num, redownload)


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
