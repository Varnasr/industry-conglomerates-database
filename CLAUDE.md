# Industry Conglomerates Tracker

Shared engineering standard: @.claude/engineering-standards.md. It applies to all work in this repository. This file adds what is specific to the project, and wins where the two disagree.

Conglomerate project tracking: a landing page, two map pages and the dataset behind them. Static, deployed on Netlify; the map data is written into the pages by `scripts/build_pages.py`.

## Commands

```bash
python3 scripts/check.py        # static checks, run by CI
python3 scripts/build_pages.py  # write the CSV into both map pages
python3 -m http.server 8000     # then open http://localhost:8000
```

Note that a local server does **not** send the `netlify.toml` headers, so the
Content-Security-Policy you see locally is only the `<meta http-equiv>` one.

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

`adani_database.csv` is the record. `crony_tracker.html` (all rows) and
`adani_research_map.html` (Adani rows) each carry it inline as
`const markersData = [...]` on one line, written by `scripts/build_pages.py`.
Edit the CSV, then run the script; `scripts/check.py` fails if either page is
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
count as not government-linked. The Modi-era share on the research map is
computed from the data at load, not typed: it was 68% before the check and
48% after it, because about fifty support claims had no document behind them.

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
