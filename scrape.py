#!/usr/bin/env python3
"""
Scraper for Ghost in the City by Seras.
Downloads chapters from AO3 and converts them to markdown.
Uses only Python stdlib. Source: https://archiveofourown.org/works/42385683

Usage:
  python3 scrape.py                   # download all chapters (skips existing)
  python3 scrape.py --update          # check AO3 for new chapters, download them
  python3 scrape.py --from N          # start from chapter N
  python3 scrape.py --from N --to M   # download chapters N to M
  python3 scrape.py --redownload      # force re-download of all chapters
"""

import urllib.request
import urllib.error
import urllib.parse
import html.parser
import re
import os
import time
import json
import sys

AO3_BASE = "https://archiveofourown.org"
WORK_ID = "42385683"
NAVIGATE_URL = f"{AO3_BASE}/works/{WORK_ID}/navigate"
OUTPUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "chapters")
INDEX_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "threadmarks_index.json")

HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64; rv:120.0) Gecko/20100101 Firefox/120.0",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
}

DELAY = 3.0  # seconds between requests (be polite to AO3)


def fetch(url, retries=3):
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers=HEADERS)
            with urllib.request.urlopen(req, timeout=30) as resp:
                return resp.read().decode("utf-8", errors="replace")
        except urllib.error.HTTPError as e:
            if e.code == 429:
                wait = 60 * (attempt + 1)
                print(f"  Rate limited (429), waiting {wait}s...")
                time.sleep(wait)
            elif e.code == 503:
                wait = 30 * (attempt + 1)
                print(f"  Service unavailable (503), waiting {wait}s...")
                time.sleep(wait)
            else:
                print(f"  HTTP {e.code} for {url}, attempt {attempt+1}")
                time.sleep(10)
        except Exception as e:
            print(f"  Error: {e}, attempt {attempt+1}")
            time.sleep(10)
    return None


# ---------------------------------------------------------------------------
# HTML -> Markdown converter (stdlib html.parser)
# ---------------------------------------------------------------------------

