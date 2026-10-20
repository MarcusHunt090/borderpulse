"""
build.py — assemble the dashboard.

Reads dashboard_body.html (the page with /*__X__*/ placeholders) and fills every placeholder
with the pipeline's outputs, producing:
  artifact.html               the body fragment that is published as the claude.ai Artifact
  borderpulse_dashboard.html  a standalone page (same content with a <html> skeleton) for GitHub Pages
                              or opening locally in a browser
Fails loudly if any placeholder is left unfilled.
"""
import json, os, csv
base = os.path.dirname(os.path.abspath(__file__))
data = json.load(open(os.path.join(base, "borderpulse_output.json")))
body = open(os.path.join(base, "dashboard_body.html")).read()
body = body.replace("/*__EXPLORER_JS__*/", open(os.path.join(base, "explorer.js")).read())
body = body.replace("/*__DATA__*/", json.dumps(data, separators=(",", ":")))

# validation payload (from backtest.py outputs)
vdir = os.path.join(base, "validation")
metrics = json.load(open(os.path.join(vdir, "backtest_metrics.json")))
timeline = {}
for r in csv.DictReader(open(os.path.join(vdir, "backtest_monthly_results.csv"))):
    timeline[r["month"]] = float(r["score"])
episodes = list(csv.DictReader(open(os.path.join(vdir, "backtest_alert_episodes.csv"))))
validation = {"summary": metrics, "timeline": timeline, "episodes": episodes}
body = body.replace("/*__VALIDATION__*/", json.dumps(validation, separators=(",", ":")))
# v4.1: border_test.json (pre-registered trade-vs-crossings border-layer comparison); timelines are not embedded
_bt_path = os.path.join(vdir, "border_test.json")
if os.path.exists(_bt_path):
    _bt = json.load(open(_bt_path)); _bt.pop("timeline", None); _bt.pop("prespecification", None)
    body = body.replace("/*__BORDERTEST__*/", json.dumps(_bt, separators=(",", ":")))
else:
    body = body.replace("/*__BORDERTEST__*/", "null")
# v5: onset evaluation (warning before a downturn vs detection after it starts)
_on_path = os.path.join(vdir, "onset_eval.json")
if os.path.exists(_on_path):
    _on = json.load(open(_on_path)); _on.pop("spec", None)
    body = body.replace("/*__ONSET__*/", json.dumps(_on, separators=(",", ":")))
else:
    body = body.replace("/*__ONSET__*/", "null")
for ph, fname in (("/*__HORIZONS__*/", "horizons.json"), ("/*__LEADLAG__*/", "leadlag.json"),
                  ("/*__BENCH__*/", "benchmarks.json"), ("/*__LAB__*/", "lab_data.json"),
                  ("/*__INFER__*/", "inference.json"), ("/*__VINTAGE__*/", "vintage_audit.json")):
    p = os.path.join(vdir, fname)
    body = body.replace(ph, json.dumps(json.load(open(p)), separators=(",", ":")) if os.path.exists(p) else "null")
# v3: embed downloadable datasets (tidy long-format CSV + backtest monthly table)
tidy_rows = ["series,date,value"]
droot = os.path.join(base, "data")
for sub in ["", "full", "extra"]:
    d = os.path.join(droot, sub) if sub else droot
    for fn in sorted(os.listdir(d)):
        p = os.path.join(d, fn)
        if not (os.path.isfile(p) and fn.endswith(".csv")) or "TEMPLATE" in fn:
            continue
        name = (sub + "/" if sub else "") + fn[:-4]
        for r in csv.DictReader(open(p)):
            v = r.get("value", "").strip()
            if v and v != ".":
                tidy_rows.append(f"{name},{r['date']},{v}")
body = body.replace("/*__TIDY__*/", json.dumps("\n".join(tidy_rows)))
mp = os.path.join(vdir, "backtest_monthly_results.csv")
body = body.replace("/*__MONTHLY__*/", json.dumps(open(mp).read() if os.path.exists(mp) else ""))
# v3.1: embed the current monthly brief so the dashboard can offer it as a download
bp = os.path.join(base, "borderpulse_brief.md")
body = body.replace("/*__BRIEF__*/", json.dumps(open(bp).read() if os.path.exists(bp) else ""))
# v4: data manifest + technical note (markdown) for the Data & Methods tab
mf = os.path.join(base, "data", "MANIFEST.json")
body = body.replace("/*__MANIFEST__*/", json.dumps(json.load(open(mf)), separators=(",", ":")) if os.path.exists(mf) else "null")
tn = os.path.join(base, "technical_note.md")
body = body.replace("/*__TECHNOTE__*/", json.dumps(open(tn).read() if os.path.exists(tn) else ""))

left = [ph for ph in ("__EXPLORER_JS__", "__DATA__", "__VALIDATION__", "__BORDERTEST__", "__ONSET__", "__HORIZONS__", "__LEADLAG__", "__BENCH__", "__LAB__",
                      "__INFER__", "__VINTAGE__", "__TIDY__", "__MONTHLY__", "__BRIEF__", "__MANIFEST__", "__TECHNOTE__") if "/*" + ph + "*/" in body]
if left:
    raise SystemExit("unfilled placeholders: " + ", ".join(left))
open(os.path.join(base, "artifact.html"), "w").write(body)
standalone = ('<!DOCTYPE html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n'
              '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
              '</head>\n<body>\n' + body + '\n</body>\n</html>\n')
open(os.path.join(base, "borderpulse_dashboard.html"), "w").write(standalone)
# GitHub Pages serves docs/index.html
os.makedirs(os.path.join(base, "docs"), exist_ok=True)
open(os.path.join(base, "docs", "index.html"), "w").write(standalone)
print("built", len(body), "bytes body -> artifact.html, borderpulse_dashboard.html, docs/index.html")
