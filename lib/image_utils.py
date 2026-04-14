"""Shared image download utilities for Selenium-based scripts."""

import base64
import os
import re
import urllib.request

# URLs to skip (avatars, forum UI, emojis, etc.)
SKIP_PATTERNS = [
    r'data/avatar/', r'/styles/', r'/data/assets/', r'smilies/',
    r'gravatar\.com/', r'data:image/gif;base64,R0lGOD',
    r'forums\.spacebattles\.com/members/',
]


def is_skip_url(url):
    """Return True if the URL should be skipped (avatar, UI element, etc.)."""
    for p in SKIP_PATTERNS:
        if re.search(p, url):
            return True
    return False


def guess_extension(url):
    """Guess the image file extension from a URL."""
    path = url.split("?")[0].split("#")[0].rstrip("/")
    m = re.search(r'\.(png|jpg|jpeg|gif|webp|svg)$', path, re.IGNORECASE)
    if m:
        ext = m.group(1).lower()
        return "jpg" if ext == "jpeg" else ext
    m = re.search(r'-(png|jpg|jpeg|gif|webp)\.\d+$', path, re.IGNORECASE)
    if m:
        ext = m.group(1).lower()
        return "jpg" if ext == "jpeg" else ext
    return "png"


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
    except Exception as e:
        print(f"    canvas download failed: {e}")
    return None


def download_via_fetch(driver, url):
    """Fetch an image via JS fetch (same-origin) and return bytes."""
    try:
        script = """
        var callback = arguments[arguments.length - 1];
        fetch(arguments[0], {credentials: 'include'})
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
        if isinstance(result, str) and result.startswith("ERROR:"):
            print(f"    fetch download failed: {result[6:]}")
    except Exception as e:
        print(f"    fetch download failed: {e}")
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
    except Exception as e:
        print(f"    urllib download failed: {e}")
    return None


def save_image(data, filepath):
    """Save image data to a file, creating directories as needed."""
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    with open(filepath, "wb") as f:
        f.write(data)
