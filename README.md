# CA Sweep Watch

Statewide tracker of enforcement actions against unhoused Californians (PC 647(e) illegal lodging, trespass-as-camping, and local anti-camping ordinances), built on monthly California Public Records Act requests, with an automated non-response escalation workflow and a public map.

## How it fits together

```
data/ordinances.csv  ──┐            data/agencies.csv (540 cities+counties)
(Berkeley HSP appendix │                     │
 + verified additions) │                     ▼
                       └──► pipeline/db.py ──► sweepwatch.db (SQLite)
                                             │
        monthly cron ──► generate_requests.py│──► outbox/YYYY-MM/*.md (drafts)
                                             │    --send emails via your SMTP
        agency responses ──► inbox/<Agency>/ │
                          ingest.py ─────────┤  text + EXIF GPS + regex events
                          geocode.py ────────┤  addresses → coords (Census, free)
                          deadlines.py ──────┤  overdue → escalation letters
                                             ▼        (+ writ petition outline)
                          export_map_data.py ──► site/data.json ──► site/index.html
                                                        (static Leaflet map)
```

## Quick start

```bash
pip install requests pdfplumber Pillow            # anthropic optional, for --llm
cd pipeline
python fetch_berkeley_appendix.py   # pull UC Berkeley HSP ordinance appendix
python merge_berkeley.py            # fold it into data/ordinances.csv
python fetch_agency_list.py         # expand agencies.csv to all 482 cities
python db.py                        # build sweepwatch.db
cp ../config.example.ini ../config.ini   # fill in requester + SMTP details
python generate_requests.py         # DRAFTS ONLY -> outbox/
python generate_requests.py --send  # actually email (only rows with cpra_email)
# ...responses arrive; save files to inbox/City_of_Fresno/ etc...
python ingest.py [--llm]
python geocode.py
python deadlines.py --letters       # overdue -> escalation letters
python export_map_data.py
python -m http.server -d ../site 8000   # preview map at localhost:8000
```

## Monthly automation

Run on the 1st via cron or GitHub Actions:
`generate_requests.py --send` → (as responses arrive) `ingest.py`, `geocode.py` → `deadlines.py --letters` → `export_map_data.py` → deploy `site/`.
A GitHub Action can commit the regenerated `data.json` and publish `site/` to GitHub Pages/Netlify/Cloudflare Pages — all free static hosting.

## Privacy & personal-data protection

- The site is fully static; it exposes only `data.json`, which `export_map_data.py` builds from whitelisted fields — never requester info, file paths, or raw document text.
- Keep `config.ini` (name/email/SMTP) out of git — see `.gitignore`.
- Use a dedicated request email and PO box; CPRA correspondence is itself a public record.
- Register the domain with WHOIS privacy; host on Pages/Netlify so no server logs tie to you.
- Redact personal identifying info of unhoused individuals from anything published; the pipeline only publishes event-level summaries.

## Legal notes (not legal advice)

- CPRA: Gov. Code § 7920.000 et seq. Determination due in 10 days (§ 7922.535(a)), one 14-day extension (§ 7922.535(b)). Electronic records in native format with metadata: § 7922.570 — this is what preserves photo EXIF GPS.
- There is no administrative "complaint" for CPRA violations; enforcement is a **petition for writ of mandate** (§ 7923.000). Mandatory attorney's fees for prevailing requesters (§ 7923.115). The pipeline generates escalation letters automatically and a petition outline (`templates/cpra_writ_petition_outline.md`) for counsel to finalize.
- Some agencies only accept requests via NextRequest/GovQA portals — `agencies.csv` has a `cpra_portal_url` column; those need manual or browser-automated submission.

## Data sources

- UC Berkeley Law Homelessness Service Project, *The State of Homelessness Criminalization in California After Grants Pass v. Johnson* (May 2025), SSRN 5257640. Appendix (public Google Sheet): https://docs.google.com/spreadsheets/d/1HNo5liFOx88Yf0KEd0UN7dzwonL7axbHjiBgezm6MUQ
- CA Penal Code §§ 647(e), 602, 370–372; local municipal codes (see `data/ordinances.csv`, `verification_status` column).

## Roadmap

1. Fill `cpra_email` / `cpra_portal_url` for all agencies (biggest manual lift; crowd-sourceable).
2. OCR pass for scanned PDFs (`ocrmypdf`), better event extraction (LLM-assisted with human review queue).
3. Portal auto-submission for NextRequest/GovQA agencies.
4. County-level choropleth + time slider on the map; per-jurisdiction ordinance pages.
5. Consider partnering/coordinating with the Berkeley HSP team — their appendix tracks proposed ordinances too.
