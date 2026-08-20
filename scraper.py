"""PropertyGuru listing scraper using __NEXT_DATA__ JSON with HTML fallback."""

import json
import re
import time
from urllib.parse import urlencode, urljoin

import httpx
from bs4 import BeautifulSoup

from config import BASE_URL, LISTING_BASE_URL, MAX_PAGES_PER_RUN

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": (
        "text/html,application/xhtml+xml,application/xml;"
        "q=0.9,image/avif,image/webp,*/*;q=0.8"
    ),
    "Accept-Language": "en-SG,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Sec-Ch-Ua": '"Chromium";v="124", "Google Chrome";v="124"',
    "Sec-Ch-Ua-Mobile": "?0",
    "Sec-Ch-Ua-Platform": '"macOS"',
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Upgrade-Insecure-Requests": "1",
}

_ONGOING_OFFER_RE = re.compile(
    r"ongoing\s+offer|offer\s+ongoing|under\s+offer|offer\s+received|option\s+exercised",
    re.I,
)


# ── URL builders ─────────────────────────────────────────────────────────────

def _build_url(base_params: list[tuple], page: int, listed_in_days: int | None) -> str:
    p = list(base_params)
    if listed_in_days:
        p.append(("listedIn", str(listed_in_days)))
    if page > 1:
        p.append(("page", str(page)))
    return f"{BASE_URL}?{urlencode(p)}"


def build_hdb_url(page: int = 1, listed_in_days: int | None = None) -> str:
    return _build_url(
        [
            ("hdbEstate", "1"),
            ("hdbEstate", "25"),
            ("hdbEstate", "3"),
            ("propertyTypeGroup", "H"),
            ("propertyTypeCode", "5A"),
            ("propertyTypeCode", "5I"),
            ("propertyTypeCode", "5S"),
            ("propertyTypeCode", "5PA"),
            ("bedrooms", "3"),
            ("minSize", "1000"),
            ("distanceToMRT", "0.75"),
            ("minTopYear", "1990"),
        ],
        page,
        listed_in_days,
    )


def build_condo_url(page: int = 1, listed_in_days: int | None = None) -> str:
    return _build_url(
        [
            ("mrtStations", "CC15"),
            ("mrtStations", "CC16"),
            ("mrtStations", "CC17"),
            ("mrtStations", "CR11"),
            ("mrtStations", "CR13"),
            ("mrtStations", "NS15"),
            ("mrtStations", "NS16"),
            ("mrtStations", "NS17"),
            ("mrtStations", "TE5"),
            ("mrtStations", "TE6"),
            ("mrtStations", "TE7"),
            ("mrtStations", "TE9"),
            ("maxPrice", "2700000"),
            ("bedrooms", "3"),
            ("bedrooms", "4"),
            ("minSize", "1000"),
            ("minTopYear", "2000"),
            ("propertyTypeGroup", "N"),
        ],
        page,
        listed_in_days,
    )


# ── HTTP helpers ──────────────────────────────────────────────────────────────

def _client() -> httpx.Client:
    return httpx.Client(timeout=30, follow_redirects=True, http2=True)


def _fetch(url: str, client: httpx.Client, delay: float = 2.5) -> str:
    time.sleep(delay)
    resp = client.get(url, headers=_HEADERS)
    resp.raise_for_status()
    return resp.text


# ── Parsing ───────────────────────────────────────────────────────────────────

def _next_data(html: str) -> dict:
    soup = BeautifulSoup(html, "lxml")
    tag = soup.find("script", {"id": "__NEXT_DATA__"})
    if tag and tag.string:
        try:
            return json.loads(tag.string)
        except json.JSONDecodeError:
            pass
    return {}


def _int(val) -> int:
    if isinstance(val, (int, float)):
        return int(val)
    if isinstance(val, str):
        clean = re.sub(r"[^\d]", "", val)
        return int(clean) if clean else 0
    return 0


def _float(val) -> float:
    if isinstance(val, (int, float)):
        return float(val)
    if isinstance(val, str):
        clean = re.sub(r"[^\d.]", "", val)
        return float(clean) if clean else 0.0
    return 0.0


def _str(val) -> str:
    return str(val).strip() if val is not None else ""


