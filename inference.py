"""
BorderPulse v4 — statistical inference for the validation results.

Everything in backtest.py / benchmarks.py is a point estimate on one autocorrelated
history. This module asks how much of it survives honest uncertainty:

  1. Moving-block bootstrap (circular, block = 12 months, B = 1000) over the
     backtest table -> percentile CIs for month-level ROC-AUC / PR-AUC of the
     index and of the continuous local-Sahm statistic, for the AUC DIFFERENCE
     (index - Sahm), and for the episode-level precision / recall of the >=65 rule.
  2. Circular-shift placebo test: the score path is rotated against the target by
     every admissible offset (|k| >= 13 months) and the metrics recomputed. The
     share of rotations that match or beat the observed value is a permutation
     p-value that respects the serial dependence of both series.
  3. HAC (Newey-West, Bartlett, L = 12) inference for the lead/lag correlations,
     with Bonferroni adjustment across the 13 leads tested per indicator.
  4. Calibration: realized 6-month event frequencies by score band and by score
     decile with Wilson 95% intervals; Brier skill score of score/100 vs the base
     rate (expected to be poor — the score is not a probability).
  5. Robustness grid: the composite is recomputed under alternative conventions
     (layer weights x min-history x z-clip x publication-lag shift) and the
     headline validation facts are re-evaluated for each configuration.

v5: band labels Calm / Near normal / Above normal / High (boundaries unchanged);
lead/lag crossings are El Paso + Ysleta (see leadlag.py).

Writes validation/inference.json. Deterministic (seed 42).
"""
import json, math, os, itertools
import numpy as np
from scipy.stats import norm

import backtest as bt
import benchmarks as bm
import leadlag as ll

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "validation")
rng = np.random.default_rng(42)
B = 1000
BLOCK = 12
ALERT = bt.ALERT

months = bt.months_bt
n = len(months)
score = np.asarray(bt.score_arr, float)
Y1 = np.asarray(bt.Y, int)
Y2raw = np.array([r["Y2"] if r["Y2"] is not None else -1 for r in bt.rows])
m2 = Y2raw >= 0
# continuous Sahm statistic aligned to decision months (labor data through t-1)
sahm_s = np.array([bm.sahm_val.get(bt.madd(t, -1), np.nan) for t in months])
ms = ~np.isnan(sahm_s)

# ---------------- helpers ----------------
def runs(flags):
    """[(start_idx, end_idx)] of consecutive True."""
    out, cur = [], None
    for i, f in enumerate(flags):
        if f and cur is None: cur = [i, i]
        elif f: cur[1] = i
        elif cur is not None: out.append(tuple(cur)); cur = None
    if cur is not None: out.append(tuple(cur))
    return out

def episode_stats(alert, y):
    a_runs, e_runs = runs(alert), runs(y == 1)
    ov = lambda a, b: not (a[1] < b[0] or b[1] < a[0])
    tw = sum(1 for a in a_runs if any(ov(a, e) for e in e_runs))
    det = sum(1 for e in e_runs if any(ov(a, e) for a in a_runs))
    return {"alert_episodes": len(a_runs), "true_warnings": tw, "events": len(e_runs), "events_detected": det,
            "precision": (tw / len(a_runs) if a_runs else None), "recall": (det / len(e_runs) if e_runs else None)}

def auc(s, y):
    y = np.asarray(y); s = np.asarray(s)
    if y.sum() in (0, len(y)): return np.nan
    return bt.roc_auc(s, y)

def pct_ci(vals, lo=2.5, hi=97.5):
    v = np.array([x for x in vals if x is not None and not (isinstance(x, float) and np.isnan(x))], float)
    if len(v) == 0: return [None, None, 0]
    return [round(float(np.percentile(v, lo)), 3), round(float(np.percentile(v, hi)), 3), int(len(v))]

def wilson(k, n_, z=1.96):
    if n_ == 0: return [None, None]
    p = k / n_; d = 1 + z * z / n_
    c = (p + z * z / (2 * n_)) / d; h = z * math.sqrt(p * (1 - p) / n_ + z * z / (4 * n_ * n_)) / d
    return [round(c - h, 3), round(c + h, 3)]

