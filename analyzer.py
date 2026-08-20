"""Claude-powered Singapore property analysis agent."""

import json
import os
import re

from anthropic import Anthropic

_client = Anthropic()

_SYSTEM = """You are a Singapore property market expert specialising in the Ang Mo Kio, Bishan, and Toa Payoh corridor.

You have deep knowledge of:
- HDB 5-room resale values, lease decay implications, and common floor plan layouts
- Condo market in the Bishan/AMK/TP/Caldecott area — pricing, age/condition, and leasehold vs freehold
- MRT line impacts: NS, CC, CR (new), TE (new) — how proximity affects value
- Singapore HDB extension-of-stay arrangements and their buyer risks
- Typical Singapore flat configurations: facing, enclosed/open kitchen, yard, utility room, bomb shelter placement

Be direct and numerical. Score fairly — a truly exceptional listing deserves 85+, an average one 50-65."""

_PROMPT = """\
Analyze this Singapore property listing and return a JSON score card.

**Property**
- Type: {ptype}
- Address: {address}
- Flat/Unit type: {flat_type}
- Asking price: S${price:,}
- Asking PSF: S${psf:.0f}/sqft
- Size: {size} sqft
- Floor level: {floor}
- Nearest MRT: {mrt} ({mrt_dist})
- Tenure / Remaining lease: {lease}
- TOP year (condo): {top_year}
- Extension of stay mentioned: {ext}

**Description (first 2000 chars)**
{desc}

---
Score each dimension 0–20 (total 0–100):

1. **size_score** — For 5-rm HDB / 3BR condo, baseline 1000sqft = 10.
   1100 = 13, 1200 = 16, 1300 = 18, 1400+ = 20. Penalise odd/wasted sqft.

2. **value_score** — Compare PSF to local market:
   HDB AMK/TP market ≈ S$450–600/sqft; Bishan ≈ S$550–700/sqft.
   Condo in this corridor ≈ S$1400–2200/sqft.
   Below lower bound = 18–20; at upper bound = 8–10; above = 4–7.

3. **layout_score** — Based on description: rectangular rooms, enclosed kitchen, yard/utility room,
   good facing (N/S preferred), balcony. Penalise irregular layouts, bay windows eating into room size,
   long corridors, poor ventilation. Score 0–20; no description = 10 (neutral).

4. **convenience_score** — MRT walking distance: ≤300m = 19–20, 300–500m = 15–18,
   500–750m = 10–14. Add +1 for Bishan (premium estate), neutral for AMK, +0 for TP.
   Cap at 20.

5. **lease_score** — HDB: remaining years 90+ = 20, 80–89 = 17, 70–79 = 14, 60–69 = 10,
   50–59 = 6, <50 = 2. (HDB filter is TOP ≥1990, so expect 60–85 yrs remaining.)
   Condo: TOP 2022+ = 20, 2018–2021 = 17, 2012–2017 = 14, 2005–2011 = 10, 2000–2004 = 7.
   Unknown = 10.

Return **only** valid JSON (no markdown fences):
{{
  "total_score": <int>,
  "size_score": <int>,
  "value_score": <int>,
  "layout_score": <int>,
  "convenience_score": <int>,
  "lease_score": <int>,
  "key_points": ["<str>", ...],
  "layout_description": "<str>",
  "extension_required": <true|false|null>,
  "value_assessment": "<brief PSF vs market>",
  "pros": ["<str>", ...],
  "cons": ["<str>", ...]
}}
key_points: 5–8 bullet strings (factual, concise).
pros / cons: 3–5 short strings each.
"""

_DEFAULT = {
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


def analyze_listing(listing: dict) -> dict:
    try:
        prompt = _PROMPT.format(
            ptype="HDB" if listing.get("type") == "hdb" else "Condo",
            address=listing.get("address") or "Unknown",
            flat_type=listing.get("property_type") or listing.get("flat_type") or "5-room",
            price=int(listing.get("price") or 0),
            psf=float(listing.get("psf") or 0),
            size=listing.get("size_sqft") or "Unknown",
            floor=listing.get("floor_level") or "Unknown",
            mrt=listing.get("nearest_mrt") or "Unknown",
            mrt_dist=listing.get("mrt_distance") or "Unknown",
            lease=listing.get("remaining_lease") or "Unknown",
            top_year=listing.get("top_year") or "N/A",
            ext="Yes" if listing.get("extension_required") else "No/Unknown",
            desc=(listing.get("description") or "")[:2000],
        )
        resp = _client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=1024,
            system=_SYSTEM,
            messages=[{"role": "user", "content": prompt}],
        )
        text = resp.content[0].text.strip()
        m = re.search(r"\{.*\}", text, re.DOTALL)
        if m:
            result = json.loads(m.group())
            # Clamp scores
            for key in ("size_score", "value_score", "layout_score", "convenience_score", "lease_score"):
                result[key] = max(0, min(20, int(result.get(key, 0))))
            result["total_score"] = sum(
                result.get(k, 0)
                for k in ("size_score", "value_score", "layout_score", "convenience_score", "lease_score")
            )
            return result
    except Exception as e:
        print(f"    ⚠ analysis error: {e}")
    return dict(_DEFAULT)
