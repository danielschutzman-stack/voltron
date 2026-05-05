"""
gtmbuddy_matcher.py — GTM Buddy asset lookup helper.

Usage:
    from gtmbuddy_matcher import get_gtmbuddy_assets, format_for_subagent, build_asset_url

    assets = get_gtmbuddy_assets(
        competitor="Tableau",
        vertical="Financial Services",
        use_case="embedded",          # "embedded" | "spotter" | "tse" | "tsa" | None
        include_case_studies=True,
        include_playbook=True,
        include_bva=False,
    )
    # Returns: {"competitive": [...], "vertical": [...], "case_studies": [...], ...}
    # Each item: {"id": str, "title": str, "url": str, "category": str}
"""

import json, re
from pathlib import Path
from typing import Optional

GTMBUDDY_BASE = "https://thoughtspot.gtmbuddy.io/viewer"
_MAP_PATH = Path("/sandbox/gtmbuddy_fallback_map.json")
_cache = None


def _load() -> dict:
    global _cache
    if _cache is None:
        _cache = json.loads(_MAP_PATH.read_text(encoding="utf-8"))
    return _cache


def clean_title(title: str) -> str:
    """Strip HTML tags from GTM Buddy asset titles."""
    return re.sub(r'<[^>]+>', '', title).strip()


def build_asset_url(asset_id: str) -> str:
    """Construct a clickable GTM Buddy viewer URL from an asset ID."""
    return f"{GTMBUDDY_BASE}/{asset_id}"


# ── Vertical keyword → GTM Buddy key prefix mapping ──────────────────────────
_VERTICAL_MAP = {
    "financial":     "FinServ",
    "finserv":       "FinServ",
    "banking":       "FinServ",
    "insurance":     "Insurance",
    "healthcare":    "Healthcare",
    "health":        "Healthcare",
    "lifesciences":  "LifeSci",
    "life sciences": "LifeSci",
    "pharma":        "LifeSci",
    "retail":        "Retail",
    "cpg":           "Retail",
    "telecom":       "Telecom",
    "telco":         "Telecom",
    "travel":        "Travel",
    "hospitality":   "Travel",
    "cruise":        "Travel",
    "supply chain":  "SupplyChain",
    "supplychain":   "SupplyChain",
    "logistics":     "SupplyChain",
    "distribution":  "SupplyChain",
    "manufacturing": "Manufacturing",
    "technology":    "Technology",
    "tech":          "Technology",
    "software":      "Technology",
    "saas":          "Technology",
    "media":         "Media",
    "utilities":     "Utilities",
    "professional":  "ProfServices",
}

# ── Competitor keyword → GTM Buddy key ───────────────────────────────────────
_COMPETITOR_MAP = {
    "tableau":  "Tableau competitive",
    "looker":   "Looker competitive",
    "power bi": "Power BI competitive",
    "powerbi":  "Power BI competitive",
    "qlik":     "Qlik competitive",
    "sisense":  "Sisense competitive",
}

# ── "Why chosen" rationale by category ───────────────────────────────────────
_RATIONALE_MAP = {
    "Tableau competitive":   "Directly addresses Tableau displacement — positioning, battle card, and win stories.",
    "Looker competitive":    "Covers Looker displacement angle — key differentiators and competitive win proof.",
    "Power BI competitive":  "Addresses Power BI displacement — TS speed, Spotter AI, and self-service story.",
    "Qlik competitive":      "Covers Qlik displacement — modern UI, cloud-native, and Snowflake-native story.",
    "Sisense competitive":   "Addresses Sisense displacement — embedded analytics and developer experience story.",
    "Case Studies":          "Proof point from a comparable customer — use to anchor credibility in outreach.",
    "AI Analyst Spotter":    "Spotter AI analyst use case — directly relevant to AI-powered analytics story.",
    "Embedded - TSE":        "Embedded analytics use case — relevant for product teams building data experiences.",
    "TSE - Overview":        "ThoughtSpot Everywhere overview — relevant for embedded/product analytics motion.",
    "TSE - Enterprise":      "Enterprise TSE motion — relevant for large-scale embedded analytics deployments.",
    "TSA - Overview":        "ThoughtSpot Analytics overview — core self-service BI positioning.",
    "TSA - Talk Track":      "TSA talk track and message house — use for discovery and demo prep.",
    "Cold Email - Best Practices": "Best practices for cold outreach — apply to all email copy in this PG.",
    "LinkedIn outreach":     "LinkedIn and messaging house reference — tone and positioning for social outreach.",
}