# ---------------- 1) moving-block bootstrap ----------------
def block_indices():
    nb = int(math.ceil(n / BLOCK))
    starts = rng.integers(0, n, size=nb)
    idx = np.concatenate([(s + np.arange(BLOCK)) % n for s in starts])[:n]
    return idx

boot = {k: [] for k in ["auc1_index", "auc1_sahm", "dauc1", "auc2_index", "auc2_sahm", "dauc2",
                        "prauc1_index", "ep_prec1", "ep_rec1", "ep_prec2", "ep_rec2",
                        "sahm_ep_prec1", "sahm_ep_rec1"]}
sahm_alert = np.array([bm.alert_sahm.get(t, False) for t in months])
for _ in range(B):
    idx = block_indices()
    s, y1, y2, ss, sa = score[idx], Y1[idx], Y2raw[idx], sahm_s[idx], sahm_alert[idx]
    ok2 = y2 >= 0; oks = ~np.isnan(ss)
    boot["auc1_index"].append(auc(s, y1))
    boot["auc1_sahm"].append(auc(ss[oks], y1[oks]))
    boot["dauc1"].append(auc(s[oks], y1[oks]) - auc(ss[oks], y1[oks]))
    boot["auc2_index"].append(auc(s[ok2], y2[ok2]))
    boot["auc2_sahm"].append(auc(ss[ok2 & oks], y2[ok2 & oks]))
    boot["dauc2"].append(auc(s[ok2 & oks], y2[ok2 & oks]) - auc(ss[ok2 & oks], y2[ok2 & oks]))
    boot["prauc1_index"].append(bt.pr_auc(s, y1) if y1.sum() else np.nan)
    e1 = episode_stats(s >= ALERT, y1); e2 = episode_stats(s[ok2] >= ALERT, y2[ok2])
    boot["ep_prec1"].append(e1["precision"]); boot["ep_rec1"].append(e1["recall"])
    boot["ep_prec2"].append(e2["precision"]); boot["ep_rec2"].append(e2["recall"])
    es = episode_stats(sa, y1)
    boot["sahm_ep_prec1"].append(es["precision"]); boot["sahm_ep_rec1"].append(es["recall"])

obs_e1 = episode_stats(score >= ALERT, Y1); obs_e2 = episode_stats(score[m2] >= ALERT, Y2raw[m2])
obs_es = episode_stats(sahm_alert, Y1)
bootstrap = {
    "method": f"circular moving-block bootstrap, block={BLOCK} months, B={B}, percentile 95% intervals; "
              "episode metrics inside resamples inherit block-join artifacts (conservative width)",
    "n_months": n,
    "auc_T1": {"index": round(auc(score, Y1), 3), "index_ci": pct_ci(boot["auc1_index"]),
               "sahm": round(auc(sahm_s[ms], Y1[ms]), 3), "sahm_ci": pct_ci(boot["auc1_sahm"]),
               "diff_index_minus_sahm": round(auc(score[ms], Y1[ms]) - auc(sahm_s[ms], Y1[ms]), 3), "diff_ci": pct_ci(boot["dauc1"])},
    "auc_T2": {"index": round(auc(score[m2], Y2raw[m2]), 3), "index_ci": pct_ci(boot["auc2_index"]),
               "sahm": round(auc(sahm_s[m2 & ms], Y2raw[m2 & ms]), 3), "sahm_ci": pct_ci(boot["auc2_sahm"]),
               "diff_index_minus_sahm": round(auc(score[m2 & ms], Y2raw[m2 & ms]) - auc(sahm_s[m2 & ms], Y2raw[m2 & ms]), 3), "diff_ci": pct_ci(boot["dauc2"])},
    "prauc_T1_index": {"obs": round(bt.pr_auc(score, Y1), 3), "ci": pct_ci(boot["prauc1_index"])},
    "episode_ge65_T1": {**{k: (round(v, 3) if isinstance(v, float) else v) for k, v in obs_e1.items()},
                        "precision_ci": pct_ci(boot["ep_prec1"]), "recall_ci": pct_ci(boot["ep_rec1"])},
    "episode_ge65_T2": {**{k: (round(v, 3) if isinstance(v, float) else v) for k, v in obs_e2.items()},
                        "precision_ci": pct_ci(boot["ep_prec2"]), "recall_ci": pct_ci(boot["ep_rec2"])},
    "episode_sahm_T1": {**{k: (round(v, 3) if isinstance(v, float) else v) for k, v in obs_es.items()},
                        "precision_ci": pct_ci(boot["sahm_ep_prec1"]), "recall_ci": pct_ci(boot["sahm_ep_rec1"])},
}

