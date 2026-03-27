#!/usr/bin/env python3
"""Debug: dump the HTML of specific posts to see how images are embedded."""

import os
import time
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By

CHROMEDRIVER = "/snap/chromium/3390/usr/lib/chromium-browser/chromedriver"

def create_driver():
    opts = Options()
    opts.binary_location = "/snap/bin/chromium"
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--disable-gpu")
    opts.add_argument("--window-size=1920,2400")
    opts.add_argument("--remote-debugging-port=9226")
    opts.add_argument("--user-data-dir=/tmp/chrome-selenium-profile")
    service = Service(executable_path=CHROMEDRIVER)
    driver = webdriver.Chrome(service=service, options=opts)
    driver.set_page_load_timeout(45)
    return driver

def main():
    post_ids = ["91941630", "93031523", "91069320"]  # catgirl, hand drawn, uragan
    driver = create_driver()
    try:
        for pid in post_ids:
            url = f"https://forums.spacebattles.com/posts/{pid}/"
            print(f"\n{'='*60}")
            print(f"Post {pid}")
            print(f"{'='*60}")
            driver.get(url)
            time.sleep(4)

            # Try to find the post
            try:
                post_el = driver.find_element(By.CSS_SELECTOR, f'article[data-content="post-{pid}"]')
                # Get bbWrapper content
                wrappers = post_el.find_elements(By.CSS_SELECTOR, '.bbWrapper')
                for i, w in enumerate(wrappers):
                    html = w.get_attribute("innerHTML")
                    print(f"\n--- bbWrapper {i} ({len(html)} chars) ---")
                    print(html[:2000])

                # Also check for iframes
                iframes = post_el.find_elements(By.TAG_NAME, "iframe")
                if iframes:
                    print(f"\nFound {len(iframes)} iframes")
                    for iframe in iframes:
                        print(f"  src: {iframe.get_attribute('src')}")

                # Check all img tags
                all_imgs = post_el.find_elements(By.TAG_NAME, "img")
                print(f"\nAll <img> tags: {len(all_imgs)}")
                for img in all_imgs:
                    src = img.get_attribute("src") or ""
                    dsrc = img.get_attribute("data-src") or ""
                    cls = img.get_attribute("class") or ""
                    print(f"  src={src[:80]}, data-src={dsrc[:80]}, class={cls}")

            except Exception as e:
                print(f"Error: {e}")
    finally:
        driver.quit()

if __name__ == "__main__":
    main()
