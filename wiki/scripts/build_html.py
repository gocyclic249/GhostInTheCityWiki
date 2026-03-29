#!/usr/bin/env python3
"""
build_html.py — Renders all HTML pages from cache JSON.
Uses only Python stdlib. No external dependencies.
"""

import html
import json
import os
import sys
from datetime import datetime, timezone
from urllib.parse import urlparse

# ── Paths ──────────────────────────────────────────────────────────────────

WIKI_DIR    = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE_DIR   = os.path.join(WIKI_DIR, "cache")
BUILD_DIR   = os.path.join(WIKI_DIR, "build")
ASSETS_DIR  = os.path.join(BUILD_DIR, "assets")
CHARS_DIR   = os.path.join(BUILD_DIR, "characters")

SUMMARIES_JSON   = os.path.join(CACHE_DIR, "chapter_summaries.json")
BRAINDANCES_JSON = os.path.join(CACHE_DIR, "braindances.json")
CHARACTERS_JSON  = os.path.join(CACHE_DIR, "characters.json")
ROCKERBOY_JSON   = os.path.join(CACHE_DIR, "rockerboy.json")
SIDESTORIES_JSON = os.path.join(
    os.path.dirname(WIKI_DIR), "sidestories_index.json"
)

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


def load_rockerboy():
    return load_json(ROCKERBOY_JSON, [])


def load_sidestories():
    return load_json(SIDESTORIES_JSON, [])


MEDIA_JSON = os.path.join(os.path.dirname(WIKI_DIR), "media_index.json")


def load_media():
    return load_json(MEDIA_JSON, [])


# ── HTML helpers ───────────────────────────────────────────────────────────

def e(text):
    """HTML-escape a string."""
    return html.escape(str(text), quote=True)


def safe_url(url):
    """Validate URL scheme is safe for use in href attributes."""
    if not url:
        return ""
    try:
        parsed = urlparse(url)
        if parsed.scheme in ("http", "https", "mailto", ""):
            return e(url)
    except Exception:
        pass
    return ""


CSS_PATH = "assets/style.css"  # relative — overridden per page depth

FONT_LINK = (
    '<link rel="preconnect" href="https://fonts.googleapis.com">'
    '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>'
    '<link href="https://fonts.googleapis.com/css2?family=Share+Tech+Mono'
    '&family=VT323&display=swap" rel="stylesheet">'
)


