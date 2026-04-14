---
description: Generate chapter summaries from raw chapter text. Accepts chapter numbers or ranges.
---

# Process Chapter

Generate wiki summaries for the specified chapters: $ARGUMENTS

Parse the arguments as space-separated chapter numbers or ranges (e.g., `241 242` or `240-242`).

## Steps

### 1. Preparation

For each chapter number:
1. Read `threadmarks_index.json` to get the `chapter_id` and `date` (array index + 1 = chapter number)
2. Read the raw chapter file: `chapters/{NNNN}_{N}._Chapter_{N}.md` (NNNN is zero-padded to 4 digits)
3. Read `wiki/cache/chapter_summaries.json` to check if an entry already exists
4. If an entry exists, warn the user and ask before overwriting

### 2. Calibrate Voice

Before writing any summary:
1. Read 2-3 existing summaries from `wiki/cache/chapter_summaries.json` near the target chapter number to calibrate tone and detail level
2. Review the style guide in CLAUDE.md carefully

Here are two reference summaries showing the target voice:

**Chapter 1 (no kills, setup chapter):**
> A gamer from our world wakes up in Night City, 2075, in the body of fourteen-year-old Kusanagi Motoko. Stripped of cyberware by Scavs, rescued, and coma-bound for a year. She can't walk, can't remember being Motoko, and the doctors couldn't care less. The Cyberpunk setting clicks into place fast, and with it the terror of knowing exactly how disposable a weak, unchipped kid is in this city.
>
> Hot-headed Tyger Claw enforcer Junichiro "Jun-Nii" Kusanagi storms into the hospital room with a katana on his hip and fire in his hair, swearing his little sister is safe. He brings her home to a cramped Japantown apartment reeking of old incense and burrito wrappers. Between awkward sibling bonding and wheelchair-bound leg raises, she starts piecing together the life of the girl she replaced. Generational Tyger Claw family, dead parents, and a box of blood-stained clothes.
>
> Buried at the bottom of that box: a shard labelled "Gema / Gamer" in a pristine case. She slots it, blacks out, and wakes to find the Cyberpunk 2077 stat screen burning in her HUD. Body, Reflexes, Cool, Technical Ability, Intelligence, all scraping the floor. The first notification pops after a set of leg raises. By nightfall she discovers the system's instant-sleep recovery, and the rested buff glowing behind her eyelids seals it. The grind has begun.

**Chapter 4 (3 kills, first combat):**
> Motoko hits the baseline stats of the game's protagonist V and Jun takes her to the secret Tyger Claw underground shooting range beneath a compound in Little China. A grizzled range master watches her quick-draw and is impressed enough to hand over a Saratoga SMG for testing. She spends an hour teaching Jun the same draw technique. Keeping her brother alive matters more than one session of grinding.
>
> Hiromi drags everyone into a car-theft gig against Gonzales, a fake-Valentino drug pusher working the Kabuki shanty town. The plan falls apart fast: Omaeda can't crack the car's security, Malcolm's distraction act wears thin, and Hiromi gets pistol-whipped unconscious by one of Gonzales's guards. Ichi tries to bluff his way through the confrontation alone. When both guards raise their SMGs on him, Motoko creeps up behind all three, steals the chromed revolver off Gonzales's hip, and opens fire with both hands. Unity in the right, stolen revolver in the left.
>
> Both guards drop. Gonzales lunges at Ichi and catches a round for it. Three dead, Motoko coated in someone else's blood, and the whole crew staring at her like she might be the next thing they need to worry about. She loots the bodies on autopilot, then drives Hiromi's bike home in a dissociative haze while a Tyger Claw woman at the club washes the gore off her face. The soda she's given is sweet. The spilled puddle on the table is red. She pukes on Jun's shoes.

### 3. Generate Summary

Read the full chapter text carefully, then write a summary following these rules:

**Structure:**
- 2-4 paragraphs, each covering a distinct scene beat
- 2-4 sentences per paragraph
- Third person, past tense

**Voice (from CLAUDE.md style guide):**
- Punchy, dry, street-level. Match the energy of the reference summaries above.
- Tone vocabulary for "punchy, dry": short sentences, action verbs first, minimal adjectives, no hedging, no editorializing.
- Slang density: at least one piece of Night City slang per summary, no more than two per paragraph. Use "preem", "choom", "chrome", "eddies", "chipped in", "gonk", "nova", "delta", "scop". If it feels forced, drop it.
- Keep dark humor when the chapter has it.
- NO: XP values, stat numbers, level-up announcements, perk names.
- NO: "Meanwhile", "However", "Furthermore", "Additionally" (transition words read as AI).
- When a game mechanic matters, describe the capability, not the number.

> **CRITICAL: NO EM-DASHES.** Em-dashes (`—` or ` — `) are the #1 AI-tell and the cleanup script does strip them, but the goal is zero hits. Use periods, commas, or sentence breaks instead. This rule has zero exceptions.

**Paragraph openers — vary across the summary. Acceptable patterns:**
- "Motoko" (use sparingly, never twice in a row)
- "She" / "Her"
- A verb-first sentence ("Walked into the bar..." / "Took the shard...")
- A location ("In Japantown...")
- A character other than Motoko ("Jun-Nii...", "Hiromi...")
- A dialogue beat or quoted line

**Kill counting:**
- Count only kills Motoko directly causes
- Confirmed deaths only. Unconscious/incapacitated does not count unless the text says they died.
- When ambiguous, undercount and note the ambiguity in kill_notes
- Write a kill_notes string explaining the count or the absence of kills

**Detection flags** (print these after the summary if found):
- **Braindance**: If Motoko records or releases a BD in this chapter, flag it with chapter number and suggested BD entry
- **New character**: If a new named character appears in a significant role (not one-line mentions), flag for potential addition to characters.json
- **Rockerboy**: If Motoko performs music, flag for rockerboy.json

### 4. Write to Cache

1. Read the current `wiki/cache/chapter_summaries.json`
2. Add or update the entry keyed by `chapter_id` (string)
3. Write the updated JSON back, preserving all existing entries
4. Use `indent=2` and `ensure_ascii=False` for the JSON output

### 5. Validate

Run: `python3 wiki/scripts/cleanup_summaries.py --chapter {N} --dry-run`

If the cleanup script finds patterns to fix, revise the summary to eliminate them before they need automated cleanup. The goal is zero changes from the cleanup pass.

### 6. Report

Print a summary for each processed chapter:
```
Chapter {N}: {title}
  Kills: {count}
  Kill notes: {notes}
  Paragraphs: {count}
  [FLAGS if any]
```
