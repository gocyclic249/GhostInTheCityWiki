# Ghost in the City — Wiki

Fan wiki for **Ghost in the City** by Seras — a *Cyberpunk 2077 / Ghost in the Shell* crossover SI.

A gamer flatlines in the real world and wakes up in Night City, 2075 — jacked into the body of fourteen-year-old Motoko Kusanagi, stripped of chrome by Scavs, fresh out of a year-long coma, and running on fumes. But the corpo gods left a gift in the wreckage: a shard labelled "Gema / Gamer" that boots a full stat screen behind her Kiroshi optics. 242 chapters of Motoko clawing her way from a zeroed-out nobody to Night City legend.

**Read the story:** [AO3](https://archiveofourown.org/works/42385683) | [SpaceBattles](https://forums.spacebattles.com/threads/ghost-in-the-city-cyberpunk-gamer-si.1046809/)

---

## Wiki Pages

**[ghostinthecity.neocities.org](https://ghostinthecity.neocities.org/)**

| Page | Description | Link |
|------|-------------|------|
| Home | Story summary, kill counter, and stats | [Home](https://ghostinthecity.neocities.org/index.html) |
| Chapters | All 242 chapter summaries with kill tracking | [Chapters](https://ghostinthecity.neocities.org/chapters.html) |
| Braindances | Full BD catalog — combat, stealth, and emotional recordings | [Braindances](https://ghostinthecity.neocities.org/braindances.html) |
| Rockerboy | Music timeline, venues, setlists, and YouTube links | [Rockerboy](https://ghostinthecity.neocities.org/rockerboy.html) |
| Jig Jig Street | 916 community side stories | [Side Stories](https://ghostinthecity.neocities.org/sidestories.html) |
| Photomode | Fan art and media from the SpaceBattles thread | [Photomode](https://ghostinthecity.neocities.org/photomode.html) |
| Characters | Character dossiers and profiles | [Characters](https://ghostinthecity.neocities.org/characters/index.html) |
| Gonk Stats | Motoko's full character sheet and skill tree | [Gonk Stats](https://ghostinthecity.neocities.org/charsheet.html) |
| Search | Full-text search across all wiki content | [Search](https://ghostinthecity.neocities.org/search.html) |

### Character Profiles

| Character | Role | Link |
|-----------|------|------|
| Motoko Kusanagi | Netrunner / Assassin | [Profile](https://ghostinthecity.neocities.org/characters/motoko.html) |
| Junichiro Kusanagi | Tyger Claw / Brother | [Profile](https://ghostinthecity.neocities.org/characters/jun.html) |
| Hiromi | Manager / Arasaka Academy | [Profile](https://ghostinthecity.neocities.org/characters/hiromi.html) |
| Malcolm | Crew Member | [Profile](https://ghostinthecity.neocities.org/characters/malcolm.html) |
| Ichi | Crew Leader | [Profile](https://ghostinthecity.neocities.org/characters/ichi.html) |
| Omaeda | Netrunner | [Profile](https://ghostinthecity.neocities.org/characters/omaeda.html) |
| Sam | Section 9 | [Profile](https://ghostinthecity.neocities.org/characters/sam.html) |
| Hayato Nakagawa | Tyger Claw Heir | [Profile](https://ghostinthecity.neocities.org/characters/hayato.html) |
| Akari | Section 9 | [Profile](https://ghostinthecity.neocities.org/characters/akari.html) |
| Alice Novak | Rockerboy / Band | [Profile](https://ghostinthecity.neocities.org/characters/alice.html) |
| Yuto Gonzales | Section 9 | [Profile](https://ghostinthecity.neocities.org/characters/yuto.html) |

---

## Project Structure

```
GhostInTheCityWiki/
├── chapters/              # Downloaded chapter markdown files (AO3)
├── sidestories/           # Downloaded side story markdown files (SpaceBattles)
├── lib/                   # Shared Python utilities
│   ├── selenium_utils.py  # Chrome driver creation, Cloudflare handling
│   ├── spacebattles_utils.py  # SpaceBattles login
│   ├── tavily_utils.py    # Tavily Extract API helper
│   └── image_utils.py     # Image download (canvas, fetch, urllib)
├── wiki/
│   ├── cache/             # JSON data files (edit these!)
│   │   ├── characters.json
│   │   ├── braindances.json
│   │   ├── rockerboy.json
│   │   └── chapter_summaries.json
│   ├── build/             # Generated HTML (don't edit)
│   └── scripts/
│       ├── build.py       # Build orchestrator
│       ├── build_html.py  # HTML renderer
│       └── upload.py      # Neocities uploader
├── scrape.py              # AO3 chapter scraper
├── scrape_media.py        # SpaceBattles media/fan art scraper
├── scrape_sidestories.py  # SpaceBattles side story scraper
├── grab_remaining.py      # Selenium image grabber (fallback)
├── chrome_download.py     # Cloudflare-protected image downloader
├── download_external.py   # External image downloader (imgur, etc.)
├── update_wiki.py         # Full pipeline orchestrator
└── .env.example           # Environment variable template
```

---

## Setup

1. Clone the repo
2. Copy `.env.example` to `.env` and fill in your keys:
   ```bash
   cp .env.example .env
   # Edit .env with your actual credentials
   source .env
   ```
3. Required environment variables:
   - `NEOCITIES_API_KEY` — for deploying to Neocities
   - `TAVILY_API_KEY` — for scraping SpaceBattles (Cloudflare bypass)
   - `SB_USER` / `SB_PASS` — SpaceBattles login (for image downloads)
4. Optional: set `CHROMEDRIVER_PATH` and `CHROMIUM_PATH` to override auto-detection

---

## How to Edit Wiki Content

All wiki content lives in **`wiki/cache/`** as plain JSON files. The HTML pages are generated from these files and should never be edited directly — any manual changes to the HTML will be overwritten on the next build.

### Files at a Glance

| File | What it controls |
|---|---|
| `wiki/cache/characters.json` | Character profiles, bios, stats |
| `wiki/cache/braindances.json` | The BD catalog |
| `wiki/cache/rockerboy.json` | Music performances and setlists |
| `wiki/cache/chapter_summaries.json` | Chapter recaps (auto-populated by scraper) |

### Editing Characters — `characters.json`

The file is a JSON object. Each key is a character slug (used in the URL), and the value is the character data.

```json
{
  "motoko": {
    "name": "Motoko Kusanagi",
    "role": "Netrunner / Assassin",
    "faction": "Section 9",
    "affiliation": "Independent",
    "status": "Active",
    "first_chapter": 1,
    "icon": "&#x2620;",
    "description": "Short one-line description shown on the character card.",
    "physical_description": "Longer appearance description shown on the character page.",
    "bio": [
      "First paragraph of background.",
      "Second paragraph of background."
    ]
  }
}
```

**Fields:**

- `name` — Full display name
- `role` — Short role label (e.g. `"Netrunner / Assassin"`)
- `faction` — Primary faction (e.g. `"Section 9"`, `"Tyger Claws"`)
- `affiliation` — Allegiance label
- `status` — `"Active"`, `"Deceased"`, or `"Unknown"`
- `first_chapter` — Chapter number they first appear (use `"?"` if unknown)
- `icon` — HTML entity for the icon shown on the card (e.g. `"&#x2620;"` = skull)
- `description` — One-sentence summary shown on the character index card
- `physical_description` — Appearance paragraph shown on the character's own page
- `bio` — Array of paragraph strings for the background section

**To add a new character**, copy an existing entry, change the slug key, and fill in the fields. The slug becomes the URL: `characters/slug.html`.

**To remove a character**, delete their entire `"slug": { ... }` block. Make sure to remove the trailing comma on the entry above it.

**The `cp_stats` block** (Motoko only) is more complex — see the existing entry as a reference. Only edit it if you have confirmed stat values from the story.

### Editing Braindances — `braindances.json`

The file is a JSON array `[ {...}, {...} ]`. Entries are displayed in the order they appear in the file (currently chapter order).

```json
{
  "bd_id": "BD-001",
  "title": "Kamikaze Raid",
  "chapter_number": 40,
  "status": "Released",
  "description": "Full description of the BD.",
  "content_tags": ["combat", "stealth", "rooftop"]
}
```

**Fields:**

- `bd_id` — Catalog ID (e.g. `"BD-001"`). Keep these in chapter order.
- `title` — Display title.
- `chapter_number` — The chapter the BD was recorded in.
- `status` — One of: `"Released"` (cyan), `"Personal Only"` (gold), `"Unreleased"` (dim), `"Leaked"` (pink)
- `description` — Full description paragraph.
- `content_tags` — Array of short tag strings shown as chips.

### Editing the Rockerboy Timeline — `rockerboy.json`

The file is a JSON array. Entries are displayed in chapter order.

```json
{
  "event_id": "RB-001",
  "chapter_number": 52,
  "venue": "Unnamed Campfire",
  "location": "Badlands",
  "type": "Impromptu",
  "band": null,
  "context": "What happened and why it mattered.",
  "setlist": [
    {
      "song": "Chippin' In",
      "artist": "Samurai (Cyberpunk 2077 OST)",
      "youtube_url": "https://www.youtube.com/watch?v=NAjf29AOxuw"
    }
  ],
  "notes": "Short factual note shown at the bottom of the card."
}
```

### JSON Syntax Rules

If the build breaks after an edit, the most common causes are:

1. **Missing comma** — Every item in an array or object needs a comma after it *except the last one*.
2. **Trailing comma** — A comma *after* the last item will break it.
3. **Unescaped characters** — If you need a literal `"` inside a string, escape it as `\"`.
4. **Unclosed brackets** — Every `[` needs a `]` and every `{` needs a `}`.

Validate your JSON at [jsonlint.com](https://jsonlint.com) before rebuilding.

---

## Building and Deploying

Full pipeline (scrape + build + upload):
```bash
source .env
python3 update_wiki.py
```

Build and upload only (no scraping):
```bash
source .env
python3 wiki/scripts/build.py --all
```

Build only (no upload):
```bash
python3 wiki/scripts/build.py --build
```

Requires Python 3 (stdlib only for build/upload — Selenium needed for image scrapers).
