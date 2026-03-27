#!/usr/bin/env python3
"""Grab remaining images from posts that the automated scraper missed.
Uses Selenium to visit each post, expand spoilers, and download visible images."""

import json
import os
import re
import time
import base64
import urllib.request

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
IMAGE_DIR = os.path.join(BASE_DIR, "wiki", "build", "media")
INDEX_PATH = os.path.join(BASE_DIR, "media_index.json")
CHROMEDRIVER = "/snap/chromium/3390/usr/lib/chromium-browser/chromedriver"

SKIP_PATTERNS = [
    r'data/avatar/', r'/styles/', r'/data/assets/', r'smilies/',
    r'gravatar\.com/', r'data:image/gif;base64,R0lGOD',
]


def is_skip(url):
    for p in SKIP_PATTERNS:
        if re.search(p, url):
            return True
    return False


def guess_ext(url):
    path = url.split("?")[0].split("#")[0].rstrip("/")
    m = re.search(r'\.(png|jpg|jpeg|gif|webp)$', path, re.I)
    if m:
        return "jpg" if m.group(1).lower() == "jpeg" else m.group(1).lower()
    m = re.search(r'-(png|jpg|jpeg|gif|webp)\.\d+$', path, re.I)
    if m:
        return "jpg" if m.group(1).lower() == "jpeg" else m.group(1).lower()
    return "png"


def create_driver():
    opts = Options()
    opts.binary_location = "/snap/bin/chromium"
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--disable-gpu")
    opts.add_argument("--window-size=1920,2400")
    opts.add_argument("--remote-debugging-port=9225")
    opts.add_argument("--user-data-dir=/tmp/chrome-selenium-profile")
    service = Service(executable_path=CHROMEDRIVER)
    driver = webdriver.Chrome(service=service, options=opts)
    driver.set_page_load_timeout(45)
    return driver


def login_sb(driver, user, pw):
    driver.get("https://forums.spacebattles.com/login/")
    time.sleep(3)
    for _ in range(5):
        if "Just a moment" in driver.page_source:
            time.sleep(5)
        else:
            break
    try:
        driver.execute_script("""
            var u = document.querySelector('input[name="login"]');
            var p = document.querySelector('input[name="password"]');
            if (u && p) {
                u.value = arguments[0];
                u.dispatchEvent(new Event('input', {bubbles: true}));
                p.value = arguments[1];
                p.dispatchEvent(new Event('input', {bubbles: true}));
            }
        """, user, pw)
        time.sleep(1)
        driver.execute_script("""
            var form = document.querySelector('form.block-body') || document.querySelector('form[action*="login"]');
            if (form) form.submit();
        """)
        time.sleep(5)
        if "Log out" in driver.page_source:
            print("  Logged in!")
        else:
            print("  Login status unclear, continuing...")
    except Exception as e:
        print(f"  Login attempt: {e}")


def download_via_canvas(driver, img_element):
    """Grab an image element's content via canvas as PNG bytes."""
    try:
        nat_w = driver.execute_script("return arguments[0].naturalWidth;", img_element)
        nat_h = driver.execute_script("return arguments[0].naturalHeight;", img_element)
        if not nat_w or not nat_h or nat_w < 20 or nat_h < 20:
            return None

        script = """
        var img = arguments[0];
        var canvas = document.createElement('canvas');
        canvas.width = img.naturalWidth;
        canvas.height = img.naturalHeight;
        var ctx = canvas.getContext('2d');
        ctx.drawImage(img, 0, 0);
        return canvas.toDataURL('image/png');
        """
        result = driver.execute_script(script, img_element)
        if result and result.startswith("data:"):
            b64 = result.split(",", 1)[1]
            data = base64.b64decode(b64)
            if len(data) > 1000:
                return data
    except Exception:
        pass
    return None


