"""Unit tests for the Access Atlas mapping, scoring and report logic. Run: python3 -m unittest discover skills/access-atlas/tests"""
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
SCRIPTS = HERE.parent
os.environ["ACCESS_ATLAS_REGISTRY"] = str(HERE / "fixtures" / "registry")
sys.path.insert(0, str(SCRIPTS))

import jurisdictions  # noqa: E402
import render  # noqa: E402


class Mapping(unittest.TestCase):
    def test_axe_tags_become_criteria(self):
        self.assertEqual(render.tag_to_sc("wcag111"), "1.1.1")
        self.assertEqual(render.tag_to_sc("wcag1410"), "1.4.10")
        self.assertEqual(render.tag_to_sc("wcag2411"), "2.4.11")
        self.assertIsNone(render.tag_to_sc("wcag21aa"))  # a level tag, not a criterion

    def test_standard_strings_map_to_wcag_versions(self):
        self.assertEqual(jurisdictions.wcag_target("WCAG 2.1 AA")[:2], ("2.1", "AA"))
        self.assertEqual(jurisdictions.wcag_target("Section 508")[:2], ("2.0", "AA"))
        self.assertEqual(jurisdictions.wcag_target("EN 301 549 V3.2.1")[:2], ("2.1", "AA"))
        self.assertFalse(jurisdictions.wcag_target("eMAG")[2])  # unknown is flagged, not guessed silently

    def test_scope_respects_version_and_obsolete_parsing(self):
        self.assertTrue(render.in_scope("1.4.10", "2.1", "AA"))
        self.assertFalse(render.in_scope("1.4.10", "2.0", "AA"))  # reflow is a 2.1 criterion
        self.assertFalse(render.in_scope("2.5.8", "2.1", "AA"))
        self.assertTrue(render.in_scope("4.1.1", "2.1", "AA"))
        self.assertFalse(render.in_scope("4.1.1", "2.2", "AA"))  # obsolete in 2.2

    def test_resolve_pulls_in_the_federal_floor(self):
        reg = jurisdictions.load()
        out, missing = jurisdictions.resolve(["us-xx"], reg)
        self.assertEqual(out, ["us-xx", "us-ada-title-ii"])
        self.assertEqual(missing, [])
        self.assertEqual(jurisdictions.resolve(["nope"], reg)[1], ["nope"])


class Report(unittest.TestCase):
    def render(self, juris):
        d = tempfile.mkdtemp()
        out = Path(d) / "r.html"
        subprocess.run([sys.executable, str(SCRIPTS / "render.py"), "--jurisdictions", juris, "--scan", str(HERE / "fixtures" / "scan.json"),
                        "--org", "Example", "--product", "example.gov", "--out", str(out)], check=True, capture_output=True,
                       env={**os.environ})
        return out, json.loads(out.with_name("r.findings.json").read_text())

    def test_legal_vs_best_practice(self):
        _, f = self.render("us-xx")
        by_rule = {x["rule"]: x for x in f["findings"]}
        # 1.1.1 is required by the 508 state and by Title II
        self.assertEqual(by_rule["image-alt"]["required_by"], ["us-xx", "us-ada-title-ii"])
        # 1.4.10 reflow: WCAG 2.1 only, so Title II requires it and the 2.0 state does not
        self.assertEqual(by_rule["reflow-320"]["required_by"], ["us-ada-title-ii"])
        # 2.5.8 is WCAG 2.2: best practice for these two
        self.assertEqual(by_rule["target-size"]["required_by"], [])

    def test_a_22_jurisdiction_makes_target_size_legal(self):
        _, f = self.render("xx-22")
        by_rule = {x["rule"]: x for x in f["findings"]}
        self.assertEqual(by_rule["target-size"]["required_by"], ["xx-22"])

    def test_untested_is_never_reported_as_pass(self):
        _, f = self.render("us-xx")
        cov = f["coverage"]
        self.assertEqual(cov["1.2.2"], "untested")  # captions: manual only
        self.assertEqual(cov["1.1.1"], "fail")
        self.assertNotIn("pass", cov.values())  # nothing manual was recorded

    def test_disk_copy_is_a_full_document_and_artifact_copy_is_not(self):
        out, _ = self.render("us-xx")
        self.assertTrue(out.read_text().startswith("<!doctype html>\n<html lang=\"en\">"))
        self.assertTrue(out.with_name("r.artifact.html").read_text().startswith("<title>"))


    def test_score_and_grade(self):
        _, f = self.render("us-xx")
        # home: critical 15 + serious 8 + reflow serious 8 = 69; /pay: 100 → mean 84.5 → 84 (B)
        self.assertEqual(f["score"], 84)
        self.assertEqual(f["grade"], "B")
        self.assertEqual({p["url"]: p["score"] for p in f["pages"]}, {"https://example.gov/": 69, "https://example.gov/pay": 100})

    def test_fix_prompt_lists_every_actionable_finding(self):
        out, f = self.render("us-xx")
        prompt = out.with_name("r.fix-prompt.md").read_text()
        for x in f["findings"]:
            if x["severity"] != "review":
                self.assertIn(x["id"], prompt)
        self.assertIn("WCAG 2.1 Level AA", prompt)
        self.assertIn("Do not add an accessibility overlay", prompt)
        self.assertIn("Copy prompt", out.read_text())


if __name__ == "__main__":
    unittest.main()
