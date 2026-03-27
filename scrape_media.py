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
  python3 scrape_media.py --retry-empty        # re-fetch only posts with no images found
  python3 scrape_media.py --show-manual        # list images needing manual browser download
  python3 scrape_media.py --grab-sb            # download SB attachments via gallery-dl + cookies
  python3 scrape_media.py --status             # show index stats

SB attachment downloads require gallery-dl with browser cookies:
  1. Install: pip install gallery-dl (or use the venv at ~/.local/gallery-dl-venv/)
  2. Export cookies from a browser where you're logged into SpaceBattles:
     - Install a "cookies.txt" browser extension
     - Export cookies for forums.spacebattles.com to cookies-sb.txt
  3. Run: python3 scrape_media.py --grab-sb --cookies cookies-sb.txt
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
COOKIES_PATH = os.path.join(BASE_DIR, "cookies-sb.txt")

# gallery-dl binary — check venv first, fall back to system
GALLERY_DL = os.path.expanduser("~/.local/gallery-dl-venv/bin/gallery-dl")
if not os.path.exists(GALLERY_DL):
    GALLERY_DL = "gallery-dl"  # hope it's on PATH

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


def _is_image_url(url):
    """Check if a URL points to an image (by extension or known image host)."""
    path = url.split("?")[0].split("#")[0].lower()
    if re.search(r'\.(png|jpg|jpeg|gif|webp|svg)$', path):
        return True
    # Known image hosts where URLs may lack extensions
    if re.match(r'https?://i\.imgur\.com/', url):
        return True
    return False


def _add_image(images, url, alt_text=""):
    """Add an image to the list if it's not a duplicate or skip URL."""
    url = url.strip()
    if is_skip_url(url):
        return
    # Skip SB member profile links
    if re.search(r'forums\.spacebattles\.com/members/', url):
        return
    # Skip if alt text suggests it's an avatar
    if alt_text and re.match(r'^Image \d+: \w+$', alt_text):
        if 'avatar' in url.lower():
            return
    # Avoid duplicates
    if not any(img["url"] == url for img in images):
        images.append({"url": url, "alt_text": alt_text})


def extract_images_from_content(text):
    """Extract image URLs from markdown content. Returns list of {url, alt_text}."""
    images = []

    # 1. Match ![alt](url) patterns (including empty alt text)
    for m in re.finditer(r'!\[([^\]]*)\]\((https?://[^)]+)\)', text):
        _add_image(images, m.group(2), m.group(1).strip())

    # 2. Match [caption](url) where URL ends in image extension (including empty caption)
    for m in re.finditer(r'(?<!!)\[([^\]]*)\]\((https?://[^)]+\.(?:png|jpg|jpeg|gif|webp)[^)]*)\)', text):
        _add_image(images, m.group(2), m.group(1).strip())

    # 3. Match <img> tags that Tavily may pass through from HTML
    for m in re.finditer(r'<img[^>]+src=["\']([^"\']+)["\']', text):
        _add_image(images, m.group(1))

    # 4. Match bare image URLs on their own line or surrounded by whitespace
    for m in re.finditer(r'(?:^|\s)(https?://[^\s<>\[\]()]+\.(?:png|jpg|jpeg|gif|webp)(?:\?[^\s<>\[\]()]*)?)(?:\s|$)', text, re.MULTILINE):
        _add_image(images, m.group(1))

    # 5. Match bare imgur URLs without file extensions (imgur serves images without .ext)
    for m in re.finditer(r'(?:^|\s)(https?://i\.imgur\.com/\w+)(?:\s|$)', text, re.MULTILINE):
        _add_image(images, m.group(1))

    # 6. Match SB attachment URLs (extension is in the slug like "name-png.12345/")
    for m in re.finditer(r'(https?://forums\.spacebattles\.com/attachments/[^)\s]+)', text):
        url = m.group(1).rstrip("/")
        # Verify it looks like an image attachment (has -png, -jpg, etc. in slug)
        if re.search(r'-(?:png|jpg|jpeg|gif|webp)\.\d+$', url):
            _add_image(images, url + "/")

    # 7. Match [](url) empty-bracket links to any URL (catches remaining cases)
    for m in re.finditer(r'(?<!!)\[\]\((https?://[^)]+)\)', text):
        url = m.group(1).strip()
        # Only add if it looks like it could be an image (not a member profile, etc.)
        if _is_image_url(url) or 'attachments/' in url:
            _add_image(images, url)

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
    # Remove "Click to expand/shrink" artifacts
    context = re.sub(r'\[Click to expand\.\.\.\]\([^)]*\)', '', context)
    context = re.sub(r'\[Click to shrink\.\.\.\]\([^)]*\)', '', context)
    context = re.sub(r'Click to expand\.\.\.', '', context)
    context = re.sub(r'Click to shrink\.\.\.', '', context)
    # Remove boilerplate lines
    context_lines = []
    for line in context.split("\n"):
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("*   [") or stripped.startswith("*   #"):
            continue
        if stripped.startswith("[!["):
            continue
        if stripped.startswith("####"):
            continue
        # Skip quote marker lines (bare > or lines that are only > characters)
        if re.match(r'^>+\s*$', stripped):
            continue
        # Strip leading quote markers from content lines
        stripped = re.sub(r'^(?:>\s*)+', '', stripped).strip()
        if not stripped:
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
    path = url.split("?")[0].split("#")[0].rstrip("/")
    ext_m = re.search(r'\.(png|jpg|jpeg|gif|webp|svg)$', path, re.IGNORECASE)
    if ext_m:
        ext = ext_m.group(1).lower()
        return "jpg" if ext == "jpeg" else ext

    # SB attachments: extension is in slug like "name-png.12345"
    sb_ext = re.search(r'-(png|jpg|jpeg|gif|webp)\.\d+$', path, re.IGNORECASE)
    if sb_ext:
        ext = sb_ext.group(1).lower()
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
    # SpaceBattles attachments are behind Cloudflare — can't download directly
    if "forums.spacebattles.com/attachments/" in url:
        print(f"    SB attachment (Cloudflare-blocked) — needs manual download")
        return "manual"

    # Discord CDN URLs expire and return 404
    if re.search(r'(cdn|media)\.discord(app)?\.com/', url):
        print(f"    Discord CDN URL (expired) — skipping")
        return False

    try:
        req = urllib.request.Request(url, headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        })
        with urllib.request.urlopen(req, timeout=30) as resp:
            content_type = resp.headers.get("Content-Type", "")
            data = resp.read()
            if len(data) < 100:
                return False
            with open(filepath, "wb") as f:
                f.write(data)
            return True
    except urllib.error.HTTPError as e:
        if e.code == 403:
            print(f"    403 Forbidden (Cloudflare?) — {url[:60]}...")
        elif e.code == 404:
            print(f"    404 Not Found (deleted/expired?) — {url[:60]}...")
        else:
            print(f"    HTTP {e.code}: {url[:60]}...")
        return False
    except Exception as e:
        print(f"    Download failed: {e}")
        return False


