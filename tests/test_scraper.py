"""Tests for mlb.scraper.BaseballReferenceScraper — HTML parsing + sabermetrics.

Network fetches are stubbed, so these exercise the table extraction, derived
metric math, and CSV/JSON output without hitting baseball-reference.com.
"""

import csv
import json
import tempfile
import unittest
from pathlib import Path

from mlb.scraper import BaseballReferenceScraper

BATTING_HTML = """
<html><body>
<table id="teams_standard_batting">
<tr><th scope="col">Team</th><th scope="col">G</th><th scope="col">AB</th>
<th scope="col">R</th><th scope="col">H</th><th scope="col">HR</th>
<th scope="col">SO</th><th scope="col">BA</th><th scope="col">OBP</th>
<th scope="col">SLG</th></tr>
<tr><td>Boston Red Sox</td><td>50</td><td>1700</td><td>250</td><td>450</td>
<td>60</td><td>400</td><td>0.265</td><td>0.330</td><td>0.430</td></tr>
</table>
</body></html>
"""


class ExtractTableTests(unittest.TestCase):
    def setUp(self):
        self.scraper = BaseballReferenceScraper()

    def test_extracts_rows_with_headers(self):
        rows = self.scraper.extract_table_data(BATTING_HTML, "teams_standard_batting")
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["Team"], "Boston Red Sox")
        self.assertEqual(rows[0]["HR"], "60")

    def test_missing_table_returns_empty(self):
        self.assertEqual(self.scraper.extract_table_data(BATTING_HTML, "nope"), [])


class BattingStatsTests(unittest.TestCase):
    def setUp(self):
        self.scraper = BaseballReferenceScraper()
        self.scraper.fetch_url = lambda url: BATTING_HTML  # stub network

    def test_parses_team_and_derived_iso(self):
        stats = self.scraper.get_team_batting_stats(2026)
        team = stats["Boston Red Sox"]
        self.assertEqual(team["home_runs"], 60)
        self.assertAlmostEqual(team["iso"], 0.430 - 0.265, places=6)
        self.assertIn("babip", team)

    def test_empty_html_yields_empty(self):
        self.scraper.fetch_url = lambda url: None
        self.assertEqual(self.scraper.get_team_batting_stats(2026), {})


class NumericHelperTests(unittest.TestCase):
    def test_to_num(self):
        self.assertEqual(BaseballReferenceScraper._to_num("3.5"), 3.5)
        self.assertEqual(BaseballReferenceScraper._to_num(""), 0.0)
        self.assertEqual(BaseballReferenceScraper._to_num("abc"), 0.0)
        self.assertEqual(BaseballReferenceScraper._to_num("x", default=-1), -1)

    def test_safe_div(self):
        self.assertEqual(BaseballReferenceScraper._safe_div(10, 2), 5)
        self.assertEqual(BaseballReferenceScraper._safe_div(10, 0), 0.0)
        self.assertEqual(BaseballReferenceScraper._safe_div(10, 0, default=-1), -1)

    def test_calc_babip(self):
        data = {"hits": 450, "home_runs": 60, "at_bats": 1700, "strikeouts": 400}
        expected = (450 - 60) / (1700 - 400 - 60 + 0.1)
        self.assertAlmostEqual(BaseballReferenceScraper._calc_babip(data), expected)

    def test_calc_fip(self):
        data = {"home_runs_allowed": 50, "walks": 400, "strikeouts": 900,
                "innings_pitched": 450}
        expected = ((13 * 50) + (3 * 400) - (2 * 900)) / 450 + 3.20
        self.assertAlmostEqual(BaseballReferenceScraper._calc_fip(data), expected)

    def test_get_team_abbr(self):
        self.assertEqual(BaseballReferenceScraper._get_team_abbr("Boston Red Sox"),
                         "BOS")
        self.assertIsNone(BaseballReferenceScraper._get_team_abbr("Unknown Team"))


class ComparisonTests(unittest.TestCase):
    def setUp(self):
        self.scraper = BaseballReferenceScraper()
        self.batting = {"A": {"ops": 0.800, "home_runs": 50},
                        "B": {"ops": 0.700, "home_runs": 40}}
        self.pitching = {"A": {"era": 3.5, "whip": 1.1},
                         "B": {"era": 4.2, "whip": 1.3}}
        self.fielding = {"A": {"fielding_pct": 0.986},
                         "B": {"fielding_pct": 0.980}}

    def test_compile_comparison_advantages(self):
        comp = self.scraper.compile_team_comparison("A", "B",
                                                    self.batting, self.pitching,
                                                    self.fielding)
        self.assertAlmostEqual(comp["batting"]["home_ops_advantage"], 0.100)
        self.assertAlmostEqual(comp["pitching"]["home_era_advantage"], 0.7)
        self.assertEqual(comp["home_team"], "A")

    def test_missing_team_omits_section(self):
        comp = self.scraper.compile_team_comparison("A", "Z",
                                                    self.batting, self.pitching,
                                                    self.fielding)
        self.assertNotIn("batting", comp)


class OutputTests(unittest.TestCase):
    def setUp(self):
        self.scraper = BaseballReferenceScraper()
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_save_stats_to_csv(self):
        stats = {"Boston Red Sox": {"team": "Boston Red Sox", "runs": 250}}
        out = self.dir / "batting.csv"
        self.scraper.save_stats_to_csv(stats, str(out), "batting")
        with out.open(encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
        self.assertEqual(rows[0]["team"], "Boston Red Sox")

    def test_save_empty_stats_writes_nothing(self):
        out = self.dir / "empty.csv"
        self.scraper.save_stats_to_csv({}, str(out), "batting")
        self.assertFalse(out.exists())

    def test_save_comparison_to_json(self):
        out = self.dir / "cmp.json"
        self.scraper.save_comparison_to_json({"matchup": "A vs B"}, str(out))
        self.assertEqual(json.loads(out.read_text(encoding="utf-8"))["matchup"],
                         "A vs B")


if __name__ == "__main__":
    unittest.main()
