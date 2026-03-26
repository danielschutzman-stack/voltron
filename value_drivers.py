"""
value_drivers.py
ThoughtSpot value drivers, pain points, and keywords by use case.
Fetched at bootstrap and used to personalize Gong Templates and Talking Points.

Usage:
    from value_drivers import VALUE_DRIVERS, get_drivers, get_money_signals,
                              match_drivers, list_drivers

    # Get a specific driver by key
    driver = get_drivers("modernize_legacy_bi")

    # Get money signals for a matched driver
    signals = get_money_signals("modernize_legacy_bi")

    # Auto-match drivers from free-text signals
    result = match_drivers("they use Tableau and have a large analyst backlog")
    if result["status"] == "ok":
        for match in result["matched"]:
            print(match["label"], match["evidence"])

    # Two-pass pattern (use in PG run after web research + competitor intel land):
    pass1 = match_drivers(extract_text(web_research_json.get("pain_points", [])))
    pass2 = match_drivers(
        extract_text(web_research_json.get("pain_points", [])) + " " +
        extract_text(web_research_json.get("competitor_tools_in_use", [])) + " " +
        extract_text(competitor_intel_json.get("displacement_opportunity", ""))
    )
    matched = pass2["matched"] if pass2["status"] == "ok" else pass1["matched"]
"""

import json


# ---------------------------------------------------------------------------
# Value driver definitions
# ---------------------------------------------------------------------------

