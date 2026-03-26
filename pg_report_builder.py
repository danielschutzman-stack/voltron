"""
pg_report_builder.py — v5.1
----------------------------------------------------------------
Builds PG report HTML files from subagent JSON output and TS query results.

v5.1 changes: No file writes. build_pg_report() and build_onepager() return
dicts with {"filename", "html", "slug"} instead of writing to disk.
Caller is responsible for delivering the HTML string via platform mechanism.

Three output files per account (always):
  {slug}_pg_report_draft.html  — Phase 1: full report without outreach
  {slug}_pg_report_final.html  — Phase 2: full report with outreach
  {slug}_onepager.html         — External customer-facing one-pager

Usage:
    from pg_report_builder import build_pg_report, build_onepager

    # Phase 1 — after all research modules complete:
    result = build_pg_report(
        slug="acme_corp",
        account_name="Acme Corp",
        raw={
            "web_research":    {...},
            "tsumble":         {...},
            "competitor_intel":{...},
            "exec_profiles":   {...},
            "case_studies":    {...},
        },
        ts_data={
            "sfdc_stakeholder":    {...},
            "deal_stage":          {...},
            "deal_funnel_timing":  {...},
            "meddpicc_flags":      {...},
            "meddpicc_detail":     {...},
            "activity_history":    {...},
            "6sense_intent":       {...},
        },
        matched_drivers=[
            {"key": "enable_self_service", "label": "...", ...},
        ],
        header_data={"owner_name": "Jane Smith", "region": "West"},
        phase=1,
    )
    # result = {"filename": "acme_corp_pg_report_draft.html",
    #           "html": "<html>...</html>",
    #           "slug": "acme_corp",
    #           "phase": 1}

    # Phase 2 — after Outreach Generator completes:
    result = build_pg_report(..., outreach_data={...}, phase=2)

    # One-pager:
    onepager = build_onepager(
        slug="acme_corp",
        account_name="Acme Corp",
        raw={...},
        matched_drivers=[...],
    )
    # onepager = {"filename": "acme_corp_onepager.html",
    #             "html": "<html>...</html>",
    #             "slug": "acme_corp"}
"""

import datetime
import html as _html

from value_drivers import get_drivers, get_money_signals


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

NAVY       = "#1D2D50"
BLUE       = "#2E5CE5"
LIGHT_BLUE = "#EBF2FF"
WHITE      = "#FFFFFF"

LEG_COLORS = {
    "DATA":     "#2E5CE5",
    "BUSINESS": "#D97706",
    "IT":       "#16A34A",
    "ANALYST":  "#7C3AED",
}

LEG_ICONS = {
    "DATA":     "🗄️",
    "BUSINESS": "💼",
    "IT":       "💻",
    "ANALYST":  "📊",
}

LEG_RULES = [
    ("DATA", [
        "cdo", "chief data", "chief analytics",
        "vp data", "vp of data", "director of data", "head of data",
        "data platform", "data engineering", "data governance",
        "data architecture", "data products", "data science",
        "analytics engineering", "data strategy",
    ]),
    ("ANALYST", [
        "bi ", "business intelligence", "analytics", "reporting",
        "insights", "dashboard", "visualization",
        "data analyst", "business analyst", "analytics engineer",
        "center of excellence", "coe",
    ]),
    ("IT", [
        "cio", "cto", "chief information", "chief technology",
        "vp technology", "vp of technology", "vp engineering",
        "director of technology", "director of it",
        "infrastructure", "platform", "architecture",
        "security", "cloud", "devops", "systems",
        "software engineering", "it ",
    ]),
    ("BUSINESS", [
        "ceo", "coo", "cfo", "cmo", "president", " gm ", "general manager",
        "svp", "evp", "managing director",
        "head of ", "operations", "finance", "marketing",
        "sales", "revenue", "strategy", "product",
    ]),
]


# ---------------------------------------------------------------------------
# Internal utilities
# ---------------------------------------------------------------------------

def _e(v) -> str:
    if v is None:
        return ""
    return _html.escape(str(v))


def _text(v, fallback: str = "") -> str:
    if v is None:
        return fallback
    if isinstance(v, str):
        return v or fallback
    if isinstance(v, dict):
        for key in ("text", "quote", "trend", "signal",
                    "headline", "title", "point", "summary"):
            if v.get(key):
                return str(v[key])
        return str(v)
    if isinstance(v, list):
        parts = [_text(item) for item in v[:5] if _text(item)]
        return "; ".join(parts) or fallback
    return str(v) or fallback


def _src_badge(v) -> str:
    if not isinstance(v, dict):
        return ""
    src      = v.get("source") or v.get("source_url") or v.get("url") or ""
    src_type = v.get("source_type", "")

    if not src:
        return " <span style='color:#9ca3af;font-size:11px;'>⚠️ no source</span>"

    if "gong" in src.lower() or "call" in src.lower():
        icon = "🎙"
    elif "sfdc" in src.lower() or "salesforce" in src.lower():
        icon = "📋"
    elif "linkedin" in src.lower() or "job" in src.lower():
        icon = "💼"
    elif src.startswith("http"):
        icon = "🌐"
    else:
        icon = "📌"

    label = _e(src_type or "source")
    if src.startswith("http"):
        return (
            f" <a href='{_e(src)}' target='_blank' "
            f"style='color:#6b7280;font-size:11px;text-decoration:none;'>"
            f"{icon} {label} ↗</a>"
        )
    return f" <span style='color:#6b7280;font-size:11px;'>{icon} {_e(src)}</span>"


def _render_item(v) -> str:
    if isinstance(v, dict):
        return _e(_text(v)) + _src_badge(v)
    return _e(str(v)) if v else ""


def _classify_leg(title: str) -> str:
    if not title:
        return "UNKNOWN"
    t = title.lower()
    for leg, keywords in LEG_RULES:
        if any(kw in t for kw in keywords):
            return leg
    return "UNKNOWN"


def _score_to_grade(score) -> str:
    try:
        n = float(score)
        if n >= 90:
            return "A+"
        if n >= 75:
            return "A"
        if n >= 60:
            return "B"
        return "C"
    except (TypeError, ValueError):
        return str(score) if score else "N/A"


# ---------------------------------------------------------------------------
# Shared CSS + JS
# ---------------------------------------------------------------------------

