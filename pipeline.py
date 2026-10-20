"""
BorderPulse — El Paso Economic Shock Detector
Data pipeline: turns raw indicator CSVs (FRED) into a monthly 0-100
El Paso Shock Risk score with layer sub-indices, sector stress, drivers,
and an out-of-sample style back-test (expanding-window normalization,
no lookahead in the z-scores).

Layers:
  LOCAL LABOR  (40%): EP unemployment momentum, EP total nonfarm growth
  BORDER       (35%): US-Mexico imports, exports (YoY), peso momentum
  HOUSEHOLD    (25%): housing active listings YoY, median days on market YoY

All indicators are converted to a "stress direction" (+ = more stress),
z-scored against an EXPANDING window of their own history (min 36 months),
clipped to [-3, 3], averaged within layers, combined with layer weights,
then mapped to 0-100 via a logistic squash.
"""
import json, math, csv, os, random, datetime
from collections import OrderedDict

VERSION = "6.2.0"   # v6.2: data explorer and refresh provenance fixes; score model unchanged. v5: ONE MODEL — the dashboard now uses exactly the back-test definitions (payroll YoY,
                    # not 6-mo; z-score history from 2000 via data/full/), verified feature-by-feature against
                    # validation/lab_data.json. Level names describe distance from normal; "Housing market"
                    # renamed "Housing market"; combined El Paso + Ysleta crossings; data-retrieval date exposed.
                    # v4.1: Las Cruces added to the regional labor comparison (display/comparison only);
                    # border-chain context series (crossings, trade, local jobs) for the Border tab;
                    # pre-specified border-layer test lives in border_test.py. Composite UNCHANGED.
                    # v4: headline = latest COMPLETE month (all expected indicators present);
                    # partial trailing months are reported as a labeled nowcast, never as the headline.
                    # v3: decomposition contract, change attribution, divergence rule,
                    # uncertainty band, benchmark hooks. Composite definition UNCHANGED from v2.
                    # v3.1 (2026-10): display-only additions in dashboard_body.html — "why" panel,
                    # data-timing labels, regional bars, history tabs, brief download, start-here cards.

DATA = os.path.join(os.path.dirname(__file__), "data")

def load(name):
    d = OrderedDict()
    with open(os.path.join(DATA, name)) as f:
        for row in csv.DictReader(f):
            v = row["value"].strip()
            if v and v != ".":
                d[row["date"][:7]] = float(v)
    return d

def load_optional(name):
    return load(name) if os.path.exists(os.path.join(DATA, name)) else OrderedDict()

def month_range(start, end):
    y, m = map(int, start.split("-")); Y, M = map(int, end.split("-"))
    out = []
    while (y, m) <= (Y, M):
        out.append(f"{y:04d}-{m:02d}")
        m += 1
        if m == 13: m, y = 1, y + 1
    return out

def shift(series, months, k):
    """value k months before month at index i (by calendar list)."""
    out = {}
    for i, mo in enumerate(months):
        if i - k >= 0:
            prev = months[i - k]
            if mo in series and prev in series:
                out[mo] = (series[mo], series[prev])
    return out

def pct_change(series, months, k):
    return {mo: 100.0 * (a / b - 1.0) for mo, (a, b) in shift(series, months, k).items() if b != 0}

def diff(series, months, k):
    return {mo: a - b for mo, (a, b) in shift(series, months, k).items()}

def expanding_z(sig, months, min_n=36):
    """z-score of sig[mo] vs its own history UP TO AND INCLUDING mo (no future data)."""
    vals, out = [], {}
    for mo in months:
        if mo in sig:
            vals.append(sig[mo])
            if len(vals) >= min_n:
                n = len(vals)
                mean = sum(vals) / n
                var = sum((v - mean) ** 2 for v in vals) / (n - 1)
                sd = math.sqrt(var) if var > 0 else 1.0
                out[mo] = max(-3.0, min(3.0, (sig[mo] - mean) / sd))
    return out

def squash(z):
    """map composite z (-3..3) to 0-100, 50 = typical conditions."""
    return round(100.0 / (1.0 + math.exp(-1.1 * z)), 1)

