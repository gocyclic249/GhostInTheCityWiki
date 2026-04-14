#!/usr/bin/env python3
"""
cleanup_summaries.py — Sand off AI-generated patterns from chapter summaries.
Applies targeted string transforms to make summaries read less mechanical.
Uses only Python stdlib. Does not change factual content.

Usage:
    python3 cleanup_summaries.py --dry-run     # preview changes, write nothing
    python3 cleanup_summaries.py               # apply changes (auto-backup)
    python3 cleanup_summaries.py --report      # apply + write markdown report
"""

import argparse
import copy
import json
import os
import re
import shutil
import sys

WIKI_DIR   = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE_DIR  = os.path.join(WIKI_DIR, "cache")
SUMMARY_PATH = os.path.join(CACHE_DIR, "chapter_summaries.json")
BACKUP_PATH  = SUMMARY_PATH + ".bak"


# ── Transform functions ───────────────────────────────────────────────────

def strip_paren_xp(text):
    """Remove parenthetical XP values like (500 XP), (knife, 500 XP), (3x 250 XP confirmed)."""
    # Match parens containing XP amounts — may have prefixes like "knife," or suffixes
    text = re.sub(r'\s*\([^)]*?\d[\d,]*\s*XP[^)]*?\)', '', text)
    return text


def strip_paren_stat_blocks(text):
    """Remove parenthetical stat dumps like (Body 5, Reflex 3, Cool 2)."""
    STAT_WORDS = {
        'body', 'reflex', 'reflexes', 'cool', 'intelligence', 'technical',
        'ninjutsu', 'cold blood', 'athletics', 'annihilation', 'blades',
        'assault', 'handguns', 'breach', 'programming', 'engineering',
        'crafting', 'street brawler', 'quick hacks', 'level'
    }

    def is_stat_block(match):
        content = match.group(1).lower()
        words = re.findall(r'[a-z]+', content)
        if not words:
            return False
        stat_hits = sum(1 for w in words if w in STAT_WORDS)
        # If >40% of words are stat-related and there's a number, strip it
        has_number = bool(re.search(r'\d', content))
        return has_number and stat_hits / len(words) > 0.4

    def replacer(match):
        if is_stat_block(match):
            return ''
        return match.group(0)

    text = re.sub(r'\s*\(([^)]{10,})\)', replacer, text)
    return text


def soften_inline_xp(text):
    """Remove or soften inline XP/level references outside parentheses."""
    # "The system awarded N XP and Cold Blood Level 1" → "The system registered Cold Blood Level 1"
    text = re.sub(
        r'The\s+(?:system|kill)\s+(?:award(?:s|ed)?|earn(?:s|ed)?)\s+\d[\d,]*\s*XP\s+and\s+',
        'The system registered ', text
    )
    # "The system awarded N XP:" → "The system registered:"
    text = re.sub(
        r'The\s+(?:system|kill)\s+(?:award(?:s|ed)?|earn(?:s|ed)?)\s+\d[\d,]*\s*XP\s*[:]\s*',
        'The system registered ', text
    )
    # "The kill awards N XP" (standalone, no continuation) → remove
    text = re.sub(
        r'The\s+(?:system|kill)\s+(?:award(?:s|ed)?|earn(?:s|ed)?)\s+\d[\d,]*\s*XP\b[.;,]?\s*',
        '', text
    )

    # "awarded/earns N XP and..." — generic verb form
    text = re.sub(r'\b(?:award(?:s|ed)?|earn(?:s|ed)?|gain(?:s|ed)?)\s+(?:her\s+)?\d[\d,]*\s*XP\s+and\s+', '', text)
    text = re.sub(r'\b(?:award(?:s|ed)?|earn(?:s|ed)?|gain(?:s|ed)?)\s+(?:her\s+)?\d[\d,]*\s*XP\b[.;,]?\s*', '', text)

    # Leading XP amounts at start of paragraph — MUST run before generic strip
    text = re.sub(r'^\d[\d,]*\s*XP\s+from\s+', 'The haul from ', text)

    # "N XP per song;" → strip the whole clause
    text = re.sub(r'\d[\d,]*\s*XP\s+per\s+\w+[;,.]\s*', '', text)

    # "— N XP" leftover fragments
    text = re.sub(r'\s*—\s*\d[\d,]*\s*(?:XP)?\s*[,;.]?\s*', ' ', text)

    # "N XP" as standalone (generic catch-all — runs last)
    text = re.sub(r'\b\d[\d,]*\s*XP\b', '', text)

    # If generic strip left "from ..." at the start
    text = re.sub(r'^\s*from\s+', 'The haul from ', text)

    # Orphaned "per song;" / "per kill;" after XP number was stripped
    text = re.sub(r'\.\s*per\s+\w+[;,]\s*', '. ', text)

    return text


