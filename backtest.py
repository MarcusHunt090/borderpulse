"""
BorderPulse Phase 1 validation: does the El Paso shock score predict
labor-market deterioration in the following six months?

PRIMARY TARGET (fixed before evaluation; not tuned on results):
  Y_t = 1 if the El Paso MSA seasonally-adjusted unemployment rate rises by
  >= 0.5 percentage points at any point in months t+1 .. t+6, relative to
  its level in month t.  Series: FRED ELPA348UR (SA, monthly, 2000-01 onward,
  revised/latest-vintage data — NOT real-time vintages; see limitations).

SECONDARY TARGET:
  S_t = 1 if El Paso year-over-year nonfarm payroll growth (FRED ELPA348NAN,
  NSA — YoY is used precisely because the series is NSA) is negative at any
  point in months t+1 .. t+6. NOTE (v5): this also counts months when growth is
  already negative, so it mixes warning and detection; onset_eval.py separates them.

LEAKAGE CONTROLS:
  * Every z-score is computed on an EXPANDING window ending at the observation
    itself (min 36 obs; 24 for the short housing series) — no full-sample
    statistics anywhere.
  * Publication lags: at decision month t the score may use labor data through
    t-1, trade data through t-2, housing data through t-1, and market (peso)
    data through t.  The live dashboard shows the same model without these lags.
  * v5: the dashboard (pipeline.py) uses exactly these signal definitions
    (payroll YoY, history from 2000); verified feature-by-feature.
  * Logistic benchmark: rolling-origin (expanding) annual retraining;
    predictions for year Y use a model fit only on months < Y.
  * Revised-data caveat: FRED serves revised history.  Benchmark revisions
    (especially the CES/LAUS annual re-benchmark around COVID) can make both
    the score and the target cleaner than they were in real time.

Run:  python3 backtest.py     (writes CSV/JSON outputs into ./validation/)
"""
import csv, json, math, os
import numpy as np

BASE = os.path.dirname(os.path.abspath(__file__))
FULL = os.path.join(BASE, "data", "full")
DATA = os.path.join(BASE, "data")
OUT  = os.path.join(BASE, "validation")
os.makedirs(OUT, exist_ok=True)

ALERT = 65          # existing high-risk threshold — evaluated first, unchanged
CALM  = 35
HORIZON = 6
RISE = 0.5
COVID_T = ("2019-09", "2020-12")   # decision months whose windows/scores are COVID-driven

# ---------------- data ----------------
def load(path):
    d = {}
    for r in csv.DictReader(open(path)):
        v = r["value"].strip()
        if v and v != ".":
            d[r["date"][:7]] = float(v)
    return d

def month_range(a, b):
    y, m = map(int, a.split("-")); Y, M = map(int, b.split("-"))
    out = []
    while (y, m) <= (Y, M):
        out.append(f"{y:04d}-{m:02d}"); m += 1
        if m == 13: m, y = 1, y + 1
    return out

def madd(mo, k):
    y, m = map(int, mo.split("-")); m += k
    y += (m - 1) // 12; m = (m - 1) % 12 + 1
    return f"{y:04d}-{m:02d}"

ur       = load(os.path.join(FULL, "ep_unrate.csv"))
emp      = load(os.path.join(FULL, "ep_nonfarm.csv"))
imports  = load(os.path.join(FULL, "us_imports_mexico.csv"))
exports  = load(os.path.join(FULL, "us_exports_mexico.csv"))
peso     = load(os.path.join(FULL, "peso_usd.csv"))
listings = load(os.path.join(DATA, "ep_active_listings.csv"))
dom      = load(os.path.join(DATA, "ep_days_on_market.csv"))

# single known gap: 2025-10 (federal data pause). Linear-interpolate and flag.
INTERPOLATED = []
if "2025-10" not in ur and "2025-09" in ur and "2025-11" in ur:
    ur["2025-10"] = round((ur["2025-09"] + ur["2025-11"]) / 2, 2)
    INTERPOLATED.append(("ep_unrate", "2025-10", ur["2025-10"]))

# v5: calendar end derived from the data (was a hand-set month that had to be edited each refresh)
MONTHS = month_range("2000-01", max(max(s) for s in (ur, emp, imports, exports, peso, listings, dom)))

