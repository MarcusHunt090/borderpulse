"""
Data manifest: one record per data file with SHA-256, row count, date span, source series
and retrieval provenance. Written to data/MANIFEST.json and embedded in the dashboard's
Data & Methods tab. Re-run after every refresh; the hash is what a replicator checks.

Usage:
    python3 make_manifest.py                       # retrieval note = today's date (FRED current vintage)
    python3 make_manifest.py --retrieved "2026-10-12 (FRED current vintage via .txt)"
    python3 make_manifest.py --bts "2026-10-12 (BTS Socrata API; annual totals cross-checked)"

The retrieval notes are provenance text only; the hashes are the audit trail.
"""
import csv, hashlib, json, os, datetime, argparse

BASE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(BASE, "data")
OUT = os.path.join(DATA, "MANIFEST.json")

SOURCES = {
    "ep_unrate": ("ELPA348UR", "FRED / BLS LAUS", "El Paso MSA unemployment rate, SA (%)"),
    "tx_unrate": ("TXUR", "FRED / BLS LAUS", "Texas unemployment rate, SA (%)"),
    "us_unrate": ("UNRATE", "FRED / BLS CPS", "U.S. unemployment rate, SA (%)"),
    "lc_unrate": ("LASC735UR", "FRED / BLS LAUS", "Las Cruces MSA unemployment rate (smoothed SA) — comparison only"),
    "ep_nonfarm": ("ELPA348NAN", "FRED / BLS CES", "El Paso MSA total nonfarm payrolls, NSA (thousands)"),
    "ep_trade": ("ELPA348TRADN", "FRED / BLS CES", "El Paso trade, transportation & utilities payrolls, NSA (thousands)"),
    "ep_govt": ("ELPA348GOVTN", "FRED / BLS CES", "El Paso government payrolls, NSA (thousands)"),
    "ep_construction": ("ELPA348NRMNN", "FRED / BLS CES", "El Paso mining, logging & construction payrolls, NSA (thousands)"),
    "ep_mfg": ("ELPA348MFGN", "FRED / BLS CES", "El Paso manufacturing payrolls, NSA (thousands)"),
    "ep_eduhealth": ("ELPA348EDUHN", "FRED / BLS CES", "El Paso private education & health payrolls, NSA (thousands)"),
    "ep_leisure": ("ELPA348LEIHN", "FRED / BLS CES", "El Paso leisure & hospitality payrolls, NSA (thousands)"),
    "ep_profbiz": ("ELPA348PBSVN", "FRED / BLS CES", "El Paso professional & business services payrolls, NSA (thousands)"),
    "us_imports_mexico": ("IMPMX", "FRED / Census FT-900", "U.S. goods imports from Mexico, customs basis, NSA ($ millions)"),
    "us_exports_mexico": ("EXPMX", "FRED / Census FT-900", "U.S. goods exports to Mexico, FAS basis, NSA ($ millions)"),
    "peso_usd": ("EXMXUS", "FRED / Federal Reserve H.10", "Mexican pesos per U.S. dollar, monthly average"),
    "ep_active_listings": ("ACTLISCOU21340", "FRED / Realtor.com", "El Paso CBSA active listing count"),
    "ep_days_on_market": ("MEDDAYONMAR21340", "FRED / Realtor.com", "El Paso CBSA median days on market"),
    "mex_manufacturing": ("MEXPRMNTO01IXOBM", "FRED / OECD MEI (discontinued 2024-03)", "Mexico manufacturing production index"),
    "ep_crossings_trucks": ("BTS keg4-3bc2 / Trucks", "BTS Border Crossing/Entry Data",
                            "El Paso port inbound trucks (count) — El Paso port (2402) only; excludes Ysleta from 2020-03"),
    "ep_crossings_pov": ("BTS keg4-3bc2 / Personal Vehicles", "BTS Border Crossing/Entry Data",
                         "El Paso port inbound personal vehicles (count) — El Paso port (2402) only; excludes Ysleta from 2020-03"),
    "ep_crossings_ped": ("BTS keg4-3bc2 / Pedestrians", "BTS Border Crossing/Entry Data",
                         "El Paso port inbound pedestrians (count) — El Paso port (2402) only; excludes Ysleta from 2020-03"),
    "ysleta_crossings_trucks": ("BTS keg4-3bc2 / Ysleta / Trucks", "BTS Border Crossing/Entry Data",
                                "Ysleta port (2401) inbound trucks — separate port from 2020-03-16"),
    "ysleta_crossings_pov": ("BTS keg4-3bc2 / Ysleta / Personal Vehicles", "BTS Border Crossing/Entry Data",
                             "Ysleta port (2401) inbound personal vehicles — separate port from 2020-03-16"),
    "ysleta_crossings_ped": ("BTS keg4-3bc2 / Ysleta / Pedestrians", "BTS Border Crossing/Entry Data",
                             "Ysleta port (2401) inbound pedestrians — separate port from 2020-03-16"),
    "dallas_fed_bci": ("Dallas Fed El Paso BCI", "Federal Reserve Bank of Dallas", "El Paso Business-Cycle Index (benchmark only)"),
}

ap = argparse.ArgumentParser()
ap.add_argument("--retrieved", default=None, help="provenance note for FRED-sourced files")
ap.add_argument("--bts", default=None, help="provenance note for BTS crossings files")
args = ap.parse_args()
today = datetime.date.today().isoformat()
FRED_NOTE = args.retrieved or f"{today} (FRED current vintage)"
BTS_NOTE = args.bts or f"{today} (BTS Socrata API)"
STATIC = {
    "mex_manufacturing": "2026-08-25 (FRED; series discontinued)",
    "pre2015": "2026-08-25 (FRED current vintage, static history 2000-2014)",
}

def sha256(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 16), b""): h.update(chunk)
    return h.hexdigest()

records = []
for sub in ["", "pre2015", "full", "extra"]:
    d = os.path.join(DATA, sub) if sub else DATA
    if not os.path.isdir(d): continue
    for fn in sorted(os.listdir(d)):
        p = os.path.join(d, fn)
        if not (os.path.isfile(p) and fn.endswith(".csv")) or "TEMPLATE" in fn: continue
        rows = [r for r in csv.DictReader(open(p)) if r.get("value", "").strip() not in ("", ".")]
        stem = fn[:-4]; rel = (sub + "/" if sub else "") + stem
        src = SOURCES.get(stem, ("", "", ""))
        if sub == "full":
            retrieved = f"merge of pre2015/ (static) + 2015+ file retrieved {FRED_NOTE.split(' ')[0]}"
        elif sub == "pre2015":
            retrieved = STATIC["pre2015"]
        elif stem in STATIC:
            retrieved = STATIC[stem]
        elif "crossings" in stem:
            retrieved = BTS_NOTE
        else:
            retrieved = FRED_NOTE
        records.append({"file": f"data/{rel}.csv", "sha256": sha256(p), "rows": len(rows),
                        "first": rows[0]["date"] if rows else None, "last": rows[-1]["date"] if rows else None,
                        "series_id": src[0], "source": src[1], "description": src[2], "retrieved": retrieved,
                        "vintage": "latest available (revised) at retrieval; real-time vintages via vintage_audit.py"})
manifest = {"generated": today, "n_files": len(records),
            "note": "Hashes identify the exact inputs behind a published result. Any refresh changes them; compare against the CHANGELOG entry for the release you are replicating.",
            "files": records}
json.dump(manifest, open(OUT, "w"), indent=1)
print(f"manifest: {len(records)} files -> data/MANIFEST.json")
