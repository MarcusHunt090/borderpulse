# BorderPulse v6.1.1: an open early-warning laboratory for the El Paso–Juárez Borderplex economy
**Technical note · 2026-10-20 · headline month August 2026 · data retrieved 2026-10-12**  
Marcus (maintainer) · marcusjhunt01@gmail.com · live dashboard: https://claude.ai/code/artifact/abaddafa-f6ba-4f07-9c38-50de4ac39816

## Abstract
BorderPulse compresses seven public monthly indicators for the El Paso metropolitan area into a 0–100 index of economic stress, defined entirely by documented conventions and evaluated against targets fixed before evaluation. On 272 decision months (2003-07 to 2026-02) the ≥65 alert fired in 2 episodes, both around genuine downturns and never in an expansion. Dated against when downturns began, it gave 1 advance warning of 2 payroll downturns (2008) and detected the other once under way (2020); it gave 0 advance warnings of 3 unemployment rises. Month-level discrimination of payroll-growth downturns is ROC-AUC 0.82 (block-bootstrap 95% [0.634, 0.946], placebo p = 0.000), but that target counts months already in a downturn; discrimination of 0.5-point unemployment rises is AUC 0.47 ([0.165, 0.736], p = 0.56) — indistinguishable from chance — and a local Sahm rule detects more of those events. Since v5 the dashboard and the back-test share one model definition. The index is a transparent screening device for unusual local conditions — stronger at confirming stress than predicting it — not a forecast and not a probability.

## 1. Purpose and design principles
The Borderplex has no public, monthly, locally-focused stress gauge that is both timely and auditable. BorderPulse is built to be a *laboratory* rather than an oracle: (i) every input is a public series with a FRED/BTS identifier; (ii) every transformation is a stated convention, labelled as such; (iii) the evaluation targets were fixed before any result was seen and are not tuned; (iv) no statistic uses information from after the month it is attached to; (v) negative results and losing benchmarks are published with the same prominence as positive ones; (vi) the full pipeline reruns from raw CSVs with one command and ships pinned dependencies, file hashes and a changelog.

