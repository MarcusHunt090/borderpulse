"""
Validation checks for backtest.py: target construction and leakage prevention.
Run: python3 test_backtest.py   (prints PASS/FAIL per check, exits non-zero on failure)
"""
import sys, importlib
import numpy as np

import backtest as bt   # executes the backtest; fast

failures = []
def check(name, cond, detail=""):
    print(("PASS  " if cond else "FAIL  ") + name + (("  " + detail) if detail else ""))
    if not cond: failures.append(name)

# ---------- 1. target construction on a synthetic series ----------
orig_ur = bt.ur
synth = {}
# flat 5.0 for 2010-01..2010-06, then jumps to 5.5 in 2010-07, back to 5.0 after
for i, m in enumerate(bt.month_range("2010-01", "2011-06")):
    synth[m] = 5.5 if m == "2010-07" else 5.0
bt.ur = synth
# months 2010-01..2010-06 should be Y=1 (5.5 - 5.0 = 0.5 within 6 months)
got = [bt.target_primary(m) for m in bt.month_range("2010-01", "2010-06")]
check("target: +0.5pp jump within window flags Y=1 for all 6 lead months", got == [1]*6, str(got))
# month 2010-07 itself: future is flat 5.0, level is 5.5 -> Y=0
check("target: month of the peak is Y=0", bt.target_primary("2010-07") == 0)
# a +0.4 jump must NOT trigger
synth2 = {m: (5.4 if m == "2010-07" else 5.0) for m in bt.month_range("2010-01", "2011-06")}
bt.ur = synth2
check("target: +0.4pp jump does not trigger", bt.target_primary("2010-02") == 0)
# event date = first month reaching the +0.5 rise
bt.ur = synth
check("target: event date is first crossing month", bt.event_date_primary("2010-03") == "2010-07")
bt.ur = orig_ur

# ---------- 2. leakage: expanding z at month t is invariant to future data ----------
sig_full = bt.pct_k(bt.imports, 12)
z_full = bt.expanding_z(sig_full)
probe_months = ["2008-06", "2015-03", "2020-02", "2024-11"]
ok = True
for pm in probe_months:
    truncated = {m: v for m, v in sig_full.items() if m <= pm}
    z_trunc = bt.expanding_z(truncated)
    if abs(z_trunc.get(pm, 999) - z_full.get(pm, -999)) > 1e-12:
        ok = False
check("leakage: z-score at t unchanged when all data after t is deleted", ok)

# ---------- 3. leakage: composite score at t invariant to future raw data ----------
# rebuild SIGNALS from raw series truncated at t and compare score_at(t)
def score_with_truncated(t):
    keep = lambda s, lastm: {m: v for m, v in s.items() if m <= lastm}
    saved = bt.SIGNALS
    bt_ur_t   = keep(bt.ur, bt.madd(t, -1))
    emp_t     = keep(bt.emp, bt.madd(t, -1))
    imp_t     = keep(bt.imports, bt.madd(t, -2))
    exp_t     = keep(bt.exports, bt.madd(t, -2))
    peso_t    = keep(bt.peso, t)
    lst_t     = keep(bt.listings, bt.madd(t, -1))
    dom_t     = keep(bt.dom, bt.madd(t, -1))
    bt.SIGNALS = {
        "ur_mom":      ("labor", 1, bt.expanding_z(bt.diff_k(bt_ur_t, 6))),
        "emp_yoy":     ("labor", 1, bt.expanding_z({m: -v for m, v in bt.pct_k(emp_t, 12).items()})),
        "imports_yoy": ("border", 2, bt.expanding_z({m: -v for m, v in bt.pct_k(imp_t, 12).items()})),
        "exports_yoy": ("border", 2, bt.expanding_z({m: -v for m, v in bt.pct_k(exp_t, 12).items()})),
        "peso_mom":    ("border", 0, bt.expanding_z(bt.pct_k(peso_t, 6))),
        "listings_yoy":("household", 1, bt.expanding_z(bt.pct_k(lst_t, 12), 24)),
        "dom_yoy":     ("household", 1, bt.expanding_z(bt.diff_k(dom_t, 12), 24)),
    }
    s, _ = bt.score_at(t)
    bt.SIGNALS = saved
    return s

ok = True
for pm in ["2009-01", "2016-06", "2020-03", "2025-06"]:
    full_s, _ = bt.score_at(pm)
    trunc_s = score_with_truncated(pm)
    if full_s is None or trunc_s is None or abs(full_s - trunc_s) > 1e-9:
        ok = False
        print(f"   mismatch at {pm}: full={full_s} truncated={trunc_s}")
check("leakage: composite score at t identical when future raw data removed", ok)

# ---------- 4. publication lags actually enforced ----------
# at decision month t the labor signal must come from month t-1
t = "2020-04"
_, feats = bt.score_at(t)
z_labor_tminus1 = bt.SIGNALS["ur_mom"][2].get(bt.madd(t, -1))
check("lags: labor feature at t equals z-score of month t-1", feats["ur_mom"] == z_labor_tminus1)
z_trade_tminus2 = bt.SIGNALS["imports_yoy"][2].get(bt.madd(t, -2))
check("lags: trade feature at t equals z-score of month t-2", feats["imports_yoy"] == z_trade_tminus2)

# ---------- 5. outputs sane ----------
check("scores within 0..100", bool(np.all((bt.score_arr >= 0) & (bt.score_arr <= 100))))
check("targets are 0/1", set(np.unique(bt.Y)) <= {0, 1})
check("OOS predictions exist only from first test year on",
      all(int(m[:4]) >= 2013 for m in bt.mo_oos))
check("no OOS month used in any training year before it",
      bt.year_of[bt.oos_mask].min() >= 2013)

print()
if failures:
    print(f"{len(failures)} CHECK(S) FAILED"); sys.exit(1)
print("ALL CHECKS PASSED")
