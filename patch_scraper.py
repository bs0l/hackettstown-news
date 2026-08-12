"""
Best-effort scraper for patch.com/new-jersey/hackettstown.

Patch doesn't publish an RSS feed for community pages anymore and doesn't
document its HTML structure, so this works heuristically:

1. Find every <a href> that points directly at an article under
   /new-jersey/hackettstown/ (one path segment, not a known non-article
   page like /calendar or /businesses).
2. Walk up to the nearest ancestor block and pull the first following
   paragraph of text as the description, and the nearest "<category>|<type>|<age>"
   label (e.g. "Hackettstown|News|12h") as a rough timestamp.

If Patch changes its markup, this will start returning fewer/no results
rather than crashing - run debug_dump.py to grab fresh HTML and adjust
the selectors below.
"""
import re
import logging
from datetime import datetime, timedelta
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup

from sources import PATCH_URL, PATCH_NON_ARTICLE_SLUGS, USER_AGENT

log = logging.getLogger(__name__)

ARTICLE_PATH_RE = re.compile(r"^/new-jersey/hackettstown/([a-z0-9\-]+)/?$")
AGE_RE = re.compile(r"^\s*(\d+)\s*(h|hr|hrs|hour|hours|d|day|days|m|min|mins|minute|minutes)\s*$", re.I)


def _parse_relative_age(text: str):
    """Turn a Patch-style age string like '3h' or '2d' into a datetime."""
    m = AGE_RE.match(text or "")
    if not m:
        return None
    n, unit = int(m.group(1)), m.group(2).lower()
    now = datetime.utcnow()
    if unit.startswith("h"):
        return now - timedelta(hours=n)
    if unit.startswith("d"):
        return now - timedelta(days=n)
    if unit.startswith("m"):
        return now - timedelta(minutes=n)
    return None


def fetch_patch_articles():
    articles = []
    try:
        resp = requests.get(
            PATCH_URL,
            headers={"User-Agent": USER_AGENT},
            timeout=20,
        )
        resp.raise_for_status()
    except requests.RequestException as exc:
        log.warning("Patch fetch failed: %s", exc)
        return articles

    soup = BeautifulSoup(resp.text, "lxml")
    seen_urls = set()

    for a in soup.find_all("a", href=True):
        href = a["href"]
        path = urlparse(href).path
        m = ARTICLE_PATH_RE.match(path)
        if not m:
            continue
        slug = m.group(1)
        if slug in PATCH_NON_ARTICLE_SLUGS:
            continue

        url = f"https://patch.com{path}"
        if url in seen_urls:
            continue

        title = a.get_text(strip=True)
        if not title or len(title) < 8:
            # Likely an image/thumbnail link wrapping the same article,
            # not the headline text itself - skip, the real title link
            # will also be in the results.
            continue
        seen_urls.add(url)

        # Walk up a few ancestors looking for a nearby description
        # paragraph and an age label like "Hackettstown|News|12h".
        description = ""
        age_label = ""
        node = a
        for _ in range(4):
            node = node.parent
            if node is None:
                break
            text_block = node.get_text(" ", strip=True)
            if not description:
                # crude: text right after the title in the same block
                idx = text_block.find(title)
                if idx != -1:
                    tail = text_block[idx + len(title):].strip(" |")
                    if len(tail) > 20:
                        description = tail[:400]
            age_match = re.search(r"\|\s*([A-Za-z]+)\|\s*(\d+[a-zA-Z]+)\s*$", text_block[:200])
            if age_match:
                age_label = age_match.group(2)
            if description and age_label:
                break

        published = _parse_relative_age(age_label)

        articles.append(
            {
                "source": "Patch",
                "title": title,
                "description": description,
                "url": url,
                "published": published.isoformat() if published else None,
            }
        )

    return articles
