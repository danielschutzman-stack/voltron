"""
bootstrap.py
Sandbox file writer for PG workflow helper modules.

Writes helper files to /sandbox/ from fetched source strings.
Includes content-aware skip logic — never skips based on size alone.
Includes markdown escape sanitizer for web_search content artifacts.

NOTE: Does not use sys or __import__ — both blocked by sandbox validator.
NOTE: Does not sanitize \\{ or \\} — breaks Python f-strings in pg_report_builder.

Usage:
    from bootstrap import bootstrap, sanitize, warm_account_cache

    results = bootstrap(
        fallback_src=sanitize(<ts_fallback_map.py content>),
        tmpl_src=sanitize(<subagent_templates.py content>),
        vd_src=sanitize(<value_drivers.py content>),
        report_builder_src=sanitize(<pg_report_builder.py content>),
        territory_xls_src=sanitize(<territory_xls.py content>),
        parallel_src=sanitize(<ts_parallel.py content>),
    )

    from bootstrap import warm_account_cache
    warm_account_cache(owner_name)
"""

from pathlib import Path

MIN_BYTES = 500
SANDBOX   = Path("/sandbox")


# ---------------------------------------------------------------------------
# Sanitizer — strips markdown escape artifacts from web_search content
# ---------------------------------------------------------------------------

def sanitize(source: str) -> str:
    """
    Strip markdown escape sequences introduced by web_search content rendering.

    NOTE: \\{ and \\} are intentionally excluded — replacing them breaks
    Python f-strings (e.g. in pg_report_builder._CSS which uses {{ and }}).
    These characters do not need sanitizing in valid Python source.

    Double-sanitizing is safe — idempotent.
    """
    if not source:
        return source
    replacements = [
        ("\\ ",  " "),   # backslash-space — broken line continuation
        ("\\_",  "_"),
        ("\\[",  "["),
        ("\\]",  "]"),
        ("\\#",  "#"),
        ("\\*",  "*"),
        ("\\`",  "`"),
        ("\\-",  "-"),
        ("\\.",  "."),
        ("\\(",  "("),
        ("\\)",  ")"),
        # ("\\{",  "{"),  ← excluded — breaks Python f-strings
        # ("\\}",  "}"),  ← excluded — breaks Python f-strings
        ("\\|",  "|"),
        ("\\>",  ">"),
        ("\\!",  "!"),
        ("\\~",  "~"),
        ("\\+",  "+"),
        ("\\=",  "="),
        ("\\@",  "@"),
    ]
    for escaped, clean in replacements:
        source = source.replace(escaped, clean)
    return source


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _should_skip(path: Path, new_src: str) -> bool:
    """
    Return True only if the existing file substantively matches
    what we are about to write.

    Never skips based on size alone — placeholder files >= 500 bytes
    would incorrectly pass a size-only check.
    """
    try:
        if not path.exists():
            return False
        existing = path.read_text(encoding="utf-8")
        if len(existing) < MIN_BYTES:
            return False
        if existing[:200].strip() == new_src[:200].strip():
            return True
        return False
    except Exception:
        return False


