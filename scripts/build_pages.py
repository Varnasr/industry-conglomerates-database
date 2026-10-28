"""Write the map data in crony_tracker.html and adani_research_map.html from adani_database.csv.

The CSV is the record. Both pages carry a copy of it as `const markersData = [...]`
on one line, and before this script those copies were edited by hand, so a
correction in one place could miss the others.

    python3 scripts/build_pages.py          rewrite both pages
    python3 scripts/build_pages.py --check  fail if either page is stale
"""
import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CSV = ROOT / "adani_database.csv"

NO_GOI = {"Private Acquisition (No GOI)", "Organic Growth (No GOI)", "International (Foreign Govt)",
          "No documented government role"}

# Marker colours by support type, as each page has always drawn them.
TRACKER_COLOURS = {
    "Direct Govt Contract/PPP": "#DC143C", "Policy/Regulatory Benefit": "#FFD700",
    "SECI Solar Contract": "#32CD32", "Private Acquisition (No GOI)": "#1E90FF",
    "Regulatory License (PNGRB/AAI/etc)": "#FF6347", "Defence Production License": "#2F4F4F",
    "Organic Growth (No GOI)": "#4169E1", "State Government MoU": "#FF8C00",
    "International (Foreign Govt)": "#9932CC", "No documented government role": "#94A3B8",
    "Government land or asset transfer": "#B45309", "Public sector finance": "#0D9488",
}
MAP_COLOURS = {
    "Direct Govt Contract/PPP": "#DC143C", "Policy/Regulatory Benefit": "#FFD700",
    "SECI Solar Contract": "#32CD32", "Private Acquisition (No GOI)": "#4169E1",
    "Regulatory License (PNGRB/AAI/etc)": "#FF4500", "Defence Production License": "#006400",
    "Organic Growth (No GOI)": "#1E90FF", "State Government MoU": "#FF6347",
    "International (Foreign Govt)": "#9932CC", "No documented government role": "#94A3B8",
    "Government land or asset transfer": "#B45309", "Public sector finance": "#0D9488",
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


def tracker_item(r, intl):
    t = r["GOI_Support_Type"]
    return {
        "group": r["Group"], "name": r["Project/Location"], "sector": r["Sector"], "state": r["State"],
        "year": int(r["Year"]), "status": r["Status"], "support_type": t, "support_note": r["Support_Note"],
        "modi_era": r["Modi_Era"], "lat": number(r["Latitude"]), "lng": number(r["Longitude"]),
        "details": r["Details"], "sources": r["Source_URLs"], "color": TRACKER_COLOURS[t],
        "is_goi": t not in NO_GOI, "is_international": intl,
        "verification": r["Verification_Status"],
    }


def map_item(r, intl):
    t = r["GOI_Support_Type"]
    return {
        "name": r["Project/Location"], "lat": number(r["Latitude"]), "lng": number(r["Longitude"]),
        "sector": r["Sector"], "state": r["State"], "year": int(r["Year"]), "status": r["Status"],
        "details": r["Details"], "support_type": t, "is_goi": t not in NO_GOI,
        "is_international": intl, "modi_era": r["Modi_Era"], "color": MAP_COLOURS[t],
        "verification": r["Verification_Status"],
    }


def international(r):
    if r.get("International", "").strip():
        return r["International"].strip().lower() in ("yes", "true", "1")
    return not is_india(r["State"])


def splice(path, items):
    text = path.read_text(encoding="utf-8")
    key = "const markersData = "
    i = text.index(key) + len(key)
    j = text.index("\n", i)
    line = json.dumps(items, ensure_ascii=False) + ";"
    return text[:i] + line + text[j:]


def main():
    check = "--check" in sys.argv[1:]
    data = rows()
    tracker = [tracker_item(r, international(r)) for r in data]
    research = [map_item(r, international(r)) for r in data if r["Group"] == "Adani"]
    stale = []
    for name, items in (("crony_tracker.html", tracker), ("adani_research_map.html", research)):
        path = ROOT / name
        new = splice(path, items)
        if new != path.read_text(encoding="utf-8"):
            stale.append(name)
            if not check:
                path.write_text(new, encoding="utf-8")
    if check and stale:
        print("FAIL - out of date with adani_database.csv: " + ", ".join(stale))
        print("Run: python3 scripts/build_pages.py")
        sys.exit(1)
    print(("PASS - both map pages match" if check else "wrote both map pages from") +
          " adani_database.csv (%d rows, %d Adani)" % (len(tracker), len(research)))


if __name__ == "__main__":
    main()
