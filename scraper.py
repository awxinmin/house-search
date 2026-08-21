"""PropertyGuru listing scraper.

Search pages: listing IDs/URLs come from __NEXT_DATA__.props.pageProps.pageData.data.contactAgentCardData
Detail pages: full data from listingData + detailsData.metatable.items
Pagination: requires Referer header on page 2+; session persists Cloudflare cookies.
"""

import json
import re
import time
from urllib.parse import urlencode, urljoin

from bs4 import BeautifulSoup
from curl_cffi import requests as cffi_requests
from datetime import date

from config import BASE_URL, LISTING_BASE_URL, MAX_PAGES_PER_RUN

_IMPERSONATE = "chrome124"

_BASE_HEADERS = {
    "Accept-Language": "en-SG,en;q=0.9",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Upgrade-Insecure-Requests": "1",
}

_ONGOING_RE = re.compile(
    r"ongoing\s+offer|offer\s+ongoing|under\s+offer|offer\s+received|option\s+exercised",
    re.I,
)
_EXT_NEG_RE = re.compile(
    r"no\s+(?:\w+\s+){0,3}extension"
    r"|move[\s-]?in\s+immediately"
    r"|immediate\s+move[\s-]?in"
    r"|immediate\s+(?:vacant\s+)?(?:possession|occupancy)"
    r"|vacant\s+(?:unit,?\s+)?immediate",
    re.I,
)
_EXT_POS_RE = re.compile(
    r"extension\s+(?:of\s+stay\s+)?(?:is\s+)?(?:required|requested|needed|preferred)"
    r"|(?:require|need|prefer)(?:s|d)?\s+(?:an?\s+)?extension"
    r"|\d+[\s-]*(?:month|mth|mo)s?\s+extension"
    r"|extension\s+of\s+stay",
    re.I,
)
_CORNER_RE = re.compile(
    r"\bcorner\s+(?:unit|stack|apartment)\b|\bstand[\s-]?alone\s+corner\b|\bend\s+unit\b", re.I
)
_MRT_RE = re.compile(
    r"(?:walk(?:ing)?\s+(?:distance\s+)?to\s+|near(?:est)?\s+|minutes?\s+(?:walk\s+)?to\s+)"
    r"([A-Za-z][A-Za-z\s/]+?)\s+MRT",
    re.I,
)
_MRT_DIST_RE = re.compile(
    r"(\d+(?:\.\d+)?)\s*(?:km|m(?:etres?|inutess?)?)\s+(?:from|to|away)?\s*(?:[A-Za-z\s]+\s+)?MRT",
    re.I,
)


# ── URL builders ─────────────────────────────────────────────────────────────

def _build_url(base_params: list, page: int, listed_in_days) -> str:
    p = list(base_params)
    if listed_in_days:
        p.append(("lastPosted", str(listed_in_days)))
    if page > 1:
        p.append(("page", str(page)))
    return f"{BASE_URL}?{urlencode(p)}"


def build_hdb_url(page: int = 1, listed_in_days=None) -> str:
    return _build_url(
        [
            ("hdbEstate", "1"), ("hdbEstate", "25"), ("hdbEstate", "3"),
            ("propertyTypeGroup", "H"),
            ("propertyTypeCode", "5A"), ("propertyTypeCode", "5I"),
            ("propertyTypeCode", "5S"), ("propertyTypeCode", "5PA"),
            ("bedrooms", "3"),
            ("minSize", "1000"),
            ("distanceToMRT", "0.75"),
            ("minTopYear", "2000"),
        ],
        page, listed_in_days,
    )


def build_condo_url(page: int = 1, listed_in_days=None) -> str:
    return _build_url(
        [
            ("mrtStations", "CC15"), ("mrtStations", "CC16"), ("mrtStations", "CC17"),
            ("mrtStations", "CR11"), ("mrtStations", "CR13"),
            ("mrtStations", "NS15"), ("mrtStations", "NS16"), ("mrtStations", "NS17"),
            ("mrtStations", "TE5"), ("mrtStations", "TE6"),
            ("mrtStations", "TE7"), ("mrtStations", "TE9"),
            ("maxPrice", "2700000"),
            ("bedrooms", "3"), ("bedrooms", "4"),
            ("minSize", "1000"),
            ("minTopYear", "2000"),
            ("propertyTypeGroup", "N"),
        ],
        page, listed_in_days,
    )


# ── HTTP ──────────────────────────────────────────────────────────────────────

def _client() -> cffi_requests.Session:
    return cffi_requests.Session(impersonate=_IMPERSONATE)


