"""
Generate the one-page monthly brief (borderpulse_brief.md) from the computed
outputs: borderpulse_output.json (current conditions), validation/backtest_metrics.json,
validation/benchmarks.json and (v5) validation/onset_eval.json.

The employment warning uses the fixed rule: score >= 65. Framing: claims are EPISODE
counts with exact intervals, never month-level precision percentages. v5: the brief
separates warnings before a downturn starts from detection of one already under way,
and states three dates (headline month, data retrieval, build).
"""
import json, os, datetime

BASE = os.path.dirname(os.path.abspath(__file__))
data = json.load(open(os.path.join(BASE, "borderpulse_output.json")))
val  = json.load(open(os.path.join(BASE, "validation", "backtest_metrics.json")))
bm   = json.load(open(os.path.join(BASE, "validation", "benchmarks.json")))
ep2  = bm["rules"]["borderpulse_ge65"]["payroll_growth_negative_6m"]["episode"]
ep1  = bm["rules"]["borderpulse_ge65"]["unemployment_+0.5pp_6m"]["episode"]
sahm1 = bm["rules"]["local_sahm_rule"]["unemployment_+0.5pp_6m"]["episode"]
_on_p = os.path.join(BASE, "validation", "onset_eval.json")
onset = json.load(open(_on_p)) if os.path.exists(_on_p) else None

MONTHS = ["January","February","March","April","May","June","July","August",
          "September","October","November","December"]
def pretty(m):  # "2026-06" -> "June 2026"
    y, mm = m.split("-"); return f"{MONTHS[int(mm)-1]} {y}"

def level_fn(x):  # v5 names: distance from El Paso's own normal (50 = typical month)
    return "Calm" if x < 35 else "Near normal" if x < 50 else "Above normal" if x < 65 else "High"

score, asof = data["score"], data["asof"]
level = level_fn(score)
warning_active = score >= 65
layers = data["layers"]
drivers = sorted(data["drivers"], key=lambda d: -d["z"])
sectors = data["sectors"]
cmp_ = {k: v["latest"] for k, v in data["comparison"].items()}
smu = data.get("same_month_unemployment")
lv = data["latest_values"]
today = datetime.datetime.now(datetime.timezone.utc).date()

lines = []
A = lines.append
nowcast = data.get("nowcast") or {}
A(f"# El Paso Economic Conditions — {pretty(asof)}")
A(f"*BorderPulse monthly brief (model v{data.get('version','')}) · headline month {pretty(asof)} (latest month with all seven indicators) · "
  f"data retrieved {data.get('data_retrieved') or '—'} · generated {today.isoformat()}*")
A("")
A("**How to read the score:** 0–100 index; 50 is a typical month in El Paso's record since 2000. "
  "It is not a probability. Below 35 Calm · 35–50 Near normal · 50–65 Above normal · 65+ High (alert zone).")
A("")
A("## Employment alert: " + ("**ACTIVE**" if warning_active else "**NOT ACTIVE**"))
_hist = (f"Since 2003 the ≥65 alert has fired in {ep2['alert_episodes']} episodes and never during an expansion. ")
if onset:
    po = onset["results"]["BorderPulse score ≥ 65"]["payroll_onset"]
    uo = onset["results"]["BorderPulse score ≥ 65"]["unemployment_onset"]
    _hist += (f"Measured against when downturns actually started, it warned ahead of {po['advance_warnings']} of "
              f"{po['n_onsets']} payroll downturns (2008, two months early) and spotted {po['detections_after_onset']} "
              f"once under way (2020); it warned ahead of {uo['advance_warnings']} of {uo['n_onsets']} unemployment rises. "
              "These are counts from very few events, not rates.")
if warning_active:
    A("The score has crossed the fixed 65 threshold. " + _hist +
      " Treat this as a prompt to look at the underlying indicators, not as a verdict.")
else:
    A("The fixed alert threshold (score ≥ 65) has not been crossed. " + _hist +
      " 'Not active' lowers concern but does not rule out a downturn: the index works best at confirming stress, not predicting it.")
if nowcast:
    nm = max(nowcast); nc = nowcast[nm]
    lbl = {d2["key"]: d2["label"] for d2 in data["drivers"]}
    miss = ", ".join(lbl.get(k, k).split(",")[0] for k in nc["missing"])
    A(f"**Preliminary {pretty(nm)} reading: {nc['score']:.0f}/100 ({level_fn(nc['score'])})** from {len(nc['present'])} of 7 indicators "
      f"(missing for {pretty(nm)} in this data snapshot: {miss}). This is a nowcast, not the headline."
      + (" It is above the 65 threshold: treat as an early flag pending the missing data." if nc['score'] >= 65 else ""))
A("")
band = data.get("score_band", {})
_b = f" (model sensitivity range {band['lo']:.0f}–{band['hi']:.0f} under alternative weights and dropped indicators)" if band else ""
A(f"## Conditions at a glance — score {score:.0f}/100 ({level}){_b}")
d3 = data["delta3m"]
A(f"- Score is {'down' if d3 <= 0 else 'up'} {abs(d3):.1f} points over three months.")
A(f"- Layers: local labor {layers['Local labor']['score']:.0f}, "
  f"border economy {layers['Border economy']['score']:.0f}, "
  f"housing market {layers['Housing market']['score']:.0f} (each 0–100; 50 ≈ a typical month).")
