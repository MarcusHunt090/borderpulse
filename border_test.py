"""
BorderPulse — pre-specified border-layer comparison (v4.1).

Question (raised in the 2026-10-02 meeting with a regional border-economy research group):
national U.S.-Mexico trade is mostly through-traffic for El Paso, so does a border layer built
from local port-of-entry crossings warn better than the published trade-based layer?

PRE-SPECIFICATION (fixed 2026-10-11, before any variant was scored; recorded in the output):
  A  published   : imports YoY, exports YoY, peso 6-mo move            (unchanged model)
  B  crossings   : personal-vehicle + pedestrian crossings, peso        (trade removed)
  C  combined    : imports, exports, personal-vehicle + pedestrian crossings, peso
  S  sensitivity : B plus truck crossings — reported, never eligible, because the BTS truck
                   series has documented reporting-level breaks (2020-03, 2022-12/2023).
  Crossings transform: stress = -(YoY % change of the 3-month moving sum), to damp the
  single-month reporting anomalies flagged in data/extra/manifest.json. Expanding-window z
  (min 36 obs, clip +/-3), publication lag t-2 (same as trade). Every other feature, weight
  (40/35/25), squash, alert threshold (>=65) and target definition is the published one.
  Targets: T1 = EP unemployment rises >= 0.5pp within 6 months; T2 = EP payroll YoY turns
  negative within 6 months. Metrics: month-level ROC-AUC with circular moving-block bootstrap
  intervals for the difference vs A (block 12, B = 1000, seed 42); episode counts at >= 65;
  everything also reported excluding 2020-01..2021-12 (COVID and the cross-border travel
  restrictions, which mechanically collapse crossings).
  Decision rule: a variant is only a candidate for promotion if its AUC gain over A has a
  95% interval above zero on BOTH targets with and without the COVID window. Otherwise the
  composite stays as published and the result is reported as a finding.

AMENDMENT v2 (2026-10-12, data correction only): the v1 run used the BTS "El Paso" port series
alone. CBP split Ysleta (port 2401) out of El Paso (port 2402) effective 2020-03-16, so that
series loses Ysleta's traffic from March 2020 — a data error, not an economic signal. v2 uses
El Paso + Ysleta (El Paso alone before 2020-03, when it already included Ysleta). Variants,
transform, lags, targets, bootstrap and decision rule are unchanged; S stays ineligible as
pre-registered. The v1 result (published 2026-10-11) is superseded.
"""
import json, csv, math, os, random

BASE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(BASE, "data")
VDIR = os.path.join(BASE, "validation")

def load(p):
    d = {}
    with open(p) as f:
        for r in csv.DictReader(f):
            v = r["value"].strip()
            if v and v != ".":
                d[r["date"][:7]] = float(v)
    return d

def month_range(a, b):
    y, m = map(int, a.split("-")); Y, M = map(int, b.split("-")); out = []
    while (y, m) <= (Y, M):
        out.append(f"{y:04d}-{m:02d}"); m += 1
        if m == 13: m, y = 1, y + 1
    return out

def expanding_z(sig, months, min_n=36):
    vals, out = [], {}
    for mo in months:
        if mo in sig:
            vals.append(sig[mo])
            if len(vals) >= min_n:
                n = len(vals); mu = sum(vals) / n
                var = sum((v - mu) ** 2 for v in vals) / (n - 1)
                sd = math.sqrt(var) if var > 0 else 1.0
                out[mo] = max(-3.0, min(3.0, (sig[mo] - mu) / sd))
    return out

def auc(scores, labels):
    pos = [s for s, l in zip(scores, labels) if l == 1]; neg = [s for s, l in zip(scores, labels) if l == 0]
    if not pos or not neg: return None
    allv = sorted((s, i) for i, s in enumerate(scores))
    ranks = [0.0] * len(scores); i = 0
    while i < len(allv):
        j = i
        while j + 1 < len(allv) and allv[j + 1][0] == allv[i][0]: j += 1
        r = (i + j) / 2 + 1
        for k in range(i, j + 1): ranks[allv[k][1]] = r
        i = j + 1
    rp = sum(r for r, l in zip(ranks, labels) if l == 1)
    return (rp - len(pos) * (len(pos) + 1) / 2) / (len(pos) * len(neg))

def runs(flags, ms):
    out, cur = [], None
    for m in ms:
        if flags.get(m):
            cur = [cur[0], m] if cur else [m, m]
        elif cur:
            out.append(cur); cur = None
    if cur: out.append(cur)
    return out

