"""
bootstrap.py
File-writer for PG workflow helper modules.

Writes helper files to /sandbox/ from fetched source strings.
Includes markdown escape sanitizer for web_fetch content artifacts.
Includes re_bootstrap() for mid-session recovery when platform clears files.

Usage:
    from bootstrap import bootstrap, re_bootstrap, warm_account_cache

    # Initial boot:
    results = bootstrap(
        fallback_src=..., tmpl_src=..., vd_src=...,
        report_builder_src=..., territory_xls_src=..., parallel_src=...
    )

    # Mid-session recovery (if platform clears /sandbox/ files):
    re_bootstrap()  # re-fetches and rewrites all files from GitHub
"""

from pathlib import Path

MIN_BYTES = 500
SANDBOX   = Path("/sandbox")

# GitHub raw URLs — used by re_bootstrap() for mid-session recovery
_GITHUB_BASE = "https://raw.githubusercontent.com/danielschutzman-stack/voltron/main"
_MODULE_URLS = {
    "ts_fallback_map":    f"{_GITHUB_BASE}/ts_fallback_map.py",
    "subagent_templates": f"{_GITHUB_BASE}/subagent_templates.py",
    "value_drivers":      f"{_GITHUB_BASE}/value_drivers.py",
    "pg_report_builder":  f"{_GITHUB_BASE}/pg_report_builder.py",
    "territory_xls":      f"{_GITHUB_BASE}/territory_xls.py",
    "ts_parallel":        f"{_GITHUB_BASE}/ts_parallel.py",
}


# ---------------------------------------------------------------------------
# Markdown escape sanitizer
# Strips artifacts from web_fetch content rendering
# ---------------------------------------------------------------------------

def _sanitize(source: str) -> str:
    """
    Strip markdown escape sequences from fetched source code.
    web_fetch sometimes returns \\_ instead of _, \\[ instead of [, etc.
    """
    if not source:
        return source
    for escaped, clean in [
        ("\\_", "_"), ("\\[", "["), ("\\]", "]"),
        ("\\#", "#"), ("\\*", "*"), ("\\`", "`"),
        ("\\-", "-"), ("\\.", "."), ("\\(", "("),
        ("\\)", ")"), ("\\{", "{"), ("\\}", "}"),
        ("\\|", "|"), ("\\>", ">"), ("\\!", "!"),
    ]:
        source = source.replace(escaped, clean)
    return source


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _should_skip(path: Path) -> bool:
    try:
        return path.exists() and path.stat().st_size >= MIN_BYTES
    except Exception:
        return False


def _write(path: Path, content: str) -> str:
    path.write_text(_sanitize(content), encoding="utf-8")
    return "written"


def _files_present() -> bool:
    """Return True if all required helper files exist and are valid."""
    required = [
        SANDBOX / "ts_fallback_map.py",
        SANDBOX / "subagent_templates.py",
        SANDBOX / "value_drivers.py",
        SANDBOX / "pg_report_builder.py",
        SANDBOX / "territory_xls.py",
        SANDBOX / "ts_parallel.py",
    ]
    return all(
        p.exists() and p.stat().st_size >= MIN_BYTES
        for p in required
    )


# ---------------------------------------------------------------------------
# Primary bootstrap — called at session start with pre-fetched sources
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
    Write all required sandbox helper files from pre-fetched source strings.

    Returns dict mapping filepath → status string:
        "written"  — file newly written
        "skipped"  — file already exists and is valid
        "error: …" — write failed or source too small
    """
    SANDBOX.mkdir(parents=True, exist_ok=True)

    sources = {
        SANDBOX / "ts_fallback_map.py":    fallback_src,
        SANDBOX / "subagent_templates.py": tmpl_src,
        SANDBOX / "value_drivers.py":      vd_src,
        SANDBOX / "pg_report_builder.py":  report_builder_src,
        SANDBOX / "territory_xls.py":      territory_xls_src,
    }

    if parallel_src and len(_sanitize(parallel_src).strip()) >= MIN_BYTES:
        sources[SANDBOX / "ts_parallel.py"] = parallel_src

    results = {}
    for path, src in sources.items():
        path_str = str(path)
        src      = _sanitize(src) if src else src
        if not src or len(src.strip()) < MIN_BYTES:
            results[path_str] = "error: source too small or empty"
            continue
        try:
            if _should_skip(path):
                results[path_str] = "skipped"
            else:
                results[path_str] = _write(path, src)
        except Exception as exc:
            results[path_str] = f"error: {exc}"

    return results


# ---------------------------------------------------------------------------
# Mid-session recovery — re-fetches and rewrites all files from GitHub
# ---------------------------------------------------------------------------

def re_bootstrap() -> dict:
    """
    Re-fetch and rewrite all helper files from GitHub.

    Call this when the platform clears /sandbox/ files mid-session:

        from bootstrap import re_bootstrap, _files_present
        if not _files_present():
            print("⚠️ Sandbox files cleared — re-bootstrapping...")
            results = re_bootstrap()
            print(results)

    Returns dict mapping module_name → status string.
    """
    try:
        import urllib.request
    except ImportError:
        return {"error": "urllib not available — cannot re-fetch files"}

    SANDBOX.mkdir(parents=True, exist_ok=True)
    results = {}

    for module_name, url in _MODULE_URLS.items():
        path = SANDBOX / f"{module_name}.py"
        try:
            with urllib.request.urlopen(url, timeout=30) as resp:
                src = resp.read().decode("utf-8")
            src = _sanitize(src)
            if len(src.strip()) < MIN_BYTES:
                results[module_name] = "error: fetched source too small"
                continue
            path.write_text(src, encoding="utf-8")
            results[module_name] = "re-written"
        except Exception as exc:
            results[module_name] = f"error: {exc}"

    return results


# ---------------------------------------------------------------------------
# Account cache warm-up
# ---------------------------------------------------------------------------

def warm_account_cache(owner_name: str) -> dict:
    """
    Pre-warm the account cache. Call AFTER "✅ Ready!" — never before.
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


if __name__ == "__main__":
    print("bootstrap.py loaded OK.")
    print(f"Files present: {_files_present()}")