# ---------------- transforms (t-indexed, leakage-free) ----------------
def diff_k(s, k):
    return {m: s[m] - s[madd(m, -k)] for m in MONTHS if m in s and madd(m, -k) in s}

def pct_k(s, k):
    return {m: 100.0 * (s[m] / s[madd(m, -k)] - 1.0)
            for m in MONTHS if m in s and madd(m, -k) in s and s[madd(m, -k)] != 0}

def expanding_z(sig, min_n=36):
    vals, out = [], {}
    for m in MONTHS:
        if m in sig:
            vals.append(sig[m])
            if len(vals) >= min_n:
                a = np.array(vals)
                sd = a.std(ddof=1)
                out[m] = float(np.clip((sig[m] - a.mean()) / (sd if sd > 0 else 1.0), -3, 3))
    return out

def squash(z):  # identical to pipeline.py
    return 100.0 / (1.0 + math.exp(-1.1 * z))

# stress signals (positive = stress), each stamped at its DATA month
SIGNALS = {
    "ur_mom":       ("labor",     1, expanding_z(diff_k(ur, 6))),
    "emp_yoy":      ("labor",     1, expanding_z({m: -v for m, v in pct_k(emp, 12).items()})),
    "imports_yoy":  ("border",    2, expanding_z({m: -v for m, v in pct_k(imports, 12).items()})),
    "exports_yoy":  ("border",    2, expanding_z({m: -v for m, v in pct_k(exports, 12).items()})),
    "peso_mom":     ("border",    0, expanding_z(pct_k(peso, 6))),
    "listings_yoy": ("household", 1, expanding_z(pct_k(listings, 12), 24)),
    "dom_yoy":      ("household", 1, expanding_z(diff_k(dom, 12), 24)),
}
WEIGHTS = {"labor": 0.40, "border": 0.35, "household": 0.25}

def score_at(t):
    """Composite score using only data available at decision month t (with pub lags)."""
    layers = {}
    feats = {}
    for k, (layer, lag, z) in SIGNALS.items():
        m = madd(t, -lag)                    # newest data month usable at t
        v = z.get(m)
        feats[k] = v
        if v is not None:
            layers.setdefault(layer, []).append(v)
    if "labor" not in layers or "border" not in layers:
        return None, feats
    w = sum(WEIGHTS[L] for L in layers)
    zc = sum(WEIGHTS[L] * np.mean(vs) for L, vs in layers.items()) / w
    return round(squash(zc), 1), feats

# ---------------- targets ----------------
def target_primary(t):
    if t not in ur: return None
    fut = [ur.get(madd(t, k)) for k in range(1, HORIZON + 1)]
    if any(v is None for v in fut): return None
    return int(max(v - ur[t] for v in fut) >= RISE)

def event_date_primary(t):
    for k in range(1, HORIZON + 1):
        v = ur.get(madd(t, k))
        if v is not None and v - ur[t] >= RISE:
            return madd(t, k)
    return None

emp_yoy_raw = pct_k(emp, 12)
def target_secondary(t):
    fut = [emp_yoy_raw.get(madd(t, k)) for k in range(1, HORIZON + 1)]
    if any(v is None for v in fut): return None
    return int(min(fut) < 0)

# ---------------- monthly table ----------------
rows = []
for t in MONTHS:
    s, feats = score_at(t)
    y  = target_primary(t)
    ys = target_secondary(t)
    if s is None or y is None:
        continue
    rows.append({"month": t, "score": s, "Y": y, "Y2": ys,
                 **{f"z_{k}": (None if v is None else round(v, 3)) for k, v in feats.items()}})

months_bt = [r["month"] for r in rows]
score_arr = np.array([r["score"] for r in rows])
Y = np.array([r["Y"] for r in rows])
print(f"backtest sample: {months_bt[0]} .. {months_bt[-1]}  n={len(rows)}  "
      f"positives={Y.sum()} base_rate={Y.mean():.3f}")

# ---------------- deterioration events (runs of Y=1) ----------------
def runs_of(y, months):
    runs, cur = [], None
    for yi, m in zip(y, months):
        if yi == 1 and cur is None: cur = [m, m]
        elif yi == 1: cur[1] = m
        elif cur: runs.append(tuple(cur)); cur = None
    if cur: runs.append(tuple(cur))
    return runs

event_runs = runs_of(Y, months_bt)

