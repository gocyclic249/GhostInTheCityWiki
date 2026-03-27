# Ghost in the City — Wiki

Fan wiki for **Ghost in the City** by Seras — a *Cyberpunk 2077 / Ghost in the Shell* crossover SI hosted on [AO3](https://archiveofourown.org/works/42385683).

[Wiki](https://ghostinthecity.neocities.org/)

---

## How to Edit Wiki Content

All wiki content lives in **`wiki/cache/`** as plain JSON files. This is the only place you need to edit. The HTML pages are generated from these files and should never be edited directly — any manual changes to the HTML will be overwritten on the next build.

---

### Files at a Glance

| File | What it controls |
|---|---|
| `wiki/cache/characters.json` | Character profiles, bios, stats |
| `wiki/cache/braindances.json` | The BD catalog |
| `wiki/cache/rockerboy.json` | Music performances and setlists |
| `wiki/cache/chapter_summaries.json` | Chapter recaps (auto-populated by scraper) |

---

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
- `icon` — HTML entity for the icon shown on the card (e.g. `"&#x2620;"` = ☠)
- `description` — One-sentence summary shown on the character index card
- `physical_description` — Appearance paragraph shown on the character's own page
- `bio` — Array of paragraph strings for the background section

**To add a new character**, copy an existing entry, change the slug key, and fill in the fields. The slug becomes the URL: `characters/slug.html`.

**To remove a character**, delete their entire `"slug": { ... }` block. Make sure to remove the trailing comma on the entry above it.

**The `cp_stats` block** (Motoko only) is more complex — see the existing entry as a reference. Only edit it if you have confirmed stat values from the story.

---

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
- `title` — Display title. Use `"Unnamed"` or `"Unnamed (subtitle)"` for untitled BDs.
- `chapter_number` — The chapter the BD was recorded in. Controls sort position.
- `status` — One of:
  - `"Released"` — publicly distributed (cyan)
  - `"Personal Only"` — not for sale (gold)
  - `"Unreleased"` — recorded but not distributed (dim)
  - `"Leaked"` — distributed without authorization (pink)
- `description` — Full description paragraph.
- `content_tags` — Array of short tag strings shown as chips.

**To add a BD**, insert a new object in the correct chapter-order position in the array. Make sure to add a comma after the preceding entry's closing `}`.

**To reorder**, move the entire `{ ... }` block to the correct position.

---

### Editing the Rockerboy Timeline — `rockerboy.json`

The file is a JSON array. Entries are displayed in the order they appear (currently chapter order).

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

**Fields:**

- `event_id` — Catalog ID (e.g. `"RB-001"`). Keep in chapter order.
- `chapter_number` — Chapter the performance occurred in.
- `venue` — Name of the venue or location.
- `location` — District/area (e.g. `"Arroyo, Santo Domingo"`).
- `type` — One of: `"Public Gig"`, `"Private Performance"`, `"Impromptu"`, `"Impromptu Solo"`, `"Studio Session"`, `"Radio / Media"`, `"Corporate Event"`, `"Rehearsal"`
- `band` — Band name if playing with a group (e.g. `"Stand Alone Complex"`), or `null` for solo.
- `context` — Narrative description of what happened.
- `setlist` — Array of song objects. Each has:
  - `song` — Song title
  - `artist` — Artist / source (be specific, e.g. which OST)
  - `youtube_url` — YouTube link, or `null` if not yet added
- `notes` — Short factual footnote (shown in dim monospace at the bottom).

**To add a YouTube link**, find the song entry and replace `null` with the URL in quotes:
```json
"youtube_url": "https://www.youtube.com/watch?v=XXXXXXXXXXX"
```

**To add a new event**, insert a new object in the correct chapter-order position.

---

### JSON Syntax Rules

If the build breaks after an edit, the most common causes are:

1. **Missing comma** — Every item in an array or object needs a comma after it *except the last one*.
   ```json
   { "a": 1 },   ← comma here
   { "b": 2 }    ← no comma on the last entry
   ```
2. **Trailing comma** — A comma *after* the last item in an array or object will also break it.
3. **Unescaped characters** — Apostrophes are fine in JSON strings, but if you need a literal `"` inside a string, escape it as `\"`.
4. **Unclosed brackets** — Every `[` needs a `]` and every `{` needs a `}`.

You can validate your JSON at [jsonlint.com](https://jsonlint.com) before rebuilding.

---

### What NOT to Edit

- `wiki/build/` — Generated HTML. Overwritten every build. Don't touch.
- `wiki/build/assets/style.css` — The stylesheet. Safe to leave alone unless you know CSS.
- `threadmarks_index.json` — Chapter index populated by the scraper.
- `wiki/cache/chapter_summaries.json` — Populated by the scraper. Manual edits are safe but will be overwritten if the scraper runs again on the same chapter.

---

### Rebuilding and Deploying

After editing any cache file, rebuild and deploy from `wiki/scripts/`:

```bash
cd wiki/scripts
python3 build.py --all
```

This regenerates all HTML and uploads the changed files to Neocities. Requires Python 3 (stdlib only — no pip installs needed) and a valid Neocities API key in the environment.
