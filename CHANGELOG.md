# Changelog

All model-relevant changes are versioned. Monthly data refreshes do not change the version unless code changed.

## 6.1.1 — 2026-10-20
Repository packaging; **score, model and data unchanged.** First public GitHub release of the full project. Added `README.md`, `.gitignore`, `LICENSE` (MIT for code), `CONTRIBUTING.md`, a GitHub Actions workflow that runs the leakage checks on every push, `tools/` (dashboard-recovery helpers), and `docs/index.html` so the dashboard can be served from GitHub Pages. `build.py` now also writes `docs/index.html`; `refresh.py` gained `--skip-inference` for quick rebuilds; `make_manifest.py` now records the Las Cruces and Ysleta series and takes `--retrieved` / `--bts` provenance notes instead of hard-coded dates; `requirements.txt` uses version floors (the release pins are kept in a comment).

## 6.1.0 — 2026-10-13
Display only; **score, model and data unchanged.** New look modeled on Marcus's reference mockup: navy banner with a mountain-and-skyline illustration and tagline; navy sidebar navigation (Overview, Indicators, Sectors, Research, plus quick links); a filter bar on the Overview with Compare to (Texas / U.S. / Las Cruces, drives the regional comparison), Time range (drives the history chart) and Download report; a semicircle gauge colored by level with the sensitivity range, change from last month and a level guide; a numbered "Why is the score 40?" panel with red/green point badges; a key-indicators table grouped by layer; the score history drawn over colored level bands; a regional comparison bar chart; three audience views (business owner, nonprofit, economic development) with links. Easing is now shown in green instead of blue. The mockup's illustrative figures (job postings, permits, food-assistance demand, CPI, a five-level scale) were not used: the page shows only BorderPulse's real indicators and its four levels.

## 6.0.0 — 2026-10-12
Display redesign after a design review; **score, model and data unchanged** (the version bump marks the new reading order and navigation).

**Overview first:** one plain-language conclusion with the reference month ("Pressure on El Paso's economy is slightly below normal and little changed from July"), the score with its monthly and 3-month change and a 0–100 level scale showing the 10–90% sensitivity range, beside a score-history chart (1 / 3 / 10 years / all). Then the three layer readings, "What moved the score since last month" (change attribution, largest three first), "Why the score is 40, below the typical 50" (level decomposition, largest three first), a data-coverage panel (headline month vs. the next month, per-indicator latest month and delay), and question-based shortcuts in place of the long audience cards. One interpretation throughout: the level name and the headline use the same words.

