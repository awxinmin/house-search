HDB_ESTATE_MAP = {
    "1": "Ang Mo Kio",
    "25": "Bishan",
    "3": "Toa Payoh",
}

MRT_STATION_MAP = {
    "CC15": "Bishan (CC15)",
    "CC16": "Marymount (CC16)",
    "CC17": "Caldecott (CC17)",
    "CR11": "Ang Mo Kio (CR11)",
    "CR13": "Bright Hill (CR13)",
    "NS15": "Yio Chu Kang (NS15)",
    "NS16": "Ang Mo Kio (NS16)",
    "NS17": "Bishan (NS17)",
    "TE5": "Lentor (TE5)",
    "TE6": "Mayflower (TE6)",
    "TE7": "Bright Hill (TE7)",
    "TE9": "Caldecott (TE9)",
}

# PropertyGuru base URL
BASE_URL = "https://www.propertyguru.com.sg/property-for-sale"
LISTING_BASE_URL = "https://www.propertyguru.com.sg"

EMAIL_TO = "for.ai.awxm@gmail.com"
STATE_FILE = "data/state.json"
LISTINGS_FILE = "data/listings.json"
EMAIL_OUTPUT_FILE = "data/email_output.json"
PENDING_ANALYSIS_FILE = "data/pending_analysis.json"

MAX_PAGES_PER_RUN = 15
LISTED_IN_DAYS = 7          # filter window for daily (non-first) runs
MAX_ANALYZE_FIRST_RUN = 165  # cap analysis calls on first run

# HDB market PSF benchmarks (S$/sqft) for value scoring
HDB_PSF_MARKET = {
    "1": (450, 590),   # AMK  (low, high)
    "25": (550, 700),  # Bishan
    "3": (480, 630),   # Toa Payoh
}

# Condo market PSF benchmarks
CONDO_PSF_MARKET = (1400, 2200)
