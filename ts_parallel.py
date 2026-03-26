"""
ts_parallel.py
Parallel ThoughtSpot query runner built on threading.
Wraps run_with_fallback() to fire multiple intents concurrently.

Usage:
    from ts_parallel import run_ts_batch, run_ts_batch_for_accounts,
                           check_token_expiry, TERRITORY_FILTER_INTENTS

    # Multiple intents for one account:
    results = run_ts_batch([
        ("deal_stage",         {"account_name": "Acme Corp"}),
        ("meddpicc_flags",     {"account_name": "Acme Corp"}),
        ("meddpicc_detail",    {"account_name": "Acme Corp"}),
        ("activity_history",   {"account_name": "Acme Corp"}),
        ("sfdc_stakeholder",   {"account_name": "Acme Corp"}),
        ("deal_funnel_timing", {"account_name": "Acme Corp"}),
    ], max_workers=6, timeout=25)

    if check_token_expiry(results):
        # Surface ⚠️ token expiry message immediately
        raise SystemExit("Token expired")

    deal = results["deal_stage"]
    if deal["status"] == "ok":
        rows = deal["data_rows"]

    # Same intent across multiple accounts:
    sfdc = run_ts_batch_for_accounts(
        "sfdc_stakeholder",
        ["Acme Corp", "Dell", "Sysco"],
        variable_key="account_name",
    )

    # Territory filter queries (all 4 at once):
    filters = run_ts_batch(
        [(intent, {"owner_name": "Jane Smith"})
         for intent in TERRITORY_FILTER_INTENTS],
        max_workers=4,
        timeout=25,
    )
"""

import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone

# ---------------------------------------------------------------------------
# Lazy import guard — ts_fallback_map.py must be present in /sandbox
# ---------------------------------------------------------------------------

try:
    from ts_fallback_map import run_with_fallback
except ImportError:
    # Stub matching real signature — safe for unit-test contexts
    def run_with_fallback(intent: str, timeout: int = 20, **variables) -> dict:  # type: ignore
        raise ImportError(
            "ts_fallback_map.py not found in /sandbox. "
            "Cannot run ThoughtSpot queries."
        )


# ---------------------------------------------------------------------------
# Convenience constant — standard territory filter batch
# ---------------------------------------------------------------------------

TERRITORY_FILTER_INTENTS = [
    "6sense_intent",
    "last_activity",
    "icp_scores",
    "account_vertical",
]


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _now_str() -> str:
    """Return a compact UTC timestamp string for logging."""
    return datetime.now(timezone.utc).strftime("%H:%M:%S.%f")[:-3]


def _run_single(
    intent:    str,
    variables: dict,
    key:       str,
    timeout:   int,
) -> tuple:
    """
    Execute a single run_with_fallback() call and return (key, result_dict).
    """
    print(
        f"[ts_parallel] {_now_str()} | START  | "
        f"intent={intent!r}  key={key!r}"
    )
    try:
        result = run_with_fallback(intent, timeout=timeout, **variables)
        print(
            f"[ts_parallel] {_now_str()} | DONE   | "
            f"key={key!r}  status={result.get('status', 'unknown')}"
        )
        return key, result
    except Exception as exc:
        err_msg = str(exc)
        print(
            f"[ts_parallel] {_now_str()} | ERROR  | "
            f"key={key!r}  error={err_msg!r}"
        )
        return key, {
            "status":       "error",
            "message":      err_msg,
            "column_names": [],
            "data_rows":    [],
        }


def _collect_futures(
    future_to_key: dict,
    results:       dict,
    timeout:       int,
) -> dict:
    """
    Collect results from futures using a wall-clock deadline.
    """
    deadline = time.monotonic() + timeout + 5

    for future in as_completed(future_to_key):
        remaining = deadline - time.monotonic()
        fkey      = future_to_key[future]

        if remaining <= 0:
            print(
                f"[ts_parallel] {_now_str()} | TIMEOUT | "
                f"key={fkey!r} — wall-clock deadline exceeded"
            )
            results[fkey] = {
                "status":       "error",
                "message":      "Wall-clock deadline exceeded",
                "column_names": [],
                "data_rows":    [],
            }
            continue

        try:
            returned_key, result_dict = future.result(timeout=remaining)
            results[returned_key] = result_dict
        except TimeoutError:
            print(
                f"[ts_parallel] {_now_str()} | TIMEOUT | "
                f"key={fkey!r}  timeout={timeout}s"
            )
            results[fkey] = {
                "status":       "error",
                "message":      f"Query timed out after {timeout}s",
                "column_names": [],
                "data_rows":    [],
            }
        except Exception as exc:
            print(
                f"[ts_parallel] {_now_str()} | FATAL   | "
                f"key={fkey!r}  error={exc!r}"
            )
            results[fkey] = {
                "status":       "error",
                "message":      str(exc),
                "column_names": [],
                "data_rows":    [],
            }

    return results


