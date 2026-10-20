"""
BorderPulse — onset evaluation (v5). Separates WARNING BEFORE A DOWNTURN STARTS from
DETECTING ONE ALREADY UNDER WAY.

Why: the v3/v4 payroll target (T2) counts a month as a hit if payroll growth is negative in ANY
of the next six months — including months when growth is already negative. In the published
back-test, 19 of the 21 alert months had negative payroll growth in the alert month itself, so
"2 of 3 payroll downturns caught" mixes one advance warning (2008) with one detection (2020).

PRE-SPECIFICATION (fixed 2026-10-12, before scoring):
  Onsets (observation-month data, as later revised):
    payroll onset       = month YoY payroll growth turns negative after >= 6 non-negative months
    unemployment onset  = month unemployment first sits >= 0.5pp above its prior-12-month low,
                          after >= 12 months without that condition
  Alert rules (as-publishable, i.e. with publication lags, from the existing back-test):
    BorderPulse  score >= 65            (validation/backtest_monthly_results.csv)
    Local Sahm   3-mo avg unemployment >= 0.5pp above the min of the prior 12 months' 3-mo avgs,
                 using unemployment through t-1 (one-month publication lag)
  Classification of each onset:
    advance warning  = an alert in the 6 months BEFORE the onset (lead = months before onset)
    detection        = no advance warning, but an alert in the onset month or the 6 months after
    missed           = neither
  False alarm episode = an alert episode with no onset of that type within 6 months either side.
  Counts are reported with exact (Clopper-Pearson) 95% intervals; there are very few events.
"""
import json, csv, os, math

BASE = os.path.dirname(os.path.abspath(__file__))
VDIR = os.path.join(BASE, "validation")

def month_range(a, b):
    y, m = map(int, a.split("-")); Y, M = map(int, b.split("-")); out = []
    while (y, m) <= (Y, M):
        out.append(f"{y:04d}-{m:02d}"); m += 1
        if m == 13: m, y = 1, y + 1
    return out

def betainc_inv(p, a, b):
    lo, hi = 0.0, 1.0
    for _ in range(80):
        mid = (lo + hi) / 2
        if reg_inc_beta(mid, a, b) < p: lo = mid
        else: hi = mid
    return (lo + hi) / 2

def reg_inc_beta(x, a, b):
    if x <= 0: return 0.0
    if x >= 1: return 1.0
    lbeta = math.lgamma(a) + math.lgamma(b) - math.lgamma(a + b)
    front = math.exp(a * math.log(x) + b * math.log(1 - x) - lbeta) / a
    if x > (a + 1) / (a + b + 2):
        return 1.0 - reg_inc_beta(1 - x, b, a)
    f, c, d = 1.0, 1.0, 0.0
    for i in range(200):
        m = i // 2
        if i == 0: num = 1.0
        elif i % 2 == 0: num = m * (b - m) * x / ((a + 2 * m - 1) * (a + 2 * m))
        else: num = -(a + m) * (a + b + m) * x / ((a + 2 * m) * (a + 2 * m + 1))
        d = 1.0 + num * d; d = 1.0 / d if abs(d) > 1e-30 else 1e30
        c = 1.0 + num / c if abs(c) > 1e-30 else 1e30
        f *= c * d
        if abs(c * d - 1.0) < 1e-12: break
    return front * (f - 1.0)

def clopper_pearson(k, n):
    if n == 0: return [None, None]
    lo = 0.0 if k == 0 else betainc_inv(0.025, k, n - k + 1)
    hi = 1.0 if k == n else betainc_inv(0.975, k + 1, n - k)
    return [round(lo, 3), round(hi, 3)]

def runs(flags, ms):
    out, cur = [], None
    for m in ms:
        if flags.get(m): cur = [cur[0], m] if cur else [m, m]
        elif cur: out.append(cur); cur = None
    if cur: out.append(cur)
    return out

