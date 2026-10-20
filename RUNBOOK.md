# BorderPulse monthly refresh — runbook

Two ways to refresh, depending on where you are running.

## A. On your own computer (the simple way)

```bash
git pull
pip install -r requirements.txt
python3 refresh.py          # downloads every FRED/BTS series, then reruns the whole chain
git add -A && git commit -m "Monthly refresh: data through YYYY-MM" && git push
```

`refresh.py` runs, in order: pipeline → backtest → test_backtest (12 checks must PASS — if any fail, STOP and publish nothing) → benchmarks → leadlag → horizons → inference → border_test (reproduction check must stay ≤ 0.06 points) → onset_eval → vintage_audit → test_vintage_audit (6 checks must PASS) → make_manifest → make_technote → build → make_brief, then renders `technical_note.pdf` if Playwright is installed. Use `--no-fetch` to rerun on the data already in `data/`, and `--skip-inference` for a quick rebuild without the slow bootstrap step.

Outputs that change on a refresh: `data/*.csv`, `data/MANIFEST.json`, `borderpulse_output.json`, `validation/*`, `technical_note.{md,html,pdf}`, `borderpulse_brief.md`, `artifact.html`, `borderpulse_dashboard.html`, `docs/index.html`. Commit all of them: the hashes in `MANIFEST.json` are the audit trail for the published numbers.

Optional local-only inputs (never fetched from the cloud):
- `data/extra/dallas_fed_bci.csv` — Dallas Fed El Paso Business-Cycle Index (benchmark only); `refresh.py` downloads the xlsx if pandas+openpyxl are installed. Never invent it.
- `data/vintages/<SERIES>.csv` — ALFRED multi-vintage exports or `python3 vintage_audit.py --fetch` with `FRED_API_KEY` set; activates the real-time audit. Until present, `vintage_audit.py` writes status "pending" and the dashboard and technical note say so. Never fabricate vintages.

## B. In a Claude cloud session (scheduled task, no internet from the shell)

The session has no files: rebuild the workspace from the GitHub repository (clone it, or `project_read` each file from the claude.ai project), then refresh the data with Claude's web tools, recompute, republish and deliver the brief.

**FRED (17 series).** Direct downloads are blocked in the sandbox — use WebFetch of `https://fred.stlouisfed.org/data/<SERIES>.txt`, asking for observations from 2025-01-01 onward as `YYYY-MM-DD,value` lines (skip "."). The `.txt` endpoint returns the current vintage with a "Last Updated" header and has worked without a prior search; the HTML `/data/<SERIES>` and `/series/` pages have been served stale. Fallback chain: WebSearch `"<SERIES>" FRED` → WebFetch the `/series/` page asking for its "View All" `/data/` link → WebFetch that. Spot-check a few values with a second fetch (the fetch summarizer can drop or invent rows). Trust ONLY `/data/` tables for observations. Merge update-or-append by date; never delete history. Trade series come back with 6-decimal precision — keep it.

Series → file: ELPA348UR→ep_unrate.csv, TXUR→tx_unrate.csv, UNRATE→us_unrate.csv, LASC735UR→lc_unrate.csv (Las Cruces, comparison only), ELPA348NAN→ep_nonfarm.csv, ELPA348TRADN→ep_trade.csv, ELPA348GOVTN→ep_govt.csv, ELPA348NRMNN→ep_construction.csv, ELPA348MFGN→ep_mfg.csv, ELPA348EDUHN→ep_eduhealth.csv, ELPA348LEIHN→ep_leisure.csv, ELPA348PBSVN→ep_profbiz.csv, IMPMX→us_imports_mexico.csv, EXPMX→us_exports_mexico.csv, EXMXUS→peso_usd.csv, ACTLISCOU21340→ep_active_listings.csv, MEDDAYONMAR21340→ep_days_on_market.csv.

**BTS crossings (6 series → `data/extra/`: `ep_crossings_*` and `ysleta_crossings_*`).** Endpoint: `https://data.bts.gov/resource/keg4-3bc2.json?port_name=El%20Paso&measure=<Trucks|Personal%20Vehicles|Pedestrians>&$select=date,value&$order=date&$limit=200` with `$where` date windows; `port_name=Ysleta` for the Ysleta port (separate since 2020-03-16). Cross-check fetched rows against a server-side yearly sum: `?port_name=<Port>&$select=measure,date_extract_y(date) AS y,sum(value) AS t&$group=measure,y`. If the fetch is blocked, leave the files as restored and say so.

Then rebuild `data/full/*.csv` by merging `data/pre2015/X.csv` + `data/X.csv` for ep_unrate, ep_nonfarm, us_imports_mexico, us_exports_mexico, peso_usd (the merge logic in `refresh.py`), and run `python3 refresh.py --no-fetch`.

**Headline convention (v4):** the headline is the latest month with ALL expected indicators; later partial months are a labeled nowcast in `borderpulse_output.json → nowcast`. Do not "fix" the headline to the latest data month.

**Border test (v4.1):** its variants and decision rule are pre-registered (2026-10-11). Rerunning it on new data is fine; changing the variants, transform or bar is a versioned change, and it never changes the composite on its own — promotion is the maintainer's documented decision.

**Publish.** Republish the dashboard: Artifact tool with file `artifact.html`, `url: https://claude.ai/code/artifact/abaddafa-f6ba-4f07-9c38-50de4ac39816` (pass the url or a duplicate is created), and `files: {"technical_note.pdf": "<path>/technical_note.pdf"}` so the Data & methods PDF link works (omit `files` if the PDF was not regenerated). Keep favicon 🌵. OMIT `capabilities` (the artifact stores `{downloads: true}`; passing `{}` would revoke the download buttons). A publish needs a plain Artifact `read` of the url first. Send `borderpulse_brief.md` (status: proactive), and `technical_note.pdf` when the version changed. If the headline score crossed ≥65 (employment warning ACTIVE) or crossed back below, say so prominently. If only the NOWCAST crossed 65, say "preliminary flag, pending <missing indicators>". Framing discipline: episode counts with intervals, never "N of N / 100% precision" month-counting; the peso lead/lag claim is "suggestive, not established".

Finally push the refreshed files to GitHub (or `project_write` them back to the claude.ai project) so the next session starts from the current data.

## Rules that never change on a refresh

- The alert rule, thresholds, target definitions and backtest methodology are FIXED — do not tune or redefine them. Constants are labeled conventions; changing one is a versioned model change (bump `VERSION` in `pipeline.py`, add a row to the version-history table in `dashboard_body.html`, an entry to `CHANGELOG.md`, and re-sync `technical_note.md`).
- Watch/extra indicators never enter the composite score automatically; promotion requires a documented backtest improvement (a human decision).
- If a fetch fails or a series looks broken (gaps, absurd values), publish nothing for that step and report exactly what failed. The 2025-10 unemployment gap (federal data pause) is known and handled (backtest interpolates; pipeline lists it as a partial interior month).
- Figures heard in partner meetings are unverified and must not appear on the dashboard or brief until confirmed in writing — see `docs/planning/v3_plan.md` Part 0.4.
