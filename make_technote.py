"""
Technical note generator. Every number is read from the pipeline's JSON outputs so the
note, the brief and the dashboard cannot disagree. Writes technical_note.md and
technical_note.html; a PDF is rendered from the HTML by refresh.py when Playwright is
available (or by any browser's print-to-PDF).

v5: one model for dashboard and back-test; onset evaluation; El Paso + Ysleta crossings;
border-layer test; new level names.
"""
import json, os, datetime, html as H

BASE = os.path.dirname(os.path.abspath(__file__))
V = os.path.join(BASE, "validation")
J = lambda name: json.load(open(os.path.join(V, name)))
JO = lambda name: J(name) if os.path.exists(os.path.join(V, name)) else None
D = json.load(open(os.path.join(BASE, "borderpulse_output.json")))
BT, BM, INF, HOR, LL = J("backtest_metrics.json"), J("benchmarks.json"), J("inference.json"), J("horizons.json"), J("leadlag.json")
ON, BTEST = JO("onset_eval.json"), JO("border_test.json")
VA = JO("vintage_audit.json") or {"status": "pending"}
MAN = json.load(open(os.path.join(BASE, "data", "MANIFEST.json")))
today = datetime.datetime.now(datetime.timezone.utc).date().isoformat()
MONTHS = ["January","February","March","April","May","June","July","August","September","October","November","December"]
pretty = lambda m: f"{MONTHS[int(m[5:])-1]} {m[:4]}"
f3 = lambda v: "—" if v is None else f"{v:.3f}"
ci = lambda c: "—" if not c or c[0] is None else f"[{c[0]:.3f}, {c[1]:.3f}]"

e1 = BM["rules"]["borderpulse_ge65"]["unemployment_+0.5pp_6m"]["episode"]
e2 = BM["rules"]["borderpulse_ge65"]["payroll_growth_negative_6m"]["episode"]
s1 = BM["rules"]["local_sahm_rule"]["unemployment_+0.5pp_6m"]["episode"]
s2 = BM["rules"]["local_sahm_rule"]["payroll_growth_negative_6m"]["episode"]
m65 = BT["month_level_at_65"]
B = INF["bootstrap"]; P = INF["placebo"]; R = INF["robustness"]; C = INF["calibration"]
peso = INF["leadlag_hac"]["results"].get("Peso depreciation, 6-mo %", {})
nc = D.get("nowcast") or {}
ncm = max(nc) if nc else None

md = []
A = md.append
A(f"# BorderPulse v{D['version']}: an open early-warning laboratory for the El Paso–Juárez Borderplex economy")
A(f"**Technical note · {today} · headline month {pretty(D['asof'])} · data retrieved {D.get('data_retrieved') or '—'}**  ")
A("Marcus (maintainer) · marcusjhunt01@gmail.com · live dashboard: https://claude.ai/code/artifact/abaddafa-f6ba-4f07-9c38-50de4ac39816")
A("")
A("## Abstract")
po = ON["results"]["BorderPulse score ≥ 65"]["payroll_onset"] if ON else None
uo = ON["results"]["BorderPulse score ≥ 65"]["unemployment_onset"] if ON else None
A(f"BorderPulse compresses seven public monthly indicators for the El Paso metropolitan area into a 0–100 index of economic stress, "
  f"defined entirely by documented conventions and evaluated against targets fixed before evaluation. On {BT['n_months']} decision months "
  f"({BT['backtest_period'][0]} to {BT['backtest_period'][1]}) the ≥65 alert fired in {e2['alert_episodes']} episodes, both around genuine downturns "
  f"and never in an expansion. "
  + (f"Dated against when downturns began, it gave {po['advance_warnings']} advance warning of {po['n_onsets']} payroll downturns (2008) and detected the other "
     f"once under way (2020); it gave {uo['advance_warnings']} advance warnings of {uo['n_onsets']} unemployment rises. " if po else "")
  + f"Month-level discrimination of payroll-growth downturns is ROC-AUC {B['auc_T2']['index']:.2f} "
  f"(block-bootstrap 95% {ci(B['auc_T2']['index_ci'])}, placebo p = {P['index_T2']['p_auc']:.3f}), but that target counts months already in a downturn; "
  f"discrimination of 0.5-point unemployment rises is AUC {B['auc_T1']['index']:.2f} ({ci(B['auc_T1']['index_ci'])}, p = {P['index_T1']['p_auc']:.2f}) — indistinguishable from chance — "
  f"and a local Sahm rule detects more of those events. Since v5 the dashboard and the back-test share one model definition. "
  f"The index is a transparent screening device for unusual local conditions — stronger at confirming stress than predicting it — not a forecast and not a probability.")
