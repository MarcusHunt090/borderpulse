"""
BorderPulse v4 — real-time (vintage) audit of the back-test.

Every validation result in backtest.py uses today's revised data. In real time the
decision-maker only had the numbers as first published, and BLS metro-area
unemployment (LAUS) and payrolls (CES) are revised every year — sometimes by
tenths of a point around turning points, which is exactly where an early-warning
rule earns its keep. This script rebuilds the score path month by month using
only the data vintage that existed at each decision month, and compares it with
the revised-data path.

DATA IT NEEDS (cannot be fetched from the cloud sandbox — run locally):
  data/vintages/<SERIES_ID>.csv for the series listed in VINTAGE_SERIES, in either
   (a) ALFRED "Download Data" wide format: observation_date, <ID>_YYYYMMDD, ... ; or
   (b) FRED API long format: date, realtime_start, realtime_end, value.
  With a FRED API key in the environment variable FRED_API_KEY, `--fetch` pulls
  format (b) for every series automatically (one request per series).

Decision-month convention (identical to backtest.py): at month t the labor series
may be used through t-1, trade through t-2, housing through t-1, peso through t,
and the vintage used is the latest one published on or before the last day of
month t. Targets (what actually happened afterwards) use revised data, as is
standard: the question is whether the SIGNAL was available in real time, not
whether the outcome was.

Output: validation/vintage_audit.json  (status = "complete" | "pending")
"""
import csv, json, os, sys, calendar, datetime, urllib.request, urllib.parse
import numpy as np

BASE = os.path.dirname(os.path.abspath(__file__))
VDIR = os.path.join(BASE, "data", "vintages")
OUT = os.path.join(BASE, "validation", "vintage_audit.json")
os.makedirs(os.path.join(BASE, "validation"), exist_ok=True)

# series -> (signal key, layer, publication lag in months, transform)
VINTAGE_SERIES = {
    "ELPA348UR":  ("ur_mom",      "labor",     1, "diff6"),
    "ELPA348NAN": ("emp_yoy",     "labor",     1, "neg_pct12"),
    "IMPMX":      ("imports_yoy", "border",    2, "neg_pct12"),
    "EXPMX":      ("exports_yoy", "border",    2, "neg_pct12"),
    "EXMXUS":     ("peso_mom",    "border",    0, "pct6"),
    "ACTLISCOU21340":   ("listings_yoy", "household", 1, "pct12"),
    "MEDDAYONMAR21340": ("dom_yoy",      "household", 1, "diff12"),
}
MIN_N = {"listings_yoy": 24, "dom_yoy": 24}
WEIGHTS = {"labor": 0.40, "border": 0.35, "household": 0.25}
ALERT = 65

def madd(mo, k):
    y, m = map(int, mo.split("-")); m += k
    y += (m - 1) // 12; m = (m - 1) % 12 + 1
    return f"{y:04d}-{m:02d}"

def month_end(mo):
    y, m = map(int, mo.split("-"))
    return datetime.date(y, m, calendar.monthrange(y, m)[1])

# ---------------- optional fetch via FRED API (local machines only) ----------------
def fetch_all(key):
    os.makedirs(VDIR, exist_ok=True)
    for sid in VINTAGE_SERIES:
        q = urllib.parse.urlencode({"series_id": sid, "api_key": key, "file_type": "json",
                                    "realtime_start": "1776-07-04", "realtime_end": "9999-12-31",
                                    "observation_start": "1999-01-01"})
        url = "https://api.stlouisfed.org/fred/series/observations?" + q
        with urllib.request.urlopen(url, timeout=120) as r:
            obs = json.load(r)["observations"]
        with open(os.path.join(VDIR, f"{sid}.csv"), "w", newline="") as f:
            w = csv.writer(f); w.writerow(["date", "realtime_start", "realtime_end", "value"])
            for o in obs:
                w.writerow([o["date"], o["realtime_start"], o["realtime_end"], o["value"]])
        print(f"fetched {sid}: {len(obs)} vintage-observations")

