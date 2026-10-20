"""
BorderPulse monthly refresh — run from your own machine (needs internet).

Re-pulls every FRED series, rebuilds the merged 2000->present files, then
reruns the score, the validation, and the dashboard build:

    python3 refresh.py            # fetch + rebuild everything
    python3 refresh.py --no-fetch # just rerun pipeline/backtest/build

Note: inside the Claude cloud sandbox direct downloads are blocked; there the
refresh is done by Claude via its web tools instead (see RUNBOOK.md).
"""
import argparse, csv, io, os, subprocess, sys, urllib.request

BASE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(BASE, "data")

# series -> (target csv relative to data/, start date)
SERIES = {
    "ELPA348UR":       ("ep_unrate.csv",          "2015-01-01"),
    "TXUR":            ("tx_unrate.csv",          "2015-01-01"),
    "UNRATE":          ("us_unrate.csv",          "2015-01-01"),
    "LASC735UR":       ("lc_unrate.csv",          "2015-01-01"),   # v4.1: Las Cruces MSA — comparison only
    "ELPA348NAN":      ("ep_nonfarm.csv",         "2015-01-01"),
    "ELPA348TRADN":    ("ep_trade.csv",           "2015-01-01"),
    "ELPA348GOVTN":    ("ep_govt.csv",            "2015-01-01"),
    "ELPA348NRMNN":    ("ep_construction.csv",    "2015-01-01"),
    "ELPA348MFGN":     ("ep_mfg.csv",             "2015-01-01"),
    "ELPA348EDUHN":    ("ep_eduhealth.csv",       "2015-01-01"),
    "ELPA348LEIHN":    ("ep_leisure.csv",         "2015-01-01"),
    "ELPA348PBSVN":    ("ep_profbiz.csv",         "2015-01-01"),
    "IMPMX":           ("us_imports_mexico.csv",  "2015-01-01"),
    "EXPMX":           ("us_exports_mexico.csv",  "2015-01-01"),
    "EXMXUS":          ("peso_usd.csv",           "2015-01-01"),
    "ACTLISCOU21340":  ("ep_active_listings.csv", "2016-07-01"),
    "MEDDAYONMAR21340":("ep_days_on_market.csv",  "2016-07-01"),
}
FULL_MERGE = ["ep_unrate", "ep_nonfarm", "us_imports_mexico", "us_exports_mexico", "peso_usd"]

def fetch(series_id, start):
    url = f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={series_id}&cosd={start}"
    with urllib.request.urlopen(url, timeout=60) as r:
        text = r.read().decode()
    rows = []
    for rec in csv.reader(io.StringIO(text)):
        if len(rec) == 2 and rec[0][:2] in ("19", "20") and rec[1] not in (".", ""):
            rows.append((rec[0], rec[1]))
    if not rows:
        raise RuntimeError(f"no rows for {series_id}")
    return rows

# weekly FRED series aggregated to monthly averages -> data/extra/
WEEKLY_EXTRA = {
    "TXICLAIMS":     "extra/tx_initial_claims.csv",       # TX initial UI claims
    "BUSAPPWNSATX":  "extra/tx_business_applications.csv" # TX business applications
}

def fetch_weekly_monthly(series_id, start="2015-01-01"):
    rows = fetch(series_id, start)
    monthly = {}
    for d, v in rows:
        monthly.setdefault(d[:7], []).append(float(v))
    return [(f"{m}-01", round(sum(vs) / len(vs), 1)) for m, vs in sorted(monthly.items())]

# ---- v3: BTS El Paso port crossings (Socrata) -> data/extra/ ----
BTS_MEASURES = {"Trucks": "crossings_trucks.csv",
                "Personal Vehicles": "crossings_pov.csv",
                "Pedestrians": "crossings_ped.csv"}
# v5: Ysleta became its own port (2401) on 2020-03-16; the dashboard combines El Paso + Ysleta.
BTS_PORTS = {"El Paso": "extra/ep_", "Ysleta": "extra/ysleta_"}

def fetch_bts_crossings():
    import json as _json, urllib.parse
    for port, prefix in BTS_PORTS.items():
      for measure, suffix in BTS_MEASURES.items():
        rel = prefix + suffix
        q = urllib.parse.urlencode({"port_name": port, "measure": measure,
                                    "$select": "date,value", "$order": "date", "$limit": "5000"})
        url = f"https://data.bts.gov/resource/keg4-3bc2.json?{q}"
        with urllib.request.urlopen(url, timeout=60) as r:
            recs = _json.load(r)
        rows = [(rec["date"][:7] + "-01", rec["value"]) for rec in recs if rec.get("value")]
        if not rows:
            print(f"WARN: BTS {port} {measure} returned no rows; keeping existing file"); continue
        with open(os.path.join(DATA, rel), "w") as f:
            f.write("date,value\n")
            for d, v in rows:
                f.write(f"{d},{v}\n")
        print(f"fetched BTS {port:8s} {measure:18s} -> {rel} ({len(rows)} rows, last {rows[-1][0][:7]})")

# ---- v3: Dallas Fed El Paso Business-Cycle Index (xlsx) -> data/extra/dallas_fed_bci.csv ----
BCI_URL = "https://www.dallasfed.org/~/media/documents/research/econdata/coini/elpcoini.xlsx"

