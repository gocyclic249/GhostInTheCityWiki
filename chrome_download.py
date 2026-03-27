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
import re
import sys
import time
import base64
import hashlib
from urllib.parse import urlparse

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
IMAGE_DIR = os.path.join(BASE_DIR, "wiki", "build", "media")
INDEX_PATH = os.path.join(BASE_DIR, "media_index.json")
CHROMEDRIVER = "/snap/chromium/3390/usr/lib/chromium-browser/chromedriver"

# URLs to skip (avatars, forum UI, etc.)
SKIP_URL_PATTERNS = [
    r'forums\.spacebattles\.com/data/avatar/',
    r'forums\.spacebattles\.com/styles/',
    r'forums\.spacebattles\.com/data/assets/',
    r'smilies/',
    r'forums\.spacebattles\.com/members/',
]


def is_skip_url(url):
    for pattern in SKIP_URL_PATTERNS:
        if re.search(pattern, url):
            return True
    return False


def guess_extension(url):
    path = url.split("?")[0].split("#")[0].rstrip("/")
    ext_m = re.search(r'\.(png|jpg|jpeg|gif|webp|svg)$', path, re.IGNORECASE)
    if ext_m:
        ext = ext_m.group(1).lower()
        return "jpg" if ext == "jpeg" else ext
    sb_ext = re.search(r'-(png|jpg|jpeg|gif|webp)\.\d+$', path, re.IGNORECASE)
    if sb_ext:
        ext = sb_ext.group(1).lower()
        return "jpg" if ext == "jpeg" else ext
    return "jpg"


def login_to_sb(driver, username, password):
    """Log into SpaceBattles via the login form."""
    try:
        driver.get("https://forums.spacebattles.com/login/")
        time.sleep(3)

        # Wait for Cloudflare
        for _ in range(5):
            if "Just a moment" in driver.page_source:
                print("  Waiting for Cloudflare...")
                time.sleep(5)
            else:
                break

        # Take debug screenshot
        driver.save_screenshot("/tmp/sb_login_page.png")
        print("  Screenshot saved to /tmp/sb_login_page.png")

        # Wait for login form to be present
        wait = WebDriverWait(driver, 20)
        user_field = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, 'input[name="login"]')))

        # Scroll to and click the field first to make it interactable
        driver.execute_script("arguments[0].scrollIntoView(true);", user_field)
        time.sleep(1)

        # Use JS to set values (more reliable than send_keys for XenForo)
        driver.execute_script("""
            var userField = document.querySelector('input[name="login"]');
            var passField = document.querySelector('input[name="password"]');
            userField.value = arguments[0];
            userField.dispatchEvent(new Event('input', {bubbles: true}));
            passField.value = arguments[1];
            passField.dispatchEvent(new Event('input', {bubbles: true}));
        """, username, password)
        time.sleep(1)

        # Submit via JS
        driver.execute_script("""
            var form = document.querySelector('form.block-body');
            if (!form) form = document.querySelector('form[action*="login"]');
            if (form) form.submit();
            else {
                var btn = document.querySelector('button.button--primary[type="submit"], .button--primary');
                if (btn) btn.click();
            }
        """)
        time.sleep(5)

        driver.save_screenshot("/tmp/sb_after_login.png")
        print("  Post-login screenshot saved to /tmp/sb_after_login.png")

        # Check if we need to verify via URL (redirected to home = logged in)
        page = driver.page_source
        if "Log out" in page or "Your account" in page:
            print("  Logged in successfully!")
            return True
        elif "Incorrect password" in page:
            print("  ERROR: Incorrect password!")
            return False
        elif "not a valid" in page.lower():
            print("  ERROR: Invalid login!")
            return False
        else:
            # Try navigating to homepage to check
            driver.get("https://forums.spacebattles.com/")
            time.sleep(3)
            if "Log out" in driver.page_source:
                print("  Logged in successfully!")
                return True
            else:
                print("  WARNING: Login status unclear")
                return False
    except Exception as e:
        driver.save_screenshot("/tmp/sb_login_error.png")
        print(f"  Login error: {e}")
        print("  Error screenshot saved to /tmp/sb_login_error.png")
        return False


def create_driver():
    """Create a Selenium Chrome driver."""
    opts = Options()
    opts.binary_location = "/snap/bin/chromium"
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--disable-gpu")
    opts.add_argument("--window-size=1920,1080")
    opts.add_argument("--remote-debugging-port=9222")
    opts.add_argument("--user-data-dir=/tmp/chrome-selenium-profile")
    # Set download directory
    prefs = {
        "download.default_directory": IMAGE_DIR,
        "download.prompt_for_download": False,
        "download.directory_upgrade": True,
    }
    opts.add_experimental_option("prefs", prefs)

    service = Service(executable_path=CHROMEDRIVER)
    driver = webdriver.Chrome(service=service, options=opts)
    driver.set_page_load_timeout(45)
    return driver


def _is_same_origin(url):
    """Check if URL is on SpaceBattles (same-origin for fetch)."""
    return "forums.spacebattles.com" in url