## 2. Data
| File | Series | Source | Span | Rows | SHA-256 (first 12) |
|---|---|---|---|---|---|
| `data/ep_active_listings.csv` | ACTLISCOU21340 | FRED / Realtor.com | 2016-07–2026-09 | 123 | `b1559c332d46` |
| `data/ep_construction.csv` | ELPA348NRMNN | FRED / BLS CES | 2015-01–2026-08 | 140 | `8506f5263679` |
| `data/ep_days_on_market.csv` | MEDDAYONMAR21340 | FRED / Realtor.com | 2016-07–2026-09 | 123 | `229df3b85670` |
| `data/ep_eduhealth.csv` | ELPA348EDUHN | FRED / BLS CES | 2015-01–2026-08 | 140 | `32f1851d38cc` |
| `data/ep_govt.csv` | ELPA348GOVTN | FRED / BLS CES | 2015-01–2026-08 | 140 | `2d90bed2e9ea` |
| `data/ep_leisure.csv` | ELPA348LEIHN | FRED / BLS CES | 2015-01–2026-08 | 140 | `69913ab7999d` |
| `data/ep_mfg.csv` | ELPA348MFGN | FRED / BLS CES | 2015-01–2026-08 | 140 | `ce615a4b1bcb` |
| `data/ep_nonfarm.csv` | ELPA348NAN | FRED / BLS CES | 2015-01–2026-08 | 140 | `dd442092b8b3` |
| `data/ep_profbiz.csv` | ELPA348PBSVN | FRED / BLS CES | 2015-01–2026-08 | 140 | `bc6e0783a44d` |
| `data/ep_trade.csv` | ELPA348TRADN | FRED / BLS CES | 2015-01–2026-08 | 140 | `dc482a81a9c1` |
| `data/ep_unrate.csv` | ELPA348UR | FRED / BLS LAUS | 2015-01–2026-08 | 139 | `1a54ed3063c3` |
| `data/lc_unrate.csv` | LASC735UR | FRED / BLS LAUS | 2015-01–2026-08 | 139 | `aa3fc078aed8` |
| `data/mex_manufacturing.csv` | MEXPRMNTO01IXOBM | FRED / OECD MEI (discontinued 2024-03) | 2013-01–2024-03 | 135 | `78898c3916c8` |
| `data/peso_usd.csv` | EXMXUS | FRED / Federal Reserve H.10 | 2015-01–2026-09 | 141 | `335456909e25` |
| `data/tx_unrate.csv` | TXUR | FRED / BLS LAUS | 2015-01–2026-08 | 139 | `f0aabee17592` |
| `data/us_exports_mexico.csv` | EXPMX | FRED / Census FT-900 | 2015-01–2026-08 | 140 | `ef2abbe80b72` |
| `data/us_imports_mexico.csv` | IMPMX | FRED / Census FT-900 | 2015-01–2026-08 | 140 | `4d28b1a3f484` |
| `data/us_unrate.csv` | UNRATE | FRED / BLS CPS | 2015-01–2026-09 | 140 | `b2eafc38cae7` |
| `data/full/ep_nonfarm.csv` | ELPA348NAN | FRED / BLS CES | 2000-01–2026-08 | 320 | `9b6082e22a98` |
| `data/full/ep_unrate.csv` | ELPA348UR | FRED / BLS LAUS | 2000-01–2026-08 | 319 | `544f667df1bf` |
| `data/full/peso_usd.csv` | EXMXUS | FRED / Federal Reserve H.10 | 2000-01–2026-09 | 321 | `45469b3b4d1a` |
| `data/full/us_exports_mexico.csv` | EXPMX | FRED / Census FT-900 | 2000-01–2026-08 | 320 | `ff54173aabeb` |
| `data/full/us_imports_mexico.csv` | IMPMX | FRED / Census FT-900 | 2000-01–2026-08 | 320 | `345e49dfe37e` |

Full manifest with retrieval dates: `data/MANIFEST.json` (34 files, generated 2026-10-12), including the six BTS crossing files. All inputs are the latest available vintage at retrieval; Section 8 describes the real-time audit. Payroll series are not seasonally adjusted (NSA), so both the dashboard and the back-test use 12-month changes for employment (v5; earlier dashboards used 6-month changes). BTS port-of-entry crossings (1996→) are context and watch indicators only. CBP made Ysleta a separate port (2401) from El Paso (2402) on 16 March 2020; the border panel, lead/lag study and border-layer test add Ysleta back from that month, which removes what earlier versions described as a reporting break.

## 3. Index construction
**Stress signals.** For indicator *i* with raw series *x<sub>i,t</sub>*, the stress signal *s<sub>i,t</sub>* is: unemployment, 6-month difference; payrolls, −(12-month % change); imports and exports, −(12-month % change); peso, 6-month % change (depreciation positive); listings, 12-month % change; days on market, 12-month difference. Signs are chosen so that larger values mean more stress. The same definitions drive the dashboard and the back-test; every dashboard *z*, shifted by its publication lag, equals the back-test feature.

**Expanding-window standardisation (no look-ahead).** *z<sub>i,t</sub>* = clip( (*s<sub>i,t</sub>* − μ<sub>i,1:t</sub>) / σ<sub>i,1:t</sub>, −3, 3 ), where μ and σ (sample SD) use only observations from 2000 up to and including *t*, with a minimum of 36 observations (24 for the two housing series, which begin in 2016). Because the window is expanding, the statistic at any month is invariant to data published later — the property checked by the automated leakage tests.