# ── Main download logic ───────────────────────────────────────────────────

def download_media(index, start_num=1, end_num=None, redownload=False, retry_empty=False):
    """Download media posts and their images."""
    os.makedirs(IMAGE_DIR, exist_ok=True)

    total = len(index)
    success = 0
    skipped = 0
    failed = []
    total_images = 0
    manual_needed = []  # (entry_index, title, url, filename) tuples

    for entry in index[start_num - 1:]:
        i = entry["index"]
        if end_num and i > end_num:
            break

        title = entry["title"]
        sb_url = entry.get("sb_url", "")
        post_id = entry.get("post_id", "")

        # --retry-empty: only process entries that have no images
        if retry_empty:
            if entry.get("images"):
                skipped += 1
                continue
            # Also skip if we already have downloaded files for this post
            existing = [f for f in os.listdir(IMAGE_DIR)
                        if f.startswith(f"{post_id}_")] if post_id and os.path.exists(IMAGE_DIR) else []
            if existing:
                skipped += 1
                continue
        # Normal mode: skip if we already have images downloaded
        elif not redownload:
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

        # Fallback: if no images found, try the direct post permalink URL.
        # SpaceBattles renders spoilered content expanded on permalink pages.
        if not extracted["images"] and post_id:
            permalink = f"https://forums.spacebattles.com/posts/{post_id}/"
            print(f"  No images on page view, trying permalink...")
            time.sleep(DELAY)
            perm_results = tavily_extract(permalink)
            if perm_results:
                perm_extracted = extract_post_content(perm_results[0]["raw_content"], post_id)
                if perm_extracted["images"]:
                    extracted = perm_extracted
                    print(f"  Found {len(extracted['images'])} image(s) via permalink")

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
            if ok is True:
                entry["images"].append({
                    "url": url,
                    "local_file": filename,
                    "alt_text": img["alt_text"],
                })
                total_images += 1
                print(f"  Downloaded: {filename}")
            elif ok == "manual":
                # Record in index (without local_file) so we don't lose the URL
                entry["images"].append({
                    "url": url,
                    "local_file": None,
                    "alt_text": img["alt_text"],
                })
                manual_needed.append((i, title, url, filename))
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
    if manual_needed:
        print(f"\n{'='*60}")
        print(f"  {len(manual_needed)} image(s) need manual download")
        print(f"  (Cloudflare-blocked SB attachments / expired Discord URLs)")
        print(f"  Open each URL in a browser, save to wiki/build/media/")
        print(f"{'='*60}")
        for idx, title, url, filename in manual_needed:
            print(f"  [{idx}] {title}")
            print(f"       URL:  {url}")
            print(f"       Save: wiki/build/media/{filename}")
            print()


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


