"""
rebuild_data_from_tidy.py — turn borderpulse_tidy.csv (series,date,value) back into the
per-series CSVs under data/ (and data/pre2015/ as the pre-2015 rows of data/full/),
then verify every file against data/MANIFEST.json sha256 hashes.

Usage: python3 tools/rebuild_data_from_tidy.py <repo root>
"""
import csv, hashlib, json, os, sys
from collections import OrderedDict

root = sys.argv[1] if len(sys.argv) > 1 else "."
tidy = os.path.join(root, "borderpulse_tidy.csv")
data = os.path.join(root, "data")

series = OrderedDict()
with open(tidy, newline="") as f:
    for row in csv.DictReader(f):
        series.setdefault(row["series"], []).append((row["date"], row["value"]))

def write(path, rows):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", newline="") as f:
        f.write("date,value\n")
        for d, v in rows:
            f.write(f"{d},{v}\n")

for name, rows in series.items():
    write(os.path.join(data, name + ".csv"), rows)

# pre2015/ = rows of full/ before 2015-01
for name in ["ep_unrate", "ep_nonfarm", "us_imports_mexico", "us_exports_mexico", "peso_usd"]:
    full = series.get("full/" + name, [])
    write(os.path.join(data, "pre2015", name + ".csv"), [(d, v) for d, v in full if d < "2015-01"])

# verify against manifest
mf = os.path.join(data, "MANIFEST.json")
ok = bad = 0
if os.path.exists(mf):
    for entry in json.load(open(mf))["files"]:
        p = os.path.join(root, entry["file"])
        if not os.path.exists(p):
            print("MISSING", entry["file"]); bad += 1; continue
        h = hashlib.sha256(open(p, "rb").read()).hexdigest()
        if h == entry["sha256"]:
            ok += 1
        else:
            print("HASH MISMATCH", entry["file"]); bad += 1
print(f"manifest check: {ok} ok, {bad} bad")