class MarkdownConverter(html.parser.HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.out = []
        self._stack = []
        self._skip = 0
        self._list_stack = []   # stack of ('ul'|'ol', count)
        self._in_blockquote = False
        self._link_text = None
        self._link_href = None

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)

        if self._skip > 0:
            self._skip += 1
            self._stack.append(tag)
            return

        if tag in ("script", "style"):
            self._skip = 1
            self._stack.append(tag)
            return

        self._stack.append(tag)

        if tag in ("b", "strong"):
            self.out.append("**")
        elif tag in ("i", "em"):
            self.out.append("*")
        elif tag in ("u",):
            self.out.append("__")
        elif tag in ("s", "del", "strike"):
            self.out.append("~~")
        elif tag == "br":
            self.out.append("  \n")
        elif tag == "hr":
            self.out.append("\n\n---\n\n")
        elif tag == "p":
            self.out.append("\n\n")
        elif tag in ("h1", "h2", "h3", "h4", "h5", "h6"):
            self.out.append("\n\n" + "#" * int(tag[1]) + " ")
        elif tag == "blockquote":
            self._in_blockquote = True
            self.out.append("\n\n> ")
        elif tag == "ul":
            self._list_stack.append(("ul", 0))
            self.out.append("\n")
        elif tag == "ol":
            self._list_stack.append(("ol", 0))
            self.out.append("\n")
        elif tag == "li":
            if self._list_stack:
                kind, count = self._list_stack[-1]
                if kind == "ol":
                    self._list_stack[-1] = (kind, count + 1)
                    self.out.append(f"\n{count + 1}. ")
                else:
                    self.out.append("\n- ")
            else:
                self.out.append("\n- ")
        elif tag == "a":
            self._link_href = attrs.get("href", "")
            self.out.append("\x00LINK_START\x00")
        elif tag in ("center", "div"):
            # AO3 uses <div> for chapter sections
            pass
        elif tag == "sup":
            self.out.append("^")
        elif tag == "sub":
            self.out.append("~")

    def handle_endtag(self, tag):
        if self._skip > 0:
            self._skip -= 1
            self._stack.pop() if self._stack else None
            return

        self._stack.pop() if self._stack else None

        if tag in ("b", "strong"):
            self.out.append("**")
        elif tag in ("i", "em"):
            self.out.append("*")
        elif tag in ("u",):
            self.out.append("__")
        elif tag in ("s", "del", "strike"):
            self.out.append("~~")
        elif tag == "p":
            self.out.append("\n\n")
        elif tag in ("h1", "h2", "h3", "h4", "h5", "h6"):
            self.out.append("\n\n")
        elif tag == "blockquote":
            self._in_blockquote = False
            self.out.append("\n\n")
        elif tag in ("ul", "ol"):
            if self._list_stack:
                self._list_stack.pop()
            self.out.append("\n")
        elif tag == "a":
            href = self._link_href or ""
            # Collect text since LINK_START
            full = "".join(self.out)
            link_start = full.rfind("\x00LINK_START\x00")
            if link_start >= 0:
                link_text = full[link_start + len("\x00LINK_START\x00"):]
                self.out = list(full[:link_start])
                link_text = link_text.strip()
                if href and link_text:
                    self.out.append(f"[{link_text}]({href})")
                elif link_text:
                    self.out.append(link_text)
            self._link_href = None

    def handle_data(self, data):
        if self._skip > 0:
            return
        if self._in_blockquote:
            data = data.replace("\n", "\n> ")
        self.out.append(data)

    def get_markdown(self):
        text = "".join(self.out)
        # Remove link sentinel if unclosed
        text = text.replace("\x00LINK_START\x00", "")
        # Normalize whitespace
        text = re.sub(r'[ \t]+\n', '\n', text)
        text = re.sub(r'\n{4,}', '\n\n\n', text)
        text = text.strip()
        return text


def html_to_markdown(html_content):
    conv = MarkdownConverter()
    try:
        conv.feed(html_content)
        return conv.get_markdown()
    except Exception as e:
        print(f"  Warning: converter error: {e}")
        return re.sub(r'<[^>]+>', '', html_content).strip()


# ---------------------------------------------------------------------------
# AO3 parsing
# ---------------------------------------------------------------------------

def extract_chapter_content(html_content):
    """Extract chapter text from an AO3 chapter page."""
    # AO3 chapter content is in div class="userstuff module" or "userstuff"
    # Landmark heading "Chapter Text" precedes the actual content

    # First try: userstuff module (post-chapter-header)
    m = re.search(
        r'<div[^>]+class="[^"]*userstuff[^"]*"[^>]*>(.*?)</div>\s*</div>\s*(?:<div|</article)',
        html_content, re.DOTALL | re.IGNORECASE
    )
    if m:
        content = m.group(1)
        # Remove the landmark heading
        content = re.sub(r'<h3[^>]+class="[^"]*landmark[^"]*"[^>]*>.*?</h3>', '', content, flags=re.DOTALL)
        return content

    # Second try: broader userstuff match
    m = re.search(
        r'id="chapters".*?<div[^>]+class="[^"]*userstuff[^"]*"[^>]*>(.*?)</div>\s*</div>',
        html_content, re.DOTALL | re.IGNORECASE
    )
    if m:
        content = m.group(1)
        content = re.sub(r'<h3[^>]+class="[^"]*landmark[^"]*"[^>]*>.*?</h3>', '', content, flags=re.DOTALL)
        return content

    return None