VALUE_DRIVERS = {

    "accelerate_customer_facing_innovation": {
        "label": "Accelerate Customer-Facing Innovation",
        "keywords": [
            "embedded product analytics", "monetize data", "customer experience analytics",
            "OEM analytics", "product differentiation", "data-driven products",
        ],
        "pain_points": [
            "competitors shipping analytics features faster",
            "customers churning due to poor data visibility in product",
            "engineering backlog for BI features",
            "slow time-to-market for new data features",
            "customers requesting reporting capabilities",
        ],
        "money_in": [
            "Monetize data as a product line - analytics as a revenue feature, not a cost center",
            "Reduce churn by giving customers the data visibility they are asking for",
            "Ship analytics features 10x faster than building in-house - compress time-to-revenue",
            "Differentiate product with embedded AI analytics competitors cannot replicate quickly",
        ],
        "money_out": [
            "Eliminate engineering backlog cost - stop diverting dev resources to build BI from scratch",
            "Replace high-cost custom analytics builds with ThoughtSpot Embedded SDK",
        ],
    },

    "accelerate_time_to_insight": {
        "label": "Accelerate Time to Insight",
        "keywords": [
            "speed to insight", "real-time insights", "instant answers", "rapid decision making",
            "on-demand analytics", "agile BI",
        ],
        "pain_points": [
            "waiting days or weeks for reports",
            "data team bottleneck",
            "analysts overwhelmed with ad hoc requests",
            "slow query performance",
            "business users cannot get answers without IT",
            "decisions made on stale data",
        ],
        "money_in": [
            "Faster decisions = faster revenue cycles - reduce latency between insight and action",
            "Real-time inventory and pricing decisions directly impact margin",
        ],
        "money_out": [
            "Cut analyst hours spent on ad hoc requests - every report request has a loaded cost",
            "Reduce cost of delayed decisions - stale data leads to missed opportunities and avoidable losses",
        ],
    },

    "automate_analysis_alerting": {
        "label": "Automate Analysis or Alerting",
        "keywords": [
            "anomaly detection", "proactive alerts", "KPI monitoring", "SpotIQ",
            "automated reporting", "AI-driven analysis", "scheduled insights", "smart alerts",
        ],
        "pain_points": [
            "manual monitoring of dashboards",
            "missing critical business changes",
            "analysts spending time on repetitive reports",
            "no early warning system for KPI drops",
            "reactive rather than proactive decision making",
        ],
        "money_in": [
            "Catch revenue anomalies before they become write-offs",
            "Proactive alerts on churn signals, demand spikes, or margin erosion",
        ],
        "money_out": [
            "Eliminate analyst time on repetitive scheduled reports - redeploy to higher-value work",
            "Avoid cost of missed KPI drops - early warning systems prevent reactive firefighting",
        ],
    },

    "embed_analytics_in_products_workflows": {
        "label": "Embed Analytics in Products/Workflows",
        "keywords": [
            "embedded analytics", "embedded BI", "ThoughtSpot Embedded", "analytics SDK",
            "white-label analytics", "in-app analytics", "ThoughtSpot Everywhere", "OEM analytics",
        ],
        "pain_points": [
            "users leaving the product to get data",
            "low engagement with standalone BI tools",
            "high cost of building analytics from scratch",
            "poor developer experience embedding BI",
            "analytics feels disconnected from workflows",
            "Salesforce and ServiceNow users need insights in context",
        ],
        "money_in": [
            "In-app analytics increases product stickiness and reduces churn",
            "Analytics as an upsell tier - charge premium for data-rich product experience",
        ],
        "money_out": [
            "Avoid cost of building embedded analytics in-house",
            "Reduce dev cycles - ThoughtSpot Embedded deploys in weeks, not quarters",
        ],
    },

    "enable_self_service": {
        "label": "Enable Self-Service for Business Teams",
        "keywords": [
            "self-service BI", "data democratization", "no-code analytics",
            "natural language search", "NLQ", "citizen analytics",
            "business user analytics", "ad hoc analysis",
        ],
        "pain_points": [
            "business teams dependent on data team for every question",
            "report backlog piling up",
            "non-technical users intimidated by BI tools",
            "only a fraction of company using data tools",
            "analysts as bottleneck",
            "low BI adoption across organization",
        ],
        "money_in": [
            "10x the number of people making data-driven decisions - compounding revenue impact",
            "Faster self-serve = faster go-to-market decisions across every business team",
        ],
        "money_out": [
            "Reduce analyst headcount pressure - self-service eliminates low-value ticket volume",
            "Cut cost-per-insight - democratized access reduces per-question cost dramatically",
        ],
    },

    "expand_data_access_ai_nlq": {
        "label": "Expand Data Access with AI & NLQ",
        "keywords": [
            "natural language query", "NLQ", "NLP search", "conversational analytics",
            "ThoughtSpot Sage", "Spotter", "search-driven analytics",
            "AI-powered BI", "democratize data",
        ],
        "pain_points": [
            "SQL required to query data",
            "non-technical users locked out of data",
            "data accessible only to analysts",
            "complex data questions go unanswered",
            "business users cannot self-serve",
            "over-reliance on technical teams",
        ],
        "money_in": [
            "Unlock value from data investments that are currently inaccessible to most of the business",
            "AI-driven answers accelerate decisions that drive revenue",
        ],
        "money_out": [
            "Remove SQL dependency - eliminate translation layer between business question and data answer",
            "Reduce cost of data literacy programs - NLQ lowers the skill bar for data access",
        ],
    },

    "improve_decisions_proactive_insights": {
        "label": "Improve Decisions with Proactive Insights",
        "keywords": [
            "proactive insights", "AI highlights", "predictive analytics", "forecasting",
            "root cause analysis", "SpotIQ", "augmented analytics",
            "automated recommendations", "KPI fluctuation analysis",
        ],
        "pain_points": [
            "decisions based on gut feel not data",
            "no visibility into why KPIs changed",
            "insights come too late to act",
            "leaders lack real-time business context",
            "no early warning on business anomalies",
            "reactive decision making",
        ],
        "money_in": [
            "AI surfaces revenue opportunities humans would miss in static dashboards",
            "Faster root cause analysis = faster recovery from revenue-impacting events",
        ],
        "money_out": [
            "Reduce cost of reactive firefighting - proactive insights prevent avoidable losses",
            "Cut time analysts spend explaining why a metric dropped - AI does it automatically",
        ],
    },

    "increase_adoption": {
        "label": "Increase Adoption of Data Stack",
        "keywords": [
            "BI adoption", "data culture", "data literacy", "active users",
            "expand analytics usage", "drive data usage", "user engagement", "analytics ROI",
        ],
        "pain_points": [
            "expensive data stack underutilized",
            "low monthly active users on BI platform",
            "data team building reports nobody reads",
            "tools too complex for business users",
            "poor ROI on data investments",
            "resistance to adopting new analytics tools",
        ],
        "money_in": [
            "Maximize ROI on existing data infrastructure - ThoughtSpot is the consumption layer",
            "Higher adoption = more data-driven decisions = measurable business impact",
        ],
        "money_out": [
            "Stop paying for seats nobody uses - consolidate on a platform people actually adopt",
            "Reduce sunk cost on underutilized data investments - ThoughtSpot drives active usage",
        ],
    },

    "modernize_legacy_bi": {
        "label": "Modernize Legacy BI Stack",
        "keywords": [
            "BI modernization", "replace legacy BI", "migrate from Tableau",
            "migrate from Cognos", "migrate from MicroStrategy", "migrate from IBM Cognos",
            "cloud BI migration", "cloud-native BI", "digital transformation",
            "replace on-premise BI",
        ],
        "pain_points": [
            "legacy BI too slow",
            "static dashboards not meeting business needs",
            "high maintenance cost of on-premise BI",
            "cannot connect to cloud data sources",
            "IT spending too much time maintaining old BI",
            "Tableau or Cognos or MicroStrategy too rigid",
            "no AI capabilities in current stack",
        ],
        "money_in": [
            "Cloud-native BI unlocks new use cases that drive revenue on modern data stack",
            "AI-ready platform future-proofs analytics investment",
        ],
        "money_out": [
            "Eliminate on-prem maintenance cost - licensing, hardware, IT support",
            "Consolidate BI vendors - most companies overpay for overlapping tools",
            "Cut legacy BI renewal cost - ThoughtSpot typically delivers significant TCO reduction",
        ],
    },

    "reduce_tco_analyst_effort": {
        "label": "Reduce TCO / Analyst Effort",
        "keywords": [
            "reduce total cost of ownership", "TCO reduction", "analyst productivity",
            "reduce data requests", "eliminate bottlenecks", "reduce report backlog",
            "cost savings", "analyst efficiency", "reduce IT dependency",
        ],
        "pain_points": [
            "high cost of maintaining BI infrastructure",
            "analysts spending most of time on data prep not analysis",
            "too many one-off report requests",
            "BI licensing too expensive",
            "data team headcount not scaling with demand",
            "manual data processes wasting analyst time",
        ],
        "money_in": [
            "Redeploy analyst capacity from report-building to strategic revenue-generating analysis",
        ],
        "money_out": [
            "Cut BI licensing cost - consolidate on one platform vs. multiple point solutions",
            "Reduce headcount pressure - self-service absorbs majority of ad hoc request volume",
            "Eliminate manual reporting labor cost - automation replaces repetitive analyst work",
        ],
    },

    "support_strategic_initiative": {
        "label": "Support Strategic Initiative",
        "keywords": [
            "strategic analytics", "executive analytics", "C-suite insights",
            "business transformation", "data strategy", "enterprise analytics",
            "strategic decision making", "board-level reporting", "digital transformation",
        ],
        "pain_points": [
            "executives lacking real-time visibility",
            "no single source of truth for strategic KPIs",
            "BI not aligned to company priorities",
            "analytics siloed from strategic planning",
            "leadership making decisions without data",
            "no unified view of business performance",
        ],
        "money_in": [
            "Align executive decisions to real-time data - every point of margin improvement matters",
            "Board-level visibility into strategic KPIs accelerates confident investment decisions",
        ],
        "money_out": [
            "Eliminate cost of misaligned strategy decisions made on stale or incomplete data",
            "Reduce executive reporting prep time - automated dashboards vs. manual deck building",
        ],
    },

    "unify_analytics": {
        "label": "Unify Analytics Across Teams/Units",
        "keywords": [
            "unified analytics", "single source of truth", "consistent metrics",
            "cross-functional analytics", "enterprise-wide BI", "governed analytics",
            "centralized data", "break data silos", "shared Liveboards", "federated analytics",
        ],
        "pain_points": [
            "different teams reporting different numbers",
            "data silos across business units",
            "inconsistent KPI definitions",
            "no shared dashboards across departments",
            "finance and sales using different data",
            "lack of governed metrics",
            "conflicting reports creating mistrust in data",
        ],
        "money_in": [
            "One source of truth for revenue metrics removes friction from cross-functional decisions",
            "Unified data accelerates M&A integration and org-wide strategic alignment",
        ],
        "money_out": [
            "Eliminate cost of reconciling conflicting reports across business units",
            "Reduce data governance overhead - governed metrics managed centrally, not per-team",
        ],
    },

}