**Layers and composite.** Layer scores are the equal-weighted mean of their indicators' *z*: local labour (unemployment, payrolls), border economy (imports, exports, peso), housing market (listings, days on market — a for-sale market measure, not a direct measure of household finances). The composite *z<sub>t</sub>* = Σ<sub>L</sub> *w<sub>L</sub>* *z<sub>L,t</sub>* / Σ<sub>L</sub> *w<sub>L</sub>* over the layers present, with *w* = (0.40, 0.35, 0.25). The display score is *S<sub>t</sub>* = 100 / (1 + exp(−1.1 *z<sub>t</sub>*)), so 50 corresponds to a historically typical month; the squash is monotone, so every rank-based result is independent of it. Levels describe distance from normal: Calm < 35 ≤ Near normal < 50 ≤ Above normal < 65 ≤ High; the ≥ 65 alert is the only operational rule.

**Headline convention (v4).** The headline month is the latest month at which every expected indicator has a *z*-score. Later months where lagging series are missing from the data snapshot are reported as a *nowcast* with the missing indicators listed. Currently the headline is August 2026 at 40.0 (Near normal).

**Decomposition contract.** Writing *z<sub>t</sub>* = Σ<sub>i</sub> *c<sub>i,t</sub>* with *c<sub>i,t</sub>* = *w<sub>L(i)</sub>* *z<sub>i,t</sub>* / (*n<sub>L(i)</sub>* Σ<sub>L</sub> *w<sub>L</sub>*), contributions are exact and additive in *z*-space; point shares of (*S<sub>t</sub>* − 50) are allocated pro rata to *c<sub>i,t</sub>*. Month-over-month attribution applies the same rule to Δ*c<sub>i,t</sub>*. **Model sensitivity range.** The 10th–90th percentile of *S<sub>t</sub>* across leave-one-indicator-out recomputations and 200 Dirichlet draws of the layer weights (concentration 60 around the published weights); currently 38–42.

## 4. Validation design
**Targets (fixed before evaluation).** T1: the El Paso MSA seasonally-adjusted unemployment rate rises by ≥ 0.5 percentage points at any point in months *t*+1…*t*+6 relative to month *t*. T2: El Paso year-over-year nonfarm payroll growth is negative at any point in *t*+1…*t*+6 — which also counts months already inside a downturn, so T2 mixes warning with detection (Section 5.1 separates them). A *deterioration event* is a maximal run of consecutive target months; an *alert episode* is a maximal run of consecutive months with *S<sub>t</sub>* ≥ 65. Episodes and events are the units of inference; month-level metrics are reported as secondary and labelled autocorrelated.

**Information sets.** At decision month *t* the back-test may use labour and housing data through *t*−1, trade data through *t*−2 and the peso through *t*. Every *z* is recomputed under these lags. Two automated checks confirm the lags and two confirm that deleting all data after *t* leaves the month-*t* score unchanged (12 checks in total, `test_backtest.py`).

**Benchmarks.** A local Sahm rule (three-month average unemployment ≥ 0.5 pp above its minimum over the prior twelve three-month averages, computed on data through *t*−1) and, when its data are present locally, a Dallas Fed El Paso Business-Cycle Index momentum rule. A rolling-origin logistic regression on the same seven *z*-features (annual retraining from 2013) is the model benchmark.

## 5. Results
### 5.1 Warning before onset vs. detection after onset (pre-registered 2026-10-12)
Onsets: payroll growth turning negative after six non-negative months; unemployment first standing ≥ 0.5 pp above its prior-12-month low after a year without that condition. An alert in the six months before an onset is an advance warning; otherwise an alert in the onset month or the six after is a detection.

| Rule | Downturn type | Onsets | Warned before | Detected after | Missed | False-alarm episodes |
|---|---|---|---|---|---|---|
| BorderPulse score ≥ 65 | Payroll growth turns negative | 2 | 1 | 1 | 0 | 0 of 2 |
| BorderPulse score ≥ 65 | Unemployment +0.5 pp | 3 | 0 | 2 | 1 | 0 of 2 |
| Local Sahm rule | Payroll growth turns negative | 2 | 1 | 1 | 0 | 2 of 5 |
| Local Sahm rule | Unemployment +0.5 pp | 3 | 0 | 3 | 0 | 1 of 5 |