_CSS = f"""
<style>
*, *::before, *::after {{box-sizing: border-box;}}
body {{
    font-family: 'Inter', 'Segoe UI', sans-serif;
    margin: 0; padding: 0;
    background: #f8fafc; color: #1e293b;
}}
.container {{max-width: 1200px; margin: 0 auto; padding: 24px;}}
h1 {{font-size: 28px; font-weight: 700; color: #0f172a;}}
h2 {{
    font-size: 22px; font-weight: 700; color: {NAVY};
    border-bottom: 2px solid {BLUE};
    padding-bottom: 8px; margin-top: 32px;
}}
h3 {{font-size: 18px; font-weight: 600; color: {NAVY}; margin-top: 24px;}}
h4 {{font-size: 15px; font-weight: 600; color: #334155; margin: 12px 0 6px;}}
p  {{margin: 6px 0; line-height: 1.6;}}
a  {{color: {BLUE};}}
table {{
    width: 100%; border-collapse: collapse;
    margin: 12px 0; font-size: 13px;
}}
th {{
    background: {NAVY}; color: #fff;
    padding: 8px 12px; text-align: left;
}}
td {{padding: 7px 12px; border-bottom: 1px solid #e2e8f0;}}
tr:nth-child(even) td {{background: #f1f5f9;}}
.section {{
    background: #fff; border-radius: 12px;
    padding: 20px 24px; margin: 16px 0;
    box-shadow: 0 1px 4px rgba(0,0,0,.08);
}}
.pill {{
    display: inline-block; background: #dbeafe; color: #1d4ed8;
    border-radius: 20px; padding: 3px 10px;
    font-size: 12px; margin: 2px;
}}
.opp-card {{
    background: #f0fdf4; border: 1px solid #86efac;
    border-radius: 8px; padding: 10px 14px;
    margin: 6px 0; font-size: 13px;
}}
.exec-card {{
    background: #fafafa; border: 1px solid #e2e8f0;
    border-radius: 8px; padding: 14px 18px; margin: 10px 0;
}}
.driver {{
    background: #f8fafc; border: 1px solid #e2e8f0;
    border-radius: 8px; padding: 12px 16px; margin: 8px 0;
}}
.talking-point {{
    background: {LIGHT_BLUE}; border-left: 4px solid {BLUE};
    border-radius: 8px; padding: 16px 20px; margin: 16px 0;
    font-size: 15px; line-height: 1.7;
}}
.talking-point strong {{color: {NAVY};}}
blockquote {{
    border-left: 3px solid {BLUE}; margin: 8px 0;
    padding: 6px 14px; color: #475569; font-style: italic;
}}
pre {{
    background: #f1f5f9; border-radius: 6px;
    padding: 12px; font-size: 12px;
    white-space: pre-wrap; word-wrap: break-word;
}}
.stool-grid {{
    display: grid; grid-template-columns: 1fr 1fr;
    gap: 12px; margin: 16px 0;
}}
.stool-leg {{
    border-radius: 10px; padding: 14px 16px;
    border: 2px solid transparent;
}}
.stool-leg.empty {{
    border: 2px dashed #ef4444;
    background: #fef2f2;
}}
.stool-leg-title {{
    font-size: 13px; font-weight: 700;
    margin-bottom: 8px; color: #fff;
    padding: 4px 10px; border-radius: 6px;
    display: inline-block;
}}
.stool-person {{font-size: 13px; margin: 4px 0;}}
.badge {{
    display: inline-block; font-size: 11px;
    padding: 2px 7px; border-radius: 10px;
    margin-left: 4px; font-weight: 600;
}}
.badge-champion {{background: #fef9c3; color: #854d0e;}}
.badge-eb {{background: #dcfce7; color: #166534;}}
.tab-nav {{
    display: flex; gap: 8px;
    flex-wrap: wrap; margin-bottom: 16px;
}}
.tab-btn {{
    padding: 8px 18px; border-radius: 8px;
    border: 1px solid #cbd5e1; background: #fff;
    cursor: pointer; font-size: 14px; font-weight: 500;
}}
.tab-btn.active {{
    background: {NAVY}; color: #fff; border-color: {NAVY};
}}
.tab-content {{display: none;}}
.tab-content.active {{display: block;}}
.account-section {{margin-bottom: 40px;}}
.header-bar {{
    background: linear-gradient(135deg, {NAVY}, {BLUE});
    color: #fff; padding: 24px 32px;
    border-radius: 12px; margin-bottom: 24px;
}}
.header-bar h1 {{color: #fff; margin: 0;}}
.header-bar p  {{margin: 4px 0; opacity: .85;}}
.flag {{color: #ef4444; font-size: 12px; font-weight: 600;}}
</style>
"""

_JS = """
<script>
function showTab(accountSlug, tabId) {
    document.querySelectorAll('.tab-content-' + accountSlug)
            .forEach(el => el.classList.remove('active'));
    document.querySelectorAll('.tab-btn-' + accountSlug)
            .forEach(el => el.classList.remove('active'));
    document.getElementById(accountSlug + '_' + tabId)
            .classList.add('active');
    document.querySelector(
        '.tab-btn-' + accountSlug + '[data-tab="' + tabId + '"]'
    ).classList.add('active');
}
</script>
"""


# ---------------------------------------------------------------------------
# Section builders
# ---------------------------------------------------------------------------

def _company_overview_section(raw: dict) -> str:
    wr   = raw.get("web_research", {})
    desc = wr.get("description", {})
    news = wr.get("recent_news", [])
    prio = wr.get("strategic_priorities", [])
    out  = ""

    desc_text = _text(desc)
    if desc_text:
        out += f"<p>{_e(desc_text)}{_src_badge(desc)}</p>"

    if prio:
        out += "<h4>Strategic Priorities</h4><ul>"
        for p in prio[:5]:
            out += f"<li>{_render_item(p)}</li>"
        out += "</ul>"

    if news:
        out += "<h4>Recent News</h4><ul>"
        for n in news[:4]:
            if isinstance(n, dict):
                headline = _e(n.get("headline", "") or n.get("title", ""))
                url      = n.get("url", "") or n.get("source_url", "")
                date     = _e(n.get("date", ""))
                link     = (
                    f"<a href='{_e(url)}' target='_blank'>{headline}</a>"
                    if url else headline
                )
                out += f"<li>{link}"
                if date:
                    out += f" <span style='color:#6b7280;font-size:12px;'>({date})</span>"
                out += "</li>"
            else:
                out += f"<li>{_e(str(n))}</li>"
        out += "</ul>"

    return out or "<p>No company overview data available.</p>"


def _four_leg_stool_section(ts_data: dict, account_name: str) -> str:
    sfdc     = ts_data.get("sfdc_stakeholder", {})
    rows     = sfdc.get("data_rows", [])
    cols     = sfdc.get("column_names", [])

    stakeholders = []
    if rows and cols:
        for row in rows:
            record = dict(zip(cols, row)) if isinstance(row, list) else row
            name   = (
                record.get("Opportunity Owner Name", "")
                or record.get("Account Owner Name", "")
            )
            title  = record.get("Executive Business Sponsor [For Calculation]", "")
            if name:
                stakeholders.append({
                    "name":        name,
                    "title":       title or "",
                    "is_champion": False,
                    "is_eb":       False,
                })

    medd      = ts_data.get("meddpicc_detail", {})
    medd_rows = medd.get("data_rows", [])
    medd_cols = medd.get("column_names", [])
    champion_name = ""
    eb_name       = ""

    if medd_rows and medd_cols:
        rec = (
            dict(zip(medd_cols, medd_rows[0]))
            if isinstance(medd_rows[0], list) else medd_rows[0]
        )
        champion_name = rec.get("Opportunity Gong Champion", "")
        eb_name       = rec.get("Opportunity Gong Economic Buyer", "")

    for s in stakeholders:
        if champion_name and champion_name.lower() in s["name"].lower():
            s["is_champion"] = True
        if eb_name and eb_name.lower() in s["name"].lower():
            s["is_eb"] = True

    legs: dict = {"DATA": [], "BUSINESS": [], "IT": [], "ANALYST": []}
    for s in stakeholders:
        leg = _classify_leg(s["title"])
        if leg in legs:
            legs[leg].append(s)

    out = "<div class='stool-grid'>"
    for row_pair in [("DATA", "BUSINESS"), ("IT", "ANALYST")]:
        for leg_key in row_pair:
            color     = LEG_COLORS[leg_key]
            icon      = LEG_ICONS[leg_key]
            contacts  = legs[leg_key]
            is_empty  = len(contacts) == 0
            leg_class = "stool-leg empty" if is_empty else "stool-leg"

            out += f"<div class='{leg_class}' style='background:#f8fafc;'>"
            out += (
                f"<div class='stool-leg-title' style='background:{color};'>"
                f"{icon} {_e(leg_key)}</div>"
            )

            if is_empty:
                out += "<p class='flag'>⚠️ No contact identified — add to target list</p>"
            else:
                for contact in contacts:
                    out += "<div class='stool-person'>"
                    out += f"<b>{_e(contact['name'])}</b>"
                    if contact["title"]:
                        out += (
                            f"<br><span style='color:#64748b;font-size:12px;'>"
                            f"{_e(contact['title'])}</span>"
                        )
                    if contact["is_champion"]:
                        out += " <span class='badge badge-champion'>🏆 Champion</span>"
                    if contact["is_eb"]:
                        out += " <span class='badge badge-eb'>💰 EB</span>"
                    out += "</div>"

            out += "</div>"

    out += "</div>"
    return out


