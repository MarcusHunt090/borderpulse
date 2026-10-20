"""
Data manifest: one record per data file with SHA-256, row count, date span, source series
and retrieval provenance. Written to data/MANIFEST.json and embedded in the dashboard's
Data & Methods tab. Re-run after every refresh; the hash is what a replicator checks.

Usage:
    python3 make_manifest.py                       # preserve provenance for unchanged files
    python3 make_manifest.py --retrieved "2026-10-12 (FRED current vintage via .txt)"
    python3 make_manifest.py --bts "2026-10-12 (BTS Socrata API; annual totals cross-checked)"

Only a successful fetch or an explicit provenance note may advance a retrieval date.
Changed local files without a provenance note are marked unknown.
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

def sha256(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 16), b""): h.update(chunk)
    return h.hexdigest()

def build_manifest(data_dir=DATA, *, retrieved=None, bts=None, fetched=(), today=None):
    today = today or datetime.date.today().isoformat()
    prior_path = os.path.join(data_dir, "MANIFEST.json")
    if os.path.exists(prior_path):
        with open(prior_path) as f:
            prior = {r["file"]: r for r in json.load(f).get("files", [])}
    else:
        prior = {}
    records, by_file = [], {}
    for sub in ["", "pre2015", "full", "extra"]:
        directory = os.path.join(data_dir, sub)
        if not os.path.isdir(directory):
            continue
        for fn in sorted(os.listdir(directory)):
            path = os.path.join(directory, fn)
            if not (os.path.isfile(path) and fn.endswith(".csv")) or "TEMPLATE" in fn:
                continue
            with open(path) as f:
                rows = [r for r in csv.DictReader(f) if r.get("value", "").strip() not in ("", ".")]
            rows.sort(key=lambda r: r["date"])
            stem = fn[:-4]
            relative = (sub + "/" if sub else "") + fn
            file = "data/" + relative
            digest = sha256(path)
            old = prior.get(file, {})
            source = SOURCES.get(stem, ("", "", ""))
            explicit = bts if "crossings" in stem else retrieved
            if sub == "full":
                # A merged file has two source vintages, rather than a new retrieval.
                parent = by_file.get("data/" + fn, {})
                history = by_file.get("data/pre2015/" + fn, {})
                if digest == old.get("sha256") and not explicit and fn not in fetched:
                    note = old.get("retrieved", "unknown")
                else:
                    note = "merge of pre2015/ (" + history.get("retrieved", "unknown") + ") + 2015+ (" + parent.get("retrieved", "unknown") + ")"
            elif explicit and sub != "pre2015":
                note = explicit
            elif relative in fetched:
                provider = "BTS Socrata API" if "crossings" in stem else (source[1] or "source")
                note = f"{today} ({provider}; successful fetch)"
            elif digest == old.get("sha256"):
                note = old.get("retrieved", "unknown")
            else:
                note = "unknown (local input changed; record retrieval provenance before publishing)"
            record = {"file": file, "sha256": digest, "rows": len(rows),
                      "first": rows[0]["date"] if rows else None, "last": rows[-1]["date"] if rows else None,
                      "series_id": source[0], "source": source[1], "description": source[2], "retrieved": note,
                      "vintage": "latest available (revised) at retrieval; real-time vintages via vintage_audit.py"}
            records.append(record)
            by_file[file] = record
    return {"generated": today, "n_files": len(records),
            "note": "Hashes identify the exact inputs behind a published result. Retrieval dates are preserved for unchanged files; an offline rebuild is not a data refresh.",
            "files": records}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--retrieved", help="explicit provenance note for FRED-sourced files")
    ap.add_argument("--bts", help="explicit provenance note for BTS crossings files")
    ap.add_argument("--fetched", action="append", default=[], help="successfully fetched path, relative to data/")
    args = ap.parse_args()
    manifest = build_manifest(retrieved=args.retrieved, bts=args.bts, fetched=args.fetched)
    with open(OUT, "w") as f:
        json.dump(manifest, f, indent=1)
    print(f"manifest: {manifest['n_files']} files -> data/MANIFEST.json")


if __name__ == "__main__":
    main()
