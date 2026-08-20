"""PropertyGuru daily property search agent — scrape, consolidate, export.

Skips detail-page fetches for listings already known (in data/listings.json or
already recorded as sent), so repeat runs only pay the rate-limited fetch cost
for genuinely new listings. Ends by exporting the full consolidated
listings.json to a Google Sheet, or to a local .xlsx if Sheets isn't set up
(see export_listings() setup notes below).
"""

import os
from datetime import date

import gspread
from openpyxl import Workbook

from config import (
    GOOGLE_SERVICE_ACCOUNT_FILE,
    GOOGLE_SHEET_ID,
    GOOGLE_SHEET_WORKSHEET,
    LISTED_IN_DAYS,
    LOCAL_EXCEL_FILE,
    MAX_FIRST_RUN_LISTINGS,
)
from scraper import build_condo_url, build_hdb_url, scrape_listings
from state import load_listings, load_state, save_state, upsert_listings

_SHEET_COLUMNS = [
    "id", "type", "address", "price", "psf", "size_sqft", "bedrooms", "bathrooms",
    "property_type", "estate", "floor_level", "listed_date", "top_year",
    "remaining_lease", "nearest_mrt", "mrt_distance", "is_corner_unit",
    "extension_required", "url", "description",
]


def scrape_and_consolidate() -> tuple[int, int]:
    state = load_state()
    is_first_run: bool = state.get("is_first_run", True)
    sent_ids: set[str] = set(state.get("sent_listing_ids", []))
    known_ids = sent_ids | set(load_listings().keys())
    today = str(date.today())

    listed_in_days = None if is_first_run else LISTED_IN_DAYS
    print(
        f"Mode      : {'FIRST RUN — all listings' if is_first_run else f'DAILY — last {listed_in_days} days'}"
    )
    print(f"Already known: {len(known_ids)}")
    print()

    print("── HDB ──────────────────────────────────────────────────────")
    hdb_raw = scrape_listings(build_hdb_url, "hdb", listed_in_days=listed_in_days, known_ids=known_ids)
    print(f"  New: {len(hdb_raw)}\n")

    print("── Condo ────────────────────────────────────────────────────")
    condo_raw = scrape_listings(build_condo_url, "condo", listed_in_days=listed_in_days, known_ids=known_ids)
    print(f"  New: {len(condo_raw)}\n")

    all_raw = hdb_raw + condo_raw

    new = [l for l in all_raw if not l.get("has_ongoing_offer")]
    print(f"Filtered {len(all_raw) - len(new)} 'ongoing offer' listings")

    if is_first_run and len(new) > MAX_FIRST_RUN_LISTINGS:
        print(f"First run: capping at {MAX_FIRST_RUN_LISTINGS} listings (sorted by price asc)")
        new = sorted(new, key=lambda x: int(x.get("price") or 0))[:MAX_FIRST_RUN_LISTINGS]

    upsert_listings(new)

    new_ids = [l["id"] for l in new]
    state["sent_listing_ids"] = list(sent_ids | set(new_ids))
    state["last_run_date"] = today
    state["is_first_run"] = False
    save_state(state)

    hdb_count = sum(1 for l in new if l.get("type") == "hdb")
    condo_count = len(new) - hdb_count
    return hdb_count, condo_count


def _sheet_row(listing: dict) -> list:
    row = []
    for col in _SHEET_COLUMNS:
        val = listing.get(col, "")
        if col == "description":
            val = (val or "")[:300]
        row.append("" if val is None else val)
    return row


def _export_to_excel(rows: list):
    wb = Workbook()
    ws = wb.active
    ws.title = GOOGLE_SHEET_WORKSHEET
    ws.append(_SHEET_COLUMNS)
    for row in rows:
        ws.append(row)
    os.makedirs(os.path.dirname(LOCAL_EXCEL_FILE) or ".", exist_ok=True)
    wb.save(LOCAL_EXCEL_FILE)
    print(
        f"GOOGLE_SERVICE_ACCOUNT_FILE ('{GOOGLE_SERVICE_ACCOUNT_FILE}') not found — "
        f"wrote {len(rows)} listings to {LOCAL_EXCEL_FILE} instead."
    )


def _export_to_sheet(rows: list):
    gc = gspread.service_account(filename=GOOGLE_SERVICE_ACCOUNT_FILE)
    sh = gc.open_by_key(GOOGLE_SHEET_ID)
    try:
        ws = sh.worksheet(GOOGLE_SHEET_WORKSHEET)
    except gspread.WorksheetNotFound:
        ws = sh.add_worksheet(title=GOOGLE_SHEET_WORKSHEET, rows=len(rows) + 1, cols=len(_SHEET_COLUMNS))

    ws.clear()
    ws.update([_SHEET_COLUMNS] + rows, "A1")

    print(f"Wrote {len(rows)} listings to sheet '{GOOGLE_SHEET_WORKSHEET}' in {sh.url}")


def export_listings():
    """Export data/listings.json to a Google Sheet, or a local .xlsx as a fallback.

    Google Sheets setup (one-time, optional):
      1. Create a GCP service account and download its JSON key to the path in
         config.GOOGLE_SERVICE_ACCOUNT_FILE (default: service_account.json).
      2. Create (or pick) a Google Sheet, share it with the service account's
         `client_email` (Editor access), and set config.GOOGLE_SHEET_ID to the
         spreadsheet ID from its URL.

    Without that key file present, listings are written to a local .xlsx
    (config.LOCAL_EXCEL_FILE) instead — no setup required.
    """
    listings = load_listings()
    if not listings:
        print("data/listings.json is empty — skipping export.")
        return

    rows = [_sheet_row(l) for l in sorted(listings.values(), key=lambda l: (l.get("type", ""), int(l.get("price") or 0)))]

    if not os.path.exists(GOOGLE_SERVICE_ACCOUNT_FILE):
        _export_to_excel(rows)
        return

    if not GOOGLE_SHEET_ID:
        print("GOOGLE_SHEET_ID not set in config.py — skipping Sheets export.")
        return

    _export_to_sheet(rows)


def main():
    print("=" * 60)
    print("PropertyGuru Search Agent")
    print("=" * 60)

    hdb_count, condo_count = scrape_and_consolidate()

    print()
    print("=" * 60)
    print(f"Scrape done — HDB: {hdb_count}  Condo: {condo_count}  Total new: {hdb_count + condo_count}")
    print("=" * 60)

    export_listings()


if __name__ == "__main__":
    main()
