#!/usr/bin/env python3
"""
build_html.py — Renders all HTML pages from cache JSON.
Uses only Python stdlib. No external dependencies.
"""

import html
import json
import os
import sys

# ── Paths ──────────────────────────────────────────────────────────────────

WIKI_DIR    = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE_DIR   = os.path.join(WIKI_DIR, "cache")
BUILD_DIR   = os.path.join(WIKI_DIR, "build")
ASSETS_DIR  = os.path.join(BUILD_DIR, "assets")
CHARS_DIR   = os.path.join(BUILD_DIR, "characters")

SUMMARIES_JSON   = os.path.join(CACHE_DIR, "chapter_summaries.json")
BRAINDANCES_JSON = os.path.join(CACHE_DIR, "braindances.json")
CHARACTERS_JSON  = os.path.join(CACHE_DIR, "characters.json")

os.makedirs(BUILD_DIR, exist_ok=True)
os.makedirs(CHARS_DIR, exist_ok=True)


# ── Cache loading ──────────────────────────────────────────────────────────

def load_json(path, default):
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    return default


def load_summaries():
    return load_json(SUMMARIES_JSON, {})


def load_braindances():
    return load_json(BRAINDANCES_JSON, [])


def load_characters():
    return load_json(CHARACTERS_JSON, {})


# ── HTML helpers ───────────────────────────────────────────────────────────

def e(text):
    """HTML-escape a string."""
    return html.escape(str(text), quote=True)


CSS_PATH = "assets/style.css"  # relative — overridden per page depth

FONT_LINK = (
    '<link rel="preconnect" href="https://fonts.googleapis.com">'
    '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>'
    '<link href="https://fonts.googleapis.com/css2?family=Share+Tech+Mono'
    '&family=VT323&display=swap" rel="stylesheet">'
)


def page_shell(title, body, css_path="assets/style.css", active_nav=""):
    """Wrap body HTML in a full page shell."""
    nav_items = [
        ("index.html",              "Home"),
        ("chapters.html",           "Chapters"),
        ("braindances.html",        "Braindances"),
        ("characters/index.html",   "Characters"),
    ]

    def nav_href(target):
        # When css_path starts with '../', we're one level deep
        if css_path.startswith("../"):
            return f"../{target}"
        return target

    nav_links = "\n".join(
        f'<a href="{nav_href(href)}"'
        + (' class="active"' if active_nav == href else "")
        + f">{e(label)}</a>"
        for href, label in nav_items
    )

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{e(title)} — Ghost in the City Wiki</title>
  {FONT_LINK}
  <link rel="stylesheet" href="{css_path}">
</head>
<body>
  <div class="site-wrapper">
    <header class="site-header">
      <div class="site-title">
        <a href="{nav_href('index.html')}">&#x2588; Ghost in the City // Wiki</a>
      </div>
      <nav>
        {nav_links}
      </nav>
    </header>
    <main>
{body}
    </main>
    <footer class="site-footer">
      Fan wiki — unofficial. Story by Seras. &nbsp;|&nbsp;
      <a href="https://archiveofourown.org/works/42385683" rel="noopener">Read on AO3</a>
    </footer>
  </div>
</body>
</html>"""


# ── Kill count helper ──────────────────────────────────────────────────────

def total_kills(summaries):
    return sum(int(ch.get("kills", 0)) for ch in summaries.values())


# ── index.html ─────────────────────────────────────────────────────────────

def build_index(summaries, characters, braindances):
    kill_count    = total_kills(summaries)
    ch_total      = 240
    ch_summarized = sum(1 for ch in summaries.values() if ch.get("summary"))
    bd_count      = len(braindances)
    char_count    = len(characters)

    body = f"""
      <h1 class="page-title">Ghost in the City</h1>
      <p class="story-summary">
        A <em>Cyberpunk 2077 / Ghost in the Shell</em> crossover SI (Self-Insert) by
        <strong>Seras</strong>. A gamer wakes up in Night City as Motoko Kusanagi —
        without memories, without allies, and with a body that was purpose-built to be
        the best netrunner in the world. 240 chapters of corpo-politics, heists, street
        violence, and one woman clawing her way from coma patient to legend.
      </p>

      <div class="kill-counter-block">
        <span class="kill-counter-label">// confirmed kills</span>
        <span class="kill-counter-number">{e(str(kill_count))}</span>
      </div>

      <div class="stat-grid">
        <div class="stat-card">
          <span class="stat-label">Chapters</span>
          <span class="stat-value">{e(str(ch_total))}</span>
        </div>
        <div class="stat-card">
          <span class="stat-label">Summarised</span>
          <span class="stat-value">{e(str(ch_summarized))}/{e(str(ch_total))}</span>
        </div>
        <div class="stat-card">
          <span class="stat-label">Braindances</span>
          <span class="stat-value">{e(str(bd_count))}</span>
        </div>
        <div class="stat-card">
          <span class="stat-label">Characters</span>
          <span class="stat-value">{e(str(char_count))}</span>
        </div>
      </div>

      <h2>Navigation</h2>
      <ul>
        <li><a href="chapters.html">Chapter Summaries</a> — two-paragraph recaps for all 240 chapters</li>
        <li><a href="braindances.html">Braindance Catalog</a> — every BD Motoko produces or sells</li>
        <li><a href="characters/index.html">Character Profiles</a> — bios and stats</li>
      </ul>