def _fetch(url: str, client: cffi_requests.Session, referer: str = None, delay: float = 2.5) -> str:
    time.sleep(delay)
    headers = dict(_BASE_HEADERS)
    if referer:
        headers["Referer"] = referer
        headers["Sec-Fetch-Site"] = "same-origin"
    resp = client.get(url, headers=headers, timeout=30, allow_redirects=True)
    resp.raise_for_status()
    return resp.text


# ── __NEXT_DATA__ helpers ─────────────────────────────────────────────────────

def _next_data(html: str) -> dict:
    soup = BeautifulSoup(html, "lxml")
    tag = soup.find("script", {"id": "__NEXT_DATA__"})
    if tag and tag.string:
        try:
            return json.loads(tag.string)
        except json.JSONDecodeError:
            pass
    return {}


def _page_data(nd: dict) -> dict:
    return nd.get("props", {}).get("pageProps", {}).get("pageData", {})


# ── Search results page ───────────────────────────────────────────────────────

def _extract_stubs(html: str, listing_type: str) -> dict[str, dict]:
    """Return {listing_id: stub_dict} from contactAgentCardData on search results page."""
    nd = _next_data(html)
    cad = _page_data(nd).get("data", {}).get("contactAgentCardData", {})
    stubs = {}
    for lid, info in cad.items():
        url = info.get("url", "")
        if url and not url.startswith("http"):
            url = urljoin(LISTING_BASE_URL, url)
        stubs[lid] = {
            "id": lid,
            "type": listing_type,
            "url": url,
            "price": info.get("price", 0),
            "address": info.get("propertyName", ""),
            "bedrooms": str(info.get("bedrooms", "")),
        }
    return stubs


# ── Detail page ───────────────────────────────────────────────────────────────

def _parse_details_items(items: list) -> dict:
    """Extract fields from detailsData.metatable.items list."""
    result = {}
    for item in items:
        icon = item.get("icon", "")
        val = item.get("value", "")
        if not val:
            continue
        if "layers-2" in icon:
            result["floor_level"] = re.sub(r"\s*floor\s*level\s*", "", val, flags=re.I).strip()
        elif "calendar-time" in icon:
            # "Listed on 19 Aug 2026"
            m = re.search(r"Listed on (.+)", val, re.I)
            if m:
                result["listed_date"] = m.group(1).strip()
        elif "document-with-lines" in icon:
            if "TOP in" in val:
                result["top_info"] = val  # e.g., "TOP in Aug 2012"
                yr = re.search(r"\d{4}", val)
                if yr:
                    result["top_year"] = yr.group()
    return result


def _remaining_lease(listing_data: dict, detail_extras: dict) -> str:
    """Compute remaining lease string for HDB."""
    top_year = detail_extras.get("top_year") or listing_data.get("completionYear")
    tenure = listing_data.get("tenure", "")
    if top_year and "L99" in tenure:
        try:
            years_elapsed = 2026 - int(top_year)
            remaining = 99 - years_elapsed
            return f"{remaining} years (TOP {top_year})"
        except ValueError:
            pass
    return str(listing_data.get("tenure", ""))


def _extract_mrt_from_desc(desc: str) -> tuple[str, str]:
    """Return (nearest_mrt_name, distance_text) extracted from listing description."""
    mrt_name = ""
    mrt_dist = ""
    m = _MRT_RE.search(desc)
    if m:
        mrt_name = m.group(1).strip().title() + " MRT"
    d = _MRT_DIST_RE.search(desc)
    if d:
        mrt_dist = d.group(0).strip()
    return mrt_name, mrt_dist


