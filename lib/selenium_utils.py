"""Shared Selenium/Chrome driver utilities."""

import os
import shutil
import tempfile
import time

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service


def find_chromedriver():
    """Find chromedriver binary via env var, known snap path, or PATH."""
    env_path = os.environ.get("CHROMEDRIVER_PATH")
    if env_path and os.path.exists(env_path):
        return env_path
    snap_path = "/snap/chromium/current/usr/lib/chromium-browser/chromedriver"
    if os.path.exists(snap_path):
        return snap_path
    which = shutil.which("chromedriver")
    if which:
        return which
    raise FileNotFoundError(
        "chromedriver not found. Set CHROMEDRIVER_PATH or install chromium-browser."
    )


def find_chromium():
    """Find chromium binary via env var, known snap path, or PATH."""
    env_path = os.environ.get("CHROMIUM_PATH")
    if env_path and os.path.exists(env_path):
        return env_path
    snap_path = "/snap/bin/chromium"
    if os.path.exists(snap_path):
        return snap_path
    which = shutil.which("chromium") or shutil.which("chromium-browser")
    if which:
        return which
    raise FileNotFoundError(
        "chromium not found. Set CHROMIUM_PATH or install chromium-browser."
    )


def create_driver(remote_debug_port=9222, user_data_suffix="default",
                  window_size="1920,2400", page_load_timeout=45, prefs=None):
    """Create a Selenium Chrome driver with common settings.

    Args:
        remote_debug_port: Port for Chrome DevTools Protocol.
        user_data_suffix: Suffix for the user-data-dir under a temp directory.
        window_size: Browser window size.
        page_load_timeout: Page load timeout in seconds.
        prefs: Optional dict of Chrome preferences.
    """
    profile_dir = os.path.join(tempfile.gettempdir(), f"chrome-selenium-{user_data_suffix}")

    opts = Options()
    opts.binary_location = find_chromium()
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--disable-gpu")
    opts.add_argument(f"--window-size={window_size}")
    opts.add_argument(f"--remote-debugging-port={remote_debug_port}")
    opts.add_argument(f"--user-data-dir={profile_dir}")
    if prefs:
        opts.add_experimental_option("prefs", prefs)

    service = Service(executable_path=find_chromedriver())
    driver = webdriver.Chrome(service=service, options=opts)
    driver.set_page_load_timeout(page_load_timeout)
    return driver


def wait_cloudflare(driver, max_wait=30):
    """Wait for Cloudflare JS challenge to complete."""
    for _ in range(max_wait // 5):
        if "Just a moment" in driver.page_source:
            time.sleep(5)
        else:
            return True
    print("Warning: Cloudflare challenge may still be active")
    return False
