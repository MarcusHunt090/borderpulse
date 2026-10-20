"""
BorderPulse v3 — benchmark rules and episode-level inference.

Evaluates the >=65 alert AGAINST transparent incumbent rules on the same
real-time information sets used by backtest.py:

  * local Sahm rule : 3-mo avg EP unemployment rises >=0.5pp above its
                      minimum over the trailing 12 months (computed on data
                      through t-1, mirroring the labor publication lag).
  * Dallas Fed El Paso Business-Cycle Index momentum rule (6-mo annualized
    growth < 0, 1-month lag) — ONLY if data/extra/dallas_fed_bci.csv exists;
    the xlsx cannot be fetched from the cloud sandbox (refresh.py fetches it
    locally). Absent data => reported as unavailable, never invented.

All rules are scored EPISODE-FIRST: alert episodes (consecutive alert months)
and deterioration events (consecutive target months) are the units, with exact
Clopper-Pearson 95% intervals on the tiny counts. Month-level metrics are kept
as secondary, explicitly labeled autocorrelated.

Also: equal-weights sensitivity of the composite (1/3,1/3,1/3 vs 40/35/25).

Writes validation/benchmarks.json and validation/lab_data.json.
"""
import csv, json, math, os
import numpy as np
from scipy.stats import beta

import backtest as bt

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "validation")
EXTRA = os.path.join(bt.DATA, "extra")

def cp_interval(k, n, conf=0.95):
    """Exact Clopper-Pearson interval for k successes of n."""
    if n == 0:
        return [None, None]
    a = (1 - conf) / 2
    lo = 0.0 if k == 0 else float(beta.ppf(a, k, n - k + 1))
    hi = 1.0 if k == n else float(beta.ppf(1 - a, k + 1, n - k))
    return [round(lo, 3), round(hi, 3)]

months_bt = bt.months_bt
Y1 = {m: int(y) for m, y in zip(months_bt, bt.Y)}
Y2 = {m: (int(r["Y2"]) if r["Y2"] is not None else None) for m, r in zip(months_bt, bt.rows)}

def runs_of_bool(flags):
    """[(start,end)] runs of True over months_bt order."""
    runs, cur = [], None
    for m in months_bt:
        if flags.get(m):
            cur = [m, m] if cur is None else [cur[0], m]
        elif cur:
            runs.append(tuple(cur)); cur = None
    if cur: runs.append(tuple(cur))
    return runs

def episode_eval(alert, target):
    """Episode-first evaluation of a boolean alert rule vs a 0/1 target dict."""
    tgt = {m: v for m, v in target.items() if v is not None and m in set(months_bt)}
    ms = [m for m in months_bt if m in tgt]
    al = {m: bool(alert.get(m)) for m in ms}
    a_runs = runs_of_bool(al)
    e_runs = []
    cur = None
    for m in ms:
        if tgt[m] == 1:
            cur = [m, m] if cur is None else [cur[0], m]
        elif cur:
            e_runs.append(tuple(cur)); cur = None
    if cur: e_runs.append(tuple(cur))
    def overlap(a, b): return not (a[1] < b[0] or b[1] < a[0])
    true_warn = sum(1 for a in a_runs if any(overlap(a, e) for e in e_runs))
    detected  = sum(1 for e in e_runs if any(overlap(a, e) for a in a_runs))
    n_al, n_ev = len(a_runs), len(e_runs)
    # month-level secondary
    yv = np.array([tgt[m] for m in ms]); av = np.array([1 if al[m] else 0 for m in ms])
    tp = int(((av == 1) & (yv == 1)).sum()); fp = int(((av == 1) & (yv == 0)).sum())
    fn = int(((av == 0) & (yv == 1)).sum()); tn = int(((av == 0) & (yv == 0)).sum())
    return {
        "episode": {
            "alert_episodes": n_al, "true_warnings": true_warn, "false_alarms": n_al - true_warn,
            "episode_precision": (round(true_warn / n_al, 3) if n_al else None),
            "episode_precision_ci95": cp_interval(true_warn, n_al),
            "events": n_ev, "events_detected": detected,
            "episode_recall": (round(detected / n_ev, 3) if n_ev else None),
            "episode_recall_ci95": cp_interval(detected, n_ev),
            "alert_windows": [list(a) for a in a_runs],
            "effective_note": f"effective sample = {n_al} alert episodes / {n_ev} events; months are NOT independent",
        },
        "month_level_secondary": {
            "TP": tp, "FP": fp, "FN": fn, "TN": tn, "n": len(ms),
            "recall": round(tp / (tp + fn), 3) if tp + fn else None,
            "precision": round(tp / (tp + fp), 3) if tp + fp else None,
            "false_alarm_rate": round(fp / (fp + tn), 3) if fp + tn else None,
            "caveat": "overlapping windows; autocorrelated; do not read as independent trials",
        },
    }

# ---------------- rule 1: the BorderPulse >=65 alert ----------------
score_by_m = dict(zip(months_bt, bt.score_arr))
alert_bp = {m: score_by_m[m] >= bt.ALERT for m in months_bt}

# ---------------- rule 2: local Sahm rule ----------------
ur = bt.ur
def three_avg(d):
    xs = [ur.get(bt.madd(d, -i)) for i in range(3)]
    return None if any(x is None for x in xs) else sum(xs) / 3
sahm_val = {}
for m in bt.MONTHS:
    a = three_avg(m)
    if a is None: continue
    window = [three_avg(bt.madd(m, -i)) for i in range(12)]
    window = [w for w in window if w is not None]
    if len(window) >= 12:
        sahm_val[m] = round(a - min(window), 3)