def cmd_show_manual():
    """Show images that need manual download (SB attachments, expired Discord)."""
    if not os.path.exists(INDEX_PATH):
        print("No index file found. Run without --status first to build it.")
        return

    with open(INDEX_PATH, encoding="utf-8") as f:
        index = json.load(f)

    manual = []
    for entry in index:
        post_id = entry.get("post_id", "")
        for img_idx, img in enumerate(entry.get("images", []), 1):
            url = img.get("url", "")
            local = img.get("local_file")
            if not local:
                ext = guess_extension(url)
                filename = f"{post_id}_{img_idx}.{ext}"
                # Check if manually downloaded already
                filepath = os.path.join(IMAGE_DIR, filename)
                if os.path.exists(filepath):
                    continue
                manual.append((entry["index"], entry["title"], url, filename, entry.get("sb_url", "")))

        # Also check entries with no images at all
        if not entry.get("images"):
            manual.append((entry["index"], entry["title"], "", "", entry.get("sb_url", "")))

    if not manual:
        print("All images are downloaded! Nothing needs manual action.")
        return

    print(f"{'='*60}")
    print(f"  {len(manual)} image(s) need attention")
    print(f"{'='*60}")
    for idx, title, url, filename, sb_url in manual:
        print(f"  [{idx}] {title}")
        if url:
            print(f"       URL:  {url}")
            print(f"       Save: wiki/build/media/{filename}")
        else:
            print(f"       Post: {sb_url}")
            print(f"       (no images extracted — may need manual check)")
        print()


def download_sb_attachment_gdl(url, filepath, cookies_path):
    """Download a SpaceBattles attachment using gallery-dl with cookies."""
    import subprocess
    import tempfile

    # gallery-dl config to register SB as a xenforo site
    config = {
        "extractor": {
            "xenforo": {
                "forums.spacebattles.com": {
                    "root": "https://forums.spacebattles.com"
                }
            }
        }
    }

    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump(config, f)
        config_path = f.name

    try:
        # gallery-dl can download XenForo attachments directly
        # Use -d to set output dir, -f to set filename format
        cmd = [
            GALLERY_DL,
            "--config", config_path,
            "--cookies", cookies_path,
            "--directory", os.path.dirname(filepath),
            "--filename", os.path.basename(filepath),
            "--no-mtime",
            url,
        ]
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=60,
        )
        if result.returncode == 0 and os.path.exists(filepath):
            return True
        # gallery-dl might not support bare attachment URLs —
        # in that case, try using requests from its venv with cookies
        return download_sb_with_cookies(url, filepath, cookies_path)
    except FileNotFoundError:
        print(f"    gallery-dl not found at {GALLERY_DL}")
        return False
    except Exception as e:
        print(f"    gallery-dl error: {e}")
        return False
    finally:
        os.unlink(config_path)


def download_sb_with_cookies(url, filepath, cookies_path):
    """Download an SB attachment using cookies from a Netscape cookie file."""
    # Parse Netscape cookie file for SB cookies
    cookies = {}
    try:
        with open(cookies_path) as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                parts = line.split("\t")
                if len(parts) >= 7 and "spacebattles" in parts[0]:
                    cookies[parts[5]] = parts[6]
    except FileNotFoundError:
        print(f"    Cookie file not found: {cookies_path}")
        return False

    if not cookies:
        print(f"    No SpaceBattles cookies found in {cookies_path}")
        return False

    cookie_header = "; ".join(f"{k}={v}" for k, v in cookies.items())
    try:
        req = urllib.request.Request(url, headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Cookie": cookie_header,
            "Referer": "https://forums.spacebattles.com/",
        })
        with urllib.request.urlopen(req, timeout=30) as resp:
            ct = resp.headers.get("Content-Type", "")
            data = resp.read()
            if len(data) < 100:
                return False
            if "text/html" in ct:
                # Got a login page, not an image — cookies may be expired
                print(f"    Got HTML instead of image — cookies may be expired")
                return False
            with open(filepath, "wb") as f:
                f.write(data)
            return True
    except urllib.error.HTTPError as e:
        print(f"    HTTP {e.code} even with cookies — {url[:60]}...")
        return False
    except Exception as e:
        print(f"    Download with cookies failed: {e}")
        return False