def _enrich_from_detail(url: str, client: cffi_requests.Session, search_url: str) -> dict:
    try:
        html = _fetch(url, client, referer=search_url, delay=1.8)
    except Exception as e:
        print(f"    ⚠ detail fetch failed: {e}")
        return {}

    nd = _next_data(html)
    pd = _page_data(nd).get("data", {})

    listing_data = pd.get("listingData", {})
    details_items = pd.get("detailsData", {}).get("metatable", {}).get("items", [])
    desc_data = pd.get("descriptionBlockData", {})
    description = desc_data.get("description", "") or ""

    detail_extras = _parse_details_items(details_items)

    # Full text for ongoing offer check
    full_text = BeautifulSoup(html, "lxml").get_text(" ", strip=True)
    has_ongoing = bool(_ONGOING_RE.search(full_text))

    # Extension of stay — scoped to the listing description only (full-page text
    # picks up unrelated site boilerplate/FAQ mentions of "extension of stay").
    # "No extension needed/required/requested" (or "move in immediately" etc.)
    # overrides a positive match. No mention either way → unknown (None), not False.
    _has_ext_neg = bool(_EXT_NEG_RE.search(description))
    _has_ext_pos = bool(_EXT_POS_RE.search(description))
    if not _has_ext_neg and not _has_ext_pos:
        ext_req = None
    else:
        ext_req = _has_ext_pos and not _has_ext_neg

    _is_corner_unit = bool(_CORNER_RE.search(description))
    if not _is_corner_unit:
        is_corner_unit = None
    else:
        is_corner_unit = _is_corner_unit

    mrt_name, mrt_dist = _extract_mrt_from_desc(description)

    # hdbEstate from listingData
    estate_text = listing_data.get("hdbEstateText", "")
    # estate code mapping
    _estate_text_to_code = {"Ang Mo Kio": "1", "Bishan": "25", "Toa Payoh": "3"}
    estate_code = _estate_text_to_code.get(estate_text, estate_text)

    today = date.today()

    return {
        "id": str(listing_data.get("listingId", "")),
        "address": listing_data.get("propertyName") or listing_data.get("streetName", ""),
        "price": listing_data.get("price", 0),
        "psf": listing_data.get("floorAreaPsf", 0),
        "size_sqft": str(listing_data.get("floorArea", "") or ""),
        "bedrooms": str(listing_data.get("bedrooms", "") or ""),
        "bathrooms": str(listing_data.get("bathrooms", "") or ""),
        "property_type": listing_data.get("hdbTypeCode") or listing_data.get("propertyTypeCode", ""),
        "estate": estate_code,
        "floor_level": detail_extras.get("floor_level", ""),
        "listed_date": detail_extras.get("listed_date", ""),
        "top_year": detail_extras.get("top_year", ""),
        "remaining_lease": _remaining_lease(listing_data, detail_extras),
        "nearest_mrt": mrt_name,
        "mrt_distance": mrt_dist,
        "description": description[:3000],
        "has_ongoing_offer": has_ongoing,
        "extension_required": ext_req,
        "is_corner_unit": is_corner_unit,
        "scraped_date": str(today)
    }


# ── Main scrape ───────────────────────────────────────────────────────────────

def scrape_listings(url_builder, listing_type: str, listed_in_days=None, known_ids: set[str] = frozenset()) -> list[dict]:
    """Scrape search results + detail pages, skipping detail fetches for listings already in `known_ids`.

    Detail-page fetches are the slow, rate-limited part (~2s each); skipping known
    listings before fetching their detail page is what makes repeat runs fast.
    """
    all_stubs: dict[str, dict] = {}
    search_url = url_builder(page=1, listed_in_days=listed_in_days)

    with _client() as client:
        # Phase 1: collect listing stubs from search pages
        prev_url = None
        for page in range(1, MAX_PAGES_PER_RUN + 1):
            url = url_builder(page=page, listed_in_days=listed_in_days)
            print(f"  Page {page} → {url}")
            try:
                html = _fetch(url, client, referer=prev_url, delay=3.0 if page == 1 else 2.5)
            except Exception as e:
                print(f"  ✗ Page {page} failed: {e}")
                break

            stubs = _extract_stubs(html, listing_type)
            if not stubs:
                print(f"  No listings on page {page}, stopping pagination")
                break

            new_count = 0
            for lid, stub in stubs.items():
                if lid not in all_stubs:
                    all_stubs[lid] = stub
                    new_count += 1
            print(f"  Page {page}: {new_count} new stubs (total: {len(all_stubs)})")
            prev_url = url

        # Phase 2: fetch detail pages for stubs not already known
        to_fetch = {lid: stub for lid, stub in all_stubs.items() if lid not in known_ids}
        skipped = len(all_stubs) - len(to_fetch)
        print(f"\n  {len(all_stubs)} stubs found, {skipped} already known (skipped), fetching {len(to_fetch)} detail pages…")

        listings = []
        total = len(to_fetch)
        for i, (lid, stub) in enumerate(to_fetch.items()):
            if not stub.get("url"):
                listings.append(stub)
                continue
            print(f"  [{i+1}/{total}] {stub.get('address') or lid}")
            extra = _enrich_from_detail(stub["url"], client, search_url)
            merged = {**stub, **{k: v for k, v in extra.items() if v}}
            # Always use detail values for these flags
            for flag in ("has_ongoing_offer", "extension_required", "is_corner_unit"):
                if flag in extra:
                    merged[flag] = extra[flag]
            listings.append(merged)

    return listings