alert_sahm = {}
for t in months_bt:
    v = sahm_val.get(bt.madd(t, -1))          # labor data through t-1
    if v is not None:
        alert_sahm[t] = v >= 0.5

# ---------------- rule 3: Dallas Fed BCI momentum (if data present) ----------------
bci_path = os.path.join(EXTRA, "dallas_fed_bci.csv")
alert_bci, bci_status = None, "unavailable — data/extra/dallas_fed_bci.csv absent (xlsx not fetchable from cloud sandbox; run refresh.py locally)"
if os.path.exists(bci_path):
    bci = {}
    for r in csv.DictReader(open(bci_path)):
        v = r["value"].strip()
        if v and v != ".":
            bci[r["date"][:7]] = float(v)
    g6 = bt.pct_k(bci, 6)
    alert_bci = {}
    for t in months_bt:
        g = g6.get(bt.madd(t, -1))
        if g is not None:
            alert_bci[t] = ((1 + g / 100) ** 2 - 1) < 0
    bci_status = f"loaded ({min(bci)}..{max(bci)})"

# ---------------- evaluate all rules on both targets ----------------
rules = {"borderpulse_ge65": alert_bp, "local_sahm_rule": alert_sahm}
if alert_bci: rules["dallas_fed_bci_momentum"] = alert_bci
results = {}
for name, al in rules.items():
    results[name] = {
        "unemployment_+0.5pp_6m": episode_eval(al, Y1),
        "payroll_growth_negative_6m": episode_eval(al, Y2),
    }

# ---------------- equal-weights sensitivity ----------------
saved = bt.WEIGHTS
bt.WEIGHTS = {"labor": 1/3, "border": 1/3, "household": 1/3}
eq_scores = {}
for t in months_bt:
    s, _ = bt.score_at(t)
    if s is not None: eq_scores[t] = s
bt.WEIGHTS = saved
common = [m for m in months_bt if m in eq_scores]
base = np.array([score_by_m[m] for m in common]); eqs = np.array([eq_scores[m] for m in common])
alert_eq = {m: eq_scores[m] >= bt.ALERT for m in common}
eq_eval = episode_eval(alert_eq, Y1)
sensitivity = {
    "weights_compared": {"baseline": saved, "alternative": {"labor": 0.333, "border": 0.333, "household": 0.333}},
    "score_correlation": round(float(np.corrcoef(base, eqs)[0, 1]), 4),
    "mean_abs_score_diff": round(float(np.mean(np.abs(base - eqs))), 2),
    "max_abs_score_diff": round(float(np.max(np.abs(base - eqs))), 2),
    "equal_weight_alert_episodes_T1": eq_eval["episode"]["alert_windows"],
    "same_alert_months": bool(all((score_by_m[m] >= bt.ALERT) == (eq_scores[m] >= bt.ALERT) for m in common)),
}

summary = {
    "framing": "Episode-first: alert episodes and deterioration events are the units of inference. "
               "Exact Clopper-Pearson 95% intervals shown; with this few events no rule's precision or "
               "recall is estimated precisely — counts, not rates, are the honest claims. The payroll target "
               "counts months already in a downturn; see onset_eval.json for warnings vs detections.",
    "sample": {"months": [months_bt[0], months_bt[-1]], "n_months": len(months_bt)},
    "rules": results,
    "sahm_rule_definition": "3-mo avg EP SA unemployment minus its min over the trailing 12 3-mo averages >= 0.5pp, using data through t-1",
    "bci_benchmark_status": bci_status,
    "weight_sensitivity": sensitivity,
    "interpolated_points": bt.INTERPOLATED,
}
with open(os.path.join(OUT, "benchmarks.json"), "w") as f:
    json.dump(summary, f, indent=1, default=str)

# ---------------- Research Lab payload ----------------
# Everything the in-browser lab needs to recombine the model client-side:
# lag-adjusted z features per decision month (exactly what score_at used),
# plus the raw target series so users can redefine the downturn.
lab = {
    "months": months_bt,
    "features": {k: [ (r[f"z_{k}"] if r[f"z_{k}"] is not None else None) for r in bt.rows ] for k in bt.FEATS},
    "feature_meta": {k: {"layer": bt.SIGNALS[k][0], "lag": bt.SIGNALS[k][1]} for k in bt.FEATS},
    "baseline_weights": bt.WEIGHTS,
    "alert_threshold": bt.ALERT,
    "squash": {"slope": 1.1, "formula": "100/(1+exp(-slope*z))"},
    "ur": {m: v for m, v in bt.ur.items() if m >= "2002-01"},
    "emp_yoy": {m: round(v, 3) for m, v in bt.emp_yoy_raw.items() if m >= "2002-01"},
    "note": "features are the publication-lag-adjusted expanding-window z-scores used at each decision month; "
            "recombining them with new weights is leakage-free by construction. Changing transforms or adding "
            "indicators requires the Python pipeline.",
}
with open(os.path.join(OUT, "lab_data.json"), "w") as f:
    json.dump(lab, f, separators=(",", ":"))

for name, r in results.items():
    e1 = r["unemployment_+0.5pp_6m"]["episode"]; e2 = r["payroll_growth_negative_6m"]["episode"]
    print(f"{name:26s} T1 alerts={e1['alert_episodes']} true={e1['true_warnings']} "
          f"det={e1['events_detected']}/{e1['events']} precCI={e1['episode_precision_ci95']} | "
          f"T2 alerts={e2['alert_episodes']} true={e2['true_warnings']} det={e2['events_detected']}/{e2['events']}")
print("equal-weights: corr", sensitivity["score_correlation"], "same alerts:", sensitivity["same_alert_months"])
print("BCI:", bci_status)
