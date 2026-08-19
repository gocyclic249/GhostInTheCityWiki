#!/usr/bin/env python3
"""Pack wiki/build/media/ into AES-256 encrypted zip volumes for git.

The fan art must survive independently of Neocities, but the artists asked to
stay out of a public GitHub repo. Encrypting the archive keeps the bytes durable
in git while leaving nothing scrapable: without the passphrase the blobs are
noise.

Volumes, not one archive, because GitHub hard-rejects any file over 100 MiB and
the media set is already ~94 MiB. Files are assigned to volumes greedily in
sorted-name order, so adding new art usually rewrites only the last volume
instead of every blob.

The passphrase is read from a getpass prompt (or MEDIA_ARCHIVE_PASSPHRASE for
non-interactive runs). It is never echoed, never written to disk, and never
passed on the command line where it would land in shell history or `ps`.

Usage:
    python3 wiki/scripts/pack_media.py --pack        # build the volumes
    python3 wiki/scripts/pack_media.py --verify      # check volumes round-trip
    python3 wiki/scripts/pack_media.py --extract     # restore into media/
    python3 wiki/scripts/pack_media.py --status      # no passphrase needed
"""

import argparse
import getpass
import hashlib
import json
import os
import pathlib
import sys

try:
    import pyzipper
except ImportError:
    sys.exit("pyzipper is required: pip install pyzipper (see requirements.txt)")

ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
MEDIA = ROOT / "wiki" / "build" / "media"
ARCHIVE_DIR = ROOT / "media-archive"
MANIFEST = ARCHIVE_DIR / "manifest.json"
STEM = "media-archive.part"

# GitHub hard-rejects >100 MiB and warns above 50 MiB, so stay under the warn
# threshold with room for one oversized image.
DEFAULT_MAX_PART = 45 * 1024 * 1024
# Largest single file we will place; anything bigger gets its own volume.
HARD_CAP = 95 * 1024 * 1024
MAX_FILES = 10000


def media_files():
    """Every media file, sorted by name for deterministic volume assignment."""
    if not MEDIA.is_dir():
        raise SystemExit(f"missing media dir {MEDIA}")
    files = sorted((p for p in MEDIA.iterdir() if p.is_file()),
                   key=lambda p: p.name)
    if not files:
        raise SystemExit(f"{MEDIA} is empty; refusing to pack nothing")
    if len(files) > MAX_FILES:
        raise SystemExit(f"{len(files)} files exceeds the {MAX_FILES} cap")
    return files


def sha256_of(path):
    """Streaming digest so a large image never lands in memory whole."""
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def plan_volumes(files, max_part):
    """Greedily bin-pack files into volumes, preserving sorted order."""
    if max_part < 1024:
        raise ValueError(f"max_part too small: {max_part}")
    volumes = []
    current, current_size = [], 0
    for path in files:
        size = path.stat().st_size
        if size > HARD_CAP:
            raise SystemExit(f"{path.name} is {size} bytes, over the {HARD_CAP} cap")
        if current and current_size + size > max_part:
            volumes.append(current)
            current, current_size = [], 0
        current.append(path)
        current_size += size
    if current:
        volumes.append(current)
    if not volumes:
        raise SystemExit("no volumes planned")
    return volumes


def read_passphrase(confirm):
    """Prompt for the passphrase without echoing it. Never logged or stored."""
    from_env = os.environ.get("MEDIA_ARCHIVE_PASSPHRASE", "")
    if from_env:
        return from_env.encode()
    if not sys.stdin.isatty():
        raise SystemExit(
            "No passphrase. Run this in a terminal, or set "
            "MEDIA_ARCHIVE_PASSPHRASE for non-interactive use.")
    secret = getpass.getpass("Archive passphrase: ")
    if len(secret) < 12:
        raise SystemExit("Refusing a passphrase under 12 characters. These "
                         "blobs go into a public repo and git history is "
                         "permanent; use a long random passphrase.")
    if confirm and secret != getpass.getpass("Confirm passphrase: "):
        raise SystemExit("Passphrases did not match")
    return secret.encode()


def volume_path(index):
    return ARCHIVE_DIR / f"{STEM}{index:02d}.zip"


