"""Write every figure the pages show from adani_database.csv.

The CSV is the record. tracker.html carries a copy of it as
`const markersData = [...]` on one line, projects.html as
`const projectsData = [...]`, and index.html a block of counts between
`<!--stats:start-->` and `<!--stats:end-->`. Before this script the copies were
edited by hand, so a correction in one place could miss the others, and the
landing page said 444 projects for months after the record was cut to 386.

    python3 scripts/build_pages.py          rewrite the pages
    python3 scripts/build_pages.py --check  fail if any page is stale
"""
import collections
import csv
import html
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CSV = ROOT / "adani_database.csv"

NO_GOI = {"Private Acquisition (No GOI)", "Organic Growth (No GOI)", "International (Foreign Govt)",
          "No documented government role"}

# The map colours government roles by family; the pop-up gives the exact type.
ROLE_FAMILY = {
    "Direct Govt Contract/PPP": "contract", "SECI Solar Contract": "contract",
    "Regulatory License (PNGRB/AAI/etc)": "licence", "Policy/Regulatory Benefit": "licence",
    "Defence Production License": "licence",
    "State Government MoU": "state", "Government land or asset transfer": "state",
    "Public sector finance": "state",
    "International (Foreign Govt)": "foreign",
    "Private Acquisition (No GOI)": "none", "Organic Growth (No GOI)": "none",
    "No documented government role": "none",
}

INDIA = {
    "Andhra Pradesh", "Arunachal Pradesh", "Assam", "Bihar", "Chhattisgarh", "Goa", "Gujarat",
    "Haryana", "Himachal Pradesh", "Jharkhand", "Karnataka", "Kerala", "Madhya Pradesh",
    "Maharashtra", "Manipur", "Meghalaya", "Mizoram", "Nagaland", "Odisha", "Punjab",
    "Rajasthan", "Sikkim", "Tamil Nadu", "Telangana", "Tripura", "Uttar Pradesh",
    "Uttarakhand", "West Bengal", "Delhi", "Jammu and Kashmir", "Jammu & Kashmir", "Ladakh",
    "Puducherry", "Chandigarh", "Andaman and Nicobar Islands", "Lakshadweep",
    "Dadra and Nagar Haveli and Daman and Diu",
}


def is_india(state):
    parts = [p.strip() for p in state.replace("/", ",").replace(" and ", ",").split(",") if p.strip()]
    low = {s.lower() for s in INDIA}
    return any(p.lower() in low or p.lower() in ("india", "multiple", "multi-state", "pan-india", "pan india", "various")
               or p.lower().startswith("multiple") or p.lower().startswith("pan") for p in parts) or state.strip().lower() in low


def number(v):
    f = float(v)
    return int(f) if f.is_integer() else f


