# Hackettstown News Aggregator

A very simple local news aggregator: pulls headline/description/date from
several sources covering Hackettstown, NJ, dedupes them, and serves them
as a single scrolling webpage. Built to run in Docker on your Pi.

## How each source is actually handled

| Source | Method | Why |
|---|---|---|
| hackettstown.net Newsflash | Direct RSS | They publish a real feed. |
| WRNJ Radio (search + News Dept) | Direct RSS | WordPress auto-generates feeds even though they're not linked in the nav (`/feed/`, `/category/.../feed/`, `/?s=...&feed=rss2`). |
| patch.com | Scraped (requests + BeautifulSoup) | No RSS, but plain requests aren't blocked. |
| lehighvalleylive.com | Google News RSS, filtered to `site:lehighvalleylive.com` | Direct requests to this site came back blocked while building this. |
| dailyrecord.com | Google News RSS, filtered to `site:dailyrecord.com` | Gannett/USA Today Network site — blocks plain requests **and** renders its search results with JavaScript, so even an unblocked scraper wouldn't see results without a headless browser. |
| njherald.com | Google News RSS, filtered to `site:njherald.com` | Same as Daily Record (same publisher family). |

**Trade-off to know about:** the three Google News-backed sources give you
short Google-generated snippets instead of the outlet's own description
text, and links go through a Google News redirect rather than the
original URL directly (they still work, just resolve through Google
first). This was the more reliable option given those three sites
actively resist scraping — a headless-browser approach (Playwright) is
possible later if you want the real snippets badly enough, but it's a
meaningfully bigger, more fragile piece of infrastructure for a Pi to
run continuously.

**Patch is heuristic, not exact.** Patch doesn't document its HTML and
mixes in some nearby-town stories on that page. The scraper only keeps
links that go directly to `/new-jersey/hackettstown/<article-slug>` and
skips known non-article pages (calendar, businesses, classifieds, etc).
Descriptions and timestamps are pulled from nearby text with some
guesswork, so occasionally a story may have a blank description or
missing date rather than a wrong one — it's written to skip what it
can't confidently parse rather than guess. If Patch redesigns their page
and results dry up, run:

```
python debug_dump.py https://patch.com/new-jersey/hackettstown
```

and open the saved `debug_dump.html` to see the current markup, then
adjust `patch_scraper.py`.

## Local test run (no Docker)

```bash
cd hackettstown-news
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
python fetch_news.py       # does one fetch, populates news.db
python app.py               # serves http://localhost:5000, also starts
                             # the background 30-min refetch loop
```

## Deploying on the Pi (Docker / Portainer)

1. Copy the `hackettstown-news` folder onto the Pi (or `git clone` if you
   push it to a repo first).
2. In Portainer: **Stacks → Add stack**, point it at this folder's
   `docker-compose.yml` (or paste its contents in), deploy.
3. Visit `http://<pi-ip>:5000`.

The container fetches all sources once on startup, then every
`FETCH_INTERVAL_MINUTES` (default 30, set via the environment variable in
`docker-compose.yml`). Articles persist in a named Docker volume
(`hackettstown-news-data`), so restarts don't lose history. There's also
a "Refresh now" button on the page for an on-demand fetch.

## Things worth tuning later, if you want

- **Retention / pruning** — right now everything ever seen stays in the
  DB forever. Fine for a while; add a `DELETE FROM articles WHERE
  first_seen < ...` if it grows past what you care to scroll through.
- **Per-source failure visibility** — a failed source currently just logs
  a warning and contributes zero articles that run; there's no on-page
  indicator saying "Daily Record didn't return anything this time."
  Worth adding if a source going quiet for days would be worth knowing
  about.
- **Etiquette** — the Patch scraper identifies itself with a descriptive
  User-Agent and only hits the page once per fetch interval (not
  per-visit), which keeps it well within polite-scraping norms for a
  single low-traffic personal use case.
