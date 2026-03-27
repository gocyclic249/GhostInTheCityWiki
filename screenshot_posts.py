#!/usr/bin/env python3
"""Take screenshots of posts that have no images extracted, to diagnose what's there."""

import json
import os
import time

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
INDEX_PATH = os.path.join(BASE_DIR, "media_index.json")
CHROMEDRIVER = "/snap/chromium/3390/usr/lib/chromium-browser/chromedriver"
SCREENSHOT_DIR = "/tmp/sb_screenshots"

def create_driver():
    opts = Options()
    opts.binary_location = "/snap/bin/chromium"
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--disable-gpu")
    opts.add_argument("--window-size=1920,2400")
    opts.add_argument("--remote-debugging-port=9224")
    opts.add_argument("--user-data-dir=/tmp/chrome-screenshot-profile")
    service = Service(executable_path=CHROMEDRIVER)
    driver = webdriver.Chrome(service=service, options=opts)
    driver.set_page_load_timeout(30)
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
    except Exception as e:
        print(f"  Login attempt: {e}")

def main():
    os.makedirs(SCREENSHOT_DIR, exist_ok=True)

    with open(INDEX_PATH) as f:
        index = json.load(f)

    empty_posts = [e for e in index if not e.get("images")]
    print(f"Taking screenshots of {len(empty_posts)} posts...")

    driver = create_driver()
    try:
        # Login
        sb_user = os.environ.get("SB_USER", "")
        sb_pass = os.environ.get("SB_PASS", "")
        if sb_user and sb_pass:
            login_sb(driver, sb_user, sb_pass)

        for entry in empty_posts:
            post_id = entry.get("post_id", "")
            title = entry.get("title", "")
            permalink = f"https://forums.spacebattles.com/posts/{post_id}/"

            print(f"  [{entry['index']}] {title}")
            driver.get(permalink)
            time.sleep(3)

            if "Just a moment" in driver.page_source:
                time.sleep(10)

            # Click spoiler buttons
            try:
                spoilers = driver.find_elements(By.CSS_SELECTOR, '.bbCodeSpoiler-button')
                for btn in spoilers:
                    driver.execute_script("arguments[0].click();", btn)
                    time.sleep(0.5)
            except Exception:
                pass

            # Also try to extract any image URLs from the page source for this post
            try:
                post_el = driver.find_element(By.CSS_SELECTOR, f'article[data-content="post-{post_id}"]')
                # Check for SB attachment images
                imgs = post_el.find_elements(By.CSS_SELECTOR, '.bbWrapper img')
                lightbox = post_el.find_elements(By.CSS_SELECTOR, '.bbWrapper a.js-lbImage')
                found_urls = []
                for img in imgs:
                    src = img.get_attribute("data-src") or img.get_attribute("src") or ""
                    if src and "avatar" not in src and "smilies" not in src and "styles" not in src:
                        found_urls.append(src)
                for a in lightbox:
                    href = a.get_attribute("href") or ""
                    if href:
                        found_urls.append(href)
                if found_urls:
                    print(f"    FOUND {len(found_urls)} image URL(s):")
                    for u in found_urls:
                        print(f"      {u[:120]}")
                else:
                    # Check what kind of content the post has
                    text = post_el.text[:300]
                    print(f"    Content preview: {text[:200]}...")
            except Exception as e:
                print(f"    Error checking post: {e}")

            # Take screenshot
            fname = f"{SCREENSHOT_DIR}/post_{post_id}.png"
            driver.save_screenshot(fname)

    finally:
        driver.quit()

    print(f"\nScreenshots saved to {SCREENSHOT_DIR}/")

if __name__ == "__main__":
    main()