# ---------------- 2) circular-shift placebo ----------------
def placebo(s, y, alert_fn, min_shift=13):
    obs_auc = auc(s, y); obs_tw = episode_stats(alert_fn(s), y)["true_warnings"]
    obs_det = episode_stats(alert_fn(s), y)["events_detected"]
    nn = len(s); null_auc, null_tw, null_det = [], [], []
    for k in range(min_shift, nn - min_shift + 1):
        sk = np.roll(s, k)
        null_auc.append(auc(sk, y)); e = episode_stats(alert_fn(sk), y)
        null_tw.append(e["true_warnings"]); null_det.append(e["events_detected"])
    null_auc = np.array(null_auc, float)
    return {"observed_auc": round(float(obs_auc), 3),
            "p_auc": round(float(np.mean(null_auc >= obs_auc)), 3),
            "null_auc_mean": round(float(np.nanmean(null_auc)), 3),
            "null_auc_95": [round(float(np.nanpercentile(null_auc, 2.5)), 3), round(float(np.nanpercentile(null_auc, 97.5)), 3)],
            "observed_true_warnings": int(obs_tw), "p_true_warnings": round(float(np.mean(np.array(null_tw) >= obs_tw)), 3),
            "observed_events_detected": int(obs_det), "p_events_detected": round(float(np.mean(np.array(null_det) >= obs_det)), 3),
            "n_shifts": int(len(null_auc))}

placebo_tests = {
    "method": "circular time-shift of the score path against the target (|k| >= 13 months); p = share of shifts whose metric >= observed",
    "index_T1": placebo(score, Y1, lambda s: s >= ALERT),
    "index_T2": placebo(score[m2], Y2raw[m2], lambda s: s >= ALERT),
    "sahm_T1": placebo(np.where(ms, sahm_s, np.nanmin(sahm_s[ms])), Y1, lambda s: s >= 0.5),
}

# ---------------- 3) HAC lead/lag inference ----------------
def nw_beta(x, y, L=12):
    """OLS slope of y on standardized x with Newey-West (Bartlett) SE."""
    x = (x - x.mean()) / x.std(ddof=1); X = np.column_stack([np.ones(len(x)), x])
    beta = np.linalg.lstsq(X, y, rcond=None)[0]; u = y - X @ beta
    S = (X * u[:, None]).T @ (X * u[:, None])
    for l in range(1, L + 1):
        w = 1 - l / (L + 1); G = (X[l:] * u[l:, None]).T @ (X[:-l] * u[:-l, None])
        S += w * (G + G.T)
    XtX_inv = np.linalg.inv(X.T @ X); V = XtX_inv @ S @ XtX_inv
    se = math.sqrt(max(V[1, 1], 1e-12)); t = beta[1] / se
    return float(beta[1]), float(se), float(t), float(2 * (1 - norm.cdf(abs(t))))

leadlag_hac = {"method": "OLS of EP payroll YoY growth(t+k) on standardized indicator(t); Newey-West SE, Bartlett kernel, L=12; "
                         "Bonferroni factor 13 (leads 0..12) for the family-wise column", "results": {}}
for name, sig in ll.signals.items():
    rows = []
    for k in range(13):
        xs, ys = [], []
        for m, v in sig.items():
            tgt = ll.emp_growth.get(bt.madd(m, k))
            if tgt is not None: xs.append(v); ys.append(tgt)
        if len(xs) < 30: continue
        x, y = np.array(xs), np.array(ys)
        r = float(np.corrcoef(x, y)[0, 1]); b_, se, t, p = nw_beta(x, y)
        rows.append({"lead": k, "n": len(x), "r": round(r, 3), "t_hac": round(t, 2), "p_hac": round(p, 4),
                     "p_bonferroni": round(min(1.0, p * 13), 4), "sig_5pct_fw": bool(p * 13 < 0.05)})
    if rows:
        best = max(rows, key=lambda q: abs(q["r"]))
        leadlag_hac["results"][name] = {"by_lead": rows, "best_lead": best["lead"], "best_r": best["r"],
                                        "best_p_hac": best["p_hac"], "best_p_bonferroni": best["p_bonferroni"],
                                        "best_sig_5pct_fw": best["sig_5pct_fw"],
                                        "r_at_0": rows[0]["r"], "p_at_0_hac": rows[0]["p_hac"]}

