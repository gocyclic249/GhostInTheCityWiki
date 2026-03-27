#!/usr/bin/env python3
"""
Download Cloudflare-protected SpaceBattles images using Selenium + Chromium.
Reads media_index.json, finds images with local_file=null or posts with no images,
visits each URL with a real browser, and saves the files.

Usage:
  DISPLAY=:99 python3 chrome_download.py              # download all missing
  DISPLAY=:99 python3 chrome_download.py --check-posts # also visit posts with 0 images
"""

import json
import os
import sys
import time
import base64

from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

from lib.selenium_utils import create_driver, wait_cloudflare
from lib.spacebattles_utils import login_sb
from lib.image_utils import is_skip_url, guess_extension, download_via_canvas, download_via_fetch, save_image

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
IMAGE_DIR = os.path.join(BASE_DIR, "wiki", "build", "media")
INDEX_PATH = os.path.join(BASE_DIR, "media_index.json")


def _is_same_origin(url):
    return "forums.spacebattles.com" in url


def _fetch_by_navigation(driver, url):
    """Fetch an external image by navigating to it and reading via canvas."""
    driver.get(url)
    time.sleep(3)
    try:
        img = driver.find_element(By.TAG_NAME, "img")
        data = download_via_canvas(driver, img)
        if data:
            return "OK:" + base64.b64encode(data).decode()
    except Exception:
        pass

    # Fallback: try fetching from the image's own origin
    try:
        script = """
        var callback = arguments[arguments.length - 1];
        var url = arguments[0];
        fetch(url)
            .then(function(r) {
                if (!r.ok) { callback('ERROR:HTTP_' + r.status); return; }
                return r.arrayBuffer();
            })
            .then(function(buf) {
                if (!buf) return;
                var bytes = new Uint8Array(buf);
                var binary = '';
                var chunkSize = 8192;
                for (var i = 0; i < bytes.length; i += chunkSize) {
                    var slice = bytes.subarray(i, Math.min(i + chunkSize, bytes.length));
                    binary += String.fromCharCode.apply(null, slice);
                }
                callback('OK:' + btoa(binary));
            })
            .catch(function(e) { callback('ERROR:' + e.toString()); });
        """
        driver.set_script_timeout(30)
        return driver.execute_async_script(script, url)
    except Exception:
        pass
    return None


def download_image_via_browser(driver, url, filepath):
    """Download an image via the browser — handles both SB and external URLs."""
    try:
        if _is_same_origin(url):
            from lib.image_utils import download_via_fetch as _fetch
            data = _fetch(driver, url)
            if data and len(data) > 500:
                save_image(data, filepath)
                print(f"    Saved: {os.path.basename(filepath)} ({len(data)} bytes)")
                return True
            elif data is None:
                print(f"    No data returned")
                return False
            else:
                print(f"    Too small ({len(data)} bytes), likely a placeholder")
                return False
        else:
            result = _fetch_by_navigation(driver, url)
            if result and isinstance(result, str) and result.startswith("OK:"):
                b64_data = result[3:]
                data = base64.b64decode(b64_data)
                if len(data) < 500:
                    print(f"    Too small ({len(data)} bytes), likely a placeholder")
                    return False
                save_image(data, filepath)
                print(f"    Saved: {os.path.basename(filepath)} ({len(data)} bytes)")
                return True
            elif result and isinstance(result, str) and "GOT_HTML" in result:
                print(f"    Got HTML instead of image — login required or URL changed")
                return False
            elif result and isinstance(result, str) and result.startswith("ERROR:"):
                print(f"    Fetch error: {result}")
                return False
            else:
                print(f"    No data returned")
                return False

    except Exception as e:
        err_msg = str(e).split('\n')[0][:120]
        print(f"    Error: {err_msg}")
        return False


def extract_images_from_post(driver, post_url, post_id):
    """Visit a post page and extract image URLs from it."""
    images = []
    try:
        permalink = f"https://forums.spacebattles.com/posts/{post_id}/"
        driver.get(permalink)
        time.sleep(3)

        if "Just a moment" in driver.page_source:
            print("    Waiting for Cloudflare...")
            time.sleep(10)

        post_el = None
        for selector in [f'article[data-content="post-{post_id}"]',
                         f'#post-{post_id}', 'article.message']:
            try:
                post_el = driver.find_element(By.CSS_SELECTOR, selector)
                break
            except Exception:
                continue

        if not post_el:
            print(f"    Could not find post {post_id}")
            return images

        # Click spoiler buttons
        try:
            spoiler_btns = post_el.find_elements(By.CSS_SELECTOR, '.bbCodeSpoiler-button')
            for btn in spoiler_btns:
                try:
                    driver.execute_script("arguments[0].click();", btn)
                    time.sleep(0.5)
                except Exception:
                    pass
        except Exception:
            pass

        # Find all images
        img_elements = post_el.find_elements(By.CSS_SELECTOR, '.bbWrapper img')
        if not img_elements:
            img_elements = post_el.find_elements(By.CSS_SELECTOR, 'img')

        for img in img_elements:
            src = img.get_attribute("src") or ""
            data_src = img.get_attribute("data-src") or ""
            url = data_src or src
            if not url or is_skip_url(url) or 'gravatar.com/' in url:
                continue
            try:
                w = img.get_attribute("width")
                h = img.get_attribute("height")
                if w and h and int(w) < 50 and int(h) < 50:
                    continue
            except Exception:
                pass
            if url not in [i["url"] for i in images]:
                alt = img.get_attribute("alt") or ""
                images.append({"url": url, "alt_text": alt})

        # Lightbox links
        link_elements = post_el.find_elements(By.CSS_SELECTOR, '.bbWrapper a.js-lbImage, .bbWrapper a[data-fancybox]')
        for link in link_elements:
            href = link.get_attribute("href") or ""
            if not href or is_skip_url(href):
                continue
            if href not in [i["url"] for i in images]:
                images.append({"url": href, "alt_text": ""})

    except Exception as e:
        print(f"    Error visiting post: {e}")

    return images