def rows():
    with CSV.open(newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def row_id(r):
    """A stable address for a project, so a map pin can link to its sources."""
    return re.sub(r"[^a-z0-9]+", "-", f'{r["Group"]} {r["Project/Location"]} {r["State"]}'.lower()).strip("-")


def tracker_item(r, intl):
    t = r["GOI_Support_Type"]
    return {
        "id": row_id(r), "group": r["Group"], "name": r["Project/Location"], "sector": r["Sector"], "state": r["State"],
        "year": int(r["Year"]), "status": r["Status"], "support_type": t, "support_note": r["Support_Note"],
        "modi_era": r["Modi_Era"], "lat": number(r["Latitude"]), "lng": number(r["Longitude"]),
        "details": r["Details"], "sources": r["Source_URLs"], "role_family": ROLE_FAMILY[t],
        "is_goi": t not in NO_GOI, "is_international": intl,
        "verification": r["Verification_Status"],
    }


def project_item(r):
    return {
        "id": row_id(r), "group": r["Group"], "name": r["Project/Location"], "sector": r["Sector"],
        "state": r["State"], "year": int(r["Year"]), "status": r["Status"],
        "support_type": r["GOI_Support_Type"], "support_note": r["Support_Note"],
        "details": r["Details"], "sources": r["Source_URLs"],
        "verification": r["Verification_Status"],
    }


def urls(r):
    return [u.strip() for u in r["Source_URLs"].split(" | ") if u.strip()]


def stats_block(data):
    """The counts on the landing page, written rather than typed."""
    e = html.escape
    out = ['<section class="stack" aria-labelledby="h-houses">', '  <h2 id="h-houses">The two groups</h2>', '  <div class="houses">']
    for group, label, colour in (("Adani", "Adani Group", "adani"), ("Reliance", "Reliance Industries (Ambani)", "reliance")):
        g = [r for r in data if r["Group"] == group]
        years = [int(r["Year"]) for r in g]
        top = collections.Counter(r["Sector"] for r in g).most_common(3)
        out += [f'    <div class="house" style="--c:var(--{colour})">',
                f'      <div class="eyebrow">{e(label)}</div>',
                f'      <div class="n">{len(g)}</div>',
                f'      <p>projects across {len({r["Sector"] for r in g})} sectors, {min(years)} to {max(years)}</p>',
                '      <div class="meta">Largest: ' + " · ".join(f"{e(s)} {n}" for s, n in top) + '</div>',
                '    </div>']
    out += ['  </div>', '</section>', '']
    order = [("Verified", "ok", "Verified"), ("Verified with corrections", "fix", "Verified with corrections"),
             ("Partly verified", "part", "Partly verified"), ("Unverified", "none", "Not yet verified")]
    c = collections.Counter(r["Verification_Status"] for r in data)
    total = len(data)
    label = ", ".join(f"{c[k]} {lab.lower()}" for k, _, lab in order)
    out += ['<section class="stack" aria-labelledby="h-check">',
            '  <h2 id="h-check">How far each project has been checked</h2>',
            f'  <p class="lede">All {total} rows were checked against documents on 28 October 2026. The check removed 58 rows that were duplicates or not these groups\' projects.</p>',
            f'  <div class="bar" role="img" aria-label="{label}">' + "".join(
                f'<span class="s-{k}" style="width:{100 * c[s] / total:.4f}%"></span>' for s, k, _ in order) + '</div>',
            '  <div class="key">' + "".join(f'<span><i class="sw s-{k}"></i>{lab} <b>{c[s]}</b></span>' for s, k, lab in order) + '</div>',
            '</section>', '']
    all_urls = [u for r in data for u in urls(r)]
    hosts = collections.Counter(re.sub(r"^www\.", "", re.match(r"https?://([^/]+)", u).group(1)) for u in all_urls if re.match(r"https?://", u))
    cited = sum(1 for r in data if urls(r))
    out += ['<section class="stack" aria-labelledby="h-sources">',
            '  <h2 id="h-sources">Where the information comes from</h2>',
            '  <div class="cols">', '    <div class="stack">',
            f'      <p>The {total} projects cite {len(all_urls)} sources on {len(hosts)} websites. {cited} projects cite at least one. Each source is listed beside its project on the <a href="projects.html">projects page</a> and in the map\'s pop-ups.</p>',
            '      <p>Most citations are the companies\' own pages and filings, regulators such as the Petroleum and Natural Gas Regulatory Board, and news reports. A company page shows what the company says it owns or runs. A regulator\'s record or a court document is stronger evidence where one exists.</p>',
            '    </div>', '    <div>', '      <div class="eyebrow" style="margin-bottom:10px">Most cited websites</div>',
            '      <ol class="domains">' + "".join(f"<li><span>{e(h)}</span><span>{n}</span></li>" for h, n in hosts.most_common(10)) + '</ol>',
            '    </div>', '  </div>', '</section>']
    return "\n".join(out) + "\n"


def splice_block(path, block):
    text = path.read_text(encoding="utf-8")
    a, b = "<!--stats:start-->\n", "<!--stats:end-->"
    i = text.index(a) + len(a)
    j = text.index(b)
    return text[:i] + block + text[j:]


def international(r):
    if r.get("International", "").strip():
        return r["International"].strip().lower() in ("yes", "true", "1")
    return not is_india(r["State"])


def splice(path, items, key="const markersData = "):
    text = path.read_text(encoding="utf-8")
    i = text.index(key) + len(key)
    j = text.index("\n", i)
    line = json.dumps(items, ensure_ascii=False) + ";"
    return text[:i] + line + text[j:]


def main():
    check = "--check" in sys.argv[1:]
    data = rows()
    tracker = [tracker_item(r, international(r)) for r in data]
    projects = [project_item(r) for r in data]
    stale = []
    for name, make in (("tracker.html", lambda p: splice(p, tracker)),
                       ("projects.html", lambda p: splice(p, projects, "const projectsData = ")),
                       ("index.html", lambda p: splice_block(p, stats_block(data)))):
        path = ROOT / name
        new = make(path)
        if new != path.read_text(encoding="utf-8"):
            stale.append(name)
            if not check:
                path.write_text(new, encoding="utf-8")
    if check and stale:
        print("FAIL - out of date with adani_database.csv: " + ", ".join(stale))
        print("Run: python3 scripts/build_pages.py")
        sys.exit(1)
    print(("PASS - every page matches" if check else "wrote every page from") +
          " adani_database.csv (%d rows)" % len(tracker))


if __name__ == "__main__":
    main()
