"""
bootstrap.py
Sandbox file writer for PG workflow helper modules.

Writes helper files to /sandbox/ from fetched source strings.
Includes content-aware skip logic — never skips based on size alone.
Includes markdown escape sanitizer for web_search content artifacts.

Usage:
    from bootstrap import bootstrap, sanitize, warm_account_cache

    # Sanitize fetched content before passing to bootstrap:
    results = bootstrap(
        fallback_src=sanitize(<ts_fallback_map.py content>),
        tmpl_src=sanitize(<subagent_templates.py content>),
        vd_src=sanitize(<value_drivers.py content>),
        report_builder_src=sanitize(<pg_report_builder.py content>),
        territory_xls_src=sanitize(<territory_xls.py content>),
        parallel_src=sanitize(<ts_parallel.py content>),
    )

    # After posting "✅ Ready!", call warm_account_cache() — never before:
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

    web_search mode=contents sometimes returns escape artifacts:
        \\_ instead of _
        \\[ instead of [
        \\ (backslash-space) causing broken line continuations
        etc.

    Call this on every fetched source string before passing to bootstrap()
    or before writing any file. bootstrap() also calls this internally,
    so double-sanitizing is safe.
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
        ("\\{",  "{"),
        ("\\}",  "}"),
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
    Return True only if the existing file contains valid Python source
    that substantively matches what we are about to write.

    Never skips based on size alone — placeholder files >= 500 bytes
    would incorrectly pass a size-only check and cause bootstrap to
    skip writing the real content.

    Compares first 200 chars of stripped content. If they match,
    the file is already the correct version and can be skipped safely.
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
    return "written"


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
    dict mapping filepath → status string:
        "written (N bytes)"        — file was newly written
        "skipped (N bytes)"        — file already exists with matching content
        "error: source too small"  — source failed minimum size check
        "error: <message>"         — write failed
    """
    SANDBOX.mkdir(parents=True, exist_ok=True)

    # Sanitize all sources before processing
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
                _write_text(path, src)
                results[path_str] = f"written ({len(src)} bytes)"
        except Exception as exc:
            results[path_str] = f"error: {exc}"

    return results


# ---------------------------------------------------------------------------
# Account cache warm-up — call AFTER "✅ Ready!", never inside bootstrap()
# ---------------------------------------------------------------------------

def warm_account_cache(owner_name: str) -> dict:
    """
    Pre-warm the account cache for the current user.

    Delegates to ts_fallback_map.warm_account_cache().
    Call this AFTER posting "✅ Ready!" — never before.

    Parameters
    ----------
    owner_name : Salesforce display name (from VOLTRON_OWNER_NAME env var)

    Returns
    -------
    dict with keys: status, message
        status "ok"            — cache warmed successfully
        status "skipped"       — no owner_name provided
        status "token_expired" — TS token needs refresh
        status "error"         — exception during warm
    """
    if not owner_name or not owner_name.strip():
        return {"status": "skipped", "message": "No owner_name provided."}

    try:
        import sys
        sys.path.insert(0, str(SANDBOX))
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
    print("=== bootstrap.py self-test ===\n")

    # 1. Test sanitizer — escape artifacts
    dirty = "def hello\\_world():\\n    x = \\_private\\n    d = \\{'key': 'val'\\}"
    clean = sanitize(dirty)
    assert "\\_" not in clean, "Sanitizer failed on underscore"
    assert "\\{" not in clean, "Sanitizer failed on brace"
    print("✅ sanitize() — escape artifacts stripped")

    # 2. Test sanitizer — backslash-space (line continuation artifact)
    dirty2 = "result = foo\\ + bar"
    clean2 = sanitize(dirty2)
    assert "\\ " not in clean2, "Sanitizer failed on backslash-space"
    print("✅ sanitize() — backslash-space stripped")

    # 3. Test sanitizer idempotent — double sanitize is safe
    once  = sanitize(dirty)
    twice = sanitize(once)
    assert once == twice, "Sanitizer not idempotent"
    print("✅ sanitize() — idempotent")

    # 4. Test _should_skip — matching content
    import tempfile, os
    content = "def hello(): pass\n" * 40  # > 500 bytes
    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
        f.write(content)
        tmp = Path(f.name)
    assert _should_skip(tmp, content), "Should skip matching file"
    print("✅ _should_skip() — skips matching content")

    # 5. Test _should_skip — different content
    different = "def world(): pass\n" * 40
    assert not _should_skip(tmp, different), "Should not skip different file"
    print("✅ _should_skip() — does not skip different content")

    # 6. Test _should_skip — placeholder (>500 bytes but different)
    placeholder = "# placeholder\n" * 40
    assert not _should_skip(tmp, placeholder), \
        "Should not skip when placeholder exists"
    print("✅ _should_skip() — does not skip over placeholder files")

    # 7. Test _should_skip — missing file
    assert not _should_skip(Path("/tmp/nonexistent_xyz.py"), content), \
        "Should return False for missing file"
    print("✅ _should_skip() — returns False for missing file")

    os.unlink(tmp)

    # 8. Test bootstrap with stub sources
    import shutil
    test_sandbox = Path("/tmp/test_sandbox_bootstrap")
    test_sandbox.mkdir(exist_ok=True)

    real_sandbox = SANDBOX
    import bootstrap as _self
    _self.SANDBOX = test_sandbox

    dummy_src = "# test module\ndef placeholder(): pass\n" * 30

    results = _self.bootstrap(
        fallback_src=dummy_src,
        tmpl_src=dummy_src,
        vd_src=dummy_src,
        report_builder_src=dummy_src,
        territory_xls_src=dummy_src,
        parallel_src=dummy_src,
    )

    for path, status in results.items():
        assert "error" not in status, f"Unexpected error: {path}: {status}"
        print(f"  {status[:7].upper()}: {Path(path).name}")

    print("✅ bootstrap() — all files written")

    # 9. Test skip on re-run
    results2 = _self.bootstrap(
        fallback_src=dummy_src,
        tmpl_src=dummy_src,
        vd_src=dummy_src,
        report_builder_src=dummy_src,
        territory_xls_src=dummy_src,
        parallel_src=dummy_src,
    )

    for path, status in results2.items():
        assert "skipped" in status, f"Expected skip on re-run: {path}: {status}"
    print("✅ bootstrap() — skips unchanged files on re-run")

    # 10. Test placeholder is NOT skipped
    placeholder_src = "# placeholder\n" * 40
    (test_sandbox / "ts_fallback_map.py").write_text(placeholder_src)
    results3 = _self.bootstrap(
        fallback_src=dummy_src,
        tmpl_src=dummy_src,
        vd_src=dummy_src,
        report_builder_src=dummy_src,
        territory_xls_src=dummy_src,
    )
    ts_status = results3.get(str(test_sandbox / "ts_fallback_map.py"), "")
    assert "written" in ts_status, \
        f"Placeholder should have been overwritten: {ts_status}"
    print("✅ bootstrap() — overwrites placeholder files correctly")

    _self.SANDBOX = real_sandbox
    shutil.rmtree(test_sandbox)

    print("\nSelf-test complete.")