**Navigation:** nine tabs became four — Overview, Indicators, Sectors, Research — always fully visible on phones. Old links (#home, #validation, #lab, #data, card anchors) still route. Research has its own section links.

**Indicators:** one repeated pattern per indicator (name → value → comparison period → reference month → comparison with typical → "Source & method" with the FRED link). Regional comparison, border chain, trade & currency, watch list and "Data on the way" moved here.

**Sectors:** ranked horizontal bars of growth from a year earlier, each with its own reference month, job count and 6-month pace; select a sector for its history chart.

**Charts:** drawn at the container's pixel width (12px labels on phones, fewer date labels), redrawn on resize, readable by touch and keyboard (arrow keys), with a "Show values as a table" view under each main chart. The arc gauge is replaced by the history chart plus a compact level scale.

**Type, spacing, color:** body text 16px in Barlow, sentence-case headings, Barlow Condensed kept for the wordmark and headline number only; one spacing scale and two corner radii; navy ink on a warm page with white panels; red = adds pressure and blue = eases pressure, always with words beside the color.

**Fix:** the "Does it work?" text compared the share of calm months (score below 35) followed by deterioration with the wrong base rate (88%, the share of months *without* deterioration). It now uses the correct 12.5%, matching the technical note: calm months were followed by deterioration more often than average.

## 5.0.1 — 2026-10-12
Display-only. "Why the score is" panel rewritten in plain language: each indicator's reading is shown next to its typical value (mean of its own history, new `typical` field in `drivers`), with a worded effect (adds/eases stress) and a tally of what pushes the score up and down. Point shares use largest-remainder rounding so they add up exactly to score − 50. Score, model and data unchanged.

## 5.0.0 — 2026-10-12 (one-model release, after an external review)
An external review of v4.1 found that the dashboard and the back-test used different model definitions, that the payroll "early warning" record mixed warnings with detections, and several data-date and display bugs. All confirmed and addressed here.

**Model (versioned change):** the dashboard score now uses exactly the back-test definitions — payroll **year-over-year** growth (was 6-month change on a not-seasonally-adjusted series) and z-score history from **2000** via `data/full/` (was 2015). Verified feature-by-feature: every dashboard z-score, shifted by its publication lag, equals the back-test feature in `validation/lab_data.json` to 3 decimals. The observation-month history now shows the same two alert episodes as the back-test (2008–09, 2020); the June 2018 "High" reading of v4 is gone. Weights 40/35/25, transforms of the other six indicators, squash, threshold 65 and targets unchanged. The pipeline calendar end month is now derived from the data (no hand edit).

**New — `onset_eval.py` (pre-registered 2026-10-12):** dates each downturn's start and classifies each alert as a warning before onset, a detection after onset, or a miss, for BorderPulse ≥ 65 and the local Sahm rule, using as-publishable data. Result: payroll downturns — 1 advance warning (Oct 2008, 2 months before Dec 2008 onset), 1 detection (Apr 2020, same month), 0 false alarms; unemployment rises — 0 advance warnings, 2 detections, 1 miss (2004). Confirms the review's count: 19 of the 21 back-test alert months already had negative payroll growth.

**Crossings — Ysleta port split:** CBP made Ysleta its own port (2401) on 2020-03-16. The BTS "El Paso" (2402) series therefore loses Ysleta's traffic from March 2020; v3–v4.1 labelled this a "reporting break". The border panel and `border_test.py` now use El Paso + Ysleta (Ysleta data from BTS, annual totals cross-checked against server-side sums). The border test was rerun with its design unchanged (amendment v2); conclusion unchanged (C clears 2–3 of 4 checks depending on the back-test span — its payroll interval sits on zero after the 2026-10-12 back-test rerun — so the composite stays as published). The v4.1 result is superseded. Watch rows and the lead/lag study still use El Paso only (labelled).

**Data:** refreshed 2026-10-12 via FRED `.txt` data endpoints and BTS — El Paso unemployment and U.S.–Mexico trade through Aug 2026, peso and housing through Sep 2026, sector payrolls through Aug 2026 (with BLS revisions), U.S. unemployment Sep 2026, BTS crossings through Aug 2026 (El Paso pedestrians Feb 2026 revised by BTS from 100,917 to 402,525). Headline moves to **August 2026: 40.0 (Near normal)**.

**Fixes:** regional chart aligns series by month (unequal histories shifted points onto wrong dates); unemployment tile compares El Paso, Texas and U.S. at one common month; header and brief show headline month, data-retrieval date and build date separately, and "not yet published" wording now says "not in this data snapshot"; peso explanation no longer claims a lead that v4 retracted; charts drawn on hidden tabs redraw when shown; Research Lab shows an explanation instead of erroring on empty configurations and compares unemployment thresholds at 0.1pp precision; downloads fall back to ordinary browser downloads outside Claude; muted and warning text darkened to meet 4.5:1 contrast. Level names now describe distance from normal (Calm / Near normal / Above normal / High); "Household stress" renamed "Housing market".

**New/changed files:** `pipeline.py`, `onset_eval.py` (new), `border_test.py` (amendment v2), `make_brief.py`, `build.py`, `refresh.py` (Ysleta fetch, onset step), `dashboard_body.html`, data (Ysleta crossings, refreshed series, manifests). Full chain rerun on 2026-10-12 with the pinned numpy 2.4.4 / scipy 1.17.1 / scikit-learn 1.8.0 (Python 3.13): back-test (now through decision month 2026-02; all 12 leakage checks pass), benchmarks, lead/lag (crossings now El Paso + Ysleta; trucks now coincident rather than 1-month leading), horizons, inference, border test, onset evaluation, technical note (v5 rewrite, PDF re-rendered) and brief. Headline validation facts unchanged: 2 alert episodes, T1 AUC 0.47, T2 AUC 0.82, peso lead family-wise p 0.27, clean record in 73% of the 90 robustness configurations. Vintage audit still pending (needs ALFRED vintages).

## 4.1.0 — 2026-10-11 (border-economy release)
Follows a 2026-10-02 meeting with a regional border-economy research group, whose main methodological point was that national U.S.–Mexico trade is mostly through-traffic for El Paso and should be read alongside port-of-entry crossings. **Composite definition unchanged.**

**New — Las Cruces comparison:** FRED `LASC735UR` (Las Cruces MSA unemployment, smoothed SA) added to the regional labor-stress comparison with the same transform as Texas and the U.S. Comparison only; the EP–TX divergence rule is unchanged.

**New — `border_test.py`:** pre-registered comparison of border-layer definitions (A published trade + peso; B crossings replace trade; C trade + crossings; S sensitivity with trucks, never eligible because of BTS reporting breaks). Crossings transform: −YoY of 3-month sums, expanding z, lag t−2. Paired circular block bootstrap (block 12, B = 1000, seed 42) for AUC differences vs A on T1 and T2, with and without 2020–21. Pre-set bar for changing the composite: interval above zero on all four checks. Result: C clears 3 of 4 (fails payroll downturns excluding 2020–21, where only 3 events remain); B clears 1 of 4 and adds a false alarm in Mar–Apr 2021 driven by travel restrictions. **Composite unchanged.** Variant A reproduces the published back-test to within 0.05 points (rounding).

**New — dashboard:** "How a border shock reaches El Paso" panel (trade → crossings → local jobs, YoY of 3-month sums, display only) with a note on the Bridge of the Americas rebuild (GSA's preferred plan, proposed Oct 2024, moves commercial trucks to Ysleta–Zaragoza and Santa Teresa, NM — a future break in the El Paso truck series); "Data on the way" roadmap panel; border-test card on "Does it work?"; Las Cruces in the regional chart; dictionary, limitations and version history updated. `pipeline.py` now emits `border_chain` and `latest_values.lc_unemployment`; `build.py` embeds `validation/border_test.json`; `refresh.py` fetches `LASC735UR` and runs `border_test.py` after `inference.py`.

Not regenerated in this release (scripts not run in this session): `technical_note.md/.pdf` (still describes 4.0.0) and `borderpulse_brief.md`. Run `python3 refresh.py --no-fetch` to regenerate them with the 4.1.0 code.

## 4.0.0 — 2026-10-01 (research-grade release)
**Convention change (versioned):** the headline score is the latest month at which every expected indicator has a z-score. Trailing months where lagging series (unemployment t−1, trade t−2) have not yet published are reported as a labeled *nowcast* with their missing indicators listed, never as the headline. Interior months scored with a missing indicator (e.g. the 2025-10 federal data pause) are listed as partial. Motivation: under the previous convention the August 2026 headline jumped +5.5 points, of which ≈ +7.0 came from three strongly-signed indicators dropping out of the composite — a data-timing artifact, not an economic move.

**New — `inference.py`:** circular moving-block bootstrap (block 12, B = 1000) intervals for ROC/PR-AUC, for the AUC difference against the continuous local-Sahm statistic, and for episode-level precision/recall; circular-shift placebo tests; Newey–West (L = 12) inference for lead/lag correlations with Bonferroni adjustment over 13 leads; calibration tables with Wilson intervals and Brier skill; a 90-configuration robustness grid (weights × min-history × z-clip × lag shift). Results are embedded in a new **Inference** tab.

**New — `vintage_audit.py` + `test_vintage_audit.py`:** real-time back-test framework consuming ALFRED multi-vintage exports or FRED-API realtime observations (`--fetch` with `FRED_API_KEY`). Six synthetic-vintage checks pass (no-revision invariance, revision sensitivity, loader equivalence, lag enforcement). Status is *pending* until vintages are exported on a machine with full internet access.

**Corrected claim:** the earlier statement that the peso "leads El Paso employment by 7 months at ~5% significance" does not survive HAC inference with a 13-lead family (family-wise p ≈ 0.27). The dashboard and brief now describe it as suggestive, not established.

**Reproducibility package:** `requirements.txt` (pinned), `data/MANIFEST.json` (SHA-256, spans, sources, retrieval dates), `CITATION.cff`, this changelog, and `technical_note.md/.html/.pdf` generated by `make_technote.py` from the same JSON outputs that feed the dashboard.

Data: FRED refresh of 2026-09-28 (data through Aug 2026 for peso, housing, payrolls, TX/US unemployment; Jul 2026 for EP unemployment and trade). Composite definition — transforms, weights 40/35/25, expanding-window z with clip ±3, logistic squash slope 1.1, alert ≥ 65 — unchanged since v1.

## 3.2.0 — 2026-10-01
Tabbed layout with hash routing; welcome panel; expandable indicator explanations; toggleable comparison series. Display only.

## 3.1.0 — 2026-10-01
Plain-English "why" panel with exact point shares; data-timing labels in change attribution; regional comparison bars; time-range tabs; downloadable brief; audience start-here cards (navigation + facts, no advice); visual layer (gauge, sparklines, mini-bars, probability bars, dot matrices). Display only.

## 3.0.0 — 2026-09-03
Episode-first inference with exact Clopper–Pearson intervals; Sahm-rule and Dallas Fed BCI benchmarks; BTS El Paso crossings (1996→) as watch series; score uncertainty band; level decomposition and change attribution; divergence rule; Research Lab; Data & Methods page. Removed unvalidated sector colour codes, advice cards and the "21/21 precision" framing.

## 2.0.1 — 2026-08-28
Monthly refresh (TXUR 2026-07 added).

## 2.0.0 — 2026-08-26
Lag-aware back-test, 12 leakage checks, multi-horizon outlook, lead/lag study, watch slots, automated monthly refresh.

## 1.0.0 — 2026-08-25
Initial composite score and dashboard.