def extract_chapter_title(html_content):
    """Extract chapter title from AO3 page."""
    # h3.title > a
    m = re.search(r'<h3[^>]+class="[^"]*title[^"]*"[^>]*>.*?<a[^>]*>([^<]+)</a>', html_content, re.DOTALL)
    if m:
        return m.group(1).strip()
    # Fallback: look for chapter title heading
    m = re.search(r'<h2[^>]+class="[^"]*heading[^"]*"[^>]*>.*?Chapter\s+\d+[^<]*</[^>]+>', html_content, re.DOTALL)
    if m:
        return re.sub(r'<[^>]+>', '', m.group(0)).strip()
    return None


def extract_author_notes(html_content, position="before"):
    """Extract author's notes (beginning or end) from AO3."""
    # AO3 has notes in div#notes (beginning) and div#end_notes
    div_id = "notes" if position == "before" else "end_notes"
    pattern = re.compile(
        r'<div[^>]+id="' + div_id + r'"[^>]*>.*?<blockquote[^>]*>(.*?)</blockquote>',
        re.DOTALL | re.IGNORECASE
    )
    m = pattern.search(html_content)
    if m:
        return m.group(1)
    return None


def fetch_index_from_ao3():
    """Fetch the current chapter list from AO3 navigate page."""
    print("Fetching chapter index from AO3...")
    content = fetch(NAVIGATE_URL)
    if not content:
        print("ERROR: Could not fetch navigate page")
        sys.exit(1)

    items = re.findall(
        r'<li[^>]*>\s*<a href="/works/' + WORK_ID + r'/chapters/(\d+)"[^>]*>\s*([^<]+)</a>'
        r'.*?<span[^>]*class="[^"]*datetime[^"]*"[^>]*>\(([^)]+)\)</span>',
        content, re.DOTALL
    )
    return [
        {
            "chapter_id": cid,
            "title": title.strip(),
            "date": date.strip(),
            "ao3_url": f"{AO3_BASE}/works/{WORK_ID}/chapters/{cid}",
            "sb_url": None
        }
        for cid, title, date in items
    ]


def get_chapter_index():
    """Load or build chapter index."""
    if os.path.exists(INDEX_PATH):
        with open(INDEX_PATH) as f:
            return json.load(f)

    index = fetch_index_from_ao3()
    with open(INDEX_PATH, "w") as f:
        json.dump(index, f, indent=2)
    print(f"  Saved index with {len(index)} chapters.")
    return index


def cmd_update():
    """Check AO3 for new chapters, download any that are missing."""
    existing = get_chapter_index()
    existing_ids = {ch["chapter_id"] for ch in existing}

    fresh = fetch_index_from_ao3()
    new_chapters = [ch for ch in fresh if ch["chapter_id"] not in existing_ids]

    if not new_chapters:
        print(f"No new chapters. Index has {len(existing)} chapters, AO3 has {len(fresh)}.")
        return

    print(f"Found {len(new_chapters)} new chapter(s):")
    for ch in new_chapters:
        print(f"  Ch.{fresh.index(ch) + 1}  {ch['title']}  ({ch['date']})")

    # Update the index file
    updated = existing + new_chapters
    with open(INDEX_PATH, "w") as f:
        json.dump(updated, f, indent=2)
    print(f"  Updated index: {len(existing)} → {len(updated)} chapters.")

    # Download new chapters
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    for ch in new_chapters:
        i = next(j + 1 for j, c in enumerate(updated) if c["chapter_id"] == ch["chapter_id"])
        title = ch["title"]
        ao3_url = ch["ao3_url"]
        filename = f"{i:04d}_{sanitize_filename(title)}.md"
        filepath = os.path.join(OUTPUT_DIR, filename)

        print(f"\nDownloading Ch.{i}: {title}")
        html_content = fetch(ao3_url)
        if not html_content:
            print("  FAILED — skipping")
            time.sleep(DELAY)
            continue

        chapter_html = extract_chapter_content(html_content)
        if not chapter_html:
            print("  WARNING: Could not extract content — skipping")
            time.sleep(DELAY)
            continue

        notes_before = extract_author_notes(html_content, "before")
        notes_after  = extract_author_notes(html_content, "after")
        chapter_md   = html_to_markdown(chapter_html)

        lines = [f"# {title}\n"]
        lines.append(f"*Source: {ao3_url}*")
        if ch.get("date"):
            lines.append(f"*Published: {ch['date']}*")
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
        print(f"  Saved: {filename} (~{len(chapter_md.split())} words)")
        time.sleep(DELAY)

    chapter_list = ", ".join(
        f"Ch.{next(j+1 for j,c in enumerate(updated) if c['chapter_id']==ch['chapter_id'])} ({ch['title']})"
        for ch in new_chapters
    )
    print("\nDone. Next steps:")
    print(f"  1. Ask Claude: \"can you process this?\" — it will summarise {chapter_list}")
    print("  2. Run: python3 wiki/scripts/build.py --all")


