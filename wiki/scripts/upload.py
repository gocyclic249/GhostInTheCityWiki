#!/usr/bin/env python3
"""
upload.py — Incremental uploader to Neocities REST API.
Uses only Python stdlib (urllib, hashlib, os, json).

Reads NEOCITIES_API_KEY from environment.
Tracks uploaded file SHA1 hashes in cache/upload_manifest.json to
only upload changed/new files and delete removed files.

Paths under PROTECTED_PREFIXES ("media/") are never deleted: wiki/build/media/
is gitignored, so a clone has no local copy and Neocities is the store of
record. run_upload restores those files before diffing.

Usage:
  python3 upload.py                      # restore missing media, then upload
  python3 upload.py --dry-run            # report changes, upload nothing
  python3 upload.py --status             # live site info
  python3 upload.py --restore-media      # pull missing media back, no upload
  python3 upload.py --restore-media --dry-run
"""

import hashlib
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

if sys.version_info < (3, 8):
    sys.exit("upload.py requires Python 3.8+ (uses walrus operator).")

# ── Paths ──────────────────────────────────────────────────────────────────

WIKI_DIR      = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BUILD_DIR     = os.path.join(WIKI_DIR, "build")
MANIFEST_PATH = os.path.join(WIKI_DIR, "cache", "upload_manifest.json")

NEOCITIES_API = "https://neocities.org/api"

SITE_BASE = "https://ghostinthecity.neocities.org"

# Paths under these prefixes exist only on Neocities — wiki/build/media/ is
# gitignored, so a fresh clone has none of them locally. Deleting them because
# they are "missing" would wipe the fan art off the live site.
PROTECTED_PREFIXES = ("media/",)


def is_protected(rel_path):
    """True if rel_path must never be deleted from the live site."""
    if not isinstance(rel_path, str):
        raise TypeError(f"rel_path must be str, got {type(rel_path).__name__}")
    return rel_path.startswith(PROTECTED_PREFIXES)


def compute_changes(manifest, local_hashes):
    """Diff the manifest against local files.

    Returns (to_upload, to_delete, missing_protected). Protected paths that are
    missing locally are reported, never deleted.
    """
    if not isinstance(manifest, dict) or not isinstance(local_hashes, dict):
        raise TypeError("manifest and local_hashes must both be dicts")

    to_upload = sorted(rel for rel, sha in local_hashes.items()
                       if manifest.get(rel) != sha)
    missing = [rel for rel in manifest if rel not in local_hashes]
    to_delete = sorted(rel for rel in missing if not is_protected(rel))
    missing_protected = sorted(rel for rel in missing if is_protected(rel))
    return to_upload, to_delete, missing_protected


def plan_restore(remote_files, local_paths):
    """Which protected files exist remotely but not locally.

    remote_files: the "files" list from GET /api/list.
    Returns a sorted list of (path, sha1_hash) tuples.
    """
    if not isinstance(remote_files, list):
        raise TypeError(f"remote_files must be a list, got {type(remote_files).__name__}")

    wanted = []
    for entry in remote_files:
        path = entry.get("path", "")
        if entry.get("is_directory"):
            continue
        if not path or not is_protected(path):
            continue
        if path in local_paths:
            continue
        wanted.append((path, entry.get("sha1_hash", "")))
    return sorted(wanted)


def verify_download(content, content_type, expected_sha1):
    """True if content is a real image matching the remote hash.

    A Neocities miss returns an HTML error page. Writing that to media/foo.png
    would look like a successful restore and render as a broken image.
    """
    if not isinstance(content, bytes):
        raise TypeError("content must be bytes")
    if not content:
        return False
    mime = content_type.split(";")[0].strip().lower()
    if not mime.startswith("image/"):
        return False
    if expected_sha1 and hashlib.sha1(content).hexdigest() != expected_sha1:
        return False
    return True


# ── Credentials ───────────────────────────────────────────────────────────

def get_api_key():
    key = os.environ.get("NEOCITIES_API_KEY", "").strip()
    if not key:
        print("ERROR: NEOCITIES_API_KEY environment variable not set.")
        sys.exit(1)
    return key


# ── Manifest ──────────────────────────────────────────────────────────────

