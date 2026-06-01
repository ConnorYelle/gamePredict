"""Tests for MlbStatsApi.live_games -- the dashboard's live schedule read.

Uses tests._fakes.FakeClient so the preview/live/final shapes (and the winner /
current-pitcher derivation) are pinned without network access.
"""

import unittest

from mlb.stats_api import MlbStatsApi
from tests._fakes import FakeClient, schedule_payload


def make_api(payload):
    return MlbStatsApi(client=FakeClient({"schedule": payload}))


def game(state="Preview", hs=None, as_=None, detailed="", linescore=None,
         home_sp="Home Ace", away_sp="Away Ace"):
    return {
        "gamePk": 1,
        "status": {"abstractGameState": state, "detailedState": detailed},
        "linescore": linescore,
        "teams": {
            "home": {"team": {"name": "Boston Red Sox"}, "score": hs,
                     "probablePitcher": {"fullName": home_sp} if home_sp else None},
            "away": {"team": {"name": "New York Yankees"}, "score": as_,
                     "probablePitcher": {"fullName": away_sp} if away_sp else None},
        },
    }


def payload(g):
    return schedule_payload([{"date": "2026-05-31", "games": [g]}])


class LiveGamesTests(unittest.TestCase):
    def test_preview_has_starters_no_scores(self):
        api = make_api(payload(game(state="Preview")))
        row = api.live_games("2026-05-31")[0]
        self.assertEqual(row["state"], "preview")
        self.assertIsNone(row["home_score"])
        self.assertEqual(row["home_sp"], "Home Ace")
        self.assertEqual(row["away_sp"], "Away Ace")
        self.assertEqual(row["current_pitcher"], "")
        self.assertIsNone(row["winner"])

    def test_live_carries_score_inning_and_mound_pitcher(self):
        ls = {"currentInning": 6, "inningState": "Bottom", "isTopInning": False,
              "defense": {"pitcher": {"fullName": "Reliever Joe"}}}
        api = make_api(payload(game(state="Live", hs=2, as_=4, linescore=ls)))
        row = api.live_games("2026-05-31")[0]
        self.assertEqual(row["state"], "live")
        self.assertEqual(row["home_score"], 2)
        self.assertEqual(row["away_score"], 4)
        self.assertEqual(row["inning"], 6)
        self.assertEqual(row["inning_state"], "Bottom")
        self.assertFalse(row["is_top"])
        self.assertEqual(row["current_pitcher"], "Reliever Joe")
        self.assertIsNone(row["winner"])  # not final

    def test_final_sets_winner_and_home_won(self):
        api = make_api(payload(game(state="Final", hs=5, as_=3)))
        row = api.live_games("2026-05-31")[0]
        self.assertEqual(row["state"], "final")
        self.assertTrue(row["home_won"])
        self.assertEqual(row["winner"], "Boston Red Sox")

    def test_final_away_winner(self):
        api = make_api(payload(game(state="Final", hs=1, as_=7)))
        row = api.live_games("2026-05-31")[0]
        self.assertFalse(row["home_won"])
        self.assertEqual(row["winner"], "New York Yankees")

    def test_final_tie_leaves_winner_none(self):
        api = make_api(payload(game(state="Final", hs=4, as_=4)))
        row = api.live_games("2026-05-31")[0]
        self.assertIsNone(row["winner"])
        self.assertIsNone(row["home_won"])

    def test_unknown_state_falls_back_to_other(self):
        api = make_api(payload(game(state="Postponed", detailed="Postponed")))
        row = api.live_games("2026-05-31")[0]
        self.assertEqual(row["state"], "other")
        self.assertEqual(row["detailed_state"], "Postponed")

    def test_missing_linescore_is_safe(self):
        api = make_api(payload(game(state="Live", hs=0, as_=0, linescore=None)))
        row = api.live_games("2026-05-31")[0]
        self.assertIsNone(row["inning"])
        self.assertEqual(row["current_pitcher"], "")


if __name__ == "__main__":
    unittest.main()
