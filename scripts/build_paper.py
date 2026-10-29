"""Write the paper and its finding pages from the sourced tables in data/paper/.

Every number the pages print is read from those tables or computed from them
here; none is typed into the prose. Each table row carries its source title,
publisher, URL and the page or table it came from, and each chart lists the
rows it used. Rows whose note says DERIVED are calculations, and the pages say
so beside them.

    python3 scripts/build_paper.py          write paper/, findings/ and data/paper/series.csv
    python3 scripts/build_paper.py --check  fail if any of them is stale
"""
import csv
import html
import io
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data" / "paper"
E = html.escape


# ---------------------------------------------------------------- data

def table(name):
    with (DATA / f"{name}.csv").open(newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


T = {n: table(n) for n in ("ports_airports", "power", "gas_telecom", "cement_retail_media", "macro_weight",
                         "coal_power_land", "reliance_state", "finance", "legal", "airports_ports")
     if (DATA / f"{n}.csv").exists()}


def pick(name, metric, entity=None, sector=None):
    out = [r for r in T[name] if r["metric"] == metric
           and (entity is None or entity.lower() in r["entity"].lower())
           and (sector is None or r["sector"] == sector)]
    if not out:
        raise SystemExit(f"no rows: {name} / {metric} / {entity}")
    return out


def num(r):
    return float(r["value"].replace(",", ""))


def fy_from_march(label):
    """TRAI's 'Mar-2016' is the close of 2015-16."""
    y = int(re.search(r"(20\d\d)", label).group(1))
    return f"{y - 1}-{str(y)[2:]}"


def series(rows, key=lambda r: r["year"]):
    return {key(r): num(r) for r in rows}


def last(d):
    k = list(d)[-1]
    return k, d[k]


def first(d):
    k = list(d)[0]
    return k, d[k]


def pct(v, nd=1):
    return f"{v:.{nd}f}%"


def inr(v):
    """Indian digit grouping for whole crore figures."""
    s = f"{v:,.0f}"
    whole = s.replace(",", "")
    if len(whole) <= 3:
        return whole
    head, tail = whole[:-3], whole[-3:]
    parts = []
    while len(head) > 2:
        parts.insert(0, head[-2:])
        head = head[:-2]
    if head:
        parts.insert(0, head)
    return ",".join(parts + [tail])


# ---------------------------------------------------------------- charts

COLOURS = {"adani": "var(--adani)", "reliance": "var(--reliance)", "ink": "var(--ink-2)",
           "muted": "var(--ink-3)", "part": "var(--part)", "ok": "var(--ok)"}


class Chart:
    """A line chart drawn as inline SVG, with its data table and sources."""

    def __init__(self, cid, title, desc, xs, lines, unit="%", ymax=None, step=None, rows=(), note=""):
        self.cid, self.title, self.desc, self.xs, self.lines = cid, title, desc, xs, lines
        self.unit, self.rows, self.note = unit, list(rows), note
        vals = [v for _, _, d in lines for v in d.values() if v is not None]
        top = max(vals)
        self.step = step or (5 if top <= 40 else 10 if top <= 80 else 500 if top <= 4000 else 1000)
        self.ymax = ymax or (int(top / self.step) + 1) * self.step

    def fmt(self, v):
        if self.unit == "%":
            return f"{v:.1f}%"
        if self.unit == "x":
            return f"{v:.2f}x"
        return f"{v:,.0f}"

    def svg(self):
        W, H, L, R, TP, B = 760, 380, 56, 170, 18, 44
        pw, ph = W - L - R, H - TP - B
        n = len(self.xs)
        x = lambda i: L + (pw * i / (n - 1) if n > 1 else pw / 2)
        y = lambda v: TP + ph - ph * v / self.ymax
        o = [f'<svg viewBox="0 0 {W} {H}" role="img" aria-labelledby="{self.cid}-t {self.cid}-d" class="chart-svg">',
             f'<title id="{self.cid}-t">{E(self.title)}</title><desc id="{self.cid}-d">{E(self.desc)}</desc>']
        v = 0
        while v <= self.ymax + 1e-9:
            yy = y(v)
            o.append(f'<line x1="{L}" x2="{L + pw}" y1="{yy:.1f}" y2="{yy:.1f}" class="grid"/>')
            lab = f"{v:g}%" if self.unit == "%" else f"{v:g}x" if self.unit == "x" else f"{v:,.0f}"
            o.append(f'<text x="{L - 8}" y="{yy + 4:.1f}" text-anchor="end" class="tick">{lab}</text>')
            v += self.step
        every = max(1, round(n / 7))
        for i, lab in enumerate(self.xs):
            if i % every == 0 or i == n - 1:
                o.append(f'<text x="{x(i):.1f}" y="{H - B + 22}" text-anchor="middle" class="tick">{E(lab)}</text>')
        ends = []
        for name, colour, d in self.lines:
            pts = [(i, d.get(lab)) for i, lab in enumerate(self.xs)]
            seg = []
            for i, val in pts + [(None, None)]:
                if val is None:
                    if len(seg) > 1:
                        o.append('<polyline fill="none" stroke="{}" stroke-width="2.5" stroke-linejoin="round" points="{}"/>'.format(
                            COLOURS[colour], " ".join(f"{x(a):.1f},{y(b):.1f}" for a, b in seg)))
                    elif len(seg) == 1:
                        a, b = seg[0]
                        o.append(f'<circle cx="{x(a):.1f}" cy="{y(b):.1f}" r="3.5" fill="{COLOURS[colour]}"/>')
                    seg = []
                else:
                    seg.append((i, val))
            have = [(i, val) for i, val in pts if val is not None]
            for i, val in have:
                o.append(f'<circle cx="{x(i):.1f}" cy="{y(val):.1f}" r="2.5" fill="{COLOURS[colour]}"/>')
            i, val = have[-1]
            ends.append([y(val), x(i), name, val, colour])
        # Spread the end labels so they never overlap.
        ends.sort()
        for k in range(1, len(ends)):
            if ends[k][0] - ends[k - 1][0] < 32:
                ends[k][0] = ends[k - 1][0] + 32
        for yy, xx, name, val, colour in ends:
            o.append(f'<text x="{xx + 10:.1f}" y="{yy - 2:.1f}" class="lab" fill="{COLOURS[colour]}">{E(name)}</text>')
            o.append(f'<text x="{xx + 10:.1f}" y="{yy + 14:.1f}" class="val">{E(self.fmt(val))}</text>')
        o.append("</svg>")
        return "".join(o)

    def sources(self):
        seen, out = set(), []
        for r in self.rows:
            k = (r["source_title"], r["url"])
            if k in seen or not r["url"].startswith("http"):
                continue
            seen.add(k)
            out.append(f'<li><a href="{E(r["url"])}" rel="noopener">{E(r["source_title"])}</a>, {E(r["publisher"])}</li>')
        return out

    def html(self):
        head = "".join(f"<th scope=\"col\">{E(n)}</th>" for n, _, _ in self.lines)
        body = "".join(
            f'<tr><th scope="row">{E(lab)}</th>' + "".join(
                f"<td>{E(self.fmt(d[lab])) if d.get(lab) is not None else '–'}</td>" for _, _, d in self.lines) + "</tr>"
            for lab in self.xs)
        src = self.sources()
        return (f'<figure class="chart" id="{self.cid}">'
                f'<figcaption class="chart-title">{E(self.title)}</figcaption>'
                f'<div class="chart-scroll" tabindex="0" role="region" aria-label="{E(self.title)}, scrolls sideways">{self.svg()}</div>'
                + (f'<p class="chart-note">{self.note}</p>' if self.note else "")
                + f'<details class="chart-data"><summary>Data and {len(src)} source{"s" if len(src) != 1 else ""}</summary>'
                f'<div class="table-scroll" tabindex="0" role="region" aria-label="Data table"><table><thead><tr><th scope="col">Year</th>{head}</tr></thead><tbody>{body}</tbody></table></div>'
                f'<ol class="srcs">{"".join(src)}</ol></details></figure>')


# ---------------------------------------------------------------- the numbers

# Ports
ports = pick("ports_airports", "APSEZ share of all-India port cargo (derived)")
P = series(ports)
port_entry = {r["entity"].split(" (")[0]: r["year"] for r in pick("ports_airports", "APSEZ port in portfolio (entry year)")}

port_src = [r for r in T["ports_airports"] if r["metric"] in (
    "cargo handled", "cargo handled, APSEZ total (company-reported)", "cargo handled, APSEZ India ports (company-reported)")]
rises = sum(1 for a, b in zip(list(P.values()), list(P.values())[1:]) if b > a)

# Airports
air = pick("ports_airports", "share of all-India airport passengers at the 7/8 airports now run by Adani (derived)")
A = series(air)
round_rows = {r["metric"]: r for r in T["ports_airports"] if r["metric"].startswith("2019 PPP round")}
bids = int(num(round_rows["2019 PPP round: bids received"]))
bidders = int(num(round_rows["2019 PPP round: bidding entities"]))
air_src = [r for r in T["ports_airports"] if r["metric"] in ("total passengers", "total passengers (intl+dom)")]
six_share = num(round_rows["2019 PPP round: share of all-India passenger traffic handled by the 6 airports (as cited by MoCA for EGoS decision)"])

# Coal and renewable power, transmission
apl_all = series(pick("power", "derived_share_APL_of_all_India_coal_incl_lignite"))
apl_pvt = series(pick("power", "derived_share_APL_of_private_coal_incl_lignite"))
apl_mw = series(pick("power", "operational_thermal_capacity", "Adani Power"))
pvt_mw = series(pick("power", "installed_capacity_private_coal_incl_lignite"))
agel = series(pick("power", "derived_share_AGEL_of_all_India_RES"))
agel_mw = series(pick("power", "operational_RE_capacity", "Adani Green"))
res_mw = series(pick("power", "installed_capacity_RES_excl_large_hydro"))
aesl = series(pick("power", "derived_share_AESL_of_all_India_ckm"))
ckm = series(pick("power", "circuit_km_220kV_and_above"))
jv_ckm = series(pick("power", "circuit_km_JV_private_sector"))["2025-26"]
tbcb_ad = sum(num(r) for r in T["power"] if r["metric"] in ("TBCB_projects_commissioned", "TBCB_projects_under_construction") and "adani" in r["entity"].lower())
tbcb_all = sum(num(r) for r in T["power"] if r["metric"] in ("TBCB_projects_commissioned_total", "TBCB_projects_under_construction_total"))
tbcb_rows = [r for r in T["power"] if r["metric"].startswith("TBCB_projects")]
coal_won = [r for r in T["power"] if r["metric"] == "commercial_coal_blocks_won"]
coal_total = pick("power", "commercial_coal_blocks_auctioned_total")[0]

# Telecom
hhi = series(pick("gas_telecom", "wireless_HHI_licensee_basis"), key=lambda r: fy_from_march(r["year"]))
hhi_2026_ex = num(pick("gas_telecom", "wireless_HHI_excl_M2M_derived")[0])
jio_sub = series(pick("gas_telecom", "wireless_mobile_subscriber_share", "jio"), key=lambda r: fy_from_march(r["year"]))
airtel_sub = series(pick("gas_telecom", "wireless_mobile_subscriber_share", "airtel"), key=lambda r: fy_from_march(r["year"]))
jio_ex = num(pick("gas_telecom", "wireless_mobile_share_excl_M2M_derived", "jio")[0])
airtel_ex = num(pick("gas_telecom", "wireless_mobile_share_excl_M2M_derived", "airtel")[0])
jio_agr = series(pick("gas_telecom", "access_AGR_share", "jio"), key=lambda r: r["year"].replace("FY", ""))
airtel_agr = series(pick("gas_telecom", "access_AGR_share", "airtel"), key=lambda r: r["year"].replace("FY", ""))
licensees = {}
for r in T["gas_telecom"]:
    if r["metric"] == "wireless_mobile_subscriber_share" and num(r) > 0:
        licensees.setdefault(fy_from_march(r["year"]), set()).add(r["entity"])
spectrum = [r for r in T["gas_telecom"] if r["metric"] == "spectrum_amount" and "jio" in r["entity"].lower()]

# City gas
gas_png = series(pick("gas_telecom", "PNG_domestic_share", "Adani Total Gas"))
gas_cng = series(pick("gas_telecom", "CNG_station_share", "Adani Total Gas"))
jv_png = series(pick("gas_telecom", "PNG_domestic_share", "Indian Oil-Adani"))
jv_cng = series(pick("gas_telecom", "CNG_station_share", "Indian Oil-Adani"))
ga = {r["entity"]: r for r in pick("gas_telecom", "geographical_areas_authorised")}

# Refining
ref = series(pick("cement_retail_media", "Reliance (RIL+RPL SEZ) share of all-India installed refining capacity"),
             key=lambda r: re.search(r"(20\d\d)", r["year"]).group(1))

# Cement
cem_rows = [r for r in T["cement_retail_media"] if r["sector"] == "cement"
            and r["metric"] in ("cement capacity (group, consolidated)", "installed and commissioned cement capacity (consolidated)")]
cem = {re.search(r"(20\d\d)", r["year"]).group(1): num(r) for r in cem_rows}
ut_rows = [r for r in T["cement_retail_media"] if "UltraTech" in r["entity"] and "capacity" in r["metric"]]
ut = {re.search(r"31 Mar (20\d\d)", r["year"]).group(1): num(r) for r in ut_rows}
india_cem = [r for r in T["cement_retail_media"] if r["metric"] == "installed capacity (approx.)"]
india_cem_last = num(india_cem[-1])

# Market weight
mcap = [r for r in T["macro_weight"] if r["metric"] in ("Share of total NSE market capitalisation", "Share of total BSE market capitalisation")]
mc_ad = {r["year"].replace("FY", ""): num(r) for r in mcap if r["entity"].startswith("Adani")}
mc_ril = {r["year"].replace("FY", ""): num(r) for r in mcap if r["entity"] == "RIL"}


# ---------------------------------------------------------------- charts in use

def fy_end(label):
    """'2013-14' -> '2014', for series that are better read by year end."""
    return "20" + label.split("-")[1]


CH = {}
CH["ports"] = Chart(
    "c-ports", "Adani Ports' share of all cargo handled at Indian ports",
    f"Line chart. Adani Ports' share of cargo at all Indian ports rose from {pct(first(P)[1])} in {first(P)[0]} to {pct(last(P)[1])} in {last(P)[0]}.",
    list(P), [("Adani Ports", "adani", P)], rows=ports + port_src,
    note="Adani's Indian ports only, from its annual reports, over all cargo at major and non-major ports from the Ministry of Ports. Derived.")
CH["airports"] = Chart(
    "c-air", "Share of India's airport passengers at the airports Adani now runs",
    f"Line chart. The same airports carried {pct(first(A)[1])} of passengers in {first(A)[0]} and {pct(last(A)[1])} in {last(A)[0]}; Adani took control between 2020 and 2021.",
    list(A), [("Airports Adani now runs", "adani", A)], rows=air + air_src,
    note="The same airports in every year, whoever ran them. Adani ran none before October 2020 and all seven from 2022-23. Derived from AAI's airport-wise traffic.")
CH["coal"] = Chart(
    "c-coal", "Adani Power's share of coal and lignite power capacity",
    f"Line chart. Adani Power's share of private coal capacity was {pct(first(apl_pvt)[1])} in {first(apl_pvt)[0]}, fell to {pct(min(apl_pvt.values()))}, and reached {pct(last(apl_pvt)[1])} in {last(apl_pvt)[0]}. Its share of all coal capacity reached {pct(last(apl_all)[1])}.",
    list(apl_pvt), [("Of private coal capacity", "adani", apl_pvt), ("Of all coal capacity", "muted", apl_all)],
    rows=pick("power", "derived_share_APL_of_private_coal_incl_lignite") + pick("power", "operational_thermal_capacity", "Adani Power") + pick("power", "installed_capacity_private_coal_incl_lignite") + pick("power", "installed_capacity_coal_incl_lignite"),
    note="Gross consolidated capacity at 31 March, over CEA's utility capacity. Derived.")
CH["coal_mw"] = Chart(
    "c-coalmw", "Private coal power capacity and Adani Power's part of it, in megawatts",
    f"Line chart. Private coal and lignite capacity was {pvt_mw[last(pvt_mw)[0]]:,.0f} MW in {last(pvt_mw)[0]}, about where it was in 2017-18, while Adani Power's grew to {last(apl_mw)[1]:,.0f} MW.",
    list(pvt_mw), [("All private coal", "muted", pvt_mw), ("Adani Power", "adani", apl_mw)], unit="MW", step=10000,
    rows=pick("power", "installed_capacity_private_coal_incl_lignite") + pick("power", "operational_thermal_capacity", "Adani Power"))
CH["green"] = Chart(
    "c-green", "Adani Green's share of India's renewable capacity (excluding large hydro)",
    f"Line chart. Adani Green's share rose from {pct(first(agel)[1])} in {first(agel)[0]} to {pct(last(agel)[1])} in {last(agel)[0]}.",
    list(agel), [("Adani Green", "adani", agel)], ymax=10, step=2,
    rows=pick("power", "derived_share_AGEL_of_all_India_RES") + pick("power", "operational_RE_capacity", "Adani Green") + pick("power", "installed_capacity_RES_excl_large_hydro"),
    note="Operational capacity in MW AC, including joint ventures with TotalEnergies at 100%. Derived.")
CH["telecom"] = Chart(
    "c-tel", "Mobile subscribers: Jio's share and market concentration",
    f"Line chart. Jio's share of mobile subscribers rose from {pct(first(jio_sub)[1])} in {first(jio_sub)[0]} to {pct(jio_ex)} in 2025-26 on a comparable basis.",
    list(hhi), [("Jio", "reliance", {**jio_sub, "2025-26": jio_ex}), ("Airtel", "muted", {**airtel_sub, "2025-26": airtel_ex})],
    rows=pick("gas_telecom", "wireless_mobile_subscriber_share", "jio") + pick("gas_telecom", "wireless_mobile_share_excl_M2M_derived"),
    note="Share of reported mobile subscribers at the end of March. 2025-26 leaves out machine-to-machine SIMs, which TRAI began counting that year. Derived.")
CH["hhi"] = Chart(
    "c-hhi", "Concentration of India's mobile market (Herfindahl-Hirschman Index)",
    f"Line chart. The index was {first(hhi)[1]:,.0f} at the end of {first(hhi)[0]} and {hhi_2026_ex:,.0f} at the end of 2025-26.",
    list(hhi), [("HHI", "reliance", {**hhi, "2025-26": hhi_2026_ex})], unit="HHI", ymax=4000, step=1000,
    rows=pick("gas_telecom", "wireless_HHI_licensee_basis") + pick("gas_telecom", "wireless_HHI_excl_M2M_derived"),
    note="Sum of squared percentage shares of every licensee TRAI lists, from 0 to 10,000. Derived.")
CH["agr"] = Chart(
    "c-agr", "Share of access-service revenue (adjusted gross revenue)",
    f"Line chart. Jio's share of access revenue was {pct(jio_agr['2025-26'])} in 2025-26 and Airtel's {pct(airtel_agr['2025-26'])}.",
    [k for k in jio_agr if k != "2016-17"], [("Jio", "reliance", jio_agr), ("Airtel", "muted", airtel_agr)], ymax=50, step=10,
    rows=pick("gas_telecom", "access_AGR_share", "jio") + pick("gas_telecom", "access_AGR_share", "airtel"),
    note="2016-17 is left out: one-off spectrum-surrender receipts inflate it and Jio's share was negative. Derived from TRAI.")
CH["refining"] = Chart(
    "c-ref", "Reliance's share of India's refining capacity, 1 April each year",
    f"Line chart. Reliance's share was {pct(ref['2000'])} in 2000, {pct(max(ref.values()))} at its peak, and {pct(last(ref)[1])} in {last(ref)[0]}.",
    list(ref), [("Reliance", "reliance", ref)], ymax=40, step=10,
    rows=pick("cement_retail_media", "Reliance (RIL+RPL SEZ) share of all-India installed refining capacity") + pick("cement_retail_media", "installed refining capacity"),
    note="Both Jamnagar refineries over all-India capacity, from PPAC. This is installed capacity; crude actually processed is a separate series. Derived.")
CH["cement"] = Chart(
    "c-cem", "Cement capacity: the Adani companies and UltraTech, million tonnes a year",
    f"Line chart. Adani's consolidated cement capacity grew from {cem['2023']:g} to {last(cem)[1]:g} million tonnes a year between March 2023 and March 2026.",
    sorted(set(cem) | set(ut)), [("UltraTech", "muted", ut), ("Adani (Ambuja, ACC and others)", "adani", cem)], unit="MT", ymax=200, step=50,
    rows=cem_rows + ut_rows,
    note="Consolidated capacity at 31 March from each company's annual report. Subsidiaries count in full whatever the stake.")
CH["mcap"] = Chart(
    "c-mcap", "Share of all listed companies' market value, end of March",
    "Line chart. The listed Adani companies were worth about 1% of the market in March 2020 and 5% in March 2022; Reliance between 3% and 7% across the period.",
    sorted(set(mc_ad) | set(mc_ril)), [("Reliance Industries", "reliance", mc_ril), ("Listed Adani companies", "adani", mc_ad)], ymax=8, step=2,
    rows=mcap, note="NSE totals except 2025, which uses BSE. The Adani sum counts ACC and NDTV alongside the parents that hold them. Derived.")


sys.path.insert(0, str(Path(__file__).resolve().parent))
import paper_parts as PP  # noqa: E402

LEV_X = sorted({k for d in PP.ND.values() for k in d})
CH["leverage"] = Chart(
    "c-lev", "Net debt as a multiple of a year's operating earnings (EBITDA)",
    "Line chart. Net debt to EBITDA for five Adani companies and Reliance Industries, 2015-16 to 2025-26.",
    LEV_X, [("Adani Green", "ok", PP.ND["Adani Green"]), ("Adani Enterprises", "adani", PP.ND["Adani Enterprises"]),
            ("Adani Energy Solutions", "muted", PP.ND["Adani Energy Solutions"]), ("Adani Power", "ink", PP.ND["Adani Power"]),
            ("Adani Ports", "part", PP.ND["Adani Ports"]), ("Reliance", "reliance", PP.ND["Reliance Industries"])],
    unit="x", ymax=14, step=2,
    rows=[r for r in PP.FIN if r["metric"].startswith(("Net debt / EBITDA", "Gross borrowings =", "EBITDA, derived", "Net debt (company"))],
    note="Consolidated figures from annual reports and audited results. Net debt is borrowings less cash, bank balances and current investments. Derived. Below zero means net cash.")
CH["pledges"] = Chart(
    "c-pledge", "Founders' shares pledged, as a share of their holding",
    "Line chart. Share of the promoter holding pledged in four Adani companies, March 2016 to March 2026.",
    PP.PLEDGE_X, [("Adani Ports", "part", PP.PLEDGE["Adani Ports"]), ("Adani Enterprises", "adani", PP.PLEDGE["Adani Enterprises"]),
                  ("Adani Energy Solutions", "muted", PP.PLEDGE["Adani Energy Solutions"]), ("Adani Power", "ink", PP.PLEDGE["Adani Power"])],
    ymax=70, step=10,
    rows=[r for r in PP.FIN if r["sector"] == "pledges"],
    note="March 2016 to March 2020 from the annual reports' MGT-9 tables, converted to a share of the promoter holding; from September 2021, NSE shareholding filings. No figure for March 2021.")

# ---------------------------------------------------------------- findings

def entry(port):
    return port_entry.get(port, "")


FINDINGS = [
    dict(slug="ports", chart="ports", eyebrow="Ports",
         title=f"Adani's ports handled {pct(last(P)[1], 0)} of India's port cargo in {last(P)[0]}, up from {pct(first(P)[1], 0)} in {first(P)[0]}",
         body=[
             f"The share rose in {rises} of the {len(P) - 1} years. The two steepest years were 2020-21 and 2021-22, when it went from {pct(P['2019-20'])} to {pct(P['2021-22'])}, the years Krishnapatnam, Dighi and Gangavaram joined the group.",
             "Most of the rise came from buying ports other companies built and ran, starting with Dhamra in June 2014, Kattupalli in June 2018, Krishnapatnam in October 2020, Dighi in February 2021, Gangavaram in stages to April 2021, Karaikal in April 2023 and Gopalpur in October 2024. Mundra, the group's first port, remains its largest.",
             "The company's own share claims match this calculation for the last three years. For 2020-21 the company says 25%; on the same official denominator its own cargo figure gives " + pct(P['2020-21']) + ".",
         ],
         method="The numerator is cargo at Adani Ports' Indian ports from its annual reports; from 2022-23 the company's headline figure also includes ports abroad, which are left out. The denominator is all cargo at major and non-major ports from the Ministry of Ports, Shipping and Waterways. Company and ministry figures for the same port differ a little (Mundra in 2023-24 handled 179.6 million tonnes in the company's report, 172.5 in the ministry's), so each side of the ratio comes from one source throughout. As a check from official figures alone, the non-major ports Adani ran in 2023-24 handled about 23% of the national total in the ministry's port-wise table; that leaves out Adani's terminals inside major ports, so it is a lower bound."),
    dict(slug="airports", chart="airports", eyebrow="Airports",
         title=f"The airports Adani runs carry {pct(last(A)[1], 0)} of India's air passengers, fewer than the {pct(first(A)[1], 0)} the same airports carried in {first(A)[0]}",
         body=[
             f"Adani took over Ahmedabad, Lucknow and Mangaluru from October 2020, Mumbai on 13 July 2021, and Jaipur, Guwahati and Thiruvananthapuram later in 2021. Navi Mumbai opened in 2025-26. Since 2022-23, the first full year with all seven, the share has stayed between {pct(min(v for k, v in A.items() if k >= '2022-23'))} and {pct(max(v for k, v in A.items() if k >= '2022-23'))}.",
             f"The share fell from {pct(A['2013-14'])} to {pct(A['2019-20'])} before Adani ran any of them, because traffic grew faster at other airports. What changed after 2020 is who runs them. One company now operates airports handling close to a quarter of passenger movements, Mumbai's among them.",
             f"Six of these airports came from one privatisation round in 2019. The Ministry of Civil Aviation records {bids} bids from {bidders} bidders, with the per-passenger fee as the bid, and Adani the highest bidder at all six. A group of secretaries decided on 17 November 2018 to set no cap on the number of airports one bidder could win, citing the six airports' {pct(six_share)} share of traffic. How the round was decided is the subject of Part 2.",
         ],
         method="Shares are of passenger movements at each airport in the Airports Authority of India's annual traffic tables, domestic and international together. AAI counts a passenger at both the airport they leave and the airport they reach, so the share is of airport throughput and does not count travellers. The same set of airports is used in every year so that the line follows the same airports through the change of owner. 2024-25 and 2025-26 are provisional."),
    dict(slug="coal-power", chart="coal", extra="coal_mw", eyebrow="Coal power",
         title=f"Adani Power runs {pct(last(apl_pvt)[1], 0)} of India's private coal power capacity, mostly bought in a market that stopped growing",
         body=[
             f"Private coal and lignite capacity grew fast to 2017-18 and then stopped. It was {pvt_mw['2017-18']:,.0f} MW in 2017-18 and {last(pvt_mw)[1]:,.0f} MW in {last(pvt_mw)[0]}. Over the same years Adani Power went from {apl_mw['2017-18']:,.0f} MW to {last(apl_mw)[1]:,.0f} MW.",
             f"The share therefore traced a U. It was {pct(apl_pvt['2013-14'])} in 2013-14, fell to {pct(min(apl_pvt.values()))} by 2018-19 while others built, and rose to {pct(last(apl_pvt)[1])} as Adani bought plants at Udupi in April 2015, Raipur and Raigarh in 2019-20, and Mahan in March 2022. Godda, 1,600 MW in Jharkhand, was built by the group and sells its power to Bangladesh.",
             f"Of all coal and lignite capacity, public and private, Adani Power's share is {pct(last(apl_all)[1])}.",
         ],
         method="Adani Power's capacity is its gross consolidated thermal capacity at 31 March from its annual reports, which counts subsidiaries in full. The denominators are the Central Electricity Authority's installed capacity reports for utilities at 31 March, which leave out captive plants. Adani Power's own share claims change basis between years (its 2024-25 figure leaves Godda out, its 2025-26 figure puts it in); this calculation includes Godda throughout from 2023-24. Whether the CEA counts Godda in Jharkhand's private capacity was not confirmed."),
    dict(slug="renewables", chart="green", eyebrow="Renewable power",
         title=f"Adani Green's share of India's renewable capacity has tripled since {first(agel)[0]}, to {pct(last(agel)[1])}",
         body=[
             f"Adani Green ran {first(agel_mw)[1]:,.0f} MW in {first(agel_mw)[0]} and {last(agel_mw)[1]:,.0f} MW in {last(agel_mw)[0]}, while renewable capacity excluding large hydro across India went from {res_mw['2017-18']:,.0f} MW to {last(res_mw)[1]:,.0f} MW.",
             "The share is of a market growing very fast, so it is the clearest case in this paper of a group gaining share by building. Adani Green's larger figures, such as a 'locked-in portfolio', count capacity contracted but not running, and are not used.",
         ],
         method="Operational capacity in MW (AC) at 31 March from Adani Green's annual reports, including its joint ventures with TotalEnergies in full. The denominator is renewable capacity excluding large hydro in the CEA and MNRE figures, which mix rooftop and off-grid capacity and do not always say whether they count AC or DC; the share is approximate to that extent. In the March 2025 report the renewables total is as of 31 January."),
    dict(slug="transmission", chart=None, eyebrow="Transmission",
         title=f"Adani is building or running {int(tbcb_ad)} of {int(tbcb_all)} competitively bid transmission projects, and owns under {pct(last(aesl)[1] + 0.5, 0)} of the grid",
         body=[
             f"The Central Electricity Authority's list of inter-state transmission projects awarded through tariff-based competitive bidding names Adani as the executing company on {int(tbcb_ad)} of {int(tbcb_all)} projects commissioned or under construction, {pct(100 * tbcb_ad / tbcb_all)} by count.",
             f"Adani Energy Solutions' operational network was {pct(first(aesl)[1])} of India's lines at 220 kV and above in {first(aesl)[0]} and {pct(last(aesl)[1])} in {last(aesl)[0]}. In the CEA's count, lines built by private companies and joint ventures of every owner were {pct(100 * jv_ckm / last(ckm)[1])} of the network in {last(ckm)[0]}; the rest belongs to central and state government utilities.",
         ],
         method="Project counts are from the CEA's September 2026 status report on competitively bid projects; they count projects and say nothing of kilometres or cost, and name the current executing company, so a project Adani bought counts as Adani's. One project lists its company only as 'Reliance', which the report does not identify, and is not attributed to Reliance Industries. Network shares are Adani's operational circuit kilometres over the CEA's all-India total at 220 kV and above; Adani's network includes some lower-voltage lines, so the share is an upper bound."),
    dict(slug="mobile", chart="telecom", extra="hhi", eyebrow="Telecom",
         title=f"Jio holds {pct(jio_ex, 0)} of India's mobile subscribers ten years after it launched, and the market is now highly concentrated",
         body=[
             f"In March 2016, before Jio's launch, TRAI listed {len(licensees.get('2015-16', ()))} mobile licensees with subscribers; in March 2026 it listed {len(licensees.get('2025-26', ()))}, Jio among them, the others having merged or stopped reporting. The concentration index rose from {first(hhi)[1]:,.0f} to {hhi_2026_ex:,.0f} over the same years. The 2023 United States Merger Guidelines treat a market above 1,800 as highly concentrated; Indian competition law sets no such threshold.",
             f"Jio and Airtel between them now have {pct(jio_ex + airtel_ex, 0)} of subscribers. The rest is mostly Vodafone Idea, itself the 2018 merger of two operators, and the state-owned BSNL.",
             "Jio grew by building its own network. A complaint that its launch pricing was predatory went to the Competition Commission in 2017 (Case 03 of 2017); the order could not be retrieved for this paper.",
         ],
         method="Shares are of reported mobile subscribers at the end of March in TRAI's monthly press releases, each operator over TRAI's printed all-India total; in every year the operators add up to that total. From March 2026 TRAI counts machine-to-machine SIMs, most of them Airtel's, so 2025-26 is shown without them. Reported subscribers include inactive connections, and the active share differs by operator (in March 2025, 96% of Jio's and 63% of BSNL's subscribers were active on the peak day), so the shares overstate some operators. The index sums the squared shares of every licensee."),
    dict(slug="telecom-revenue", chart="agr", eyebrow="Telecom",
         title=f"Jio earns {pct(jio_agr['2025-26'], 0)} of India's mobile and access-service revenue, and Jio and Airtel together {pct(jio_agr['2025-26'] + airtel_agr['2025-26'], 0)}",
         body=[
             f"Revenue tells the same story as subscribers with less noise, because an inactive SIM earns nothing. Jio's share went from {pct(jio_agr['2017-18'])} in 2017-18 to {pct(jio_agr['2018-19'])} a year later, and has stayed between {pct(min(v for k, v in jio_agr.items() if k >= '2019-20'))} and {pct(max(v for k, v in jio_agr.items() if k >= '2019-20'))} since. Airtel's has risen every year since 2018-19.",
             "Jio paid for the spectrum it uses in the government's auctions, paying " + "; ".join(f"Rs {inr(num(r))} crore in the {r['year']}" for r in spectrum) + ".",
         ],
         method="Adjusted gross revenue for access services, from TRAI's quarterly and annual performance reports, each operator over the total. 2016-17 to 2021-22 sum four quarters; later years use TRAI's annual figures. 2016-17 is left out of the chart because one-off receipts from spectrum surrendered by Videocon and Aircel inflate it."),
    dict(slug="refining", chart="refining", eyebrow="Refining",
         title=f"Reliance's share of India's refining capacity has fallen from {pct(max(ref.values()), 0)} in 2009 to {pct(last(ref)[1], 0)}",
         body=[
             f"Reliance's two Jamnagar refineries hold {pct(last(ref)[1])} of India's refining capacity on 1 April {last(ref)[0]}. The share jumped in 2009 when the second refinery opened and has drifted down since as public sector refiners added capacity; Reliance's own capacity has not changed since 2018.",
             "This is the one market in Part 1 where a Reliance share is falling. It also overstates Reliance's place in India's fuel market, because the second refinery sits in a special economic zone and mainly exports.",
         ],
         method="Installed capacity at 1 April from the Petroleum Planning and Analysis Cell, both Jamnagar refineries over all India. Nayara Energy's Vadinar refinery, nearby, is not Reliance's. Capacity is not crude processed; PPAC's throughput tables could not be read for this paper."),
    dict(slug="cement", chart="cement", eyebrow="Cement",
         title=f"The Adani group built India's second largest cement business in four years, almost entirely by acquisition",
         body=[
             f"The Adani family took control of Ambuja Cements and, through it, ACC from Holcim in September 2022. The group then bought Sanghi Industries (December 2023), Penna Cement (August 2024) and Orient Cement (April 2025). Consolidated capacity went from {cem['2023']:g} million tonnes a year in March 2023 to {last(cem)[1]:g} in March 2026.",
             f"UltraTech, the largest, had {last(ut)[1]:g}. Against the Economic Survey's figure of about {india_cem_last:g} million tonnes for all of India, the two together hold roughly {pct(100 * (last(ut)[1] + last(cem)[1]) / india_cem_last, 0)} of capacity and Adani about {pct(100 * last(cem)[1] / india_cem_last, 0)}. Those two shares are indicative only, because the national figure has no stated date and UltraTech's includes plants abroad.",
             "Cement is sold regionally, so national capacity shares say little about market power in any one region. The Competition Commission's orders on each acquisition would give regional shares; they could not be retrieved for this paper.",
         ],
         method="Consolidated capacity at 31 March from Ambuja Cements' and UltraTech's annual reports. Consolidation counts each subsidiary in full whatever the stake (Ambuja held 50.05% of ACC at acquisition, and about 73% of Orient by March 2026), so ownership-weighted capacity would be lower. Targets of 119 and 140 million tonnes in company material are plans and are not used."),
    dict(slug="city-gas", chart=None, eyebrow="City gas",
         title=f"Adani Total Gas supplies {pct(last(gas_png)[1], 0)} of India's piped household gas connections and runs {pct(last(gas_cng)[1], 0)} of its CNG stations",
         body=[
             f"Adani Total Gas holds licences for {E(ga[next(k for k in ga if 'Adani Total' in k)]['value'])} of the geographical areas the Petroleum and Natural Gas Regulatory Board has authorised, and its 50:50 joint venture with Indian Oil holds {E(ga[next(k for k in ga if 'Indian Oil' in k)]['value'])} more. The joint venture adds {pct(last(jv_png)[1])} of household connections and {pct(last(jv_cng)[1])} of CNG stations; it is kept separate here because Indian Oil owns half of it.",
             f"These shares have barely moved since 2020-21, with household connections between {pct(min(gas_png.values()))} and {pct(max(gas_png.values()))}, CNG stations between {pct(min(gas_cng.values()))} and {pct(max(gas_cng.values()))}. City gas is a sizeable business for the group without being a dominant one.",
         ],
         method="Area-by-area tables of the gas regulator, as reprinted in the Petroleum Planning and Analysis Cell's Ready Reckoner, summed by company over the printed national totals. The regulator's own site could not be reached, and no table was found for March 2016 to 2019, 2024 or 2025. The April 2026 table's rows add to about 2% more than its printed total, so the 2026 shares are indicative."),
    dict(slug="market-value", chart="mcap", eyebrow="Economic weight",
         title=f"The listed Adani companies went from {pct(mc_ad['2020'], 0)} to {pct(mc_ad['2022'], 0)} of India's stock market value in two years, and fell back after January 2023",
         body=[
             f"In March 2020 the listed Adani companies were worth {pct(mc_ad['2020'])} of all companies on the NSE; in March 2022, {pct(mc_ad['2022'])}. After the Hindenburg Research report of 24 January 2023 the share fell to {pct(mc_ad['2023'])} by March 2023, and was {pct(mc_ad['2025'])} in March 2025.",
             f"Reliance Industries alone was worth between {pct(min(mc_ril.values()))} and {pct(max(mc_ril.values()))} of the market across these years. By the size of its balance sheet it is much the larger group. A 2025 working paper by Dasgupta and Jayadev, using CMIE Prowess, puts Reliance at 11.3% of the assets of India's non-financial companies in 2023-24 and Adani at 2.5%, fourth among the five largest groups behind Tata and Aditya Birla.",
         ],
         method="Market capitalisation at the end of March from the exchanges' lists, over the exchange total in the RBI's Handbook of Statistics; 2025 uses BSE figures. The Adani sum includes ACC and NDTV as well as the companies that own them, so it counts those holdings twice; the double counting is small. Market value moves with share prices and measures what investors expect. A group's place in its markets is measured in the sector charts above."),
]


for f in FINDINGS:
    f.setdefault("part", 1)

WORDS = dict(enumerate("zero one two three four five six seven eight nine ten eleven twelve".split()))
bid_counts = [PP.nums(r)[0] for r in PP.CPL if r["sector"] == "coal" and "bidders" in r["event"] and "lost" not in r["event"]] + [1]
thin = sum(1 for n in bid_counts if n <= 2)
auction_rows = [r for r in PP.CPL if r["sector"] == "coal" and r["date"] >= "2020"]
lev_last = {k: v[sorted(v)[-1]] for k, v in PP.ND.items()}

FINDINGS += [
    dict(part=2, slug="coal-auctions", anchor="p2-coal", eyebrow="Coal", chart=None,
         html=PP.events_table(auction_rows, "Commercial coal auctions won by Adani companies"),
         title=f"{WORDS[thin].capitalize()} of the {WORDS[len(bid_counts)]} coal auctions Adani won with a published bidder count drew two bidders or fewer",
         body=[f"Adani companies won {len(PP.coal_auction)} mines in the Ministry of Coal's commercial auctions between 2020 and 2023. The ministry published the number of bidders for {len(bid_counts)} of them, and the counts were {', '.join(f'{n:.0f}' for n in sorted(bid_counts))}. Gondbahera Ujheni East went to an Adani company on a single bid at the second attempt, with the approval of the Empowered Committee of Secretaries.",
               "In one auction two Adani companies qualified for the same mine, which another bidder won. The ministry has said that no link between another bidder, Cavill Mining, and Adani has been established."],
         method="Bidder counts and winning offers from the Ministry of Coal's and the Nominated Authority's auction documents and press releases; ownership of the winning companies from Adani Enterprises' related-party disclosure to the BSE. Two auctions have no published bidder count and are left out of the count."),
    dict(part=2, slug="hasdeo", anchor="p2-coal", eyebrow="Coal", chart=None,
         html=PP.events_table([r for r in PP.CPL if r["sector"] == "coal" and r["date"] < "2020"], "Hasdeo Arand: the record"),
         title="A forest committee rejected the Hasdeo coal clearance in June 2011; the minister overruled it the next day",
         body=[f"The environment ministry's Forest Advisory Committee recommended on 22 June 2011 that {PP.fac_ha:,.0f} hectares of forest in Hasdeo Arand should not be diverted for the Parsa East and Kanta Basan blocks, which the Rajasthan state generation company holds and an Adani company mines. On 23 June the Minister of State for Environment granted first-stage clearance, giving six reasons.",
               "In March 2014 the National Green Tribunal sent the clearance back to the committee and suspended work. Permissions for the second phase were granted in 2022 and are under challenge in the Supreme Court and the Chhattisgarh High Court."],
         method="From the National Green Tribunal's judgment in Appeal 73 of 2012 (24 March 2014), which sets out the committee's recommendation and the minister's order, and the Tribunal's order of 28 May 2025. The reported Supreme Court stay of the Tribunal's suspension and the Chhattisgarh Assembly's 2022 resolution rest on press reports and are labelled as such."),
    dict(part=2, slug="airports-2018", anchor="p2-airports", eyebrow="Airports", chart=None,
         html=PP.events_table([r for r in PP.APT if r["sector"] == "airports"], "Airports: the record"),
         title="Adani won all six airports leased in 2018-19, in a round where the finance ministry and NITI Aayog had questioned the bid documents",
         body=["The rules for the round, set by an Empowered Group of Secretaries in November 2018, put no cap on how many airports one bidder could win and required no airport experience. Adani Enterprises quoted the highest fee per passenger at all six.",
               "Notes from the Department of Economic Affairs and NITI Aayog on 10 December 2018 asked for the bid terms to be reviewed and said the PPP guidelines' two-stage process had not been followed. The Kerala High Court held that the committees could overrule such notes and had considered them, and dismissed Kerala's challenge."],
         method="From the Kerala High Court's judgment of 19 October 2020 in W.P.(C) 2224 of 2019 and connected cases (paras 13, 31, 41-54), the Ministry of Civil Aviation's press note of 21 January 2021, the Cabinet decisions, and Lok Sabha answers of 2019 and 2024. The notes themselves and the per-passenger bids at five of the six airports were not found in any public record."),
    dict(part=2, slug="solar-award", anchor="p2-solar", eyebrow="Solar power", chart=None,
         html=PP.events_table([r for r in PP.CPL if r["sector"] == "renewables"], "The manufacturing-linked solar award"),
         title="One package of the 2019 solar tender drew no bids, and only Adani Green took the 4,000 MW moved from it",
         body=[f"The Solar Energy Corporation of India's tender of June 2019 linked 8,000 MW of solar power to building solar factories. The Central Electricity Regulatory Commission's order records that {E(PP.seci_bids)}, and that only Adani Green accepted the capacity moved from the package nobody bid for. The final award was {E(PP.seci_final)}.",
               f"Andhra Pradesh agreed to buy 7,000 MW in 2021 after the tariff was cut to Rs {PP.seci_cut:.2f} a unit. An objector told the Commission the ceiling tariff had been raised to accommodate the manufacturing condition; the Commission declined to examine the bidding structure and adopted the tariffs. This is the transaction behind the 2024 New York indictment, whose allegations are reported in Part 3 as allegations."],
         method="From CERC Order 286/AT/2021 of 2 April 2022, which records the bids, the transfer of capacity, the tariff revisions and the objections. The Andhra Pradesh cabinet decision is reported in the press and its order number was not found."),
    dict(part=2, slug="dharavi", anchor="p2-dharavi", eyebrow="Land", chart=None,
         html=PP.events_table([r for r in PP.CPL if r["sector"] == "land" and ("Dharavi" in r["event"] or "Seclink" in r["event"] or "CoS" in r["event"] or "GR " in r["event"])], "Dharavi: the record"),
         title=f"Dharavi went to Adani at Rs {PP.inr(PP.dh_new)} crore after a first tender with a higher Rs {PP.inr(PP.dh_old[0])} crore bid was cancelled",
         body=[f"In the first Dharavi tender, opened in January 2019, Seclink bid Rs {PP.inr(PP.dh_old[0])} crore and Adani Rs {PP.inr(PP.dh_old[1])} crore. Maharashtra cancelled it in 2020, on the ground that railway land had not been part of the bid. In the fresh tender of 2022, {E(PP.dh_bidders)}, and Adani was selected at Rs {PP.inr(PP.dh_new)} crore.",
               "The Bombay High Court dismissed Seclink's challenge in December 2024. It recorded Adani's argument that the two price bids measured different things, because the bid is the money a bidder commits to the project company."],
         method="All facts from the Bombay High Court's judgment in Writ Petition 4823 of 2022 (20 December 2024). The Supreme Court's notice on Seclink's appeal is reported in the press only."),
    dict(part=2, slug="transmission-bids", anchor="p2-transmission", eyebrow="Transmission", chart=None,
         html=PP.events_table([r for r in PP.CPL if r["sector"] == "transmission"], "Transmission awards on the record"),
         title="Where transmission auctions were open, Adani won by fractions of a percent",
         body=[f"For the first phase of the Khavda transmission lines, {E(PP.kh_resp)}; Adani won at Rs {PP.kh:,.2f} million a year against Power Grid's Rs 1,002.84 million. At Karur, Adani won at Rs {PP.kr:,.2f} million a year against Sterlite's Rs 184.01 million.",
               "Not every award in Part 2 was thin. These two were contested to the last rupee, and the paper reports them for that reason."],
         method="From the Central Electricity Regulatory Commission's tariff adoption orders for the two projects (May 2022). Only these two orders were read in full; the others would complete the picture."),
    dict(part=2, slug="jio-licence", anchor="p2-jio", eyebrow="Telecom", chart=None,
         html=PP.events_table([r for r in PP.REL if r["sector"].startswith("Telecom")], "Jio's licence: the record"),
         title=f"The federal auditor found that Jio's 2013 move to a voice licence gave it a Rs {PP.inr(PP.jio_adv)} crore advantage",
         body=[f"Infotel, which became Reliance Jio, won broadband spectrum in all 22 circles in 2010 as an internet licensee. In 2013 it moved to a unified licence permitting voice calls by paying Rs {PP.inr(PP.jio_fee)} crore, the fee set in 2001.",
               f"The Comptroller and Auditor General's Report No. 20 of 2015 found that the fee's value in 2013 was higher, that the company got an \"undue advantage\" of Rs {PP.inr(PP.jio_adv)} crore, and rejected the telecom department's explanation."],
         method="From CAG Report No. 20 of 2015, para 2.8, which sets out the auction, the committees' decisions and the computation. The Competition Commission's 2017 order on a predatory-pricing complaint could not be retrieved, and its reported outcome is labelled as such."),
    dict(part=2, slug="kg-d6", anchor="p2-kgd6", eyebrow="Oil and gas", chart=None,
         html=PP.events_table([r for r in PP.REL if r["sector"].startswith("Oil")], "KG-D6: the record"),
         title=f"The auditor could not validate Reliance's KG-D6 costs, and later put excess cost recovery at US$ {PP.kg_excess:,.0f} million",
         body=[f"The Comptroller and Auditor General's 2011 audit found that the whole KG-D6 block had been treated as a discovery area, so none was relinquished; that estimated development spending rose from US$ {PP.kg_capex[0]:g} billion to US$ {PP.kg_capex[1] + PP.kg_capex[2]:g} billion; and that {E(PP.kg_single)} high-value contracts went on single financial bids. The 2016 follow-up put excess cost recovery at US$ {PP.kg_excess:,.2f} million.",
               f"The auditor did not find that costs were inflated; it said it could not validate them. Separately, the arbitral award rejecting the government's gas-migration claim was set aside by the Delhi High Court in February 2025, and the petroleum ministry has demanded US$ {PP.kg_demand:g} billion."],
         method="From CAG Reports No. 19 of 2011-12, No. 24 of 2014 and No. 11 of 2016, and Reliance's stock exchange filings of February and March 2025 on the court outcome and the demand. The Justice A.P. Shah committee report was not retrieved."),
    dict(part=3, slug="leverage", anchor="p3-leverage", eyebrow="Debt", chart="leverage",
         title=f"Adani Green's net debt is {lev_last['Adani Green']:.1f} times a year's earnings and Adani Enterprises' {lev_last['Adani Enterprises']:.1f}; Adani Power and Adani Ports are under two",
         body=[f"Net debt as a multiple of a year's operating earnings differs widely across the Adani companies. In 2025-26 it was {lev_last['Adani Green']:.2f} at Adani Green, {lev_last['Adani Enterprises']:.2f} at Adani Enterprises, {lev_last['Adani Energy Solutions']:.2f} at Adani Energy Solutions, {lev_last['Adani Power']:.2f} at Adani Power and {lev_last['Adani Ports']:.2f} at Adani Ports. Reliance Industries was at {lev_last['Reliance Industries']:.2f}.",
               "Adani Power's fall from about eight times in 2016-17 is the largest change. The companies that are building fastest carry the most debt."],
         method="Consolidated borrowings, cash, bank balances and current investments, and earnings before interest, tax, depreciation and amortisation, from annual reports filed with the NSE (to 2021-22) and audited results (from 2022-23). Reliance uses the company's own net debt and EBITDA. A group total is not given because the companies' debts overlap."),
    dict(part=3, slug="lenders", anchor="p3-lenders", eyebrow="Debt", chart="pledges",
         title="By its own account, the Adani group replaced Indian bank loans with bonds and foreign banks, and its founders all but stopped borrowing against their shares",
         body=[f"In the group's investor presentation, Indian public-sector banks provided {PP.mix['PSU banks']['2016']:g}% of long-term debt in March 2016 and {PP.mix['PSU banks']['2024']:g}% in March 2024; private Indian banks went from {PP.mix['Private banks']['2016']:g}% to {PP.mix['Private banks']['2024']:g}%. Bonds, foreign banks and non-bank lenders took their place. This is the group's claim; public-sector bank exposure has never been officially disclosed.",
               f"Pledged founders' shares tell the same story. In March 2020 the founders had pledged {PP.PLEDGE['Adani Ports']['Mar 2020']:.0f}% of their Adani Ports holding; by March 2025 almost nothing. The group said its founders prepaid US$ {PP.prepay:g} billion of share-backed loans in early 2023."],
         method="Lender shares are read from a chart in Adani Ports' March 2025 investor presentation and are a company claim. Pledges are from the annual reports' MGT-9 tables (to 2020) and NSE shareholding filings (from September 2021)."),
    dict(part=3, slug="sebi-order", anchor="p3-legal", eyebrow="Regulation", chart=None,
         html=PP.events_table([r for r in PP.LEG if r["forum"].startswith("SEBI") or r["forum"].startswith("Supreme Court")], "SEBI and the Supreme Court: the record", text_key="event", extra="holding_or_outcome"),
         title="SEBI found the offshore-fund allegation \"not established\", and said what its evidence did not cover",
         body=["SEBI's final order of 28 September 2026 decided the central question raised in January 2023, which was whether offshore funds holding Adani shares were controlled by the founders' side, which would have breached the rule that a quarter of a listed company's shares be held by the public. It found the allegation not established, because there was no evidence that Vinod Adani directed the funds' investments.",
               "The order adds that there was no allegation that he financed the investments, and that the result could have been different if there had been. Two individuals linked to the funds were fined Rs 20 lakh each for incorrect or incomplete information. The companies, Gautam Adani and 13 directors settled for Rs 1.48 crore without admission."],
         method="From SEBI's final order WTM/KV/IVD-3/ID2/32734/2026-27 (paras 167 to 181) and its corrigendum, the Supreme Court's judgment of 3 January 2024 (para 67) and its order of 2 March 2023 (para 10)."),
    dict(part=3, slug="us-case", anchor="p3-legal", eyebrow="Courts", chart=None,
         html=PP.events_table([r for r in PP.LEG if r["forum"].startswith("US")], "United States: the record", text_key="event", extra="holding_or_outcome"),
         title="The US fraud charges against the Adanis were dismissed without a finding on the merits, and the SEC case ended in a settlement without admission",
         body=["The indictment unsealed in November 2024 charged Gautam Adani, Sagar Adani and Vneet Jaain with securities and wire fraud, and five others with bribery conspiracy. On 10 August 2026 the court dismissed the charges against the three, on the prosecutors' motion, with prejudice, stating that this expressed no opinion about the merits.",
               "The same day it entered a consent judgment in the SEC's civil case, under which Gautam Adani pays US$ 6 million and Sagar Adani US$ 12 million, without admitting or denying the allegations. The bribery charges against the five others remain before the court."],
         method="From the docket of United States v. Adani, 1:24-cr-00433 (E.D.N.Y.), entries 1, 23, 49 and 57, and SEC v. Adani, 1:24-cv-08080, entry 43. The Second Circuit's reported refusal to expedite the prosecutors' petition is from a secondary source."),
]

# ---------------------------------------------------------------- pages

ICONS = {
    "sun": '<svg class="i-sun" viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="4.5"/><path d="M12 2v2.5M12 19.5V22M2 12h2.5M19.5 12H22M4.9 4.9l1.8 1.8M17.3 17.3l1.8 1.8M4.9 19.1l1.8-1.8M17.3 6.7l1.8-1.8"/></svg><svg class="i-moon" viewBox="0 0 24 24" aria-hidden="true"><path d="M20 14.5A8 8 0 0 1 9.5 4a8 8 0 1 0 10.5 10.5z"/></svg>',
    "aa": '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M3 19 8 5l5 14M4.8 14h6.4M14.5 19l3.5-9 3.5 9M15.6 16.2h4.8"/></svg>',
    "menu": '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 7h16M4 12h16M4 17h16"/></svg>',
}
NAV = [("tracker.html", "Map"), ("projects.html", "Projects and sources"), ("paper/", "Paper"), ("findings/", "Findings"), ("index.html#data", "Download")]


def header(up, current):
    cur = ' aria-current="page"'
    links = "".join(f'      <a href="{up}{h}"{cur if h == current else ""}>{t}</a>\n' for h, t in NAV)
    return f'''<header class="top">
  <div class="wrap">
    <a class="brand" href="{up}index.html"><span class="brand-mark" aria-hidden="true"><i></i><i></i><i></i><i></i></span>Adani and Ambani</a>
    <nav class="nav" id="siteNav" aria-label="Site">
{links}    </nav>
    <div class="tools">
      <button type="button" class="tool" id="themeBtn" aria-label="Switch colour theme">{ICONS["sun"]}<span class="tool-l">Theme</span></button>
      <button type="button" class="tool" id="displayBtn" aria-expanded="false" aria-controls="displayPanel">{ICONS["aa"]}<span class="tool-l">Display</span></button>
      <button type="button" class="tool menu-btn" id="menuBtn" aria-expanded="false" aria-controls="siteNav">{ICONS["menu"]}<span class="tool-l">Menu</span></button>
    </div>
    <div class="display-panel" id="displayPanel" role="group" aria-label="Display settings" hidden>
      <div class="dp-row"><span class="dp-l" id="dp-theme">Colour theme</span>
        <div class="seg" role="group" aria-labelledby="dp-theme"><button type="button" data-theme-choice="system">Device</button><button type="button" data-theme-choice="light">Light</button><button type="button" data-theme-choice="dark">Dark</button></div></div>
      <div class="dp-row"><span class="dp-l" id="dp-font">Reading font</span>
        <div class="seg" role="group" aria-labelledby="dp-font"><button type="button" data-font-choice="standard">Standard</button><button type="button" data-font-choice="dyslexic">Dyslexia-friendly</button></div>
        <p class="dp-note">OpenDyslexic, with wider letter, word and line spacing. Remembered on this device.</p></div>
      <button type="button" class="dp-done" data-close>Done</button>
    </div>
  </div>
</header>'''


def page(up, current, title, description, body):
    icon = ("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 32 32'%3E%3Crect x='2' y='2' width='13' height='13' rx='2' fill='%23b42318'/%3E"
            "%3Crect x='17' y='2' width='13' height='13' rx='2' fill='%231d4ed8'/%3E%3Crect x='2' y='17' width='13' height='13' rx='2' fill='%231d4ed8'/%3E"
            "%3Crect x='17' y='17' width='13' height='13' rx='2' fill='%23b42318'/%3E%3C/svg%3E")
    return f'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{E(title)}</title>
<meta name="description" content="{E(description)}">
<link rel="icon" type="image/svg+xml" href="{icon}">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&family=JetBrains+Mono:wght@400;600&family=Source+Serif+4:ital,opsz,wght@0,8..60,400;0,8..60,600;1,8..60,400&display=swap" rel="stylesheet">
<link rel="stylesheet" href="{up}assets/site.css">
<script>
try {{ var t = localStorage.getItem('ind.theme'); if (t === 'dark' || t === 'light') document.documentElement.setAttribute('data-theme', t);
      if (localStorage.getItem('reading-font') === 'opendyslexic') document.documentElement.classList.add('dyslexic-font'); }} catch (_) {{}}
</script>
</head>
<body>
<!-- Written by scripts/build_paper.py from data/paper/. Edit the script or the data, not this file. -->

{header(up, current)}

<main>
<div class="wrap">
{body}
</div>
</main>

<footer class="foot">
  <div class="wrap">
    <span>&copy; <span id="copyrightYear"></span> <a href="https://www.impactmojo.in">ImpactMojo</a></span>
    <a href="https://github.com/Varnasr/industry-conglomerates-database">Source and data on GitHub</a>
    <span>Text and data CC BY 4.0</span>
  </div>
</footer>
<script src="{up}assets/site.js"></script>
</body>
</html>
'''


def finding_page(f, i):
    charts = "".join(CH[c].html() for c in (f.get("chart"), f.get("extra")) if c) + f.get("html", "")
    part_name = {1: "Part 1, Concentration", 2: "Part 2, How the assets were obtained", 3: "Part 3, Finance and risk"}[f["part"]]
    part_href = {1: f'../../paper/#{f["slug"]}', 2: f'../../paper/part-2/#{f.get("anchor", "")}', 3: f'../../paper/part-3/#{f.get("anchor", "")}'}[f["part"]]
    prev_f = FINDINGS[i - 1] if i > 0 else None
    next_f = FINDINGS[i + 1] if i + 1 < len(FINDINGS) else None
    pager = '<nav class="pager" aria-label="Other findings">' + (
        f'<a href="../{prev_f["slug"]}/"><span class="eyebrow">Previous</span>{E(prev_f["title"])}</a>' if prev_f else "<span></span>") + (
        f'<a href="../{next_f["slug"]}/" class="next"><span class="eyebrow">Next</span>{E(next_f["title"])}</a>' if next_f else "<span></span>") + "</nav>"
    body = f'''<article class="finding">
<p class="crumbs"><a href="../">Findings</a> · {E(f["eyebrow"])} · {part_name}</p>
<h1>{E(f["title"])}</h1>
{"".join(f"<p>{p}</p>" for p in f["body"][:1])}
{charts}
{"".join(f"<p>{p}</p>" for p in f["body"][1:])}
<section class="method" aria-labelledby="m-{f["slug"]}"><h2 id="m-{f["slug"]}">{"How this was measured" if f["part"] == 1 or f.get("chart") else "The documents"}</h2><p>{f["method"]}</p>
<p>Every figure above is in <a href="../../data/paper/">the data tables</a> with its source and page. Read the argument in full in <a href="{part_href}">{part_name.split(",")[0]} of the paper</a>.</p></section>
{pager}
</article>'''
    return page("../../", "findings/", f'{f["title"]} | {f["eyebrow"]} | Adani and Ambani', f["title"], body)


def findings_index():
    groups = []
    for part, name, lede in ((1, "Part 1, Concentration", "How much of each market the two groups hold, on official totals."),
                             (2, "Part 2, How the assets were obtained", "How the assets were obtained, and what auditors, regulators and courts recorded."),
                             (3, "Part 3, Finance and risk", "Debt, lenders, pledged shares, and what the regulators and courts decided.")):
        items = "".join(
            f'<li><a class="card" href="{f["slug"]}/"><span class="eyebrow">{E(f["eyebrow"])}</span><h3 class="h3">{E(f["title"])}</h3></a></li>'
            for f in FINDINGS if f["part"] == part)
        groups.append(f'<section class="stack" aria-labelledby="fg-{part}"><h2 id="fg-{part}">{E(name)}</h2><p class="note">{E(lede)}</p><ol class="finding-list">{items}</ol></section>')
    body = f'''<section class="stack" style="padding-block:40px 24px;border:0">
<div class="eyebrow">Findings</div>
<h1>What the record shows</h1>
<p class="lede">Each page takes one finding from the paper and shows the chart or the documents behind it. Every number and every event comes from a government, regulator, court or company document, listed with the page it came from.</p>
</section>
{"".join(groups)}'''
    return page("../", "findings/", "Findings | Adani and Ambani | ImpactMojo",
                "Findings from the paper on India's largest business houses, each with its chart or documents and sources.", body)


REFERENCES = [
    ("acharya", 'Acharya, Viral V. 2023. "India at 75: Replete with Contradictions, Brimming with Opportunities, Saddled with Challenges." <em>Brookings Papers on Economic Activity</em> 54(1): 185–215.', "https://www.brookings.edu/bpea-articles/emerging-market-challenges/"),
    ("commander", 'Commander, Simon, Saul Estrin, Naveen Joseph Thomas and Varun Lingineni. 2026. "Business Groups, Concentration and Market Power in India." <em>World Bank Economic Review</em>, advance article.', "https://doi.org/10.1093/wber/lhag026"),
    ("dasgupta", 'Dasgupta, Zico and Arjun Jayadev. 2025. "Economic Concentration in India: The Role of Financial Conditions." CSIE Working Paper, Azim Premji University.', "https://publications.azimpremjiuniversity.edu.in/6305/1/%23%202%20CSIE%20Working%20Paper.pdf"),
    ("dlgkp", 'De Loecker, Jan, Pinelopi K. Goldberg, Amit K. Khandelwal and Nina Pavcnik. 2016. "Prices, Markups, and Trade Reform." <em>Econometrica</em> 84(2): 445–510.', "https://doi.org/10.3982/ECTA11042"),
    ("deu", 'De Loecker, Jan, Jan Eeckhout and Gabriel Unger. 2020. "The Rise of Market Power and the Macroeconomic Implications." <em>Quarterly Journal of Economics</em> 135(2): 561–644.', "https://doi.org/10.1093/qje/qjz041"),
    ("wnm", 'Walton, Michael, Anusha Nath and Ashoka Mody. 2011. "Sources of Corporate Profits in India: Business Dynamism or Advantages of Entrenchment?" IMF Working Paper WP/11/8.', "https://doi.org/10.5089/9781455211869.001"),
    ("doj", 'U.S. Department of Justice and Federal Trade Commission. 2023. <em>Merger Guidelines</em>, section 2.1.', "https://www.justice.gov/atr/2023-merger-guidelines"),
]


def paper_page():
    sec = []
    sec.append(f'''<section class="stack" style="padding-block:40px 24px;border:0">
<div class="eyebrow">Working paper · Part 1 of 3</div>
<h1>How much of India's economy do Adani and Ambani hold?</h1>
<p class="lede">Part 1 measures concentration, meaning the share of each market the two groups hold, sector by sector, on official totals, and their weight in the economy as a whole. Parts 2 and 3 take up how the assets were obtained and how they are financed.</p>
<p class="byline">ImpactMojo · Draft of {E(last_updated())} · <a href="part-2/">Part 2, How the assets were obtained</a> · <a href="part-3/">Part 3, Finance and risk</a> · <a href="../data/paper/">Data and sources</a> · <a href="../findings/">Findings</a></p>
</section>
<nav class="toc" aria-label="Contents"><div class="eyebrow">Contents</div><ol>
<li><a href="#question">The question and the answer in brief</a></li>
<li><a href="#method">What is measured, and how</a></li>
<li><a href="#infrastructure">Adani in infrastructure</a></li>
<li><a href="#consumer">Reliance in telecom and fuel</a></li>
<li><a href="#weight">Weight in the economy</a></li>
<li><a href="#literature">What others have found</a></li>
<li><a href="#reading">How to read this</a></li>
<li><a href="#limits">Limits and next steps</a></li>
<li><a href="#refs">References</a></li>
</ol><p class="note" style="margin:10px 0 0">Also read <a href="part-2/">Part 2, How the assets were obtained</a> · <a href="part-3/">Part 3, Finance and risk</a></p></nav>''')
    sec.append(f'''<section id="question" class="paper-sec"><h2>1. The question and the answer in brief</h2>
<p>Public argument about the Adani and Reliance groups tends to run on two kinds of evidence, lists of what each group owns, and the wealth of the two men who control them. Neither says how much of any market the groups hold. A list of assets cannot tell a 3% share from a 30% one, and a fortune moves with share prices. This paper asks the narrower question that can be answered from public records. In each market where these groups are large, what share do they hold, measured against an official total, and how has it changed?</p>
<p>The answer differs by group and by market, which is the first thing worth knowing. Adani's position is a set of large but minority shares across infrastructure, with {pct(last(P)[1], 0)} of port cargo, {pct(last(A)[1], 0)} of airport passengers, {pct(last(apl_pvt)[1], 0)} of private coal power capacity, {pct(last(agel)[1], 0)} of renewable capacity, {pct(last(aesl)[1], 0)} of the high-voltage grid, about {pct(100 * last(cem)[1] / india_cem_last, 0)} of cement capacity and {pct(last(gas_png)[1], 0)} of household gas connections. In ports, coal power and cement, most of the growth since 2014 came from buying assets other companies had built. Reliance's position is narrower and deeper, with {pct(jio_ex, 0)} of mobile subscribers and {pct(jio_agr['2025-26'], 0)} of mobile revenue in a market now held largely by two firms, and {pct(last(ref)[1], 0)} of refining capacity, a share that has been falling.</p>
<p>No market in Part 1 is a monopoly, and the strongest form of the public claim, that two groups control the economy, is not supported by these figures. A weaker claim is supported. In ports, private coal power and mobile telecom, one of these groups now holds a quarter or more of the market, and in each the share has risen sharply within a decade.</p></section>''')
    sec.append('''<section id="method" class="paper-sec"><h2>2. What is measured, and how</h2>
<p>Every share in this paper is a numerator from the group's own filings, or from a regulator's table that names the company, over a denominator from a government source, which is the Ministry of Ports for cargo, the Airports Authority for passengers, the Central Electricity Authority for power and transmission, TRAI for telecom, the Petroleum Planning and Analysis Cell for refining and city gas, and the Economic Survey for cement. Where a company publishes its own market share, it is compared with the calculation and the difference is reported.</p>
<p>Four choices run through the paper and each moves the numbers.</p>
<ul>
<li><strong>Capacity or output.</strong> Power, refining and cement are measured by installed capacity, because that is what the government publishes by company. Capacity is not production, and it is not sales, which is what a competition authority usually measures.</li>
<li><strong>Operated or owned.</strong> Companies report subsidiaries and joint ventures in full whatever their stake. An Adani company that holds half a joint venture reports all of its capacity. This paper uses the reported figures and says "runs" or "operates"; an ownership-weighted share would be lower. The one exception is city gas, where the joint venture with Indian Oil is shown separately.</li>
<li><strong>National or regional.</strong> Every share here is national. Cement, city gas and power are sold in regional markets, where a group's share can be far higher or lower than its national one.</li>
<li><strong>Which Reliance.</strong> Reliance Industries is Mukesh Ambani's company. Reliance Power and Reliance Infrastructure belong to his brother Anil Ambani's separate group and are left out throughout.</li>
</ul>
<p>Every number printed here is computed from the tables in <a href="../data/paper/">data/paper</a>, where each row names its source document, publisher, address and page or table. Rows marked as derived are calculations made for this paper.</p></section>''')
    sec.append(f'''<section id="infrastructure" class="paper-sec"><h2>3. Adani in infrastructure</h2>
<h3 id="ports">3.1 Ports</h3>
<p>{FINDINGS[0]["body"][0]} {FINDINGS[0]["body"][1]}</p>
{CH["ports"].html()}
<p>{FINDINGS[0]["body"][2]}</p>
<h3 id="airports">3.2 Airports</h3>
<p>{FINDINGS[1]["body"][0]}</p>
{CH["airports"].html()}
<p>{FINDINGS[1]["body"][1]} {FINDINGS[1]["body"][2]}</p>
<h3 id="coal-power">3.3 Coal power</h3>
<p>{FINDINGS[2]["body"][0]} {FINDINGS[2]["body"][1]}</p>
{CH["coal"].html()}
{CH["coal_mw"].html()}
<p>{FINDINGS[2]["body"][2]} The group also mines coal. Its companies won {", ".join(E(r["value"]) for r in coal_won if "adani" in r["entity"].lower())} of the {E(coal_total["value"])} blocks sold in the Ministry of Coal's commercial auctions to July 2023, and it runs further mines under contract for state and central utilities, which own them.</p>
<h3 id="renewables">3.4 Renewable power</h3>
<p>{FINDINGS[3]["body"][0]}</p>
{CH["green"].html()}
<p>{FINDINGS[3]["body"][1]}</p>
<h3 id="transmission">3.5 Transmission</h3>
<p>{FINDINGS[4]["body"][0]} {FINDINGS[4]["body"][1]}</p>
<h3 id="cement">3.6 Cement</h3>
<p>{FINDINGS[8]["body"][0]}</p>
{CH["cement"].html()}
<p>{FINDINGS[8]["body"][1]} {FINDINGS[8]["body"][2]}</p>
<h3 id="city-gas">3.7 City gas</h3>
<p>{FINDINGS[9]["body"][0]} {FINDINGS[9]["body"][1]}</p>
<p>Across these seven markets the pattern is consistent. Adani holds between a twentieth and a quarter of each, and in ports, coal power and cement the share grew mainly through acquisition. Renewable power is the exception, built from scratch in a fast-growing market.</p></section>''')
    sec.append(f'''<section id="consumer" class="paper-sec"><h2>4. Reliance in telecom and fuel</h2>
<h3 id="mobile">4.1 Mobile telecom</h3>
<p>{FINDINGS[5]["body"][0]}</p>
{CH["telecom"].html()}
{CH["hhi"].html()}
<p>{FINDINGS[5]["body"][1]} {FINDINGS[5]["body"][2]}</p>
<h3 id="telecom-revenue">4.2 Telecom revenue</h3>
<p>{FINDINGS[6]["body"][0]}</p>
{CH["agr"].html()}
<p>{FINDINGS[6]["body"][1]}</p>
<h3 id="refining">4.3 Refining</h3>
<p>{FINDINGS[7]["body"][0]}</p>
{CH["refining"].html()}
<p>{FINDINGS[7]["body"][1]}</p>
<h3>4.4 Retail and media</h3>
<p>Reliance is also India's largest retailer by its own account and, since November 2024, the controlling owner of the media joint venture with Disney. Neither can be given a share here. No government body publishes the size of the organised retail market, and the retail segment's revenue in Reliance's accounts includes wholesale and device sales. The Competition Commission approved the Disney combination on 28 August 2024 subject to modifications the parties offered; its detailed order, which states market shares, could not be retrieved for this paper and will be added when it is.</p></section>''')
    sec.append(f'''<section id="weight" class="paper-sec"><h2>5. Weight in the economy</h2>
<p>{FINDINGS[10]["body"][0]}</p>
{CH["mcap"].html()}
<p>{FINDINGS[10]["body"][1]}</p>
<p>The two measures answer different questions. Market value is what investors expect the companies to earn; it rose fastest for Adani and fell fastest after January 2023. Assets measure what the companies hold now, and on that measure Reliance is several times the size of the Adani group.</p></section>''')
    sec.append('''<section id="literature" class="paper-sec"><h2>6. What others have found</h2>
<p>The best-known estimate is <a href="#ref-acharya">Acharya (2023)</a>. Using CMIE Prowess, he finds that the five largest groups (Reliance, Tata, Aditya Birla, Adani and Bharti) held about 10% of non-financial corporate assets in 1991 and nearly 18% in 2021, that they first spread across sectors and then, from 2015, deepened their shares within them, and that their markups rose relative to other firms. He describes the link to inflation as potentially causal and calls for further inquiry. His sector figures for telecom, retail and petroleum are shares of the top five firms in each sector, and are often quoted as if they were Reliance's alone; they are not.</p>
<p><a href="#ref-commander">Commander, Estrin, Thomas and Lingineni (2026)</a>, the main peer-reviewed study, find that concentration within narrowly defined industries fell between 2000 and 2020, while markups rose after 2013 and business groups' revenue grew relative to GDP. The two findings fit together. A group can hold modest shares in many markets and still weigh more in the economy as a whole. That is close to what Part 1 finds for Adani.</p>
<p><a href="#ref-dasgupta">Dasgupta and Jayadev (2025)</a> are the only source found that reports the groups separately, and on assets they put Reliance at 11.3% and Adani at 2.5%. Their paper is a working paper and has not been peer reviewed. An earlier IMF study, <a href="#ref-wnm">Walton, Nath and Mody (2011)</a>, found little sign before about 2010 that Indian firms profited from product-market power, which places the rise these studies describe in the last decade. Markup estimates of the kind Acharya uses come from <a href="#ref-deu">De Loecker, Eeckhout and Unger (2020)</a>; <a href="#ref-dlgkp">De Loecker and co-authors (2016)</a> show, with Indian data, that markups can rise when costs fall and prices do not follow, so a rise in markups is a reason to investigate and does not by itself show market power.</p></section>''')
    sec.append(f'''<section id="reading" class="paper-sec"><h2>7. How to read this</h2>
<p>The analytic position of this paper is that concentration should be measured market by market, on official totals, before it is argued about. On that measure, the picture is of two different kinds of business house. Reliance holds large shares in a few markets that households pay into every month, namely telephone service, fuel and, by its own account, retail. Adani holds large minority positions in physical infrastructure, in ports, airports, power plants, transmission lines, coal mines and cement, much of it infrastructure the state once built and ran, or now allocates through licences, concessions and auctions.</p>
<p>The second pattern is the reason Parts 2 and 3 exist. A share built by acquisition and by winning concessions raises different questions from one built by taking customers from rivals. They are questions about the terms on which public assets were transferred, the competitive bidding that allocated them, and the lending that paid for them. Part 1 establishes how large the positions are. It does not say how they were obtained, and nothing here should be read as a finding about that.</p></section>''')
    sec.append('''<section id="limits" class="paper-sec"><h2>8. Limits and next steps</h2>
<ul>
<li>The Competition Commission's detailed orders on the Reliance-Disney combination, the Holcim, Sanghi, Penna and Orient cement acquisitions, and the 2017 complaint against Jio could not be retrieved from outside India. They hold the Commission's own market definitions and shares and will be added.</li>
<li>The gas regulator's monthly reports and the Lok Sabha and Rajya Sabha answers on airport leases could not be retrieved for the same reason.</li>
<li>Capacity shares in power, refining and cement are not output or sales shares, and national shares are not regional ones.</li>
<li>Company figures count subsidiaries and joint ventures in full.</li>
<li>Most years for 2024-25 and 2025-26 are provisional and may be revised.</li>
</ul>
<p>Continue to <a href="part-2/">Part 2, on how the assets were obtained</a>, and <a href="part-3/">Part 3, on finance and the legal record</a>. Corrections are welcome on <a href="https://github.com/Varnasr/industry-conglomerates-database/issues">GitHub</a>.</p></section>''')
    refs = "".join(f'<li id="ref-{k}">{t} <a href="{E(u)}" rel="noopener">{E(u)}</a></li>' for k, t, u in REFERENCES)
    sec.append(f'<section id="refs" class="paper-sec"><h2>References</h2><ol class="refs">{refs}</ol><p class="note">Data sources for each figure are listed under its chart and, row by row, in the <a href="../data/paper/">data tables</a>.</p></section>')
    return page("../", "paper/", "How much of the economy do Adani and Ambani hold? Part 1 | ImpactMojo",
                "Part 1 of a working paper measuring the Adani and Reliance groups' shares of India's ports, airports, power, telecom, refining, cement and city gas on official totals.",
                "\n".join(sec))