A("")
A("## 1. Purpose and design principles")
A("The Borderplex has no public, monthly, locally-focused stress gauge that is both timely and auditable. BorderPulse is built to be a *laboratory* rather than an oracle: "
  "(i) every input is a public series with a FRED/BTS identifier; (ii) every transformation is a stated convention, labelled as such; (iii) the evaluation targets were fixed before any result was seen and are not tuned; "
  "(iv) no statistic uses information from after the month it is attached to; (v) negative results and losing benchmarks are published with the same prominence as positive ones; "
  "(vi) the full pipeline reruns from raw CSVs with one command and ships pinned dependencies, file hashes and a changelog.")
A("")
A("## 2. Data")
A("| File | Series | Source | Span | Rows | SHA-256 (first 12) |")
A("|---|---|---|---|---|---|")
for r in MAN["files"]:
    if r["file"].startswith("data/pre2015") or "crossings" in r["file"]:  # keep table compact
        continue
    A(f"| `{r['file']}` | {r.get('series_id','')} | {r.get('source','')} | {r['first'][:7] if r['first'] else ''}–{r['last'][:7] if r['last'] else ''} | {r['rows']} | `{r['sha256'][:12]}` |")
A("")
A(f"Full manifest with retrieval dates: `data/MANIFEST.json` ({MAN['n_files']} files, generated {MAN['generated']}), including the six BTS crossing files. All inputs are the latest available vintage at retrieval; "
  "Section 8 describes the real-time audit. Payroll series are not seasonally adjusted (NSA), so both the dashboard and the back-test use 12-month changes for employment (v5; earlier dashboards used 6-month changes). "
  "BTS port-of-entry crossings (1996→) are context and watch indicators only. CBP made Ysleta a separate port (2401) from El Paso (2402) on 16 March 2020; the border panel, lead/lag study and border-layer test add Ysleta back from that month, "
  "which removes what earlier versions described as a reporting break.")