def fetch_dallas_fed_bci():
    """Benchmark series only — never a score input. Requires pandas+openpyxl locally."""
    try:
        import pandas as pd
        raw = pd.read_excel(BCI_URL)
        dcol = raw.columns[0]
        vcol = next(c for c in raw.columns[1:] if pd.api.types.is_numeric_dtype(raw[c]))
        df = raw[[dcol, vcol]].dropna()
        df[dcol] = pd.to_datetime(df[dcol]).dt.strftime("%Y-%m-01")
        p = os.path.join(DATA, "extra", "dallas_fed_bci.csv")
        df.rename(columns={dcol: "date", vcol: "value"}).to_csv(p, index=False)
        print(f"fetched Dallas Fed BCI -> extra/dallas_fed_bci.csv ({len(df)} rows) — VERIFY the column mapping once by eye")
    except Exception as e:
        print(f"WARN: Dallas Fed BCI fetch failed ({e}); benchmark stays unavailable")

# NOTE (v3): Juárez IMMEX manufacturing employment (INEGI, monthly, 2007->) is the
# planned successor to the discontinued FRED Mexico-manufacturing series; ingest is
# manual for now (INEGI / INDEX Juárez publish monthly tables) -> data/extra/juarez_immex.csv.
# NOTE (v4.1): a harmonized five-sector El Paso–Juárez employment series from the regional
# border-economy research group is preferred over IMMEX if they share it or publish it.

STEPS = ("pipeline.py", "backtest.py", "test_backtest.py", "benchmarks.py",
         "leadlag.py", "horizons.py", "inference.py", "border_test.py", "onset_eval.py",
         "vintage_audit.py", "test_vintage_audit.py",
         "make_manifest.py", "make_technote.py", "build.py", "make_brief.py")

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-fetch", action="store_true", help="skip downloads; rerun the pipeline on the data already in data/")
    ap.add_argument("--skip-inference", action="store_true", help="skip inference.py (the slow bootstrap step) for a quick rebuild")
    args = ap.parse_args()

    if not args.no_fetch:
        for sid, (fname, start) in SERIES.items():
            rows = fetch(sid, start)
            with open(os.path.join(DATA, fname), "w") as f:
                f.write("date,value\n")
                for d, v in rows:
                    f.write(f"{d},{v}\n")
            print(f"fetched {sid:16s} -> {fname}  ({len(rows)} rows, last {rows[-1][0][:7]})")
        for sid, rel in WEEKLY_EXTRA.items():
            try:
                rows = fetch_weekly_monthly(sid)
                # drop the current (incomplete) month
                rows = rows[:-1]
                with open(os.path.join(DATA, rel), "w") as f:
                    f.write("date,value\n")
                    for d, v in rows:
                        f.write(f"{d},{v}\n")
                print(f"fetched {sid:16s} -> {rel}  (monthly avg, {len(rows)} rows)")
            except Exception as e:
                print(f"WARN: {sid} failed ({e}); watch slot stays inactive")
        try:
            fetch_bts_crossings()
        except Exception as e:
            print(f"WARN: BTS crossings fetch failed ({e}); existing files kept")
        fetch_dallas_fed_bci()
        # merge pre-2015 history (static, shipped with the repo) with fresh 2015+
        os.makedirs(os.path.join(DATA, "full"), exist_ok=True)
        for name in FULL_MERGE:
            merged = {}
            for src in (os.path.join(DATA, "pre2015", f"{name}.csv"),
                        os.path.join(DATA, f"{name}.csv")):
                for r in csv.DictReader(open(src)):
                    if r["value"].strip() and r["value"].strip() != ".":
                        merged[r["date"]] = r["value"].strip()
            with open(os.path.join(DATA, "full", f"{name}.csv"), "w") as f:
                f.write("date,value\n")
                for d in sorted(merged):
                    f.write(f"{d},{merged[d]}\n")
            print(f"merged full/{name}.csv ({len(merged)} rows)")

    for step in STEPS:
        if args.skip_inference and step == "inference.py":
            print("\n== inference.py == (skipped)"); continue
        print(f"\n== {step} ==")
        rc = subprocess.call([sys.executable, os.path.join(BASE, step)], cwd=BASE)
        if rc != 0:
            sys.exit(f"{step} failed (exit {rc})")
    # technical note PDF (optional: needs `pip install playwright && playwright install chromium`)
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as pw:
            b = pw.chromium.launch(); pg = b.new_page()
            pg.goto("file://" + os.path.join(BASE, "technical_note.html"))
            pg.pdf(path=os.path.join(BASE, "technical_note.pdf"), format="A4", print_background=True,
                   margin={"top": "16mm", "bottom": "16mm", "left": "15mm", "right": "15mm"})
            b.close()
        print("technical_note.pdf rendered")
    except Exception as e:
        print(f"note: technical_note.pdf not rendered ({e}); open technical_note.html and print to PDF")
    print("\nRefresh complete: borderpulse_dashboard.html, docs/index.html, artifact.html, validation/, "
          "technical_note.{md,html}, data/MANIFEST.json and borderpulse_brief.md are up to date.")

if __name__ == "__main__":
    main()