# ---------------- metrics helpers ----------------
def confusion(pred, y):
    tp = int(((pred == 1) & (y == 1)).sum()); fp = int(((pred == 1) & (y == 0)).sum())
    fn = int(((pred == 0) & (y == 1)).sum()); tn = int(((pred == 0) & (y == 0)).sum())
    return tp, fp, fn, tn

def metrics(pred, y):
    tp, fp, fn, tn = confusion(pred, y)
    rec  = tp / (tp + fn) if tp + fn else float("nan")
    spec = tn / (tn + fp) if tn + fp else float("nan")
    prec = tp / (tp + fp) if tp + fp else float("nan")
    npv  = tn / (tn + fn) if tn + fn else float("nan")
    f1   = 2 * prec * rec / (prec + rec) if prec + rec and not math.isnan(prec) else float("nan")
    return {"TP": tp, "FP": fp, "FN": fn, "TN": tn,
            "recall": rec, "specificity": spec, "precision": prec, "NPV": npv,
            "false_alarm_rate": 1 - spec if not math.isnan(spec) else float("nan"),
            "F1": f1, "balanced_accuracy": (rec + spec) / 2}

def roc_auc(scores, y):
    if y.sum() in (0, len(y)): return float("nan")
    order = np.argsort(scores)
    ranks = np.empty(len(scores)); ranks[order] = np.arange(1, len(scores) + 1)
    # average ranks for ties
    s_sorted = np.array(scores)[order]
    i = 0
    while i < len(s_sorted):
        j = i
        while j + 1 < len(s_sorted) and s_sorted[j + 1] == s_sorted[i]: j += 1
        ranks[order[i:j + 1]] = (i + 1 + j + 1) / 2
        i = j + 1
    n1, n0 = int(y.sum()), int((1 - y).sum())
    return float((ranks[y == 1].sum() - n1 * (n1 + 1) / 2) / (n1 * n0))

def pr_auc(scores, y):
    if y.sum() == 0: return float("nan")
    idx = np.argsort(-np.array(scores))
    ys = np.array(y)[idx]
    tp = np.cumsum(ys); fp = np.cumsum(1 - ys)
    prec = tp / (tp + fp); rec = tp / ys.sum()
    # step integration over recall
    auc, prev_r = 0.0, 0.0
    for p, r in zip(prec, rec):
        auc += p * (r - prev_r); prev_r = r
    return float(auc)

def brier(prob, y):
    return float(np.mean((np.array(prob) - np.array(y)) ** 2))

# ---------------- 1) transparent index, existing thresholds ----------------
alert_pred = (score_arr >= ALERT).astype(int)
idx_month = metrics(alert_pred, Y)
idx_month["ROC_AUC"] = roc_auc(score_arr, Y)
idx_month["PR_AUC"]  = pr_auc(score_arr, Y)
idx_month["Brier_score_over_100"] = brier(score_arr / 100.0, Y)  # caveat: score is not a calibrated probability
idx_month["base_rate"] = float(Y.mean())

# calm analysis
calm_mask = score_arr < CALM
calm_ok = float((Y[calm_mask] == 0).mean()) if calm_mask.sum() else float("nan")

# threshold sensitivity (exploratory only — not a re-tuned model)
sens = []
for th in [55, 60, 65, 70, 75]:
    m = metrics((score_arr >= th).astype(int), Y)
    sens.append({"threshold": th, **{k: (round(v, 3) if isinstance(v, float) else v) for k, v in m.items()}})

# ---------------- 2) alert episodes ----------------
score_by_m = dict(zip(months_bt, score_arr))
alert_runs = runs_of(alert_pred, months_bt)
episodes = []
for a0, a1 in alert_runs:
    y0 = target_primary(a0)
    ev = event_date_primary(a0)
    # if the first alert month didn't lead the event, check any month in the episode
    if not ev:
        for m in month_range(a0, a1):
            ev = event_date_primary(m)
            if ev: break
    lead = None
    if ev:
        y0_, m0_ = int(a0[:4]) * 12 + int(a0[5:]), int(ev[:4]) * 12 + int(ev[5:])
        lead = m0_ - y0_
    episodes.append({"alert_start": a0, "alert_end": a1,
                     "score_at_start": score_by_m[a0],
                     "event_followed": bool(ev), "event_date": ev,
                     "lead_months": lead,
                     "classification": "true warning" if ev else "false alarm"})