def cmd_grab_sb(cookies_path=None):
    """Download SB attachment images using gallery-dl + cookies."""
    if not cookies_path:
        cookies_path = COOKIES_PATH

    if not os.path.exists(cookies_path):
        print(f"Cookie file not found: {cookies_path}")
        print(f"Export your SpaceBattles cookies to this file using a browser extension.")
        print(f"  Recommended: 'cookies.txt' extension for Chrome/Firefox")
        print(f"  Save as: {cookies_path}")
        return

    if not os.path.exists(INDEX_PATH):
        print("No index file found. Run the scraper first to build it.")
        return

    with open(INDEX_PATH, encoding="utf-8") as f:
        index = json.load(f)

    os.makedirs(IMAGE_DIR, exist_ok=True)

    # Find SB attachment images that need downloading
    sb_images = []
    for entry in index:
        post_id = entry.get("post_id", "")
        for img_idx, img in enumerate(entry.get("images", []), 1):
            url = img.get("url", "")
            if "forums.spacebattles.com/attachments/" not in url:
                continue
            local = img.get("local_file")
            ext = guess_extension(url)
            filename = f"{post_id}_{img_idx}.{ext}"
            filepath = os.path.join(IMAGE_DIR, filename)
            # Skip if already downloaded (check by filename or local_file)
            if local and os.path.exists(os.path.join(IMAGE_DIR, local)):
                continue
            if os.path.exists(filepath):
                continue
            sb_images.append((entry, img_idx, img, url, filename, filepath))

    if not sb_images:
        print("No SB attachments need downloading.")
        return

    print(f"Found {len(sb_images)} SB attachment(s) to download")
    success = 0
    failed = 0

    for entry, img_idx, img, url, filename, filepath in sb_images:
        title = entry.get("title", "")
        print(f"  [{entry['index']}] {title} — {filename}")

        ok = download_sb_with_cookies(url, filepath, cookies_path)
        if ok:
            img["local_file"] = filename
            success += 1
            print(f"    OK: {filename}")
        else:
            failed += 1

    # Save updated index
    with open(INDEX_PATH, "w", encoding="utf-8") as f:
        json.dump(index, f, indent=2, ensure_ascii=False)

    print(f"\nDone! {success} downloaded, {failed} failed.")
    if failed:
        print("Failed downloads may have expired cookies. Re-export and try again.")


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
    manual = sum(1 for e in index for img in e.get("images", []) if not img.get("local_file"))
    empty = sum(1 for e in index if not e.get("images"))

    print("=" * 60)
    print("  GHOST IN THE CITY — MEDIA STATUS")
    print("=" * 60)
    print(f"  Media posts in index:   {len(index)}")
    print(f"  Posts with image data:  {with_images}")
    print(f"  Posts with no images:   {empty}")
    print(f"  Images downloaded:      {total_images}")
    print(f"  Unique posts downloaded:{downloaded}")
    if manual:
        print(f"  Need manual download:   {manual}")
    print("=" * 60)
    if manual or empty:
        print("  Run --show-manual for details")


def cmd_download(start_num=1, end_num=None, redownload=False, retry_empty=False):
    if os.path.exists(INDEX_PATH):
        with open(INDEX_PATH, encoding="utf-8") as f:
            index = json.load(f)
        print(f"Loaded index with {len(index)} media entries.")
    else:
        index = cmd_build_index()

    with_urls = sum(1 for e in index if e.get("sb_url"))
    print(f"  {with_urls}/{len(index)} entries have direct URLs")
    if retry_empty:
        empty = sum(1 for e in index if not e.get("images"))
        print(f"  {empty} entries have no images — retrying those")

    download_media(index, start_num, end_num, redownload, retry_empty)


# ── Entry point ───────────────────────────────────────────────────────────

def main():
    args = sys.argv[1:]

    if "--help" in args or "-h" in args:
        print(__doc__)
        return

    if "--status" in args:
        cmd_status()
        return

    if "--show-manual" in args:
        cmd_show_manual()
        return

    if "--grab-sb" in args:
        cookies = COOKIES_PATH
        if "--cookies" in args:
            ci = args.index("--cookies")
            if ci + 1 < len(args):
                cookies = args[ci + 1]
        cmd_grab_sb(cookies)
        return

    if "--index-only" in args:
        cmd_build_index()
        return

    redownload = "--redownload" in args
    retry_empty = "--retry-empty" in args

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

    cmd_download(start_num=start_num, end_num=end_num, redownload=redownload,
                 retry_empty=retry_empty)


if __name__ == "__main__":
    main()
