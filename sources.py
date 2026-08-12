"""
Source configuration for the Hackettstown news aggregator.

Design notes (read this before "fixing" a broken source):

- hackettstown.net and wrnjradio.com both publish real RSS/XML feeds, so
  they're fetched directly with feedparser. No scraping needed.

- lehighvalleylive.com, dailyrecord.com, and njherald.com all actively
  block simple automated requests (confirmed while building this - plain
  GETs came back blocked). Daily Record and NJ Herald are Gannett/USA
  Today Network sites that render search results with JavaScript, so even
  if the block were lifted, a plain requests+BeautifulSoup scraper
  wouldn't see any results. Rather than fight bot-detection and a JS
  search UI, these three use Google News' public RSS search
  (news.google.com/rss/search) filtered to the specific site with a
  `site:` query. It's a proxy, not the original site's markup, so item
  descriptions are short Google-generated snippets rather than full
  article ledes - that's an acceptable trade for reliability.

- patch.com does NOT block plain requests, so it's scraped directly.
  Patch's HTML structure isn't officially documented and can change
  without notice, so patch_scraper.py is intentionally written to degrade
  gracefully (skip a story it can't parse rather than crash the whole
  run) and there's a `debug_dump.py` helper to pull down the current raw
  HTML if the selectors ever need updating.
"""

GOOGLE_NEWS_HL = "hl=en-US&gl=US&ceid=US:en"


def google_news_rss(query: str) -> str:
    from urllib.parse import quote

    return f"https://news.google.com/rss/search?q={quote(query)}&{GOOGLE_NEWS_HL}"


def wrnj_hackettstown_filter(title: str, description: str) -> bool:
    """Keep only WRNJ News Dept items whose description starts with
    'Hackettstown' or 'Warren County' (their dateline convention), per
    the user's requirement. Case-insensitive."""
    text = (description or "").strip().upper()
    return text.startswith("HACKETTSTOWN") or text.startswith("WARREN COUNTY")


# --- RSS / XML sources (feedparser handles all of these) -------------------
RSS_SOURCES = [
    {
        "name": "Hackettstown.net Newsflash",
        "url": "https://www.hackettstown.net/RSSFeed.aspx?ModID=1&CID=All-newsflash.xml",
        "filter": None,
    },
    {
        "name": "WRNJ Radio (search: hackettstown)",
        "url": "https://wrnjradio.com/?s=hackettstown&feed=rss2",
        "filter": None,
    },
    {
        "name": "WRNJ Radio - News Dept",
        "url": "https://wrnjradio.com/category/wrnj-news/news-dept/feed/",
        "filter": wrnj_hackettstown_filter,
    },
    {
        "name": "lehighvalleylive.com (via Google News)",
        "url": google_news_rss("hackettstown site:lehighvalleylive.com"),
        "filter": None,
    },
    {
        "name": "Daily Record (via Google News)",
        "url": google_news_rss("hackettstown site:dailyrecord.com"),
        "filter": None,
    },
    {
        "name": "NJ Herald (via Google News)",
        "url": google_news_rss("hackettstown site:njherald.com"),
        "filter": None,
    },
]

# --- Scraped sources ---------------------------------------------------
PATCH_URL = "https://patch.com/new-jersey/hackettstown"

# Patch also republishes region-wide stories (from nearby towns) on this
# page. We only keep links whose path is directly under
# /new-jersey/hackettstown/ and isn't one of these known non-article pages.
PATCH_NON_ARTICLE_SLUGS = {
    "calendar",
    "businesses",
    "advertise-with-us",
    "classifieds",
    "photos",
    "platform",
    "compose",
}

USER_AGENT = (
    "Mozilla/5.0 (compatible; HackettstownNewsBot/1.0; "
    "personal single-user RSS reader; not for redistribution)"
)