# ---------------- load raw ----------------
raw = {
    "ep_ur":      load("full/ep_unrate.csv"),          # v5: 2000-> history, same as backtest.py
    "tx_ur":      load("tx_unrate.csv"),
    "us_ur":      load("us_unrate.csv"),
    "lc_ur":      load_optional("lc_unrate.csv"),     # v4.1: Las Cruces MSA (FRED LASC735UR) — comparison only
    "ep_emp":     load("full/ep_nonfarm.csv"),
    "imports":    load("full/us_imports_mexico.csv"),
    "exports":    load("full/us_exports_mexico.csv"),
    "peso":       load("full/peso_usd.csv"),
    "listings":   load("ep_active_listings.csv"),
    "dom":        load("ep_days_on_market.csv"),
}
sectors_raw = {
    "Trade, Transportation & Utilities": load("ep_trade.csv"),
    "Government":                        load("ep_govt.csv"),
    "Construction & Mining":             load("ep_construction.csv"),
    "Manufacturing":                     load("ep_mfg.csv"),
    "Education & Health (private)":      load("ep_eduhealth.csv"),
    "Leisure & Hospitality":             load("ep_leisure.csv"),
    "Professional & Business Services":  load("ep_profbiz.csv"),
}

# v5: the calendar runs from 2000 (same as backtest.py) to the latest month present in any core input —
# no hand-edited end month.
_core_last = max(max(s) for s in raw.values() if s)
months = month_range("2000-01", _core_last)

# ---------------- stress signals (+ = stress) ----------------
signals = {
    # labor
    "ep_ur_mom":   ("Local labor", "El Paso unemployment, 6-mo change (pp)",
                    diff(raw["ep_ur"], months, 6)),
    # v5: year-over-year, as in backtest.py — the payroll series is not seasonally adjusted, and a
    # 6-month change carries seasonal swings (the v4 dashboard/backtest mismatch flagged in review).
    "ep_emp_yoy":  ("Local labor", "El Paso nonfarm jobs, YoY growth (%)",
                    {k: -v for k, v in pct_change(raw["ep_emp"], months, 12).items()}),
    # border
    "imports_yoy": ("Border economy", "US imports from Mexico, YoY (%)",
                    {k: -v for k, v in pct_change(raw["imports"], months, 12).items()}),
    "exports_yoy": ("Border economy", "US exports to Mexico, YoY (%)",
                    {k: -v for k, v in pct_change(raw["exports"], months, 12).items()}),
    "peso_mom":    ("Border economy", "Peso/USD, 6-mo depreciation (%)",
                    pct_change(raw["peso"], months, 6)),
    # household / housing
    "listings_yoy":("Housing market", "Active home listings, YoY (%)",
                    pct_change(raw["listings"], months, 12)),
    "dom_yoy":     ("Housing market", "Median days on market, YoY change (days)",
                    diff(raw["dom"], months, 12)),
}

LAYERS = {"Local labor": 0.40, "Border economy": 0.35, "Housing market": 0.25}
MIN_N = {"listings_yoy": 24, "dom_yoy": 24}   # shorter history for housing series

zs = {k: expanding_z(sig, months, MIN_N.get(k, 36)) for k, (_, _, sig) in signals.items()}

# ---------------- composite ----------------
composite, layers_hist = {}, {L: {} for L in LAYERS}
for mo in months:
    layer_vals = {}
    for L in LAYERS:
        vals = [zs[k][mo] for k, (lyr, _, _) in signals.items() if lyr == L and mo in zs[k]]
        if vals:
            layer_vals[L] = sum(vals) / len(vals)
    if "Local labor" not in layer_vals or "Border economy" not in layer_vals:
        continue
    wsum = sum(LAYERS[L] for L in layer_vals)
    z = sum(LAYERS[L] * layer_vals[L] for L in layer_vals) / wsum
    composite[mo] = squash(z)
    for L, v in layer_vals.items():
        layers_hist[L][mo] = squash(v)

def level(score):
    # v5: names describe distance from El Paso's own normal (50 = a typical month); 65+ is the alert zone.
    return ("Calm" if score < 35 else "Near normal" if score < 50 else
            "Above normal" if score < 65 else "High")

