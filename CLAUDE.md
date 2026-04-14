# Ghost in the City Wiki

Fan wiki for *Ghost in the City*, a Cyberpunk 2077 / Ghost in the Shell crossover SI fanfic by **Seras** on SpaceBattles and AO3.

## Project Overview

This is a fan wiki project (Neocities-hosted). The main workflow is: scrape/update data → rebuild wiki pages → deploy to Neocities. Always confirm which branch and which script version before running anything.

## Project Layout

```
chapters/                      # Raw chapter markdown from AO3 (242 chapters)
sidestories/                   # Side story markdown from SpaceBattles
wiki/
  cache/                       # JSON data caches (edit these for wiki content)
    chapter_summaries.json     # Chapter recaps + kill counts
    braindances.json           # BD catalog
    characters.json            # Character profiles
    rockerboy.json             # Music performances
  build/                       # Generated HTML (do not edit directly)
  scripts/
    build.py                   # Build orchestrator
    build_html.py              # HTML renderer
    cleanup_summaries.py       # AI pattern removal (safety net)
    upload.py                  # Neocities uploader
lib/                           # Shared Python utilities
scripts/debug/                 # Debug & fallback image-recovery scripts
threadmarks_index.json         # Chapter metadata index
sidestories_index.json         # Side story metadata index
media_index.json               # Media threadmark index + image metadata
update_wiki.py                 # Full pipeline orchestrator
scrape.py                      # AO3 chapter scraper
scrape_media.py                # SpaceBattles media scraper (images)
scrape_sidestories.py          # SpaceBattles side story index scraper
```

## Chapter File Convention

Chapter files: `chapters/{NNNN}_{N}._Chapter_{N}.md`
- NNNN is zero-padded to 4 digits, N is the chapter number
- Example: Chapter 42 -> `chapters/0042_42._Chapter_42.md`

To resolve chapter number -> chapter_id: read `threadmarks_index.json` (array of objects with `chapter_id`, `title`, `date`, `ao3_url`). The array index + 1 = chapter number.

## JSON Schemas

### chapter_summaries.json
```json
{
  "chapter_id_string": {
    "chapter_num": 1,
    "title": "1. Chapter 1",
    "date": "2022-10-15",
    "summary": [
      "Paragraph 1...",
      "Paragraph 2...",
      "Paragraph 3..."
    ],
    "kills": 0,
    "kill_notes": "No kills -- description of what happened"
  }
}
```

### braindances.json
```json
[
  {
    "bd_id": "BD-001",
    "title": "Kamikaze Raid",
    "chapter_number": 40,
    "status": "Released",
    "description": "Narrative description...",
    "content_tags": ["combat", "stealth"]
  }
]
```

### characters.json
```json
{
  "slug": {
    "name": "Full Name",
    "role": "Role",
    "faction": "Faction",
    "affiliation": "Allegiance",
    "status": "Active",
    "first_chapter": 1,
    "icon": "&#x2620;",
    "description": "One-line summary",
    "physical_description": "Appearance paragraph",
    "bio": ["Background paragraph 1", "Background paragraph 2"]
  }
}
```

## Pipeline

### Automated (runs via `update_wiki.py` or cron)
1. `scrape.py --update` downloads new chapters from AO3
2. `scrape_sidestories.py` refreshes side story index from SpaceBattles
3. `scrape_media.py` refreshes media index + downloads new images
4. `build.py --build` renders JSON cache to static HTML
5. `build.py --all` or `upload.py` deploys to Neocities

### Manual (requires Claude session for new chapters)
6. `/process-chapter N` generates summaries for new chapters
7. `/fact-check N` verifies summary accuracy against source text
8. Review new chapters for braindance entries (`braindances.json`)
9. Review new chapters for rockerboy performances (`rockerboy.json`)
10. `cleanup_summaries.py` strips any remaining AI patterns (safety net)
11. Rebuild + upload after manual updates

## Manual Image Workflow

Some media images can't be scraped automatically: dead imgur URLs that return placeholder PNGs (fake-success downloads), SB-served logo fallbacks, parser misses, Discord CDN expirations, and Cloudflare-blocked SB attachments. The recovery procedure lives in [`docs/manual-images.md`](docs/manual-images.md). Quick commands:

- `python3 scrape_media.py --show-manual` — list every image needing attention
- `python3 scrape_media.py --mark-manual POST_ID [--count N]` — flag a post for manual replacement (creates placeholders if the post has no images yet)
- `python3 scrape_media.py --unmark-manual POST_ID` — clear the flag once a real file is in `wiki/build/media/`

## Deployment

When deploying to Neocities, always verify the deployed files match the local build output. Stale deployed files have caused bugs before.

## Scripts & Scrapers

When running scrapers or build scripts, ask which specific script and branch the user wants before executing. Do NOT run download/scrape operations when the user only asks for index/metadata generation.

## Writing Style Guide

Derived from Seras's own prose (sampled across chapters 1, 50, 100, 200, 242).

### Seras's Voice

Seras writes first-person present-tense with these patterns:
- Short punchy fragments as standalone beats: "No thanks." / "Good enough." / "That wasn't my voice."
- Self-interrupting internal monologue: "I mean friends!" / "I definitely didn't cry though. Fuck you."
- Casual Night City slang: "preem", "choom", "chrome", "eddies", "chipped in", "gonk", "nova", "delta"
- Dry humor under pressure: joking during surgery, snarking at corpos mid-op
- Run-on conversational cadence: "It made me feel even more helpless. Realizing that these doctors taking care of me, they literally didn't care about me."
- Game system references woven casually: "I had a stat point" not "the system awarded +1 Body"

### Summary Style Rules

Summaries translate Seras's voice into third-person past-tense recaps:
- Match Seras's punchy, dry energy. Street slang, no literary filler.
- **Tone vocabulary** for "punchy, dry": short sentences, action verbs first, minimal adjectives, no hedging, no editorializing.
- **NO em-dashes** (`—` or ` — `). They read as AI-generated. Use periods, commas, or sentence breaks instead. Cleanup script strips them automatically; the goal is zero hits.
- Summaries should feel like Motoko would approve of how they read.
- **Slang density**: at least one piece of Night City slang per summary, no more than two per paragraph. Use "preem", "choom", "chrome", "eddies", "chipped in", "gonk", "nova", "delta", "scop". If a slang word feels forced, drop it.
- Keep the dark humor. If the chapter is funny, the summary should be too.
- **Never include**: XP values, stat numbers, level-up announcements, perk names, "Meanwhile", "However", "Furthermore", "Additionally".
- When a game mechanic matters to the plot, describe the capability gained, not the number.
- Vary paragraph openers. Not every paragraph starts with "Motoko".
- 2-4 paragraphs per chapter, each covering a distinct scene beat.
- 2-4 sentences per paragraph.

### Kill Counting Rules

- Only count kills Motoko directly causes.
- Confirmed kills only. Unconscious or incapacitated targets do not count unless the text says they died.
- Write a `kill_notes` string explaining the count or explaining why there were no kills.
- When in doubt, undercount and note the ambiguity in kill_notes.