def episodes(score, target, ms, thr=65.0):
    a = runs({m: score[m] >= thr for m in ms}, ms)
    e = runs({m: target[m] == 1 for m in ms}, ms)
    ov = lambda x, y: not (x[1] < y[0] or y[1] < x[0])
    tw = sum(1 for x in a if any(ov(x, y) for y in e))
    det = sum(1 for y in e if any(ov(x, y) for x in a))
    return {"alert_episodes": len(a), "true_warnings": tw, "false_alarms": len(a) - tw,
            "events": len(e), "events_detected": det, "alert_runs": a}

def main():
    lab = json.load(open(os.path.join(VDIR, "lab_data.json")))
    published = {r["month"]: float(r["score"]) for r in csv.DictReader(open(os.path.join(VDIR, "backtest_monthly_results.csv")))}
    LM = lab["months"]
    calendar = month_range("1996-01", LM[-1])
    feats = {k: {m: v for m, v in zip(LM, lab["features"][k]) if v is not None} for k in lab["features"]}
    layer_of = {k: lab["feature_meta"][k]["layer"] for k in lab["features"]}
    # crossings features: -(YoY of 3-month moving sum), expanding z, lag 2
    def combined(measure):
        ep = load(os.path.join(DATA, "extra", f"ep_crossings_{measure}.csv"))
        ys = load(os.path.join(DATA, "extra", f"ysleta_crossings_{measure}.csv"))
        return {m: (v if m < "2020-03" else v + ys[m]) for m, v in ep.items() if m < "2020-03" or m in ys}
    for key in ("pov", "ped", "trucks"):
        s = combined(key)
        s3 = {}
        for i in range(2, len(calendar)):
            w = calendar[i - 2:i + 1]
            if all(m in s for m in w): s3[calendar[i]] = sum(s[m] for m in w)
        sig = {}
        for i in range(12, len(calendar)):
            m, p = calendar[i], calendar[i - 12]
            if m in s3 and p in s3 and s3[p] > 0: sig[m] = -100.0 * (s3[m] / s3[p] - 1.0)
        z = expanding_z(sig, calendar, 36)
        fk = "x_" + key
        feats[fk] = {}
        for i, m in enumerate(calendar):
            if i >= 2 and calendar[i - 2] in z: feats[fk][m] = round(z[calendar[i - 2]], 3)
        layer_of[fk] = "border"
    W = lab["baseline_weights"]; slope = lab["squash"]["slope"]
    VARIANTS = {
        "A": {"label": "A · Published (trade + peso)", "keys": ["ur_mom", "emp_yoy", "imports_yoy", "exports_yoy", "peso_mom", "listings_yoy", "dom_yoy"], "eligible": True},
        "B": {"label": "B · Crossings replace trade", "keys": ["ur_mom", "emp_yoy", "x_pov", "x_ped", "peso_mom", "listings_yoy", "dom_yoy"], "eligible": True},
        "C": {"label": "C · Trade + crossings", "keys": ["ur_mom", "emp_yoy", "imports_yoy", "exports_yoy", "x_pov", "x_ped", "peso_mom", "listings_yoy", "dom_yoy"], "eligible": True},
        "S": {"label": "S · Sensitivity: B + trucks (not eligible: reporting breaks)", "keys": ["ur_mom", "emp_yoy", "x_pov", "x_ped", "x_trucks", "peso_mom", "listings_yoy", "dom_yoy"], "eligible": False},
    }
    def score_series(keys):
        out = {}
        for m in LM:
            per = {}
            for k in keys:
                if m in feats[k]: per.setdefault(layer_of[k], []).append(feats[k][m])
            if "labor" not in per or "border" not in per: continue
            ws = sum(W[L] for L in per)
            z = sum(W[L] * sum(v) / len(v) for L, v in per.items()) / ws
            out[m] = 100.0 / (1.0 + math.exp(-slope * z))
        return out
    scores = {v: score_series(VARIANTS[v]["keys"]) for v in VARIANTS}
    # reproduction check: variant A must equal the published backtest score
    rep = [abs(scores["A"][m] - published[m]) for m in LM if m in scores["A"] and m in published]
    madd = lambda m, k: calendar[calendar.index(m) + k] if m in calendar and calendar.index(m) + k < len(calendar) else None
    def target(kind, m):
        if kind == "T1":
            base = lab["ur"].get(m)
            if base is None: return None
            mx = None
            for k in range(1, 7):
                mm = madd(m, k)
                v = lab["ur"].get(mm) if mm else None
                if v is None: return None
                mx = v - base if mx is None else max(mx, v - base)
            return 1 if mx >= 0.5 else 0
        neg = False
        for k in range(1, 7):
            mm = madd(m, k); v = lab["emp_yoy"].get(mm) if mm else None
            if v is None: return None
            if v < 0: neg = True
        return 1 if neg else 0
    covid = set(month_range("2020-01", "2021-12"))
    rng = random.Random(42)
    results = {"targets": {}}
    for T in ("T1", "T2"):
        tg = {m: target(T, m) for m in LM}
        ms_all = [m for m in LM if tg[m] is not None and all(m in scores[v] for v in VARIANTS)]
        results["targets"][T] = {}
        for sample, ms in (("full", ms_all), ("ex_covid", [m for m in ms_all if m not in covid])):
            lab_ = [tg[m] for m in ms]
            row = {"months": len(ms), "first": ms[0], "last": ms[-1], "variants": {}}
            sc = {v: [scores[v][m] for m in ms] for v in VARIANTS}
            # paired circular block bootstrap of AUC(v) - AUC(A)
            n, Bk, B = len(ms), 12, 1000
            draws = {v: [] for v in VARIANTS if v != "A"}
            for _ in range(B):
                idx = []
                while len(idx) < n:
                    st = rng.randrange(n); idx.extend((st + j) % n for j in range(Bk))
                idx = idx[:n]; lb = [lab_[i] for i in idx]
                a0 = auc([sc["A"][i] for i in idx], lb)
                if a0 is None: continue
                for v in draws:
                    av = auc([sc[v][i] for i in idx], lb)
                    if av is not None: draws[v].append(av - a0)
            for v in VARIANTS:
                a = auc(sc[v], lab_)
                ep = episodes({m: scores[v][m] for m in ms}, tg, ms)
                entry = {"auc": round(a, 3) if a is not None else None, "episodes": ep}
                if v != "A" and draws[v]:
                    d = sorted(draws[v]); q = lambda p: d[max(0, min(len(d) - 1, int(round(p * (len(d) - 1)))))]
                    entry["auc_diff_vs_A"] = round(a - auc(sc["A"], lab_), 3)
                    entry["diff_ci95"] = [round(q(0.025), 3), round(q(0.975), 3)]
                    entry["n_boot"] = len(d)
                row["variants"][v] = entry
            results["targets"][T][sample] = row
    # decision
    verdict = {}
    for v in ("B", "C"):
        ok = all(results["targets"][T][s]["variants"][v]["diff_ci95"][0] > 0 for T in ("T1", "T2") for s in ("full", "ex_covid"))
        verdict[v] = ok
    lastm = LM[-1]
    out = {
        "generated_for_version": "5.0.0",
        "amendment": "v2 2026-10-12: crossings = El Paso + Ysleta ports (CBP port split 2020-03-16); v1 used El Paso only and is superseded. Design unchanged.",
        "prespecified": "2026-10-11",
        "question": "Does a border layer built from El Paso port-of-entry crossings warn better than the published trade-based layer?",
        "prespecification": __doc__.strip(),
        "variants": {v: {"label": VARIANTS[v]["label"], "inputs": VARIANTS[v]["keys"], "eligible": VARIANTS[v]["eligible"]} for v in VARIANTS},
        "reproduction_check_max_abs_diff_A_vs_published": round(max(rep), 3) if rep else None,
        "results": results,
        "promotion_candidate": verdict,
        "decision": ("composite unchanged: no variant beats the published border layer with an interval above zero on both targets, with and without COVID"
                     if not any(verdict.values()) else "candidate found — requires a documented human decision before any change to the composite"),
        "timeline": {v: {m: round(scores[v][m], 1) for m in LM if m in scores[v]} for v in ("A", "B", "C")},
        "latest_month": lastm,
    }
    json.dump(out, open(os.path.join(VDIR, "border_test.json"), "w"), indent=1)
    print("reproduction max |A - published| =", out["reproduction_check_max_abs_diff_A_vs_published"])
    for T, d in results.items() if False else results["targets"].items():
        for s, row in d.items():
            print(T, s, row["months"], {v: (e["auc"], e.get("auc_diff_vs_A"), e.get("diff_ci95"), f'{e["episodes"]["alert_episodes"]} ep / {e["episodes"]["events_detected"]} of {e["episodes"]["events"]}') for v, e in row["variants"].items()})
    print("decision:", out["decision"])

if __name__ == "__main__":
    main()