"""
    out = page_shell("Home", body, active_nav="index.html")
    dest = os.path.join(BUILD_DIR, "index.html")
    with open(dest, "w", encoding="utf-8") as f:
        f.write(out)
    print(f"  Wrote {dest}")


# ── chapters.html ──────────────────────────────────────────────────────────

def build_chapters(summaries):
    # Load threadmarks for authoritative chapter order & metadata
    threadmarks_path = os.path.join(
        os.path.dirname(WIKI_DIR), "threadmarks_index.json"
    )
    if os.path.exists(threadmarks_path):
        with open(threadmarks_path, encoding="utf-8") as f:
            index = json.load(f)
    else:
        index = []

    items_html = []
    for i, chapter in enumerate(index, start=1):
        cid   = chapter["chapter_id"]
        title = chapter["title"]
        date  = chapter.get("date", "")
        url   = chapter.get("ao3_url", "")

        cached = summaries.get(cid, {})
        kills  = int(cached.get("kills", 0))

        if cached.get("summary"):
            paras = "".join(f"<p>{e(p)}</p>" for p in cached["summary"])
            kill_notes = cached.get("kill_notes", "")
            kill_note_html = (
                f'<p class="chapter-meta">&#x2620; {e(kill_notes)}</p>'
                if (kill_notes and kills > 0) else ""
            )
            body_html = (
                paras
                + kill_note_html
                + (f'<p class="chapter-meta">Date: {e(date)}'
                   + (f' &nbsp;|&nbsp; <a href="{e(url)}" rel="noopener">AO3 &#8599;</a>' if url else "")
                   + "</p>")
            )
        else:
            body_html = (
                '<p class="placeholder-note">[Summary pending]</p>'
                + (f'<p class="chapter-meta">Date: {e(date)}'
                   + (f' &nbsp;|&nbsp; <a href="{e(url)}" rel="noopener">AO3 &#8599;</a>' if url else "")
                   + "</p>")
            )

        kills_html = (
            f'<span class="ch-kills" data-kills="{kills}">☠ {kills}</span>'
            if kills > 0
            else f'<span class="ch-kills" data-kills="0"></span>'
        )

        items_html.append(f"""      <li>
        <details>
          <summary>
            <span class="ch-num">{e(str(i).zfill(3))}</span>
            <span class="ch-title">{e(title)}</span>
            {kills_html}
          </summary>
          <div class="chapter-summary-body">
            {body_html}
          </div>
        </details>
      </li>""")

    kill_count = total_kills(summaries)
    summarized = sum(1 for ch in summaries.values() if ch.get("summary"))

    body = f"""
      <h1 class="page-title">Chapter Summaries</h1>
      <p>
        {e(str(summarized))}/{e(str(len(index)))} chapters summarised.
        Running kill count: <span style="color:var(--accent-pink)">&#x2620; {e(str(kill_count))}</span>
      </p>
      <ul class="chapter-list">
{chr(10).join(items_html)}
      </ul>
"""
    out = page_shell("Chapters", body, active_nav="chapters.html")
    dest = os.path.join(BUILD_DIR, "chapters.html")
    with open(dest, "w", encoding="utf-8") as f:
        f.write(out)
    print(f"  Wrote {dest}")


# ── braindances.html ───────────────────────────────────────────────────────

def build_braindances(braindances):
    if not braindances:
        cards_html = '<p class="placeholder-note">[Braindance catalog pending — no entries in cache yet]</p>'
    else:
        cards = []
        for bd in braindances:
            bd_id       = bd.get("bd_id", "???")
            bd_title    = bd.get("title", "Untitled")
            chapter_num = bd.get("chapter_number", "?")
            description = bd.get("description", "")
            tags        = bd.get("content_tags", [])
            status      = bd.get("status", "Unknown").lower()

            tags_html = "".join(f'<span class="tag">{e(t)}</span>' for t in tags)
            chapter_link = f'<a href="chapters.html">Ch.{e(str(chapter_num))}</a>'

            cards.append(f"""    <div class="bd-card">
      <div class="bd-id">{e(bd_id)} &nbsp;// {chapter_link}</div>
      <div class="bd-title">{e(bd_title)}</div>
      <div class="bd-status {e(status)}">[{e(status.upper())}]</div>
      <div class="bd-desc">{e(description)}</div>
      <div class="tag-list">{tags_html}</div>
    </div>""")

        cards_html = f'<div class="bd-grid">\n' + "\n".join(cards) + "\n</div>"

    body = f"""
      <h1 class="page-title">Braindance Catalog</h1>
      <p>
        Braindances produced, commissioned, or sold by Motoko throughout the story.
        Each entry is a full-immersion experience — the viewer lives someone else's
        memories frame by frame.
      </p>
      {cards_html}