In the back-test, 19 of the 21 alert months already had negative payroll growth in the alert month itself. The one advance warning is October 2008, two months before payroll growth turned negative in December 2008; the 2020 alert fired in April, the month the downturn appears in the data (useful because April data were published in May, but a detection). With so few onsets every rate interval spans most of [0, 1]; the counts are the claim.

### 5.2 Episode-level record (T1/T2 windows)
| Rule | Alert episodes | True warnings | Unemployment events caught | Payroll downturns caught | Episode precision 95% CI (exact) |
|---|---|---|---|---|---|
| BorderPulse ≥ 65 | 2 | 1 | 1 of 6 | 2 of 3 | [0.013, 0.987] |
| Local Sahm rule | 5 | 3 | 4 of 6 | 3 of 3 | [0.147, 0.947] |

With realistic publication lags the COVID alert fires in April 2020, one month after the shock. The slower deteriorations of 2004, 2010 and late 2019 are missed. Months scored below 35 were followed by deterioration 19% of the time against a base rate of 12% — the calm band is not a safety signal.

### 5.3 Month-level discrimination with resampling uncertainty
| Metric | Index | Block-bootstrap 95% | Sahm statistic | 95% | Δ (index − Sahm) | 95% |
|---|---|---|---|---|---|---|
| ROC-AUC, T1 | 0.472 | [0.165, 0.736] | 0.606 | [0.415, 0.781] | -0.134 | [-0.459, 0.198] |
| ROC-AUC, T2 | 0.825 | [0.634, 0.946] | 0.892 | [0.731, 0.991] | -0.067 | [-0.296, 0.146] |
| PR-AUC, T1 | 0.207 | [0.044, 0.419] | | | | |

Circular moving-block bootstrap, block length 12 months, B = 1000 (Künsch 1989). Placebo tests rotate the score path against the target by every offset of at least 13 months: p(AUC) = 0.563 for T1 and 0.000 for T2; the null mean AUC is 0.49 for T2 with 95% range [0.251, 0.763]. Episode-level bootstrap intervals: T2 recall [0.164, 1.000]; the T2 precision interval is degenerate at 1 because every resampled alert block lies inside a downturn — a reminder that two episodes cannot estimate a rate.

### 5.4 Lead/lag correlations with HAC inference
| Indicator → EP payroll YoY growth | r at lead 0 | p (HAC) | Best lead | r | p (HAC) | p (Bonferroni, 13 leads) |
|---|---|---|---|---|---|---|
| US imports from Mexico, YoY % | +0.527 | 0.0000 | 0 | +0.527 | 0.0000 | 0.001 |
| US exports to Mexico, YoY % | +0.534 | 0.0001 | 0 | +0.534 | 0.0001 | 0.001 |
| Peso depreciation, 6-mo % | +0.144 | 0.2495 | 7 | +0.301 | 0.0209 | 0.271 |
| Mexico manufacturing, YoY % | +0.619 | 0.0002 | 0 | +0.619 | 0.0002 | 0.003 |
| Border crossings: trucks, YoY % | +0.279 | 0.0156 | 0 | +0.279 | 0.0156 | 0.203 |
| Border crossings: personal vehicles, YoY % | +0.658 | 0.0000 | 0 | +0.658 | 0.0000 | 0.000 |
| Border crossings: pedestrians, YoY % | +0.354 | 0.0964 | 0 | +0.354 | 0.0964 | 1.000 |

Newey–West standard errors with a Bartlett kernel and L = 12 (Newey & West 1987). Crossings combine the El Paso and Ysleta ports. Trade flows, Mexico manufacturing and personal-vehicle crossings are reliably *coincident* with El Paso payroll growth. The peso's best lead (7 months, r = 0.301) has a family-wise p of 0.2713: suggestive, not established. An earlier version of this project described the peso as a leading signal at 5% significance; that claim is withdrawn.

