"""
Border lead/lag research question:
  Does deterioration in cross-border activity predict changes in El Paso
  employment 3-6 months later?

Method: Pearson correlation of each border indicator at month t with El Paso
nonfarm employment YoY growth at month t+k, k = 0..12.  n ~ 250-290 monthly
observations (2001+; Mexico manufacturing 2014+). Correlation, not causation;
formal HAC inference is in inference.py.

v5: crossings are El Paso + Ysleta ports. CBP split Ysleta (port 2401) out of
El Paso (2402) effective 2020-03-16, so the El Paso-only series lost Ysleta's
traffic from March 2020 — earlier versions misread that drop as a reporting break.

Writes validation/leadlag.json and prints a summary table.
"""
import json, os, csv
import numpy as np
import backtest as bt   # reuses loaded series + transforms (executes backtest)

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "validation")

emp_growth = bt.pct_k(bt.emp, 12)                     # EP payroll YoY growth, %

mex = {}
for r in csv.DictReader(open(os.path.join(bt.DATA, "mex_manufacturing.csv"))):
    mex[r["date"][:7]] = float(r["value"])

def _load_extra(name):
    p = os.path.join(bt.DATA, "extra", name)
    if not os.path.exists(p):
        return None
    d = {}
    for r in csv.DictReader(open(p)):
        v = r["value"].strip()
        if v and v != ".":
            d[r["date"][:7]] = float(v)
    return d

def combined_crossings(measure):
    """El Paso + Ysleta (El Paso alone before 2020-03, when it already included Ysleta)."""
    ep, ys = _load_extra(f"ep_crossings_{measure}.csv"), _load_extra(f"ysleta_crossings_{measure}.csv")
    if not ep: return None
    if not ys: return ep
    return {m: (v if m < "2020-03" else v + ys[m]) for m, v in ep.items() if m < "2020-03" or m in ys}

signals = {
    "US imports from Mexico, YoY %":  bt.pct_k(bt.imports, 12),
    "US exports to Mexico, YoY %":    bt.pct_k(bt.exports, 12),
    "Peso depreciation, 6-mo %":      {m: -v for m, v in bt.pct_k(bt.peso, 6).items()},
    "Mexico manufacturing, YoY %":    bt.pct_k(mex, 12),
}
# Same convention as imports/exports: raw YoY, LOWER = border stress, so a positive r at
# lead k means crossings strength moves with (or precedes) EP job growth k months later.
CROSSING_NOTE = ("crossings combine the El Paso and Ysleta ports (CBP port split 2020-03-16); "
                 "2020-21 travel restrictions dominate the YoY variance, so r values are descriptive only")
for measure, label in [("trucks", "Border crossings: trucks, YoY %"),
                       ("pov",    "Border crossings: personal vehicles, YoY %"),
                       ("ped",    "Border crossings: pedestrians, YoY %")]:
    s = combined_crossings(measure)
    if s:
        signals[label] = bt.pct_k(s, 12)
# note: peso is sign-flipped so that for every signal LOWER = border stress;
# a positive correlation at lead k then means border weakness -> weaker EP jobs k months later.

def corr_at_lead(sig, k):
    xs, ys = [], []
    for m, v in sig.items():
        tgt = emp_growth.get(bt.madd(m, k))
        if tgt is not None:
            xs.append(v); ys.append(tgt)
    if len(xs) < 30:
        return None, len(xs)
    return float(np.corrcoef(xs, ys)[0, 1]), len(xs)

results = {}
for name, sig in signals.items():
    row = []
    for k in range(0, 13):
        r, n = corr_at_lead(sig, k)
        row.append({"lead": k, "r": (round(r, 3) if r is not None else None), "n": n})
    valid = [x for x in row if x["r"] is not None]
    best = max(valid, key=lambda x: abs(x["r"]))
    r0 = row[0]["r"]
    results[name] = {"by_lead": row, "best_lead": best["lead"], "best_r": best["r"],
                     "r_at_0": r0, "n": best["n"],
                     "sig_threshold": round(2 / (best["n"] ** 0.5), 3)}

summary = {
    "question": "Does cross-border activity lead El Paso employment growth by 3-6 months?",
    "method": "Pearson r between border indicator at t and EP nonfarm YoY growth at t+k, k=0..12",
    "results": results,
    "crossings_geography": "El Paso (2402) + Ysleta (2401) from 2020-03; El Paso port alone before (it then included Ysleta)",
    "note": "Correlation, not causation; overlapping YoY windows inflate serial correlation, so treat r values as descriptive strength-of-association, not formal tests. "
            "Crossings series: raw YoY like the trade series; " + CROSSING_NOTE + ".",
}
with open(os.path.join(OUT, "leadlag.json"), "w") as f:
    json.dump(summary, f, indent=1)

print(f"{'indicator':42s} {'r@0':>6s} {'best r':>7s} {'at lead':>8s} {'n':>5s} {'~5% sig':>8s}")
for name, r in results.items():
    print(f"{name:42s} {r['r_at_0']:6.3f} {r['best_r']:7.3f} {r['best_lead']:8d} {r['n']:5d} {r['sig_threshold']:8.3f}")