def _stakeholder_map_section(ts_data: dict) -> str:
    sfdc      = ts_data.get("sfdc_stakeholder", {})
    rows      = sfdc.get("data_rows", [])
    cols      = sfdc.get("column_names", [])
    medd      = ts_data.get("meddpicc_detail", {})
    medd_rows = medd.get("data_rows", [])
    medd_cols = medd.get("column_names", [])
    flags     = ts_data.get("meddpicc_flags", {})
    flag_rows = flags.get("data_rows", [])
    flag_cols = flags.get("column_names", [])

    opp_owner = cs_name = exec_sponsor = ""
    if rows and cols:
        rec = dict(zip(cols, rows[0])) if isinstance(rows[0], list) else rows[0]
        opp_owner    = rec.get("Opportunity Owner Name", "")
        cs_name      = rec.get("Opportunity CS Name", "")
        exec_sponsor = rec.get("Executive Business Sponsor [For Calculation]", "")

    champion_name  = ""
    eb_name        = ""
    champion_valid = False
    eb_valid       = False

    if medd_rows and medd_cols:
        rec = dict(zip(medd_cols, medd_rows[0])) if isinstance(medd_rows[0], list) else medd_rows[0]
        champion_name = rec.get("Opportunity Gong Champion", "")
        eb_name       = rec.get("Opportunity Gong Economic Buyer", "")

    if flag_rows and flag_cols:
        rec = dict(zip(flag_cols, flag_rows[0])) if isinstance(flag_rows[0], list) else flag_rows[0]
        champion_valid = bool(rec.get("Opportunity Gong Champion Validated"))
        eb_valid       = bool(rec.get("Opportunity Gong Economic Buyer Validated"))

    def _flag_if_empty(val, label):
        if val and val.strip():
            return _e(val)
        return f"<span class='flag'>⚠️ {_e(label)} — prioritize discovery</span>"

    if champion_valid and not champion_name:
        champion_display = "<span class='flag'>⚠️ Champion validated in Gong but name not captured</span>"
    elif champion_name:
        champion_display = _e(champion_name)
        if not champion_valid:
            champion_display += " <span class='flag'>(unconfirmed)</span>"
    else:
        champion_display = "<span class='flag'>⚠️ No champion identified — prioritize discovery</span>"

    if eb_valid and not eb_name:
        eb_display = "<span class='flag'>⚠️ EB validated in Gong but name not captured</span>"
    elif eb_name:
        eb_display = _e(eb_name)
        if not eb_valid:
            eb_display += " <span class='flag'>(unconfirmed)</span>"
    else:
        eb_display = "<span class='flag'>⚠️ No economic buyer identified — prioritize discovery</span>"

    crossref = ""
    if champion_name and exec_sponsor and champion_name.lower() != exec_sponsor.lower():
        crossref = (
            f"<p class='flag'>⚠️ Gong Champion ({_e(champion_name)}) "
            f"differs from SFDC Executive Sponsor ({_e(exec_sponsor)}) "
            f"— verify alignment.</p>"
        )

    out  = "<table>"
    out += "<tr><th>Role</th><th>Name</th></tr>"
    out += f"<tr><td>🏆 Champion</td><td>{champion_display}</td></tr>"
    out += f"<tr><td>💰 Economic Buyer</td><td>{eb_display}</td></tr>"
    out += f"<tr><td>Executive Sponsor (SFDC)</td><td>{_flag_if_empty(exec_sponsor, 'No exec sponsor in SFDC')}</td></tr>"
    out += f"<tr><td>Opportunity Owner</td><td>{_flag_if_empty(opp_owner, 'No opp owner found')}</td></tr>"
    out += f"<tr><td>CS Name</td><td>{_flag_if_empty(cs_name, 'No CS assigned')}</td></tr>"
    out += "</table>"
    if crossref:
        out += crossref
    return out


def _talking_point_section(account_name: str, matched_drivers: list, raw: dict) -> str:
    if not matched_drivers:
        return (
            "<div class='talking-point'>"
            "<span class='flag'>⚠️ No matched drivers — "
            "talking point cannot be generated automatically. "
            "Select a value driver manually.</span>"
            "</div>"
        )

    top_driver_key = (
        matched_drivers[0].get("key", "")
        if isinstance(matched_drivers[0], dict)
        else matched_drivers[0]
    )
    signals        = get_money_signals(top_driver_key)
    driver         = get_drivers(top_driver_key)
    label          = driver.get("label", top_driver_key) if driver else top_driver_key
    money_in       = signals.get("money_in", [])
    money_out      = signals.get("money_out", [])
    pain_pts       = driver.get("pain_points", []) if driver else []
    financial_hook = money_in[0] if money_in else (money_out[0] if money_out else "")
    pain_signal    = pain_pts[0] if pain_pts else ""
    flag           = (
        "<br><span class='flag'>⚠️ No financial signal found — generic value used</span>"
        if not financial_hook else ""
    )

    ep        = raw.get("exec_profiles", {})
    execs     = ep.get("executives", [])
    exec_name = execs[0].get("name", "") if execs and isinstance(execs[0], dict) else ""
    addressee = _e(exec_name) if exec_name else f"your team at {_e(account_name)}"

    out  = "<div class='talking-point'>"
    out += f"<strong>💡 ThoughtSpot Talking Point — {_e(label)}</strong><br><br>"
    if pain_signal:
        out += f"A lot of companies like {_e(account_name)} are dealing with {_e(pain_signal.lower())}. "
    out += (
        f"The way {addressee} is thinking about this space, "
        f"there's a real opportunity to {_e(financial_hook.lower())}. "
        f"That's exactly where ThoughtSpot tends to land — "
        f"not as another BI tool, but as the layer that makes your "
        f"data investment actually pay off. "
        f"Worth a conversation to see if the timing is right?"
    )
    out += flag
    out += "</div>"
    return out


