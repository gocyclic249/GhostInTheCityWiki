# Ghost in the City — Wiki

Fan wiki for **Ghost in the City** by Seras — a *Cyberpunk 2077 / Ghost in the Shell* crossover SI.

A gamer flatlines in the real world and wakes up in Night City, 2075 — jacked into the body of fourteen-year-old Motoko Kusanagi, stripped of chrome by Scavs, fresh out of a year-long coma, and running on fumes. But the corpo gods left a gift in the wreckage: a shard labelled "Gema / Gamer" that boots a full stat screen behind her Kiroshi optics. Hundreds of chapters of Motoko clawing her way from a zeroed-out nobody to Night City legend.

**Read the story:** [AO3](https://archiveofourown.org/works/42385683) | [SpaceBattles](https://forums.spacebattles.com/threads/ghost-in-the-city-cyberpunk-gamer-si.1046809/)

---

## Wiki Pages

**[ghostinthecity.neocities.org](https://ghostinthecity.neocities.org/)**

| Page | Description | Link |
|------|-------------|------|
| Home | Story summary, kill counter, and stats | [Home](https://ghostinthecity.neocities.org/index.html) |
| Chapters | Every chapter summary, with kill tracking | [Chapters](https://ghostinthecity.neocities.org/chapters.html) |
| Braindances | Full BD catalog — combat, stealth, and emotional recordings | [Braindances](https://ghostinthecity.neocities.org/braindances.html) |
| Rockerboy | Music timeline, venues, setlists, and YouTube links | [Rockerboy](https://ghostinthecity.neocities.org/rockerboy.html) |
| Jig Jig Street | Community side stories from the SB thread | [Side Stories](https://ghostinthecity.neocities.org/sidestories.html) |
| Photomode | Fan art and media from the SpaceBattles thread | [Photomode](https://ghostinthecity.neocities.org/photomode.html) |
| Characters | Character dossiers and profiles | [Characters](https://ghostinthecity.neocities.org/characters/index.html) |
| Gonk Stats | Motoko's full character sheet and skill tree | [Gonk Stats](https://ghostinthecity.neocities.org/charsheet.html) |

Every page header carries a search box that runs a Google `site:` query against the wiki.

### Character Profiles

Every profile is listed on the [Characters index](https://ghostinthecity.neocities.org/characters/index.html), and each one gets its own page at `characters/<slug>.html`. The roster is whatever `wiki/cache/characters.json` contains — run `python3 wiki/scripts/build.py --status` for the current list rather than trusting a copy pasted here.

---

## Project Structure

```
GhostInTheCityWiki/
├── chapters/              # Downloaded chapter markdown files (AO3, gitignored)
├── docs/
│   └── manual-images.md   # Manual image recovery procedure
├── tests/                 # Test suite (stdlib unittest, no env vars needed)
├── lib/                   # Shared Python utilities
│   ├── safe_index.py      # Guarded, atomic index writes (stdlib only)
│   ├── selenium_utils.py  # Chrome driver creation, Cloudflare handling
│   ├── spacebattles_utils.py  # SpaceBattles login
│   ├── tavily_utils.py    # Tavily Extract API helper
│   └── image_utils.py     # Image download (canvas, fetch, urllib)
├── scripts/
│   └── debug/             # Fallback image-recovery scripts (Selenium)
│       ├── grab_remaining.py     # Selenium image grabber
│       ├── chrome_download.py    # Cloudflare-protected image downloader
│       └── download_external.py  # External image downloader (imgur, etc.)
├── wiki/
│   ├── cache/             # JSON data files (edit these!)
│   │   ├── characters.json
│   │   ├── braindances.json
│   │   ├── rockerboy.json
│   │   └── chapter_summaries.json
│   ├── build/             # Generated HTML (don't edit)
│   └── scripts/
│       ├── build.py             # Build orchestrator
│       ├── build_html.py        # HTML renderer
│       ├── cleanup_summaries.py # AI-pattern cleanup safety net
│       └── upload.py            # Neocities uploader
├── scrape.py              # AO3 chapter scraper
├── scrape_media.py        # SpaceBattles media/fan art scraper
├── scrape_sidestories.py  # SpaceBattles side story scraper
├── update_wiki.py         # Full pipeline orchestrator
├── threadmarks_index.json # Chapter metadata index
├── sidestories_index.json # Side story metadata index
├── media_index.json       # Media threadmark index + image metadata
├── requirements.txt       # Python dependencies
├── install-deps.sh        # Dependency installer (apt/dnf/pacman/brew)
├── LICENSE                # AGPL-3.0
└── .env.example           # Environment variable template
```

Note there is no `sidestories/` directory. Side stories are indexed but never
downloaded — `sidestories_index.json` holds title, author, word count, and a
link back to the SpaceBattles post.

---

## Setup

1. Clone the repo
2. Install Python dependencies:
   ```bash
   pip install -r requirements.txt
   ```
   The SpaceBattles scrapers (`scrape_media.py`, `scrape_sidestories.py`) need:
   - `requests` — HTTP client
   - `beautifulsoup4` — HTML parsing
   - `lxml` — fast parser backend for BeautifulSoup

   Build/upload and the AO3 scraper use the Python standard library only.

   Optional packages (commented out in `requirements.txt`):
   - `tavily-python` — improves SpaceBattles image extraction; falls back to direct HTTP if absent
   - `selenium` — only needed for the debug recovery scripts in `scripts/debug/`
3. Copy `.env.example` to `.env` and fill in your keys:
   ```bash
   cp .env.example .env
   # Edit .env with your actual credentials
   source .env
   ```
4. Required environment variables:
   - `NEOCITIES_API_KEY` — for deploying to Neocities
   - `SB_USER` / `SB_PASS` — SpaceBattles login (for image downloads)
5. Optional environment variables:
   - `TAVILY_API_KEY` — improves SpaceBattles image extraction; falls back to direct HTTP if unset
   - `CHROMEDRIVER_PATH` / `CHROMIUM_PATH` — override Chrome auto-detection (debug scripts only)

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
python3 update_wiki.py            # full update: scrape + build + upload
python3 update_wiki.py --scrape   # scrape only (no build/upload)
python3 update_wiki.py --build    # build + upload only (no scraping)
python3 update_wiki.py --dry-run  # show what would change, don't upload
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

Individual scrapers:
```bash
python3 scrape.py --update                # pull new AO3 chapters
python3 scrape_sidestories.py             # refresh the side story index
python3 scrape_sidestories.py --status    # index stats, no network
python3 scrape_media.py                   # media index + download images
python3 scrape_media.py --index-only      # index only, no downloads
```

Both SpaceBattles scrapers accept `--force` to override the shrink guard
described under [Content Recovery](#content-recovery).

Requires Python 3. Build/upload and the AO3 scraper use the standard library only;
the SpaceBattles scrapers need the packages in `requirements.txt`. Selenium is only
needed for the optional debug recovery scripts in `scripts/debug/`.

---

## Content Recovery

Chapter text and fan art are deliberately kept out of git — the story text is not
redistributed, and the artists asked not to have their work sitting in a public
repo. So a fresh clone starts without either. Each has an external store of
record and a one-command restore:

| Content | Store of record | Restore |
|---|---|---|
| `wiki/build/media/` | Neocities | `python3 wiki/scripts/upload.py --restore-media` |
| `chapters/*.md` | AO3 | `python3 scrape.py --restore` |

```bash
source .env
python3 wiki/scripts/upload.py --restore-media   # ~126 images, about 75 seconds
python3 scrape.py --restore                      # all missing chapters, 3s each
python3 scrape.py --restore --from 200 --to 246  # or bound the range
```

Media cannot be re-scraped from its original sources — many are dead imgur links,
expired Discord CDN URLs, or Cloudflare-blocked attachments — so Neocities is the
live store of record. Each download is checked against the SHA1 the Neocities
API reports and discarded unless it is really an image, so a 404 page can never
land as a broken file. `upload.py` also refuses to delete anything under
`media/`, even when the local copy is missing.

Neocities alone is not enough, though. If a bad local file is uploaded over the
Neocities original, the good copy is gone — restoring from Neocities just pulls
the bad file back. Two fallbacks cover that case:

- **`media-archive/`** — encrypted volumes of the whole media tree, tracked in
  git. See [Encrypted Media Archive](#encrypted-media-archive) below.
- **Git history, commit `577f2a7`** — media was tracked until commit `072e2cd`.
  That older commit still holds 121 images as real blobs:
  ```bash
  git show 577f2a7:wiki/build/media/<name> > wiki/build/media/<name>
  ```
  It predates the untracking, so it does not cover anything added since.

Some images are gone from every store. As of 2026-08-19, eleven images referenced
by `photomode.html` exist nowhere — their SpaceBattles posts were deleted upstream
and they postdate `577f2a7`: `91754121_{1,2,3}.png`, `91765497_{1,2,3}.png`,
`91788975_{1,2,3,4}.png`, and `92611121_1.jpg`.

### Encrypted Media Archive

The artists asked not to have their work sitting in a public repo, but the art
still needs to survive independently of Neocities. `media-archive/` squares that
circle: it holds the full media tree as **AES-256 encrypted zip volumes**, tracked
in git. Without the passphrase the blobs are noise, so nothing is scrapable.

```bash
python3 wiki/scripts/pack_media.py --status    # compare media/ to the archive (no passphrase)
python3 wiki/scripts/pack_media.py --pack      # rebuild the volumes (prompts for a passphrase)
python3 wiki/scripts/pack_media.py --verify    # sha256 every entry against the manifest
python3 wiki/scripts/pack_media.py --extract   # restore media/ from the volumes
```

Repack whenever `--status` reports `STALE`, which happens after any
`scrape_media.py` run that adds images. Always `--verify` afterwards — that is
what proves the archive can actually be restored.

**Passphrase handling.** The script prompts via `getpass`, or reads
`MEDIA_ARCHIVE_PASSPHRASE` for non-interactive runs. It is never accepted as a
command-line argument, so it stays out of shell history and `ps`. Use a long
random passphrase from a password manager: these blobs go into a public repo, and
**git history is permanent — a weak or leaked passphrase cannot be walked back**
by deleting the file later.

**What is and is not hidden.** WinZip AES encrypts file contents, not the zip
central directory, so the post-ID filenames are readable in a tracked volume. That
leaks nothing new, since `media_index.json` already maps those IDs to their
SpaceBattles URLs and artist names in the clear.

The set splits into volumes capped at 45 MiB (`--max-part-bytes`) — currently 3
parts totalling ~94 MiB. GitHub hard-rejects any file over 100 MiB and warns above
50 MiB, and a single archive would already be at 94 MiB with no headroom. Files
are assigned in sorted-name order, so new art usually rewrites only the last
volume rather than every blob.

`scrape.py --restore` re-downloads chapters that are missing and re-fetches ones
that look damaged (under 500 bytes, or missing their title line).

### Failed scrapes cannot blank an index

`scrape_sidestories.py` and `scrape_media.py` write through `lib/safe_index.py`,
which refuses a zero-entry result or a shrink of more than 10% and exits 2. If a
scrape is blocked or rate-limited, the existing index survives untouched:

```
  REFUSED: scrape returned 0 entries; existing index has 960.
  sidestories_index.json left untouched. Re-run when the source is reachable, or pass --force.
```

Pass `--force` when a drop is genuine. Writes are atomic and leave a `.bak` copy.

---

## Tests

```bash
python3 -m unittest discover -s tests -v
```

Standard-library `unittest`, no third-party packages, and no environment
variables or API keys required. The suite covers the index guards, the media
protection and restore logic, and chapter classification.

---

## Manual Image Workflow

Some media images can't be scraped automatically (dead imgur URLs, SB-served logo
fallbacks, parser misses, Discord CDN expirations, Cloudflare-blocked SB attachments).
The full recovery procedure is in [`docs/manual-images.md`](docs/manual-images.md).
Quick commands:

- `python3 scrape_media.py --show-manual` — list every image needing attention
- `python3 scrape_media.py --mark-manual POST_ID [--count N]` — flag a post for manual replacement
- `python3 scrape_media.py --unmark-manual POST_ID` — clear the flag once a real file is in `wiki/build/media/`

---

## License

Code is licensed under AGPL-3.0 — see [`LICENSE`](LICENSE). Story content belongs to
Seras; chapter and side-story text is gitignored and not redistributed in this repo.
