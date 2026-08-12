import logging
import os
import sqlite3
import threading
import time
from datetime import datetime, timezone

from flask import Flask, render_template, redirect, url_for

from fetch_news import DB_PATH, init_db, run_once

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

app = Flask(__name__)

FETCH_INTERVAL_MINUTES = int(os.environ.get("FETCH_INTERVAL_MINUTES", "30"))

# last_run is shared with the background thread; a plain dict is fine
# here since there's only ever one writer.
state = {"last_run": None, "last_added": None}


def get_articles(limit=200):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT source, title, description, url, published, first_seen "
        "FROM articles "
        "ORDER BY COALESCE(published, first_seen) DESC "
        "LIMIT ?",
        (limit,),
    ).fetchall()
    conn.close()
    return rows


def format_date(iso_str):
    if not iso_str:
        return ""
    try:
        dt = datetime.fromisoformat(iso_str)
        return dt.strftime("%b %d, %Y %I:%M %p").replace(" 0", " ")
    except ValueError:
        return iso_str


@app.route("/")
def index():
    articles = get_articles()
    return render_template(
        "index.html",
        articles=articles,
        format_date=format_date,
        last_run=format_date(state["last_run"]) if state["last_run"] else "never yet",
    )


@app.route("/refresh", methods=["POST"])
def refresh():
    _do_fetch()
    return redirect(url_for("index"))


def _do_fetch():
    try:
        added, total = run_once()
        state["last_run"] = datetime.now(timezone.utc).isoformat()
        state["last_added"] = added
        log.info("Manual/scheduled fetch complete: %d new, %d total", added, total)
    except Exception:
        log.exception("Fetch run failed")


def _background_loop():
    while True:
        _do_fetch()
        time.sleep(FETCH_INTERVAL_MINUTES * 60)


def start_background_fetcher():
    conn = sqlite3.connect(DB_PATH)
    init_db(conn)
    conn.close()
    t = threading.Thread(target=_background_loop, daemon=True)
    t.start()


if __name__ == "__main__":
    start_background_fetcher()
    app.run(host="0.0.0.0", port=5000)
