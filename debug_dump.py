"""
Dumps raw HTML for a source to a file so you can inspect it in a browser
or text editor and fix selectors in patch_scraper.py if Patch changes
its layout. Not needed for normal operation.

Usage:
    python debug_dump.py https://patch.com/new-jersey/hackettstown
"""
import sys

import requests

from sources import USER_AGENT

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(__doc__)
        sys.exit(1)
    url = sys.argv[1]
    resp = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=20)
    out_path = "debug_dump.html"
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(resp.text)
    print(f"Status: {resp.status_code}")
    print(f"Saved {len(resp.text)} chars to {out_path}")
