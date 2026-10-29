#!/usr/bin/env python3
"""Static checks for this single-page data explorer. No dependencies.

The repository had no CI, so nothing held the page to its own security policy.

The specific thing this exists for: the Content-Security-Policy is declared
**twice**, as a `<meta http-equiv>` in index.html and as a header in
netlify.toml. A browser enforces the intersection of the two, so the tighter one
governs and the looser one is invisible. They had drifted: the header was copied
verbatim from the Experiments repository, which hosts many tools, and allowed 17
origins this site never touches. Nothing broke, and nothing would have, until
someone deleted the meta tag believing the header covered it and silently widened
the policy instead.

A CSP that is too tight fails silently too: the script simply does not load, the
chart does not draw, and only the browser console says why.

Run:  python3 scripts/check.py
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HTML = (ROOT / "index.html").read_text(encoding="utf-8")
TOML = (ROOT / "netlify.toml").read_text(encoding="utf-8")

failures = []


def check(name, fn):
    try:
        note = fn()
        print(f"  ok    {name}" + (f" ({note})" if note else ""))
    except AssertionError as e:
        failures.append(name)
        print(f"  FAIL  {name}\n        {e}")


def parse_csp(text):
    out = {}
    for part in text.split(";"):
        part = part.strip()
        if not part:
            continue
        name, *values = part.split()
        out[name] = set(values)
    return out


def origins(urls):
    got = set()
    for u in urls:
        m = re.match(r"(https?://[^/\s]+)", u)
        if m:
            got.add(m.group(1))
    return got


meta_m = re.search(r'http-equiv="Content-Security-Policy"\s+content="([^"]+)"', HTML)
head_m = re.search(r'Content-Security-Policy\s*=\s*"([^"]+)"', TOML)


def _both_present():
    assert meta_m, "index.html has no Content-Security-Policy meta tag"
    assert head_m, "netlify.toml sets no Content-Security-Policy header"
check("the page and the deploy config both declare a CSP", _both_present)

meta = parse_csp(meta_m.group(1)) if meta_m else {}
head = parse_csp(head_m.group(1)) if head_m else {}

# Directives the header adds as hardening; the meta tag has no reason to repeat
# them because they cannot be relaxed by their absence.
HEADER_ONLY = {"object-src", "worker-src", "media-src"}


def _agree():
    shared = (set(meta) | set(head)) - HEADER_ONLY
    diffs = []
    for d in sorted(shared):
        a, b = meta.get(d, set()), head.get(d, set())
        if a != b:
            only_head = sorted(b - a)
            only_meta = sorted(a - b)
            bits = []
            if only_head:
                bits.append(f"header allows {only_head}")
            if only_meta:
                bits.append(f"meta allows {only_meta}")
            diffs.append(f"{d}: " + "; ".join(bits))
    assert not diffs, (
        "the two policies disagree, so the tighter one silently governs:\n        "
        + "\n        ".join(diffs)
    )
    return f"{len(shared)} directives identical in both"
check("the meta CSP and the header CSP say the same thing", _agree)


def _covers_usage():
    """Anything the page loads must be allowed, or it fails with no visible error."""
    checks = [
        ("script-src", origins(re.findall(r'<script[^>]+src="([^"]+)"', HTML))),
        # Only real stylesheets. A Google Fonts <link> pulls CSS from
        # fonts.googleapis.com (style-src) and the font files from
        # fonts.gstatic.com (font-src); lumping them together reports a
        # violation that does not exist.
        ("style-src", origins(
            re.findall(r'<link[^>]+rel="stylesheet"[^>]*href="([^"]+)"', HTML)
            + re.findall(r'<link[^>]+href="([^"]+)"[^>]*rel="stylesheet"', HTML))),
        ("font-src", origins(
            re.findall(r'<link[^>]+href="(https://fonts\.gstatic\.com[^"]*)"', HTML))),
        ("img-src", origins(re.findall(r'<img[^>]+src="([^"]+)"', HTML))),
    ]
    blocked = []
    for directive, used in checks:
        allowed = meta.get(directive, set()) | meta.get("default-src", set())
        for origin in used:
            if origin not in allowed:
                blocked.append(f"{directive}: {origin}")
    assert not blocked, "loaded but not allowed by the CSP: " + ", ".join(blocked)
    return "every subresource origin in the page is allowed"
check("the CSP allows everything the page actually loads", _covers_usage)


PAGES = sorted(p for p in ROOT.rglob("*.html") if ".git" not in p.parts and "node_modules" not in p.parts)


def _every_page_covered():
    """The header governs every page, not just index.html. Checking only the
    landing page let the CSP be tightened in September 2026 while both map
    pages still loaded Leaflet from unpkg.com and tiles from carto: the maps
    were blank in production, with nothing but a console message to show it."""
    blocked = []
    for page in PAGES:
        text = page.read_text(encoding="utf-8")
        used = [
            ("script-src", origins(re.findall(r'<script[^>]+src="([^"]+)"', text))),
            ("style-src", origins(
                re.findall(r'<link[^>]+rel="stylesheet"[^>]*href="([^"]+)"', text)
                + re.findall(r'<link[^>]+href="([^"]+)"[^>]*rel="stylesheet"', text))),
            ("img-src", origins(re.findall(r'<img[^>]+src="([^"]+)"', text)
                                + re.findall(r"""['"](https://[^'"]+\{z\}[^'"]*)['"]""", text))),
        ]
        for directive, found in used:
            allowed = head.get(directive, set()) | head.get("default-src", set())
            for origin in found:
                if origin not in allowed:
                    blocked.append(f"{page.name} {directive}: {origin}")
    assert not blocked, "loaded but not allowed by the header CSP: " + ", ".join(blocked)
    return f"{len(PAGES)} pages, map tiles included"
