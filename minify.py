import re
from pathlib import Path

FILES = [
    "ts_fallback_map.py",
    "subagent_templates.py",
    "value_drivers.py",
    "pg_report_builder.py",
    "territory_xls.py",
]

def minify(src):
    lines = src.splitlines()

    # 1. Remove self-test block (if __name__ == "__main__": to end of file)
    cleaned = []
    in_main = False
    for line in lines:
        if line.strip().startswith('if __name__') and '__main__' in line:
            in_main = True
        if not in_main:
            cleaned.append(line)
    lines = cleaned

    # 2. Remove pure comment lines longer than 60 chars (section dividers)
    #    Keep short comments, inline comments, and blank lines
    no_comments = []
    for line in lines:
        stripped = line.strip()
        if stripped.startswith('#') and len(stripped) > 60:
            continue
        no_comments.append(line)
    lines = no_comments

    # 3. Collapse 3+ consecutive blank lines down to 1
    out   = []
    blank = 0
    for line in lines:
        if line.strip() == "":
            blank += 1
            if blank <= 1:
                out.append(line)
        else:
            blank = 0
            out.append(line)

    return "\n".join(out)


for fname in FILES:
    path = Path(fname)
    if not path.exists():
        print(f"SKIP {fname} — not found in current directory")
        continue

    src      = path.read_text(encoding="utf-8")
    minified = minify(src)

    # Verify it's still valid Python
    try:
        compile(minified, fname, "exec")
        valid = "✅ valid Python"
    except SyntaxError as e:
        valid = f"❌ SYNTAX ERROR: {e}"

    out_path = Path(f"min_{fname}")
    out_path.write_text(minified, encoding="utf-8")

    orig_kb = len(src.encode("utf-8")) / 1024
    mini_kb = len(minified.encode("utf-8")) / 1024
    saved   = orig_kb - mini_kb
    pct     = (saved / orig_kb) * 100

    print(f"{fname}")
    print(f"  {orig_kb:.1f}KB → {mini_kb:.1f}KB  (saved {saved:.1f}KB / {pct:.0f}%)")
    print(f"  {valid}")
    print(f"  → min_{fname}")
    print()