A("")
A("## 3. Index construction")
A("**Stress signals.** For indicator *i* with raw series *x<sub>i,t</sub>*, the stress signal *s<sub>i,t</sub>* is: unemployment, 6-month difference; payrolls, −(12-month % change); imports and exports, −(12-month % change); peso, 6-month % change (depreciation positive); listings, 12-month % change; days on market, 12-month difference. Signs are chosen so that larger values mean more stress. The same definitions drive the dashboard and the back-test; every dashboard *z*, shifted by its publication lag, equals the back-test feature.")
A("")
A("**Expanding-window standardisation (no look-ahead).** *z<sub>i,t</sub>* = clip( (*s<sub>i,t</sub>* − μ<sub>i,1:t</sub>) / σ<sub>i,1:t</sub>, −3, 3 ), where μ and σ (sample SD) use only observations from 2000 up to and including *t*, with a minimum of 36 observations (24 for the two housing series, which begin in 2016). Because the window is expanding, the statistic at any month is invariant to data published later — the property checked by the automated leakage tests.")
A("")
A("**Layers and composite.** Layer scores are the equal-weighted mean of their indicators' *z*: local labour (unemployment, payrolls), border economy (imports, exports, peso), housing market (listings, days on market — a for-sale market measure, not a direct measure of household finances). The composite *z<sub>t</sub>* = Σ<sub>L</sub> *w<sub>L</sub>* *z<sub>L,t</sub>* / Σ<sub>L</sub> *w<sub>L</sub>* over the layers present, with *w* = (0.40, 0.35, 0.25). The display score is *S<sub>t</sub>* = 100 / (1 + exp(−1.1 *z<sub>t</sub>*)), so 50 corresponds to a historically typical month; the squash is monotone, so every rank-based result is independent of it. Levels describe distance from normal: Calm < 35 ≤ Near normal < 50 ≤ Above normal < 65 ≤ High; the ≥ 65 alert is the only operational rule.")
A("")
A(f"**Headline convention (v4).** The headline month is the latest month at which every expected indicator has a *z*-score. Later months where lagging series are missing from the data snapshot are reported as a *nowcast* with the missing indicators listed. Currently the headline is {pretty(D['asof'])} at {D['score']:.1f} ({D['level']})" + (f"; the {pretty(ncm)} nowcast is {nc[ncm]['score']:.1f} from {len(nc[ncm]['present'])} of 7 indicators." if ncm else "."))
A("")
A("**Decomposition contract.** Writing *z<sub>t</sub>* = Σ<sub>i</sub> *c<sub>i,t</sub>* with *c<sub>i,t</sub>* = *w<sub>L(i)</sub>* *z<sub>i,t</sub>* / (*n<sub>L(i)</sub>* Σ<sub>L</sub> *w<sub>L</sub>*), contributions are exact and additive in *z*-space; point shares of (*S<sub>t</sub>* − 50) are allocated pro rata to *c<sub>i,t</sub>*. Month-over-month attribution applies the same rule to Δ*c<sub>i,t</sub>*. "
  f"**Model sensitivity range.** The 10th–90th percentile of *S<sub>t</sub>* across leave-one-indicator-out recomputations and 200 Dirichlet draws of the layer weights (concentration 60 around the published weights); currently {D['score_band']['lo']:.0f}–{D['score_band']['hi']:.0f}.")
A("")
A("## 4. Validation design")
A("**Targets (fixed before evaluation).** T1: the El Paso MSA seasonally-adjusted unemployment rate rises by ≥ 0.5 percentage points at any point in months *t*+1…*t*+6 relative to month *t*. T2: El Paso year-over-year nonfarm payroll growth is negative at any point in *t*+1…*t*+6 — which also counts months already inside a downturn, so T2 mixes warning with detection (Section 5.1 separates them). A *deterioration event* is a maximal run of consecutive target months; an *alert episode* is a maximal run of consecutive months with *S<sub>t</sub>* ≥ 65. Episodes and events are the units of inference; month-level metrics are reported as secondary and labelled autocorrelated.")
A("")
A("**Information sets.** At decision month *t* the back-test may use labour and housing data through *t*−1, trade data through *t*−2 and the peso through *t*. Every *z* is recomputed under these lags. Two automated checks confirm the lags and two confirm that deleting all data after *t* leaves the month-*t* score unchanged (12 checks in total, `test_backtest.py`).")
A("")
A("**Benchmarks.** A local Sahm rule (three-month average unemployment ≥ 0.5 pp above its minimum over the prior twelve three-month averages, computed on data through *t*−1) and, when its data are present locally, a Dallas Fed El Paso Business-Cycle Index momentum rule. A rolling-origin logistic regression on the same seven *z*-features (annual retraining from 2013) is the model benchmark.")
A("")
A("## 5. Results")
if ON:
    A("### 5.1 Warning before onset vs. detection after onset (pre-registered 2026-10-12)")
    A("Onsets: payroll growth turning negative after six non-negative months; unemployment first standing ≥ 0.5 pp above its prior-12-month low after a year without that condition. An alert in the six months before an onset is an advance warning; otherwise an alert in the onset month or the six after is a detection.")
    A("")
    A("| Rule | Downturn type | Onsets | Warned before | Detected after | Missed | False-alarm episodes |")
    A("|---|---|---|---|---|---|---|")
    for rule, rr in ON["results"].items():
        for t, lab in (("payroll_onset", "Payroll growth turns negative"), ("unemployment_onset", "Unemployment +0.5 pp")):
            e = rr[t]
            A(f"| {rule} | {lab} | {e['n_onsets']} | {e['advance_warnings']} | {e['detections_after_onset']} | {e['missed']} | {e['false_alarm_episodes']} of {e['alert_episodes']} |")
    A("")
    A(f"In the back-test, {ON['alert_months_with_payroll_already_negative']} of the {ON['alert_months_ge65']} alert months already had negative payroll growth in the alert month itself. "
      "The one advance warning is October 2008, two months before payroll growth turned negative in December 2008; the 2020 alert fired in April, the month the downturn appears in the data (useful because April data were published in May, but a detection). "
      "With so few onsets every rate interval spans most of [0, 1]; the counts are the claim.")
    A("")