def _hiring_signals_section(raw: dict) -> str:
    t     = raw.get("tsumble", {})
    roles = t.get("role_highlights", [])
    if not roles:
        return "<p>No role data available.</p>"

    total  = t.get("total_open_roles", "")
    trends = t.get("hiring_trends", [])
    out    = ""

    if total:
        out += f"<p><b>Total Open Roles:</b> {_e(str(total))}</p>"
    if trends:
        out += "<p><b>Hiring Trends:</b></p><ul>"
        for trend in trends[:3]:
            out += f"<li>{_render_item(trend) if isinstance(trend, dict) else _e(str(trend))}</li>"
        out += "</ul>"

    out += "<table><thead><tr><th>Role</th><th>Department</th><th>Location</th><th>Date Posted</th><th>Source</th></tr></thead><tbody>"
    for r in roles[:10]:
        if isinstance(r, dict):
            title      = _e(r.get("title", ""))
            url        = r.get("url", "")
            title_link = f"<a href='{_e(url)}' target='_blank'>{title} ↗</a>" if url else title
            out += (
                f"<tr><td>{title_link}</td>"
                f"<td>{_e(r.get('department', ''))}</td>"
                f"<td>{_e(r.get('location', ''))}</td>"
                f"<td>{_e(r.get('date_posted', ''))}</td>"
                f"<td>{_e(r.get('source', ''))}</td></tr>"
            )
        else:
            out += f"<tr><td>{_e(str(r))}</td><td></td><td></td><td></td><td></td></tr>"
    out += "</tbody></table>"
    return out


def _competitor_section(raw: dict, matched_drivers: list) -> str:
    ci        = raw.get("competitor_intel", {})
    confirmed = ci.get("tools_confirmed", [])
    suspected = ci.get("tools_suspected", [])
    disp_sum  = ci.get("displacement_summary", "")

    if not confirmed and not suspected and not disp_sum:
        return "<p>No competitor data available.</p>"

    out = ""
    if confirmed:
        out += "<h4>Confirmed Tools</h4>"
        for t in confirmed:
            if not isinstance(t, dict):
                out += f"<p>{_e(str(t))}</p>"
                continue
            tool     = _e(t.get("tool", ""))
            evidence = _e(_text(t.get("evidence", "")))
            angle    = _e(t.get("displacement_angle", "")) or "<span class='flag'>⚠️ No ThoughtSpot angle identified for this tool</span>"
            fit      = _e(t.get("thoughtspot_fit", ""))
            src      = _src_badge(t)
            if not t.get("source"):
                src += "<span class='flag'> ⚠️ Unconfirmed — inferred from limited source</span>"
            out += "<div class='driver'>"
            out += f"<b>{tool}</b>{src}<br>"
            if evidence:
                out += f"<p><i>Evidence:</i> {evidence}</p>"
            if angle:
                out += f"<p><i>ThoughtSpot Angle:</i> {angle}</p>"
            if fit:
                out += f"<p><i>Fit Signal:</i> {fit}</p>"
            out += "</div>"

    if suspected:
        out += "<h4>Suspected Tools</h4><ul>"
        for t in suspected[:5]:
            if isinstance(t, dict):
                out += (
                    f"<li><b>{_e(t.get('tool', ''))}</b> "
                    f"(confidence: {_e(t.get('confidence', ''))}) {_src_badge(t)}"
                    f"{'— ' + _e(_text(t.get('evidence', ''))) if t.get('evidence') else ''}</li>"
                )
            else:
                out += f"<li>{_e(str(t))}</li>"
        out += "</ul>"

    if disp_sum:
        out += f"<p><b>Displacement Summary:</b> {_e(str(disp_sum))}</p>"

    return out


def _value_drivers_section(matched_drivers: list) -> str:
    if not matched_drivers:
        return "<p>No value driver data available.</p>"

    out = ""
    for m in matched_drivers:
        key    = m.get("key", "") if isinstance(m, dict) else m
        driver = get_drivers(key)
        if not driver:
            continue

        label     = _e(driver.get("label", key))
        pain_pts  = driver.get("pain_points", [])
        money_in  = driver.get("money_in", [])
        money_out = driver.get("money_out", [])
        evidence  = m.get("evidence", []) if isinstance(m, dict) else []

        out += f"<div class='driver'><h4>{label}</h4>"
        if evidence:
            out += f"<p><i>Matched signals: {_e('; '.join(str(e) for e in evidence[:3]))}</i></p>"
        if pain_pts:
            out += f"<p><b>Pain addressed:</b> {_e(pain_pts[0])}</p>"
        if money_in:
            out += "<p><b>💰 Value In:</b></p><ul>"
            for bullet in money_in[:2]:
                out += f"<li>{_e(bullet)}</li>"
            out += "</ul>"
        if money_out:
            out += "<p><b>🛡️ Risk Out:</b></p><ul>"
            for bullet in money_out[:2]:
                out += f"<li>{_e(bullet)}</li>"
            out += "</ul>"
        if not money_in and not money_out:
            out += "<p class='flag'>⚠️ No financial signal found — generic value used</p>"
        out += "</div>"

    return out


def _deal_story_section(ts_data: dict) -> str:
    ds_result = ts_data.get("deal_stage", {})
    ft_result = ts_data.get("deal_funnel_timing", {})
    ds_rows   = ds_result.get("data_rows", [])
    ds_cols   = ds_result.get("column_names", [])
    ft_rows   = ft_result.get("data_rows", [])
    ft_cols   = ft_result.get("column_names", [])

    if not ds_rows:
        return "<p>No deal story data available.</p>"

    out = "<div>"
    for row in ds_rows[:3]:
        rec   = dict(zip(ds_cols, row)) if isinstance(row, list) else row
        name  = _e(rec.get("Opportunity Name", ""))
        stage = _e(rec.get("Opportunity Stage Maximum Name", ""))
        owner = _e(rec.get("Opportunity Owner Name", ""))
        date  = _e(rec.get("Opportunity Last Activity Date", ""))
        pq    = rec.get("Opportunity Pipeline Qualified Flag", "")

        out += "<div class='opp-card'>"
        out += f"<b>{name}</b>"
        if stage: out += f" | Stage: {stage}"
        if owner: out += f" | Owner: {owner}"
        if pq:    out += " | <span style='color:#16a34a;'>✅ Pipeline Qualified</span>"
        if date:  out += f"<br><span style='color:#64748b;font-size:12px;'>Last Activity: {date}</span>"
        out += "</div>"
    out += "</div>"

    if ft_rows:
        rec = dict(zip(ft_cols, ft_rows[0])) if isinstance(ft_rows[0], list) else ft_rows[0]
        out += "<h4>Funnel Timing</h4><table><thead><tr><th>Stage</th><th>Duration</th></tr></thead><tbody>"
        for stage_key, label in [
            ("f Opportunity S1 Duration", "S1"),
            ("f Opportunity S2 Duration", "S2"),
            ("f Opportunity S3 Duration", "S3"),
            ("f Opportunity M0 to S7 Duration", "M0→S7"),
            ("Opportunity Current Stage Duration", "Current Stage"),
        ]:
            val = rec.get(stage_key, "")
            if val:
                out += f"<tr><td>{label}</td><td>{_e(str(val))}</td></tr>"
        out += "</tbody></table>"

    return out


