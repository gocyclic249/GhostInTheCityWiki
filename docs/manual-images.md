# Manual Image Workflow

The media scraper handles most images automatically, but some need manual help. This doc covers the failure modes and how to recover.

## When does manual help kick in?

Three cases:

1. **Dead imgur URL, fake-success download.** Imgur deletes the image but still returns a 200 with a placeholder PNG ("image not found" or similar). The scraper saves the placeholder as if it were the real art. You only notice when you look at the photomode page and see a wrong picture.
2. **SB-hosted hotlink fallback.** When an external image (usually imgur) dies, SpaceBattles sometimes serves its own forum logo as a fallback. Same outcome as #1: the file exists, but it's not the art.
3. **Parser miss.** The scraper never extracted any image URL from the post body — usually because the user posted the image inside a spoiler, attachment block, or non-standard markup the regex didn't catch. The post entry in `media_index.json` has no `images` array at all.

A fourth class — Discord CDN URLs and SB attachments behind Cloudflare — is handled automatically: the scraper now flags those with `needs_manual: true` instead of skipping them silently. They show up in `--show-manual` from the start.

## Step 1: Find what needs help

```bash
python3 scrape_media.py --show-manual
# alias: --list-manual
```

This lists every image that needs attention with a one-word reason: `flagged: discord`, `flagged: sb_attachment`, `flagged: manual`, `no local file`, or `parser miss — no images extracted`. Each entry includes the post URL, the placeholder filename, and the reason.

You can also browse `media_index.json` directly — search for `"needs_manual": true`.

## Step 2: Mark a problem post

If you spot a fake-success image (cases 1 and 2 above) by eyeballing the photomode page, flag it:

```bash
# Single-image post
python3 scrape_media.py --mark-manual 91534014

# Post with multiple images
python3 scrape_media.py --mark-manual 91534014 --count 3
```

For a parser-miss post (case 3), the same command creates placeholder image entries from scratch — pass `--count` to match the number of images you see in the post body.

The command will tell you exactly where to drop the replacement file.

## Step 3: Get the actual image

Several options, in order of effort:

**Option A — From the SpaceBattles thread.**
1. Open the post in a browser (the URL is in the `--show-manual` output).
2. Right-click the image → Save image as…
3. Save it to `wiki/build/media/{post_id}_{N}.{ext}` matching the placeholder filename. Example: `wiki/build/media/91534014_1.png`.

**Option B — From the artist's source (Twitter, Pixiv, ArtStation, etc.).**
If the SB thread links to the original artist post, fetch the original — usually higher resolution.

**Option C — Grok or another AI with live web access.**
Per CLAUDE.md, Grok has live X/social fetching that the local scraper lacks. Useful when the source is on X/Twitter or a Discord channel that's still live:

> Paste the URLs into a Grok session with: "download these images and save them to /tmp" then move the files into wiki/build/media/ with the standard naming.

NotebookLM is a research tool, not a downloader — skip it for this use case.

**Option D — `--grab-sb` for SB attachments.**
SpaceBattles attachments behind Cloudflare can be grabbed via gallery-dl + browser cookies. See the `--grab-sb` section in `scrape_media.py --help`.

## Step 4: Clear the flag

Once the file is in `wiki/build/media/`:

```bash
python3 scrape_media.py --unmark-manual 91534014
```

This verifies the local file exists before clearing the flag — a safety check so you don't mark something complete that still has no image behind it.

## Step 5: Rebuild and review

```bash
python3 wiki/scripts/build.py --build
```

Open `wiki/build/photomode.html` in a browser, scroll to the post, confirm the image renders correctly. **Do not upload to Neocities until the visual check passes.**

Once it looks right:

```bash
python3 wiki/scripts/upload.py
```

The upload script diffs against the manifest and only pushes the new image plus the rebuilt photomode page.

## Schema reference

The `media_index.json` image object now supports two optional fields:

```json
{
  "url": "https://i.imgur.com/Ddc956A.png",
  "local_file": "91534014_1.png",
  "alt_text": "Image 23",
  "needs_manual": true,
  "manual_source": "discord"
}
```

`manual_source` is informational — current values are `discord`, `sb_attachment`, and `manual`. Both fields are optional and backwards-compatible with old entries.

## Quick reference

| Failure mode | How to spot | Recovery |
|---|---|---|
| Dead imgur, fake success | Wrong image on photomode page | `--mark-manual POST_ID`, drop file, `--unmark-manual POST_ID` |
| SB logo placeholder | SB logo on photomode page | Same as above |
| Parser miss | Post has no images in `--show-manual` | `--mark-manual POST_ID --count N`, drop files, `--unmark-manual POST_ID` |
| Discord CDN expired | Auto-flagged on next scrape | Same workflow; source the file from artist directly |
| SB attachment behind CF | Auto-flagged on next scrape | Try `--grab-sb` first; fall back to manual |
