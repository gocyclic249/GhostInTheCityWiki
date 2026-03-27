#!/usr/bin/env python3
"""Check remaining empty posts for iframe-embedded content."""

import json
import os
import time
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
INDEX_PATH = os.path.join(BASE_DIR, "media_index.json")
CHROMEDRIVER = "/snap/chromium/3390/usr/lib/chromium-browser/chromedriver"

def create_driver():
    opts = Options()
    opts.binary_location = "/snap/bin/chromium"
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--disable-gpu")
    opts.add_argument("--window-size=1920,2400")
    opts.add_argument("--remote-debugging-port=9227")
    opts.add_argument("--user-data-dir=/tmp/chrome-selenium-profile")
    service = Service(executable_path=CHROMEDRIVER)
    driver = webdriver.Chrome(service=service, options=opts)
    driver.set_page_load_timeout(45)
    return driver

def main():
    with open(INDEX_PATH) as f:
        index = json.load(f)

    # Posts with no images that we haven't solved yet
    skip_ids = {75, 83, 69}  # text-only / mod-removed
    solved_ids = {46, 67, 33}  # imgur iframes we already handled
    empty = [e for e in index if not e.get("images") and e["index"] not in skip_ids and e["index"] not in solved_ids]

    if not empty:
        print("No empty posts to check!")
        return

    print(f"Checking {len(empty)} posts for iframes/embeds...")
    driver = create_driver()
    try:
        for entry in empty:
            pid = entry.get("post_id", "")
            print(f"\n[{entry['index']}] {entry['title']}")
            driver.get(f"https://forums.spacebattles.com/posts/{pid}/")
            time.sleep(3)
            if "Just a moment" in driver.page_source:
                time.sleep(10)

            try:
                post = driver.find_element(By.CSS_SELECTOR, f'article[data-content="post-{pid}"]')

                # Check iframes
                iframes = post.find_elements(By.TAG_NAME, "iframe")
                if iframes:
                    print(f"  Iframes: {len(iframes)}")
                    for iframe in iframes:
                        src = iframe.get_attribute("src") or ""
                        print(f"    {src[:120]}")

                # Check for links to external image sites
                links = post.find_elements(By.CSS_SELECTOR, '.bbWrapper a')
                for a in links:
                    href = a.get_attribute("href") or ""
                    if any(x in href for x in ["imgur.com", "deviantart.com", "artstation.com", "tumblr.com"]):
                        print(f"  External image link: {href[:120]}")

                # Show content preview
                wrappers = post.find_elements(By.CSS_SELECTOR, '.bbWrapper')
                if wrappers:
                    html = wrappers[0].get_attribute("innerHTML")
                    # Check for special embeds
                    if "iframe" in html.lower() or "embed" in html.lower():
                        print(f"  Has embed in HTML")
                    # Show text content
                    text = wrappers[0].text[:200]
                    print(f"  Content: {text}")

            except Exception as e:
                print(f"  Error: {e}")
    finally:
        driver.quit()

if __name__ == "__main__":
    main()
