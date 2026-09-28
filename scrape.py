"""Step 1: scrape PropertyGuru + filter, write pending listings for analysis.

No LLM call here. Run this, then have Claude (via the `analyze-listings` skill)
fill in each listing's "analysis" field in PENDING_ANALYSIS_FILE, then run
finalize.py.
"""

import json
import os
from datetime import date

from config import LISTED_IN_DAYS, MAX_ANALYZE_FIRST_RUN, PENDING_ANALYSIS_FILE
from scraper import build_condo_url, build_hdb_url, scrape_listings
from state import load_state


def main():
    print("=" * 60)
    print("PropertyGuru Search Agent — scrape")
    print("=" * 60)

    state = load_state()
    is_first_run: bool = state.get("is_first_run", True)
    sent_ids: set[str] = set(state.get("sent_listing_ids", []))
    today = str(date.today())

    listed_in_days = None if is_first_run else LISTED_IN_DAYS
    print(
        f"Mode      : {'FIRST RUN — all listings' if is_first_run else f'DAILY — last {listed_in_days} days'}"
    )
    print(f"Previously sent: {len(sent_ids)}")
    print()

    print("── HDB ──────────────────────────────────────────────────────")
    hdb_raw = scrape_listings(build_hdb_url, "hdb", listed_in_days=listed_in_days)
    print(f"  Total scraped: {len(hdb_raw)}\n")

    print("── Condo ────────────────────────────────────────────────────")
    condo_raw = scrape_listings(build_condo_url, "condo", listed_in_days=listed_in_days)
    print(f"  Total scraped: {len(condo_raw)}\n")

    all_raw = hdb_raw + condo_raw

    clean = [l for l in all_raw if not l.get("has_ongoing_offer")]
    print(f"Filtered {len(all_raw) - len(clean)} 'ongoing offer' listings")

    new = [l for l in clean if l["id"] not in sent_ids]
    print(f"New (unsent): {len(new)}\n")

    if is_first_run and len(new) > MAX_ANALYZE_FIRST_RUN:
        print(f"First run: capping at {MAX_ANALYZE_FIRST_RUN} listings (sorted by price asc)")
        new = sorted(new, key=lambda x: int(x.get("price") or 0))[:MAX_ANALYZE_FIRST_RUN]

    os.makedirs("data", exist_ok=True)
    with open(PENDING_ANALYSIS_FILE, "w") as f:
        json.dump(
            {"run_date": today, "is_first_run": is_first_run, "listings": new},
            f,
            ensure_ascii=False,
            indent=2,
            default=str,
        )

    print(f"Wrote {len(new)} listings → {PENDING_ANALYSIS_FILE}")
    print("Next: have Claude run the `analyze-listings` skill on this file, then run finalize.py")


if __name__ == "__main__":
    main()