def _norm_listing(raw: dict, listing_type: str) -> dict | None:
    lid = _str(
        raw.get("id") or raw.get("listingId") or raw.get("listing_id")
    )
    if not lid:
        return None

    url_path = _str(
        raw.get("listingUrl") or raw.get("url") or raw.get("listing_url")
    )
    url = url_path if url_path.startswith("http") else urljoin(LISTING_BASE_URL, url_path)

    return {
        "id": lid,
        "type": listing_type,
        "url": url,
        "title": _str(raw.get("name") or raw.get("title") or raw.get("listing_title")),
        "address": _str(
            raw.get("address") or raw.get("formattedAddress") or
            raw.get("formatted_address") or raw.get("streetName") or
            raw.get("street_name")
        ),
        "price": _int(raw.get("price") or raw.get("askingPrice") or raw.get("asking_price")),
        "psf": _float(
            raw.get("unitPrice") or raw.get("pricePerSqft") or
            raw.get("psf") or raw.get("price_per_sqft")
        ),
        "bedrooms": _str(
            raw.get("bedroomFormatted") or raw.get("bedroom") or raw.get("bedrooms")
        ),
        "bathrooms": _str(
            raw.get("bathroomFormatted") or raw.get("bathroom") or raw.get("bathrooms")
        ),
        "size_sqft": _str(
            raw.get("size") or raw.get("floorSize") or raw.get("floor_size") or
            raw.get("landSize")
        ),
        "floor_level": _str(raw.get("floorLevel") or raw.get("floor_level")),
        "estate": _str(raw.get("hdbEstate") or raw.get("hdb_estate")),
        "property_type": _str(
            raw.get("propertyTypeCode") or raw.get("property_type_code") or
            raw.get("propertyType")
        ),
        "nearest_mrt": _str(
            raw.get("nearestMrt") or raw.get("nearest_mrt") or
            raw.get("mrtStation") or raw.get("mrt_station")
        ),
        "mrt_distance": _str(
            raw.get("nearestMrtDistance") or raw.get("mrt_distance") or
            raw.get("mrtDistance")
        ),
        "listed_date": _str(
            raw.get("listedAt") or raw.get("listed_at") or
            raw.get("listDate") or raw.get("list_date")
        ),
        "updated_date": _str(
            raw.get("updatedAt") or raw.get("updated_at") or raw.get("updateDate")
        ),
        "remaining_lease": _str(
            raw.get("remainingLease") or raw.get("remaining_lease") or
            raw.get("tenure") or raw.get("leaseInfo")
        ),
        "top_year": _str(raw.get("topYear") or raw.get("top_year") or raw.get("completionYear")),
        "description": _str(
            raw.get("description") or raw.get("listingDescription") or
            raw.get("remarks")
        ),
        "has_ongoing_offer": False,
        "extension_required": False,
        "fetch_detail": True,
    }


def _parse_next_data_listings(data: dict, listing_type: str) -> list[dict]:
    if not data:
        return []
    props = data.get("props", {}).get("pageProps", {})
    raw_list = (
        props.get("listings") or
        props.get("searchResult", {}).get("listings") or
        props.get("data", {}).get("listings") or
        props.get("initialData", {}).get("listings") or
        props.get("searchData", {}).get("listings") or
        []
    )
    result = []
    for item in raw_list:
        norm = _norm_listing(item, listing_type)
        if norm:
            result.append(norm)
    return result


def _parse_html_listings(html: str, listing_type: str) -> list[dict]:
    """Fallback: extract minimal listing info from raw HTML."""
    soup = BeautifulSoup(html, "lxml")
    results = []
    cards = soup.select("[data-listing-id], .listing-card, [class*='ListingCard']")
    for card in cards:
        lid = card.get("data-listing-id") or card.get("data-id", "")
        link = card.select_one("a[href*='property-for-sale'], a[href*='/listing/']")
        url = urljoin(LISTING_BASE_URL, link["href"]) if link else ""
        if not lid and url:
            m = re.search(r"-(\d{6,})(?:[/?#]|$)", url)
            lid = m.group(1) if m else ""
        if not lid:
            continue
        price_el = card.select_one("[class*='price'], [class*='Price']")
        addr_el = card.select_one("h3, h2, [class*='address'], [class*='title']")
        results.append({
            "id": lid,
            "type": listing_type,
            "url": url,
            "title": addr_el.get_text(strip=True) if addr_el else "",
            "address": addr_el.get_text(strip=True) if addr_el else "",
            "price": _int(price_el.get_text() if price_el else ""),
            "psf": 0.0,
            "bedrooms": "", "bathrooms": "", "size_sqft": "", "floor_level": "",
            "estate": "", "property_type": "", "nearest_mrt": "", "mrt_distance": "",
            "listed_date": "", "updated_date": "", "remaining_lease": "", "top_year": "",
            "description": "",
            "has_ongoing_offer": False,
            "extension_required": False,
            "fetch_detail": True,
        })
    return results


