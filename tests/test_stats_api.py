"""Tests for mlb.stats_api.MlbStatsApi — the Stats API repository.

All network access is replaced by tests._fakes.FakeClient, so these pin the
JSON-shape parsing, winner/tie/dedup logic, and pitcher math.
"""

import unittest

from mlb.stats_api import MlbStatsApi
from tests._fakes import FakeClient, schedule_payload, stats_group


def make_api(responses):
    return MlbStatsApi(client=FakeClient(responses))


class TeamModelStatsTests(unittest.TestCase):
    def setUp(self):
        self.responses = {
            "group=hitting": stats_group([
                {"team": {"id": 1},
                 "stat": {"gamesPlayed": 10, "runs": 50, "obp": "0.330", "slg": "0.450"}},
            ]),
            "group=pitching": stats_group([
                {"team": {"id": 1}, "stat": {"gamesPlayed": 10, "runs": 40}},
            ]),
            "group=fielding": stats_group([
                {"team": {"id": 1}, "stat": {"fielding": "0.984"}},
            ]),
        }

    def test_assembles_per_team_dict(self):
        api = make_api(self.responses)
        stats = api.team_model_stats(2025)
        self.assertAlmostEqual(stats[1]["runsPerGame"], 5.0)
        self.assertAlmostEqual(stats[1]["onBasePercentage"], 0.330)
        self.assertAlmostEqual(stats[1]["sluggingPercentage"], 0.450)
        self.assertAlmostEqual(stats[1]["runsAllowedPerGame"], 4.0)
        self.assertAlmostEqual(stats[1]["fieldingPercentage"], 0.984)

    def test_zero_games_avoids_div_by_zero(self):
        self.responses["group=hitting"] = stats_group([
            {"team": {"id": 2}, "stat": {"gamesPlayed": 0, "runs": 7}},
        ])
        api = make_api(self.responses)
        stats = api.team_model_stats(2025)
        self.assertEqual(stats[2]["runsPerGame"], 7.0)  # divided by fallback 1.0

    def test_model_stats_only_exposes_model_fields(self):
        api = make_api(self.responses)
        stats = api.team_model_stats(2025)
        self.assertNotIn("name", stats[1])
        self.assertNotIn("homeRuns", stats[1])


class TeamStandardStatsTests(unittest.TestCase):
    def setUp(self):
        self.responses = {
            "group=hitting": stats_group([
                {"team": {"id": 1, "name": "Boston Red Sox"},
                 "stat": {"gamesPlayed": 10, "runs": 50, "avg": "0.265",
                          "obp": "0.330", "slg": "0.450", "homeRuns": 22}},
            ]),
            "group=pitching": stats_group([
                {"team": {"id": 1, "name": "Boston Red Sox"},
                 "stat": {"gamesPlayed": 10, "runs": 40}},
            ]),
            "group=fielding": stats_group([
                {"team": {"id": 1, "name": "Boston Red Sox"},
                 "stat": {"fielding": "0.984"}},
            ]),
        }

    def test_carries_name_hr_and_avg(self):
        api = make_api(self.responses)
        stats = api.team_standard_stats(2025)
        t = stats[1]
        self.assertEqual(t["name"], "Boston Red Sox")
        self.assertEqual(t["homeRuns"], 22.0)
        self.assertAlmostEqual(t["battingAvg"], 0.265)
        self.assertAlmostEqual(t["runsPerGame"], 5.0)
        self.assertAlmostEqual(t["runsAllowedPerGame"], 4.0)
        self.assertAlmostEqual(t["fieldingPercentage"], 0.984)