# ---------------- load vintages into {vintage_date: {month: value}} ----------------
def load_vintages(sid):
    p = os.path.join(VDIR, f"{sid}.csv")
    if not os.path.exists(p): return None
    rows = list(csv.reader(open(p)))
    hdr = [h.strip() for h in rows[0]]
    vint = {}   # vintage_date (date) -> {YYYY-MM: value}
    if "realtime_start" in hdr:                                    # FRED API long format
        iD, iS, iE, iV = hdr.index("date"), hdr.index("realtime_start"), hdr.index("realtime_end"), hdr.index("value")
        # each row is valid from realtime_start to realtime_end; build the set of vintage dates
        recs = [(r[iD][:7], r[iS], r[iE], r[iV]) for r in rows[1:] if r[iV] not in (".", "")]
        vdates = sorted({s for _, s, _, _ in recs})
        for vd in vdates:
            d = datetime.date.fromisoformat(vd)
            snap = {}
            for mo, s, e, v in recs:
                if s <= vd and (e >= vd or e == "9999-12-31"):
                    snap[mo] = float(v)
            vint[d] = snap
    else:                                                          # ALFRED wide format
        cols = [(j, h.split("_")[-1]) for j, h in enumerate(hdr) if j > 0 and "_" in h]
        for j, ymd in cols:
            d = datetime.date(int(ymd[:4]), int(ymd[4:6]), int(ymd[6:8]))
            snap = {}
            for r in rows[1:]:
                if j < len(r) and r[j] not in (".", ""):
                    snap[r[0][:7]] = float(r[j])
            vint[d] = snap
    return vint

def snapshot_at(vint, decision_month):
    """latest vintage published on or before the end of the decision month"""
    cutoff = month_end(decision_month)
    ok = [d for d in vint if d <= cutoff]
    return vint[max(ok)] if ok else None

def transform(series, kind, months):
    out = {}
    for m in months:
        if kind == "diff6":      a, b = series.get(m), series.get(madd(m, -6));  out[m] = (a - b) if a is not None and b is not None else None
        elif kind == "diff12":   a, b = series.get(m), series.get(madd(m, -12)); out[m] = (a - b) if a is not None and b is not None else None
        elif kind == "pct6":     a, b = series.get(m), series.get(madd(m, -6));  out[m] = (100 * (a / b - 1)) if a is not None and b else None
        elif kind == "pct12":    a, b = series.get(m), series.get(madd(m, -12)); out[m] = (100 * (a / b - 1)) if a is not None and b else None
        elif kind == "neg_pct12":a, b = series.get(m), series.get(madd(m, -12)); out[m] = (-100 * (a / b - 1)) if a is not None and b else None
    return {m: v for m, v in out.items() if v is not None}

def expanding_z_last(sig, months, upto, min_n):
    vals = [sig[m] for m in months if m in sig and m <= upto]
    if len(vals) < min_n or upto not in sig: return None
    a = np.array(vals); sd = a.std(ddof=1)
    return float(np.clip((sig[upto] - a.mean()) / (sd if sd > 0 else 1.0), -3, 3))

