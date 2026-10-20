"""
Multi-horizon outlook: 3 / 6 / 12-month versions of both targets, evaluated
with the same leakage rules as backtest.py, plus:
  * empirical P(event | current score band)  — transparent, no fitting
  * rolling-origin logistic OOS metrics per horizon, and a current-month
    probability from a model trained on all COMPLETE months (labeled estimate)

v5: band names describe distance from El Paso's normal (Calm / Near normal /
Above normal / High); boundaries unchanged.

Writes validation/horizons.json.
"""
import json, os
import numpy as np
from sklearn.linear_model import LogisticRegression
import backtest as bt

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "validation")
BANDS = [(0, 35, "Calm"), (35, 50, "Near normal"), (50, 65, "Above normal"), (65, 101, "High")]

def target_ur(t, h):
    fut = [bt.ur.get(bt.madd(t, k)) for k in range(1, h + 1)]
    if any(v is None for v in fut) or t not in bt.ur: return None
    return int(max(v - bt.ur[t] for v in fut) >= bt.RISE)

def target_emp(t, h):
    fut = [bt.emp_yoy_raw.get(bt.madd(t, k)) for k in range(1, h + 1)]
    if any(v is None for v in fut): return None
    return int(min(fut) < 0)

months = bt.months_bt
score_by_m = dict(zip(months, bt.score_arr))
X_by_m = dict(zip(months, bt.X))
year_of = {m: int(m[:4]) for m in months}

def band_of(s):
    for lo, hi, name in BANDS:
        if lo <= s < hi: return name

# truly latest scorable month (target may be unknown there — that's the point of a forecast)
latest_scored, latest_feats = None, None
for m in reversed(bt.MONTHS):
    s, feats = bt.score_at(m)
    if s is not None:
        latest_scored = m
        score_by_m[m] = s
        latest_feats = [feats[k] if feats[k] is not None else 0.0 for k in bt.FEATS] \
                       + [0.0 if feats["listings_yoy"] is None else 1.0]
        break
X_by_m[latest_scored] = np.array(latest_feats)
cur_band = band_of(score_by_m[latest_scored])
out = {"horizons": {}, "current": {"month": latest_scored,
                                   "score": score_by_m[latest_scored], "band": cur_band}}

for h in (3, 6, 12):
    for tname, tf in (("unemployment_+0.5pp", target_ur), ("payroll_growth_negative", target_emp)):
        ms = [m for m in months if tf(m, h) is not None]
        y = np.array([tf(m, h) for m in ms])
        s = np.array([score_by_m[m] for m in ms])
        pred = (s >= bt.ALERT).astype(int)
        met = bt.metrics(pred, y)
        met["ROC_AUC"] = bt.roc_auc(s, y)
        met["PR_AUC"] = bt.pr_auc(s, y)
        met["base_rate"] = round(float(y.mean()), 3)
        met["n"] = len(ms)
        # empirical band probabilities
        bands = {}
        for lo, hi, name in BANDS:
            mask = (s >= lo) & (s < hi)
            bands[name] = {"n": int(mask.sum()),
                           "p_event": (round(float(y[mask].mean()), 3) if mask.sum() >= 5 else None)}
        # rolling-origin logistic OOS
        Xh = np.array([X_by_m[m] for m in ms])
        yrs = np.array([year_of[m] for m in ms])
        oos = np.full(len(ms), np.nan)
        for yr in range(2013, yrs.max() + 1):
            tr, te = yrs < yr, yrs == yr
            if te.sum() == 0 or y[tr].sum() == 0: continue
            clf = LogisticRegression(C=1.0, max_iter=2000).fit(Xh[tr], y[tr])
            oos[te] = clf.predict_proba(Xh[te])[:, 1]
        om = ~np.isnan(oos)
        logi = {"ROC_AUC": bt.roc_auc(oos[om], y[om]) if y[om].sum() else None,
                "PR_AUC": bt.pr_auc(oos[om], y[om]) if y[om].sum() else None,
                "Brier": bt.brier(oos[om], y[om]),
                "oos_base_rate": round(float(y[om].mean()), 3), "oos_n": int(om.sum())}
        # current-month estimate: fit on all complete months, predict latest scored month
        clf = LogisticRegression(C=1.0, max_iter=2000).fit(Xh, y)
        cur_p = float(clf.predict_proba([X_by_m[latest_scored]])[0, 1])
        key = f"{h}m"
        out["horizons"].setdefault(key, {})[tname] = {
            "index_at_65": {k: (round(v, 3) if isinstance(v, float) else v) for k, v in met.items()},
            "band_probabilities": bands,
            "logistic_oos": {k: (round(v, 3) if isinstance(v, float) else v) for k, v in logi.items()},
            "current_band_p": bands.get(cur_band, {}).get("p_event"),
            "current_logistic_p": round(cur_p, 3),
        }

out["caveats"] = [
    "Band probabilities are historical frequencies 2003-2025 (n per band shown); with 6 deterioration episodes they are rough guides, not calibrated forecasts.",
    "The payroll event counts months already in a downturn (growth negative at any point in the horizon).",
    "current_logistic_p is fit on all complete months (in-sample for the final fit); OOS quality per horizon is reported separately and is weak for the unemployment target.",
    "12-month windows overlap heavily; effective sample is far smaller than n.",
]
with open(os.path.join(OUT, "horizons.json"), "w") as f:
    json.dump(out, f, indent=1, default=float)

for h in ("3m", "6m", "12m"):
    for tname, d in out["horizons"][h].items():
        m = d["index_at_65"]
        print(f"{h:>4s} {tname:26s} base={m['base_rate']:.3f} ROC={m['ROC_AUC']:.2f} "
              f"P(evt|{cur_band})={d['current_band_p']} logiP={d['current_logistic_p']}")