# ---------------------------------------------------------------------------
# Token expiry check
# ---------------------------------------------------------------------------

def check_token_expiry(results: dict) -> bool:
    """
    Return True if any result in the batch indicates token expiry.

    Use immediately after run_ts_batch() or run_ts_batch_for_accounts():

        results = run_ts_batch([...])
        if check_token_expiry(results):
            # Surface ⚠️ token expiry message per Error Handling rules
            # Do NOT continue TS queries — halt and wait for user refresh
    """
    return any(
        v.get("status") == "token_expired"
        for k, v in results.items()
        if k != "_token_expired" and isinstance(v, dict)
    )


# ---------------------------------------------------------------------------
# Primary public helper — multiple intents, one or more accounts
# ---------------------------------------------------------------------------

def run_ts_batch(
    intents_and_vars: list,
    max_workers:      int = 6,
    timeout:          int = 25,
) -> dict:
    """
    Fire multiple ThoughtSpot intents concurrently and return all results.

    Parameters
    ----------
    intents_and_vars : list of (intent_str, variables_dict) tuples
    max_workers      : Maximum number of concurrent threads (default 6)
    timeout          : Per-query timeout in seconds (default 25)

    Returns
    -------
    dict keyed by intent name. Duplicate intents get _2, _3 suffixes.
    Always includes "_token_expired": True if any query expired.
    """
    if not intents_and_vars:
        return {}

    # Build de-duplicated keys
    key_counts:  dict = {}
    keyed_tasks: list = []

    for intent, variables in intents_and_vars:
        if intent not in key_counts:
            key_counts[intent] = 1
            key = intent
        else:
            key_counts[intent] += 1
            key = f"{intent}_{key_counts[intent]}"
        keyed_tasks.append((key, intent, variables))

    n       = len(keyed_tasks)
    workers = min(max_workers, n)

    print(
        f"[ts_parallel] {_now_str()} | BATCH  | "
        f"{n} quer{'y' if n == 1 else 'ies'}  "
        f"max_workers={workers}  timeout={timeout}s"
    )
    batch_start = time.monotonic()
    results: dict = {}

    with ThreadPoolExecutor(max_workers=workers) as executor:
        future_to_key = {
            executor.submit(_run_single, intent, variables, key, timeout): key
            for key, intent, variables in keyed_tasks
        }
        _collect_futures(future_to_key, results, timeout)

    # Flag token expiry prominently
    if check_token_expiry(results):
        results["_token_expired"] = True
        expired_keys = [
            k for k, v in results.items()
            if isinstance(v, dict) and v.get("status") == "token_expired"
        ]
        print(
            f"[ts_parallel] {_now_str()} | ⚠️  TOKEN EXPIRED | "
            f"detected in: {expired_keys}"
        )

    elapsed  = time.monotonic() - batch_start
    ok_count = sum(
        1 for k, v in results.items()
        if k != "_token_expired" and isinstance(v, dict)
        and v.get("status") == "ok"
    )
    print(
        f"[ts_parallel] {_now_str()} | FINISH | "
        f"{ok_count}/{n} succeeded  elapsed={elapsed:.2f}s"
    )
    return results


# ---------------------------------------------------------------------------
# Secondary public helper — same intent, multiple accounts or owners
# ---------------------------------------------------------------------------

