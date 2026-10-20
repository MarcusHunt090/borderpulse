"""Regression checks for data provenance and the self-contained release artifacts."""
import csv
import hashlib
import json
from pathlib import Path
import re
import tempfile
import unittest
from unittest.mock import patch

import make_manifest
import refresh

BASE = Path(__file__).resolve().parent


class ProvenanceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.file = self.root / "ep_unrate.csv"
        self.file.write_text("date,value\n2020-01-01,4\n")
        manifest = make_manifest.build_manifest(self.root, retrieved="2020-02-01 (verified download)", today="2020-02-01")
        (self.root / "MANIFEST.json").write_text(json.dumps(manifest))

    def test_offline_rebuild_preserves_retrieval(self):
        got = make_manifest.build_manifest(self.root, today="2030-01-01")
        self.assertEqual(got["generated"], "2030-01-01")
        self.assertEqual(got["files"][0]["retrieved"], "2020-02-01 (verified download)")

    def test_changed_local_file_does_not_claim_a_download(self):
        self.file.write_text("date,value\n2020-01-01,5\n")
        got = make_manifest.build_manifest(self.root, today="2030-01-01")
        self.assertTrue(got["files"][0]["retrieved"].startswith("unknown"))

    def test_successful_fetch_can_advance_date_even_if_bytes_unchanged(self):
        got = make_manifest.build_manifest(self.root, today="2030-01-01", fetched=["ep_unrate.csv"])
        self.assertTrue(got["files"][0]["retrieved"].startswith("2030-01-01"))

    def test_failed_optional_fetch_retains_its_previous_date(self):
        extra = self.root / "extra"
        extra.mkdir()
        (extra / "ep_crossings_trucks.csv").write_text(self.file.read_text())
        prior = make_manifest.build_manifest(self.root, bts="2020-02-02 (BTS)")
        (self.root / "MANIFEST.json").write_text(json.dumps(prior))
        got = make_manifest.build_manifest(self.root, today="2030-01-01", fetched=["ep_unrate.csv"])
        self.assertEqual(got["files"][-1]["retrieved"], "2020-02-02 (BTS)")

    def test_refresh_reads_current_provenance_and_embeds_current_brief(self):
        state = {"provenance": "old", "brief": "old"}
        def run(command, **kwargs):
            if Path(command[1]).name == "make_manifest.py":
                state["provenance"] = "current"
        def call(command, **kwargs):
            name = Path(command[1]).name
            if name == "pipeline.py":
                self.assertEqual(state["provenance"], "current")
            if name == "make_brief.py":
                state["brief"] = "current"
            if name == "build.py":
                self.assertEqual(state["brief"], "current")
            return 0
        with patch("sys.argv", ["refresh.py", "--no-fetch"]), patch.object(refresh.subprocess,"run",side_effect=run), patch.object(refresh.subprocess,"call",side_effect=call), patch.dict("sys.modules", {"playwright.sync_api": None}):
            refresh.main()


class ArtifactTests(unittest.TestCase):
    def test_embedded_outputs_match_the_current_snapshot(self):
        page = (BASE / "borderpulse_dashboard.html").read_text()
        for variable, path in [("DATA", "borderpulse_output.json"), ("MANIFEST", "data/MANIFEST.json"), ("BRIEF_MD", "borderpulse_brief.md"), ("TECHNOTE_MD", "technical_note.md")]:
            with self.subTest(variable=variable):
                match = re.search(r"^const " + variable + r" = (.*);$", page, re.M)
                self.assertIsNotNone(match)
                embedded = json.loads(match.group(1))
                actual = (BASE / path).read_text()
                self.assertEqual(embedded, json.loads(actual) if path.endswith(".json") else actual)
        self.assertNotRegex(page, r"/\*__[A-Z_]+__\*/")
        self.assertIn((BASE / "explorer.js").read_text(), page)
        self.assertEqual(page, (BASE / "docs/index.html").read_text())

    def test_manifest_matches_each_input_file(self):
        manifest = json.loads((BASE / "data/MANIFEST.json").read_text())
        for record in manifest["files"]:
            with self.subTest(file=record["file"]):
                path = BASE / record["file"]
                self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), record["sha256"])
                with path.open() as stream:
                    rows = [r for r in csv.DictReader(stream) if r["value"].strip() not in ("", ".")]
                self.assertEqual(len(rows), record["rows"])


if __name__ == "__main__":
    unittest.main()
