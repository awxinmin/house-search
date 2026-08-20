"""PropertyGuru daily property search agent — orchestration entry point."""

import json
import os
from datetime import date

from analyzer import analyze_listing
from config import EMAIL_OUTPUT_FILE, LISTED_IN_DAYS, MAX_ANALYZE_FIRST_RUN
from email_formatter import format_email
from scraper import build_condo_url, build_hdb_url, scrape_listings
from state import load_state, save_state, upsert_listings


def main():
    print("=" * 60)
    print("PropertyGuru Search Agent")
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

    # ── Scrape ────────────────────────────────────────────────────────────────
    print("── HDB ──────────────────────────────────────────────────────")
    hdb_raw = scrape_listings(build_hdb_url, "hdb", listed_in_days=listed_in_days)
    print(f"  Total scraped: {len(hdb_raw)}\n")

    print("── Condo ────────────────────────────────────────────────────")
    condo_raw = scrape_listings(build_condo_url, "condo", listed_in_days=listed_in_days)
    print(f"  Total scraped: {len(condo_raw)}\n")

    all_raw = hdb_raw + condo_raw

    # ── Filter: ongoing offer ─────────────────────────────────────────────────
    clean = [l for l in all_raw if not l.get("has_ongoing_offer")]
    print(f"Filtered {len(all_raw) - len(clean)} 'ongoing offer' listings")

    # ── Filter: already sent ──────────────────────────────────────────────────
    new = [l for l in clean if l["id"] not in sent_ids]
    print(f"New (unsent): {len(new)}\n")

    # Cap first-run analysis to avoid excessive API cost/time
    if is_first_run and len(new) > MAX_ANALYZE_FIRST_RUN:
        print(f"First run: capping at {MAX_ANALYZE_FIRST_RUN} listings (sorted by price asc)")
        new = sorted(new, key=lambda x: int(x.get("price") or 0))[:MAX_ANALYZE_FIRST_RUN]

    hdb_new = [l for l in new if l.get("type") == "hdb"]
    condo_new = [l for l in new if l.get("type") == "condo"]

    # ── Analyze ───────────────────────────────────────────────────────────────
    print(f"── Analyzing {len(new)} listings ────────────────────────────")
    for i, lst in enumerate(new):
        label = lst.get("address") or lst["id"]
        print(f"  [{i+1}/{len(new)}] {label}")
        analysis = analyze_listing(lst)
        lst["analysis"] = analysis
        print(
            f"       Score {analysis['total_score']}/100  "
            f"(Sz:{analysis['size_score']} Val:{analysis['value_score']} "
            f"Ly:{analysis['layout_score']} Cv:{analysis['convenience_score']} "
            f"Ls:{analysis['lease_score']})"
        )

    # ── Persist ───────────────────────────────────────────────────────────────
    upsert_listings(new)

    new_ids = [l["id"] for l in new]
    state["sent_listing_ids"] = list(sent_ids | set(new_ids))
    state["last_run_date"] = today
    state["is_first_run"] = False
    save_state(state)

    # ── Email output ──────────────────────────────────────────────────────────
    subject, html_body = format_email(hdb_new, condo_new, today)

    os.makedirs("data", exist_ok=True)
    with open(EMAIL_OUTPUT_FILE, "w") as f:
        json.dump(
            {
                "subject": subject,
                "html": html_body,
                "hdb_count": len(hdb_new),
                "condo_count": len(condo_new),
                "total": len(new),
            },
            f,
            ensure_ascii=False,
        )

    print()
    print("=" * 60)
    print(f"Done  — HDB: {len(hdb_new)}  Condo: {len(condo_new)}")
    print(f"Email output → {EMAIL_OUTPUT_FILE}")
    print(f"Subject: {subject}")
    print("=" * 60)


if __name__ == "__main__":
    main()