def run_ts_batch_for_accounts(
    intent:       str,
    values:       list,
    variable_key: str = "account_name",
    max_workers:  int = 5,
    timeout:      int = 25,
) -> dict:
    """
    Fire the same ThoughtSpot intent against multiple values in parallel.

    Parameters
    ----------
    intent       : ThoughtSpot intent name (e.g. "sfdc_stakeholder")
    values       : List of values for the variable
    variable_key : The variable name to use (default "account_name").
                   Use "owner_name" for owner-scoped intents.
    max_workers  : Maximum number of concurrent threads (default 5)
    timeout      : Per-query timeout in seconds (default 25)

    Returns
    -------
    dict keyed by value (account name or owner name).
    Always includes "_token_expired": True if any query expired.
    """
    if not values:
        return {}

    n       = len(values)
    workers = min(max_workers, n)

    print(
        f"[ts_parallel] {_now_str()} | ACCT-BATCH | "
        f"intent={intent!r}  {n} value(s)  "
        f"variable_key={variable_key!r}  "
        f"max_workers={workers}  timeout={timeout}s"
    )
    batch_start = time.monotonic()
    results: dict = {}

    def _run_for_value(value: str) -> tuple:
        print(
            f"[ts_parallel] {_now_str()} | START  | "
            f"intent={intent!r}  {variable_key}={value!r}"
        )
        try:
            result = run_with_fallback(
                intent,
                timeout=timeout,
                **{variable_key: value},
            )
            print(
                f"[ts_parallel] {_now_str()} | DONE   | "
                f"intent={intent!r}  {variable_key}={value!r}  "
                f"status={result.get('status', 'unknown')}"
            )
            return value, result
        except Exception as exc:
            err_msg = str(exc)
            print(
                f"[ts_parallel] {_now_str()} | ERROR  | "
                f"intent={intent!r}  {variable_key}={value!r}  "
                f"error={err_msg!r}"
            )
            return value, {
                "status":       "error",
                "message":      err_msg,
                "column_names": [],
                "data_rows":    [],
            }

    with ThreadPoolExecutor(max_workers=workers) as executor:
        future_to_value = {
            executor.submit(_run_for_value, v): v
            for v in values
        }

        deadline = time.monotonic() + timeout + 5
        for future in as_completed(future_to_value):
            remaining = deadline - time.monotonic()
            val       = future_to_value[future]

            if remaining <= 0:
                print(
                    f"[ts_parallel] {_now_str()} | TIMEOUT | "
                    f"{variable_key}={val!r} — deadline exceeded"
                )
                results[val] = {
                    "status":       "error",
                    "message":      "Wall-clock deadline exceeded",
                    "column_names": [],
                    "data_rows":    [],
                }
                continue

            try:
                returned_val, result_dict = future.result(timeout=remaining)
                results[returned_val] = result_dict
            except TimeoutError:
                results[val] = {
                    "status":       "error",
                    "message":      f"Query timed out after {timeout}s",
                    "column_names": [],
                    "data_rows":    [],
                }
            except Exception as exc:
                results[val] = {
                    "status":       "error",
                    "message":      str(exc),
                    "column_names": [],
                    "data_rows":    [],
                }

    # Flag token expiry
    if check_token_expiry(results):
        results["_token_expired"] = True
        print(
            f"[ts_parallel] {_now_str()} | ⚠️  TOKEN EXPIRED | "
            f"intent={intent!r}"
        )

    elapsed  = time.monotonic() - batch_start
    ok_count = sum(
        1 for k, v in results.items()
        if k != "_token_expired" and isinstance(v, dict)
        and v.get("status") == "ok"
    )
    print(
        f"[ts_parallel] {_now_str()} | FINISH | "
        f"intent={intent!r}  {ok_count}/{n} succeeded  "
        f"elapsed={elapsed:.2f}s"
    )
    return results


# ---------------------------------------------------------------------------
# Self-test
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print("=== ts_parallel.py self-test ===\n")

    print("✅ Module imported OK")

    assert len(TERRITORY_FILTER_INTENTS) == 4
    print(f"✅ TERRITORY_FILTER_INTENTS: {TERRITORY_FILTER_INTENTS}")

    fake_expired = {
        "deal_stage": {"status": "token_expired", "column_names": [], "data_rows": []},
        "activity_history": {"status": "ok", "column_names": [], "data_rows": []},
    }
    assert check_token_expiry(fake_expired) is True
    print("✅ check_token_expiry detects expiry correctly")

    fake_ok = {"deal_stage": {"status": "ok", "column_names": [], "data_rows": []}}
    assert check_token_expiry(fake_ok) is False
    print("✅ check_token_expiry clean on ok results")

    result = run_ts_batch([])
    assert result == {}
    print("✅ run_ts_batch handles empty input")

    result = run_ts_batch_for_accounts("deal_stage", [])
    assert result == {}
    print("✅ run_ts_batch_for_accounts handles empty input")

    print("\nSelf-test complete.")
