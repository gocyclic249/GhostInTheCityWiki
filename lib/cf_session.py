"""SpaceBattles request headers with a browser-borrowed Cloudflare cookie.

SpaceBattles fronts its forum with Cloudflare, which now serves a JavaScript
"managed challenge" to plain HTTP clients (curl, requests, curl_cffi). A pure
HTTP client cannot solve that challenge. The workaround is to borrow the
``cf_clearance`` cookie from a real browser that already solved it, and send it
with the *exact same* User-Agent the browser used — the cookie is bound to the
(IP, User-Agent) pair, and WSL2 shares the Windows host's public IP.

Environment variables (set in ``.env``):
  SB_USER_AGENT   - copy verbatim from the browser (navigator.userAgent). MUST
                    match the browser that produced the cookie or Cloudflare
                    rejects the cookie.
  SB_CF_CLEARANCE - the ``cf_clearance`` cookie value from that browser.
  SB_COOKIE       - optional: a full raw Cookie header (e.g.
                    "cf_clearance=...; xf_user=...; xf_session=..."). When set,
                    it overrides SB_CF_CLEARANCE and is sent verbatim. Use this
                    when a page needs login cookies too.

Both cookies are short-lived (often 30-60 min). When they lapse, re-copy from
the browser. See docs/spacebattles-cloudflare.md for the step-by-step.
"""

import os

# Fallback matches the scrapers' historical UA. It will still be challenged
# without a matching cookie; that path exists so imports never fail.
DEFAULT_UA = ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")

# Cloudflare challenge signals: the cf-mitigated header and interstitial body.
CHALLENGE_STATUSES = (403, 503)
CHALLENGE_MARKERS = ("just a moment", "cf-challenge", "enable javascript",
                     "attention required", "cf_chl_opt")


class CloudflareChallenge(RuntimeError):
    """Raised when SpaceBattles returns a Cloudflare challenge page."""


def cookie_header():
    """Return the raw Cookie header value, or "" if none is configured."""
    raw = os.environ.get("SB_COOKIE", "").strip()
    if raw:
        return raw
    clearance = os.environ.get("SB_CF_CLEARANCE", "").strip()
    return f"cf_clearance={clearance}" if clearance else ""


def build_headers(extra=None):
    """Build request headers with the browser UA and Cloudflare cookie.

    Args:
        extra: optional dict merged over the base headers.

    Returns:
        A new headers dict. Never mutates the caller's ``extra``.
    """
    assert extra is None or isinstance(extra, dict), "extra must be a dict or None"

    ua = os.environ.get("SB_USER_AGENT", "").strip() or DEFAULT_UA
    headers = {"User-Agent": ua}

    cookie = cookie_header()
    if cookie:
        headers["Cookie"] = cookie

    if extra:
        headers.update(extra)

    assert "User-Agent" in headers, "headers must carry a User-Agent"
    return headers


def is_challenge(resp):
    """Return True if ``resp`` looks like a Cloudflare challenge page."""
    if resp is None:
        return False
    if resp.headers.get("cf-mitigated") == "challenge":
        return True
    if resp.status_code not in CHALLENGE_STATUSES:
        return False
    body = resp.text.lower()
    return any(marker in body for marker in CHALLENGE_MARKERS)


def raise_if_challenged(resp, url):
    """Raise CloudflareChallenge with actionable guidance if blocked.

    Retrying a challenge is pointless, so callers should let this propagate
    rather than loop.
    """
    if not is_challenge(resp):
        return
    have_cookie = bool(cookie_header())
    reason = ("the cf_clearance cookie has expired or its User-Agent no longer "
              "matches" if have_cookie
              else "no cf_clearance cookie is configured")
    raise CloudflareChallenge(
        f"Cloudflare challenged {url} ({reason}).\n"
        f"  Fix: copy a fresh cf_clearance cookie and the browser's exact\n"
        f"  User-Agent into .env (SB_CF_CLEARANCE, SB_USER_AGENT).\n"
        f"  See docs/spacebattles-cloudflare.md."
    )