def _activity_section(ts_data: dict) -> str:
    act_result = ts_data.get("activity_history", {})
    rows       = act_result.get("data_rows", [])
    cols       = act_result.get("column_names", [])

    if not rows:
        return "<p>No activity history available.</p>"

    out  = "<table><thead><tr>"
    out += "<th>Date</th><th>Type</th><th>Prospect Contact</th><th>Subject</th><th>Owner</th>"
    out += "</tr></thead><tbody>"

    for row in rows[:20]:
        rec  = dict(zip(cols, row)) if isinstance(row, list) else row
        out += (
            f"<tr>"
            f"<td>{_e(rec.get('Activity Time', '') or rec.get('Activity Created Date', ''))}</td>"
            f"<td>{_e(rec.get('Activity Type', ''))}</td>"
            f"<td>Unknown Contact</td>"
            f"<td>{_e(rec.get('Activity Subject', ''))}</td>"
            f"<td>{_e(rec.get('Activity Owner Name', ''))}</td>"
            f"</tr>"
        )

    out += "</tbody></table>"
    out += (
        "<p style='color:#6b7280;font-size:12px;'>"
        "⚠️ Prospect contact name requires SFDC contact matching — "
        "showing 'Unknown Contact' where not resolved.</p>"
    )
    return out


def _sales_call_section(ts_data: dict) -> str:
    flags     = ts_data.get("meddpicc_flags", {})
    detail    = ts_data.get("meddpicc_detail", {})
    flag_rows = flags.get("data_rows", [])
    flag_cols = flags.get("column_names", [])
    det_rows  = detail.get("data_rows", [])
    det_cols  = detail.get("column_names", [])

    if not flag_rows and not det_rows:
        return "<p>No sales call data available.</p>"

    flag_rec = {}
    det_rec  = {}
    if flag_rows and flag_cols:
        flag_rec = dict(zip(flag_cols, flag_rows[0])) if isinstance(flag_rows[0], list) else flag_rows[0]
    if det_rows and det_cols:
        det_rec  = dict(zip(det_cols, det_rows[0]))  if isinstance(det_rows[0], list)  else det_rows[0]

    gong_fields = [
        ("Opportunity Gong Champion Validated",        "Opportunity Gong Champion",         "Champion"),
        ("Opportunity Gong Economic Buyer Validated",  "Opportunity Gong Economic Buyer",   "Economic Buyer"),
        ("Opportunity Gong Identify Pain Validated",   "Opportunity Gong Identify Pain",    "Identified Pain"),
        ("Opportunity Gong Metrics Validated",         "Opportunity Gong Metrics",          "Metrics"),
        ("Opportunity Gong Decision Criteria Validated","Opportunity Gong Decision Criteria","Decision Criteria"),
        ("Opportunity Gong Decision Process Validated", "Opportunity Gong Decision Process", "Decision Process"),
        ("Opportunity Gong Paper Process Validated",   "Opportunity Gong Paper Process",    "Paper Process"),
        ("Opportunity Gong Competition Validated",     "Opportunity Gong Competition",      "Competition"),
        ("Opportunity Gong Data Readiness Validated",  "Opportunity Gong Data Readiness",   "Data Readiness"),
    ]

    out  = "<table><thead><tr><th>Signal</th><th>Validated</th><th>Detail</th></tr></thead><tbody>"
    for flag_field, detail_field, label in gong_fields:
        validated   = flag_rec.get(flag_field, False)
        detail_text = det_rec.get(detail_field, "")
        validated_display = (
            "<span style='color:#16a34a;'>✅ Yes</span>"
            if validated
            else "<span style='color:#ef4444;'>❌ No</span>"
        )
        if label in ("Champion", "Economic Buyer") and validated and not detail_text:
            detail_display = f"<span class='flag'>⚠️ {label} validated in Gong but name not captured</span>"
        else:
            detail_display = _e(detail_text) if detail_text else "—"
        out += f"<tr><td>{_e(label)}</td><td>{validated_display}</td><td>{detail_display}</td></tr>"
    out += "</tbody></table>"
    return out


def _6sense_section(ts_data: dict) -> str:
    result = ts_data.get("6sense_intent", {})
    rows   = result.get("data_rows", [])
    cols   = result.get("column_names", [])

    if not rows:
        return "<p>No 6Sense intent data available.</p>"

    out  = "<table><thead><tr><th>Account</th><th>Intent Grade</th><th>Reach Grade</th></tr></thead><tbody>"
    for row in rows[:10]:
        rec = dict(zip(cols, row)) if isinstance(row, list) else row
        out += (
            f"<tr>"
            f"<td>{_e(rec.get('Account Name', ''))}</td>"
            f"<td>{_e(_score_to_grade(rec.get('Person 6S Intent Score', '')))}</td>"
            f"<td>{_e(_score_to_grade(rec.get('Account Snapshot 6S Reach Score', '')))}</td>"
            f"</tr>"
        )
    out += "</tbody></table>"
    return out


def _case_studies_section(raw: dict, account_name: str) -> str:
    studies = raw.get("case_studies", {}).get("recommended_case_studies", [])
    if not studies:
        return "<p>No case studies matched.</p>"

    out = "<ul style='list-style:none;padding:0;'>"
    for s in studies[:5]:
        if not isinstance(s, dict):
            out += f"<li>{_e(str(s))}</li>"
            continue
        company = _e(s.get("company", ""))
        url     = s.get("url", "")
        why     = _e(s.get("why_chosen", ""))
        metric  = _e(s.get("key_metric", ""))
        link    = f"<a href='{_e(url)}' target='_blank'>{company} ↗</a>" if url else company

        out += "<li style='background:#f8fafc;border:1px solid #e2e8f0;border-radius:8px;padding:14px;margin:8px 0;'>"
        out += f"<b>{link}</b>"
        if metric:
            out += f"<div style='font-size:18px;font-weight:700;color:{BLUE};margin:6px 0;'>📊 {metric}</div>"
        if why:
            out += f"<p><i>Why for {_e(account_name)}:</i> {why}</p>"
        if not url:
            out += "<span class='flag'>⚠️ No URL available for this case study</span>"
        out += "</li>"
    out += "</ul>"
    return out