def last_updated():
    return "29 October 2026"


SHEETS = [
    ("ports_airports", "Ports and airports", "Cargo at all Indian ports and at Adani's ports; passengers at every airport; the 2019 airport privatisation round."),
    ("power", "Power, transmission and coal", "CEA installed capacity and transmission; Adani Power, Adani Green and Adani Energy Solutions; coal blocks and mining contracts; Reliance's new energy business."),
    ("gas_telecom", "Telecom and city gas", "TRAI subscribers, broadband and revenue by operator; spectrum auctions; city gas connections and CNG stations by company."),
    ("cement_retail_media", "Cement, refining, retail and media", "PPAC refining capacity; cement capacity and acquisitions; Reliance Retail; the Reliance-Disney and Adani-NDTV transactions."),
    ("macro_weight", "Economic weight", "Market value, revenue, investment and debt of the listed Adani companies and Reliance Industries; GDP and investment; LIC's disclosed holdings."),
    ("airports_ports", "Part 2: airports and ports", "The 2019 airport round, the Mumbai airport transfer, and how each port was acquired, with the documents."),
    ("coal_power_land", "Part 2: coal, power and land", "Coal clearances and auctions, Godda, the solar award, Dharavi, transmission bids and Mundra, as dated events."),
    ("reliance_state", "Part 2: Reliance and the state", "KG-D6 audits and disputes, Jio's licence, retail and media approvals, and electoral bond purchases."),
    ("finance", "Part 3: debt and financing", "Borrowings, cash, net debt and earnings by company, lender mix, pledged shares, ratings and the 2023 episode."),
    ("legal", "Part 3: the legal record", "Dated court and regulatory steps from January 2023 to October 2026, each marked primary or secondary."),
]