# event coverage: which deterioration runs had an alert while their window was open
covered = []
for e0, e1 in event_runs:
    hit_months = [m for m in month_range(e0, e1) if score_by_m.get(m, 0) >= ALERT]
    ev_date = event_date_primary(e0)
    lead = None
    if hit_months and ev_date:
        h = hit_months[0]
        lead = (int(ev_date[:4]) * 12 + int(ev_date[5:])) - (int(h[:4]) * 12 + int(h[5:]))
    covered.append({"event_window_start": e0, "event_window_end": e1,
                    "deterioration_date": ev_date,
                    "detected": bool(hit_months),
                    "first_alert_in_window": hit_months[0] if hit_months else None,
                    "lead_months": lead})

# ---------------- 3) logistic benchmark (rolling-origin) ----------------
FEATS = list(SIGNALS.keys())
X = np.array([[r[f"z_{k}"] if r[f"z_{k}"] is not None else 0.0 for k in FEATS] for r in rows])
HAS_HOUSING = np.array([[0.0 if r["z_listings_yoy"] is None else 1.0] for r in rows])
X = np.hstack([X, HAS_HOUSING])          # missing-indicator, knowable in real time
FEAT_NAMES = FEATS + ["has_housing_data"]

from sklearn.linear_model import LogisticRegression
oos_prob = np.full(len(rows), np.nan)
first_test_year = 2013                    # train 2003..2012 first (contains 2008-09)
year_of = np.array([int(m[:4]) for m in months_bt])
coefs_last = None
for yr in range(first_test_year, int(months_bt[-1][:4]) + 1):
    tr = year_of < yr
    te = year_of == yr
    if te.sum() == 0 or Y[tr].sum() == 0: continue
    clf = LogisticRegression(C=1.0, max_iter=2000)   # L2 penalty is scikit-learn's default
    clf.fit(X[tr], Y[tr])
    oos_prob[te] = clf.predict_proba(X[te])[:, 1]
    coefs_last = dict(zip(FEAT_NAMES, np.round(clf.coef_[0], 3)))

oos_mask = ~np.isnan(oos_prob)
Yo, Po, So = Y[oos_mask], oos_prob[oos_mask], score_arr[oos_mask]
mo_oos = [m for m, k in zip(months_bt, oos_mask) if k]

def summarize(pred, y, scores, probs=None, label=""):
    m = metrics(pred, y)
    m["ROC_AUC"] = roc_auc(scores, y)
    m["PR_AUC"]  = pr_auc(scores, y)
    if probs is not None: m["Brier"] = brier(probs, y)
    m["model"] = label
    return m

# logistic alert threshold: fixed at 0.5 (no tuning on test period)
cmp_rows = [
    summarize((So >= ALERT).astype(int), Yo, So, So / 100.0, "transparent index (>=65)"),
    summarize((Po >= 0.5).astype(int),  Yo, Po, Po,        "logistic regression (p>=0.5)"),
    summarize(np.zeros(len(Yo), int),   Yo, np.full(len(Yo), Yo.mean()),
              np.full(len(Yo), Yo.mean()), "naive base rate (never alert)"),
]

# ---------------- 4) COVID sensitivity ----------------
def mask_excluding(months, lo, hi):
    return np.array([not (lo <= m <= hi) for m in months])

ex_all  = mask_excluding(months_bt, *COVID_T)
ex_oos  = mask_excluding(mo_oos,   *COVID_T)
idx_ex_covid = summarize((score_arr[ex_all] >= ALERT).astype(int), Y[ex_all],
                         score_arr[ex_all], score_arr[ex_all] / 100.0,
                         "index ex-COVID (full sample)")
cmp_ex = [
    summarize((So[ex_oos] >= ALERT).astype(int), Yo[ex_oos], So[ex_oos], So[ex_oos] / 100.0,
              "transparent index ex-COVID (OOS)"),
    summarize((Po[ex_oos] >= 0.5).astype(int), Yo[ex_oos], Po[ex_oos], Po[ex_oos],
              "logistic ex-COVID (OOS)"),
]

# secondary target quick check (index only)
Y2 = np.array([r["Y2"] if r["Y2"] is not None else -1 for r in rows])
m2 = Y2 >= 0
idx_secondary = summarize((score_arr[m2] >= ALERT).astype(int), Y2[m2],
                          score_arr[m2], None, "index vs payroll-growth-negative-within-6m")