def main():
    check_posts = "--check-posts" in sys.argv

    os.makedirs(IMAGE_DIR, exist_ok=True)

    with open(INDEX_PATH, encoding="utf-8") as f:
        index = json.load(f)

    # 1. SB attachment images with local_file=null
    attachment_jobs = []
    for entry in index:
        post_id = entry.get("post_id", "")
        for img_idx, img in enumerate(entry.get("images", []), 1):
            url = img.get("url", "")
            local = img.get("local_file")
            if local is not None:
                filepath = os.path.join(IMAGE_DIR, local)
                if os.path.exists(filepath):
                    continue
            if "forums.spacebattles.com/attachments/" in url:
                ext = guess_extension(url)
                filename = f"{post_id}_{img_idx}.{ext}"
                filepath = os.path.join(IMAGE_DIR, filename)
                if os.path.exists(filepath):
                    continue
                attachment_jobs.append((entry, img_idx, img, url, filename, filepath))

    # 2. Posts with no images extracted
    empty_posts = []
    if check_posts:
        for entry in index:
            if not entry.get("images"):
                sb_url = entry.get("sb_url")
                post_id = entry.get("post_id")
                if sb_url and post_id:
                    empty_posts.append(entry)

    total_jobs = len(attachment_jobs) + len(empty_posts)
    if total_jobs == 0:
        print("Nothing to download!")
        return

    print(f"Jobs: {len(attachment_jobs)} attachment downloads, {len(empty_posts)} posts to check")
    print(f"Starting Chromium browser...")

    driver = create_driver(
        remote_debug_port=9222,
        user_data_suffix="chrome-dl",
        window_size="1920,1080",
        prefs={
            "download.default_directory": IMAGE_DIR,
            "download.prompt_for_download": False,
            "download.directory_upgrade": True,
        },
    )
    updated = False

    try:
        print("Warming up browser with SpaceBattles visit...")
        driver.get("https://forums.spacebattles.com/")
        time.sleep(5)
        wait_cloudflare(driver)

        login_sb(driver)
        print("  Browser ready\n")

        # Download SB attachment images
        if attachment_jobs:
            print(f"{'='*60}")
            print(f"  Downloading {len(attachment_jobs)} SB attachments")
            print(f"{'='*60}")

            success = 0
            for entry, img_idx, img, url, filename, filepath in attachment_jobs:
                title = entry.get("title", "")
                print(f"  [{entry['index']}] {title} — {filename}")
                print(f"    URL: {url}")

                ok = download_image_via_browser(driver, url, filepath)
                if ok:
                    img["local_file"] = filename
                    success += 1
                    updated = True
                time.sleep(1)

            print(f"\n  Attachments: {success}/{len(attachment_jobs)} downloaded\n")

        # Check posts with no images
        if empty_posts:
            print(f"{'='*60}")
            print(f"  Checking {len(empty_posts)} posts for images")
            print(f"{'='*60}")

            found_total = 0
            for entry in empty_posts:
                title = entry.get("title", "")
                sb_url = entry.get("sb_url", "")
                post_id = entry.get("post_id", "")
                print(f"  [{entry['index']}] {title}")
                print(f"    URL: {sb_url}")

                images = extract_images_from_post(driver, sb_url, post_id)
                if not images:
                    print(f"    No images found")
                    continue

                print(f"    Found {len(images)} image(s)")
                entry["images"] = []
                for img_idx, img_data in enumerate(images, 1):
                    url = img_data["url"]
                    ext = guess_extension(url)
                    filename = f"{post_id}_{img_idx}.{ext}"
                    filepath = os.path.join(IMAGE_DIR, filename)

                    print(f"    Downloading image {img_idx}: {url[:80]}...")
                    ok = download_image_via_browser(driver, url, filepath)
                    entry["images"].append({
                        "url": url,
                        "local_file": filename if ok else None,
                        "alt_text": img_data.get("alt_text", ""),
                    })
                    if ok:
                        found_total += 1
                    if not _is_same_origin(url):
                        driver.get("https://forums.spacebattles.com/")
                        time.sleep(2)
                    time.sleep(1)

                updated = True
                time.sleep(2)

            print(f"\n  Posts checked: {len(empty_posts)}, images found & downloaded: {found_total}\n")

    finally:
        driver.quit()

    if updated:
        with open(INDEX_PATH, "w", encoding="utf-8") as f:
            json.dump(index, f, indent=2, ensure_ascii=False)
        print(f"Updated {INDEX_PATH}")

    print("Done!")


if __name__ == "__main__":
    main()
