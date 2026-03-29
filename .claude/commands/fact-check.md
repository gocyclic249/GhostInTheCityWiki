---
description: Fact-check chapter summaries, braindances, or character bios against source text.
---

# Fact Check

Verify wiki content accuracy against source chapter text for: $ARGUMENTS

Parse arguments as:
- Chapter numbers or ranges: `1 2 3`, `1-5`, `240-242`
- `--all` to check all chapter summaries (processes one at a time)
- `--braindances` to check braindances.json entries
- `--characters` to check characters.json entries
- `--rockerboy` to check rockerboy.json entries
- `--fix` to apply corrections (default: report only, no changes)

## Verification Process

### For Chapter Summaries

For each chapter number:

1. **Load data**: Read the summary entry from `wiki/cache/chapter_summaries.json` and the full chapter text from `chapters/{NNNN}_{N}._Chapter_{N}.md`

2. **Read the entire chapter carefully**, then check the summary for these error types:

   **CRITICAL errors** (factually wrong):
   - **Fabricated events**: Things described in the summary that do not appear in the chapter
   - **Wrong names**: Characters attributed to actions they did not perform
   - **Wrong locations**: Places mentioned that differ from the chapter
   - **Incorrect kill counts**: Kills counted that did not happen, or confirmed kills missed
   - **Misattributed dialogue or actions**: Mixing up which character said or did what

   **MODERATE errors** (misleading):
   - **Wrong sequence**: Events described in a different order, implying wrong causation
   - **Conflated scenes**: Two separate events merged into one in a way that changes meaning
   - **Missing context**: A described event is technically correct but omits crucial context that changes its meaning

   **MINOR errors** (imprecise):
   - **Imprecise wording**: Description is close but not quite right (e.g., "sword" when it was a "knife")
   - **Significant omissions**: Major plot beats present in the chapter but absent from the summary
   - **Tone mismatch**: Summary misrepresents the emotional register of a scene (e.g., describing a comedic moment as serious)

3. **Check kill count**: Compare the `kills` field against what actually happens in the chapter. Count only confirmed kills by Motoko. Note any ambiguous cases.

4. **Check kill_notes**: Verify the kill_notes accurately describe what happened.

5. **Style check** (non-blocking, just note):
   - Em-dashes present? (should not be)
   - XP values or stat numbers? (should not be)
   - Starts every paragraph with "Motoko"? (should vary)
   - Uses "Meanwhile", "However", "Furthermore"? (should not)

### For Braindances (--braindances)

For each entry in `wiki/cache/braindances.json`:
1. Read the chapter referenced by `chapter_number`
2. Verify a BD recording or release actually occurs in that chapter
3. Check the `title` and `description` match what happens
4. Check `content_tags` are accurate
5. Check `status` is correct (Released, Personal Only, etc.)

### For Characters (--characters)

For each entry in `wiki/cache/characters.json`:
1. Read the chapter referenced by `first_chapter`
2. Verify the character actually appears in that chapter
3. Check `role`, `faction`, `affiliation` against the source
4. Check `bio` paragraphs for factual accuracy against their appearance chapters
5. For characters with `cp_stats`: note these are game-mechanic data and may not be directly verifiable from prose

### For Rockerboy (--rockerboy)

For each entry in `wiki/cache/rockerboy.json`:
1. Read the referenced chapter
2. Verify the performance actually occurs
3. Check details (song names, venue, audience) against source

## Output Format

For each checked entry, print:

```
## Chapter {N}: {title}
Status: PASS | FAIL

[If FAIL, list each error:]

### Error 1: {error type} (CRITICAL|MODERATE|MINOR)
Summary says: "{quoted text from summary}"
Source says: "{quoted text from chapter}"
Suggested fix: "{corrected text}"

[After all errors:]
Kill count: {summary says X, source shows Y} - CORRECT | INCORRECT

[Style notes if any:]
Style: {notes about em-dashes, stat numbers, etc.}
```

## Applying Fixes (--fix flag)

Only if `--fix` is passed in the arguments:
1. Show the full error report first
2. Ask the user to confirm before applying changes
3. Update `wiki/cache/chapter_summaries.json` (or the relevant cache file)
4. Run `python3 wiki/scripts/cleanup_summaries.py --chapter {N} --dry-run` to validate

Without `--fix`, this command is read-only. It reports problems but changes nothing.

## When checking --all

Process chapters one at a time to stay within context limits. Print a running tally:
```
Checked: {N}/{total} | Pass: {X} | Fail: {Y}
```

After completing all chapters, print a summary:
```
## Fact Check Complete
Total checked: {N}
Passed: {X}
Failed: {Y}
Critical errors: {count}
Moderate errors: {count}
Minor errors: {count}

Chapters with errors: {list of chapter numbers}
```