# ---------------- TX / US / Las Cruces labor-only comparison ----------------
def labor_score(ur):
    z = expanding_z(diff(ur, months, 6), months)
    return {mo: squash(v) for mo, v in z.items()}
cmp_scores = {"El Paso": {mo: layers_hist["Local labor"].get(mo) for mo in months
                          if mo in layers_hist["Local labor"]},
              "Texas": labor_score(raw["tx_ur"]),
              "United States": labor_score(raw["us_ur"])}
if raw["lc_ur"]:
    # Las Cruces uses the unemployment-only transform (same as TX/US); El Paso's labor layer also
    # includes payrolls — documented on the dashboard so the comparison is not over-read.
    cmp_scores["Las Cruces"] = labor_score(raw["lc_ur"])
cmp_scores = {k: cmp_scores[k] for k in ("El Paso", "Las Cruces", "Texas", "United States") if k in cmp_scores}

# ---------------- v4: headline convention = latest COMPLETE month ----------------
# An indicator is "expected" at month mo if it has a z-score at or before mo (i.e. its
# series has started). A month is complete if every expected indicator has a z-score
# there. The headline score is the latest complete month; later months with a composite
# (where lagging series have not yet published) are reported as a NOWCAST, and interior
# gaps (e.g. the 2025-10 federal data pause) are listed as partial months.
_started = {k: (min(zs[k]) if zs[k] else None) for k in signals}
def expected_at(mo):
    return [k for k in signals if _started[k] is not None and _started[k] <= mo]
def missing_at(mo):
    return [k for k in expected_at(mo) if mo not in zs[k]]
complete_months = [mo for mo in months if mo in composite and not missing_at(mo)]
last = complete_months[-1]
partial_months = sorted(mo for mo in composite if mo <= last and missing_at(mo))
nowcast = {}
for mo in sorted(m for m in composite if m > last):
    miss = missing_at(mo)
    nowcast[mo] = {"score": composite[mo], "missing": miss,
                   "present": [k for k in signals if mo in zs[k]],
                   "note": "preliminary: computed from the indicators published so far, with layer weights renormalized; becomes the headline once all expected indicators publish"}

# ---------------- sector stress ----------------
def sector_state(s):
    g6 = pct_change(s, months, 6); g12 = pct_change(s, months, 12)
    mo = max(m for m in months if m in g6 and m in g12)
    a6 = (1 + g6[mo] / 100) ** 2 - 1   # 6-mo annualized
    y = g12[mo]
    score = 0.6 * a6 * 100 + 0.4 * y
    state = "green" if score > 0.5 else "yellow" if score > -1.0 else "red"
    return {"asof": mo, "growth6m_ann": round(a6 * 100, 1), "yoy": round(y, 1),
            "state": state, "latest": s[max(m for m in months if m in s)]}
sectors = {name: sector_state(s) for name, s in sectors_raw.items()}

# ---------------- drivers at latest month ----------------
def latest_common(sig):
    ms = [m for m in months if m in sig]
    return ms[-1] if ms else None
# ---------------- extra indicators (watch / community modules) ----------------
# These NEVER enter the composite score; they surface in the dashboard with
# their own z-scores.  See data/extra/manifest.json for the promotion rule.
watch = []
_man_path = os.path.join(DATA, "extra", "manifest.json")
if os.path.exists(_man_path):
    _man = json.load(open(_man_path))
    for ind in _man["indicators"]:
        if ind.get("group") == "benchmark":
            continue   # benchmarks (e.g. Dallas Fed BCI) never render as watch indicators
        path = os.path.normpath(os.path.join(DATA, "extra", ind["file"]))
        entry = {"label": ind["label"], "group": ind["group"], "source": ind["source"],
                 "status": ind["status"], "active": False}
        if os.path.exists(path):
            s = OrderedDict()
            with open(path) as f:
                for row in csv.DictReader(f):
                    v = row["value"].strip()
                    if v and v != ".":
                        s[row["date"][:7]] = float(v)
            if len(s) >= ind["min_n"] + 12:
                if ind["transform"] == "pct3":
                    sig = pct_change(s, months, 3)
                else:  # yoy_pct
                    sig = pct_change(s, months, 12)
                if ind["direction"] == "down_is_stress":
                    sig = {k: -v for k, v in sig.items()}
                z = expanding_z(sig, months, ind["min_n"])
                zm = [m for m in months if m in z]
                if zm:
                    mo = zm[-1]
                    raw_disp = sig[mo] if ind["direction"] == "up_is_stress" else -sig[mo]
                    entry.update({"active": True, "z": round(z[mo], 2),
                                  "raw_change_pct": round(raw_disp, 1), "asof": mo,
                                  "stale": mo < months[-14]})
        watch.append(entry)