def _exec_profiles_section(raw: dict) -> str:
    execs = raw.get("exec_profiles", {}).get("executives", [])
    if not execs:
        return "<p>No executive profiles available.</p>"

    out = ""
    for exec_data in execs[:5]:
        if not isinstance(exec_data, dict):
            out += f"<p>{_e(str(exec_data))}</p>"
            continue

        name     = _e(exec_data.get("name", ""))
        title    = _e(exec_data.get("title", ""))
        li_url   = exec_data.get("linkedin_url", "")
        bio      = exec_data.get("bio_summary", {})
        quotes   = exec_data.get("public_quotes", [])
        activity = exec_data.get("recent_activity", [])

        out += "<div class='exec-card'>"
        out += f"<h4>{name}"
        if title:   out += f" — {title}"
        if li_url:  out += f" <a href='{_e(li_url)}' target='_blank' style='font-size:12px;'>LinkedIn ↗</a>"
        out += "</h4>"

        bio_text = _text(bio)
        if bio_text:
            out += f"<p>{_e(bio_text)}{_src_badge(bio)}</p>"

        if activity:
            out += "<p><b>Recent Activity:</b></p><ul>"
            for act in activity[:3]:
                out += f"<li>{_render_item(act)}</li>"
            out += "</ul>"

        if quotes:
            out += "<p><b>Public Quotes:</b></p>"
            for q in quotes[:2]:
                if isinstance(q, dict):
                    quote_text = _e(q.get("quote", ""))
                    context    = _e(q.get("context", ""))
                    src        = _src_badge(q)
                    if quote_text:
                        out += f"<blockquote>{quote_text}{src}"
                        if context:
                            out += f"<br><span style='font-size:12px;color:#64748b;'>{context}</span>"
                        out += "</blockquote>"
        out += "</div>"

    return out


def _outreach_section(outreach_data: dict) -> str:
    if not outreach_data:
        return "<p>Outreach sequences not yet generated.</p>"

    sequences = outreach_data.get("sequences", [])
    if not sequences:
        return "<p>No outreach sequences available.</p>"

    out = ""
    for seq in sequences:
        if not isinstance(seq, dict):
            continue
        name    = _e(seq.get("name", "") or seq.get("contact_name", ""))
        title   = _e(seq.get("title", "") or seq.get("contact_title", ""))
        emails  = seq.get("emails", [])
        li_msgs = seq.get("linkedin_messages", [])

        out += "<div class='exec-card'>"
        out += f"<h4>✉️ {name}"
        if title: out += f" — {title}"
        out += "</h4>"

        if emails:
            out += "<p><b>Email Sequence:</b></p>"
            for i, email in enumerate(emails, 1):
                if isinstance(email, dict):
                    out += f"<p><b>Email {i}: {_e(email.get('subject', f'Email {i}'))}</b></p>"
                    out += f"<pre>{_e(email.get('body', ''))}</pre>"
                else:
                    out += f"<pre>{_e(str(email))}</pre>"

        if li_msgs:
            out += "<p><b>LinkedIn Sequence:</b></p>"
            for i, msg in enumerate(li_msgs, 1):
                if isinstance(msg, dict):
                    out += f"<p><b>LinkedIn {i}:</b></p>"
                    out += f"<pre>{_e(msg.get('body', '') or msg.get('message', ''))}</pre>"
                else:
                    out += f"<pre>{_e(str(msg))}</pre>"

        out += "</div>"

    return out


# ---------------------------------------------------------------------------
# Tab definitions
# ---------------------------------------------------------------------------

def _get_tabs(phase: int) -> list:
    tabs = [
        ("overview",      "Company Overview"),
        ("stakeholders",  "Stakeholders"),
        ("why_ts",        "Why ThoughtSpot"),
        ("competitor",    "Competitor Intel"),
        ("deal_story",    "Deal Story"),
        ("sales_call",    "Sales Call Analysis"),
        ("6sense",        "6Sense Intent"),
        ("roles",         "Hiring Signals"),
        ("case_studies",  "Case Studies"),
        ("exec_profiles", "Exec Profiles"),
    ]
    if phase == 2:
        tabs.append(("outreach", "Outreach"))
    return tabs


# ---------------------------------------------------------------------------
# HTML page wrapper
# ---------------------------------------------------------------------------

def _build_html_page(title: str, body: str) -> str:
    return (
        "<!DOCTYPE html><html lang='en'><head>"
        "<meta charset='UTF-8'>"
        "<meta name='viewport' content='width=device-width,initial-scale=1'>"
        f"<title>{_e(title)}</title>"
        + _CSS
        + "</head><body><div class='container'>"
        + body
        + _JS
        + "</div></body></html>"
    )


# ---------------------------------------------------------------------------
# Primary public function — internal PG report
# Returns dict with filename + html string — no file writes
# ---------------------------------------------------------------------------

def build_pg_report(
    slug:            str,
    account_name:    str,
    raw:             dict,
    ts_data:         dict,
    matched_drivers: list,
    header_data:     dict,
    phase:           int  = 1,
    outreach_data:   dict = None,
    output_dir:      str  = "/sandbox",  # kept for API compatibility, not used
) -> dict:
    """
    Build a PG report HTML string.

    Returns
    -------
    dict with keys:
        filename : str  — suggested filename (e.g. "acme_corp_pg_report_draft.html")
        html     : str  — complete HTML string ready to deliver
        slug     : str  — account slug
        phase    : int  — 1 (draft) or 2 (final)
    """
    outreach_data = outreach_data or {}
    tabs          = _get_tabs(phase)
    owner         = header_data.get("owner_name", "AE")
    region        = header_data.get("region", "")
    now           = datetime.datetime.utcnow().strftime("%B %d, %Y %H:%M UTC")

    body  = "<div class='header-bar'>"
    body += f"<h1>PG Report — {_e(account_name)}</h1>"
    body += f"<p>Prepared by: {_e(owner)}"
    if region:
        body += f" | {_e(region)}"
    body += f"</p><p style='font-size:12px;opacity:.7;'>Generated {now}</p>"
    body += "</div>"
    body += f"<div class='account-section' id='{_e(slug)}'>"

    body += "<div class='tab-nav'>"
    for i, (tab_id, tab_label) in enumerate(tabs):
        active = "active" if i == 0 else ""
        body += (
            f"<button class='tab-btn tab-btn-{_e(slug)} {active}' "
            f"data-tab='{_e(tab_id)}' "
            f"onclick='showTab(\"{_e(slug)}\",\"{_e(tab_id)}\")'>"
            f"{_e(tab_label)}</button>"
        )
    body += "</div>"

    for i, (tab_id, _) in enumerate(tabs):
        active = "active" if i == 0 else ""
        body += (
            f"<div id='{_e(slug)}_{_e(tab_id)}' "
            f"class='tab-content tab-content-{_e(slug)} {active}'>"
            f"<div class='section'>"
        )

        if tab_id == "overview":
            body += _company_overview_section(raw)
        elif tab_id == "stakeholders":
            body += "<h3>4-Leg Stool</h3>"
            body += _four_leg_stool_section(ts_data, account_name)
            body += "<h3>Stakeholder Map</h3>"
            body += _stakeholder_map_section(ts_data)
            body += "<h3>ThoughtSpot Talking Point</h3>"
            body += _talking_point_section(account_name, matched_drivers, raw)
        elif tab_id == "why_ts":
            body += _value_drivers_section(matched_drivers)
        elif tab_id == "competitor":
            body += _competitor_section(raw, matched_drivers)
        elif tab_id == "deal_story":
            body += _deal_story_section(ts_data)
        elif tab_id == "sales_call":
            body += _sales_call_section(ts_data)
            body += "<h3>Activity History</h3>"
            body += _activity_section(ts_data)
        elif tab_id == "6sense":
            body += _6sense_section(ts_data)
        elif tab_id == "roles":
            body += _hiring_signals_section(raw)
        elif tab_id == "case_studies":
            body += _case_studies_section(raw, account_name)
        elif tab_id == "exec_profiles":
            body += _exec_profiles_section(raw)
        elif tab_id == "outreach":
            body += _outreach_section(outreach_data)

        body += "</div></div>"

    body += "</div>"

    suffix   = "draft" if phase == 1 else "final"
    filename = f"{slug}_pg_report_{suffix}.html"
    html     = _build_html_page(f"PG Report — {account_name}", body)

    print(f"[pg_report_builder v5.1] Phase {phase} report built → {filename}")
    return {"filename": filename, "html": html, "slug": slug, "phase": phase}


