# PropertyGuru base URL
BASE_URL = "https://www.propertyguru.com.sg/property-for-sale"
LISTING_BASE_URL = "https://www.propertyguru.com.sg"

STATE_FILE = "data/state.json"
LISTINGS_FILE = "data/listings.json"

MAX_PAGES_PER_RUN = 15
LISTED_IN_DAYS = 7            # filter window for daily (non-first) runs
MAX_FIRST_RUN_LISTINGS = 165  # cap detail-page fetches on first run (sorted by price asc)

# Listings export (see export_listings() in main.py)
GOOGLE_SHEET_ID = ""                             # spreadsheet ID from its URL
GOOGLE_SERVICE_ACCOUNT_FILE = "service_account.json"  # path to service account key JSON
GOOGLE_SHEET_WORKSHEET = "Listings"
LOCAL_EXCEL_FILE = "data/listings.xlsx"  # fallback used when GOOGLE_SERVICE_ACCOUNT_FILE is missing