def do_pack(max_part):
    files = media_files()
    volumes = plan_volumes(files, max_part)
    ARCHIVE_DIR.mkdir(exist_ok=True)
    secret = read_passphrase(confirm=True)

    entries = []
    for index, group in enumerate(volumes, start=1):
        dest = volume_path(index)
        with pyzipper.AESZipFile(dest, "w",
                                 compression=pyzipper.ZIP_DEFLATED,
                                 encryption=pyzipper.WZ_AES) as archive:
            archive.setpassword(secret)
            archive.setencryption(pyzipper.WZ_AES, nbits=256)
            for path in group:
                archive.write(path, arcname=path.name)
        packed = dest.stat().st_size
        print(f"  {dest.name}: {len(group)} files, {packed/1024/1024:.1f} MiB")
        entries.append({"volume": dest.name, "files": len(group),
                        "bytes": packed})

    manifest = {
        "format": "zip/AES-256 (WinZip AE-2)",
        "volumes": entries,
        "source_files": len(files),
        "source_bytes": sum(p.stat().st_size for p in files),
        "contents": {p.name: {"bytes": p.stat().st_size,
                              "sha256": sha256_of(p)} for p in files},
    }
    MANIFEST.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    print(f"  manifest: {MANIFEST.name} ({len(files)} files listed)")
    print(f"Packed {len(files)} files into {len(entries)} volume(s).")


def open_volumes(secret):
    """Yield (volume_path, AESZipFile) for each existing volume."""
    index = 1
    while True:
        path = volume_path(index)
        if not path.is_file():
            break
        archive = pyzipper.AESZipFile(path)
        archive.setpassword(secret)
        yield path, archive
        index += 1
    if index == 1:
        raise SystemExit(f"no volumes found in {ARCHIVE_DIR}; run --pack first")


def do_verify():
    if not MANIFEST.is_file():
        raise SystemExit(f"missing {MANIFEST}; run --pack first")
    manifest = json.loads(MANIFEST.read_text())
    expected = manifest["contents"]
    secret = read_passphrase(confirm=False)

    seen, bad = {}, []
    for path, archive in open_volumes(secret):
        with archive:
            for name in archive.namelist():
                digest = hashlib.sha256(archive.read(name)).hexdigest()
                seen[name] = digest
                want = expected.get(name, {}).get("sha256")
                if want is None:
                    bad.append(f"{name}: in {path.name} but not in manifest")
                elif want != digest:
                    bad.append(f"{name}: sha256 mismatch in {path.name}")
    for name in expected:
        if name not in seen:
            bad.append(f"{name}: in manifest but in no volume")

    for line in bad:
        print(f"  FAIL {line}", file=sys.stderr)
    if bad:
        raise SystemExit(f"{len(bad)} problem(s) found")
    print(f"Verified {len(seen)} files across all volumes; all digests match.")


def do_extract():
    MEDIA.mkdir(parents=True, exist_ok=True)
    secret = read_passphrase(confirm=False)
    restored = 0
    for path, archive in open_volumes(secret):
        with archive:
            for name in archive.namelist():
                # Volumes are built with bare filenames; reject anything else
                # so a tampered archive cannot write outside media/.
                if "/" in name or "\\" in name or name.startswith("."):
                    raise SystemExit(f"unsafe entry {name!r} in {path.name}")
                (MEDIA / name).write_bytes(archive.read(name))
                restored += 1
    print(f"Extracted {restored} file(s) into {MEDIA}")


def do_status():
    files = media_files()
    total = sum(p.stat().st_size for p in files)
    print(f"  media/:   {len(files)} files, {total/1024/1024:.1f} MiB")
    if not MANIFEST.is_file():
        print("  archive:  not built (run --pack)")
        return
    manifest = json.loads(MANIFEST.read_text())
    packed = sum(v["bytes"] for v in manifest["volumes"])
    print(f"  archive:  {len(manifest['volumes'])} volume(s), "
          f"{packed/1024/1024:.1f} MiB, {manifest['source_files']} files")
    on_disk = {p.name for p in files}
    archived = set(manifest["contents"])
    if on_disk - archived:
        print(f"  STALE:    {len(on_disk - archived)} file(s) not in archive")
    if archived - on_disk:
        print(f"  missing:  {len(archived - on_disk)} archived file(s) not on disk")
    if on_disk == archived:
        print("  archive matches media/ by filename.")


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--pack", action="store_true", help="build encrypted volumes")
    group.add_argument("--verify", action="store_true", help="check volumes against the manifest")
    group.add_argument("--extract", action="store_true", help="restore media/ from volumes")
    group.add_argument("--status", action="store_true", help="compare media/ to the archive")
    parser.add_argument("--max-part-bytes", type=int, default=DEFAULT_MAX_PART,
                        help=f"volume size cap (default {DEFAULT_MAX_PART})")
    args = parser.parse_args()

    if args.pack:
        do_pack(args.max_part_bytes)
    elif args.verify:
        do_verify()
    elif args.extract:
        do_extract()
    else:
        do_status()


if __name__ == "__main__":
    main()