def main():
    lab = json.load(open(os.path.join(VDIR, "lab_data.json")))
    score = {r["month"]: float(r["score"]) for r in csv.DictReader(open(os.path.join(VDIR, "backtest_monthly_results.csv")))}
    ur, emp = lab["ur"], lab["emp_yoy"]
    scored = sorted(score)
    first, last = scored[0], scored[-1]
    cal = month_range(min(min(ur), min(emp)), max(max(ur), max(emp)))
    idx = {m: i for i, m in enumerate(cal)}
    sh = lambda m, k: cal[idx[m] + k] if m in idx and 0 <= idx[m] + k < len(cal) else None
    # --- onsets
    pay_on = []
    for m in cal:
        prev = [sh(m, -k) for k in range(1, 7)]
        if emp.get(m) is not None and emp[m] < 0 and all(p and emp.get(p) is not None and emp[p] >= 0 for p in prev):
            pay_on.append(m)
    cond = {}
    for m in cal:
        prev = [ur.get(sh(m, -k)) for k in range(1, 13)]
        if ur.get(m) is None or any(v is None for v in prev): continue
        cond[m] = round(ur[m] - min(prev), 1) >= 0.5          # compare at source precision (0.1pp)
    ur_on = []
    for m in cal:
        if cond.get(m) and not any(cond.get(sh(m, -k)) for k in range(1, 13)):
            ur_on.append(m)
    # --- alert rules (as-publishable)
    alert = {"BorderPulse score ≥ 65": {m: score[m] >= 65 for m in scored}}
    avg3 = {}
    for m in cal:
        w = [ur.get(sh(m, -k)) for k in range(0, 3)]
        if all(v is not None for v in w): avg3[m] = sum(w) / 3
    sahm = {}
    for m in scored:
        t = sh(m, -1)                                           # one-month publication lag
        if t not in avg3: continue
        prior = [avg3.get(sh(t, -k)) for k in range(1, 13)]
        if any(v is None for v in prior): continue
        sahm[m] = round(avg3[t] - min(prior), 2) >= 0.5
    alert["Local Sahm rule"] = sahm
    def evaluate(onsets, flags):
        ms = [m for m in scored if m in flags]
        eligible = [o for o in onsets if sh(o, -6) and sh(o, -6) >= ms[0] and sh(o, 6) and sh(o, 6) <= ms[-1]]
        rows, adv, det = [], 0, 0
        for o in eligible:
            before = [sh(o, -k) for k in range(6, 0, -1)]
            after = [sh(o, k) for k in range(0, 7)]
            b = [m for m in before if flags.get(m)]
            a = [m for m in after if flags.get(m)]
            if b:
                adv += 1; rows.append({"onset": o, "result": "advance warning", "first_alert": b[0], "lead_months": idx[o] - idx[b[0]]})
            elif a:
                det += 1; rows.append({"onset": o, "result": "detected after onset", "first_alert": a[0], "lag_months": idx[a[0]] - idx[o]})
            else:
                rows.append({"onset": o, "result": "missed"})
        eps = runs(flags, ms)
        fa = [e for e in eps if not any(idx[o] - 6 <= idx[e[1]] and idx[e[0]] <= idx[o] + 6 for o in onsets)]
        n = len(eligible)
        return {"onsets": rows, "n_onsets": n, "advance_warnings": adv, "detections_after_onset": det,
                "missed": n - adv - det, "advance_rate_ci95": clopper_pearson(adv, n),
                "alert_episodes": len(eps), "false_alarm_episodes": len(fa), "false_alarm_runs": fa}
    res = {}
    for name, flags in alert.items():
        res[name] = {"payroll_onset": evaluate(pay_on, flags), "unemployment_onset": evaluate(ur_on, flags)}
    alert_months = [m for m in scored if score[m] >= 65]
    already = [m for m in alert_months if emp.get(m) is not None and emp[m] < 0]
    out = {"version": "5.0.0", "prespecified": "2026-10-12", "spec": __doc__.strip(),
           "evaluation_span": [first, last], "payroll_onsets": pay_on, "unemployment_onsets": ur_on,
           "results": res,
           "alert_months_ge65": len(alert_months), "alert_months_with_payroll_already_negative": len(already)}
    json.dump(out, open(os.path.join(VDIR, "onset_eval.json"), "w"), indent=1)
    print("payroll onsets:", pay_on); print("unemployment onsets:", ur_on)
    for name, r in res.items():
        for t, e in r.items():
            print(f"{name:24s} {t:18s} n={e['n_onsets']} adv={e['advance_warnings']} det={e['detections_after_onset']} missed={e['missed']} CI={e['advance_rate_ci95']} FA={e['false_alarm_episodes']}/{e['alert_episodes']}")
            for row in e["onsets"]: print("     ", row)
    print("alert months", len(alert_months), "already negative", len(already))

if __name__ == "__main__":
    main()