# ---------------------------------------------------------------------------
# Text extraction helper — safely pulls text from stringified JSON structures
# ---------------------------------------------------------------------------

def extract_text(raw) -> str:
    """
    Safely extract readable text from a value that may be a string,
    list of dicts, or stringified Python/JSON structure.

    Use this before passing subagent JSON fields to match_drivers():
        signal = extract_text(web_research_json.get("pain_points", []))
    """
    if raw is None:
        return ""
    if isinstance(raw, str):
        # Try to parse as JSON first
        try:
            parsed = json.loads(raw)
            return extract_text(parsed)
        except Exception:
            pass
        # Try to parse as Python literal (stringified dicts use single quotes)
        try:
            import ast
            parsed = ast.literal_eval(raw)
            return extract_text(parsed)
        except Exception:
            pass
        return raw
    if isinstance(raw, list):
        return " ".join(extract_text(item) for item in raw)
    if isinstance(raw, dict):
        # Extract only string values — skip source/url metadata keys
        skip_keys = {"source", "source_type", "url", "source_url", "retrieved_date"}
        return " ".join(
            str(v) for k, v in raw.items()
            if isinstance(v, str) and k not in skip_keys
        )
    return str(raw)


# ---------------------------------------------------------------------------
# Public accessors
# ---------------------------------------------------------------------------