def load_manifest():
    if os.path.exists(MANIFEST_PATH):
        with open(MANIFEST_PATH, encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_manifest(manifest):
    with open(MANIFEST_PATH, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)


def sha1_file(path):
    h = hashlib.sha1()
    with open(path, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


# ── Local file scan ────────────────────────────────────────────────────────

def scan_build_dir():
    """Return {neocities_path: local_abs_path} for all files in build/."""
    result = {}
    for dirpath, _, filenames in os.walk(BUILD_DIR):
        for fname in filenames:
            abs_path = os.path.join(dirpath, fname)
            # Neocities path: relative to build/, using forward slashes
            rel = os.path.relpath(abs_path, BUILD_DIR).replace(os.sep, "/")
            result[rel] = abs_path
    return result


# ── Multipart/form-data encoder (stdlib) ──────────────────────────────────

BOUNDARY = b"----GitcWikiBoundary7x3k9"


def encode_multipart(fields):
    """
    fields: list of (name, filename_or_None, content_bytes, content_type_or_None)
    Returns (body_bytes, content_type_header_value).
    """
    parts = []
    for name, filename, data, ctype in fields:
        disp = f'Content-Disposition: form-data; name="{name}"'
        if filename:
            disp += f'; filename="{filename}"'
        header = disp.encode()
        if ctype:
            header += f"\r\nContent-Type: {ctype}".encode()
        parts.append(b"--" + BOUNDARY + b"\r\n" + header + b"\r\n\r\n" + data + b"\r\n")

    body = b"".join(parts) + b"--" + BOUNDARY + b"--\r\n"
    ctype_header = f"multipart/form-data; boundary={BOUNDARY.decode()}"
    return body, ctype_header


def guess_mime(filename):
    ext = os.path.splitext(filename)[1].lower()
    return {
        ".html": "text/html",
        ".css":  "text/css",
        ".js":   "application/javascript",
        ".png":  "image/png",
        ".jpg":  "image/jpeg",
        ".jpeg": "image/jpeg",
        ".gif":  "image/gif",
        ".svg":  "image/svg+xml",
        ".ico":  "image/x-icon",
        ".txt":  "text/plain",
        ".json": "application/json",
    }.get(ext, "application/octet-stream")


# ── Neocities API calls ────────────────────────────────────────────────────

def api_request(endpoint, method="GET", body=None, content_type=None, api_key=None):
    """Make a Neocities API request. Returns parsed JSON dict."""
    url = f"{NEOCITIES_API}/{endpoint}"
    headers = {"Authorization": f"Bearer {api_key}"}
    if content_type:
        headers["Content-Type"] = content_type

    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body_txt = e.read().decode("utf-8", errors="replace")
        print(f"  HTTP {e.code}: {body_txt[:200]}")
        return {"result": "error", "message": f"HTTP {e.code}"}
    except Exception as ex:
        print(f"  Request error: {ex}")
        return {"result": "error", "message": str(ex)}


def neocities_upload(file_fields, api_key):
    """Upload one or more files. file_fields: list of (nc_path, local_path)."""
    fields = []
    for nc_path, local_path in file_fields:
        with open(local_path, "rb") as f:
            data = f.read()
        mime = guess_mime(local_path)
        fields.append((nc_path, nc_path, data, mime))

    body, ctype = encode_multipart(fields)
    result = api_request("upload", method="POST", body=body,
                         content_type=ctype, api_key=api_key)
    return result.get("result") == "success"


def neocities_delete(nc_paths, api_key):
    """Delete files from Neocities. nc_paths: list of strings."""
    # Neocities delete accepts multiple filenames[] params
    params = "&".join(
        f"filenames[]={urllib.parse.quote(p)}"
        for p in nc_paths
    )
    body = params.encode()
    ctype = "application/x-www-form-urlencoded"
    result = api_request("delete", method="POST", body=body,
                         content_type=ctype, api_key=api_key)
    return result.get("result") == "success"


def neocities_info(api_key):
    return api_request("info", api_key=api_key)


def neocities_list(api_key):
    """Every file on the live site, with sha1 hashes. Returns [] on error."""
    result = api_request("list", api_key=api_key)
    if result.get("result") != "success":
        print(f"  ERROR: could not list remote files: {result.get('message', '?')}",
              file=sys.stderr)
        return []
    return result.get("files", [])


def download_file(url, attempts=3):
    """Fetch a public URL. Returns (content, content_type) or (None, "")."""
    if attempts < 1:
        raise ValueError(f"attempts must be >= 1, got {attempts}")
    for attempt in range(attempts):
        try:
            req = urllib.request.Request(
                url, headers={"User-Agent": "gitc-wiki-restore/1.0"})
            with urllib.request.urlopen(req, timeout=60) as resp:
                return resp.read(), resp.headers.get("Content-Type", "")
        except Exception as ex:
            if attempt == attempts - 1:
                print(f"  ERROR: {url} -> {ex}", file=sys.stderr)
            else:
                time.sleep(2 * (attempt + 1))
    return None, ""


# ── Media restore ──────────────────────────────────────────────────────────

def restore_media(api_key, dry_run=False):
    """Download protected files that exist on Neocities but not locally.

    Neocities is the store of record for media: wiki/build/media/ is gitignored
    because the artists asked to stay out of the repo, so a fresh clone restores
    from the live site. Returns the number of files restored.
    """
    if not api_key:
        raise ValueError("api_key must be non-empty")

    local_paths = set(scan_build_dir())
    remote_files = neocities_list(api_key)
    wanted = plan_restore(remote_files, local_paths)

    if not wanted:
        return 0

    print(f"  Missing locally: {len(wanted)} media file(s)")
    if dry_run:
        for path, _ in wanted:
            print(f"    would restore {path}")
        return 0

    manifest = load_manifest()
    restored = 0
    failed = []
    for path, expected_sha1 in wanted:
        url = f"{SITE_BASE}/{urllib.parse.quote(path)}"
        content, content_type = download_file(url)
        if content is None or not verify_download(content, content_type, expected_sha1):
            failed.append(path)
            continue
        dest = os.path.join(BUILD_DIR, path)
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        with open(dest, "wb") as f:
            f.write(content)
        manifest[path] = hashlib.sha1(content).hexdigest()
        restored += 1
        if restored % 10 == 0:
            print(f"    restored {restored}/{len(wanted)}")

    save_manifest(manifest)
    print(f"  Restored {restored}/{len(wanted)} media file(s)")
    if failed:
        shown = failed[:5]
        suffix = "..." if len(failed) > 5 else ""
        print(f"  WARNING: {len(failed)} could not be restored and stay protected"
              f" from deletion: {shown}{suffix}", file=sys.stderr)
    return restored


# ── Main upload logic ──────────────────────────────────────────────────────

def run_upload(dry_run=False):
    api_key  = get_api_key()
    # Restore first: media lives only on Neocities, and a missing local copy
    # must never be read as "deleted". restore_media updates the manifest on
    # disk, so both reads below have to happen after it.
    restore_media(api_key, dry_run=dry_run)
    manifest = load_manifest()
    local    = scan_build_dir()

    # Compute SHA1 for every local file
    local_hashes = {rel: sha1_file(path) for rel, path in local.items()}

    to_upload, to_delete, missing_protected = compute_changes(manifest, local_hashes)

    print(f"  Files to upload: {len(to_upload)}")
    print(f"  Files to delete: {len(to_delete)}")
    if missing_protected:
        print(f"  Protected from deletion: {len(missing_protected)} media file(s)"
              " missing locally", file=sys.stderr)
        print("  Run: python3 wiki/scripts/upload.py --restore-media",
              file=sys.stderr)

    if not to_upload and not to_delete:
        print("  Nothing to do — site is up to date.")
        return

    if dry_run:
        print("  (dry-run — no changes made)")
        if to_upload:
            print("  Would upload:")
            for p in to_upload:
                print(f"    + {p}")
        if to_delete:
            print("  Would delete:")
            for p in to_delete:
                print(f"    - {p}")
        return

    # Upload in batches of 10 (Neocities limit per request)
    BATCH = 10
    for i in range(0, len(to_upload), BATCH):
        batch = to_upload[i:i + BATCH]
        pairs = [(rel, local[rel]) for rel in batch]
        print(f"  Uploading batch {i // BATCH + 1}: {[p for p, _ in pairs]}")
        ok = neocities_upload(pairs, api_key)
        if ok:
            for rel in batch:
                manifest[rel] = local_hashes[rel]
            save_manifest(manifest)
        else:
            print("  ERROR: Upload batch failed. Stopping.")
            sys.exit(1)

    # Delete removed files
    if to_delete:
        print(f"  Deleting: {to_delete}")
        ok = neocities_delete(to_delete, api_key)
        if ok:
            for rel in to_delete:
                del manifest[rel]
            save_manifest(manifest)
        else:
            print("  WARNING: Delete failed — manifest not updated for deletions.")

    print("  Upload complete.")


def run_status():
    api_key = get_api_key()
    info = neocities_info(api_key)
    if info.get("result") == "success":
        site = info.get("info", {})
        print(f"  Site:  {site.get('sitename', '?')}.neocities.org")
        print(f"  Views: {site.get('views', '?')}")
        print(f"  Hits:  {site.get('hits', '?')}")
    else:
        print(f"  Could not fetch site info: {info.get('message', '?')}")


if __name__ == "__main__":
    if "--restore-media" in sys.argv:
        restore_media(get_api_key(), dry_run="--dry-run" in sys.argv)
    elif "--dry-run" in sys.argv:
        run_upload(dry_run=True)
    elif "--status" in sys.argv:
        run_status()
    else:
        run_upload()
