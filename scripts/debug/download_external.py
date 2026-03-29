#!/usr/bin/env python3
"""Download external images (imgur, deviantart, tumblr, etc.) that have URLs in the
index but no local_file. Uses Selenium to navigate directly to each image URL."""

import json
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))

from selenium.webdriver.common.by import By

from lib.selenium_utils import create_driver
from lib.image_utils import guess_extension, download_via_canvas, download_via_fetch, save_image

BASE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..")
IMAGE_DIR = os.path.join(BASE_DIR, "wiki", "build", "media")
INDEX_PATH = os.path.join(BASE_DIR, "media_index.json")


def download_image(driver, url, filepath):
    """Navigate to the image URL and save it."""
    try:
        driver.get(url)
        time.sleep(3)

        # Try to get the image via canvas
        try:
            img = driver.find_element(By.TAG_NAME, "img")
            data = download_via_canvas(driver, img)
            if data:
                fp = os.path.splitext(filepath)[0] + ".png"
                save_image(data, fp)
                print(f"  Saved via canvas: {os.path.basename(fp)} ({len(data)} bytes)")
                return os.path.basename(fp)
        except Exception:
            pass

        # Try fetch from same origin
        data = download_via_fetch(driver, url)
        if data and len(data) > 500:
            save_image(data, filepath)
            print(f"  Saved via fetch: {os.path.basename(filepath)} ({len(data)} bytes)")
            return os.path.basename(filepath)

        print(f"  Failed to download")
        return None
    except Exception as e:
        print(f"  Error: {str(e)[:100]}")
        return None


def main():
    with open(INDEX_PATH, encoding="utf-8") as f:
        index = json.load(f)

    jobs = []
    for entry in index:
        post_id = entry.get("post_id", "")
        for img_idx, img in enumerate(entry.get("images", []), 1):
            url = img.get("url", "")
            local = img.get("local_file")
            if url and not local:
                if "forums.spacebattles.com/attachments/" in url:
                    continue
                ext = guess_extension(url)
                filename = f"{post_id}_{img_idx}.{ext}"
                filepath = os.path.join(IMAGE_DIR, filename)
                if os.path.exists(filepath):
                    img["local_file"] = filename
                    continue
                jobs.append((entry, img_idx, img, url, filename, filepath))

    if not jobs:
        print("No external images to download!")
        return

    print(f"Downloading {len(jobs)} external image(s)...")
    driver = create_driver(remote_debug_port=9223, user_data_suffix="external")
    success = 0

    try:
        for entry, img_idx, img, url, filename, filepath in jobs:
            print(f"[{entry['index']}] {entry['title']} — {filename}")
            print(f"  URL: {url[:100]}")
            result_fn = download_image(driver, url, filepath)
            if result_fn:
                img["local_file"] = result_fn
                success += 1
            time.sleep(1)
    finally:
        driver.quit()

    with open(INDEX_PATH, "w", encoding="utf-8") as f:
        json.dump(index, f, indent=2, ensure_ascii=False)

    print(f"\nDone! {success}/{len(jobs)} downloaded")


if __name__ == "__main__":
    main()