check("the header CSP allows what every page loads", _every_page_covered)


def _fetch_targets_allowed():
    """Iconify fetches its icon data at runtime, which connect-src governs."""
    conn = meta.get("connect-src", set()) | meta.get("default-src", set())
    if "<iconify-icon" in HTML or "iconify-icon.min.js" in HTML:
        for needed in ("https://api.iconify.design", "https://api.simplesvg.com",
                       "https://api.unisvg.com"):
            assert needed in conn, (
                f"the page uses iconify-icon, which fetches icon data at runtime, "
                f"but connect-src does not allow {needed}. Icons render as empty "
                f"boxes with only a console message."
            )
    return "iconify icon-data origins allowed" if "<iconify-icon" in HTML else None
check("runtime fetch targets are allowed", _fetch_targets_allowed)


def _no_hardcoded_latest_year():
    """A pinned year makes the page quietly stale a year after it is written."""
    if "new Date().getFullYear()" in HTML:
        return "the latest year is derived from the clock, not pinned"
    pinned = re.findall(r"(?:LATEST|YEAR_MAX|CURRENT_YEAR)\s*=\s*(20\d\d)", HTML)
    assert not pinned, (
        f"a year is hardcoded ({', '.join(pinned)}). The page will show stale data "
        f"from the next release onwards without anything failing."
    )
check("no hardcoded 'latest year'", _no_hardcoded_latest_year)


def _page_basics():
    assert re.search(r"<html[^>]+lang=", HTML), "no lang attribute on <html>"
    assert re.search(r'<meta[^>]+name=["\']?viewport', HTML, re.I), (
        "no viewport meta; a phone lays the page out at desktop width")
    assert re.search(r"<title>[^<]+</title>", HTML), "no title"
    m = re.search(r"<title>([^<]+)</title>", HTML)
    return m.group(1)[:48]
check("page basics", _page_basics)


def _inline_handlers_are_permitted():
    """Inline handlers are fine here, and only here, because script-src carries
    'unsafe-inline'. If that is ever tightened to a nonce or hash, every one of
    them stops firing with no error on the page."""
    found = re.findall(r"\son(?:click|change|load|submit|error)\s*=", HTML)
    if not found:
        return "none used"
    allowed = "'unsafe-inline'" in meta.get("script-src", set())
    assert allowed, (
        f"{len(found)} inline event handlers, but script-src no longer allows "
        f"'unsafe-inline', so none of them fire. Move them to addEventListener.")
    return f"{len(found)} used, and script-src still allows 'unsafe-inline'"
