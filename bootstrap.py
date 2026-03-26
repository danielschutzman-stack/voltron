"""
bootstrap.py
In-memory module loader for PTC sandbox environments.

PTC sandbox blocks os module file writes and pathlib mutations.
This version loads all helper modules directly into Python's
module registry without touching the filesystem.

Usage:
    from bootstrap import bootstrap, warm_account_cache

    results = bootstrap(
        fallback_src=<ts_fallback_map.py content>,
        tmpl_src=<subagent_templates.py content>,
        vd_src=<value_drivers.py content>,
        report_builder_src=<pg_report_builder.py content>,
        territory_xls_src=<territory_xls.py content>,
        parallel_src=<ts_parallel.py content>,
    )

    # After posting "✅ Ready!", call warm_account_cache() — never before:
    from bootstrap import warm_account_cache
    warm_account_cache(owner_name)
"""

import importlib
import importlib.util
import types


# ---------------------------------------------------------------------------
# Internal: load a source string as a named module
# ---------------------------------------------------------------------------

def _load_module(module_name: str, source: str) -> tuple:
    """
    Compile and execute a source string as a named Python module.
    Registers it in sys.modules so it can be imported normally afterward.

    Returns (module, None) on success, (None, error_message) on failure.
    """
    try:
        import sys
        module      = types.ModuleType(module_name)
        module.__name__ = module_name
        code        = compile(source, f"<{module_name}>", "exec")
        exec(code, module.__dict__)
        sys.modules[module_name] = module
        return module, None
    except Exception as exc:
        return None, str(exc)


# ---------------------------------------------------------------------------
# Primary bootstrap entry point
# ---------------------------------------------------------------------------

def bootstrap(
    fallback_src:       str,
    tmpl_src:           str,
    vd_src:             str,
    report_builder_src: str,
    territory_xls_src:  str,
    parallel_src:       str = "",
) -> dict:
    """
    Load all required helper modules into memory.

    No file writes. No filesystem access. Modules are registered in
    sys.modules and can be imported normally after bootstrap() runs:

        from ts_fallback_map import run_with_fallback
        from value_drivers import match_drivers
        from subagent_templates import render
        from pg_report_builder import build_pg_report, build_onepager
        from territory_xls import TerritoryWorkbook
        from ts_parallel import run_ts_batch

    Parameters
    ----------
    fallback_src        : Full source of ts_fallback_map.py
    tmpl_src            : Full source of subagent_templates.py
    vd_src              : Full source of value_drivers.py
    report_builder_src  : Full source of pg_report_builder.py
    territory_xls_src   : Full source of territory_xls.py
    parallel_src        : Full source of ts_parallel.py (optional)

    Returns
    -------
    dict mapping module_name → status string:
        "loaded"                   — module loaded into memory successfully
        "skipped (already loaded)" — module already in sys.modules
        "error: source too small"  — source content failed minimum size check
        "error: <message>"         — load failed
    """
    import sys
    MIN_BYTES = 500

    sources = {
        "ts_fallback_map":    fallback_src,
        "subagent_templates": tmpl_src,
        "value_drivers":      vd_src,
        "pg_report_builder":  report_builder_src,
        "territory_xls":      territory_xls_src,
    }

    if parallel_src and len(parallel_src.strip()) >= MIN_BYTES:
        sources["ts_parallel"] = parallel_src

    results = {}

    for module_name, src in sources.items():

        # Validate source
        if not src or len(src.strip()) < MIN_BYTES:
            results[module_name] = "error: source too small or empty"
            continue

        # Check if already loaded
        if module_name in sys.modules:
            results[module_name] = "skipped (already loaded)"
            continue

        # Load into memory
        module, err = _load_module(module_name, src)
        if err:
            results[module_name] = f"error: {err}"
        else:
            results[module_name] = "loaded"

    return results


# ---------------------------------------------------------------------------
# Account cache warm-up — call AFTER "✅ Ready!", never inside bootstrap()
# ---------------------------------------------------------------------------

def warm_account_cache(owner_name: str) -> dict:
    """
    Pre-warm the account cache for the current user.

    Delegates to ts_fallback_map.warm_account_cache().
    Call this AFTER posting "✅ Ready!" — never before.

    NOTE: In PTC sandbox, cache is held in memory only for this session.
    It cannot be persisted to disk between sessions.
    """
    if not owner_name or not owner_name.strip():
        return {"status": "skipped", "message": "No owner_name provided."}

    try:
        from ts_fallback_map import warm_account_cache as _warm
        cache_result = _warm(owner_name.strip())
        status       = cache_result.get("status", "unknown")

        return {
            "status": status,
            "message": (
                f"Account cache warmed for '{owner_name}'."
                if status == "ok"
                else f"Cache warm returned status '{status}' for '{owner_name}'."
            ),
        }
    except Exception as exc:
        return {"status": "error", "message": str(exc)}


# ---------------------------------------------------------------------------
# Self-test
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print(
        "bootstrap.py loaded OK (in-memory mode).\n"
        "Call bootstrap(fallback_src, tmpl_src, vd_src, "
        "report_builder_src, territory_xls_src) to initialize."
    )
