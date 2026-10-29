"""Parts 2 and 3 of the paper, written from data/paper/. Imported by build_paper.py.

Part 2 is a record of decisions, so most of it is dated events: who decided
what, by which process, what an auditor or court recorded. Rows that rest on a
press report alone are shown with a label and never carry a finding.
"""
import csv
import html
import re
from pathlib import Path

E = html.escape
DATA = Path(__file__).resolve().parent.parent / "data" / "paper"


def load(name):
    p = DATA / f"{name}.csv"
    if not p.exists():
        return []
    with p.open(newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


CPL = load("coal_power_land")
REL = load("reliance_state")
APT = load("airports_ports")
FIN = load("finance")
LEG = load("legal")
MAC = load("macro_weight")


def reported(r):
    pub = r.get("publisher", "").lower()  # the airports and ports table records provenance here
    if any(k in pub for k in ("news report", "not retrieved", "primary not found", "blog")):
        return True
    if r.get("sector") in ("airports", "ports") and "status_note" not in r:
        return False  # its notes say "reported" of facts a primary document does record
    return "REPORTED" in (r.get("note", "") + r.get("source_title", "") + r.get("status_note", "")).upper() \
        or r.get("status_note", "").lower().startswith("secondary")


def ev(rows, text):
    hit = [r for r in rows if text.lower() in r.get("event", "").lower()]
    if not hit:
        raise SystemExit(f"no event: {text}")
    return hit[0]


def nums(r):
    return [float(x.replace(",", "")) for x in re.findall(r"-?\d[\d,]*\.?\d*", r["value"])]


def inr(v):
    whole = f"{v:.0f}"
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


def src_link(r):
    t = E(r["source_title"])
    loc = E(r.get("locator", ""))
    if r.get("url", "").startswith("http"):
        t = f'<a href="{E(r["url"])}" rel="noopener">{t}</a>'
    return t + (f", {loc}" if loc else "")


def events_table(rows, caption, date_key="date", text_key="event", extra=None):
    """A dated table of decisions, each with its document. Press-only rows are labelled."""
    body = []
    for r in sorted(rows, key=lambda r: r[date_key]):
        tag = ' <span class="chip none">Secondary source</span>' if reported(r) else ""
        what = E(r[text_key])
        if extra and r.get(extra):
            what += f'<div class="ev-note">{E(r[extra])}</div>'
        val = ""
        if r.get("value", "").strip() and r.get("unit", "").strip():
            val = f'<div class="ev-val">{E(r["value"])} {E(r["unit"])}</div>'
        body.append(f'<tr><td class="ev-date">{E(r[date_key])}</td><td>{what}{val}{tag}</td><td class="ev-src">{src_link(r)}</td></tr>')
    return (f'<figure class="events"><figcaption class="chart-title">{E(caption)}</figcaption>'
            f'<div class="table-scroll" tabindex="0" role="region" aria-label="{E(caption)}"><table>'
            f'<thead><tr><th scope="col">Date</th><th scope="col">What the record shows</th><th scope="col">Document</th></tr></thead>'
            f'<tbody>{"".join(body)}</tbody></table></div></figure>')


# ---------------------------------------------------------------- Part 2 numbers

dh_old = nums(ev(CPL, "Earlier Dharavi tender"))          # Seclink, Adani
dh_new = nums(ev(CPL, "CoS selects Adani Properties"))[0]
dh_bidders = ev(CPL, "Fresh Dharavi tender: bidders")["value"]

seci_bids = ev(CPL, "Bids received under manufacturing-linked tender")["value"]
seci_final = ev(CPL, "Final awarded capacity")["value"]
seci_cut = nums(ev(CPL, "Voluntary tariff cut for Packages II-IV"))[0]

coal_auction = [r for r in CPL if r["sector"] == "coal" and "MDO" not in r["event"]
                and re.search(r"won by|to (Adani|CG|MH)|allocated on single bid", r["event"])]
single_bid = ev(CPL, "allocated on single bid")
gondulpara_bidders = nums(ev(CPL, "qualified bidders for Gondulpara"))[0]

fac = ev(CPL, "Forest Advisory Committee rejects")
fac_ha = nums(fac)[0]

kh = nums(ev(CPL, "Khavda 3 GW Phase-I: Adani L-1"))[0]
kh_resp = ev(CPL, "Khavda 3 GW Phase-I TBCB: responses")["value"]
kr = nums(ev(CPL, "Karur/Tiruppur"))[0]

mund_mangrove = nums(ev(CPL, "Committee finds mangrove loss"))[0]

kg_spent, kg_recovered = nums(ev(REL, "Block expenditure and cost recovery"))[:2]
kg_excess = nums(ev(REL, "excess cost recovery"))[0]
kg_capex = nums(ev(REL, "D1-D3 development plan capex"))
kg_single = ev(REL, "single financial bids")["value"]
kg_demand = nums(ev(REL, "MoPNG demand"))[0]
jio_fee = nums(ev(REL, "Migration of ISP-BWA licensee"))[0]
jio_adv = nums(ev(REL, "CAG finding on migration fee"))[0]
jio_bwa = nums(ev(REL, "BWA auction: Infotel"))[0]
qwik = nums(ev(REL, "Electoral bond purchases by Qwik Supply Chain"))[0]
fut = nums(ev(REL, "RRVL agrees to acquire Future Group"))[0]


# ---------------------------------------------------------------- Part 3 numbers

def fin(metric, entity=None):
    out = {}
    for r in FIN:
        if r["metric"] == metric and (entity is None or entity.lower() in r["entity"].lower()):
            out[r["year"]] = float(r["value"])
    return out


def fy(label):
    y = int(re.search(r"(20\d\d)", label).group(1))
    return f"{y - 1}-{str(y)[2:]}"


ND = {}
for name, key in (("Adani Enterprises", "Adani Enterprises"), ("Adani Ports", "Adani Ports"), ("Adani Power", "Adani Power"),
                  ("Adani Green", "Adani Green"), ("Adani Energy Solutions", "Adani Energy Solutions")):
    ND[name] = {fy(k): v for k, v in fin("Net debt / EBITDA, derived", key).items()}
ND["Reliance Industries"] = {fy(k): v for k, v in fin("Net debt / EBITDA, derived (company net debt / company EBDIT)", "RIL").items()}

PLEDGE = {}
for name, key in (("Adani Ports", "Adani Ports"), ("Adani Enterprises", "Adani Enterprises"),
                  ("Adani Energy Solutions", "Adani Energy Solutions"), ("Adani Power", "Adani Power")):
    d = {}
    for k, v in fin("Promoter shares pledged or encumbered, % of promoter holding (derived)", key).items():
        d["Mar " + k[:4]] = v
    for k, v in fin("Promoter shares pledged or encumbered, % of promoter holding", key).items():
        mon = {"MAR": "Mar", "SEP": "Sep", "DEC": "Dec", "JUN": "Jun"}[k[3:6]]
        if mon in ("Mar", "Dec") or k.startswith("30-SEP-2021"):
            d[f"{mon} {k[-4:]}"] = v
    PLEDGE[name] = d
order = lambda s: (int(s[-4:]), {"Mar": 3, "Jun": 6, "Sep": 9, "Dec": 12}[s[:3]])
PLEDGE_X = sorted({k for d in PLEDGE.values() for k in d}, key=order)

mix = {}
for r in FIN:
    if r["metric"] == "Adani portfolio long-term debt mix, share":
        mix.setdefault(r["entity"].replace("Adani portfolio: ", ""), {})[r["year"][:4]] = float(r["value"])
gqg = float(next(r for r in FIN if r["metric"].startswith("GQG Partners"))["value"])
fpo = float(next(r for r in FIN if r["metric"] == "FPO size (partly paid equity), up to")["value"])
prepay = float(next(r for r in FIN if r["metric"].startswith("Margin-linked"))["value"])
lic = {r["metric"]: r for r in MAC if r["sector"] == "lic_banks"}
lic_mv = float(lic["LIC market value of Adani group equity holdings"]["value"])
lic_cost = float(lic["LIC purchase value of equity, all Adani group companies"]["value"])
lic_2025 = float([r for r in MAC if r["metric"] == "LIC equity + debt holding, book value, total" and r["year"].startswith("2025")][0]["value"])
mcap_fall = next(r for r in MAC if r["metric"].startswith("Decline in market capitalisation"))
moodys = [r for r in FIN if r["sector"] == "ratings" and r["year"] == "2023-02-10" and "Negative" in r["value"]]

ril_nd = {r["metric"]: r for r in FIN if r["entity"] == "RIL" and ("net-debt-free" in r["metric"] or "31 Mar 2020" in r["metric"])}


# ---------------------------------------------------------------- pages


def part2_body(CH, Chart):
    s = []
    s.append('''<section class="stack" style="padding-block:40px 24px;border:0">
<div class="eyebrow">Working paper · Part 2 of 3</div>
<h1>How the Adani and Reliance assets were obtained</h1>
<p class="lede">Part 1 measured how large the two groups' positions are. Part 2 asks how they were obtained, whether by auction, by concession, by acquisition, or by a regulatory decision, and what auditors, regulators and courts recorded about each.</p>
<p class="byline">ImpactMojo · Draft of 29 October 2026 · <a href="../">Part 1</a> · <a href="../part-3/">Part 3</a> · <a href="../../data/paper/">Data and sources</a></p>
</section>
<nav class="toc" aria-label="Contents"><div class="eyebrow">Contents</div><ol>
<li><a href="#p2-method">What a document can show</a></li>
<li><a href="#p2-airports">Airports and ports</a></li>
<li><a href="#p2-coal">Coal</a></li>
<li><a href="#p2-solar">The manufacturing-linked solar award</a></li>
<li><a href="#p2-godda">Godda</a></li>
<li><a href="#p2-dharavi">Dharavi</a></li>
<li><a href="#p2-transmission">Transmission, where the bidding was close</a></li>
<li><a href="#p2-mundra">Land at Mundra</a></li>
<li><a href="#p2-kgd6">The KG-D6 gas field</a></li>
<li><a href="#p2-jio">Jio's licence</a></li>
<li><a href="#p2-retail">Reliance in retail and media</a></li>
<li><a href="#p2-bonds">Political finance</a></li>
<li><a href="#p2-reading">What the record adds up to</a></li>
</ol></nav>''')
    s.append(f'''<section id="p2-method" class="paper-sec"><h2>1. What a document can show</h2>
<p>A government record can show who decided, when, by what process, what was bid or paid, what an official body objected to, and what a court held. It cannot show why a decision-maker chose as they did. Part 2 therefore reports processes and recorded findings, and makes no claim about motive. Three kinds of statement are kept apart throughout. They are decisions and holdings, which are facts about the record; findings by an auditor or regulator, which are that body's conclusions; and allegations, which are reported as allegations and never as findings.</p>
<p>Every event below is in the <a href="../../data/paper/">data tables</a> with its document and page. Where a fact rests on a press report alone, the table says so and the text does not rely on it.</p></section>''')
    # airports and ports
    ap_rows = [r for r in APT]
    s.append(f'''<section id="p2-airports" class="paper-sec"><h2>2. Airports and ports</h2>
{airports_text()}
{events_table(ap_rows, "Airports and ports: the record") if ap_rows else ""}</section>''')
    s.append(f'''<section id="p2-coal" class="paper-sec"><h2>3. Coal</h2>
<p>The Adani group reaches coal by two routes. It operates mines that state and central utilities own, as mine developer and operator, and since 2020 it has bought mines outright in the Ministry of Coal's commercial auctions.</p>
<h3>3.1 Hasdeo Arand</h3>
<p>Parsa East and Kanta Basan in Chhattisgarh's Hasdeo Arand forest were allocated to the Rajasthan state generation company in 2007, with an Adani company as mine operator and majority partner in the mining joint venture. On 22 June 2011 the environment ministry's Forest Advisory Committee recommended rejecting the diversion of {fac_ha:,.0f} hectares of forest for these blocks. The next day the Minister of State for Environment overruled the committee and granted first-stage clearance. In March 2014 the National Green Tribunal sent the clearance back to the committee and suspended work; that suspension is reported to have been stayed by the Supreme Court. The Supreme Court's 2014 order cancelling coal allocations nationally included these blocks, and the Ministry of Coal's later records treat the same state company as the prior allottee. The second phase received fresh permissions in 2022 and is under challenge in the Supreme Court and the Chhattisgarh High Court.</p>
<h3>3.2 Commercial auctions</h3>
<p>Adani companies won {len([r for r in coal_auction])} mines in the Ministry of Coal's commercial auctions between 2020 and 2023. Where the ministry published the number of bidders, most of these auctions drew two. Gondulpara drew {gondulpara_bidders:.0f} qualified bidders and Bijahan six. Gondbahera Ujheni East went to an Adani company on a single bid at the second attempt, with the approval of the Empowered Committee of Secretaries; the ministry records that eleven mines in all were allotted that way across the auctions. In one auction two Adani companies both qualified for the same mine, which another bidder won.</p>
{events_table([r for r in CPL if r["sector"] == "coal"], "Coal: the record")}</section>''')
    s.append(f'''<section id="p2-solar" class="paper-sec"><h2>4. The manufacturing-linked solar award</h2>
<p>In June 2019 the Solar Energy Corporation of India tendered 8,000 MW of solar power linked to building 2,000 MW of solar manufacturing. The Central Electricity Regulatory Commission's order of 2 April 2022 records that {E(seci_bids)}. Capacity from the package nobody bid for was moved to the other, and only Adani Green accepted it. The final award was {E(seci_final)}.</p>
<p>No state signed to buy the power until 2021. After the developers cut their tariff to Rs {seci_cut:.2f} a unit, Andhra Pradesh agreed to buy 7,000 MW and its regulator approved the purchase on 11 November 2021. An objector told the Commission that the ceiling tariff had been raised from Rs 2.75 to Rs 2.93 to make room for the manufacturing condition; the Commission declined to examine how the bidding had been structured and adopted the tariffs.</p>
<p>This is the transaction behind the 2024 indictment in New York. What the indictment alleges is set out in Part 3, as allegation. The record above does not depend on it.</p>
{events_table([r for r in CPL if r["sector"] == "renewables"], "Solar award: the record")}</section>''')
    s.append(f'''<section id="p2-godda" class="paper-sec"><h2>5. Godda</h2>
<p>Adani Power's 1,600 MW plant at Godda in Jharkhand sells all its output to Bangladesh. The commerce ministry notified a power special economic zone of 222.668 hectares for it in September 2019, which carries the tax treatment of an export unit. In August 2024 the Ministry of Power amended its cross-border electricity guidelines so that a plant built only to export can be connected to India's grid if its foreign buyer stops scheduling power or defaults. Godda is the only such plant the paper found. The earlier steps (the SEZ board's rejection in 2018 and approval in 2019, the Jharkhand agreement) rest on press reports, and are shown as such.</p>
{events_table([r for r in CPL if r["sector"] == "power"], "Godda: the record")}</section>''')
    s.append(f'''<section id="p2-dharavi" class="paper-sec"><h2>6. Dharavi</h2>
<p>The Bombay High Court's judgment of 20 December 2024 sets out how the Dharavi redevelopment was awarded. In the first tender, opened in January 2019, Seclink bid Rs {inr(dh_old[0])} crore and Adani Rs {inr(dh_old[1])} crore. The state cancelled that tender in 2020, on the ground that railway land had not been part of the bid documents. The fresh tender of 2022 added the railway land and further concessions; {E(dh_bidders)}. Adani was selected at Rs {inr(dh_new)} crore. The court dismissed Seclink's challenge, and recorded Adani's argument that the two price bids measured different things. A further challenge is reported to be before the Supreme Court.</p>
{events_table([r for r in CPL if r["sector"] == "land" and "Dharavi" in r["event"] or (r["sector"] == "land" and "Seclink" in r["event"])], "Dharavi: the record")}</section>''')
    s.append(f'''<section id="p2-transmission" class="paper-sec"><h2>7. Transmission, where the bidding was close</h2>
<p>Not every award was thin. The two transmission auctions examined in full were contested to the last rupee. For the first phase of the Khavda lines, {E(kh_resp)}, and Adani won at Rs {kh:,.2f} million a year against Power Grid's Rs 1,002.84 million. At Karur, Adani won at Rs {kr:,.2f} million against Sterlite's Rs 184.01 million. Adani's 2018 purchase of Mumbai's electricity business was from Reliance Infrastructure, Anil Ambani's company, and was approved by the Maharashtra regulator.</p>
{events_table([r for r in CPL if r["sector"] == "transmission"], "Transmission awards on the record")}</section>''')
    s.append(f'''<section id="p2-mundra" class="paper-sec"><h2>8. Land at Mundra</h2>
<p>A committee constituted by the environment ministry in 2012 reported in April 2013 that {mund_mangrove:.0f} hectares of mangrove had been lost at Bocha Island near the Mundra port, and recommended a restoration fund of Rs 200 crore or 1% of project cost. It also recorded that grazing land at Zarpara village had been taken back by the state for the SEZ in 2007. No audit by the Comptroller and Auditor General finding land allotted to Adani at concessional rates was found. One reported audit figure on forest land valuation could not be confirmed from the report itself and is not used.</p>
{events_table([r for r in CPL if r["sector"] == "land" and "Dharavi" not in r["event"] and "Seclink" not in r["event"]], "Mundra and other land: the record")}</section>''')
    s.append(f'''<section id="p2-kgd6" class="paper-sec"><h2>9. The KG-D6 gas field</h2>
<p>Reliance won the KG-D6 block in 2000. Three audits by the Comptroller and Auditor General followed. The 2011 audit found that the whole 7,645 square kilometre block had been treated as a discovery area, so none of it was given back as the contract required; that the development plan's cost estimate rose from US$ {kg_capex[0]:g} billion to US$ {kg_capex[1]:g} billion plus {kg_capex[2]:g} billion; that {E(kg_single)} high-value contracts were awarded on single financial bids; and that the profit-sharing formula gave the contractor a reason to spend early. The 2014 audit found US$ {kg_spent:,.0f} million spent and US$ {kg_recovered:,.0f} million recovered as cost by March 2013. The 2016 follow-up put excess cost recovery at US$ {kg_excess:,.2f} million.</p>
<p>The auditor did not find that costs were inflated. It said it could not yet validate them. The separate dispute over gas that migrated from ONGC's blocks went to arbitration, where Reliance won in 2018; the Delhi High Court upheld that award in 2023 and a Division Bench set it aside in February 2025, after which the petroleum ministry demanded US$ {kg_demand:g} billion. The appeal is in the Supreme Court.</p>
{events_table([r for r in REL if r["sector"].startswith("Oil")], "KG-D6: the record")}</section>''')
    s.append(f'''<section id="p2-jio" class="paper-sec"><h2>10. Jio's licence</h2>
<p>Jio began as Infotel, an internet licensee that won broadband spectrum in all 22 circles in the 2010 auction for Rs {inr(jio_bwa)} crore. In 2013 it moved to a unified licence that allowed voice calls, paying a migration fee of Rs {inr(jio_fee)} crore, the price set in 2001. The Comptroller and Auditor General's Report No. 20 of 2015 found that this gave the company an "undue advantage" of Rs {inr(jio_adv)} crore, because the fee took no account of the time value of money, and rejected the telecom department's reply. TRAI later cut the charge an operator pays another to complete its customers' calls, from 14 paise a minute to 6 in 2017 and to zero from 2021; the lower the charge, the less an operator whose customers make more calls than they receive pays out. The Competition Commission closed a predatory-pricing complaint against Jio in 2017; that order could not be retrieved, and its outcome is shown as reported.</p>
{events_table([r for r in REL if r["sector"].startswith("Telecom")], "Jio: the record")}</section>''')
    s.append(f'''<section id="p2-retail" class="paper-sec"><h2>11. Reliance in retail and media</h2>
<p>Reliance agreed in 2020 to buy Future Group's retail and logistics businesses for Rs {inr(fut)} crore. Amazon, an investor in a Future company, objected; the Supreme Court held in August 2021 that the emergency arbitrator's order in Amazon's favour was enforceable, and the deal lapsed in April 2022 when Future's secured creditors voted against it. The Disney media merger was approved by the Competition Commission in August 2024 subject to modifications the parties offered.</p>
{events_table([r for r in REL if r["sector"].startswith(("Retail", "Media"))], "Retail and media: the record")}</section>''')
    s.append(f'''<section id="p2-bonds" class="paper-sec"><h2>12. Political finance</h2>
<p>The Supreme Court struck down electoral bonds in February 2024 and ordered the State Bank of India to disclose purchases, which the Election Commission published in March 2024. Qwik Supply Chain Private Limited bought bonds worth Rs {qwik:.0f} crore between January 2022 and November 2023. News reports linked the company to Reliance through a director and its registered address; Reliance said it is not a subsidiary of any Reliance company. No official filing establishing or ruling out the link was found, so the paper records the purchases and treats the link as reported. No purchaser in the published list carries the name Adani or Reliance, which does not rule out companies trading under other names.</p>
{events_table([r for r in REL if r["sector"].startswith("Political")], "Electoral bonds: the record")}</section>''')
    s.append('''<section id="p2-reading" class="paper-sec"><h2>13. What the record adds up to</h2>
<p>Read together, the documents show three patterns. First, several of the Adani group's largest positions came through processes with few bidders or a single one, among them two-bidder coal auctions and a single-bid allotment, a solar tender where one package drew no bids and only Adani took the transferred capacity, and a Dharavi re-tender with two qualified bidders after a higher first bid was cancelled. Second, at decisive points an official body's objection was overruled or not examined, as with the forest committee in 2011, and the bidding structure the regulator declined to review in 2022. Third, where bidding was open and contested, as in the transmission auctions, Adani won on price by fractions of a percent.</p>
<p>For Reliance, the record is older and more about terms than about allocation. It covers the terms of a gas contract the auditor could not validate, and a licence migration the auditor priced at a Rs 3,367 crore advantage.</p>
<p>None of this establishes that any decision was improper. The Bombay High Court upheld the Dharavi award and the electricity regulator adopted the solar tariffs. What the record does establish is that a few public decisions, taken by a small number of officials and committees, did much to shape who holds India's infrastructure, and that the documents behind several of them (the forest committee's reasons, the SEZ board's minutes, the Competition Commission's orders) are not easily available to the public that bears their consequences.</p></section>''')
    return "\n".join(s)


def airports_text():
    def vu(r):  # this table puts a second figure in the unit column
        return nums({"value": r["value"] + " " + r["unit"]})
    tvm = vu(ev(APT, "Thiruvananthapuram: Adani bid"))
    gap = (tvm[0] - tvm[1]) / tvm[0] * 100
    fr = ev(APT, "Per-passenger fees and upfront")
    fees = [nums(fr)[0], float(re.search(r"upfront fee Rs ([\d,]+)", fr["unit"]).group(1).replace(",", ""))]
    cap = nums(ev(APT, "issues RFP for six airports"))[0]
    vz = nums(ev(APT, "lone bidder APSEZ"))[0]
    vz_term = nums(ev(APT, "CAG audit findings on concession"))[0]
    kp = nums(ev(APT, "Krishnapatnam"))[0]
    gv = nums(ev(APT, "Government of Andhra Pradesh's 10.4%"))[0]
    nm = nums(ev(APT, "Navi Mumbai airport"))[0]
    return f"""<h3>2.1 Six airports in one round</h3>
<p>In November 2018 the Union Cabinet approved leasing six Airports Authority airports (Ahmedabad, Jaipur, Lucknow, Guwahati, Thiruvananthapuram and Mangaluru) and set up an Empowered Group of Secretaries, chaired by the chief executive of NITI Aayog, to decide matters beyond the appraisal committee's remit. The Ministry of Civil Aviation records that this group decided on 17 November 2018 to put no limit on how many airports one bidder could win and to require no prior airport experience. Bidders needed Rs {inr(cap)} crore of financial capacity and experience in any kind of infrastructure.</p>
<p>The Department of Economic Affairs and NITI Aayog both sent notes on the bid documents on 10 December 2018. The Kerala High Court's judgment summarises them. One asked for the bid parameter and the thresholds to be reviewed, the other said the two-stage procedure in the PPP guidelines had not been followed, that there was no approved model concession and no project cost estimate, and called the request for proposals "poorly prepared". The appraisal committee met the next day and the request for proposals went out on 14 December. The court held the notes to be recommendations that the committees could overrule and had considered. The Ministry's 2021 press note does not deny their content; it says they were not overruled because both departments sat on both committees.</p>
<p>Adani Enterprises quoted the highest fee per passenger at all six airports, by the Ministry's account. The only rival bid in a public record is at Thiruvananthapuram, where Adani bid Rs {tvm[0]:.0f} per domestic passenger against Rs {tvm[1]:.0f} from Kerala's state company, {gap:.0f}% lower and so outside the 10% band in which Kerala could have matched. The Cabinet approved three leases in July 2019 and three in August 2020, each for 50 years. By June 2024 the six concessionaires had paid the Airports Authority about Rs {inr(fees[0])} crore in per-passenger fees and Rs {inr(fees[1])} crore in upfront fees. The Kerala High Court dismissed the state's challenge in October 2020.</p>
<h3>2.2 Mumbai and Navi Mumbai</h3>
<p>Mumbai's airport came by acquisition. In August 2020 Adani Airport Holdings agreed to buy the debt of GVK's holding company, the route to GVK's 50.5% of Mumbai International Airport, and to complete the purchase of the 23.5% held by Airports Company South Africa and Bidvest. It took management control in July 2021 after approvals from the Union government, CIDCO and Maharashtra. Navi Mumbai's concession had been awarded in 2017, before Adani, to the GVK-led Mumbai company, which bid a {nm:.2f}% revenue share; the state auditor faulted signing it before the land was acquired. The CBI case against GVK and the Mumbai company, registered in June 2020, is reported in the press; no document in this record connects it to the sale.</p>
<h3>2.3 Ports</h3>
<p>The port record shows three routes. Some were negotiated purchases, such as 75% of Krishnapatnam at an enterprise value of Rs {inr(kp)} crore in 2020, and Gopalpur in 2024. One was a sale by a state government, when Andhra Pradesh sold its 10.4% of Gangavaram to Adani Ports for Rs {gv:,.2f} crore in 2021, and no Government Order or valuation for that sale was found. Two came through insolvency, Dighi in 2020 and Karaikal in 2023, each on a resolution plan approved by the creditors and the tribunal.</p>
<p>Vizhinjam in Kerala was a concession, and the Comptroller and Auditor General audited it. Adani Ports was the lone bidder and asked for the full viability gap grant of Rs {inr(vz)} crore; the state bears 67% of the cost. The auditor found that the 40-year term, ten years over the standard, gives the concessionaire Rs {inr(vz_term)} crore of extra revenue, and that with the termination payment the state's net receipts over the concession come to minus Rs 5,608 crore. Kerala's replies are in the report, and the auditor did not accept them.</p>
<p>The Mundra record concerns environmental compliance. A committee set up by the environment ministry in 2012 reported in April 2013, and in January 2014 the Gujarat High Court ordered the ministry to decide the port's clearance and stopped further work until it did.</p>
"""


def part3_body(CH, Chart):
    s = []
    s.append('''<section class="stack" style="padding-block:40px 24px;border:0">
<div class="eyebrow">Working paper · Part 3 of 3</div>
<h1>How the positions are paid for, and what regulators and courts found</h1>
<p class="lede">Part 3 looks at the money behind the assets. It asks how much each company owes against what it earns, who lends, how much of the founders' stock is pledged, what happened in the weeks after January 2023, and what Indian and American regulators and courts have decided.</p>
<p class="byline">ImpactMojo · Draft of 29 October 2026 · <a href="../">Part 1</a> · <a href="../part-2/">Part 2</a> · <a href="../../data/paper/">Data and sources</a></p>
</section>
<nav class="toc" aria-label="Contents"><div class="eyebrow">Contents</div><ol>
<li><a href="#p3-leverage">Debt against earnings</a></li>
<li><a href="#p3-lenders">Who lends</a></li>
<li><a href="#p3-pledges">Pledged shares</a></li>
<li><a href="#p3-2023">January to March 2023</a></li>
<li><a href="#p3-public">Public money</a></li>
<li><a href="#p3-legal">The legal record</a></li>
<li><a href="#p3-reliance">Reliance</a></li>
<li><a href="#p3-reading">What it adds up to</a></li>
</ol></nav>''')
    nd = ND
    last = lambda d: d[sorted(d)[-1]]
    s.append(f'''<section id="p3-leverage" class="paper-sec"><h2>1. Debt against earnings</h2>
<p>Net debt divided by a year's earnings before interest, tax, depreciation and amortisation says how many years of operating earnings it would take to repay what a company owes, net of its cash. The higher the number, the more the company depends on lenders continuing to lend.</p>
{CH["leverage"].html()}
<p>The companies differ more than the group label suggests. Adani Power, at about {nd["Adani Power"]["2016-17"]:.0f} times in 2016-17, was down to {nd["Adani Power"]["2023-24"]:.2f} in 2023-24 and {last(nd["Adani Power"]):.2f} in 2025-26. Adani Ports has stayed between 1.8 and 3.9 and ended at {last(nd["Adani Ports"]):.2f}. Adani Green, building fast, has never been below six and ended at {last(nd["Adani Green"]):.2f}. Adani Enterprises, the group's incubator for airports, roads and new energy, rose back to {last(nd["Adani Enterprises"]):.2f}. Reliance Industries has been below one since 2020-21.</p>
<p>A group-wide figure is not shown because the companies lend to and own parts of each other, and adding their debts would count some twice. The group's own portfolio figures use broader definitions of cash and earnings and come out lower.</p></section>''')
    rows = "".join(f"<tr><th scope=\"row\">{E(k)}</th><td>{v.get('2016', 0):g}%</td><td>{v.get('2024', 0):g}%</td></tr>"
                   for k, v in sorted(mix.items(), key=lambda kv: -kv[1].get("2016", 0) - kv[1].get("2024", 0) / 100))
    s.append(f'''<section id="p3-lenders" class="paper-sec"><h2>2. Who lends</h2>
<p>The only breakdown of who lends to the Adani companies comes from the group's own presentations, so it is the group's claim. By that account, Indian banks provided most of its long-term debt in 2016 and very little by 2024; bonds, foreign banks and non-bank lenders took their place.</p>
<figure class="events"><figcaption class="chart-title">Adani portfolio long-term debt by lender type (company presentation)</figcaption>
<div class="table-scroll" tabindex="0" role="region" aria-label="Lender mix"><table><thead><tr><th scope="col">Lender</th><th scope="col">March 2016</th><th scope="col">March 2024</th></tr></thead><tbody>{rows}</tbody></table></div>
<p class="chart-note">Read from a chart in Adani Ports' March 2025 investor presentation. Company claim.</p></figure>
<p>How much public-sector banks lend to the group has never been officially disclosed. Asked in Parliament in 2023, the government and the Reserve Bank cited section 45E of the Reserve Bank of India Act, which bars disclosure of a borrower's credit information.</p></section>''')
    s.append(f'''<section id="p3-pledges" class="paper-sec"><h2>3. Pledged shares</h2>
<p>When founders pledge their shares to borrow, a falling share price can force sales. In March 2020 the founders had pledged {PLEDGE["Adani Ports"]["Mar 2020"]:.0f}% of their holding in Adani Ports, {PLEDGE["Adani Enterprises"]["Mar 2020"]:.0f}% in Adani Enterprises and {PLEDGE["Adani Energy Solutions"]["Mar 2020"]:.0f}% in Adani Energy Solutions. By March 2025 these were near zero. The steepest fall came between December 2022 and March 2023, when the group said its founders had prepaid US$ {prepay:g} billion of share-backed loans.</p>
{CH["pledges"].html()}</section>''')
    mo = ", ".join(sorted({E(r["entity"].split(" (")[0]) for r in moodys}))
    s.append(f'''<section id="p3-2023" class="paper-sec"><h2>4. January to March 2023</h2>
<p>Hindenburg Research published its report on the group on 24 January 2023, as Adani Enterprises was preparing a follow-on share sale of up to Rs {inr(fpo)} crore. The sale closed fully subscribed and the board withdrew it on 1 February. By 1 March, the government told Parliament, the nine listed Adani companies had lost around {E(mcap_fall["value"].lstrip("-"))}% of their market value, while the Nifty 50 fell around 4.5%. On 10 February Moody's moved the outlook to negative on {mo}, citing the fall in equity values. On 2 March GQG Partners bought shares worth Rs {inr(gqg)} crore from the founders' family trust.</p></section>''')
    s.append(f'''<section id="p3-public" class="paper-sec"><h2>5. Public money</h2>
<p>The Life Insurance Corporation, which is owned by the government, disclosed in January 2023 that it had bought Adani shares for Rs {inr(lic_cost)} crore, then worth Rs {inr(lic_mv)} crore. By 30 September 2025 its Adani equity and debt together stood at Rs {inr(lic_2025)} crore at book value, according to a reply in the Lok Sabha. For public-sector banks there is no equivalent disclosure.</p></section>''')
    est = [r for r in LEG if not reported(r)]
    s.append(f'''<section id="p3-legal" class="paper-sec"><h2>6. The legal record</h2>
<p>Three years of proceedings in India and the United States have produced holdings, settlements and allegations, and they should not be mixed up.</p>
<h3>What courts and regulators decided</h3>
<ul>
<li>Supreme Court of India, 3 January 2024 (<em>Vishal Tiwari v. Union of India</em>, 2024 INSC 3). The Court declined to move the investigation to a special team or the CBI, upheld SEBI's rule changes, and said it had not interfered with the outcome of SEBI's investigations. It did not decide whether any Adani company broke the law. A review petition was dismissed in May 2024.</li>
<li>SEBI, 18 September 2025. Two orders found allegations about the Milestone, Rehvar and Adicorp transactions "not established", because the dealings were with parties that were not related under the definition in force before 2021.</li>
<li>SEBI, 28 September 2026. The order on the central question, whether offshore funds holding Adani shares were controlled by the founders' side, found the allegation "not established" for want of evidence that Vinod Adani directed their investments. The order adds that there was no allegation that he financed them, and that the result could have been different if there had been. Two individuals linked to the funds were fined Rs 20 lakh each for giving incorrect or incomplete information. The companies, Gautam Adani and 13 directors settled for Rs 1.48 crore without admitting anything.</li>
<li>SEBI settlements, September 2026. Five companies settled charges over undisclosed related-party dealings in 2012-13 and audits signed by firms without valid peer-review certificates; two executives settled a separate charge. None admitted the charges.</li>
<li>United States. The indictment unsealed in November 2024 charged Gautam Adani, Sagar Adani and Vneet Jaain with securities and wire fraud conspiracy and securities fraud, and five others connected with Azure Power and a Canadian pension fund with bribery conspiracy. On 10 August 2026, on the prosecutors' motion, the court dismissed the charges against the three Adani defendants with prejudice, stating that this expressed no opinion on the merits. The same day it entered a consent judgment in the SEC's civil case, under which Gautam Adani pays US$ 6 million and Sagar Adani US$ 12 million, without admitting or denying the allegations. The bribery charges against the five others remain, and the prosecutors have asked the appeals court to dismiss them.</li>
</ul>
<h3>What remains allegation</h3>
<p>The Hindenburg report, the OCCRP's reporting and the indictment's account of a bribery scheme are allegations; no court has made a finding on them. The indictment alleges that offers of payment to Indian officials were made through the three Adani defendants; Adani Green has stated that they were not charged under the bribery statute, which is true of the counts. Both statements are reproduced so the reader can see the difference.</p>
<h3>Bhatia's film</h3>
<p>On 26 October 2026 the Calcutta High Court, in a defamation suit brought by Adani Enterprises, restrained publication of Sabeer Bhatia's video until 31 January 2027 and ordered platforms to take it down, without having heard Bhatia. The order says it does not restrain constructive criticism or fair reporting on the group or on government policy.</p>
{events_table(LEG, "The legal record, January 2023 to October 2026", text_key="event", extra="holding_or_outcome")}</section>''')
    s.append(f'''<section id="p3-reliance" class="paper-sec"><h2>7. Reliance</h2>
<p>Reliance declared itself net-debt-free on 19 June 2020. The claim compared its net debt of Rs 1,61,035 crore at 31 March 2020 with the capital it raised or agreed to raise afterwards, from selling stakes in Jio Platforms and a rights issue, and it uses a definition of cash that includes some long-term investments. The first year-end on which the balance sheet bore it out was March 2021. Net debt has since returned, to Rs 1,24,717 crore by the company's figure in March 2026, at well under one year's earnings.</p>
<p>In May 2026 the Supreme Court set aside SEBI's fraud finding and Rs 447 crore disgorgement against Reliance over trading in Reliance Petroleum shares in 2007, while upholding a penalty for a disclosure breach; SEBI's Adani order of September 2026 relies on that judgment. The KG-D6 gas-migration appeals are before the Supreme Court.</p></section>''')
    s.append('''<section id="p3-reading" class="paper-sec"><h2>8. What it adds up to</h2>
<p>The Adani companies are not one balance sheet. Adani Power and Adani Ports have cut their debt relative to earnings to levels lenders treat as comfortable; Adani Green and Adani Enterprises carry far more, because they are building. The group replaced Indian bank lending with bonds and foreign banks over the past decade, by its own account, and its founders all but stopped borrowing against their shares after January 2023.</p>
<p>On the legal side, the question at the centre of the Hindenburg report, whether offshore funds were fronts for the founders, has been decided in the group's favour on the evidence SEBI gathered, and SEBI said plainly what that evidence did not cover. The American criminal case against the Adanis is over without a finding either way. Neither outcome is a finding that the allegations were false, and neither is a finding that they were true. Where the law offers settlement without admission, the record will often end there.</p>
<p>What the record cannot show is the exposure of India's public-sector banks, because it has not been disclosed. A country that publishes which company bought each electoral bond, by court order, does not publish how much its own banks have lent to its largest borrowers. That gap is a policy choice, and closing it would answer more than this paper can.</p></section>''')
    return "\n".join(s)