def sanitize_filename(s):
    s = re.sub(r'[^\w\s\-\.]', '', s)
    s = re.sub(r'\s+', '_', s.strip())
    return s[:80]


def main():
    if "--update" in sys.argv:
        cmd_update()
        return

    os.makedirs(OUTPUT_DIR, exist_ok=True)

    # Parse args
    redownload = "--redownload" in sys.argv
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

    index = get_chapter_index()
    total = len(index)
    print(f"Total chapters: {total}")
    print(f"Starting from chapter {start_num}")
    if end_num:
        print(f"Ending at chapter {end_num}")
    print()

    success = 0
    failed = []

    for i, chapter in enumerate(index[start_num - 1:], start=start_num):
        if end_num and i > end_num:
            break

        title = chapter["title"]
        ao3_url = chapter["ao3_url"]
        filename = f"{i:04d}_{sanitize_filename(title)}.md"
        filepath = os.path.join(OUTPUT_DIR, filename)

        if os.path.exists(filepath) and not redownload:
            size = os.path.getsize(filepath)
            if size > 500:  # skip if file looks valid
                print(f"[{i}/{total}] Skip (exists, {size} bytes): {title}")
                success += 1
                continue

        print(f"[{i}/{total}] {title}")
        print(f"  URL: {ao3_url}")

        html_content = fetch(ao3_url)
        if not html_content:
            print(f"  FAILED")
            failed.append(i)
            time.sleep(DELAY)
            continue

        # Extract content
        chapter_html = extract_chapter_content(html_content)
        if not chapter_html:
            print(f"  WARNING: Could not extract chapter content")
            failed.append(i)
            time.sleep(DELAY)
            continue

        # Extract notes
        notes_before = extract_author_notes(html_content, "before")
        notes_after = extract_author_notes(html_content, "after")

        # Convert to markdown
        chapter_md = html_to_markdown(chapter_html)
        notes_before_md = html_to_markdown(notes_before) if notes_before else None
        notes_after_md = html_to_markdown(notes_after) if notes_after else None

        # Build the output
        lines = [f"# {title}\n"]
        lines.append(f"*Source: {ao3_url}*")
        if chapter.get("date"):
            lines.append(f"*Published: {chapter['date']}*")
        if chapter.get("sb_url"):
            lines.append(f"*SpaceBattles: {chapter['sb_url']}*")
        lines.append("\n---\n")

        if notes_before_md:
            lines.append("**Author's Note:**\n")
            lines.append(f"> {notes_before_md}\n")
            lines.append("---\n")

        lines.append(chapter_md)

        if notes_after_md:
            lines.append("\n\n---\n")
            lines.append("**Author's End Note:**\n")
            lines.append(f"> {notes_after_md}")

        with open(filepath, "w", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")

        word_count = len(chapter_md.split())
        print(f"  Saved: {filename} (~{word_count} words)")
        success += 1

        time.sleep(DELAY)

    print(f"\nDone! {success}/{total} chapters saved.")
    if failed:
        print(f"Failed chapters: {failed}")
        print("Re-run with --from N to retry from a specific chapter.")
    print(f"Output directory: {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