def get_drivers(key: str) -> dict | None:
    """
    Return a single driver dict by key.
    Returns None if key not found.

    Example:
        driver = get_drivers("modernize_legacy_bi")
        print(driver["label"])
        print(driver["money_in"])
    """
    return VALUE_DRIVERS.get(key)


def get_money_signals(key: str) -> dict:
    """
    Return money_in and money_out bullets for a driver key.
    Returns empty lists if key not found.

    Use this when injecting financial hooks into Talking Points and emails:
        signals = get_money_signals("enable_self_service")
        hook = signals["money_in"][0]
    """
    driver = VALUE_DRIVERS.get(key)
    if not driver:
        return {"money_in": [], "money_out": []}
    return {
        "money_in":  driver.get("money_in", []),
        "money_out": driver.get("money_out", []),
    }


def match_drivers(signal_text: str, top_n: int = 3, min_score: int = 2) -> dict:
    """
    Auto-match value drivers from free-text signals.

    Scoring:
        Exact keyword match  → 3 points
        Pain point phrase    → 1 point (requires 2+ content words matching)

    Parameters
    ----------
    signal_text : Free text from web research, job postings, competitor intel.
                  Pass through extract_text() first if source is a list of dicts.
    top_n       : Maximum number of drivers to return (default 3)
    min_score   : Minimum score threshold to include a driver (default 2)

    Returns
    -------
    dict with keys:
        status   : "ok" | "no_match"
        matched  : list of {key, label, match_score, evidence}
        message  : diagnostic string

    Example:
        result = match_drivers("they use Tableau, analysts are overwhelmed")
        if result["status"] == "ok":
            for m in result["matched"]:
                print(m["label"], m["evidence"])
        else:
            # Fall back to manual selection
            print(list_drivers())
    """
    signal_lower = signal_text.lower()
    scores: dict[str, int]       = {}
    evidence: dict[str, list]    = {}

    for key, driver in VALUE_DRIVERS.items():
        score = 0
        hits  = []

        # Keyword exact match — 3 points each
        for kw in driver["keywords"]:
            if kw.lower() in signal_lower:
                hits.append(kw)
                score += 3

        # Pain point phrase match — 1 point each
        # Requires at least 2 content words (len > 5) to match
        for pp in driver["pain_points"]:
            pp_words = [w for w in pp.lower().split() if len(w) > 5]
            match_count = sum(1 for w in pp_words if w in signal_lower)
            if match_count >= 2:
                hits.append(f"pain: {pp}")
                score += 1

        if score >= min_score:
            scores[key]   = score
            evidence[key] = hits[:3]

    sorted_keys = sorted(scores, key=lambda k: scores[k], reverse=True)[:top_n]

    if not sorted_keys:
        return {
            "status":  "no_match",
            "matched": [],
            "message": (
                "No drivers matched minimum score threshold. "
                "Use list_drivers() to select manually."
            ),
        }

    return {
        "status": "ok",
        "matched": [
            {
                "key":         k,
                "label":       VALUE_DRIVERS[k]["label"],
                "match_score": scores[k],
                "evidence":    evidence[k],
            }
            for k in sorted_keys
        ],
        "message": f"{len(sorted_keys)} driver(s) matched.",
    }