A("### 5.2 Episode-level record (T1/T2 windows)")
A("| Rule | Alert episodes | True warnings | Unemployment events caught | Payroll downturns caught | Episode precision 95% CI (exact) |")
A("|---|---|---|---|---|---|")
A(f"| BorderPulse ≥ 65 | {e1['alert_episodes']} | {e1['true_warnings']} | {e1['events_detected']} of {e1['events']} | {e2['events_detected']} of {e2['events']} | {ci(e1['episode_precision_ci95'])} |")
A(f"| Local Sahm rule | {s1['alert_episodes']} | {s1['true_warnings']} | {s1['events_detected']} of {s1['events']} | {s2['events_detected']} of {s2['events']} | {ci(s1['episode_precision_ci95'])} |")
A("")
A(f"With realistic publication lags the COVID alert fires in April 2020, one month after the shock. The slower deteriorations of 2004, 2010 and late 2019 are missed. Months scored below 35 were followed by deterioration {100*(1-BT['calm_reliability_below_35']):.0f}% of the time against a base rate of {100*m65['base_rate']:.0f}% — the calm band is not a safety signal.")
A("")
A("### 5.3 Month-level discrimination with resampling uncertainty")
A("| Metric | Index | Block-bootstrap 95% | Sahm statistic | 95% | Δ (index − Sahm) | 95% |")
A("|---|---|---|---|---|---|---|")
A(f"| ROC-AUC, T1 | {f3(B['auc_T1']['index'])} | {ci(B['auc_T1']['index_ci'])} | {f3(B['auc_T1']['sahm'])} | {ci(B['auc_T1']['sahm_ci'])} | {B['auc_T1']['diff_index_minus_sahm']:+.3f} | {ci(B['auc_T1']['diff_ci'])} |")
A(f"| ROC-AUC, T2 | {f3(B['auc_T2']['index'])} | {ci(B['auc_T2']['index_ci'])} | {f3(B['auc_T2']['sahm'])} | {ci(B['auc_T2']['sahm_ci'])} | {B['auc_T2']['diff_index_minus_sahm']:+.3f} | {ci(B['auc_T2']['diff_ci'])} |")
A(f"| PR-AUC, T1 | {f3(B['prauc_T1_index']['obs'])} | {ci(B['prauc_T1_index']['ci'])} | | | | |")
A("")
A(f"Circular moving-block bootstrap, block length 12 months, B = 1000 (Künsch 1989). Placebo tests rotate the score path against the target by every offset of at least 13 months: p(AUC) = {P['index_T1']['p_auc']:.3f} for T1 and {P['index_T2']['p_auc']:.3f} for T2; the null mean AUC is {P['index_T2']['null_auc_mean']:.2f} for T2 with 95% range {ci(P['index_T2']['null_auc_95'])}. "
  f"Episode-level bootstrap intervals: T2 recall {ci(B['episode_ge65_T2']['recall_ci'])}; the T2 precision interval is degenerate at 1 because every resampled alert block lies inside a downturn — a reminder that two episodes cannot estimate a rate.")
A("")
A("### 5.4 Lead/lag correlations with HAC inference")
A("| Indicator → EP payroll YoY growth | r at lead 0 | p (HAC) | Best lead | r | p (HAC) | p (Bonferroni, 13 leads) |")
A("|---|---|---|---|---|---|---|")
for name, r in INF["leadlag_hac"]["results"].items():
    A(f"| {name} | {r['r_at_0']:+.3f} | {r['p_at_0_hac']:.4f} | {r['best_lead']} | {r['best_r']:+.3f} | {r['best_p_hac']:.4f} | {r['best_p_bonferroni']:.3f} |")