# display values: undo the stress-direction inversion so users see the true change
INVERTED = {"ep_emp_yoy", "imports_yoy", "exports_yoy"}
def reading(k, mo):
    lyr, label, sig = signals[k]
    if mo not in zs[k]: return None
    disp = -sig[mo] if k in INVERTED else sig[mo]
    # v5.0.1: the typical value this reading is compared against (mean of its own history up to mo,
    # in display units) — so the dashboard can say "slower than the usual 1.7%" instead of only a z-score
    hist = [sig[m] for m in months if m in sig and m <= mo]
    typ = sum(hist) / len(hist)
    typ = -typ if k in INVERTED else typ
    return {"key": k, "layer": lyr, "label": label, "z": round(zs[k][mo], 2), "raw": round(disp, 2),
            "typical": round(typ, 2), "asof": mo}
drivers = [r for r in (reading(k, last) for k in signals) if r]           # all at the headline month
drivers.sort(key=lambda d: -d["z"])
latest_readings = [r for r in (reading(k, latest_common(zs[k])) for k in signals if latest_common(zs[k])) if r]
latest_readings.sort(key=lambda d: -d["z"])

# ---------------- back-test check (COVID) ----------------
covid = {mo: composite[mo] for mo in month_range("2019-09", "2020-12") if mo in composite}

# ---------------- v3: decomposition contract ----------------
def composite_at(mo, weights=LAYERS, drop=None):
    """(score, z_comp, {indicator: weighted z contribution}) or None.
    Contributions are exact and additive: z_comp == sum(contribs.values())."""
    layer_ind = {}
    for L in weights:
        ks = [k for k, (lyr, _, _) in signals.items()
              if lyr == L and mo in zs[k] and k != drop]
        if ks:
            layer_ind[L] = ks
    if "Local labor" not in layer_ind or "Border economy" not in layer_ind:
        return None
    wsum = sum(weights[L] for L in layer_ind)
    per = {}
    for L, ks in layer_ind.items():
        for k in ks:
            per[k] = weights[L] / (len(ks) * wsum) * zs[k][mo]
    zc = sum(per.values())
    return squash(zc), zc, per

def points_alloc(score, zc, per):
    """Proportional allocation of (score-50) across indicators. Adds exactly to score-50.
    Documented convention: exact additivity holds in z-space; the squash is monotone,
    so point shares are allocated pro-rata. Reproducible from per/zc."""
    if abs(zc) < 1e-9:
        return {k: 0.0 for k in per}
    # v5.0.1: largest-remainder rounding so the 0.1-pt shares add up EXACTLY to the rounded (score-50)
    exact = {k: (score - 50.0) * v / zc for k, v in per.items()}
    target = round((score - 50.0) * 10)
    tenths = {k: math.floor(x * 10) for k, x in exact.items()}
    short = target - sum(tenths.values())
    for k in sorted(exact, key=lambda k: exact[k] * 10 - tenths[k], reverse=True)[:max(0, short)]:
        tenths[k] += 1
    return {k: round(t / 10, 1) for k, t in tenths.items()}

_cur = composite_at(last)
_score, _zc, _per = _cur
prev = months[months.index(last) - 1]
_prevc = composite_at(prev)
decomposition = {
    "asof": last, "score": _score, "z_composite": round(_zc, 4),
    "neutral": 50.0,
    "z_contributions": {k: round(v, 4) for k, v in _per.items()},
    "points_vs_neutral": points_alloc(_score, _zc, _per),
    "convention": "z-contributions are exact and additive; points are pro-rata shares of (score-50)",
}