def list_drivers() -> list:
    """
    Return all driver keys and labels as a list of dicts.
    Useful for manual selection when match_drivers() returns no_match.

    Returns:
        [{"key": "modernize_legacy_bi", "label": "Modernize Legacy BI Stack"}, ...]
    """
    return [
        {"key": k, "label": v["label"]}
        for k, v in VALUE_DRIVERS.items()
    ]


# ---------------------------------------------------------------------------
# Self-test
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print("=== value_drivers.py self-test ===\n")

    # 1. List all drivers
    drivers = list_drivers()
    print(f"Drivers loaded ({len(drivers)}):")
    for d in drivers:
        print(f"  {d['key']}: {d['label']}")
    print()

    # 2. Test get_drivers
    d = get_drivers("modernize_legacy_bi")
    assert d is not None, "get_drivers failed"
    assert "money_in" in d, "money_in missing"
    print("✅ get_drivers OK")

    # 3. Test get_money_signals
    signals = get_money_signals("enable_self_service")
    assert signals["money_in"], "money_in empty"
    assert signals["money_out"], "money_out empty"
    print("✅ get_money_signals OK")

    # 4. Test extract_text
    raw_list = [
        {"text": "analyst backlog is growing", "source": "https://example.com", "source_type": "web"},
        {"text": "they use Tableau for reporting", "source": "job posting", "source_type": "job_posting"},
    ]
    extracted = extract_text(raw_list)
    assert "analyst backlog" in extracted, "extract_text failed on list of dicts"
    assert "https://example.com" not in extracted, "extract_text should skip source URLs"
    print("✅ extract_text OK")

    # 5. Test match_drivers
    result = match_drivers(
        "they use Tableau, analysts overwhelmed with report requests, "
        "low BI adoption, want to migrate from legacy BI"
    )
    assert result["status"] == "ok", f"match_drivers returned: {result}"
    print(f"✅ match_drivers OK — matched: {[m['label'] for m in result['matched']]}")

    # 6. Test no-match case
    result_empty = match_drivers("nothing relevant here at all xyz123")
    assert result_empty["status"] == "no_match", "Expected no_match"
    print("✅ no_match case OK")

    # 7. Test two-pass pattern
    pass1 = match_drivers(extract_text(raw_list))
    pass2 = match_drivers(
        extract_text(raw_list) + " Tableau migration cloud BI modernization"
    )
    final = pass2["matched"] if pass2["status"] == "ok" else pass1["matched"]
    print(f"✅ two-pass pattern OK — final drivers: {[m['label'] for m in final]}")

    print("\nSelf-test complete.")
