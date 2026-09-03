"""Generate HTML email with property listings in scored tables."""

from config import HDB_ESTATE_MAP

_CSS = """
<style>
body{font-family:Arial,Helvetica,sans-serif;font-size:13px;color:#333;max-width:1400px;margin:0 auto;padding:12px}
h1{color:#1a73e8;margin-bottom:4px}
h2{color:#0d47a1;border-bottom:3px solid #0d47a1;padding-bottom:6px;margin-top:28px}
h3{color:#1565c0;margin-top:18px;margin-bottom:6px}
table{border-collapse:collapse;width:100%;margin-bottom:20px;font-size:12px}
th{background:#1a73e8;color:#fff;padding:7px 9px;text-align:left;white-space:nowrap}
td{padding:6px 9px;border-bottom:1px solid #e0e0e0;vertical-align:top}
tr:nth-child(even) td{background:#f7f9ff}
tr:hover td{background:#e8f0fe}
.sh{color:#2e7d32;font-weight:700}
.sm{color:#f57f17;font-weight:700}
.sl{color:#c62828;font-weight:700}
.sub{color:#666;font-size:11px}
a{color:#1565c0;text-decoration:none}
a:hover{text-decoration:underline}
.ext{background:#fff3e0;color:#e65100;border-radius:3px;padding:1px 5px;font-size:11px;white-space:nowrap}
.pro{background:#e8f5e9;color:#2e7d32;border-radius:3px;padding:1px 5px;font-size:11px;margin:1px;display:inline-block}
.con{background:#ffebee;color:#c62828;border-radius:3px;padding:1px 5px;font-size:11px;margin:1px;display:inline-block}
ul{margin:2px 0;padding-left:15px}
li{margin:1px 0}
.badge{display:inline-block;border-radius:3px;padding:2px 6px;font-size:11px;font-weight:700}
</style>
"""

_TH = """<tr>
<th>#</th><th>Score</th><th>Address / Link</th><th>Type</th>
<th>Price (S$)</th><th>PSF</th><th>Size sqft</th><th>Level</th>
<th>Lease / TOP</th><th>Nearest MRT</th><th>Listed</th>
<th>Key Points &amp; Tags</th>
</tr>"""


def _sc(score: int) -> str:
    if score >= 75:
        return "sh"
    if score >= 55:
        return "sm"
    return "sl"


def _price(v) -> str:
    try:
        return f"{int(v):,}"
    except Exception:
        return str(v) if v else "N/A"


def _psf(v) -> str:
    try:
        return f"{float(v):,.0f}"
    except Exception:
        return str(v) if v else "N/A"


def _row(rank: int, lst: dict) -> str:
    a = lst.get("analysis", {})
    score = a.get("total_score", 0)
    breakdown = (
        f"Sz:{a.get('size_score',0)} "
        f"Val:{a.get('value_score',0)} "
        f"Ly:{a.get('layout_score',0)} "
        f"Cv:{a.get('convenience_score',0)} "
        f"Ls:{a.get('lease_score',0)}"
    )
    ext_flag = " <span class='ext'>⚠ Ext.Stay</span>" if lst.get("extension_required") or a.get("extension_required") else ""

    kp = a.get("key_points", [])
    kp_html = ""
    if kp:
        kp_html = "<ul>" + "".join(f"<li>{p}</li>" for p in kp[:6]) + "</ul>"

    pros = "".join(f"<span class='pro'>✓ {p}</span>" for p in a.get("pros", [])[:3])
    cons = "".join(f"<span class='con'>✗ {c}</span>" for c in a.get("cons", [])[:3])
    tags = f"<div style='margin-top:3px'>{pros}{cons}</div>" if (pros or cons) else ""

    val_note = a.get("value_assessment", "")
    val_html = f"<div class='sub' style='margin-top:2px'>{val_note}</div>" if val_note else ""

    mrt_dist = lst.get("mrt_distance", "")
    mrt = lst.get("nearest_mrt", "") or "—"
    if mrt_dist:
        mrt += f"<br><span class='sub'>{mrt_dist}</span>"

    return f"""<tr>
<td>{rank}</td>
<td>
  <span class='{_sc(score)} badge'>{score}/100</span><br>
  <span class='sub'>{breakdown}</span>
</td>
<td>
  <a href='{lst.get("url","")}'>{lst.get("address") or lst.get("title") or lst["id"]}</a>{ext_flag}
</td>
<td>{lst.get("property_type","") or "—"}</td>
<td>{_price(lst.get("price"))}</td>
<td>{_psf(lst.get("psf"))}</td>
<td>{lst.get("size_sqft","") or "—"}</td>
<td>{lst.get("floor_level","") or "—"}</td>
<td>{lst.get("remaining_lease","") or lst.get("top_year","") or "—"}</td>
<td>{mrt}</td>
<td><span class='sub'>{lst.get("listed_date","") or "—"}</span></td>
<td>{kp_html}{tags}{val_html}</td>
</tr>"""