A("")
A(f"Newey–West standard errors with a Bartlett kernel and L = 12 (Newey & West 1987). Crossings combine the El Paso and Ysleta ports. Trade flows, Mexico manufacturing and personal-vehicle crossings are reliably *coincident* with El Paso payroll growth. The peso's best lead ({peso.get('best_lead')} months, r = {peso.get('best_r')}) has a family-wise p of {peso.get('best_p_bonferroni')}: suggestive, not established. An earlier version of this project described the peso as a leading signal at 5% significance; that claim is withdrawn.")
A("")
A("### 5.5 Calibration")
A("| Band | n | Payroll downturn within 6 mo | Wilson 95% | Unemployment +0.5 pp within 6 mo | Wilson 95% |")
A("|---|---|---|---|---|---|")
for b2, b1 in zip(C["T2_by_band"], C["T1_by_band"]):
    pf = lambda x: '—' if x is None else f"{100*x:.0f}%"
    A(f"| {b2['bin']} | {b2['n']} | {pf(b2['freq'])} | {ci(b2['wilson95'])} | {pf(b1['freq'])} | {ci(b1['wilson95'])} |")
A("")
A(f"Base rates: T2 {100*C['base_rate_T2']:.0f}%, T1 {100*C['base_rate_T1']:.0f}%. Brier skill of *S*/100 against the base rate is {C['brier_score_over_100']['T1_skill_vs_base_rate']} (T1) and {C['brier_score_over_100']['T2_skill_vs_base_rate']} (T2): the score is a ranking, not a probability, and must not be read as one.")
A("")
A("### 5.6 Robustness grid")
A(f"The composite was recomputed under {R['n_configs']} conventions (five weight vectors × minimum history 24/36/48 × z-clip 2/3/4 × publication lags shifted by 0/+1 month) with targets and the ≥65 rule held fixed. Both historical alerts fire in {100*R['share_fires_2008']:.0f}% (2008) and {100*R['share_fires_2020']:.0f}% (2020) of configurations; the record is *clean* (those two episodes and nothing else) in {100*R['share_clean_record']:.0f}%. T2 AUC ranges {R['auc_T2_range'][0]:.2f}–{R['auc_T2_range'][2]:.2f} (median {R['auc_T2_range'][1]:.2f}); T1 AUC ranges {R['auc_T1_range'][0]:.2f}–{R['auc_T1_range'][2]:.2f} and never exceeds 0.5. Equal layer weights correlate {100*BM['weight_sensitivity']['score_correlation']:.1f}% with the published score (maximum gap {BM['weight_sensitivity']['max_abs_score_diff']} points).")
A("")
if BTEST:
    A("### 5.7 Border-layer test: national trade vs. port-of-entry crossings (pre-registered)")
    A("A regional research group noted that national U.S.–Mexico trade is largely through-traffic for El Paso. Three border layers were compared on the same targets and lags: A (published: imports, exports, peso), B (crossings replace trade), C (trade plus crossings); S adds trucks as a sensitivity only.")
    A("")
    A("| Variant | Sample | AUC T1 | Δ vs A, 95% | AUC T2 | Δ vs A, 95% |")
    A("|---|---|---|---|---|---|")
    for v in ("B", "C", "S"):
        for smp, lab in (("full", "all months"), ("ex_covid", "excl. 2020–21")):
            a1 = BTEST["results"]["targets"]["T1"][smp]["variants"][v]; a2 = BTEST["results"]["targets"]["T2"][smp]["variants"][v]
            A(f"| {BTEST['variants'][v]['label']} | {lab} | {a1['auc']:.3f} | {a1['auc_diff_vs_A']:+.3f} {ci(a1['diff_ci95'])} | {a2['auc']:.3f} | {a2['auc_diff_vs_A']:+.3f} {ci(a2['diff_ci95'])} |")
    A("")
    A(f"Decision rule: a variant is a candidate only if its 95% interval is above zero on both targets, with and without 2020–21. Result: {BTEST['decision']}. {BTEST.get('amendment','')}")
    A("")