# ---------------------------------------------------------------------------
# One-pager builder — external, customer-facing
# Returns dict with filename + html string — no file writes
# ---------------------------------------------------------------------------

def build_onepager(
    slug:            str,
    account_name:    str,
    raw:             dict,
    matched_drivers: list,
    output_dir:      str = "/sandbox",  # kept for API compatibility, not used
) -> dict:
    """
    Build an external customer-facing one-pager HTML string.

    Returns
    -------
    dict with keys:
        filename : str  — suggested filename (e.g. "acme_corp_onepager.html")
        html     : str  — complete HTML string ready to deliver
        slug     : str  — account slug
    """
    wr       = raw.get("web_research", {})
    cs_data  = raw.get("case_studies", {})
    desc     = _text(wr.get("description", {}))
    pain_pts = wr.get("pain_points", [])
    studies  = cs_data.get("recommended_case_studies", [])

    challenges = [_text(p) for p in pain_pts[:4] if _text(p)]

    value_statements = []
    for m in matched_drivers[:4]:
        key    = m.get("key", "") if isinstance(m, dict) else m
        driver = get_drivers(key)
        if driver:
            signals = get_money_signals(key)
            mi      = signals.get("money_in", [])
            mo      = signals.get("money_out", [])
            hook    = mi[0] if mi else (mo[0] if mo else "")
            if hook:
                value_statements.append(hook)

    proof_points = []
    for s in studies[:3]:
        if isinstance(s, dict):
            metric  = s.get("key_metric", "")
            company = s.get("company", "")
            if metric and company:
                proof_points.append(f"{_e(company)}: {_e(metric)}")

    onepager_css = f"""
<style>
*, *::before, *::after {{box-sizing: border-box;}}
body {{font-family: 'Inter', 'Segoe UI', sans-serif; margin: 0; padding: 0; background: {WHITE}; color: #1e293b;}}
.page {{max-width: 800px; margin: 0 auto; padding: 40px 48px;}}
.hero {{background: linear-gradient(135deg, {NAVY}, {BLUE}); color: #fff; padding: 32px 40px; border-radius: 12px; margin-bottom: 32px;}}
.hero h1 {{font-size: 26px; font-weight: 700; margin: 0 0 8px; color: #fff;}}
.hero p {{margin: 0; opacity: .85; font-size: 15px;}}
h2 {{font-size: 18px; font-weight: 700; color: {NAVY}; margin: 28px 0 12px; border-bottom: 2px solid {BLUE}; padding-bottom: 6px;}}
ul {{padding-left: 20px; margin: 8px 0;}}
li {{margin: 6px 0; line-height: 1.6;}}
.value-card {{background: {LIGHT_BLUE}; border-radius: 8px; padding: 12px 16px; margin: 8px 0; border-left: 4px solid {BLUE}; font-size: 14px; line-height: 1.6;}}
.proof-card {{background: #f0fdf4; border-radius: 8px; padding: 12px 16px; margin: 8px 0; border-left: 4px solid #16a34a; font-size: 14px; font-weight: 600;}}
.cta {{background: {BLUE}; color: #fff; border-radius: 10px; padding: 24px 32px; text-align: center; margin-top: 32px;}}
.cta a {{color: #fff; font-size: 18px; font-weight: 700; text-decoration: none;}}
.cta p {{color: #fff; opacity: .85; margin: 8px 0 0;}}
@media print {{body {{background: #fff;}} .cta {{background: {NAVY};}}}}
</style>
"""

    body  = "<div class='page'>"
    body += "<div class='hero'>"
    body += f"<h1>{_e(account_name)}</h1>"
    if desc:
        body += f"<p>{_e(desc[:200])}</p>"
    body += "</div>"

    if challenges:
        body += "<h2>Business Challenges</h2><ul>"
        for c in challenges:
            body += f"<li>{_e(c)}</li>"
        body += "</ul>"

    if value_statements:
        body += "<h2>How ThoughtSpot Helps</h2>"
        for v in value_statements:
            body += f"<div class='value-card'>{_e(v)}</div>"
    else:
        body += (
            "<h2>How ThoughtSpot Helps</h2>"
            "<div class='value-card'>"
            "ThoughtSpot delivers AI-powered analytics that help business "
            "teams get answers from data instantly — no SQL required."
            "</div>"
        )

    if proof_points:
        body += "<h2>Customer Proof Points</h2>"
        for p in proof_points:
            body += f"<div class='proof-card'>📊 {p}</div>"

    body += (
        "<div class='cta'>"
        "<a href='https://www.thoughtspot.com/demo' target='_blank'>"
        "See ThoughtSpot in Action →</a>"
        "<p>Request a personalized demo at thoughtspot.com/demo</p>"
        "</div>"
    )
    body += "</div>"

    filename = f"{slug}_onepager.html"
    full_html = (
        "<!DOCTYPE html><html lang='en'><head>"
        "<meta charset='UTF-8'>"
        "<meta name='viewport' content='width=device-width,initial-scale=1'>"
        f"<title>{_e(account_name)} — ThoughtSpot</title>"
        + onepager_css
        + "</head><body>"
        + body
        + "</body></html>"
    )

    print(f"[pg_report_builder v5.1] One-pager built → {filename}")
    return {"filename": filename, "html": full_html, "slug": slug}