"""
    out = page_shell("Braindances", body, active_nav="braindances.html")
    dest = os.path.join(BUILD_DIR, "braindances.html")
    with open(dest, "w", encoding="utf-8") as f:
        f.write(out)
    print(f"  Wrote {dest}")


# ── characters/index.html ──────────────────────────────────────────────────

def build_char_index(characters):
    if not characters:
        grid_html = '<p class="placeholder-note">[Character profiles pending — no entries in cache yet]</p>'
    else:
        cards = []
        for slug, char in characters.items():
            name        = char.get("name", slug)
            role        = char.get("role", "")
            affil       = char.get("affiliation", "")
            bio_paras   = char.get("bio", [])
            bio_excerpt = bio_paras[0] if bio_paras else ""
            icon        = char.get("icon", "&#x25A0;")
            status      = char.get("status", "Unknown")

            cards.append(f"""    <a class="char-card" href="{e(slug)}.html">
      <span class="char-icon">{icon}</span>
      <span class="char-name">{e(name)}</span>
      <span class="char-role">{e(role)}</span>
      <span class="char-affil">{e(affil)}</span>
      <span class="char-bio-excerpt">{e(bio_excerpt)}</span>
    </a>""")

        grid_html = '<div class="char-grid">\n' + "\n".join(cards) + "\n</div>"

    body = f"""
      <h1 class="page-title">Characters</h1>
      {grid_html}
"""
    out = page_shell("Characters", body, css_path="../assets/style.css",
                     active_nav="characters/index.html")
    dest = os.path.join(CHARS_DIR, "index.html")
    with open(dest, "w", encoding="utf-8") as f:
        f.write(out)
    print(f"  Wrote {dest}")


# ── characters/<slug>.html ─────────────────────────────────────────────────

def build_char_page(slug, char):
    name     = char.get("name", slug)
    role     = char.get("role", "")
    affil    = char.get("affiliation", "")
    status   = char.get("status", "Unknown")
    bio_paras = char.get("bio", [])
    first_ch  = char.get("first_chapter", "?")
    icon      = char.get("icon", "&#x25A0;")

    status_cls = {
        "Active": "status-active",
        "Deceased": "status-deceased",
    }.get(status, "status-unknown")

    bio_html = "".join(f"<p>{e(p)}</p>" for p in bio_paras) if bio_paras \
        else '<p class="placeholder-note">[Bio pending]</p>'

    stat_rows = [
        ("Name",        name),
        ("Role",        role),
        ("Affiliation", affil),
        ("Status",      status),
        ("First App.",  f"Chapter {first_ch}"),
    ]

    rows_html = "\n".join(
        f'    <div class="char-stat-row">'
        f'<span class="char-stat-key">{e(k)}</span>'
        f'<span class="char-stat-val">{e(v)}</span>'
        f'</div>'
        for k, v in stat_rows
    )

    body = f"""
      <h1 class="page-title">{e(name)}</h1>
      <div class="char-profile">
        <div class="char-sidebar">
          <div class="char-icon">{icon}</div>
          {rows_html}
        </div>
        <div class="char-bio">
          {bio_html}
        </div>
      </div>
      <p><a href="index.html">&#x2190; All Characters</a></p>
"""
    out = page_shell(name, body, css_path="../assets/style.css",
                     active_nav="characters/index.html")
    dest = os.path.join(CHARS_DIR, f"{slug}.html")
    with open(dest, "w", encoding="utf-8") as f:
        f.write(out)
    print(f"  Wrote {dest}")


# ── Main entry point ───────────────────────────────────────────────────────

def main():
    print("Loading cache...")
    summaries   = load_summaries()
    braindances = load_braindances()
    characters  = load_characters()

    print("Building HTML...")
    build_index(summaries, characters, braindances)
    build_chapters(summaries)
    build_braindances(braindances)
    build_char_index(characters)

    for slug, char in characters.items():
        build_char_page(slug, char)

    print("Done.")


if __name__ == "__main__":
    main()