def _write_text(path: Path, content: str) -> str:
    path.write_text(content, encoding="utf-8")
    return f"written ({len(content)} bytes)"


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
    Sanitize and write all required sandbox helper files.

    Sanitizes all source strings before writing — safe to call with
    raw web_search content that may contain markdown escape artifacts.

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
    dict mapping filepath → status string
    """
    SANDBOX.mkdir(parents=True, exist_ok=True)

    sources = {
        SANDBOX / "ts_fallback_map.py":    sanitize(fallback_src),
        SANDBOX / "subagent_templates.py": sanitize(tmpl_src),
        SANDBOX / "value_drivers.py":      sanitize(vd_src),
        SANDBOX / "pg_report_builder.py":  sanitize(report_builder_src),
        SANDBOX / "territory_xls.py":      sanitize(territory_xls_src),
    }

    if parallel_src and len(sanitize(parallel_src).strip()) >= MIN_BYTES:
        sources[SANDBOX / "ts_parallel.py"] = sanitize(parallel_src)

    results = {}

    for path, src in sources.items():
        path_str = str(path)

        if not src or len(src.strip()) < MIN_BYTES:
            results[path_str] = (
                f"error: source too small or empty "
                f"({len(src) if src else 0} bytes)"
            )
            continue

        try:
            if _should_skip(path, src):
                results[path_str] = (
                    f"skipped ({path.stat().st_size} bytes — already current)"
                )
            else:
                results[path_str] = _write_text(path, src)
        except Exception as exc:
            results[path_str] = f"error: {exc}"

    return results


# ---------------------------------------------------------------------------
# Import verification — call after bootstrap() to confirm all modules load
# ---------------------------------------------------------------------------

def verify_imports() -> dict:
    """
    Verify all helper modules are importable after bootstrap() runs.
    Uses direct named imports — does not use __import__() or sys.

    Returns dict mapping module_name → "ok" or "error: <message>"
    """
    results = {}

    try:
        from ts_fallback_map import run_with_fallback
        results["ts_fallback_map"] = "ok"
    except Exception as e:
        results["ts_fallback_map"] = f"error: {e}"

    try:
        from subagent_templates import render
        results["subagent_templates"] = "ok"
    except Exception as e:
        results["subagent_templates"] = f"error: {e}"

    try:
        from value_drivers import match_drivers
        results["value_drivers"] = "ok"
    except Exception as e:
        results["value_drivers"] = f"error: {e}"

    try:
        from pg_report_builder import build_pg_report, build_onepager
        results["pg_report_builder"] = "ok"
    except Exception as e:
        results["pg_report_builder"] = f"error: {e}"

    try:
        from territory_xls import TerritoryWorkbook
        results["territory_xls"] = "ok"
    except Exception as e:
        results["territory_xls"] = f"error: {e}"

    try:
        from ts_parallel import run_ts_batch
        results["ts_parallel"] = "ok"
    except Exception as e:
        results["ts_parallel"] = f"error: {e}"

    return results


# ---------------------------------------------------------------------------
# Account cache warm-up — call AFTER "✅ Ready!", never inside bootstrap()
# ---------------------------------------------------------------------------

def warm_account_cache(owner_name: str) -> dict:
    """
    Pre-warm the account cache for the current user.
    Delegates to ts_fallback_map.warm_account_cache().
    Call AFTER posting "✅ Ready!" — never before.
    Does not use sys — direct import only.
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
                else f"Cache warm returned '{status}' for '{owner_name}'."
            ),
        }
    except Exception as exc:
        return {"status": "error", "message": str(exc)}


# ---------------------------------------------------------------------------
# Self-test
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print("=== bootstrap.py self-test ===\n")

    # 1. Sanitizer — escape artifacts
    dirty = "def hello\\_world():\\n    x = \\_private"
    clean = sanitize(dirty)
    assert "\\_" not in clean
    print("✅ sanitize() escape artifacts")

    # 2. Sanitizer — backslash-space
    assert "\\ " not in sanitize("foo\\ bar")
    print("✅ sanitize() backslash-space")

    # 3. Sanitizer — braces preserved (f-string safety)
    fstring = "style = f\"color: {NAVY}; background: {{white}}\""
    assert sanitize(fstring) == fstring, "Sanitizer must not modify braces"
    print("✅ sanitize() braces preserved")

    # 4. Sanitizer idempotent
    assert sanitize(clean) == clean
    print("✅ sanitize() idempotent")

    # 5. _should_skip matching content
    import tempfile, os
    content = "def hello(): pass\n" * 40
    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
        f.write(content)
        tmp = Path(f.name)
    assert _should_skip(tmp, content)
    print("✅ _should_skip() matching content")

    # 6. _should_skip different content
    assert not _should_skip(tmp, "def world(): pass\n" * 40)
    print("✅ _should_skip() different content")

    # 7. _should_skip placeholder
    assert not _should_skip(tmp, "# placeholder\n" * 40)
    print("✅ _should_skip() rejects placeholder")

    # 8. _should_skip missing file
    assert not _should_skip(Path("/tmp/nonexistent_xyz.py"), content)
    print("✅ _should_skip() missing file")

    os.unlink(tmp)
    print("\nSelf-test complete.")