def data_page():
    cards = "".join(
        f'<li class="card"><div class="eyebrow">{len(T[n])} rows</div><h2 class="h3">{E(t)}</h2><p>{E(d)}</p><a class="go" href="{n}.csv" download>Download {n}.csv</a></li>'
        for n, t, d in SHEETS if n in T)
    total = sum(len(T[n]) for n, _, _ in SHEETS if n in T)
    body = f'''<section class="stack" style="padding-block:40px 24px;border:0">
<div class="eyebrow">Data</div>
<h1>The tables behind the paper</h1>
<p class="lede">{total:,} rows, each with the title of the document it came from, the publisher, the address and the page or table. A row whose source begins "Derived" is a calculation made for this paper from other rows. In the Part 2 and Part 3 tables, a row resting on a press report alone says so.</p>
</section>
<ul class="cards data-cards">{cards}</ul>
<section class="stack"><h2>Columns</h2>
<dl class="dict">
<dt>sector</dt><dd>The market the row belongs to.</dd>
<dt>metric</dt><dd>What is measured, in words.</dd>
<dt>entity</dt><dd>The company, group or total the figure is for.</dd>
<dt>year</dt><dd>The date or period, as the source states it. Indian financial years run April to March and are written 2023-24.</dd>
<dt>value, unit</dt><dd>The figure and its unit.</dd>
<dt>source_title, publisher, url, locator</dt><dd>The document, who published it, where it is, and the page, table or paragraph.</dd>
<dt>note</dt><dd>Definitions, traps and whether the figure is derived.</dd>
</dl>
<p>The figures each chart draws are also in <a href="series.csv" download>series.csv</a>. The paper and its pages are written from these tables by <code>scripts/build_paper.py</code> in the <a href="https://github.com/Varnasr/industry-conglomerates-database">repository</a>, so a corrected row changes every page that uses it.</p>
</section>'''
    return page("../../", "", "Data | Adani and Ambani | ImpactMojo",
                "The sourced tables behind the paper on India's largest business houses.", body)