def _items(key: str) -> list:
    m = _load()
    return [
        {
            "id":       i["id"],
            "title":    clean_title(i["title"]),
            "url":      build_asset_url(i["id"]),
            "category": key,
            "source":   "GTM Buddy",
            "rationale": _RATIONALE_MAP.get(key, "Recommended internal asset for this account."),
        }
        for i in m.get(key, [])
    ]


def get_gtmbuddy_assets(
    competitor: Optional[str] = None,
    vertical: Optional[str] = None,
    use_case: Optional[str] = None,   # "embedded" | "spotter" | "tse" | "tsa"
    include_case_studies: bool = True,
    include_playbook: bool = False,
    include_bva: bool = False,
    include_demo: bool = False,
    max_case_studies: int = 4,
) -> dict:
    """
    Return a structured dict of relevant GTM Buddy assets.
    All matching is case-insensitive and keyword-based.
    Each item includes: id, title, url, category, source, rationale.
    """
    result = {}
    m = _load()

    # ── Competitive ──────────────────────────────────────────────────────────
    if competitor:
        c_lower = competitor.lower().strip()
        for kw, key in _COMPETITOR_MAP.items():
            if kw in c_lower:
                items = _items(key)
                if items:
                    result["competitive"] = items
                break

    # ── Vertical ─────────────────────────────────────────────────────────────
    if vertical:
        v_lower = vertical.lower().strip()
        prefix = None
        for kw, pfx in _VERTICAL_MAP.items():
            if kw in v_lower:
                prefix = pfx
                break

        if prefix:
            vert_key = next((k for k in m if prefix in k and "vertical" in k.lower()), None)
            if vert_key:
                result["vertical"] = _items(vert_key)

            if include_playbook:
                pb_key = next((k for k in m if prefix in k and "playbook" in k.lower()), None)
                if pb_key:
                    result["playbook"] = _items(pb_key)

            if include_bva:
                bva_key = next((k for k in m if prefix in k and "bva" in k.lower()), None)
                if not bva_key:
                    bva_key = "BVA business value calculator"
                result["bva"] = _items(bva_key)

            if include_demo:
                demo_key = next((k for k in m if prefix in k and "demo" in k.lower()), None)
                if demo_key:
                    result["demo"] = _items(demo_key)

    # ── Use Case ─────────────────────────────────────────────────────────────
    if use_case:
        uc = use_case.lower()
        if "spotter" in uc or "ai" in uc:
            result["use_case"] = _items("AI Analyst Spotter")
        elif "embedded" in uc:
            result["use_case"] = _items("Embedded - TSE")
        elif "tse" in uc:
            result["use_case"] = _items("TSE - Overview") + _items("TSE - Enterprise")
        elif "tsa" in uc:
            result["use_case"] = _items("TSA - Overview") + _items("TSA - Talk Track")

    # ── Case Studies (capped, authoritative source) ───────────────────────────
    if include_case_studies:
        result["case_studies"] = _items("Case Studies")[:max_case_studies]

    # ── Talk Tracks (always included for outreach use) ────────────────────────
    result["talk_tracks"] = (
        _items("Cold Email - Best Practices") +
        _items("LinkedIn outreach")
    )

    return result