# ---------------- v3: month-over-month change attribution ----------------
change_attr = None
if _prevc is not None:
    ps, pzc, pper = _prevc
    dscore = round(_score - ps, 1)
    dzc = _zc - pzc
    keys = sorted(set(_per) | set(pper))
    dz = {k: _per.get(k, 0.0) - pper.get(k, 0.0) for k in keys}
    if abs(dzc) < 1e-9:
        pts = {k: 0.0 for k in keys}
    else:
        pts = {k: round(dscore * dz[k] / dzc, 2) for k in keys}
    change_attr = {
        "from": prev, "to": last, "delta_score": dscore,
        "points_by_indicator": pts,
        "new_data": {k: (latest_common(signals[k][2])) for k in keys},
        "note": "Attribution of score(t)-score(t-1) to each indicator's movement in weighted z-space, pro-rata in points.",
    }

# ---------------- v3: uncertainty band (weight perturbation + indicator jackknife) ----------------
random.seed(42)
_band_scores = [_score]
for k in list(signals):                     # leave-one-indicator-out
    r = composite_at(last, drop=k)
    if r: _band_scores.append(r[0])
_base = [LAYERS[L] for L in LAYERS]
_names = list(LAYERS)
CONC = 60.0                                  # Dirichlet concentration around 40/35/25
for _ in range(200):
    draw = [random.gammavariate(CONC * b, 1.0) for b in _base]
    s = sum(draw)
    w = {L: d / s for L, d in zip(_names, draw)}
    r = composite_at(last, weights=w)
    if r: _band_scores.append(r[0])
_band_scores.sort()
def _pct(p):
    i = max(0, min(len(_band_scores) - 1, int(round(p * (len(_band_scores) - 1)))))
    return _band_scores[i]
score_band = {"lo": round(_pct(0.10), 1), "hi": round(_pct(0.90), 1),
              "method": "10th-90th pct over leave-one-indicator-out + 200 Dirichlet weight draws (conc=60, seed=42)"}

# ---------------- v3: EP vs TX divergence rule ----------------
DIVERGE_PP, DIVERGE_MONTHS = 10.0, 2
_dvhist = {}
for mo in months:
    a, b = cmp_scores["El Paso"].get(mo), cmp_scores["Texas"].get(mo)
    if a is not None and b is not None:
        _dvhist[mo] = round(a - b, 1)
_dvhist = {m: v for m, v in _dvhist.items() if m <= last}
_dvm = sorted(_dvhist)
divergence = {"rule": f"underperforming if EP labor-stress minus TX >= +{DIVERGE_PP:.0f} for {DIVERGE_MONTHS} consecutive months; outperforming if <= -{DIVERGE_PP:.0f}; else tracking",
              "history": _dvhist, "state": "tracking", "latest_gap": _dvhist[_dvm[-1]] if _dvm else None}
if len(_dvm) >= DIVERGE_MONTHS:
    tail = [_dvhist[m] for m in _dvm[-DIVERGE_MONTHS:]]
    if all(v >= DIVERGE_PP for v in tail):   divergence["state"] = "underperforming"
    elif all(v <= -DIVERGE_PP for v in tail): divergence["state"] = "outperforming"

# ---------------- v3: model-regime flag (housing layer entry) ----------------
_hm = [m for m in months if m in zs["listings_yoy"] or m in zs["dom_yoy"]]
regime_break = _hm[0] if _hm else None   # composite before this month is labor+border only

# ---------------- v4.1: border transmission chain (display only — never scored) ----------------
# Step-by-step context for the Border tab: national trade (the corridor), port-of-entry
# crossings (people and freight actually entering El Paso), then local jobs that depend on
# them. YoY % change of 3-month moving sums, to damp single-month reporting anomalies.
_chain_months = month_range("2014-01", months[-1])
def _yoy3(series):
    s3 = {}
    for i in range(2, len(_chain_months)):
        w = _chain_months[i - 2:i + 1]
        if all(m in series for m in w):
            s3[_chain_months[i]] = sum(series[m] for m in w)
    out = {}
    for i in range(12, len(_chain_months)):
        m, p = _chain_months[i], _chain_months[i - 12]
        if m in s3 and p in s3 and s3[p] > 0 and m >= "2016-01":
            out[m] = round(100.0 * (s3[m] / s3[p] - 1.0), 1)
    return out