def series_csv():
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\n")
    w.writerow(["chart", "series", "period", "value", "unit"])
    for c in CH.values():
        for name, _, d in c.lines:
            for k in c.xs:
                if d.get(k) is not None:
                    w.writerow([c.title, name, k, f"{d[k]:g}", c.unit])
    return buf.getvalue()


def outputs():
    out = {ROOT / "paper" / "index.html": paper_page(),
           ROOT / "findings" / "index.html": findings_index(),
           ROOT / "paper" / "part-2" / "index.html": page("../../", "paper/", "How the assets were obtained, Part 2 | Adani and Ambani | ImpactMojo",
                "Part 2 of a working paper: how the Adani and Reliance groups obtained their assets, and what auditors, regulators and courts recorded.",
                PP.part2_body(CH, Chart)),
           ROOT / "paper" / "part-3" / "index.html": page("../../", "paper/", "Finance and risk, Part 3 | Adani and Ambani | ImpactMojo",
                "Part 3 of a working paper: debt, lenders, pledged shares, and the regulatory and court record on the Adani and Reliance groups.",
                PP.part3_body(CH, Chart)),
           ROOT / "data" / "paper" / "index.html": data_page(),
           ROOT / "data" / "paper" / "series.csv": series_csv()}
    for i, f in enumerate(FINDINGS):
        out[ROOT / "findings" / f["slug"] / "index.html"] = finding_page(f, i)
    return out


def main():
    check = "--check" in sys.argv[1:]
    stale = []
    for path, text in outputs().items():
        if not path.exists() or path.read_text(encoding="utf-8") != text:
            stale.append(str(path.relative_to(ROOT)))
            if not check:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(text, encoding="utf-8")
    if check and stale:
        print("FAIL - out of date with data/paper: " + ", ".join(stale))
        print("Run: python3 scripts/build_paper.py")
        sys.exit(1)
    print(("PASS - paper pages match" if check else "wrote paper pages from") + f" data/paper ({len(FINDINGS)} findings, {len(CH)} charts)")


if __name__ == "__main__":
    main()