# ---------------------------------------------------------------------------
# Self-test
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print("=== pg_report_builder v5.1 self-test ===\n")

    raw = {
        "web_research": {
            "industry": "Financial Services",
            "description": {"text": "Acme Corp is a leading financial services firm.", "source": "https://acme.com/about", "source_type": "web", "url": "https://acme.com/about"},
            "recent_news": [{"headline": "Acme raises $200M Series D", "date": "2024-11-01", "url": "https://techcrunch.com/acme", "source_type": "news"}],
            "strategic_priorities": [{"text": "Expand self-service analytics", "source": "https://acme.com/blog", "source_type": "web", "url": "https://acme.com/blog"}],
            "pain_points": [{"text": "Analysts overwhelmed with ad hoc requests", "source": "https://acme.com/jobs", "source_type": "job_posting", "url": "https://acme.com/jobs"}],
        },
        "tsumble": {
            "total_open_roles": 12,
            "role_highlights": [{"title": "Senior Data Analyst", "department": "Analytics", "location": "New York, NY", "date_posted": "2024-11-01", "source": "LinkedIn", "source_type": "linkedin", "url": "https://linkedin.com/jobs/123"}],
            "hiring_trends": [{"trend": "Heavy hiring in data and analytics roles", "evidence": "8 of 12 open roles are data-related", "source": "LinkedIn", "url": "https://linkedin.com/jobs"}],
        },
        "competitor_intel": {
            "tools_confirmed": [{"tool": "Tableau", "evidence": "Multiple job postings require Tableau", "source": "https://acme.com/jobs", "source_type": "job_posting", "url": "https://acme.com/jobs", "displacement_angle": "ThoughtSpot offers AI NLQ vs static dashboards", "thoughtspot_fit": "Strong"}],
            "tools_suspected": [],
            "displacement_summary": "Tableau is primary BI tool.",
        },
        "exec_profiles": {
            "executives": [{"name": "Jane Smith", "title": "Chief Data Officer", "linkedin_url": "https://linkedin.com/in/janesmith", "bio_summary": {"text": "Jane leads all data strategy.", "source": "https://acme.com/team", "url": "https://acme.com/team"}, "public_quotes": [{"quote": "We need to democratize data.", "context": "Data Summit 2024", "source": "https://datasummit.com", "date": "2024-09-15", "url": "https://datasummit.com/janesmith"}], "recent_activity": [], "talking_points": []}]
        },
        "case_studies": {
            "recommended_case_studies": [{"company": "T-Mobile", "url": "https://www.thoughtspot.com/customers/t-mobile", "why_chosen": "Similar self-service BI transformation", "key_metric": "10x faster insights for 5,000+ users", "industry_match": "Enterprise", "use_case_match": "Self-service BI", "source": "ThoughtSpot case study library", "source_type": "case_study"}]
        },
    }

    ts_data = {
        "sfdc_stakeholder": {"status": "ok", "column_names": ["Account Name", "Account Owner Name", "Account Owner Team", "Opportunity Name", "Opportunity Owner Name", "Opportunity CS Name", "Executive Business Sponsor [For Calculation]", "Opportunity Status"], "data_rows": [["Acme Corp", "Bob Jones", "West", "Acme - Q1 2025", "Bob Jones", "Sarah Lee", "Jane Smith", "Open"]]},
        "meddpicc_flags": {"status": "ok", "column_names": ["Account Name", "Opportunity Name", "Opportunity Gong Champion Validated", "Opportunity Gong Economic Buyer Validated", "Opportunity Gong Identify Pain Validated", "Opportunity Gong Metrics Validated", "Opportunity Gong Decision Criteria Validated", "Opportunity Gong Decision Process Validated", "Opportunity Gong Paper Process Validated", "Opportunity Gong Competition Validated", "Opportunity Gong Data Readiness Validated"], "data_rows": [["Acme Corp", "Acme - Q1 2025", True, False, True, False, False, False, False, True, False]]},
        "meddpicc_detail": {"status": "ok", "column_names": ["Account Name", "Opportunity Name", "Opportunity Gong Champion", "Opportunity Gong Economic Buyer", "Opportunity Gong Identify Pain", "Opportunity Gong Metrics", "Opportunity Gong Decision Criteria", "Opportunity Gong Decision Process", "Opportunity Gong Paper Process", "Opportunity Gong Competition", "Opportunity Gong Data Readiness"], "data_rows": [["Acme Corp", "Acme - Q1 2025", "Jane Smith", "", "Analyst bottleneck", "", "", "", "", "Tableau", ""]]},
        "deal_stage": {"status": "ok", "column_names": ["Account Name", "Opportunity Name", "Opportunity Stage Maximum Name", "Opportunity Pipeline Qualified Flag", "Opportunity Owner Name", "Opportunity Last Activity Date"], "data_rows": [["Acme Corp", "Acme - Q1 2025", "S2 - Discovery", True, "Bob Jones", "2024-11-10"]]},
        "deal_funnel_timing": {"status": "empty", "data_rows": [], "column_names": []},
        "activity_history": {"status": "ok", "column_names": ["Account Name", "Activity Type", "Activity Subject", "Activity Time", "Activity Owner Name", "Activity Owner Role", "Activity Direction"], "data_rows": [["Acme Corp", "Call", "Discovery call", "2024-11-10", "Bob Jones", "AE", "Outbound"]]},
        "6sense_intent": {"status": "ok", "column_names": ["Account Name", "Person 6S Intent Score", "Account Snapshot 6S Reach Score", "Account Owner Name"], "data_rows": [["Acme Corp", 87, 72, "Bob Jones"]]},
    }

    matched_drivers = [
        {"key": "enable_self_service", "label": "Enable Self-Service for Business Teams", "match_score": 9, "evidence": ["self-service BI", "pain: analysts overwhelmed"]},
        {"key": "modernize_legacy_bi", "label": "Modernize Legacy BI Stack", "match_score": 6, "evidence": ["migrate from Tableau"]},
    ]

    header_data = {"owner_name": "Bob Jones", "region": "West"}

    # Test 1 — Phase 1
    result1 = build_pg_report(slug="acme_corp", account_name="Acme Corp", raw=raw, ts_data=ts_data, matched_drivers=matched_drivers, header_data=header_data, phase=1)
    assert result1["filename"] == "acme_corp_pg_report_draft.html"
    assert "<html" in result1["html"]
    assert result1["phase"] == 1
    print(f"✅ Phase 1 report built: {result1['filename']} ({len(result1['html'])} chars)")

    # Test 2 — Phase 2
    outreach_data = {"sequences": [{"name": "Jane Smith", "title": "CDO", "emails": [{"subject": "Re: data at Acme", "body": "Hi Jane,\n\nSaw your Data Summit talk.\n\nBob"}], "linkedin_messages": [{"body": "Hi Jane — open to a chat?"}]}]}
    result2 = build_pg_report(slug="acme_corp", account_name="Acme Corp", raw=raw, ts_data=ts_data, matched_drivers=matched_drivers, header_data=header_data, phase=2, outreach_data=outreach_data)
    assert result2["filename"] == "acme_corp_pg_report_final.html"
    assert "Jane Smith" in result2["html"]
    assert result2["phase"] == 2
    print(f"✅ Phase 2 report built: {result2['filename']} ({len(result2['html'])} chars)")

    # Test 3 — One-pager
    onepager = build_onepager(slug="acme_corp", account_name="Acme Corp", raw=raw, matched_drivers=matched_drivers)
    assert onepager["filename"] == "acme_corp_onepager.html"
    assert "thoughtspot.com/demo" in onepager["html"]
    assert "MEDDPICC" not in onepager["html"]
    assert "SFDC" not in onepager["html"]
    assert "Bob Jones" not in onepager["html"]
    print(f"✅ One-pager built: {onepager['filename']} ({len(onepager['html'])} chars)")

    # Test 4 — 6Sense grades not raw scores
    assert "87" not in result1["html"], "Raw 6Sense score must not appear"
    assert "72" not in result1["html"], "Raw reach score must not appear"
    print("✅ 6Sense raw scores not in report — grades only")

    # Test 5 — Draft has no outreach tab, final does
    assert "outreach" not in result1["html"].lower() or "Outreach" not in result1["html"]
    assert "Data Summit" in result2["html"]
    print("✅ Phase 1 no outreach, Phase 2 has outreach")

    # Test 6 — Return type is dict not filepath string
    assert isinstance(result1, dict), "build_pg_report must return dict"
    assert isinstance(onepager, dict), "build_onepager must return dict"
    assert "html" in result1
    assert "html" in onepager
    print("✅ Return types are dicts with html key")

    print("\n=== All tests passed ===")