check("inline handlers match what the CSP permits", _inline_handlers_are_permitted)


def _map_pages_match_csv():
    """Both map pages carry the CSV inline. A correction to the CSV that does not
    reach them leaves the map showing what the record no longer says."""
    import subprocess
    out = subprocess.run([sys.executable, str(ROOT / "scripts" / "build_pages.py"), "--check"],
                         capture_output=True, text=True)
    assert out.returncode == 0, out.stdout.strip() or out.stderr.strip()
    return out.stdout.strip().removeprefix("PASS - ")
check("every page matches adani_database.csv", _map_pages_match_csv)


def _paper_matches_data():
    """The paper and its finding pages print numbers computed from data/paper.
    A corrected row that does not reach them leaves the paper saying what the
    data no longer says."""
    import subprocess
    out = subprocess.run([sys.executable, str(ROOT / "scripts" / "build_paper.py"), "--check"],
                         capture_output=True, text=True)
    assert out.returncode == 0, out.stdout.strip() or out.stderr.strip()
    return out.stdout.strip().removeprefix("PASS - ")
check("the paper matches data/paper", _paper_matches_data)


def _paper_rows_name_a_source():
    """Every row in the paper's tables names a document, and every row that is
    not a calculation says where in it the figure is: a web address, a page or
    a table. A figure with no source is the thing this site exists not to
    publish."""
    import csv
    bad = []
    for f in sorted((ROOT / "data" / "paper").glob("*.csv")):
        if f.name == "series.csv":
            continue
        with f.open(newline="", encoding="utf-8") as fh:
            for i, r in enumerate(csv.DictReader(fh), 2):
                derived = r["source_title"].lower().startswith("derived")
                located = r["url"].strip().startswith("http") or r["locator"].strip()
                if not r["source_title"].strip() or not (derived or located):
                    bad.append(f"{f.name}:{i}")
    assert not bad, f"{len(bad)} rows name no document, or no address or page for it, e.g. {bad[:5]}"
    return "every row names its document, and every non-derived row an address or page"
check("every row in data/paper names its source", _paper_rows_name_a_source)


def _rows_carry_their_check():
    """Every row says how far it has been checked, and a row marked verified
    names at least one source."""
    import csv
    with (ROOT / "adani_database.csv").open(newline="", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    bad = [r["Project/Location"] for r in rows if not r["Verification_Status"].strip()]
    assert not bad, f"{len(bad)} rows have no Verification_Status, e.g. {bad[:3]}"
    bare = [r["Project/Location"] for r in rows
            if r["Verification_Status"].startswith("Verified") and not r["Source_URLs"].strip()]
    assert not bare, f"{len(bare)} rows marked verified name no source, e.g. {bare[:3]}"
    return f"{len(rows)} rows"
check("every row states how far it was checked", _rows_carry_their_check)


def _stated_counts_match():
    """The project counts written into the pages are typed, not computed, so
    they are compared with the CSV. They read 444 for months after the record
    was cut to 386."""
    import csv
    with (ROOT / "adani_database.csv").open(newline="", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    total = len(rows)
    adani = [r for r in rows if r["Group"] == "Adani"]
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    # The pages' counts are written by build_pages.py or computed at load.
    want = {
        "README.md": (re.search(r"database of (\d+) major", readme), total),
    }
    wrong = [f"{k} states no count" if not m else f"{k} says {m.group(1)}, CSV has {n}"
             for k, (m, n) in want.items() if not m or int(m.group(1)) != n]
    assert not wrong, "; ".join(wrong)
    return f"{total} projects, {len(adani)} Adani"
check("stated project counts match the CSV", _stated_counts_match)


print()
if failures:
    print(f"FAIL - {len(failures)} check(s) failed")
    sys.exit(1)
print("PASS - all checks passed")
