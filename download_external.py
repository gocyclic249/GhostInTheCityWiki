#!/usr/bin/env python3
"""Download external images (imgur, deviantart, tumblr, etc.) that have URLs in the
index but no local_file. Uses Selenium to navigate directly to each image URL."""

import json
import os
import re
import sys
import time
import base64

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
IMAGE_DIR = os.path.join(BASE_DIR, "wiki", "build", "media")
INDEX_PATH = os.path.join(BASE_DIR, "media_index.json")
CHROMEDRIVER = "/snap/chromium/3390/usr/lib/chromium-browser/chromedriver"


def guess_extension(url):
    path = url.split("?")[0].split("#")[0].rstrip("/")
    ext_m = re.search(r'\.(png|jpg|jpeg|gif|webp|svg)$', path, re.IGNORECASE)
    if ext_m:
        ext = ext_m.group(1).lower()
        return "jpg" if ext == "jpeg" else ext
    return "png"


def create_driver():
    opts = Options()
    opts.binary_location = "/snap/bin/chromium"
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--disable-gpu")
    opts.add_argument("--window-size=1920,1080")
    opts.add_argument("--remote-debugging-port=9223")
    opts.add_argument("--user-data-dir=/tmp/chrome-external-profile")
    service = Service(executable_path=CHROMEDRIVER)
    driver = webdriver.Chrome(service=service, options=opts)
    driver.set_page_load_timeout(30)
    return driver


def download_image(driver, url, filepath):
    """Navigate to the image URL and save it."""
    try:
        driver.get(url)
        time.sleep(3)

        # Try to get the image via canvas
        try:
            img = driver.find_element(By.TAG_NAME, "img")
            nat_w = driver.execute_script("return arguments[0].naturalWidth;", img)
            nat_h = driver.execute_script("return arguments[0].naturalHeight;", img)
            if nat_w and nat_h and nat_w > 10 and nat_h > 10:
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
                    b64_data = result.split(",", 1)[1]
                    data = base64.b64decode(b64_data)
                    if len(data) > 500:
                        # Force .png extension since canvas outputs PNG
                        fp = os.path.splitext(filepath)[0] + ".png"
                        os.makedirs(os.path.dirname(fp), exist_ok=True)
                        with open(fp, "wb") as f:
                            f.write(data)
                        print(f"  Saved via canvas: {os.path.basename(fp)} ({len(data)} bytes)")
                        return os.path.basename(fp)
        except Exception as e:
            pass

        # Try fetch from same origin
        try:
            script = """
            var callback = arguments[arguments.length - 1];
            fetch(arguments[0])
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
                data = base64.b64decode(result[3:])
                if len(data) > 500:
                    os.makedirs(os.path.dirname(filepath), exist_ok=True)
                    with open(filepath, "wb") as f:
                        f.write(data)
                    print(f"  Saved via fetch: {os.path.basename(filepath)} ({len(data)} bytes)")
                    return os.path.basename(filepath)
        except Exception:
            pass

        print(f"  Failed to download")
        return None
    except Exception as e:
        print(f"  Error: {str(e)[:100]}")
        return None


def main():
    with open(INDEX_PATH, encoding="utf-8") as f:
        index = json.load(f)

    # Find entries with URLs but no local file
    jobs = []
    for entry in index:
        post_id = entry.get("post_id", "")
        for img_idx, img in enumerate(entry.get("images", []), 1):
            url = img.get("url", "")
            local = img.get("local_file")
            if url and not local:
                # Skip SB attachments (handled by main script)
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
    driver = create_driver()
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