def strip_trailing_stat_sentences(text):
    """Remove final sentences that are purely stat announcements."""
    STAT_PATTERN = re.compile(
        r'(?:Body|Reflex(?:es)?|Cool|Intelligence|Technical|Ninjutsu|'
        r'Cold Blood|Athletics|Annihilation|Blades?|Assault|Handguns?|'
        r'Breach Protocol|Programming|Engineering|Crafting|Street Brawl(?:er|ing)|'
        r'Quick Hacks?|Rockerboy|Level|levels?|hits?|reaches?|rises?|ticks?|'
        r'unlocks?|gained|XP)\b',
        re.IGNORECASE
    )

    sentences = re.split(r'(?<=[.!?])\s+', text.strip())
    if len(sentences) < 2:
        return text

    last = sentences[-1]
    words = re.findall(r'[a-zA-Z]+', last)
    if not words:
        return text

    stat_hits = len(STAT_PATTERN.findall(last))
    ratio = stat_hits / len(words)

    # If >50% of the last sentence is stat-speak, drop it
    if ratio > 0.5 and len(words) > 3:
        return ' '.join(sentences[:-1])

    return text


def vary_motoko_opener(text, para_index):
    """On paragraph 2+, replace leading 'Motoko' with 'She' / 'Her'."""
    if para_index == 0:
        return text

    if text.startswith("Motoko's "):
        text = "Her " + text[len("Motoko's "):]
    elif text.startswith("Motoko "):
        text = "She " + text[len("Motoko "):]

    return text


def reduce_semicolons(text):
    """Replace 2nd+ semicolons in a paragraph with periods."""
    parts = text.split('; ')
    if len(parts) <= 2:
        return text

    # Keep the first semicolon, convert the rest to periods
    result = parts[0] + '; ' + parts[1]
    for part in parts[2:]:
        if part and part[0].islower():
            part = part[0].upper() + part[1:]
        result += '. ' + part

    return result