# ---------------- 4) calibration ----------------
def calib(s, y, edges, labels):
    rows = []
    for (lo, hi), lab in zip(edges, labels):
        mk = (s >= lo) & (s < hi); k, nn = int(y[mk].sum()), int(mk.sum())
        rows.append({"bin": lab, "n": nn, "events": k, "freq": (round(k / nn, 3) if nn else None), "wilson95": wilson(k, nn)})
    return rows
band_edges = [(0, 35), (35, 50), (50, 65), (65, 101)]; band_labels = ["Calm", "Near normal", "Above normal", "High"]
dec_edges = [(float(np.percentile(score, 10 * i)), float(np.percentile(score, 10 * (i + 1))) + (1e-9 if i == 9 else 0)) for i in range(10)]
dec_labels = [f"D{i+1}" for i in range(10)]
def brier_skill(p, y):
    bs = float(np.mean((p - y) ** 2)); ref = float(np.mean((y.mean() - y) ** 2)); return round(bs, 4), round(1 - bs / ref, 3)
bs1, bss1 = brier_skill(score / 100.0, Y1); bs2, bss2 = brier_skill(score[m2] / 100.0, Y2raw[m2])
calibration = {
    "T1_by_band": calib(score, Y1, band_edges, band_labels), "T2_by_band": calib(score[m2], Y2raw[m2], band_edges, band_labels),
    "T1_by_decile": calib(score, Y1, dec_edges, dec_labels), "T2_by_decile": calib(score[m2], Y2raw[m2], dec_edges, dec_labels),
    "base_rate_T1": round(float(Y1.mean()), 3), "base_rate_T2": round(float(Y2raw[m2].mean()), 3),
    "brier_score_over_100": {"T1": bs1, "T1_skill_vs_base_rate": bss1, "T2": bs2, "T2_skill_vs_base_rate": bss2,
                              "note": "score/100 is not a probability; a negative skill score is expected and is a reason not to read the score as one"},
    "note": "in-sample frequencies; Wilson intervals do not account for overlapping 6-month windows (effective n is smaller)",
}

# ---------------- 5) robustness grid ----------------
def expanding_z_clip(sig, min_n=36, clip=3.0):
    vals, out = [], {}
    for m in bt.MONTHS:
        if m in sig:
            vals.append(sig[m])
            if len(vals) >= min_n:
                a = np.array(vals); sd = a.std(ddof=1)
                out[m] = float(np.clip((sig[m] - a.mean()) / (sd if sd > 0 else 1.0), -clip, clip))
    return out

RAW = {"ur_mom": ("labor", 1, bt.diff_k(bt.ur, 6)),
       "emp_yoy": ("labor", 1, {m: -v for m, v in bt.pct_k(bt.emp, 12).items()}),
       "imports_yoy": ("border", 2, {m: -v for m, v in bt.pct_k(bt.imports, 12).items()}),
       "exports_yoy": ("border", 2, {m: -v for m, v in bt.pct_k(bt.exports, 12).items()}),
       "peso_mom": ("border", 0, bt.pct_k(bt.peso, 6)),
       "listings_yoy": ("household", 1, bt.pct_k(bt.listings, 12)),
       "dom_yoy": ("household", 1, bt.diff_k(bt.dom, 12))}
HOUSING_MIN = {"listings_yoy", "dom_yoy"}
WEIGHT_SETS = {"40/35/25 (published)": (0.40, 0.35, 0.25), "equal": (1/3, 1/3, 1/3), "50/30/20": (0.5, 0.3, 0.2),
               "30/45/25": (0.3, 0.45, 0.25), "40/25/35": (0.4, 0.25, 0.35)}