def page_shell(title, body, css_path="assets/style.css", active_nav="",
               description="", canonical_path=""):
    """Wrap body HTML in a full page shell."""
    nav_items = [
        ("index.html",              "Home"),
        ("chapters.html",           "Chapters"),
        ("braindances.html",        "Braindances"),
        ("rockerboy.html",          "Rockerboy"),
        ("sidestories.html",        "Jig Jig Street"),
        ("photomode.html",          "Photomode"),
        ("characters/index.html",   "Characters"),
        ("charsheet.html",          "Gonk Stats"),
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

    site_name = "Ghost in the City Wiki"
    full_title = site_name if title == site_name else f"{e(title)} — {site_name}"

    # Per-page description for SEO — falls back to site-wide default
    if not description:
        description = "Fan wiki for Ghost in the City — a Cyberpunk 2077 / Ghost in the Shell crossover fanfiction by Seras."
    desc_escaped = e(description)

    # Canonical URL
    canonical_tag = ""
    og_url_tag = ""
    if canonical_path:
        canonical_url = f"{SITE_BASE}/{canonical_path}"
        canonical_tag = f'<link rel="canonical" href="{canonical_url}">'
        og_url_tag = f'<meta property="og:url" content="{canonical_url}">'

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{full_title}</title>
  <meta name="description" content="{desc_escaped}">
  <meta name="keywords" content="Ghost in the City, Cyberpunk 2077, Ghost in the Shell, fanfiction, Motoko Kusanagi, Night City, wiki">
  <meta name="author" content="GhostInTheCity Wiki Contributors">
  {canonical_tag}
  <meta property="og:title" content="{full_title}">
  <meta property="og:description" content="{desc_escaped}">
  <meta property="og:type" content="website">
  <meta property="og:site_name" content="{site_name}">
  {og_url_tag}
  <meta name="twitter:card" content="summary">
  <meta name="twitter:title" content="{full_title}">
  <meta name="twitter:description" content="{desc_escaped}">
  {FONT_LINK}
  <link rel="stylesheet" href="{css_path}?v=4">
</head>
<body>
  <div class="site-wrapper">
    <header class="site-header">
      <div class="site-title" style="display:flex;align-items:center;justify-content:space-between;">
        <a href="{nav_href('index.html')}">&#x2588; Ghost in the City // Wiki</a>
        <form class="search-float" style="display:flex;gap:0;margin:0;" action="{nav_href('search.html')}" method="GET">
          <input type="text" name="q" placeholder="// search" aria-label="Search">
          <button type="submit">&#x25B6;</button>
        </form>
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

def build_index(summaries, characters, braindances, sidestories, ch_total):
    kill_count    = total_kills(summaries)
    ch_summarized = sum(1 for ch in summaries.values() if ch.get("summary"))
    bd_count      = len(braindances)
    ss_count      = len(sidestories)
    char_count    = len(characters)

    body = f"""
      <h1 class="page-title">Ghost in the City</h1>
      <p class="blackwall-credit"><a href="https://claude.ai" rel="noopener" target="_blank">Made with help from beyond the Blackwall</a></p>
      <p class="blackwall-credit"><a href="https://github.com/gocyclic249/GhostInTheCityWiki/issues" rel="noopener" target="_blank">Update Wiki Engram or Report Blackwall Breach</a></p>
      <p class="story-summary">
        A <em>Cyberpunk 2077 / Ghost in the Shell</em> crossover SI (Self-Insert) by
        <strong>Seras</strong>. A gamer flatlines in the real world and wakes up in Night City,
        2075 — jacked into the body of fourteen-year-old Motoko Kusanagi, stripped of chrome
        by Scavs, fresh out of a year-long coma, and running on fumes. No eddies. No cyberware.
        No allies except a hothead Tyger Claw brother with a katana and a death wish.
        But the corpo gods left a gift in the wreckage: a shard labelled "Gema / Gamer" that
        boots a full stat screen behind her Kiroshi optics. Every pushup, every kill, every gig
        ticks the XP counter. The grind has begun.
        {e(str(ch_total))} chapters of Motoko clawing her way from a zeroed-out nobody to Night City
        legend — netrunner, assassin, Kensei swordswoman, founder of Section 9, and frontwoman
        of Stand Alone Complex. Corpo heists, gang wars, Scav raids, Cyberpsycho throwdowns,
        Tyger Claw politics, Aldecaldo barbeques, and a kill count north of {e(str(kill_count))}.
        She'll hack your subnet, flatline your crew, write a song about it, and be home in time
        for ramen at Cherry Blossom Market.
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
        <div class="stat-card">
          <span class="stat-label">Side Stories</span>
          <span class="stat-value">{e(str(ss_count))}</span>
        </div>
      </div>
"""
    out = page_shell("Ghost in the City Wiki", body, active_nav="index.html",
                      description=f"Fan wiki for Ghost in the City — a Cyberpunk 2077 / Ghost in the Shell crossover SI by Seras. {ch_total} chapters, {char_count} character profiles, {ss_count} community side stories.",
                      canonical_path="")
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
                   + (f' &nbsp;|&nbsp; <a href="{safe_url(url)}" rel="noopener">AO3 &#8599;</a>' if url else "")
                   + "</p>")
            )
        else:
            body_html = (
                '<p class="placeholder-note">[Summary pending]</p>'
                + (f'<p class="chapter-meta">Date: {e(date)}'
                   + (f' &nbsp;|&nbsp; <a href="{safe_url(url)}" rel="noopener">AO3 &#8599;</a>' if url else "")
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
    out = page_shell("Chapters", body, active_nav="chapters.html",
                      description=f"Chapter-by-chapter summaries for Ghost in the City. {summarized}/{len(index)} chapters summarised with kill counts and key events.",
                      canonical_path="chapters.html")
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
    out = page_shell("Braindances", body, active_nav="braindances.html",
                      description=f"Braindance catalog for Ghost in the City — every BD Motoko produces, commissions, or sells throughout the story. {len(braindances)} entries.",
                      canonical_path="braindances.html")
    dest = os.path.join(BUILD_DIR, "braindances.html")
    with open(dest, "w", encoding="utf-8") as f:
        f.write(out)
    print(f"  Wrote {dest}")


# ── characters/index.html ──────────────────────────────────────────────────

def _build_char_cards(characters, category):
    """Build card HTML for characters matching the given category."""
    cards = []
    for slug, char in characters.items():
        if char.get("category", "story") != category:
            continue
        if slug == "motoko":
            continue
        name        = char.get("name", slug)
        role        = char.get("role", "")
        affil       = char.get("affiliation", "")
        description = char.get("description", "")
        icon        = char.get("icon", "&#x25A0;")
        status      = char.get("status", "Unknown")

        cards.append(f"""    <a class="char-card" href="{e(slug)}.html">
      <span class="char-icon">{icon}</span>
      <span class="char-name">{e(name)}</span>
      <span class="char-role">{e(role)}</span>
      <span class="char-affil">{e(affil)}</span>
      <span class="char-bio-excerpt">{e(description)}</span>
    </a>""")
    return cards


def build_char_index(characters):
    if not characters:
        grid_html = '<p class="placeholder-note">[Character profiles pending — no entries in cache yet]</p>'
    else:
        # Motoko gets her own card at the top
        motoko = characters.get("motoko")
        motoko_html = ""
        if motoko:
            motoko_html = f"""<div class="char-grid">
    <a class="char-card" href="motoko.html">
      <span class="char-icon">{motoko.get("icon", "&#x25A0;")}</span>
      <span class="char-name">{e(motoko.get("name", "Motoko"))}</span>
      <span class="char-role">{e(motoko.get("role", ""))}</span>
      <span class="char-affil">{e(motoko.get("affiliation", ""))}</span>
      <span class="char-bio-excerpt">{e(motoko.get("description", ""))}</span>
    </a>
</div>"""

        # Story-original characters
        story_cards = _build_char_cards(characters, "story")
        story_html = ""
        if story_cards:
            story_html = (
                '<h2 class="char-section-heading">// Story Characters</h2>\n'
                '<div class="char-grid">\n' + "\n".join(story_cards) + "\n</div>"
            )

        # Canon CP2077 / Edgerunners characters
        canon_cards = _build_char_cards(characters, "canon")
        canon_html = ""
        if canon_cards:
            canon_html = (
                '<h2 class="char-section-heading">// Cyberpunk 2077 &amp; Edgerunners</h2>\n'
                '<p class="canon-note">Canon characters from the game and anime. '
                'Bios cover their role in this fanfic only.</p>\n'
                '<div class="char-grid">\n' + "\n".join(canon_cards) + "\n</div>"
            )

        grid_html = motoko_html + "\n" + story_html + "\n" + canon_html

    body = f"""
      <h1 class="page-title">Characters</h1>
      {grid_html}
"""
    out = page_shell("Characters", body, css_path="../assets/style.css",
                     active_nav="characters/index.html",
                     description=f"Character profiles for Ghost in the City — bios, stats, and faction details for {len(characters)} characters from the Cyberpunk 2077 / Ghost in the Shell crossover.",
                     canonical_path="characters/")
    dest = os.path.join(CHARS_DIR, "index.html")
    with open(dest, "w", encoding="utf-8") as f:
        f.write(out)
    print(f"  Wrote {dest}")


# ── CP RED stat block ──────────────────────────────────────────────────────

def build_cp_stats_block(cp):
    game      = cp.get("game", "Cyberpunk 2077")
    as_of     = cp.get("as_of", "")
    level     = cp.get("level", "?")
    attrs     = cp.get("attributes", {})
    skills    = cp.get("skills", [])
    cyberware = cp.get("cyberware", [])

    ATTR_ORDER = ["Body", "Reflexes", "Technical Ability", "Intelligence", "Cool"]
    MAX_ATTR   = 20

    # Group skills by attribute
    skills_by_attr = {}
    for sk in skills:
        a = sk.get("attribute", "")
        skills_by_attr.setdefault(a, []).append(sk)

    # Build attribute sections — each with its bar, then nested skills + perks
    attr_sections = ""
    for a in ATTR_ORDER:
        val = attrs.get(a, 0)
        bar_width = int(val / MAX_ATTR * 100)

        attr_header = (
            f'<div class="cp-attr-row">'
            f'<span class="cp-attr-name">{e(a)}</span>'
            f'<div class="cp-attr-bar">'
            f'<div class="cp-attr-fill" style="width:{bar_width}%"></div>'
            f'</div>'
            f'<span class="cp-attr-val">{e(str(val))}</span>'
            f'</div>'
        )

        skill_html = ""
        for sk in skills_by_attr.get(a, []):
            sk_name  = sk.get("name", "")
            sk_level = sk.get("level", 0)
            sk_perks = sk.get("perks", [])
            sk_bar   = int(sk_level / 20 * 100)

            skill_row = (
                f'<div class="cp-skill-row">'
                f'<span class="cp-skill-name">{e(sk_name)}</span>'
                f'<div class="cp-skill-bar">'
                f'<div class="cp-skill-fill" style="width:{sk_bar}%"></div>'
                f'</div>'
                f'<span class="cp-skill-level">{e(str(sk_level))}</span>'
                f'</div>'
            )

            perk_html = ""
            if sk_perks:
                chips = "".join(
                    f'<span class="cp-perk-chip">{e(p)}</span>' for p in sk_perks
                )
                perk_html = f'<div class="cp-perk-row">{chips}</div>'

            skill_html += skill_row + perk_html

        attr_sections += (
            f'<div class="cp-attr-group">'
            f'{attr_header}'
            f'<div class="cp-skill-list">{skill_html}</div>'
            f'</div>'
        )

    cw_items = "".join(f'<li>{e(item)}</li>' for item in cyberware)
    cw_html  = f'<ul class="cp-cyberware-list">{cw_items}</ul>' if cw_items else ""

    header_note = e(game) + (f' \u2014 as of {e(as_of)}' if as_of else "")

    return (
        f'<div class="cp-stats-block">'
        f'<h3 class="char-section-label">// Gonk Stats ({header_note})</h3>'
        f'<div class="cp-level-badge">// Character Level &nbsp; {e(str(level))}</div>'
        f'{attr_sections}'
        f'<h4 class="cp-subsection">// Cyberware</h4>'
        f'{cw_html}'
        f'</div>'
    )


# ── characters/<slug>.html ─────────────────────────────────────────────────

def build_char_page(slug, char):
    name        = char.get("name", slug)
    role        = char.get("role", "")
    affil       = char.get("affiliation", "")
    faction     = char.get("faction", "")
    description = char.get("description", "")
    status      = char.get("status", "Unknown")
    bio_paras   = char.get("bio", [])
    first_ch    = char.get("first_chapter", "?")
    icon        = char.get("icon", "&#x25A0;")

    status_cls = {
        "Active": "status-active",
        "Deceased": "status-deceased",
    }.get(status, "status-unknown")

    phys       = char.get("physical_description", "")
    phys_html  = (
        f'<h3 class="char-section-label">// Appearance</h3><p>{e(phys)}</p>'
        if phys else ""
    )
    bio_label  = '<h3 class="char-section-label">// Background</h3>' if phys else ""
    bio_html   = (
        bio_label + "".join(f"<p>{e(p)}</p>" for p in bio_paras)
        if bio_paras else '<p class="placeholder-note">[Bio pending]</p>'
    )

    stat_rows = [
        ("Name",        name),
        ("Role",        role),
        ("Faction",     faction),
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

    desc_html = f'<p class="char-description">{e(description)}</p>' if description else ""

    body = f"""
      <h1 class="page-title">{e(name)}</h1>
      {desc_html}
      <div class="char-profile">
        <div class="char-sidebar">
          <div class="char-icon">{icon}</div>
          {rows_html}
        </div>
        <div class="char-bio">
          {phys_html}
          {bio_html}
        </div>
      </div>
      <p><a href="index.html">&#x2190; All Characters</a></p>
"""
    char_desc = description if description else f"{name} — character profile from Ghost in the City, a Cyberpunk 2077 / Ghost in the Shell crossover."
    out = page_shell(name, body, css_path="../assets/style.css",
                     active_nav="characters/index.html",
                     description=char_desc,
                     canonical_path=f"characters/{slug}.html")
    dest = os.path.join(CHARS_DIR, f"{slug}.html")
    with open(dest, "w", encoding="utf-8") as f:
        f.write(out)
    print(f"  Wrote {dest}")


# ── charsheet.html ─────────────────────────────────────────────────────────

def build_charsheet(characters):
    motoko = characters.get("motoko", {})
    cp = motoko.get("cp_stats")

    if cp:
        cp_html = build_cp_stats_block(cp)
    else:
        cp_html = '<p class="placeholder-note">[Character sheet pending — no cp_stats in Motoko\'s cache entry]</p>'

    body = f"""
      <h1 class="page-title">Gonk Stats</h1>
      <p>
        Motoko Kusanagi's stats under the
        <em>Cyberpunk 2077</em> pre-Update 2.0 system.
        Attributes cap at 20. Skill levels are independent of attributes.
      </p>
      {cp_html}
"""
    out = page_shell("Gonk Stats", body, active_nav="charsheet.html",
                      description="Motoko Kusanagi's Cyberpunk 2077 character sheet — attributes, skills, perks, and cyberware from Ghost in the City.",
                      canonical_path="charsheet.html")
    dest = os.path.join(BUILD_DIR, "charsheet.html")
    with open(dest, "w", encoding="utf-8") as f:
        f.write(out)
    print(f"  Wrote {dest}")


# ── rockerboy.html ─────────────────────────────────────────────────────────

def build_rockerboy(events):
    TYPE_CLASS = {
        "Public Gig":         "rb-type-gig",
        "Impromptu":          "rb-type-improv",
        "Impromptu Solo":     "rb-type-improv",
        "Private Performance":"rb-type-private",
        "Studio Session":     "rb-type-studio",
        "Radio / Media":      "rb-type-radio",
        "Corporate Event":    "rb-type-corp",
        "Rehearsal":          "rb-type-studio",
    }

    if not events:
        body_content = '<p class="placeholder-note">[Rockerboy timeline pending]</p>'
    else:
        cards = []
        for ev in events:
            ev_id      = ev.get("event_id", "???")
            chapter    = ev.get("chapter_number", "?")
            venue      = ev.get("venue", "Unknown Venue")
            location   = ev.get("location", "")
            ev_type    = ev.get("type", "")
            band       = ev.get("band")
            context    = ev.get("context", "")
            setlist    = ev.get("setlist", [])
            notes      = ev.get("notes", "")

            type_cls   = TYPE_CLASS.get(ev_type, "rb-type-private")
            chapter_link = f'<a href="chapters.html">Ch.{e(str(chapter))}</a>'
            venue_line = e(venue) + (f" — {e(location)}" if location else "")
            band_html  = (
                f'<div class="rb-band">// {e(band)}</div>' if band else ""
            )

            songs_html = ""
            for song in setlist:
                title_  = song.get("song", "")
                artist_ = song.get("artist", "")
                yt_url  = song.get("youtube_url")
                if yt_url:
                    song_label = (
                        f'<a class="rb-song-link" href="{safe_url(yt_url)}" '
                        f'rel="noopener" target="_blank">{e(title_)} &#x2197;</a>'
                    )
                else:
                    song_label = f'<span class="rb-song-title">{e(title_)}</span>'
                songs_html += (
                    f'<li class="rb-song-row">'
                    f'{song_label}'
                    f'<span class="rb-song-artist">{e(artist_)}</span>'
                    f'</li>'
                )
            setlist_html = (
                f'<ol class="rb-setlist">{songs_html}</ol>'
                if songs_html else ""
            )

            notes_html = (
                f'<div class="rb-notes">{e(notes)}</div>' if notes else ""
            )

            cards.append(
                f'<div class="rb-card">'
                f'<div class="rb-header">'
                f'<span class="rb-id">{e(ev_id)}</span>'
                f'<span class="rb-chapter">{chapter_link}</span>'
                f'<span class="rb-type {e(type_cls)}">[{e(ev_type.upper())}]</span>'
                f'</div>'
                f'<div class="rb-venue">{venue_line}</div>'
                f'{band_html}'
                f'<div class="rb-context">{e(context)}</div>'
                f'<h4 class="rb-setlist-label">// Setlist</h4>'
                f'{setlist_html}'
                f'{notes_html}'
                f'</div>'
            )

        body_content = '<div class="rb-timeline">\n' + "\n".join(cards) + "\n</div>"

    body = f"""
      <h1 class="page-title">Rockerboy</h1>
      <p>
        Every performance, studio session, and public appearance in chapter order.
        Motoko's music career — from a single campfire song to a corpo record deal.
      </p>
      {body_content}
"""
    out = page_shell("Rockerboy", body, active_nav="rockerboy.html",
                      description=f"Rockerboy timeline for Ghost in the City — every performance, studio session, and setlist from Motoko's music career. {len(events)} events.",
                      canonical_path="rockerboy.html")
    dest = os.path.join(BUILD_DIR, "rockerboy.html")
    with open(dest, "w", encoding="utf-8") as f:
        f.write(out)
    print(f"  Wrote {dest}")


# ── sidestories.html ─────────────────────────────────────────────────────

def parse_word_count(wc_str):
    """Convert word count strings like '1.5k', '420', '59k' to integers."""
    if not wc_str or wc_str == "?":
        return 0
    wc_str = wc_str.replace(",", "")
    if wc_str.lower().endswith("k"):
        try:
            return int(float(wc_str[:-1]) * 1000)
        except ValueError:
            return 0
    try:
        return int(wc_str)
    except ValueError:
        return 0


def build_sidestories(sidestories):
    if not sidestories:
        list_html = '<p class="placeholder-note">[Side stories pending — run scrape_sidestories.py to build the index]</p>'
    else:
        total_words = sum(parse_word_count(ss.get("word_count", "0"))
                         for ss in sidestories)

        items = []
        for ss in sidestories:
            idx     = ss.get("index", "?")
            title   = ss.get("title", "Untitled")
            wc      = ss.get("word_count", "?")
            date    = ss.get("date", "")
            sb_url  = ss.get("sb_url", "")

            wc_html = (
                f'<span class="ss-words" title="~{e(str(wc))} words">&#x270E; {e(str(wc))}</span>'
                if wc and wc != "?" else ""
            )

            link_html = (
                f'<a href="{safe_url(sb_url)}" rel="noopener" target="_blank">'
                f'SpaceBattles &#8599;</a>'
                if sb_url else ""
            )

            date_html = f'<span class="ss-date">{e(date)}</span>' if date else ""

            author  = ss.get("author", "")
            author_html = f'<span class="ss-author">by {e(author)}</span>' if author else ""

            items.append(f"""      <li class="ss-entry">
        <span class="ss-num">{e(str(idx).zfill(3))}</span>
        <span class="ss-title">{e(title)}</span>
        {author_html}
        {wc_html}
        {date_html}
        {link_html}
      </li>""")

        list_html = f'<ul class="ss-list">\n' + "\n".join(items) + "\n      </ul>"

    ss_count = len(sidestories)
    total_words = sum(parse_word_count(ss.get("word_count", "0"))
                      for ss in sidestories)

    body = f"""
      <h1 class="page-title">Tales from Jig Jig Street</h1>
      <p>
        Community-written side stories, omakes, and snippets from the
        <a href="https://forums.spacebattles.com/threads/ghost-in-the-city-cyberpunk-gamer-si.1046809/"
           rel="noopener" target="_blank">SpaceBattles thread</a>.
        Canon and non-canon glimpses into Night City through other eyes.
      </p>
      <p>
        {e(str(ss_count))} side stories.
        ~{e(str(f'{total_words:,}'))} words total.
      </p>
      {list_html}
"""
    out = page_shell("Tales from Jig Jig Street", body,
                     active_nav="sidestories.html",
                     description=f"Community side stories for Ghost in the City — {ss_count} fan-written omakes and snippets from SpaceBattles. ~{total_words:,} words total.",
                     canonical_path="sidestories.html")
    dest = os.path.join(BUILD_DIR, "sidestories.html")
    with open(dest, "w", encoding="utf-8") as f:
        f.write(out)
    print(f"  Wrote {dest}")


# ── photomode.html ────────────────────────────────────────────────────────

def build_photomode(media_entries):
    if not media_entries:
        gallery_html = '<p class="placeholder-note">[Photomode pending — run scrape_media.py to build the index]</p>'
    else:
        # Only show entries that have images
        with_images = [m for m in media_entries if m.get("images")]

        cards = []
        for m in with_images:
            title = m.get("title", "Untitled")
            artist = m.get("artist", "Unknown")
            date = m.get("date", "")
            sb_url = m.get("sb_url", "")
            context = m.get("context", "")
            images = m.get("images", [])

            if not images:
                continue

            # Filter to images that have been downloaded locally
            local_images = [img for img in images if img.get("local_file")]
            if not local_images:
                continue

            # Use first image as the card image
            img = local_images[0]
            local_file = img.get("local_file", "")
            img_src = f"media/{e(local_file)}"

            # Build additional images if more than one
            extra_html = ""
            if len(local_images) > 1:
                extra_imgs = []
                for extra in local_images[1:]:
                    ef = extra.get("local_file", "")
                    if ef:
                        extra_imgs.append(
                            f'<a href="media/{e(ef)}" target="_blank">'
                            f'<img class="pm-extra-img" src="media/{e(ef)}" '
                            f'loading="lazy" alt="{e(extra.get("alt_text", ""))}">'
                            f'</a>'
                        )
                if extra_imgs:
                    extra_html = (
                        f'<div class="pm-extra-images">'
                        + "".join(extra_imgs)
                        + '</div>'
                    )

            link_html = (
                f'<a href="{safe_url(sb_url)}" rel="noopener" target="_blank">'
                f'SpaceBattles &#8599;</a>'
                if sb_url else ""
            )

            date_html = f'<span class="pm-date">{e(date)}</span>' if date else ""

            context_html = ""
            if context and len(context) > 5:
                import re as _re
                # Strip any remaining quote markers, post refs, click artifacts
                clean = _re.sub(r'(?:^|\s)>\s*', ' ', context)
                clean = _re.sub(r'Click to (?:expand|shrink)\.\.\.', '', clean)
                clean = _re.sub(r'\*\s+#[\d,]+', '', clean)
                clean = _re.sub(r'\s{2,}', ' ', clean).strip()
                if clean and len(clean) > 5:
                    short = clean[:200] + "..." if len(clean) > 200 else clean
                    context_html = f'<p class="pm-context">{e(short)}</p>'

            cards.append(f"""    <div class="pm-card">
      <a href="media/{e(local_file)}" target="_blank" class="pm-img-link">
        <img class="pm-img" src="{img_src}" loading="lazy" alt="{e(title)}">
      </a>
      {extra_html}
      <div class="pm-info">
        <span class="pm-title">{e(title)}</span>
        <span class="pm-artist">// {e(artist)}</span>
        {context_html}
        <div class="pm-meta">
          {date_html}
          {link_html}
        </div>
      </div>
    </div>""")

        gallery_html = (
            f'<div class="pm-grid">\n'
            + "\n".join(cards)
            + "\n</div>"
        )

    total_threadmarks = len(media_entries)
    shown = len([m for m in media_entries
                 if any(img.get("local_file") for img in m.get("images", []))])
    broken_links = sum(1 for m in media_entries
                       if m.get("images")
                       and not any(img.get("local_file") for img in m.get("images", [])))
    no_images = sum(1 for m in media_entries if not m.get("images"))
    total_local = sum(
        sum(1 for img in m.get("images", []) if img.get("local_file"))
        for m in media_entries
    )

    stats_parts = [f"{e(str(total_threadmarks))} threadmarks"]
    if broken_links:
        stats_parts.append(f"{e(str(broken_links))} broken links")
    if no_images:
        stats_parts.append(f"{e(str(no_images))} non-image posts")
    stats_line = " &#x2022; ".join(stats_parts)

    body = f"""
      <h1 class="page-title">Photomode</h1>
      <p>
        Fan art, AI-generated images, and visual media from the
        <a href="https://forums.spacebattles.com/threads/ghost-in-the-city-cyberpunk-gamer-si.1046809/"
           rel="noopener" target="_blank">SpaceBattles thread</a>.
        Click any image to view full size.
      </p>
      <p>
        {stats_line} &#x2022; {e(str(shown))} posts shown, {e(str(total_local))} images.
      </p>
      {gallery_html}
"""
    out = page_shell("Photomode", body,
                     active_nav="photomode.html",
                     description=f"Fan art gallery for Ghost in the City — {shown} posts with {total_local} images from the SpaceBattles community.",
                     canonical_path="photomode.html")
    dest = os.path.join(BUILD_DIR, "photomode.html")
    with open(dest, "w", encoding="utf-8") as f:
        f.write(out)
    print(f"  Wrote {dest}")


# ── search.html ───────────────────────────────────────────────────────────

def build_search():
    body = """
      <h1 class="page-title">Search Results</h1>
      <script async src="https://cse.google.com/cse.js?cx=d4dfaaef6c88f4085"></script>
      <div class="gcse-searchresults-only"></div>
      <script>
        // Read ?q= param and feed it to Google CSE once it loads
        var q = new URLSearchParams(window.location.search).get('q');
        if (q) {
          var wait = setInterval(function() {
            var el = google.search.cse.element.getElement('searchresults-only0');
            if (el) { el.execute(q); clearInterval(wait); }
          }, 100);
        }
      </script>
"""
    out = page_shell("Search", body, active_nav="",
                      description="Search the Ghost in the City wiki — find chapters, characters, braindances, and side stories.",
                      canonical_path="search.html")
    dest = os.path.join(BUILD_DIR, "search.html")
    with open(dest, "w", encoding="utf-8")as f:
        f.write(out)
    print(f"  Wrote {dest}")


# ── sitemap.xml ───────────────────────────────────────────────────────────

SITE_BASE = "https://ghostinthecity.neocities.org"

# Pages listed in priority order — character pages are added dynamically
STATIC_PAGES = [
    ("",                        "1.0"),
    ("chapters.html",           "0.9"),
    ("braindances.html",        "0.8"),
    ("rockerboy.html",          "0.8"),
    ("sidestories.html",        "0.8"),
    ("photomode.html",          "0.8"),
    ("characters/",             "0.8"),
    ("charsheet.html",          "0.7"),
]


def build_sitemap(characters):
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    urls = []
    for page, priority in STATIC_PAGES:
        urls.append(
            f"  <url>\n"
            f"    <loc>{SITE_BASE}/{page}</loc>\n"
            f"    <lastmod>{today}</lastmod>\n"
            f"    <priority>{priority}</priority>\n"
            f"  </url>"
        )
    for slug in characters:
        urls.append(
            f"  <url>\n"
            f"    <loc>{SITE_BASE}/characters/{slug}.html</loc>\n"
            f"    <lastmod>{today}</lastmod>\n"
            f"    <priority>0.6</priority>\n"
            f"  </url>"
        )

    xml = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        + "\n".join(urls) + "\n"
        '</urlset>\n'
    )
    dest = os.path.join(BUILD_DIR, "sitemap.xml")
    with open(dest, "w", encoding="utf-8") as f:
        f.write(xml)
    print(f"  Wrote {dest}")


def build_robots():
    content = (
        f"User-agent: *\n"
        f"Allow: /\n"
        f"\n"
        f"Sitemap: {SITE_BASE}/sitemap.xml\n"
    )
    dest = os.path.join(BUILD_DIR, "robots.txt")
    with open(dest, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"  Wrote {dest}")


# ── Main entry point ───────────────────────────────────────────────────────

def main():
    print("Loading cache...")
    summaries   = load_summaries()
    braindances = load_braindances()
    characters  = load_characters()
    rockerboy   = load_rockerboy()
    sidestories = load_sidestories()
    media       = load_media()

    threadmarks_path = os.path.join(os.path.dirname(WIKI_DIR), "threadmarks_index.json")
    if os.path.exists(threadmarks_path):
        with open(threadmarks_path, encoding="utf-8") as f:
            ch_total = len(json.load(f))
    else:
        ch_total = len(summaries)

    print("Building HTML...")
    build_index(summaries, characters, braindances, sidestories, ch_total)
    build_chapters(summaries)
    build_braindances(braindances)
    build_rockerboy(rockerboy)
    build_sidestories(sidestories)
    build_photomode(media)
    build_char_index(characters)
    build_charsheet(characters)
    build_search()

    for slug, char in characters.items():
        build_char_page(slug, char)

    build_sitemap(characters)
    build_robots()
    print("Done.")


if __name__ == "__main__":
    main()