def vary_then_transitions(text):
    """Replace every other ', then ' with a sentence break."""
    ALTS = ['. She ', '. From there, she ']
    count = [0]

    def replacer(match):
        count[0] += 1
        if count[0] % 2 == 0:
            return ALTS[(count[0] // 2) % len(ALTS)]
        return match.group(0)

    return re.sub(r',\s+then\s+', replacer, text)


def strip_em_dashes(text):
    """Replace em-dashes with periods. CLAUDE.md forbids them outright."""
    if '—' not in text and '–' not in text:
        return text
    text = re.sub(r'\s*[—–]\s*', '. ', text)
    text = re.sub(r'(\.\s+)([a-z])', lambda m: m.group(1) + m.group(2).upper(), text)
    return text


def strip_forbidden_transitions(text):
    """Drop sentence-leading 'Meanwhile', 'However', 'Furthermore', 'Additionally'.

    These read as AI essay-mode. CLAUDE.md forbids them. We strip the word
    plus its trailing comma; the next sentence stands on its own.
    """
    text = re.sub(
        r'(^|(?<=[.!?]\s))(Meanwhile|However|Furthermore|Additionally)\s*,?\s*([a-z])',
        lambda m: m.group(1) + m.group(3).upper(),
        text
    )
    return text


def collapse_whitespace(text):
    """Clean up double-spaces, leading/trailing whitespace, orphaned punctuation."""
    text = re.sub(r'  +', ' ', text)
    text = re.sub(r'\s+([,;.!?])', r'\1', text)
    text = re.sub(r'([,;])\s*([,;.!?])', r'\2', text)  # orphaned comma before period
    text = re.sub(r'\.\s*\.', '.', text)  # double periods
    text = re.sub(r'—\s*[,;.]\s*', '— ', text)  # dash then orphan punctuation
    text = re.sub(r'\s*—\s*—\s*', ' — ', text)  # double dashes
    # Capitalize after periods
    text = re.sub(r'([.!?])\s+([a-z])', lambda m: m.group(1) + ' ' + m.group(2).upper(), text)
    text = text.strip()
    return text


# ── Pipeline ──────────────────────────────────────────────────────────────

def cleanup_paragraph(text, para_index):
    """Apply all transforms to a single paragraph."""
    text = strip_paren_xp(text)
    text = strip_paren_stat_blocks(text)
    text = soften_inline_xp(text)
    text = strip_trailing_stat_sentences(text)
    text = vary_motoko_opener(text, para_index)
    text = reduce_semicolons(text)
    text = vary_then_transitions(text)
    text = strip_em_dashes(text)
    text = strip_forbidden_transitions(text)
    text = collapse_whitespace(text)
    return text


def cleanup_entry(entry):
    """Clean up all summary paragraphs in a chapter entry."""
    summary = entry.get("summary")
    if not summary or not isinstance(summary, list):
        return entry, False

    new_summary = []
    changed = False
    for i, para in enumerate(summary):
        cleaned = cleanup_paragraph(para, i)
        if cleaned != para:
            changed = True
        # Safety: don't let a paragraph lose >30% of its length
        if len(cleaned) < len(para) * 0.7 and len(para) > 50:
            cleaned = para  # revert — too aggressive
            changed = False
        new_summary.append(cleaned)

    entry["summary"] = new_summary
    return entry, changed


# ── Diff display ──────────────────────────────────────────────────────────

RED   = '\033[91m'
GREEN = '\033[92m'
DIM   = '\033[2m'
RESET = '\033[0m'
BOLD  = '\033[1m'


def print_diff(chapter_num, old_paras, new_paras):
    """Print a colored before/after diff for a chapter."""
    print(f"\n{BOLD}=== Chapter {chapter_num} ==={RESET}")
    for i, (old, new) in enumerate(zip(old_paras, new_paras)):
        if old != new:
            print(f"  {DIM}Paragraph {i + 1}:{RESET}")
            print(f"  {RED}- {old[:200]}{'...' if len(old) > 200 else ''}{RESET}")
            print(f"  {GREEN}+ {new[:200]}{'...' if len(new) > 200 else ''}{RESET}")


def write_report(changes, report_path):
    """Write a markdown report of all changes."""
    with open(report_path, 'w', encoding='utf-8') as f:
        f.write("# Summary Cleanup Report\n\n")
        f.write(f"**Chapters changed:** {len(changes)}\n\n")
        for ch_num, old_paras, new_paras in changes:
            f.write(f"## Chapter {ch_num}\n\n")
            for i, (old, new) in enumerate(zip(old_paras, new_paras)):
                if old != new:
                    f.write(f"**Paragraph {i + 1}:**\n\n")
                    f.write(f"~~{old}~~\n\n")
                    f.write(f"{new}\n\n")
            f.write("---\n\n")
    print(f"Report written to {report_path}")


# ── Main ──────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Clean AI patterns from chapter summaries")
    parser.add_argument('--dry-run', action='store_true', help="Preview changes without writing")
    parser.add_argument('--report', action='store_true', help="Write a markdown report of changes")
    parser.add_argument('--chapter', type=int, help="Process only this chapter number")
    args = parser.parse_args()

    if not os.path.exists(SUMMARY_PATH):
        print(f"ERROR: {SUMMARY_PATH} not found")
        sys.exit(1)

    with open(SUMMARY_PATH, encoding='utf-8') as f:
        data = json.load(f)

    original = copy.deepcopy(data)
    changes = []
    total_changed = 0

    for key, entry in data.items():
        ch_num = entry.get("chapter_num", "?")

        if args.chapter is not None and ch_num != args.chapter:
            continue

        old_summary = entry.get("summary", [])
        if not old_summary:
            continue

        old_paras = list(old_summary)
        entry, changed = cleanup_entry(entry)

        if changed:
            total_changed += 1
            changes.append((ch_num, old_paras, entry["summary"]))
            if args.dry_run:
                print_diff(ch_num, old_paras, entry["summary"])

    print(f"\n{'[DRY RUN] ' if args.dry_run else ''}Chapters changed: {total_changed}/{len(data)}")

    if args.dry_run:
        return

    # Backup
    if os.path.exists(SUMMARY_PATH):
        shutil.copy2(SUMMARY_PATH, BACKUP_PATH)
        print(f"Backup saved to {BACKUP_PATH}")

    # Write
    with open(SUMMARY_PATH, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print(f"Updated {SUMMARY_PATH}")

    if args.report:
        report_path = os.path.join(CACHE_DIR, "cleanup_report.md")
        write_report(changes, report_path)


if __name__ == "__main__":
    main()
