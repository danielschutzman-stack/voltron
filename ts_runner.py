"""
ts_runner.py
_ts_query() and run_with_fallback() for ThoughtSpot.
Combined with ts_intent_map.py by bootstrap() into /sandbox/ts_fallback_map.py.
"""

import os
import requests


def _ts_query(query_string, worksheet_key, timeout=20):
    token = os.environ.get("THOUGHTSPOT_TOKEN", "")
    base_url = os.environ.get("THOUGHTSPOT_URL", "").rstrip("/")
    if not token or not base_url:
        return {"_error": "missing_env", "_message": "THOUGHTSPOT_TOKEN or THOUGHTSPOT_URL not set."}
    worksheet_id = WORKSHEETS.get(worksheet_key)
    if not worksheet_id:
        return {"_error": "bad_worksheet", "_message": f"Unknown worksheet key: {worksheet_key}"}
    url = f"{base_url}/api/rest/2.0/searchdata"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Accept": "application/json"
    }
    payload = {
        "query_string": query_string,
        "logical_table_identifier": worksheet_id,
        "data_format": "COMPACT",
        "record_offset": 0,
        "record_size": 1000
    }
    try:
        resp = requests.post(url, headers=headers, json=payload, timeout=timeout)
    except requests.exceptions.Timeout:
        return {"_error": "timeout", "_message": f"Query timed out after {timeout}s."}
    except Exception as e:
        return {"_error": "request_exception", "_message": str(e)}
    if resp.status_code == 401:
        return {"_error": "token_expired", "_message": "ThoughtSpot token expired (401)."}
    if resp.status_code == 403:
        return {"_error": "token_expired", "_message": "ThoughtSpot token forbidden (403)."}
    if resp.status_code != 200:
        return {"_error": "http_error", "_message": f"HTTP {resp.status_code}: {resp.text[:300]}"}
    try:
        data = resp.json()
    except Exception:
        return {"_error": "parse_error", "_message": "Could not parse JSON response."}
    return data


def run_with_fallback(intent, **variables):
    base_result = {
        "status": "error",
        "column_names": [],
        "data_rows": [],
        "used_fallback": False,
        "message": "",
        "intent": intent,
        "query_used": ""
    }
    if intent not in INTENT_MAP:
        base_result["message"] = f"Unknown intent: {intent!r}. Valid intents: {list(INTENT_MAP.keys())}"
        return base_result
    primary_ws, primary_tpl, fallback_ws, fallback_tpl = INTENT_MAP[intent]

    def _attempt(worksheet_key, query_template, used_fallback):
        try:
            query = query_template.format(**variables)
        except KeyError as e:
            return None, f"Missing variable for query template: {e}"
        raw = _ts_query(query, worksheet_key)
        if raw.get("_error") in ("token_expired",):
            return "token_expired", raw.get("_message", "Token expired.")
        if "_error" in raw:
            return None, raw.get("_message", "Unknown error.")
        try:
            # Handle both top-level and contents-wrapped response shapes
            if "contents" in raw:
                payload = raw["contents"][0] if raw["contents"] else {}
            else:
                payload = raw
            col_names = payload.get("column_names") or ([c["column_name"] for c in payload.get("columns", [])])
            rows = payload.get("data_rows") or payload.get("data", {}).get("data_rows", [])
        except Exception as e:
            return None, f"Could not parse response structure: {e}"
        if not rows:
            return "empty", col_names, [], query, used_fallback
        return "ok", col_names, rows, query, used_fallback

    result = _attempt(primary_ws, primary_tpl, False)
    if result[0] == "token_expired":
        base_result["status"] = "token_expired"
        base_result["message"] = result[1]
        return base_result
    if result[0] == "ok":
        _, col_names, rows, query, uf = result
        base_result.update({"status": "ok", "column_names": col_names, "data_rows": rows, "query_used": query, "used_fallback": uf})
        return base_result
    # Try fallback
    result2 = _attempt(fallback_ws, fallback_tpl, True)
    if result2[0] == "token_expired":
        base_result["status"] = "token_expired"
        base_result["message"] = result2[1]
        return base_result
    if result2[0] == "ok":
        _, col_names, rows, query, uf = result2
        base_result.update({"status": "ok", "column_names": col_names, "data_rows": rows, "query_used": query, "used_fallback": uf})
        return base_result
    # Both empty or error
    if result[0] == "empty" or result2[0] == "empty":
        base_result["status"] = "empty"
        base_result["message"] = "No data returned from primary or fallback query."
        if result[0] == "empty":
            base_result["column_names"] = result[1]
        return base_result
    base_result["message"] = f"Primary: {result[1] if result[0] is None else ''}  Fallback: {result2[1] if result2[0] is None else ''}"
    return base_result