def _total_pages(html: str, data: dict) -> int:
    props = data.get("props", {}).get("pageProps", {}) if data else {}
    for path in [
        lambda p: p.get("totalPages"),
        lambda p: p.get("searchResult", {}).get("totalPages"),
        lambda p: p.get("pagination", {}).get("totalPage"),
        lambda p: p.get("data", {}).get("totalPages"),
        lambda p: p.get("searchData", {}).get("totalPages"),
    ]:
        val = path(props)
        if val:
            try:
                return int(val)
            except (ValueError, TypeError):
                pass
    # HTML fallback
    soup = BeautifulSoup(html, "lxml")
    nums = [
        int(el.get_text())
        for el in soup.select(".pagination a, [class*='pagination'] a")
        if el.get_text().strip().isdigit()
    ]
    return max(nums) if nums else 1


# ── Detail page ───────────────────────────────────────────────────────────────

def _enrich_from_detail(url: str, client: httpx.Client) -> dict:
    try:
        html = _fetch(url, client, delay=1.8)
    except Exception as e:
        print(f"    ⚠ detail fetch failed: {e}")
        return {}

    full_text = BeautifulSoup(html, "lxml").get_text(" ", strip=True)
    result: dict = {}

    # Check ongoing offer
    result["has_ongoing_offer"] = bool(_ONGOING_OFFER_RE.search(full_text))

    # Extension of stay
    result["extension_required"] = bool(
        re.search(
            r"extension\s+of\s+stay|extension\s+required|seller.*extension|owner.*extension",
            full_text,
            re.I,
        )
    )

    # Enrich from __NEXT_DATA__ if present
    data = _next_data(html)
    if data:
        props = data.get("props", {}).get("pageProps", {})
        raw = (
            props.get("listing") or
            props.get("data", {}).get("listing") or
            props.get("initialData", {}).get("listing") or
            {}
        )
        if raw:
            norm = _norm_listing(raw, "")
            if norm:
                for k, v in norm.items():
                    if v:
                        result[k] = v

    # Fallback: remaining lease
    if not result.get("remaining_lease"):
        m = re.search(
            r"(\d+)\s+years?\s+(?:\d+\s+months?\s+)?remaining(?:\s+lease)?",
            full_text,
            re.I,
        )
        if m:
            result["remaining_lease"] = f"{m.group(1)} years"

    return result


# ── Main scrape function ──────────────────────────────────────────────────────

def scrape_listings(
    url_builder,
    listing_type: str,
    listed_in_days: int | None = None,
) -> list[dict]:
    all_listings: list[dict] = []
    seen_ids: set[str] = set()

    with _client() as client:
        url = url_builder(page=1, listed_in_days=listed_in_days)
        print(f"  Page 1 → {url}")
        try:
            html = _fetch(url, client, delay=3.0)
        except httpx.HTTPStatusError as e:
            print(f"  ✗ HTTP {e.response.status_code} — PropertyGuru may be blocking. Try again later.")
            return []

        data = _next_data(html)
        listings = _parse_next_data_listings(data, listing_type)
        if not listings:
            listings = _parse_html_listings(html, listing_type)

        for lst in listings:
            if lst["id"] not in seen_ids:
                seen_ids.add(lst["id"])
                all_listings.append(lst)

        total = min(_total_pages(html, data), MAX_PAGES_PER_RUN)
        print(f"  Page 1: {len(listings)} listings (total pages: {total})")

        for page in range(2, total + 1):
            url = url_builder(page=page, listed_in_days=listed_in_days)
            print(f"  Page {page} → {url}")
            try:
                html = _fetch(url, client, delay=2.5)
            except Exception as e:
                print(f"  ✗ Page {page} failed: {e}")
                break
            data = _next_data(html)
            listings = _parse_next_data_listings(data, listing_type)
            if not listings:
                listings = _parse_html_listings(html, listing_type)
            new = [l for l in listings if l["id"] not in seen_ids]
            for lst in new:
                seen_ids.add(lst["id"])
            all_listings.extend(new)
            print(f"  Page {page}: {len(new)} new listings")

        # Fetch detail pages
        print(f"\n  Fetching {len(all_listings)} detail pages…")
        for i, listing in enumerate(all_listings):
            if not listing.get("url"):
                continue
            print(
                f"  [{i+1}/{len(all_listings)}] "
                f"{listing.get('address') or listing['id']}"
            )
            extra = _enrich_from_detail(listing["url"], client)
            for k, v in extra.items():
                if v and not listing.get(k):
                    listing[k] = v
                elif k in ("has_ongoing_offer", "extension_required"):
                    listing[k] = v  # always override these flags

    return all_listings