A("### 5.8 Horizons")
A("| Event | Horizon | Base rate | P(event | current band) | ROC-AUC (index) |")
A("|---|---|---|---|---|")
for key, lab in (("payroll_growth_negative", "Payroll growth negative within horizon"), ("unemployment_+0.5pp", "Unemployment +0.5 pp")):
    for h in ("3m", "6m", "12m"):
        d = HOR["horizons"][h][key]; p = d["current_band_p"]
        A(f"| {lab} | {h} | {100*d['index_at_65']['base_rate']:.0f}% | {'—' if p is None else format(100*p, '.0f') + '%'} | {d['index_at_65']['ROC_AUC']:.2f} |")
A("")
A("## 6. Interpretation")
A("The evidence supports a narrow claim: when El Paso is in or entering a payroll downturn the composite is usually already unusual, and it has not produced a false High reading in 23 years. Measured from the date downturns began, it gave one advance warning (2008) and one prompt detection (2020). "
  "It does not anticipate unemployment spikes — on that target a plain Sahm rule is better and neither warns ahead. "
  "The practical reading is a screening device: High means 'look at the underlying indicators now'; Calm and Near normal mean 'conditions resemble ordinary months', which historically still preceded deterioration roughly one month in five.")
A("")
A("## 7. Changes in v5")
A("The v4 dashboard used 6-month payroll changes and a 2015 history window while the back-test used 12-month changes and a 2000 window, so published validation did not describe the displayed score; v5 uses one definition. "
  "v5 adds the onset evaluation (5.1), adds the Ysleta port to crossings, refreshes data to the latest published months, and fixes several display and date issues identified in an external review (see `CHANGELOG.md`).")
A("")
A("## 8. Real-time vintage audit")
if VA.get("status") == "complete":
    A(VA.get("summary_text", ""))
else:
    A("All results above use latest-vintage data. BLS LAUS and CES series are benchmarked annually and first prints at turning points are often revised by several tenths. `vintage_audit.py` rebuilds the score path month by month from the data vintage available at each decision date (ALFRED exports or FRED-API realtime observations) and compares alert episodes and AUC with the revised path. "
      "Six synthetic-vintage checks pass (`test_vintage_audit.py`). "
      f"Status: **{VA.get('status','pending')}** — the vintage files must be exported on a machine with full internet access. Until then the revised-data caveat is the largest open limitation of every figure in this note.")
A("")
A("## 9. Limitations")
A("Six deterioration events since 2003, two of them COVID-driven — every rate carries a wide interval and ex-COVID results weaken. Revised rather than real-time vintages (Section 8). Housing enters only from mid-2019, so earlier composites are a two-layer model (marked on the history chart). NSA employment series. Overlapping windows in all 6- and 12-month transforms (addressed by HAC and block methods, not eliminated). "
  "Crossings cover the El Paso and Ysleta ports only (Santa Teresa and Tornillo not included); the planned Bridge of the Americas rebuild is expected to move commercial trucks between ports. Constants are conventions with published sensitivity, not estimates. The index is not a probability, not a forecast and not official statistics.")
A("")
A("## 10. Reproducibility")
A("`python3 refresh.py --no-fetch` reruns pipeline → backtest → 12 leakage checks → benchmarks → lead/lag → horizons → inference → border test → onset evaluation → vintage audit → manifest → this note → dashboard → brief, from the CSVs whose hashes are in `data/MANIFEST.json`. `python3 refresh.py` additionally re-pulls every FRED and BTS series. Dependencies are pinned in `requirements.txt` (numpy 2.4.4, scipy 1.17.1, scikit-learn 1.8.0). Random seeds are fixed (42). `CHANGELOG.md` records every versioned change; `CITATION.cff` gives the citation.")
A("")
A("## References")
A("Clopper, C. J. & Pearson, E. S. (1934). The use of confidence or fiducial limits illustrated in the case of the binomial. *Biometrika* 26, 404–413.  ")
A("Künsch, H. R. (1989). The jackknife and the bootstrap for general stationary observations. *Annals of Statistics* 17, 1217–1241.  ")
A("Newey, W. K. & West, K. D. (1987). A simple, positive semi-definite, heteroskedasticity and autocorrelation consistent covariance matrix. *Econometrica* 55, 703–708.  ")
A("Phillips, K. R. (2004). A new monthly index of the Texas business cycle. Federal Reserve Bank of Dallas Working Paper 0401 (basis of the Dallas Fed metro business-cycle indexes).  ")
A("Sahm, C. (2019). Direct stimulus payments to individuals. In *Recession Ready: Fiscal Policies to Stabilize the American Economy*, Brookings/Hamilton Project.  ")
A("Wilson, E. B. (1927). Probable inference, the law of succession, and statistical inference. *JASA* 22, 209–212.  ")
A("")
A(f"*Generated {today} by make_technote.py from the pipeline outputs; model v{D['version']}.*")