def _fetch_same_origin(driver, url):
    """Fetch an SB URL via JS fetch (same-origin, uses session cookies)."""
    script = """
    var callback = arguments[arguments.length - 1];
    var url = arguments[0];
    fetch(url, {credentials: 'include', redirect: 'follow'})
        .then(function(r) {
            if (!r.ok) { callback('ERROR:HTTP_' + r.status); return; }
            var ct = r.headers.get('content-type') || '';
            if (ct.indexOf('text/html') >= 0) {
                callback('ERROR:GOT_HTML');
                return;
            }
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


def _fetch_by_navigation(driver, url):
    """Fetch an external image by navigating to it and reading via canvas."""
    driver.get(url)
    time.sleep(3)

    # Check if we got an image rendered directly
    try:
        img = driver.find_element(By.TAG_NAME, "img")
        nat_w = driver.execute_script("return arguments[0].naturalWidth;", img)
        nat_h = driver.execute_script("return arguments[0].naturalHeight;", img)
        if nat_w and nat_h and nat_w > 10 and nat_h > 10:
            # Get original image bytes via canvas
            script = """
            var img = arguments[0];
            var canvas = document.createElement('canvas');
            canvas.width = img.naturalWidth;
            canvas.height = img.naturalHeight;
            var ctx = canvas.getContext('2d');
            ctx.drawImage(img, 0, 0);
            return canvas.toDataURL('image/png');
            """
            result = driver.execute_script(script, img)
            if result and result.startswith("data:"):
                return "OK:" + result.split(",", 1)[1]
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
            result = _fetch_same_origin(driver, url)
        else:
            result = _fetch_by_navigation(driver, url)

        if result and isinstance(result, str) and result.startswith("OK:"):
            b64_data = result[3:]
            data = base64.b64decode(b64_data)
            if len(data) < 500:
                print(f"    Too small ({len(data)} bytes), likely a placeholder")
                return False
            os.makedirs(os.path.dirname(filepath), exist_ok=True)
            with open(filepath, "wb") as f:
                f.write(data)
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
        # Try permalink first — spoilered content renders on permalinks
        permalink = f"https://forums.spacebattles.com/posts/{post_id}/"
        driver.get(permalink)
        time.sleep(3)

        # Check for Cloudflare
        if "Just a moment" in driver.page_source:
            print("    Waiting for Cloudflare...")
            time.sleep(10)

        # Find the specific post
        post_el = None
        try:
            post_el = driver.find_element(By.CSS_SELECTOR, f'article[data-content="post-{post_id}"]')
        except Exception:
            try:
                post_el = driver.find_element(By.ID, f'post-{post_id}')
            except Exception:
                # Try finding by js-post class
                try:
                    posts = driver.find_elements(By.CSS_SELECTOR, 'article.message')
                    for p in posts:
                        if post_id in (p.get_attribute('data-content') or ''):
                            post_el = p
                            break
                except Exception:
                    pass

        if not post_el:
            print(f"    Could not find post {post_id} on page, trying permalink...")
            permalink = f"https://forums.spacebattles.com/posts/{post_id}/"
            driver.get(permalink)
            time.sleep(3)
            if "Just a moment" in driver.page_source:
                time.sleep(10)
            try:
                post_el = driver.find_element(By.CSS_SELECTOR, 'article.message')
            except Exception:
                print(f"    Could not find post via permalink either")
                return images

        # Click any "Click to expand..." buttons to reveal spoilered content
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

        # Find all images in the post
        img_elements = post_el.find_elements(By.CSS_SELECTOR, '.bbWrapper img')
        if not img_elements:
            img_elements = post_el.find_elements(By.CSS_SELECTOR, 'img')

        for img in img_elements:
            src = img.get_attribute("src") or ""
            data_src = img.get_attribute("data-src") or ""
            url = data_src or src
            if not url:
                continue
            if is_skip_url(url):
                continue
            # Skip gravatar (profile pics, not fan art)
            if 'gravatar.com/' in url:
                continue
            # Skip tiny images (likely emojis/icons)
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

        # Also check for lightbox links (SB wraps images in links)
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

    # Collect work items
    # 1. SB attachment images with local_file=null
    attachment_jobs = []
    for entry in index:
        post_id = entry.get("post_id", "")
        for img_idx, img in enumerate(entry.get("images", []), 1):
            url = img.get("url", "")
            local = img.get("local_file")
            if local is not None:
                # Already downloaded (or has a filename assigned)
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

    driver = create_driver()
    updated = False

    try:
        # Visit SB and log in if credentials are provided
        print("Warming up browser with SpaceBattles visit...")
        driver.get("https://forums.spacebattles.com/")
        time.sleep(5)
        if "Just a moment" in driver.page_source:
            print("  Cloudflare challenge, waiting...")
            time.sleep(15)

        # Check if we need to log in
        sb_user = os.environ.get("SB_USER", "")
        sb_pass = os.environ.get("SB_PASS", "")
        if sb_user and sb_pass:
            print(f"  Logging in as {sb_user}...")
            login_to_sb(driver, sb_user, sb_pass)
        else:
            # Check if already logged in
            if "Log in" in driver.page_source and "Your account" not in driver.page_source:
                print("  WARNING: Not logged in! SB attachments require login.")
                print("  Set SB_USER and SB_PASS environment variables, or")
                print("  pass --login to be prompted for credentials.")
                if "--login" in sys.argv:
                    import getpass
                    sb_user = input("  SpaceBattles username: ")
                    sb_pass = getpass.getpass("  SpaceBattles password: ")
                    login_to_sb(driver, sb_user, sb_pass)
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
                    # Navigate back to SB after external image download
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
