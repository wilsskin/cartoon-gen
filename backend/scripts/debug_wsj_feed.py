#!/usr/bin/env python3
"""
Debug script for WSJ RSS: logs status, headers, body length, first ~300 chars, parse result.

Modes (set USE_SERVICE=1 to use rss_ingest fetch with browser headers + retries):
- Default: requests.get with no User-Agent (legacy production-like).
- USE_SERVICE=1: use backend.services.rss_ingest.fetch_rss_feed (with UA, retries).

Run from repo root: python3 -m backend.scripts.debug_wsj_feed
With DATABASE_URL set to use service: USE_SERVICE=1 python3 -m backend.scripts.debug_wsj_feed
"""
import os
import sys
from pathlib import Path

backend_path = Path(__file__).resolve().parent.parent
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

import feedparser
import requests

WSJ_URL = "https://feeds.content.dowjones.io/public/rss/RSSUSnews"  # WSJ US News (live)
TIMEOUT = 5


def fetch_no_ua(url: str, timeout: int, etag=None, last_modified=None):
    """Legacy: no User-Agent (old production path)."""
    headers = {}
    if etag:
        headers["If-None-Match"] = etag
    if last_modified:
        headers["If-Modified-Since"] = last_modified
    return requests.get(url, headers=headers, timeout=timeout)


def main():
    use_service = os.environ.get("USE_SERVICE", "0") == "1"
    if use_service:
        try:
            from services.rss_ingest import fetch_rss_feed
        except Exception as e:
            print(f"USE_SERVICE=1 requires DATABASE_URL and backend deps: {e}")
            return
        print("=== WSJ RSS (rss_ingest.fetch_rss_feed: browser UA + retries) ===\n")
        fetch_fn = fetch_rss_feed
    else:
        print("=== WSJ RSS (no User-Agent, timeout=5) ===\n")
        fetch_fn = fetch_no_ua

    try:
        response = fetch_fn(WSJ_URL, TIMEOUT)
    except requests.exceptions.Timeout as e:
        print(f"FETCH: Timeout - {e}")
        return
    except requests.exceptions.RequestException as e:
        print(f"FETCH: RequestException - {e}")
        return

    print(f"Status: {response.status_code} {response.reason}")
    print(f"Response headers: {dict(response.headers)}")
    body = response.content
    print(f"Body length: {len(body)} bytes")
    preview = body[:300].decode("utf-8", errors="replace")
    print(f"Body preview (first 300 chars):\n{preview!r}\n")

    if response.status_code != 200:
        if body:
            print(f"Error body (first 500 chars): {body[:500].decode('utf-8', errors='replace')!r}")
        return

    feed = feedparser.parse(response.content)
    print(f"Parse: bozo={feed.bozo}, bozo_exception={getattr(feed, 'bozo_exception', None)}")
    print(f"Entries count: {len(feed.entries)}")
    if feed.entries:
        e0 = feed.entries[0]
        print(f"First entry title: {getattr(e0, 'title', 'N/A')[:80]!r}")
        print(f"First entry link: {getattr(e0, 'link', 'N/A')[:80]!r}")
        print(f"First entry published_parsed: {getattr(e0, 'published_parsed', None)}")
    print("\n=== Done ===")


if __name__ == "__main__":
    main()
