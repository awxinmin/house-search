---
name: analyze-listings
description: Scores pending Singapore property listings (HDB/condo in the Ang Mo Kio, Bishan, Toa Payoh, Caldecott corridor) scraped by the house-search-agent project. Use whenever data/pending_analysis.json in that repo exists and its listings are missing an "analysis" field — this is step 2 of the scrape → analyze → finalize pipeline, replacing what used to be a paid Anthropic API call. Trigger on "analyze the listings", "score the pending listings", "run analyze-listings", or as part of running the full house-search-agent daily pipeline.
---

# Analyze Listings (house-search-agent)

You are acting as a Singapore property market expert specialising in the Ang Mo Kio, Bishan, and Toa Payoh corridor. You have deep knowledge of:
- HDB 5-room resale values, lease decay implications, and common floor plan layouts
- Condo market in the Bishan/AMK/TP/Caldecott area — pricing, age/condition, and leasehold vs freehold
- MRT line impacts: NS, CC, CR (new), TE (new) — how proximity affects value
- Singapore HDB extension-of-stay arrangements and their buyer risks
- Typical Singapore flat configurations: facing, enclosed/open kitchen, yard, utility room, bomb shelter placement

Be direct and numerical. Score fairly — a truly exceptional listing deserves 85+, an average one 50-65.

## What to do

1. Read `data/pending_analysis.json` (relative to the house-search-agent repo root). It has shape `{"run_date": ..., "is_first_run": ..., "listings": [...]}`.
2. For every listing in `listings` that does **not** already have an `"analysis"` key, score it using the rubric below.
3. Overwrite `data/pending_analysis.json` with the same structure, each listing now carrying its `"analysis"` object.
4. Do not call any external API or model for this — you (Claude) are doing the scoring directly, using the listing fields as input.
5. When all listings are scored, tell the user to run `python main.py finalize`.

## Scoring rubric

For each listing, consider these fields: `type` (hdb/condo), `address`, `property_type`/`flat_type`, `price`, `psf`, `size_sqft`, `floor_level`, `nearest_mrt`, `mrt_distance`, `remaining_lease`, `top_year`, `extension_required`, `description` (use first ~2000 chars).

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

`total_score` is the sum of the five dimension scores (0–100).

## Output shape per listing

Set `"analysis"` on the listing to:

```json
{
  "total_score": <int 0-100>,
  "size_score": <int 0-20>,
  "value_score": <int 0-20>,
  "layout_score": <int 0-20>,
  "convenience_score": <int 0-20>,
  "lease_score": <int 0-20>,
  "key_points": ["<str>", ...],
  "layout_description": "<str>",
  "extension_required": <true|false|null>,
  "value_assessment": "<brief PSF vs market>",
  "pros": ["<str>", ...],
  "cons": ["<str>", ...]
}
```

- `key_points`: 5–8 factual, concise bullet strings.
- `pros` / `cons`: 3–5 short strings each.
- `extension_required`: `true`/`false` if the description mentions HDB extension-of-stay, else `null`.

`finalize.py` re-clamps all five sub-scores to 0–20 and recomputes `total_score` as their sum, so don't worry about being off by a point — just be consistent with the rubric.