class SeasonGamesTests(unittest.TestCase):
    def _game(self, pk, home_id, away_id, hs, as_, state="Final",
              home_sp=None, away_sp=None):
        return {
            "gamePk": pk,
            "status": {"abstractGameState": state},
            "teams": {
                "home": {"team": {"id": home_id}, "score": hs,
                         "probablePitcher": {"id": home_sp} if home_sp else None},
                "away": {"team": {"id": away_id}, "score": as_,
                         "probablePitcher": {"id": away_sp} if away_sp else None},
            },
        }

    def test_winner_from_score_and_starters(self):
        payload = schedule_payload([{"date": "2025-05-01", "games": [
            self._game(1, 10, 20, 5, 3, home_sp=100, away_sp=200),
        ]}])
        api = make_api({"gameType=R": payload})
        games = api.season_games("2025-05-01", "2025-05-01", 2025)
        self.assertEqual(len(games), 1)
        g = games[0]
        self.assertTrue(g["home_won"])
        self.assertEqual(g["home_id"], 10)
        self.assertEqual(g["away_id"], 20)
        self.assertEqual(g["home_sp_id"], 100)
        self.assertEqual(g["away_sp_id"], 200)

    def test_away_winner(self):
        payload = schedule_payload([{"date": "2025-05-01", "games": [
            self._game(1, 10, 20, 2, 6),
        ]}])
        api = make_api({"gameType=R": payload})
        self.assertFalse(api.season_games("a", "b", 2025)[0]["home_won"])

    def test_skips_non_final_ties_and_missing_scores(self):
        payload = schedule_payload([{"date": "d", "games": [
            self._game(1, 1, 2, 5, 3, state="Live"),
            self._game(2, 1, 2, 4, 4),          # tie
            self._game(3, 1, 2, None, 3),       # missing score
            self._game(4, 1, 2, 7, 1),          # valid
        ]}])
        api = make_api({"gameType=R": payload})
        games = api.season_games("a", "b", 2025)
        self.assertEqual(len(games), 1)

    def test_dedupes_by_gamepk(self):
        g = self._game(99, 1, 2, 5, 3)
        payload = schedule_payload([{"date": "d", "games": [g, dict(g)]}])
        api = make_api({"gameType=R": payload})
        self.assertEqual(len(api.season_games("a", "b", 2025)), 1)

    def test_missing_probable_pitcher_is_none(self):
        payload = schedule_payload([{"date": "d", "games": [
            self._game(1, 1, 2, 5, 3),
        ]}])
        api = make_api({"gameType=R": payload})
        g = api.season_games("a", "b", 2025)[0]
        self.assertIsNone(g["home_sp_id"])
        self.assertIsNone(g["away_sp_id"])


class ScheduledAndFinalTests(unittest.TestCase):
    def _payload(self, state="Final", hs=5, as_=3):
        return schedule_payload([{"date": "2026-05-30", "games": [{
            "gamePk": 1,
            "status": {"abstractGameState": state},
            "teams": {
                "home": {"team": {"name": "Boston Red Sox"}, "score": hs,
                         "probablePitcher": {"fullName": "Ace Home", "id": 1}},
                "away": {"team": {"name": "New York Yankees"}, "score": as_,
                         "probablePitcher": {"fullName": "Ace Away", "id": 2}},
            },
        }]}])

    def test_scheduled_games_names(self):
        api = make_api({"schedule": self._payload(state="Preview")})
        games = api.scheduled_games("2026-05-30")
        self.assertEqual(games[0]["home"], "Boston Red Sox")
        self.assertEqual(games[0]["away"], "New York Yankees")
        self.assertEqual(games[0]["home_sp"], "Ace Home")

    def test_scheduled_games_blank_when_unannounced(self):
        payload = self._payload(state="Preview")
        payload["dates"][0]["games"][0]["teams"]["home"]["probablePitcher"] = None
        api = make_api({"schedule": payload})
        self.assertEqual(api.scheduled_games("2026-05-30")[0]["home_sp"], "")

    def test_final_scores_winner_loser(self):
        api = make_api({"schedule": self._payload(hs=5, as_=3)})
        row = api.final_scores("2026-05-30")[0]
        self.assertEqual(row["winner"], "Boston Red Sox")
        self.assertEqual(row["loser"], "New York Yankees")
        self.assertTrue(row["home_won"])
        self.assertEqual(row["home_score"], 5)

    def test_final_scores_skips_non_final(self):
        api = make_api({"schedule": self._payload(state="Live")})
        self.assertEqual(api.final_scores("2026-05-30"), [])

    def test_probable_starters_map(self):
        api = make_api({"schedule": self._payload(state="Preview")})
        starters = api.probable_starters("2026-05-30")
        self.assertEqual(starters, {1: "Ace Home", 2: "Ace Away"})


