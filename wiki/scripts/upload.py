#!/usr/bin/env python3
"""
upload.py — Incremental uploader to Neocities REST API.
Uses only Python stdlib (urllib, hashlib, os, json).

Reads NEOCITIES_API_KEY from environment.
Tracks uploaded file SHA1 hashes in cache/upload_manifest.json to
only upload changed/new files and delete removed files.
"""

import hashlib
import json
import os
import sys
import urllib.error
import urllib.request

# ── Paths ──────────────────────────────────────────────────────────────────

WIKI_DIR      = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BUILD_DIR     = os.path.join(WIKI_DIR, "build")
MANIFEST_PATH = os.path.join(WIKI_DIR, "cache", "upload_manifest.json")

NEOCITIES_API = "https://neocities.org/api"


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
    import urllib.parse  # noqa (already imported via urllib)
    body = params.encode()
    ctype = "application/x-www-form-urlencoded"
    result = api_request("delete", method="POST", body=body,
                         content_type=ctype, api_key=api_key)
    return result.get("result") == "success"


def neocities_info(api_key):
    return api_request("info", api_key=api_key)


# ── Main upload logic ──────────────────────────────────────────────────────

def run_upload(dry_run=False):
    import urllib.parse  # ensure available

    api_key  = get_api_key()
    manifest = load_manifest()
    local    = scan_build_dir()

    # Compute SHA1 for every local file
    local_hashes = {rel: sha1_file(path) for rel, path in local.items()}

    to_upload = []
    for rel, sha1 in local_hashes.items():
        if manifest.get(rel) != sha1:
            to_upload.append(rel)

    to_delete = [rel for rel in manifest if rel not in local_hashes]

    print(f"  Files to upload: {len(to_upload)}")
    print(f"  Files to delete: {len(to_delete)}")

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
            print(f"  ERROR: Upload batch failed. Stopping.")
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
    import urllib.parse
    if "--dry-run" in sys.argv:
        run_upload(dry_run=True)
    elif "--status" in sys.argv:
        run_status()
    else:
        run_upload()