def main():
    if "--fetch" in sys.argv:
        key = os.environ.get("FRED_API_KEY")
        if not key: sys.exit("set FRED_API_KEY to use --fetch")
        fetch_all(key)

    import backtest as bt
    months = bt.MONTHS
    vint = {sid: load_vintages(sid) for sid in VINTAGE_SERIES}
    missing = [sid for sid, v in vint.items() if v is None]
    core_missing = [s for s in ("ELPA348UR", "ELPA348NAN", "IMPMX", "EXPMX", "EXMXUS") if s in missing]
    if core_missing:
        out = {"status": "pending", "missing_series": missing,
               "summary_text": ("Vintage files absent for " + ", ".join(missing) + ". Export each series from ALFRED "
                                "(Download Data → all vintages) or run `python3 vintage_audit.py --fetch` with FRED_API_KEY set, "
                                "then rerun. Until then all validation uses latest-vintage (revised) data."),
               "expected_files": [f"data/vintages/{s}.csv" for s in VINTAGE_SERIES],
               "generated": datetime.date.today().isoformat()}
        json.dump(out, open(OUT, "w"), indent=1)
        print("vintage audit: PENDING —", out["summary_text"]); return

    # revised-data reference path from backtest.py
    revised = dict(zip(bt.months_bt, [float(s) for s in bt.score_arr]))
    Y1 = dict(zip(bt.months_bt, [int(y) for y in bt.Y]))
    rt_path, detail = {}, {}
    for t in bt.months_bt:
        layers, feats = {}, {}
        for sid, (key, layer, lag, kind) in VINTAGE_SERIES.items():
            v = vint[sid]
            if v is None:                                 # housing vintages optional: fall back to revised series
                src = {"listings_yoy": bt.listings, "dom_yoy": bt.dom}.get(key)
                snap = src
            else:
                snap = snapshot_at(v, t)
            if not snap: continue
            sig = transform(snap, kind, months)
            z = expanding_z_last(sig, months, madd(t, -lag), MIN_N.get(key, 36))
            feats[key] = z
            if z is not None: layers.setdefault(layer, []).append(z)
        if "labor" not in layers or "border" not in layers: continue
        w = sum(WEIGHTS[L] for L in layers)
        zc = sum(WEIGHTS[L] * np.mean(v) for L, v in layers.items()) / w
        rt_path[t] = round(bt.squash(zc), 1); detail[t] = feats

    common = [t for t in bt.months_bt if t in rt_path]
    rt = np.array([rt_path[t] for t in common]); rv = np.array([revised[t] for t in common]); y = np.array([Y1[t] for t in common])
    def runs(flags, ms):
        out, cur = [], None
        for f, m in zip(flags, ms):
            if f and cur is None: cur = [m, m]
            elif f: cur[1] = m
            elif cur: out.append(tuple(cur)); cur = None
        if cur: out.append(tuple(cur))
        return out
    rt_alerts, rv_alerts = runs(rt >= ALERT, common), runs(rv >= ALERT, common)
    res = {
        "status": "complete", "generated": datetime.date.today().isoformat(),
        "series_audited": [s for s in VINTAGE_SERIES if vint[s] is not None],
        "n_vintages": int(sum(len(v) for v in vint.values() if v)),
        "months": [common[0], common[-1]], "n_months": len(common),
        "mean_abs_score_gap": round(float(np.mean(np.abs(rt - rv))), 2),
        "max_abs_score_gap": round(float(np.max(np.abs(rt - rv))), 2),
        "corr_realtime_vs_revised": round(float(np.corrcoef(rt, rv)[0, 1]), 4),
        "auc_T1_realtime": round(bt.roc_auc(rt, y), 3), "auc_T1_revised": round(bt.roc_auc(rv, y), 3),
        "alert_episodes_realtime": rt_alerts, "alert_episodes_revised": rv_alerts,
        "same_alert_months": bool(np.array_equal(rt >= ALERT, rv >= ALERT)),
        "realtime_path": dict(zip(common, [float(x) for x in rt])),
    }
    res["summary_text"] = (f"Real-time and revised score paths correlate {res['corr_realtime_vs_revised']:.3f} (mean |gap| {res['mean_abs_score_gap']} pts, "
                           f"max {res['max_abs_score_gap']}). Alert episodes real-time: {rt_alerts}; revised: {rv_alerts}. "
                           f"T1 ROC-AUC real-time {res['auc_T1_realtime']} vs revised {res['auc_T1_revised']}.")
    json.dump(res, open(OUT, "w"), indent=1, default=str)
    print("vintage audit: COMPLETE —", res["summary_text"])

if __name__ == "__main__":
    main()