# ---------------- outputs ----------------
with open(os.path.join(OUT, "backtest_monthly_results.csv"), "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0].keys()) + ["oos_logistic_prob"])
    w.writeheader()
    prob_by_m = dict(zip(mo_oos, Po))
    for r in rows:
        r2 = dict(r); r2["oos_logistic_prob"] = round(prob_by_m[r["month"]], 4) if r["month"] in prob_by_m else None
        w.writerow(r2)

with open(os.path.join(OUT, "backtest_alert_episodes.csv"), "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=episodes[0].keys()); w.writeheader(); w.writerows(episodes)

with open(os.path.join(OUT, "event_coverage.csv"), "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=covered[0].keys()); w.writeheader(); w.writerows(covered)

with open(os.path.join(OUT, "model_comparison.csv"), "w", newline="") as f:
    keys = ["model", "TP", "FP", "FN", "TN", "recall", "precision", "false_alarm_rate",
            "specificity", "NPV", "F1", "balanced_accuracy", "ROC_AUC", "PR_AUC", "Brier"]
    w = csv.DictWriter(f, fieldnames=keys, extrasaction="ignore")
    w.writeheader()
    for r in cmp_rows + cmp_ex:
        w.writerow({k: (round(v, 3) if isinstance(v, float) else v) for k, v in r.items()})

leads = [e["lead_months"] for e in episodes if e["lead_months"] is not None]
summary = {
    "backtest_period": [months_bt[0], months_bt[-1]],
    "n_months": len(rows),
    "target": "EP SA unemployment (ELPA348UR) rises >=0.5pp within 6 months",
    "base_rate": round(float(Y.mean()), 3),
    "n_positive_months": int(Y.sum()),
    "n_deterioration_events": len(event_runs),
    "event_windows": event_runs,
    "events_detected_at_65": sum(1 for c in covered if c["detected"]),
    "alert_episodes": len(episodes),
    "true_warnings": sum(1 for e in episodes if e["event_followed"]),
    "false_alarms": sum(1 for e in episodes if not e["event_followed"]),
    "median_lead_months": (float(np.median(leads)) if leads else None),
    "mean_lead_months": (round(float(np.mean(leads)), 1) if leads else None),
    "month_level_at_65": {k: (round(v, 3) if isinstance(v, float) else v) for k, v in idx_month.items()},
    "calm_reliability_below_35": round(calm_ok, 3),
    "threshold_sensitivity": sens,
    "oos_window": [mo_oos[0], mo_oos[-1]] if mo_oos else None,
    "oos_base_rate": round(float(Yo.mean()), 3),
    "model_comparison_oos": [{k: (round(v, 3) if isinstance(v, float) else v) for k, v in r.items()} for r in cmp_rows],
    "covid_excluded": {
        "index_full_sample": {k: (round(v, 3) if isinstance(v, float) else v) for k, v in idx_ex_covid.items()},
        "oos": [{k: (round(v, 3) if isinstance(v, float) else v) for k, v in r.items()} for r in cmp_ex],
        "exclusion_window_decision_months": COVID_T,
    },
    "secondary_target_index": {k: (round(v, 3) if isinstance(v, float) else v) for k, v in idx_secondary.items()},
    "logistic_last_coefficients": coefs_last,
    "interpolated_points": INTERPOLATED,
    "caveats": [
        "Revised (latest-vintage) data, not real-time vintages; benchmark revisions may flatter results.",
        "Score uses publication lags (labor/housing t-1, trade t-2, peso t-0); the dashboard shows the same model at observation dates.",
        "v5: dashboard and back-test share one model definition (payroll YoY, history from 2000).",
        "Housing layer only exists from mid-2019 onward; earlier scores are labor+border reweighted.",
        "Secondary target counts months already in a payroll downturn; see onset_eval.py for warnings vs detections.",
        "Brier for the index treats score/100 as a probability, which it is not calibrated to be.",
        "2025-10 EP unemployment missing at source; linearly interpolated.",
    ],
}
with open(os.path.join(OUT, "backtest_metrics.json"), "w") as f:
    json.dump(summary, f, indent=1, default=str)

print(json.dumps({k: summary[k] for k in ("backtest_period", "n_months", "n_deterioration_events", "alert_episodes", "true_warnings", "false_alarms")}, default=str))
