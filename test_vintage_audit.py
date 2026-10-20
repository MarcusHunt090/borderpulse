"""
Checks for vintage_audit.py using synthetic vintages built from the revised series:
  1. No-revision invariance: if every vintage equals the revised series truncated at its
     vintage date, the real-time score path must equal backtest.py's path exactly.
  2. Revision sensitivity: perturbing the unemployment vintages must change the path.
  3. Loader equivalence: ALFRED wide format and FRED-API long format load identically.
Run: python3 test_vintage_audit.py
"""
import os, sys, csv, json, tempfile, datetime, importlib
import numpy as np

import backtest as bt
import vintage_audit as va

failures = []
def check(name, cond, detail=""):
    print(("PASS  " if cond else "FAIL  ") + name + (("  " + detail) if detail else ""))
    if not cond: failures.append(name)

SRC = {"ELPA348UR": bt.ur, "ELPA348NAN": bt.emp, "IMPMX": bt.imports, "EXPMX": bt.exports, "EXMXUS": bt.peso,
       "ACTLISCOU21340": bt.listings, "MEDDAYONMAR21340": bt.dom}
LAG = {sid: v[2] for sid, v in va.VINTAGE_SERIES.items()}

def write_wide(dirpath, sid, series, perturb=None):
    """monthly vintages from 2002-01 on: vintage on the 20th of each month contains data through (month - lag)."""
    months = [m for m in bt.MONTHS if m >= "2002-01"]
    vd = [datetime.date(int(m[:4]), int(m[5:]), 20) for m in months]
    cols = [f"{sid}_{d.strftime('%Y%m%d')}" for d in vd]
    obs = sorted(series)
    with open(os.path.join(dirpath, f"{sid}.csv"), "w", newline="") as f:
        w = csv.writer(f); w.writerow(["observation_date"] + cols)
        for mo in obs:
            row = [mo + "-01"]
            for m in months:
                avail = mo <= va.madd(m, -LAG[sid])
                v = series[mo] if avail else None
                if v is not None and perturb: v = perturb(mo, m, v)
                row.append("" if v is None else repr(v))
            w.writerow(row)

def write_long(dirpath, sid, series):
    months = [m for m in bt.MONTHS if m >= "2002-01"]
    with open(os.path.join(dirpath, f"{sid}.csv"), "w", newline="") as f:
        w = csv.writer(f); w.writerow(["date", "realtime_start", "realtime_end", "value"])
        for mo in sorted(series):
            first = [m for m in months if mo <= va.madd(m, -LAG[sid])]
            if not first: continue
            d = datetime.date(int(first[0][:4]), int(first[0][5:]), 20)
            w.writerow([mo + "-01", d.isoformat(), "9999-12-31", repr(series[mo])])

def run_audit(dirpath):
    va.VDIR = dirpath
    tmp_out = os.path.join(dirpath, "out.json"); va.OUT = tmp_out
    va.main()
    return json.load(open(tmp_out))

with tempfile.TemporaryDirectory() as d:
    for sid, s in SRC.items(): write_wide(d, sid, s)
    res = run_audit(d)
    check("audit runs to completion on synthetic vintages", res["status"] == "complete")
    revised = dict(zip(bt.months_bt, [float(x) for x in bt.score_arr]))
    gaps = [abs(res["realtime_path"][m] - revised[m]) for m in res["realtime_path"] if m in revised]
    check("no-revision invariance: real-time path == revised path", max(gaps) < 1e-9, f"max gap {max(gaps):.3g}")
    check("same alert months under no revisions", res["same_alert_months"])

with tempfile.TemporaryDirectory() as d:
    for sid, s in SRC.items():
        if sid == "ELPA348UR":
            write_wide(d, sid, s, perturb=lambda mo, m, v: v - 0.3 if "2008-01" <= mo <= "2009-12" else v)  # first prints understate the 2008-09 rise
        else: write_wide(d, sid, s)
    res2 = run_audit(d)
    revised = dict(zip(bt.months_bt, [float(x) for x in bt.score_arr]))
    diff = max(abs(res2["realtime_path"][m] - revised[m]) for m in res2["realtime_path"] if "2008-01" <= m <= "2010-06")
    check("revision sensitivity: perturbed 2008-09 unemployment vintages move the 2008-10 path", diff > 0.5, f"max gap {diff:.2f}")

with tempfile.TemporaryDirectory() as d:
    write_wide(d, "ELPA348UR", bt.ur); wide = va.load_vintages("ELPA348UR") if (setattr(va, "VDIR", d) or True) else None
    with tempfile.TemporaryDirectory() as d2:
        write_long(d2, "ELPA348UR", bt.ur); va.VDIR = d2; long = va.load_vintages("ELPA348UR")
    probe = "2015-06"; snapw = va.snapshot_at(wide, probe); snapl = va.snapshot_at(long, probe)
    check("loader equivalence: wide and long formats give the same snapshot", snapw == snapl, f"{len(snapw)} vs {len(snapl)} obs")
    check("snapshot respects publication lag", max(snapw) == va.madd(probe, -1), max(snapw))

print()
if failures: print(f"{len(failures)} CHECK(S) FAILED"); sys.exit(1)
print("ALL VINTAGE CHECKS PASSED")
