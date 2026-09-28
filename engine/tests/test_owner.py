"""Owner detection, which laws bind whom, and the run ledger. Run: python3 -m unittest discover -s engine/tests"""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ENGINE = Path(__file__).resolve().parent.parent
REGISTRY = ENGINE.parent / "data" / "registry"
sys.path.insert(0, str(ENGINE))

import identify  # noqa: E402
import jurisdictions as J  # noqa: E402
import ledger  # noqa: E402

REG = J.load(REGISTRY)


class WhoIsBound(unittest.TestCase):
    def test_a_texas_county_is_bound_by_title_ii_not_the_state_agency_rule(self):
        b, c, r = J.applicable(REG, "US", "county", "TX", "Travis County")
        self.assertEqual(b, ["us-ada-title-ii"])
        self.assertIn("us-tx", r)

    def test_a_texas_state_agency_is_bound_by_both(self):
        b, _, _ = J.applicable(REG, "US", "state-agency", "TX")
        self.assertEqual(sorted(b), ["us-ada-title-ii", "us-tx"])

    def test_city_policy_binds_only_its_own_city(self):
        self.assertIn("us-local-austin", J.applicable(REG, "US", "city", "TX", "City of Austin")[0])
        self.assertNotIn("us-local-austin", J.applicable(REG, "US", "city", "TX", "City of Dallas")[0])
        self.assertIn("us-local-nyc", J.applicable(REG, "US", "city", "NY", "City of New York")[0])

    def test_conditional_coverage_is_not_binding(self):
        b, c, _ = J.applicable(REG, "US", "city", "NY", "Buffalo")
        self.assertNotIn("us-ny", b)
        self.assertIn("us-ny", c)

    def test_federal_agency_gets_section_508(self):
        self.assertEqual(J.applicable(REG, "US", "federal-agency")[0], ["us-federal-508"])

    def test_eu_member_public_body_gets_the_directive(self):
        b, _, _ = J.applicable(REG, "IE", "county")
        self.assertEqual(sorted(b), ["eu-wad", "ie"])

    def test_place_names_reduce_to_the_same_core(self):
        self.assertEqual(J.core("City of New York"), J.core("New York City"))
        self.assertEqual(J.core("City and County of Denver"), "denver")


class Identify(unittest.TestCase):
    def test_county_with_state_code_in_domain(self):
        g = identify.guess("https://www.traviscountytx.gov/", "<title>Travis County Homepage | Travis County, Texas</title>")
        self.assertEqual((g["entity"], g["country"], g["region"], g["place"]), ("county", "US", "TX", "Travis County"))

    def test_state_name_in_domain_is_not_misread_as_a_territory_code(self):
        # 'austintexAS.gov' once matched American Samoa (AS)
        g = identify.guess("https://www.austintexas.gov/", "<title>City of Austin | AustinTexas.gov</title>")
        self.assertEqual((g["entity"], g["region"]), ("city", "TX"))

    def test_non_us_government_domain(self):
        g = identify.guess("https://www.gov.ie/", "<title>gov.ie</title>")
        self.assertEqual((g["country"], g["entity"]), ("IE", "public-sector-body"))


class Ledger(unittest.TestCase):
    def run_cli(self, *args, home):
        out = subprocess.run([sys.executable, str(ENGINE / "ledger.py"), *args], capture_output=True, text=True,
                             env={"ACCESS_ATLAS_HOME": home, "PATH": "/usr/bin:/bin"}, check=True)
        return out.stdout.strip()

    def test_decisions_are_recorded_with_who_and_why_and_logged(self):
        home = tempfile.mkdtemp()
        run = self.run_cli("open", "https://example.gov/", home=home)
        self.run_cli("decide", run, "entity", "county", "--why", "footer says County", "--by", "user", home=home)
        r = json.loads((Path(run) / "run.json").read_text())
        self.assertEqual(r["decisions"]["entity"]["value"], "county")
        self.assertEqual(r["decisions"]["entity"]["by"], "user")
        events = [json.loads(x) for x in (Path(run) / "log.jsonl").read_text().splitlines()]
        self.assertEqual([e["step"] for e in events], ["open", "decide"])

    def test_compare_reports_fixed_new_and_still_failing(self):
        home = Path(tempfile.mkdtemp())
        old, new = home / "a", home / "b"
        for d in (old, new):
            d.mkdir()
            (d / "run.json").write_text(json.dumps({"decisions": {"scope": {"value": "quick"}}, "steps": {}}))
        f = lambda rule, sev="serious": {"id": "X", "rule": rule, "source": "automated", "severity": sev, "title": rule, "scs": ["1.1.1"], "where": ["u"]}  # noqa: E731
        (old / "x.findings.json").write_text(json.dumps({"score": 70, "findings": [f("image-alt"), f("label")], "pages": [{"url": "u"}]}))
        (new / "x.findings.json").write_text(json.dumps({"score": 85, "findings": [f("label"), f("list")], "pages": [{"url": "u"}]}))
        d = ledger.compare(old, new)
        self.assertEqual([x["title"] for x in d["fixed"]], ["image-alt"])
        self.assertEqual([x["title"] for x in d["new"]], ["list"])
        self.assertEqual([x["title"] for x in d["still"]], ["label"])
        self.assertFalse(d["scope_changed"])


if __name__ == "__main__":
    unittest.main()