def _section(title: str, listings: list[dict]) -> str:
    if not listings:
        return ""
    sorted_lst = sorted(
        listings, key=lambda x: x.get("analysis", {}).get("total_score", 0), reverse=True
    )
    rows = "".join(_row(i + 1, l) for i, l in enumerate(sorted_lst))
    return f"<h3>{title} <span class='sub'>({len(listings)} listings)</span></h3><table>{_TH}{rows}</table>"


def format_email(
    hdb_listings: list[dict], condo_listings: list[dict], run_date: str
) -> tuple[str, str]:
    total = len(hdb_listings) + len(condo_listings)
    subject = f"PropertyGuru Daily — {total} new listings ({run_date})"

    if total == 0:
        body = f"""\
<html><head>{_CSS}</head><body>
<h1>PropertyGuru Daily — {run_date}</h1>
<p>No new listings today matching your criteria.</p>
<ul>
  <li>HDB 5-room: Ang Mo Kio · Bishan · Toa Payoh — ≥1,000 sqft, ≤750m to MRT</li>
  <li>Condo: Bishan/AMK/TP/Caldecott/Lentor MRT corridor — ≤S$2.7M, ≥1,000 sqft, TOP ≥2000, 3–4 BR</li>
</ul>
</body></html>"""
        return subject, body

    parts = [f"<html><head>{_CSS}</head><body>",
             f"<h1>PropertyGuru Daily — {run_date}</h1>",
             f"<p><strong>{len(hdb_listings)} HDB</strong> · <strong>{len(condo_listings)} Condo</strong> new listings</p>"]

    # ── HDB ───────────────────────────────────────────────────────────────────
    if hdb_listings:
        parts.append("<h2>HDB Listings</h2>")
        # Group by estate
        by_estate: dict[str, list] = {}
        for lst in hdb_listings:
            code = lst.get("estate", "")
            name = HDB_ESTATE_MAP.get(code, code or "Other")
            by_estate.setdefault(name, []).append(lst)

        for estate in ("Ang Mo Kio", "Bishan", "Toa Payoh"):
            if estate in by_estate:
                parts.append(_section(estate, by_estate.pop(estate)))
        for name, lsts in by_estate.items():
            parts.append(_section(name, lsts))

    # ── Condo ─────────────────────────────────────────────────────────────────
    if condo_listings:
        parts.append("<h2>Condo Listings</h2>")
        by_mrt: dict[str, list] = {}
        for lst in condo_listings:
            mrt = lst.get("nearest_mrt", "") or "Other"
            by_mrt.setdefault(mrt, []).append(lst)

        mrt_order = [
            "Bishan MRT", "Ang Mo Kio MRT", "Marymount MRT",
            "Caldecott MRT", "Bright Hill MRT", "Lentor MRT",
            "Mayflower MRT", "Yio Chu Kang MRT",
        ]
        shown: set = set()
        for mrt in mrt_order:
            for key in list(by_mrt):
                if mrt.lower() in key.lower() and key not in shown:
                    parts.append(_section(f"Near {key}", by_mrt[key]))
                    shown.add(key)
        for key, lsts in by_mrt.items():
            if key not in shown:
                parts.append(_section(f"Near {key}", lsts))

    parts.append("</body></html>")
    return subject, "".join(parts)