### 5.5 Calibration
| Band | n | Payroll downturn within 6 mo | Wilson 95% | Unemployment +0.5 pp within 6 mo | Wilson 95% |
|---|---|---|---|---|---|
| Calm | 67 | 2% | [0.003, 0.080] | 19% | [0.117, 0.304] |
| Near normal | 119 | 8% | [0.046, 0.148] | 6% | [0.029, 0.116] |
| Above normal | 65 | 14% | [0.075, 0.243] | 11% | [0.053, 0.206] |
| High | 21 | 100% | [0.845, 1.000] | 33% | [0.172, 0.546] |

Base rates: T2 15%, T1 12%. Brier skill of *S*/100 against the base rate is -1.162 (T1) and -0.392 (T2): the score is a ranking, not a probability, and must not be read as one.

### 5.6 Robustness grid
The composite was recomputed under 90 conventions (five weight vectors × minimum history 24/36/48 × z-clip 2/3/4 × publication lags shifted by 0/+1 month) with targets and the ≥65 rule held fixed. Both historical alerts fire in 100% (2008) and 100% (2020) of configurations; the record is *clean* (those two episodes and nothing else) in 73%. T2 AUC ranges 0.79–0.87 (median 0.82); T1 AUC ranges 0.41–0.50 and never exceeds 0.5. Equal layer weights correlate 99.3% with the published score (maximum gap 8.6 points).

### 5.7 Border-layer test: national trade vs. port-of-entry crossings (pre-registered)
A regional research group noted that national U.S.–Mexico trade is largely through-traffic for El Paso. Three border layers were compared on the same targets and lags: A (published: imports, exports, peso), B (crossings replace trade), C (trade plus crossings); S adds trucks as a sensitivity only.

| Variant | Sample | AUC T1 | Δ vs A, 95% | AUC T2 | Δ vs A, 95% |
|---|---|---|---|---|---|
| B · Crossings replace trade | all months | 0.602 | +0.125 [-0.003, 0.295] | 0.888 | +0.057 [-0.032, 0.179] |
| B · Crossings replace trade | excl. 2020–21 | 0.578 | +0.158 [0.023, 0.359] | 0.868 | +0.039 [-0.092, 0.161] |
| C · Trade + crossings | all months | 0.540 | +0.063 [0.006, 0.121] | 0.900 | +0.069 [0.000, 0.177] |
| C · Trade + crossings | excl. 2020–21 | 0.496 | +0.075 [0.013, 0.130] | 0.880 | +0.051 [-0.031, 0.152] |
| S · Sensitivity: B + trucks (not eligible: reporting breaks) | all months | 0.569 | +0.093 [-0.014, 0.195] | 0.904 | +0.072 [-0.009, 0.192] |
| S · Sensitivity: B + trucks (not eligible: reporting breaks) | excl. 2020–21 | 0.535 | +0.114 [-0.001, 0.223] | 0.901 | +0.072 [-0.040, 0.225] |

Decision rule: a variant is a candidate only if its 95% interval is above zero on both targets, with and without 2020–21. Result: composite unchanged: no variant beats the published border layer with an interval above zero on both targets, with and without COVID. v2 2026-10-12: crossings = El Paso + Ysleta ports (CBP port split 2020-03-16); v1 used El Paso only and is superseded. Design unchanged.

### 5.8 Horizons
| Event | Horizon | Base rate | P(event | current band) | ROC-AUC (index) |
|---|---|---|---|---|
| Payroll growth negative within horizon | 3m | 13% | 7% | 0.86 |
| Payroll growth negative within horizon | 6m | 15% | 8% | 0.82 |
| Payroll growth negative within horizon | 12m | 20% | 14% | 0.72 |
| Unemployment +0.5 pp | 3m | 6% | 3% | 0.75 |
| Unemployment +0.5 pp | 6m | 12% | 6% | 0.47 |
| Unemployment +0.5 pp | 12m | 19% | 13% | 0.42 |

