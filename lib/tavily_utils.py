"""Shared Tavily Extract API helper."""

import json
import os
import sys
import time
import urllib.error
import urllib.request

TAVILY_EXTRACT_URL = "https://api.tavily.com/extract"


def get_tavily_key():
    """Get Tavily API key from environment, exit if missing."""
    key = os.environ.get("TAVILY_API_KEY", "")
    if not key:
        print("ERROR: TAVILY_API_KEY environment variable is required.")
        print("  Set it with: export TAVILY_API_KEY=your-key-here")
        sys.exit(1)
    return key


def tavily_extract(urls, extract_depth="advanced", api_key=None):
    """Fetch one or more URLs via Tavily Extract API. Returns list of {url, raw_content}."""
    if isinstance(urls, str):
        urls = [urls]

    api_key = api_key or get_tavily_key()

    payload = json.dumps({
        "api_key": api_key,
        "urls": urls,
        "extract_depth": extract_depth,
    }).encode("utf-8")

    req = urllib.request.Request(
        TAVILY_EXTRACT_URL,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                results = data.get("results", [])
                return [
                    {"url": r.get("url", ""), "raw_content": r.get("raw_content", "")}
                    for r in results
                ]
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", errors="replace") if e.fp else ""
            print(f"  Tavily HTTP {e.code}, attempt {attempt+1}: {body[:200]}")
            if e.code == 429:
                time.sleep(30 * (attempt + 1))
            else:
                time.sleep(5)
        except Exception as e:
            print(f"  Tavily error: {e}, attempt {attempt+1}")
            time.sleep(5)
    return []