def download_via_fetch(driver, url):
    """Fetch an image via JS fetch (same-origin) and return bytes."""
    try:
        script = """
        var callback = arguments[arguments.length - 1];
        fetch(arguments[0], {credentials: 'include'})
            .then(function(r) {
                if (!r.ok) { callback('ERROR:HTTP_' + r.status); return; }
                return r.arrayBuffer();
            })
            .then(function(buf) {
                if (!buf) return;
                var bytes = new Uint8Array(buf);
                var binary = '';
                var cs = 8192;
                for (var i = 0; i < bytes.length; i += cs) {
                    var s = bytes.subarray(i, Math.min(i + cs, bytes.length));
                    binary += String.fromCharCode.apply(null, s);
                }
                callback('OK:' + btoa(binary));
            })
            .catch(function(e) { callback('ERROR:' + e.toString()); });
        """
        driver.set_script_timeout(30)
        result = driver.execute_async_script(script, url)
        if result and isinstance(result, str) and result.startswith("OK:"):
            return base64.b64decode(result[3:])
    except Exception:
        pass
    return None


def download_via_urllib(url):
    """Fallback: download via urllib."""
    try:
        req = urllib.request.Request(url, headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        })
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = resp.read()
            if len(data) > 500:
                return data
    except Exception:
        pass
    return None


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

    # Debug: save screenshot
    driver.save_screenshot(f"/tmp/grab_debug_{post_id}.png")

    # Expand ALL spoilers (try multiple selector patterns)
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

    # Collect all image URLs — search in the post AND the full page
    found_images = []

    # Try both post-scoped and page-scoped searches
    search_contexts = [post_el]
    # Also try searching the whole page if post has no images
    containers = post_el.find_elements(By.CSS_SELECTOR, '.bbWrapper')
    search_contexts.extend(containers)

    for ctx in search_contexts:
        # From <img> tags
        for img in ctx.find_elements(By.TAG_NAME, 'img'):
            src = img.get_attribute("data-src") or img.get_attribute("src") or ""
            if not src or is_skip(src):
                continue
            # Check size via natural dimensions
            try:
                nat_w = driver.execute_script("return arguments[0].naturalWidth;", img)
                nat_h = driver.execute_script("return arguments[0].naturalHeight;", img)
                if nat_w and nat_h and nat_w < 40 and nat_h < 40:
                    continue
            except Exception:
                pass
            if src not in [x[0] for x in found_images]:
                found_images.append((src, img))

        # From lightbox links
        for a in ctx.find_elements(By.CSS_SELECTOR, 'a.js-lbImage, a[data-fancybox]'):
            href = a.get_attribute("href") or ""
            if href and not is_skip(href) and href not in [x[0] for x in found_images]:
                found_images.append((href, None))

    if not found_images:
        print("  No images found in post")
        return []

    print(f"  Found {len(found_images)} image(s)")

    downloaded = []
    for img_idx, (url, img_el) in enumerate(found_images, 1):
        ext = guess_ext(url)
        filename = f"{post_id}_{img_idx}.{ext}"
        filepath = os.path.join(IMAGE_DIR, filename)

        if os.path.exists(filepath):
            print(f"  [{img_idx}] Already exists: {filename}")
            downloaded.append({"url": url, "local_file": filename, "alt_text": ""})
            continue

        print(f"  [{img_idx}] {url[:100]}")
        data = None

        # Try canvas first (if we have the element and it's loaded)
        if img_el:
            data = download_via_canvas(driver, img_el)
            if data:
                # Canvas outputs PNG
                filename = f"{post_id}_{img_idx}.png"
                filepath = os.path.join(IMAGE_DIR, filename)

        # Try SB fetch (same-origin)
        if not data and "forums.spacebattles.com" in url:
            data = download_via_fetch(driver, url)

        # Try urllib for external URLs
        if not data:
            data = download_via_urllib(url)

        if data and len(data) > 500:
            os.makedirs(os.path.dirname(filepath), exist_ok=True)
            with open(filepath, "wb") as f:
                f.write(data)
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

    # Posts with no images
    empty_posts = [e for e in index if not e.get("images")]
    # Skip known text-only / mod-removed posts
    skip_indices = {
        75,  # "Other Self insert recs" — text recommendations only
        83,  # "Motoko's Music Box" — link to playlist only
        69,  # "Angry Motoko!" — mod-removed image
    }
    posts_to_check = [e for e in empty_posts if e["index"] not in skip_indices]

    print(f"Checking {len(posts_to_check)} posts for images...")
    print(f"Skipping {len(skip_indices)} known text-only posts")

    driver = create_driver()
    updated = False

    try:
        # Login
        sb_user = os.environ.get("SB_USER", "")
        sb_pass = os.environ.get("SB_PASS", "")
        if sb_user and sb_pass:
            login_sb(driver, sb_user, sb_pass)

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