def score_path(min_n, clip, lag_shift, w):
    zs = {k: (layer, lag + lag_shift, expanding_z_clip(sig, (24 if k in HOUSING_MIN else min_n) if min_n != 24 else 24, clip))
          for k, (layer, lag, sig) in RAW.items()}
    W = dict(zip(["labor", "border", "household"], w)); out = {}
    for t in months:
        layers = {}
        for k, (layer, lag, z) in zs.items():
            v = z.get(bt.madd(t, -lag))
            if v is not None: layers.setdefault(layer, []).append(v)
        if "labor" not in layers or "border" not in layers: continue
        ws = sum(W[L] for L in layers); zc = sum(W[L] * np.mean(v) for L, v in layers.items()) / ws
        out[t] = round(bt.squash(zc), 1)
    return out

grid = []
for (wname, w), min_n, clip, shift in itertools.product(WEIGHT_SETS.items(), [24, 36, 48], [2.0, 3.0, 4.0], [0, 1]):
    sp = score_path(min_n, clip, shift, w)
    idx = np.array([i for i, t in enumerate(months) if t in sp]); s = np.array([sp[months[i]] for i in idx])
    y1 = Y1[idx]; y2 = Y2raw[idx]; ok2 = y2 >= 0
    e1 = episode_stats(s >= ALERT, y1); e2 = episode_stats(s[ok2] >= ALERT, y2[ok2])
    windows = [(months[idx[a]], months[idx[b]]) for a, b in runs(s >= ALERT)]
    fires_2008 = any(a <= "2009-06" and b >= "2008-06" for a, b in windows)
    fires_2020 = any(a <= "2020-12" and b >= "2020-03" for a, b in windows)
    other = [wd for wd in windows if not (wd[0] <= "2009-06" and wd[1] >= "2008-06") and not (wd[0] <= "2020-12" and wd[1] >= "2020-03")]
    grid.append({"weights": wname, "min_n": min_n, "clip": clip, "lag_shift": shift, "n": int(len(s)),
                 "auc_T1": round(auc(s, y1), 3), "auc_T2": round(auc(s[ok2], y2[ok2]), 3),
                 "alert_episodes": e1["alert_episodes"], "true_warnings_T1": e1["true_warnings"], "events_detected_T1": e1["events_detected"],
                 "true_warnings_T2": e2["true_warnings"], "events_detected_T2": e2["events_detected"],
                 "fires_2008": fires_2008, "fires_2020": fires_2020, "n_other_alert_episodes": len(other), "alert_windows": windows})
a1 = np.array([g["auc_T1"] for g in grid]); a2 = np.array([g["auc_T2"] for g in grid])
robustness = {
    "method": "composite recomputed under alternative conventions; publication lags and targets held fixed",
    "n_configs": len(grid),
    "auc_T1_range": [round(float(a1.min()), 3), round(float(np.median(a1)), 3), round(float(a1.max()), 3)],
    "auc_T2_range": [round(float(a2.min()), 3), round(float(np.median(a2)), 3), round(float(a2.max()), 3)],
    "share_fires_2008": round(float(np.mean([g["fires_2008"] for g in grid])), 3),
    "share_fires_2020": round(float(np.mean([g["fires_2020"] for g in grid])), 3),
    "share_no_other_alerts": round(float(np.mean([g["n_other_alert_episodes"] == 0 for g in grid])), 3),
    "share_clean_record": round(float(np.mean([g["fires_2008"] and g["fires_2020"] and g["n_other_alert_episodes"] == 0 for g in grid])), 3),
    "share_T2_auc_above_0_75": round(float(np.mean(a2 > 0.75)), 3),
    "share_T1_auc_above_0_5": round(float(np.mean(a1 > 0.5)), 3),
    "grid": grid,
}

