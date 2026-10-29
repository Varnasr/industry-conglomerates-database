# India's largest business houses: Adani and Ambani

Shared engineering standard: @.claude/engineering-standards.md. It applies to all work in this repository. This file adds what is specific to the project, and wins where the two disagree.

Project tracking for the Adani and Reliance groups: a landing page, one map (`tracker.html`), a projects-and-sources table (`projects.html`) and the dataset behind them. Static, deployed on Netlify. Every figure the pages show is written from the CSV by `scripts/build_pages.py`: the map data, the table data, and the counts on `index.html` between `<!--stats:start-->` and `<!--stats:end-->`. Do not type a count into a page; `--check` fails if one drifts.

All three pages share `assets/site.css`, with light and dark tokens; the map switches its Esri base map with the theme. The Adani-only map (`adani_research_map.html`) was folded into the one map in October 2026: `/adani_research_map.html` 301s to `tracker.html?group=Adani&colour=role`, and the map reads `group` and `colour` from the address. `assets/site.js` runs the header on every page: the theme button, the Display menu (colour theme and the OpenDyslexic reading font, fonts in `assets/fonts` under the SIL OFL) and, below 760px, the Menu button that folds the links. Choices are stored as `ind.theme` and `reading-font`, and a short inline script in each `<head>` applies them before first paint. The map listens for the `themechange` event to swap its base map. Government roles are coloured in five families (`ROLE_FAMILY` in `build_pages.py`); the pop-up always gives the exact type.

## Commands

```bash
python3 scripts/check.py        # static checks, run by CI
python3 scripts/build_pages.py  # write the CSV into every page
python3 scripts/build_paper.py  # write paper/, findings/ and data/paper/ pages from data/paper/*.csv
python3 -m http.server 8000     # then open http://localhost:8000
```

Note that a local server does **not** send the `netlify.toml` headers, so the
Content-Security-Policy you see locally is only the `<meta http-equiv>` one.

## The paper

`paper/index.html` (Part 1, concentration), `paper/part-2/` (how the assets
were obtained), `paper/part-3/` (finance and risk), `findings/<slug>/index.html`
(one finding per page, 23 of them) and `data/paper/index.html` are written by
`scripts/build_paper.py` from the tables in `data/paper/`. Part 1 reads ports
and airports, power, telecom and city gas, cement-refining-retail-media and
economic weight. Parts 2 and 3 read `airports_ports`, `coal_power_land`,
`reliance_state`, `finance` and `legal`, and their prose lives in
`scripts/paper_parts.py`. Every number in the prose is computed from those rows;
do not type a figure into the text. `check.py` runs `--check`, and fails if any
row names no document or, unless it is a calculation, no address or page.

Rows whose `source_title` begins "Derived" are calculations, and the pages say
so. The rules the numbers follow: official denominators only; company figures
count subsidiaries in full, so the pages say "runs", not "owns"; national
shares only; Reliance Power (Anil Ambani) is never Reliance Industries.

Parts 2 and 3 keep three kinds of statement apart: decisions and holdings,
findings by an auditor or regulator, and allegations. A row resting on the
press alone carries a "Secondary source" chip (`reported()` in
`paper_parts.py`; the airports table records this in its `publisher` column)
and never carries a finding. No page claims a motive.

What could not be fetched from outside India, and is still owed to the paper:
the CCI's detailed orders (Reliance-Disney, Holcim, Sanghi, Penna, Orient, and
Case 03 of 2017 against Jio), PNGRB's monthly city gas reports, the per-passenger
bids at five of the six airports leased in 2019-20, the DEA and NITI Aayog notes
of 10 December 2018 themselves, AERA tariff orders, and the ECI electoral bond
files (the purchaser file was read from a copy; recheck against eci.gov.in).

## The CSP is declared twice, and that is the thing to get right

`index.html` carries a `<meta http-equiv="Content-Security-Policy">` and
`netlify.toml` sets the same header. A browser enforces the **intersection**, so
whichever is tighter governs and the looser one is invisible.

They had drifted. The header was carried over verbatim when this site was split
out of the Experiments repository, which hosts many tools, so it allowed ten
origins this site never touches: unpkg, cdnjs, openlibrary.org, the three
open-meteo endpoints, api.dhsprogram.com, tessdata.projectnaptha.com,
basemaps.cartocdn.com and licensebuttons.net.

Nothing broke, and nothing would have. The meta policy was a strict subset of
the header for every directive, so the intersection already equalled the meta
policy. The hazard ran the other way: delete the meta tag believing the header
covered it, and the policy silently widens by ten origins.

The header is now the meta policy verbatim, plus `object-src`, `worker-src` and
`media-src`, which a meta tag has no reason to carry. `scripts/check.py` fails
if the two drift apart again.

## Watch out for

- **A CSP that is too tight fails silently.** The script does not load, the
  chart does not draw, and only the browser console says why. If you add a CDN,
  add it to **both** policies, and remember that `<iconify-icon>` fetches its
  icon data at runtime from `api.iconify.design`, with `api.simplesvg.com` and
  `api.unisvg.com` as fallbacks, so those belong in `connect-src` rather than
  `script-src`.
- **Inline event handlers work here only because `script-src` carries
  `'unsafe-inline'`.** Tighten that to a nonce or a hash and every one of them
  stops firing with nothing on the page to show it. A check pairs the two.
- **Google Fonts spans two directives.** The stylesheet comes from
  `fonts.googleapis.com` under `style-src`, the font files from
  `fonts.gstatic.com` under `font-src`. Putting both in one is a common way to
  end up with a page in a fallback typeface.

## Data

`adani_database.csv` is the record. `tracker.html` carries it inline as
`const markersData = [...]` on one line and `projects.html` as
`const projectsData = [...]`, both written by `scripts/build_pages.py`.
Edit the CSV, then run the script; `scripts/check.py` fails if a page is
stale. Before October 2026 the copies were edited by hand.
`adani_database_sourced.xlsx` is the same table for download; regenerate it
from the CSV when the CSV changes.

**Every row was checked against documents on 28 October 2026.**
`Verification_Status` says how far: Verified, Verified with corrections, Partly
verified, or Unverified, and every map pin shows it. The check removed 58 rows:
33 city gas areas PNGRB lists under other companies, other assets the group
does not own, and 18 duplicates. 82 rows remain Unverified because the
session's web-search budget ran out; their notes say what to check.

`GOI_Support_Type` records only a documented government role. A row with
nothing documented says "No documented government role", which the pages
count as not government-linked. The map's share of projects from 2014 on with a government role is computed
from the data at load, not typed. On the Adani rows it was 68% before the
check and 48% after it, because about fifty support claims had no document
behind them.

The page derives its most recent year from the clock rather than pinning one, so
it advances on its own. A check fails if a literal year is introduced, because
that is how a live explorer becomes quietly stale a year later without anything
erroring. The map timelines take their range from the data for the same reason.

## The maps were blank in production, and the CSP check could not see it

The September 2026 CSP pass read `index.html` only. Both map pages loaded
Leaflet from unpkg.com and basemap tiles from carto, neither of which the
header allowed, so in production neither map drew anything, and only the
browser console said why. Leaflet now comes from jsDelivr, the basemaps from
Esri (Carto had started answering "API key required" anyway), and
`scripts/check.py` checks what every page loads, map tile URLs included,
against the header.

## Testing

`.github/workflows/ci.yml` runs `scripts/check.py` on every push and pull
request. Before 2026-09-22 there was no CI in this repository at all.
