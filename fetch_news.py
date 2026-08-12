"""
Pulls every configured source, normalizes into a common shape, and
upserts into a local SQLite database. Safe to run repeatedly - articles
are deduped by URL, so running it every 30 minutes just adds whatever's
new.

Run directly to do a one-off fetch:
    python fetch_news.py

Or import run_once() from app.py to run it on a schedule.
"""
import logging
import os
import re
import sqlite3
import time
from datetime import datetime, timezone

import feedparser
from bs4 import BeautifulSoup

from sources import RSS_SOURCES, USER_AGENT
from patch_scraper import fetch_patch_articles

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

DB_PATH = os.environ.get("NEWS_DB_PATH", "news.db")

# Google News RSS titles look like "Actual Headline - Source Name".
# Strip the " - Source Name" suffix so it matches how the other sources
# display titles.
GOOGLE_NEWS_SUFFIX_RE = re.compile(r"\s+-\s+[^-]+$")


def init_db(conn):
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS articles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source TEXT NOT NULL,
            title TEXT NOT NULL,
            description TEXT,
            url TEXT NOT NULL UNIQUE,
            published TEXT,
            first_seen TEXT NOT NULL
        )
        """
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_articles_published ON articles(published)")
    conn.commit()


def clean_html(raw: str) -> str:
    if not raw:
        return ""
    text = BeautifulSoup(raw, "lxml").get_text(" ", strip=True)
    return text[:500]


def clean_google_news_title(title: str) -> str:
    return GOOGLE_NEWS_SUFFIX_RE.sub("", title or "").strip()


def parse_published(entry):
    for key in ("published_parsed", "updated_parsed"):
        val = getattr(entry, key, None)
        if val:
            try:
                return datetime.fromtimestamp(time.mktime(val), tz=timezone.utc).isoformat()
            except (OverflowError, ValueError):
                pass
    return None


def fetch_rss_source(source: dict) -> list:
    articles = []
    try:
        feed = feedparser.parse(source["url"], agent=USER_AGENT)
    except Exception as exc:  # feedparser rarely raises, but just in case
        log.warning("Failed to fetch %s: %s", source["name"], exc)
        return articles

    if getattr(feed, "bozo", False) and not feed.entries:
        log.warning("Feed %s looked malformed and returned no entries: %s", source["name"], feed.bozo_exception)
        return articles

    is_google_news = "news.google.com" in source["url"]

    for entry in feed.entries:
        title = entry.get("title", "").strip()
        description = clean_html(entry.get("summary", "") or entry.get("description", ""))
        if is_google_news:
            title = clean_google_news_title(title)

        if source.get("filter") and not source["filter"](title, description):
            continue

        articles.append(
            {
                "source": source["name"],
                "title": title,
                "description": description,
                "url": entry.get("link", "").strip(),
                "published": parse_published(entry),
            }
        )
    return articles


def upsert_articles(conn, articles: list) -> int:
    now = datetime.now(timezone.utc).isoformat()
    added = 0
    for a in articles:
        if not a.get("url") or not a.get("title"):
            continue
        cur = conn.execute(
            "INSERT OR IGNORE INTO articles (source, title, description, url, published, first_seen) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (a["source"], a["title"], a.get("description", ""), a["url"], a.get("published"), now),
        )
        if cur.rowcount:
            added += 1
    conn.commit()
    return added


def run_once():
    conn = sqlite3.connect(DB_PATH)
    init_db(conn)

    all_articles = []
    for source in RSS_SOURCES:
        log.info("Fetching %s", source["name"])
        all_articles.extend(fetch_rss_source(source))

    log.info("Fetching Patch (scrape)")
    all_articles.extend(fetch_patch_articles())

    added = upsert_articles(conn, all_articles)
    total = conn.execute("SELECT COUNT(*) FROM articles").fetchone()[0]
    conn.close()

    log.info("Fetched %d articles this run, %d new, %d total in DB", len(all_articles), added, total)
    return added, total


if __name__ == "__main__":
    run_once()