_extra = "extra"
def combined_crossings(measure):
    """v5: El Paso + Ysleta ports. CBP split Ysleta (port 2401) out of El Paso (2402) effective
    2020-03-16, so the BTS 'El Paso' series loses Ysleta's traffic from March 2020 — the drop the
    v3/v4 manifest called a 'reporting break'. Before 2020-03 the El Paso port already included
    Ysleta; from 2020-03 we add the Ysleta port. Months after the split with no Ysleta record are
    left missing rather than undercounted. Santa Teresa and Tornillo are not included (a geography
    decision to settle with regional partners)."""
    ep = load_optional(os.path.join(_extra, f"ep_crossings_{measure}.csv"))
    ys = load_optional(os.path.join(_extra, f"ysleta_crossings_{measure}.csv"))
    if not ys:
        return OrderedDict()
    out = OrderedDict()
    for m, v in ep.items():
        if m < "2020-03":
            out[m] = v
        elif m in ys:
            out[m] = v + ys[m]
    return out
_imp_full, _exp_full = load_optional("full/us_imports_mexico.csv") or raw["imports"], load_optional("full/us_exports_mexico.csv") or raw["exports"]
_chain_inputs = [
    ("trade", "U.S.–Mexico goods trade (imports + exports)", "Census via FRED IMPMX + EXPMX · national · ~2-mo lag", "corridor",
     {m: _imp_full[m] + _exp_full[m] for m in _imp_full if m in _exp_full}),
    ("trucks", "Truck crossings, El Paso + Ysleta ports", "BTS keg4-3bc2 · Ysleta added from 2020-03 (port split)", "freight",
     combined_crossings("trucks")),
    ("pov", "Personal-vehicle crossings, El Paso + Ysleta ports", "BTS keg4-3bc2 · ~1–2-mo lag", "people",
     combined_crossings("pov")),
    ("ped", "Pedestrian crossings, El Paso + Ysleta ports", "BTS keg4-3bc2 · single-month spikes in source data", "people",
     combined_crossings("ped")),
    ("trade_jobs", "El Paso trade, transportation & utilities jobs", "BLS CES via FRED ELPA348TRADN · ~1-mo lag", "local",
     sectors_raw["Trade, Transportation & Utilities"]),
    ("leisure_jobs", "El Paso leisure & hospitality jobs", "BLS CES via FRED ELPA348LEIHN · visitor-spending proxy", "local",
     sectors_raw["Leisure & Hospitality"]),
]
border_chain = {"note": "YoY % change of 3-month moving sums; display only — none of these enter the composite.",
                "series": []}
for key, label, src, stage, ser in _chain_inputs:
    if ser:
        y = _yoy3(ser)
        if y:
            lm = max(y)
            border_chain["series"].append({"key": key, "label": label, "source": src, "stage": stage,
                                           "latest_month": lm, "latest": y[lm], "yoy3": y})

# ---------------- v5: dates readers need ----------------
# data_retrieved = the most recent retrieval date recorded in data/MANIFEST.json (the build date is "generated").
_data_retrieved = None
_mf = os.path.join(DATA, "MANIFEST.json")
if os.path.exists(_mf):
    import re as _re
    _dates = [_re.match(r"\d{4}-\d{2}-\d{2}", f.get("retrieved", "") or "") for f in json.load(open(_mf)).get("files", [])]
    _dates = [d.group(0) for d in _dates if d]
    _data_retrieved = max(_dates) if _dates else None
# unemployment for El Paso, Las Cruces, Texas and the U.S. at ONE common month (the latest month all have)
_ur_keys = {"El Paso": "ep_ur", "Las Cruces": "lc_ur", "Texas": "tx_ur", "United States": "us_ur"}
_ur_common = [m for m in months if all(m in raw[k] for k in _ur_keys.values() if raw[k])]
_same_month_ur = ({"month": _ur_common[-1], **{n: raw[k][_ur_common[-1]] for n, k in _ur_keys.items() if raw[k]}}
                  if _ur_common else None)

