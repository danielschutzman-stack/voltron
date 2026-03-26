"""
ts_intent_map.py
INTENT_MAP and WORKSHEETS for ThoughtSpot query runner.
Fetched separately and combined with ts_runner.py by bootstrap().
"""

WORKSHEETS = {
    "revops": "9cfb299b-7378-48cb-ae20-a0bc5a82b223",
    "campaigns": "b2d24878-0150-4c1e-a74c-bfc46cc4a682",
    "studio": "dbef58b8-a3ea-485e-8818-c1bfc35bf207",
    "engage": "6d10b8a9-d4ca-451c-a102-a745329db735",
}

INTENT_MAP = {
    "account_ownership": (
        "revops",
        "[Account Name] [Account Owner Name] [Account Owner Team] [Account Segment] [Account Status] [Account Owner Name] = '{owner_name}' [Account Status] = 'Prospect'",
        "studio",
        "[Account Name] [Account Owner Name] [Account Owner Team] [Account Segment] [Account Owner Name] = '{owner_name}' [Account Status] = 'Prospect'"
    ),
    "territory_overview": (
        "revops",
        "[Account Name] [Account Segment] [Account TSA ICP Score] [Account TSE ICP Score] [Account Last Activity Date] [Days from Account last touch] [Account Snapshot 6S Reach Score] [Account Kernel Main Vertical] [Account Owner Name] = '{owner_name}' [Account Status] = 'Prospect'",
        "studio",
        "[Account Name] [Account Segment] [Account Rev Score - TSA] [Account Rev Score - TSE] [Account Clearbit Industry Group] [Account Owner Name] = '{owner_name}' [Account Status] = 'Prospect'"
    ),
    "6sense_intent": (
        "revops",
        "[Account Name] [Account Snapshot 6S Reach Score] [Person 6S Intent Score] [Account Owner Name] = '{owner_name}' [Account Status] = 'Prospect'",
        "revops",
        "[Account Name] [Account Snapshot 6S Reach Score] [Account Owner Name] = '{owner_name}' [Account Status] = 'Prospect'"
    ),
    "last_activity": (
        "revops",
        "[Account Name] [Account Last Activity Date] [Days from Account last touch] [Account last touch grouped] [Account Owner Name] = '{owner_name}' [Account Status] = 'Prospect'",
        "revops",
        "[Account Name] [Account Last Activity Date] [Account Owner Name] = '{owner_name}' [Account Status] = 'Prospect'"
    ),
    "icp_scores": (
        "revops",
        "[Account Name] [Account TSA ICP Score] [Account TSA ICP Grade] [Account TSE ICP Score] [Account Owner Name] = '{owner_name}' [Account Status] = 'Prospect'",
        "studio",
        "[Account Name] [Account Rev Score - TSA] [Account Rev Score - TSE] [Account Owner Name] = '{owner_name}' [Account Status] = 'Prospect'"
    ),
    "account_vertical": (
        "revops",
        "[Account Name] [Account Kernel Main Vertical] [Account Kernel Sub Vertical] [Account Clearbit Industry] [Account Owner Name] = '{owner_name}' [Account Status] = 'Prospect'",
        "studio",
        "[Account Name] [Account Clearbit Industry Group] [Account Owner Name] = '{owner_name}' [Account Status] = 'Prospect'"
    ),
    "deal_stage": (
        "revops",
        "[Account Name] [Opportunity Name] [Opportunity Stage Maximum Name] [Opportunity Pipeline Qualified Flag] [Opportunity Owner Name] [Opportunity Created Date] [Opportunity Last Activity Date] account name = '{account_name}'",
        "revops",
        "[Account Name] [Opportunity Name] [Opportunity Stage Maximum Name] [Opportunity Owner Name] account name = '{account_name}'"
    ),
    "deal_funnel_timing": (
        "revops",
        "[Account Name] [Opportunity Name] [f Opportunity S1 Duration] [f Opportunity S2 Duration] [f Opportunity S3 Duration] [Opportunity Stage Maximum Name] account name = '{account_name}'",
        "revops",
        "[Account Name] [Opportunity Name] [Opportunity Current Stage Duration] [Opportunity Stage Maximum Name] account name = '{account_name}'"
    ),
    "meddpicc_flags": (
        "revops",
        "[Account Name] [Opportunity Name] [Opportunity Gong Champion Validated] [Opportunity Gong Economic Buyer Validated] [Opportunity Gong Identify Pain Validated] account name = '{account_name}'",
        "revops",
        "[Account Name] [Opportunity Name] [Opportunity Gong Champion Validated] account name = '{account_name}'"
    ),
    "meddpicc_detail": (
        "revops",
        "[Account Name] [Opportunity Name] [Opportunity Gong Champion] [Opportunity Gong Economic Buyer] [Opportunity Gong Identify Pain] account name = '{account_name}'",
        "revops",
        "[Account Name] [Opportunity Name] [Opportunity Gong Champion] account name = '{account_name}'"
    ),
    "activity_history": (
        "revops",
        "[Account Name] [Activity Type] [Activity Subject] [Activity Time] [Activity Owner Name] account name = '{account_name}'",
        "revops",
        "[Account Name] [Activity Type] [Activity Subject] [Activity Time] account name = '{account_name}'"
    ),
    "sfdc_stakeholder": (
        "studio",
        "[Account Name] [Executive Business Sponsor [For Calculation]] [Opportunity CS Name] [Opportunity Owner Name] [Opportunity Name] [Opportunity Status] account name = '{account_name}'",
        "revops",
        "[Account Name] [Opportunity Owner Name] [Opportunity Name] [Opportunity Stage Maximum Name] account name = '{account_name}'"
    ),
}

# ─────────────────────────────────────────────────────────────
# ACCOUNT PRE-LOAD CACHE  (added for AE session warm-up)
# ─────────────────────────────────────────────────────────────
import json as _json
import os as _os
import time as _time

_CACHE_TTL_SECONDS = 1800  # 30 minutes


def _cache_path(owner_name: str) -> str:
    slug = owner_name.lower().replace(" ", "_").replace(".", "")
    return f"/sandbox/account_cache_{slug}.json"


def warm_account_cache(owner_name: str) -> dict:
    """
    Fire the account_ownership query and write the result to a
    30-minute TTL JSON cache file. Called during bootstrap so
    the result is ready before the user reaches the territory flow.
    """
    path = _cache_path(owner_name)

    # Don't re-query if a fresh cache already exists
    if _os.path.exists(path):
        try:
            with open(path) as f:
                cached = _json.load(f)
            age = _time.time() - cached.get("_cached_at", 0)
            if age < _CACHE_TTL_SECONDS:
                return cached  # still fresh — skip query
        except Exception:
            pass  # corrupt cache → fall through and re-fetch

    result = run_with_fallback("account_ownership", owner_name=owner_name)

    if result.get("status") == "token_expired":
        return result  # surface expiry but don't crash bootstrap

    # Stamp and persist
    result["_cached_at"] = _time.time()
    result["_owner_name"] = owner_name
    try:
        with open(path, "w") as f:
            _json.dump(result, f)
    except Exception as e:
        result["_cache_write_error"] = str(e)

    return result


def read_account_cache(owner_name: str) -> dict | None:
    """
    Return cached account_ownership result if < 30 min old.
    Returns None if missing, expired, or corrupt.
    """
    path = _cache_path(owner_name)
    if not _os.path.exists(path):
        return None
    try:
        with open(path) as f:
            cached = _json.load(f)
        age = _time.time() - cached.get("_cached_at", 0)
        if age < _CACHE_TTL_SECONDS:
            return cached
    except Exception:
        pass
    return None
