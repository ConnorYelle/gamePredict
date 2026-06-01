"""Tests for mlb.live -- the predictions+live+stats merge layer.

No network and no real files beyond a tmp dir: a fake API supplies live_games
and the predictions/stats are written to temp files, so the border (correct/
incorrect/pending) logic and field passthrough are pinned deterministically.
"""

import tempfile
import unittest
from pathlib import Path

from mlb import live


SAMPLE_PREDICTIONS = """\
[DEBUG] Loading config from config/config.json
[DEBUG] Loaded games count=2
=== Game Predictions ===
                 MLB GAME PREDICTIONS
============================================================

Toronto Blue Jays @ Baltimore Orioles
------------------------------------------------------------
Starters: Spencer Miles vs Kyle Bradish
Toronto Blue Jays            63.1%
Baltimore Orioles            36.9%

Favorite: Toronto Blue Jays (63.1%)

============================================================

San Diego Padres @ Washington Nationals
------------------------------------------------------------
Starters: Griffin Canning vs Zack Littell
San Diego Padres             31.5%
Washington Nationals         68.5%

Favorite: Washington Nationals (68.5%)
"""


class FakeApi:
    def __init__(self, games=None, error=None):
        self._games = games or []
        self._error = error

    def live_games(self, date_str):
        if self._error:
            raise self._error
        return self._games


def live_game(away, home, **kw):
    base = {
        "away": away, "home": home, "state": "preview", "detailed_state": "",
        "home_score": None, "away_score": None, "inning": None,
        "inning_state": "", "is_top": None, "home_sp": "", "away_sp": "",
        "current_pitcher": "", "home_won": None, "winner": None,
    }
    base.update(kw)
    return base


class ParsePredictionsTests(unittest.TestCase):
    def test_parses_matchups_and_probs(self):
        games = live.parse_predictions(SAMPLE_PREDICTIONS)
        self.assertEqual(len(games), 2)
        g = games[0]
        self.assertEqual(g["away"], "Toronto Blue Jays")
        self.assertEqual(g["home"], "Baltimore Orioles")
        self.assertAlmostEqual(g["away_prob"], 0.631)
        self.assertAlmostEqual(g["home_prob"], 0.369)
        self.assertEqual(g["favorite"], "Toronto Blue Jays")

    def test_favorite_is_home_on_tie_or_higher(self):
        text = "A Team @ B Team\nA Team 40.0%\nB Team 60.0%\n"
        self.assertEqual(live.parse_predictions(text)[0]["favorite"], "B Team")

    def test_ignores_header_without_two_pcts(self):
        # An "@"-looking line with no following percentages is not a matchup.
        self.assertEqual(live.parse_predictions("contact me @ home\n"), [])


class LogoUrlTests(unittest.TestCase):
    def test_known_team(self):
        self.assertEqual(live.logo_url("Toronto Blue Jays"),
                         "https://a.espncdn.com/i/teamlogos/mlb/500/tor.png")

    def test_unknown_team_falls_back(self):
        self.assertIn("/mlb.png", live.logo_url("Some Nonexistent Team"))


class LoadTeamStatsTests(unittest.TestCase):
    def test_reads_batting_and_fielding_columns(self):
        with tempfile.TemporaryDirectory() as d:
            dirp = Path(d)
            batting = ["Tm" + ",c" * 19]  # header (20 cols)
            row = ["x"] * 20
            row[0], row[3], row[11], row[18], row[19] = \
                "Toronto Blue Jays", "5.1", "30", "0.330", "0.450"
            batting.append(",".join(row))
            (dirp / "TeamStandardBatting.txt").write_text(
                "\n".join(batting), encoding="utf-8")

            fielding = ["Tm" + ",c" * 13]
            frow = ["x"] * 14
            frow[0], frow[2], frow[13] = "Toronto Blue Jays", "4.2", "0.985"
            fielding.append(",".join(frow))
            (dirp / "TeamFielding.txt").write_text(
                "\n".join(fielding), encoding="utf-8")

            stats = live.load_team_stats(dirp)
            t = stats["Toronto Blue Jays"]
            self.assertAlmostEqual(t["rpg"], 5.1)
            self.assertEqual(t["hr"], 30.0)
            self.assertAlmostEqual(t["obp"], 0.330)
            self.assertAlmostEqual(t["rag"], 4.2)
            self.assertAlmostEqual(t["fld"], 0.985)

    def test_missing_dir_returns_empty(self):
        self.assertEqual(live.load_team_stats("/no/such/dir"), {})


class BuildPayloadTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.preds = Path(self.tmp.name) / "predictions.txt"
        self.preds.write_text(SAMPLE_PREDICTIONS, encoding="utf-8")
        # An empty stats dir keeps detail stats out of the way of these tests.
        self.stats_dir = Path(self.tmp.name) / "stats"
        self.stats_dir.mkdir()

    def tearDown(self):
        self.tmp.cleanup()

    def build(self, api):
        return live.build_live_payload(api, self.preds, "2026-05-31",
                                       self.stats_dir)

    def test_pending_when_no_live_data(self):
        payload = self.build(FakeApi([]))
        self.assertEqual(len(payload["games"]), 2)
        self.assertTrue(all(g["border"] == "pending" for g in payload["games"]))
        self.assertIsNone(payload["error"])
        # Model probabilities are surfaced as rounded percentages.
        self.assertEqual(payload["games"][0]["awayP"], 63.1)

    def test_correct_border_when_favorite_wins(self):
        api = FakeApi([
            live_game("Toronto Blue Jays", "Baltimore Orioles", state="final",
                      away_score=6, home_score=2, winner="Toronto Blue Jays"),
        ])
        g = self.build(api)["games"][0]
        self.assertEqual(g["border"], "correct")
        self.assertEqual(g["awayScore"], 6)
        self.assertEqual(g["winner"], "Toronto Blue Jays")

    def test_incorrect_border_when_favorite_loses(self):
        api = FakeApi([
            live_game("Toronto Blue Jays", "Baltimore Orioles", state="final",
                      away_score=1, home_score=4, winner="Baltimore Orioles"),
        ])
        self.assertEqual(self.build(api)["games"][0]["border"], "incorrect")

    def test_live_fields_passthrough(self):
        api = FakeApi([
            live_game("Toronto Blue Jays", "Baltimore Orioles", state="live",
                      away_score=2, home_score=3, inning=5, inning_state="Top",
                      current_pitcher="Kyle Bradish"),
        ])
        g = self.build(api)["games"][0]
        self.assertEqual(g["state"], "live")
        self.assertEqual(g["inning"], 5)
        self.assertEqual(g["currentPitcher"], "Kyle Bradish")
        self.assertEqual(g["border"], "pending")  # not final yet

    def test_api_failure_reports_error_but_keeps_games(self):
        payload = self.build(FakeApi(error=RuntimeError("boom")))
        self.assertIn("boom", payload["error"])
        self.assertEqual(len(payload["games"]), 2)
        self.assertTrue(all(g["border"] == "pending" for g in payload["games"]))

    def test_missing_predictions_file_yields_no_games(self):
        payload = live.build_live_payload(
            FakeApi([]), Path(self.tmp.name) / "nope.txt", "2026-05-31",
            self.stats_dir)
        self.assertEqual(payload["games"], [])


if __name__ == "__main__":
    unittest.main()