## 6. Interpretation
The evidence supports a narrow claim: when El Paso is in or entering a payroll downturn the composite is usually already unusual, and it has not produced a false High reading in 23 years. Measured from the date downturns began, it gave one advance warning (2008) and one prompt detection (2020). It does not anticipate unemployment spikes — on that target a plain Sahm rule is better and neither warns ahead. The practical reading is a screening device: High means 'look at the underlying indicators now'; Calm and Near normal mean 'conditions resemble ordinary months', which historically still preceded deterioration roughly one month in five.

## 7. Changes in v5
The v4 dashboard used 6-month payroll changes and a 2015 history window while the back-test used 12-month changes and a 2000 window, so published validation did not describe the displayed score; v5 uses one definition. v5 adds the onset evaluation (5.1), adds the Ysleta port to crossings, refreshes data to the latest published months, and fixes several display and date issues identified in an external review (see `CHANGELOG.md`).

## 8. Real-time vintage audit
All results above use latest-vintage data. BLS LAUS and CES series are benchmarked annually and first prints at turning points are often revised by several tenths. `vintage_audit.py` rebuilds the score path month by month from the data vintage available at each decision date (ALFRED exports or FRED-API realtime observations) and compares alert episodes and AUC with the revised path. Six synthetic-vintage checks pass (`test_vintage_audit.py`). Status: **pending** — the vintage files must be exported on a machine with full internet access. Until then the revised-data caveat is the largest open limitation of every figure in this note.

## 9. Limitations
Six deterioration events since 2003, two of them COVID-driven — every rate carries a wide interval and ex-COVID results weaken. Revised rather than real-time vintages (Section 8). Housing enters only from mid-2019, so earlier composites are a two-layer model (marked on the history chart). NSA employment series. Overlapping windows in all 6- and 12-month transforms (addressed by HAC and block methods, not eliminated). Crossings cover the El Paso and Ysleta ports only (Santa Teresa and Tornillo not included); the planned Bridge of the Americas rebuild is expected to move commercial trucks between ports. Constants are conventions with published sensitivity, not estimates. The index is not a probability, not a forecast and not official statistics.

## 10. Reproducibility
`python3 refresh.py --no-fetch` reruns pipeline → backtest → 12 leakage checks → benchmarks → lead/lag → horizons → inference → border test → onset evaluation → vintage audit → manifest → this note → dashboard → brief, from the CSVs whose hashes are in `data/MANIFEST.json`. `python3 refresh.py` additionally re-pulls every FRED and BTS series. Dependencies are pinned in `requirements.txt` (numpy 2.4.4, scipy 1.17.1, scikit-learn 1.8.0). Random seeds are fixed (42). `CHANGELOG.md` records every versioned change; `CITATION.cff` gives the citation.

## References
Clopper, C. J. & Pearson, E. S. (1934). The use of confidence or fiducial limits illustrated in the case of the binomial. *Biometrika* 26, 404–413.  
Künsch, H. R. (1989). The jackknife and the bootstrap for general stationary observations. *Annals of Statistics* 17, 1217–1241.  
Newey, W. K. & West, K. D. (1987). A simple, positive semi-definite, heteroskedasticity and autocorrelation consistent covariance matrix. *Econometrica* 55, 703–708.  
Phillips, K. R. (2004). A new monthly index of the Texas business cycle. Federal Reserve Bank of Dallas Working Paper 0401 (basis of the Dallas Fed metro business-cycle indexes).  
Sahm, C. (2019). Direct stimulus payments to individuals. In *Recession Ready: Fiscal Policies to Stabilize the American Economy*, Brookings/Hamilton Project.  
Wilson, E. B. (1927). Probable inference, the law of succession, and statistical inference. *JASA* 22, 209–212.  

*Generated 2026-10-20 by make_technote.py from the pipeline outputs; model v6.1.1.*