class PitcherStatsTests(unittest.TestCase):
    def test_season_stats(self):
        payload = stats_group([{"stat": {"era": "2.50", "whip": "1.05",
                                         "strikeoutsPer9Inn": "9.8"}}])
        api = make_api({"stats=season": payload})
        stats = api.pitcher_season_stats(123, 2025)
        # No innings pitched in the payload -> FIP unavailable (-1.0).
        self.assertEqual(stats, {"era": 2.50, "whip": 1.05, "k9": 9.8, "fip": -1.0})

    def test_season_stats_computes_fip(self):
        payload = stats_group([{"stat": {
            "era": "3.00", "whip": "1.10", "strikeoutsPer9Inn": "9.0",
            "inningsPitched": "100.0", "homeRuns": 10,
            "baseOnBalls": 30, "hitByPitch": 5, "strikeOuts": 100}}])
        api = make_api({"stats=season": payload})
        fip = api.pitcher_season_stats(7, 2025)["fip"]
        expected = (13 * 10 + 3 * (30 + 5) - 2 * 100) / 100.0 + 3.10
        self.assertAlmostEqual(fip, expected, places=9)

    def test_season_stats_none_pid(self):
        self.assertIsNone(make_api({}).pitcher_season_stats(None, 2025))

    def test_season_stats_no_splits_returns_none(self):
        api = make_api({"stats=season": {"stats": [{"splits": []}]}})
        self.assertIsNone(api.pitcher_season_stats(1, 2025))

    def test_game_log_filters_relief_and_sorts(self):
        payload = stats_group([
            {"date": "2025-05-10", "stat": {"gamesStarted": 1,
                                            "earnedRuns": 2, "inningsPitched": "6.0"}},
            {"date": "2025-05-01", "stat": {"gamesStarted": 1,
                                            "earnedRuns": 3, "inningsPitched": "5.0"}},
            {"date": "2025-05-05", "stat": {"gamesStarted": 0,  # relief, dropped
                                            "earnedRuns": 0, "inningsPitched": "1.0"}},
        ])
        api = make_api({"stats=gameLog": payload})
        starts = api.pitcher_game_log(7, 2025)
        self.assertEqual([s["date"] for s in starts], ["2025-05-01", "2025-05-10"])

    def test_game_log_empty_pid(self):
        self.assertEqual(make_api({}).pitcher_game_log(None, 2025), [])

    def test_recent_era_over_last_starts(self):
        payload = stats_group([
            {"date": "2025-05-01", "stat": {"gamesStarted": 1,
                                            "earnedRuns": 2, "inningsPitched": "6.0"}},
            {"date": "2025-05-08", "stat": {"gamesStarted": 1,
                                            "earnedRuns": 4, "inningsPitched": "6.0"}},
        ])
        api = make_api({"stats=gameLog": payload})
        # (2+4) ER over (6+6)=12 IP -> 9*6/12 = 4.5
        self.assertAlmostEqual(api.recent_era(7, 2025), 4.5)

    def test_recent_era_respects_before_date(self):
        payload = stats_group([
            {"date": "2025-05-01", "stat": {"gamesStarted": 1,
                                            "earnedRuns": 1, "inningsPitched": "9.0"}},
            {"date": "2025-05-20", "stat": {"gamesStarted": 1,
                                            "earnedRuns": 9, "inningsPitched": "1.0"}},
        ])
        api = make_api({"stats=gameLog": payload})
        # only the 2025-05-01 start counts -> 9*1/9 = 1.0
        self.assertAlmostEqual(api.recent_era(7, 2025, before_date="2025-05-10"), 1.0)

    def test_recent_era_no_data_returns_sentinel(self):
        api = make_api({"stats=gameLog": {"stats": []}})
        self.assertEqual(api.recent_era(7, 2025), -1.0)


if __name__ == "__main__":
    unittest.main()
