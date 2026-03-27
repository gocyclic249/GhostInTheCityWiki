#!/usr/bin/env python3
"""Grab remaining images from posts that the automated scraper missed.
Uses Selenium to visit each post, expand spoilers, and download visible images."""

import json
import os
import time

from selenium.webdriver.common.by import By

from lib.selenium_utils import create_driver, wait_cloudflare
from lib.spacebattles_utils import login_sb
from lib.image_utils import (
    is_skip_url, guess_extension, download_via_canvas,
    download_via_fetch, download_via_urllib, save_image,
)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
IMAGE_DIR = os.path.join(BASE_DIR, "wiki", "build", "media")
INDEX_PATH = os.path.join(BASE_DIR, "media_index.json")


def process_post(driver, entry):
    """Visit a post and extract/download all images."""
    post_id = entry.get("post_id", "")
    title = entry.get("title", "")
    permalink = f"https://forums.spacebattles.com/posts/{post_id}/"

    print(f"\n[{entry['index']}] {title}")
    print(f"  URL: {permalink}")

    driver.get(permalink)
    time.sleep(3)
    if "Just a moment" in driver.page_source:
        print("  Waiting for Cloudflare...")
        time.sleep(10)

    # Find the post article
    post_el = None
    try:
        post_el = driver.find_element(By.CSS_SELECTOR, f'article[data-content="post-{post_id}"]')
    except Exception:
        try:
            post_el = driver.find_element(By.CSS_SELECTOR, 'article.message')
        except Exception:
            print("  Could not find post element")
            return []

    # Expand ALL spoilers
    try:
        for selector in ['.bbCodeSpoiler-button', 'button.bbCodeSpoiler-button',
                         '.bbCodeSpoiler > .bbCodeSpoiler-button']:
            spoilers = driver.find_elements(By.CSS_SELECTOR, selector)
            for btn in spoilers:
                try:
                    driver.execute_script("arguments[0].click();", btn)
                    time.sleep(0.3)
                except Exception:
                    pass
        time.sleep(1)
    except Exception:
        pass

    # Scroll down to trigger lazy loading
    driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
    time.sleep(1)
    driver.execute_script("window.scrollTo(0, 0);")
    time.sleep(1)

    # Collect all image URLs
    found_images = []
    search_contexts = [post_el]
    containers = post_el.find_elements(By.CSS_SELECTOR, '.bbWrapper')
    search_contexts.extend(containers)

    for ctx in search_contexts:
        for img in ctx.find_elements(By.TAG_NAME, 'img'):
            src = img.get_attribute("data-src") or img.get_attribute("src") or ""
            if not src or is_skip_url(src):
                continue
            try:
                nat_w = driver.execute_script("return arguments[0].naturalWidth;", img)
                nat_h = driver.execute_script("return arguments[0].naturalHeight;", img)
                if nat_w and nat_h and nat_w < 40 and nat_h < 40:
                    continue
            except Exception:
                pass
            if src not in [x[0] for x in found_images]:
                found_images.append((src, img))

        for a in ctx.find_elements(By.CSS_SELECTOR, 'a.js-lbImage, a[data-fancybox]'):
            href = a.get_attribute("href") or ""
            if href and not is_skip_url(href) and href not in [x[0] for x in found_images]:
                found_images.append((href, None))

    if not found_images:
        print("  No images found in post")
        return []

    print(f"  Found {len(found_images)} image(s)")

    downloaded = []
    for img_idx, (url, img_el) in enumerate(found_images, 1):
        ext = guess_extension(url)
        filename = f"{post_id}_{img_idx}.{ext}"
        filepath = os.path.join(IMAGE_DIR, filename)

        if os.path.exists(filepath):
            print(f"  [{img_idx}] Already exists: {filename}")
            downloaded.append({"url": url, "local_file": filename, "alt_text": ""})
            continue

        print(f"  [{img_idx}] {url[:100]}")
        data = None

        if img_el:
            data = download_via_canvas(driver, img_el)
            if data:
                filename = f"{post_id}_{img_idx}.png"
                filepath = os.path.join(IMAGE_DIR, filename)

        if not data and "forums.spacebattles.com" in url:
            data = download_via_fetch(driver, url)

        if not data:
            data = download_via_urllib(url)

        if data and len(data) > 500:
            save_image(data, filepath)
            print(f"    Saved: {filename} ({len(data)} bytes)")
            downloaded.append({"url": url, "local_file": filename, "alt_text": ""})
        else:
            print(f"    FAILED to download")
            downloaded.append({"url": url, "local_file": None, "alt_text": ""})

    return downloaded


def main():
    os.makedirs(IMAGE_DIR, exist_ok=True)

    with open(INDEX_PATH) as f:
        index = json.load(f)

    empty_posts = [e for e in index if not e.get("images")]
    skip_indices = {
        75,  # "Other Self insert recs" — text recommendations only
        83,  # "Motoko's Music Box" — link to playlist only
        69,  # "Angry Motoko!" — mod-removed image
    }
    posts_to_check = [e for e in empty_posts if e["index"] not in skip_indices]

    print(f"Checking {len(posts_to_check)} posts for images...")
    print(f"Skipping {len(skip_indices)} known text-only posts")

    driver = create_driver(remote_debug_port=9225, user_data_suffix="grab")
    updated = False

    try:
        login_sb(driver)

        for entry in posts_to_check:
            images = process_post(driver, entry)
            if images:
                entry["images"] = images
                updated = True

    finally:
        driver.quit()

    if updated:
        with open(INDEX_PATH, "w") as f:
            json.dump(index, f, indent=2, ensure_ascii=False)
        print(f"\nUpdated {INDEX_PATH}")

    print("\nDone!")


if __name__ == "__main__":
    main()