dv = data.get("divergence", {})
if smu:
    others = " · ".join(f"{k} {v:.1f}%" for k, v in smu.items() if k not in ("month", "El Paso"))
    A(f"- Unemployment, {pretty(smu['month'])}: El Paso {smu['El Paso']:.1f}% · {others}.")
A(f"- Labor-stress comparison: " + " · ".join(f"{k} {v:.0f}" for k, v in cmp_.items()) +
  f" — El Paso is **{dv.get('state','tracking')}** Texas under the published divergence rule.")
A(f"- Border trade (national, mostly through-traffic for El Paso): imports from Mexico ${lv['imports_bn']}B, "
  f"exports ${lv['exports_bn']}B; peso {lv['peso']:.1f}/USD.")
bc = data.get("border_chain", {}).get("series", [])
if bc:
    byk = {s["key"]: s for s in bc}
    parts = [f"{byk[k]['label'].split(',')[0]} {byk[k]['latest']:+.1f}%" for k in ("pov", "ped", "trucks") if k in byk]
    if parts:
        A(f"- Crossings into El Paso + Ysleta (YoY, 3-month sums, {pretty(byk['pov']['latest_month']) if 'pov' in byk else ''}): " + " · ".join(parts) + ".")
A("")
ca = data.get("change_attribution")
if ca:
    A(f"## What moved the score ({pretty(ca['from'])} → {pretty(ca['to'])}: {ca['delta_score']:+.1f} pts)")
    moves = sorted(ca["points_by_indicator"].items(), key=lambda kv: kv[1])
    lbl = {d2["key"]: d2["label"] for d2 in data["drivers"]}
    for k, v in moves:
        if abs(v) >= 0.1:
            A(f"- {lbl.get(k, k)}: {v:+.1f} pts")
    A("")
hor_path = os.path.join(BASE, "validation", "horizons.json")
if os.path.exists(hor_path):
    hor = json.load(open(hor_path))
    A("## Outlook (historical frequencies for months in a similar score band, 2003–2025)")
    for key, label in (("payroll_growth_negative", "Payroll growth negative within the horizon"),
                       ("unemployment_+0.5pp", "Unemployment rises ≥0.5pp")):
        cells = []
        for h in ("3m", "6m", "12m"):
            d = hor["horizons"][h][key]
            p, b = d["current_band_p"], d["index_at_65"]["base_rate"]
            cells.append(f"{h}: " + ("—" if p is None else f"{p*100:.0f}% (base {b*100:.0f}%)"))
        A(f"- {label} — " + " · ".join(cells))
    _bandname = {"Normal": "Calm", "Watch": "Near normal", "Elevated": "Above normal"}.get(hor['current']['band'], hor['current']['band'])
    A(f"- Band computed from the as-publishable back-test score ({hor['current']['score']:.0f}, {_bandname} band); "
      "six downturns since 2003 — read as rough odds, not forecasts.")
    A("")
A("## Sectors (6-mo annualized / YoY payroll growth — descriptive only)")
for n, s in sorted(sectors.items(), key=lambda kv: kv[1]["growth6m_ann"]):
    A(f"- {n}: {s['growth6m_ann']:+.1f}% 6-mo ann. · {s['yoy']:+.1f}% YoY ({pretty(s['asof'])})")
A("")
A("## What is moving the score")
up = [d for d in drivers if d["z"] > 0.1][:3]
if up:
    for d in up:
        A(f"- Toward stress: {d['label']} — z {d['z']:+.2f} (latest {d['raw']:+.1f}).")
else:
    A("- No indicator is currently pushing stress meaningfully above its historical norm.")
for d in drivers[-2:]:
    A(f"- Away from stress: {d['label']} — z {d['z']:+.2f} (latest {d['raw']:+.1f}).")
A("")
A("---")
m65 = val["month_level_at_65"]
A("*Methodology and honesty note (v" + data.get("version", "") + "): the score standardizes seven public indicators "
  "(local labor, U.S.–Mexico trade, the peso, El Paso housing market) against their own history since 2000 with expanding "
  "windows — no future data touches any score. Since v5 the dashboard and the back-test use one model definition; the "
  "back-test additionally applies publication lags. Results, 2003–2025: one advance warning (2008) and one detection after "
  "onset (2020) for payroll downturns, no false alarms; for 0.5-point unemployment rises the score is coincident, not leading "
  f"(month-level ROC-AUC {m65['ROC_AUC']:.2f} ≈ chance; {ep1['events_detected']} of {ep1['events']} events detected), and a plain "
  f"local Sahm rule detects more ({sahm1['events_detected']} of {sahm1['events']}) with more false alarms. Ex-COVID, results weaken. "
  "Data are revised vintages (disclosed); weights 40/35/25 and threshold 65 are documented conventions. "
  "Not official statistics or investment advice. Live dashboard: https://claude.ai/code/artifact/abaddafa-f6ba-4f07-9c38-50de4ac39816*")

open(os.path.join(BASE, "borderpulse_brief.md"), "w").write("\n".join(lines) + "\n")
print("\n".join(lines))