text = "\n".join(md) + "\n"
open(os.path.join(BASE, "technical_note.md"), "w").write(text)

# ---------- minimal markdown -> HTML (headings, paragraphs, pipes tables, inline code/bold/italic) ----------
def inline(t):
    t = t.replace("&", "&amp;")
    import re
    t = re.sub(r"`([^`]+)`", r"<code>\1</code>", t)
    t = re.sub(r"\*\*([^*]+)\*\*", r"<b>\1</b>", t)
    t = re.sub(r"(?<![*\w])\*([^*]+)\*(?!\w)", r"<i>\1</i>", t)
    return t
out, i, lines = [], 0, text.split("\n")
while i < len(lines):
    ln = lines[i]
    if ln.startswith("# "): out.append(f"<h1>{inline(ln[2:])}</h1>")
    elif ln.startswith("## "): out.append(f"<h2>{inline(ln[3:])}</h2>")
    elif ln.startswith("### "): out.append(f"<h3>{inline(ln[4:])}</h3>")
    elif ln.startswith("|"):
        rows = []
        while i < len(lines) and lines[i].startswith("|"):
            rows.append([c.strip() for c in lines[i].strip().strip("|").split("|")]); i += 1
        hdr, body = rows[0], [r for r in rows[2:]]
        out.append("<table><thead><tr>" + "".join(f"<th>{inline(c)}</th>" for c in hdr) + "</tr></thead><tbody>" +
                   "".join("<tr>" + "".join(f"<td>{inline(c)}</td>" for c in r) + "</tr>" for r in body) + "</tbody></table>")
        continue
    elif ln.strip() == "": pass
    else:
        para = [ln]
        while i + 1 < len(lines) and lines[i + 1].strip() and not lines[i + 1].startswith(("#", "|")):
            i += 1; para.append(lines[i])
        out.append("<p>" + "<br>".join(inline(p.rstrip()) for p in para) + "</p>")
    i += 1
style = """<style>
@page{size:A4;margin:18mm 17mm}body{font-family:Georgia,'Times New Roman',serif;font-size:10.5pt;line-height:1.45;color:#141413;max-width:180mm;margin:0 auto;padding:12mm 0}
h1{font-size:19pt;line-height:1.15;margin:0 0 6pt}h2{font-size:13pt;margin:16pt 0 4pt;border-bottom:1px solid #ccc;padding-bottom:2pt}h3{font-size:11pt;margin:12pt 0 3pt}
p{margin:5pt 0;text-align:justify}table{border-collapse:collapse;width:100%;font-size:8.6pt;margin:6pt 0 8pt}tr{page-break-inside:avoid}
th,td{border-bottom:1px solid #ddd;padding:3pt 5pt;text-align:left;vertical-align:top}th{background:#f3f2ee;font-weight:600}code{font-family:Menlo,Consolas,monospace;font-size:8.6pt}
</style>"""
htmlout = f"<!doctype html><html lang='en'><head><meta charset='utf-8'><title>BorderPulse technical note</title>{style}</head><body>{''.join(out)}</body></html>"
open(os.path.join(BASE, "technical_note.html"), "w").write(htmlout)
print("technical_note.md / .html written;", len(text.split()), "words")
