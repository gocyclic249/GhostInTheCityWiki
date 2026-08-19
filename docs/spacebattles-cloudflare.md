# SpaceBattles Cloudflare 403

SpaceBattles fronts its forum with Cloudflare. As of mid-2026, Cloudflare
serves a JavaScript **managed challenge** to plain HTTP clients on the
threadmarks endpoints. The `requests`-based scrapers can't execute that
challenge, so they get:

```
HTTP 403  |  server: cloudflare  |  cf-mitigated: challenge  |  body: "Just a moment..."
```

This is a serverside change on SpaceBattles' side, not a bug in the scrapers.
`curl`, `requests`, and even TLS-impersonation libraries (`curl_cffi`,
`cloudscraper`) are all challenged the same way — verified.

## Affected vs. not

| Scraper | Uses | Affected |
|---|---|---|
| `scrape_sidestories.py` | `requests` → SB | **Yes** |
| `scrape_media.py` (index + post fetch) | `requests` → SB | **Yes** |
| `scrape.py` | `requests` → AO3 | No (AO3 isn't behind Cloudflare) |

## Fix: borrow the `cf_clearance` cookie from your browser

Cloudflare's `cf_clearance` cookie is proof that *a browser* solved the
challenge. It's bound to the **(public IP, User-Agent)** pair. Under WSL2 the
scraper shares your Windows host's public IP, so a cookie earned in Windows
Chrome works from WSL — **as long as the User-Agent matches exactly.**

### Steps

1. Open the SpaceBattles thread in the browser you're logged into. Make sure
   the page actually loads (challenge already solved).

2. **Copy the User-Agent.** Open DevTools (F12) → Console, run:
   ```js
   copy(navigator.userAgent)
   ```
   (or just read it and copy the string).

3. **Copy the `cf_clearance` cookie.** DevTools → Application (Chrome) or
   Storage (Firefox) → Cookies → `https://forums.spacebattles.com` → select
   `cf_clearance` → copy its **Value**.

4. Put both in `.env` (see `.env.example`):
   ```sh
   export SB_USER_AGENT='<paste navigator.userAgent verbatim>'
   export SB_CF_CLEARANCE='<paste cf_clearance value>'
   ```

5. Reload and run:
   ```sh
   source .env
   python3 scrape_sidestories.py --status   # sanity check, no network
   python3 scrape_sidestories.py            # should fetch now
   ```

If a page also needs your login (most threadmarks pages don't), copy the whole
Cookie header instead and set `SB_COOKIE` — it overrides `SB_CF_CLEARANCE`:

```sh
export SB_COOKIE='cf_clearance=...; xf_user=...; xf_session=...'
```

## When it stops working again

`cf_clearance` is short-lived (often 30–60 min; sometimes longer). When it
lapses, the scrapers now exit with code `3` and print:

```
Cloudflare challenged <url> (the cf_clearance cookie has expired ...).
  Fix: copy a fresh cf_clearance cookie ...
```

Just repeat steps 2–5 with a fresh cookie. Common gotchas:

- **User-Agent mismatch** — the cookie is rejected if `SB_USER_AGENT` doesn't
  match the browser byte-for-byte. Re-copy both together.
- **Different IP** — a VPN/proxy on either side breaks the (IP, UA) binding.
- **You copied `__cf_bm`, not `cf_clearance`** — `__cf_bm` is a separate,
  even shorter-lived bot cookie. You want `cf_clearance`.

## If manual re-pasting gets tedious

The durable alternative is to let a real browser solve the challenge
automatically (`undetected-chromedriver` / Playwright) and hand the fresh
`cf_clearance` to the `requests` scrapers. The repo already has Selenium
plumbing in `lib/selenium_utils.py` (`wait_cloudflare`) but no browser/driver
installed. That's a larger change — ask for the "browser auto-solve" path.