def get_recommended_case_studies(
    vertical: Optional[str] = None,
    competitor: Optional[str] = None,
    max_results: int = 3,
) -> list:
    """
    Return top recommended case study assets for a given account context.
    Prioritises vertical-matched case studies, then general pool.
    Each item includes full card data: title, url, source, rationale, key_metric placeholder.
    """
    m = _load()
    results = []

    # Try vertical-specific pool first (playbook items often contain case studies)
    if vertical:
        v_lower = vertical.lower().strip()
        prefix = next((pfx for kw, pfx in _VERTICAL_MAP.items() if kw in v_lower), None)
        if prefix:
            pb_key = next((k for k in m if prefix in k and "playbook" in k.lower()), None)
            if pb_key:
                results.extend(_items(pb_key))

    # Fill from general case studies pool
    general = _items("Case Studies")
    seen_ids = {r["id"] for r in results}
    for item in general:
        if item["id"] not in seen_ids:
            results.append(item)
        if len(results) >= max_results:
            break

    return results[:max_results]


def format_for_subagent(assets: dict) -> str:
    """
    Render asset dict as a clean text block for injection into subagent prompts.
    Includes title, URL, and rationale for each asset.
    """
    lines = ["## GTM Buddy Internal Assets\n",
             "Source: GTM Buddy (https://thoughtspot.gtmbuddy.io)\n"]
    for category, items in assets.items():
        if not items:
            continue
        label = category.replace("_", " ").title()
        lines.append(f"### {label}")
        for item in items:
            lines.append(f"- {item['title']}")
            lines.append(f"  URL: {item['url']}")
            lines.append(f"  Why: {item['rationale']}")
        lines.append("")
    return "\n".join(lines)


def render_case_study_cards_html(assets: list, account_name: str = "") -> str:
    """
    Render GTM Buddy assets as full case study cards for injection into
    pg_report_builder HTML output (case_studies tab) and one-pager.

    Each card matches existing case study card format:
      - Title (clickable link to GTM Buddy viewer)
      - 'Why chosen for [Account]' rationale
      - Source badge: GTM Buddy
    """
    if not assets:
        return ""

    account_label = f" for {account_name}" if account_name else ""
    cards_html = []

    for item in assets:
        title   = item.get("title", "Untitled Asset")
        url     = item.get("url", "#")
        why     = item.get("rationale", "Recommended internal asset.")
        cat     = item.get("category", "")

        # Badge color by category type
        if "competitive" in cat.lower():
            badge_color = "#dc2626"
            badge_label = "Competitive"
        elif "case stud" in cat.lower():
            badge_color = "#16a34a"
            badge_label = "Case Study"
        elif "spotter" in cat.lower() or "ai analyst" in cat.lower():
            badge_color = "#7c3aed"
            badge_label = "AI / Spotter"
        elif "embedded" in cat.lower() or "tse" in cat.lower():
            badge_color = "#0369a1"
            badge_label = "Embedded Analytics"
        elif "vertical" in cat.lower() or "playbook" in cat.lower():
            badge_color = "#d97706"
            badge_label = "Vertical"
        else:
            badge_color = "#475569"
            badge_label = "Internal Asset"

        card = f"""
<div style="border:1px solid #e2e8f0;border-radius:10px;padding:18px 20px;
            margin-bottom:14px;background:#ffffff;">
  <div style="display:flex;align-items:flex-start;justify-content:space-between;
              margin-bottom:10px;">
    <a href="{url}" target="_blank"
       style="font-size:14px;font-weight:600;color:#1D2D50;text-decoration:none;
              line-height:1.4;flex:1;margin-right:12px;">
      {title}
    </a>
    <span style="background:{badge_color};color:white;font-size:10px;
                 font-weight:700;padding:3px 8px;border-radius:12px;
                 white-space:nowrap;flex-shrink:0;">
      {badge_label}
    </span>
  </div>
  <div style="font-size:12px;color:#64748b;margin-bottom:8px;font-style:italic;">
    Why chosen{account_label}: {why}
  </div>
  <div style="font-size:11px;color:#94a3b8;display:flex;align-items:center;gap:6px;">
    <span style="background:#f1f5f9;border:1px solid #e2e8f0;border-radius:4px;
                 padding:2px 7px;font-weight:600;color:#475569;">
      📚 GTM Buddy
    </span>
    <a href="{url}" target="_blank"
       style="color:#3b82f6;text-decoration:none;font-size:11px;">
      Open in GTM Buddy →
    </a>
  </div>
</div>""".strip()

        cards_html.append(card)

    return "\n".join(cards_html)
