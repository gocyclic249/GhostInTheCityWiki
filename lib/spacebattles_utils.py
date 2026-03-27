"""Shared SpaceBattles login and interaction utilities."""

import os
import time

from lib.selenium_utils import wait_cloudflare


SB_THREAD = "https://forums.spacebattles.com/threads/ghost-in-the-city-cyberpunk-gamer-si.1046809"


def login_sb(driver, user=None, pw=None):
    """Log into SpaceBattles. Uses SB_USER/SB_PASS env vars if not provided.

    Returns True if login appears successful.
    """
    user = user or os.environ.get("SB_USER", "")
    pw = pw or os.environ.get("SB_PASS", "")
    if not user or not pw:
        print("  No SB credentials provided (set SB_USER and SB_PASS)")
        return False

    driver.get("https://forums.spacebattles.com/login/")
    time.sleep(3)
    wait_cloudflare(driver)

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

        page = driver.page_source.lower()
        if "log out" in page or "log-out" in page:
            print("  Logged in!")
            return True

        # Check if redirected away from login (also means success)
        if "login" not in driver.current_url:
            # Verify by visiting homepage
            driver.get("https://forums.spacebattles.com/")
            time.sleep(3)
            if "log out" in driver.page_source.lower():
                print("  Logged in!")
                return True

        print("  Login status unclear, continuing...")
        return False
    except Exception as e:
        print(f"  Login attempt failed: {e}")
        return False