out = {
    "version": VERSION,
    "generated": datetime.datetime.now(datetime.timezone.utc).date().isoformat(),
    "asof": last,
    "score": composite[last],
    "score_band": score_band,
    "decomposition": decomposition,
    "change_attribution": change_attr,
    "divergence": divergence,
    "regime_break": regime_break,
    "level": level(composite[last]),
    "delta3m": round(composite[last] - composite[months[months.index(last) - 3]], 1),
    "layers": {L: {"score": layers_hist[L].get(last), "weight": LAYERS[L]} for L in LAYERS},
    "history": {m: v for m, v in composite.items() if m <= last},
    "nowcast": nowcast,
    "partial_months": partial_months,
    "headline_convention": "latest month at which every expected indicator has a z-score; later partial months are nowcasts",
    "latest_readings": latest_readings,
    "layers_history": {L: {m: x for m, x in h.items() if m <= last} for L, h in layers_hist.items()},
    "comparison": {k: {"latest": v.get(max(m for m in v if m <= last)),
                       "history": {m: x for m, x in v.items() if m <= last}} for k, v in cmp_scores.items()},
    "sectors": sectors,
    "drivers": drivers,
    "covid_backtest": covid,
    "watch": watch,
    "border_chain": border_chain,
    "context_series": {
        "ep_unemployment": {m: v for m, v in raw["ep_ur"].items() if m >= "2018-01"},
        "us_imports_mexico": {m: v for m, v in raw["imports"].items() if m >= "2018-01"},
        "active_listings": {m: v for m, v in raw["listings"].items() if m >= "2018-01"},
    },
    "sector_history": {name: {m: v for m, v in s.items() if m >= "2023-01"}
                       for name, s in sectors_raw.items()},
    "data_retrieved": _data_retrieved,
    "same_month_unemployment": _same_month_ur,
    "latest_values": {
        "ep_unemployment": raw["ep_ur"][latest_common(raw["ep_ur"])],
        "tx_unemployment": raw["tx_ur"][latest_common(raw["tx_ur"])],
        "us_unemployment": raw["us_ur"][latest_common(raw["us_ur"])],
        "lc_unemployment": raw["lc_ur"][latest_common(raw["lc_ur"])] if raw["lc_ur"] else None,
        "ep_jobs_k": raw["ep_emp"][latest_common(raw["ep_emp"])],
        "imports_bn": round(raw["imports"][latest_common(raw["imports"])] / 1000, 1),
        "exports_bn": round(raw["exports"][latest_common(raw["exports"])] / 1000, 1),
        "peso": round(raw["peso"][latest_common(raw["peso"])], 2),
    },
}
with open(os.path.join(os.path.dirname(__file__), "borderpulse_output.json"), "w") as f:
    json.dump(out, f, indent=1)

print("as of", last, "(latest complete month)", "score", out["score"], out["level"], "Δ3m", out["delta3m"],
      f"band [{score_band['lo']}, {score_band['hi']}]", "divergence:", divergence["state"])
for mo, nc in nowcast.items():
    print(f"  nowcast {mo}: {nc['score']} ({level(nc['score'])}) from {len(nc['present'])}/{len(signals)} indicators; missing {nc['missing']}")
if partial_months: print("  partial interior months:", partial_months)
if change_attr:
    print("change attribution", change_attr["from"], "->", change_attr["to"],
          "Δ", change_attr["delta_score"], change_attr["points_by_indicator"])
for L in LAYERS: print(f"  {L}: {layers_hist[L].get(last)}")
print("drivers:")
for d in drivers: print(f"  z={d['z']:+.2f}  {d['label']}  raw={d['raw']} ({d['asof']})")
print("sectors:")
for n, s in sectors.items(): print(f"  {s['state']:6s} {n}: 6m ann {s['growth6m_ann']}%, yoy {s['yoy']}%")
print("covid backtest:")
for mo in sorted(covid): print(f"  {mo}: {covid[mo]} {level(covid[mo])}")
print("comparison latest:", {k: v['latest'] for k, v in out['comparison'].items()})
print("border chain:", {s['key']: (s['latest_month'], s['latest']) for s in border_chain['series']})