peso_hac = leadlag_hac["results"]["Peso depreciation, 6-mo %"]
summary = {
    "seed": 42, "sample": {"months": [months[0], months[-1]], "n": n, "events_T1": int(len(runs(Y1 == 1))), "events_T2": int(len(runs(Y2raw[m2] == 1)))},
    "bootstrap": bootstrap, "placebo": placebo_tests, "leadlag_hac": leadlag_hac, "calibration": calibration, "robustness": robustness,
    "reading": [
        f"Payroll-downturn discrimination (T2): ROC-AUC {bootstrap['auc_T2']['index']} with bootstrap 95% CI {bootstrap['auc_T2']['index_ci'][:2]} and placebo p = {placebo_tests['index_T2']['p_auc']}; "
        f"unemployment-spike discrimination (T1): AUC {bootstrap['auc_T1']['index']}, CI {bootstrap['auc_T1']['index_ci'][:2]}, placebo p = {placebo_tests['index_T1']['p_auc']} — indistinguishable from chance. "
        "T2 counts months already in a downturn, so it measures detection as much as warning (see the onset evaluation).",
        f"Index minus continuous Sahm statistic: ΔAUC {bootstrap['auc_T1']['diff_index_minus_sahm']} on T1 (CI {bootstrap['auc_T1']['diff_ci'][:2]}) and {bootstrap['auc_T2']['diff_index_minus_sahm']} on T2 (CI {bootstrap['auc_T2']['diff_ci'][:2]}): no evidence the index beats the simpler rule.",
        f"Episode-level rates are not estimable from {obs_e2['alert_episodes']} alert episodes: bootstrap recall interval for T2 is {bootstrap['episode_ge65_T2']['recall_ci'][:2]}; the precision interval is degenerate because every resampled alert block sits inside a downturn.",
        "After Newey-West correction and a Bonferroni family of 13 leads, border trade and port-of-entry crossings (El Paso + Ysleta) are coincident with El Paso payroll growth, not leading; "
        f"the peso's best lead ({peso_hac['best_lead']} months, r = {peso_hac['best_r']}) has family-wise p = {peso_hac['best_p_bonferroni']} — suggestive, not established.",
        f"The clean two-alert record (2008, 2020, nothing else) holds in {round(100*robustness['share_clean_record'])}% of the {robustness['n_configs']} alternative conventions; both historical alerts fire in {round(100*min(robustness['share_fires_2008'],robustness['share_fires_2020']))}% of them. T2 AUC stays within {robustness['auc_T2_range'][0]}–{robustness['auc_T2_range'][2]}; T1 AUC never exceeds {robustness['auc_T1_range'][2]}.",
    ],
}
with open(os.path.join(OUT, "inference.json"), "w") as f:
    json.dump(summary, f, indent=1, default=float)

print("bootstrap AUC T1 index", bootstrap["auc_T1"]["index"], bootstrap["auc_T1"]["index_ci"], "| sahm", bootstrap["auc_T1"]["sahm"], bootstrap["auc_T1"]["sahm_ci"], "| diff", bootstrap["auc_T1"]["diff_index_minus_sahm"], bootstrap["auc_T1"]["diff_ci"])
print("bootstrap AUC T2 index", bootstrap["auc_T2"]["index"], bootstrap["auc_T2"]["index_ci"], "| sahm", bootstrap["auc_T2"]["sahm"], bootstrap["auc_T2"]["sahm_ci"], "| diff", bootstrap["auc_T2"]["diff_index_minus_sahm"], bootstrap["auc_T2"]["diff_ci"])
print("episode T2 prec CI", bootstrap["episode_ge65_T2"]["precision_ci"], "recall CI", bootstrap["episode_ge65_T2"]["recall_ci"])
print("placebo p(AUC) T1", placebo_tests["index_T1"]["p_auc"], "T2", placebo_tests["index_T2"]["p_auc"], "| p(true warnings) T2", placebo_tests["index_T2"]["p_true_warnings"])
for name, r in leadlag_hac["results"].items():
    print(f"HAC {name:42s} r0={r['r_at_0']:+.3f} p0={r['p_at_0_hac']:.4f} best lead {r['best_lead']} r={r['best_r']:+.3f} p={r['best_p_hac']:.4f} bonf={r['best_p_bonferroni']:.3f}")
print("calibration BSS T1", bss1, "T2", bss2)
print("robustness: configs", robustness["n_configs"], "AUC T1 range", robustness["auc_T1_range"], "AUC T2 range", robustness["auc_T2_range"],
      "clean record share", robustness["share_clean_record"], "fires 2008", robustness["share_fires_2008"], "fires 2020", robustness["share_fires_2020"])
