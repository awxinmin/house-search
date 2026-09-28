"""Step 3: consume analyzed listings, persist, update state, write email output.

Run after PENDING_ANALYSIS_FILE has been populated by scrape.py and then had
"analysis" filled in on every listing by the `analyze-listings` skill.
"""

import json
import os

from config import EMAIL_OUTPUT_FILE, PENDING_ANALYSIS_FILE
from email_formatter import format_email
from state import load_state, save_state, upsert_listings

_SCORE_KEYS = ("size_score", "value_score", "layout_score", "convenience_score", "lease_score")

_DEFAULT_ANALYSIS = {
    "total_score": 0,
    "size_score": 0,
    "value_score": 0,
    "layout_score": 0,
    "convenience_score": 0,
    "lease_score": 0,
    "key_points": ["Analysis unavailable"],
    "layout_description": "N/A",
    "extension_required": None,
    "value_assessment": "N/A",
    "pros": [],
    "cons": [],
}


def _normalize_analysis(analysis: dict | None) -> dict:
    if not analysis:
        return dict(_DEFAULT_ANALYSIS)
    result = dict(analysis)
    for key in _SCORE_KEYS:
        result[key] = max(0, min(20, int(result.get(key, 0) or 0)))
    result["total_score"] = sum(result[k] for k in _SCORE_KEYS)
    return result


def main():
    with open(PENDING_ANALYSIS_FILE) as f:
        pending = json.load(f)

    run_date = pending["run_date"]
    new = pending["listings"]

    missing = [l["id"] for l in new if not l.get("analysis")]
    if missing:
        raise SystemExit(
            f"{len(missing)} listings missing 'analysis' — run the analyze-listings skill first: {missing[:5]}"
        )

    for lst in new:
        lst["analysis"] = _normalize_analysis(lst["analysis"])

    upsert_listings(new)

    state = load_state()
    sent_ids = set(state.get("sent_listing_ids", []))
    new_ids = [l["id"] for l in new]
    state["sent_listing_ids"] = list(sent_ids | set(new_ids))
    state["last_run_date"] = run_date
    state["is_first_run"] = False
    save_state(state)

    hdb_new = [l for l in new if l.get("type") == "hdb"]
    condo_new = [l for l in new if l.get("type") == "condo"]
    subject, html_body = format_email(hdb_new, condo_new, run_date)

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

    print("=" * 60)
    print(f"Done  — HDB: {len(hdb_new)}  Condo: {len(condo_new)}")
    print(f"Email output → {EMAIL_OUTPUT_FILE}")
    print(f"Subject: {subject}")
    print("=" * 60)


if __name__ == "__main__":
    main()
