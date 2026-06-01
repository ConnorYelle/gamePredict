"""Repository over the public MLB Stats API.

``MlbStatsApi`` is the single source of truth for every read against
statsapi.mlb.com: team season stats, completed game results (with starters),
and pitcher stats/game logs. Callers work with plain dicts and never see URLs
or JSON shapes. All network access goes through an injected ``JsonHttpClient``.
"""

from . import config
from .http_client import JsonHttpClient
from .utils import ip_to_float, to_float


class MlbStatsApi:
    def __init__(self, client=None, api_base=config.API):
        self.api = api_base
        self.client = client or JsonHttpClient(config.CACHE_DIR)

    def _get(self, url, use_cache=False):
        return self.client.get_json(url, use_cache=use_cache)

    # ----------------------------------------------------------------- #
    # Team season stats (model inputs)
    # ----------------------------------------------------------------- #
    def team_standard_stats(self, season, use_cache=False):
        """Return rich per-team season stats keyed by team id:
        {id: {name, runsPerGame, battingAvg, onBasePercentage,
              sluggingPercentage, homeRuns, runsAllowedPerGame,
              fieldingPercentage}}.

        This is the single fetch path for team season stats (one call each to
        the hitting/pitching/fielding endpoints). It carries everything needed
        both to feed the model (see :meth:`team_model_stats`) and to write the
        predictor's TeamStandardBatting.txt / TeamFielding.txt files.
        """
        teams = {}
        games_by_team = {}

        hitting = self._get(
            f"{self.api}/teams/stats?season={season}&group=hitting"
            f"&stats=season&sportId=1", use_cache)
        for split in hitting["stats"][0]["splits"]:
            stat = split["stat"]
            games = to_float(stat.get("gamesPlayed")) or 1.0
            tid = split["team"]["id"]
            games_by_team[tid] = games
            teams[tid] = {
                "name": split["team"].get("name", ""),
                "runsPerGame": to_float(stat.get("runs")) / games,
                "battingAvg": to_float(stat.get("avg")),
                "onBasePercentage": to_float(stat.get("obp")),
                "sluggingPercentage": to_float(stat.get("slg")),
                "homeRuns": to_float(stat.get("homeRuns")),
            }

        pitching = self._get(
            f"{self.api}/teams/stats?season={season}&group=pitching"
            f"&stats=season&sportId=1", use_cache)
        for split in pitching["stats"][0]["splits"]:
            stat = split["stat"]
            games = to_float(stat.get("gamesPlayed")) or 1.0
            tid = split["team"]["id"]
            games_by_team.setdefault(tid, games)
            entry = teams.setdefault(tid, {})
            entry.setdefault("name", split["team"].get("name", ""))
            entry["runsAllowedPerGame"] = to_float(stat.get("runs")) / games

        fielding = self._get(
            f"{self.api}/teams/stats?season={season}&group=fielding"
            f"&stats=season&sportId=1", use_cache)
        for split in fielding["stats"][0]["splits"]:
            entry = teams.setdefault(split["team"]["id"], {})
            entry.setdefault("name", split["team"].get("name", ""))
            entry["fieldingPercentage"] = to_float(split["stat"].get("fielding"))

        self._regress_rate_stats(teams, games_by_team)

        for entry in teams.values():
            entry["parkFactor"] = config.PARK_FACTORS.get(entry.get("name", ""), 1.0)

        for tid, bp in self.team_bullpen_stats(season, use_cache=use_cache).items():
            if tid in teams:
                teams[tid].update(bp)

        return teams

    # Rate stats shrunk toward the league mean to tame small samples.
    _REGRESSED_FIELDS = ("runsPerGame", "onBasePercentage",
                         "sluggingPercentage", "runsAllowedPerGame")

    @staticmethod
    def _regress_rate_stats(teams, games_by_team, k=None):
        """Shrink each team's rate stats toward the league mean, weighting the
        team's own value by its games played and the mean by ``k`` games. This
        is the cheap, untrained calibration win: early in a season the league
        spread is mostly noise, so regressing toward the mean lowers the Brier
        score without touching any weight."""
        k = config.REGRESSION_GAMES if k is None else k
        if k <= 0 or not teams:
            return
        for field in MlbStatsApi._REGRESSED_FIELDS:
            vals = [t[field] for t in teams.values() if field in t]
            if not vals:
                continue
            mean = sum(vals) / len(vals)
            for tid, t in teams.items():
                if field not in t:
                    continue
                g = games_by_team.get(tid, 1.0)
                t[field] = (t[field] * g + mean * k) / (g + k)

    # Fields consumed by the win-probability model (see mlb.model).
    _MODEL_FIELDS = ("runsPerGame", "onBasePercentage", "sluggingPercentage",
                     "runsAllowedPerGame", "fieldingPercentage",
                     "parkFactor", "bullpenEra", "bullpenKbb")

    def team_model_stats(self, season, use_cache=False):
        """Return {team_id: {runsPerGame, onBasePercentage, sluggingPercentage,
        runsAllowedPerGame, fieldingPercentage}} for the season -- the subset of
        :meth:`team_standard_stats` the model actually consumes."""
        full = self.team_standard_stats(season, use_cache=use_cache)
        return {tid: {k: s[k] for k in self._MODEL_FIELDS if k in s}
                for tid, s in full.items()}

    # ----------------------------------------------------------------- #
    # Game results / schedule (with starters)
    # ----------------------------------------------------------------- #
    def season_games(self, start_date, end_date, season, use_cache=False):
        """Return completed regular-season games as dicts:
        {date, home_id, away_id, home_won, home_sp_id, away_sp_id}.

        Winner is taken from the final score (the API only flags ``isWinner`` on
        the winning side). Games are deduped by gamePk.
        """
        url = (f"{self.api}/schedule?sportId=1&gameType=R&season={season}"
               f"&startDate={start_date}&endDate={end_date}"
               f"&hydrate=probablePitcher")
        data = self._get(url, use_cache)

        games = []
        seen = set()
        for day in data.get("dates", []):
            date = day.get("date", "")
            for game in day.get("games", []):
                game_pk = game.get("gamePk")
                if game_pk in seen:
                    continue
                if game.get("status", {}).get("abstractGameState") != "Final":
                    continue
                home = game["teams"]["home"]
                away = game["teams"]["away"]
                hs, as_ = home.get("score"), away.get("score")
                if hs is None or as_ is None or hs == as_:
                    continue
                seen.add(game_pk)
                games.append({
                    "date": date,
                    "home_id": home["team"]["id"],
                    "away_id": away["team"]["id"],
                    "home_won": hs > as_,
                    "home_sp_id": (home.get("probablePitcher") or {}).get("id"),
                    "away_sp_id": (away.get("probablePitcher") or {}).get("id"),
                })
        return games

    def scheduled_games(self, date_str):
        """Return today's scheduled games as
        {home, away, home_sp, away_sp} name dicts (blank starter when unannounced)."""
        url = f"{self.api}/schedule?sportId=1&date={date_str}&hydrate=probablePitcher"
        data = self._get(url)

        games = []
        for day in data.get("dates", []):
            for game in day.get("games", []):
                home = game["teams"]["home"]
                away = game["teams"]["away"]
                games.append({
                    "home": home["team"]["name"],
                    "away": away["team"]["name"],
                    "home_sp": (home.get("probablePitcher") or {}).get("fullName", ""),
                    "away_sp": (away.get("probablePitcher") or {}).get("fullName", ""),
                })
        return games

    def final_scores(self, date_str):
        """Return completed games for a date with names and final scores:
        {date, home, away, home_score, away_score, home_won, winner, loser,
        home_sp, away_sp}. Ties and non-final games are skipped."""
        url = f"{self.api}/schedule?sportId=1&date={date_str}&hydrate=probablePitcher"
        data = self._get(url)

        games = []
        seen = set()
        for day in data.get("dates", []):
            date = day.get("date", "")
            for game in day.get("games", []):
                game_pk = game.get("gamePk")
                if game_pk in seen:
                    continue
                if game.get("status", {}).get("abstractGameState") != "Final":
                    continue
                home = game["teams"]["home"]
                away = game["teams"]["away"]
                hs, as_ = home.get("score"), away.get("score")
                if hs is None or as_ is None or hs == as_:
                    continue
                seen.add(game_pk)
                home_won = hs > as_
                home_name = home["team"]["name"]
                away_name = away["team"]["name"]
                games.append({
                    "date": date,
                    "home": home_name,
                    "away": away_name,
                    "home_score": hs,
                    "away_score": as_,
                    "home_won": home_won,
                    "winner": home_name if home_won else away_name,
                    "loser": away_name if home_won else home_name,
                    "home_sp": (home.get("probablePitcher") or {}).get("fullName", ""),
                    "away_sp": (away.get("probablePitcher") or {}).get("fullName", ""),
                })
        return games

    # Maps the API's coarse game phase onto the three states the live
    # dashboard cares about; anything else (postponed, suspended, ...) is
    # surfaced verbatim via ``detailed_state``.
    _LIVE_STATE = {"Preview": "preview", "Live": "live", "Final": "final"}

    def live_games(self, date_str):
        """Return today's games with live status for the dashboard:
        ``{home, away, state, start_time, detailed_state, home_score,
        away_score, inning, inning_state, is_top, home_sp, away_sp,
        current_pitcher, home_won, winner}``.

        ``start_time`` is the scheduled first pitch as a UTC ISO timestamp
        (the feed's ``gameDate``); the front-end renders it in local time.

        One schedule call hydrated with ``linescore`` (live score/inning and,
        when a game is underway, the pitcher on the mound) and
        ``probablePitcher`` (announced starters). ``state`` is one of
        ``preview``/``live``/``final``/``other``. Scores are ``None`` before
        first pitch; ``winner``/``home_won`` are only set once a final has a
        decided score.
        """
        url = (f"{self.api}/schedule?sportId=1&date={date_str}"
               f"&hydrate=linescore,probablePitcher")
        data = self._get(url)

        games = []
        for day in data.get("dates", []):
            for game in day.get("games", []):
                home = game["teams"]["home"]
                away = game["teams"]["away"]
                abstract = game.get("status", {}).get("abstractGameState", "")
                line = game.get("linescore") or {}

                hs, as_ = home.get("score"), away.get("score")
                home_won = winner = None
                state = self._LIVE_STATE.get(abstract, "other")
                if state == "final" and hs is not None and as_ is not None \
                        and hs != as_:
                    home_won = hs > as_
                    winner = home["team"]["name"] if home_won else away["team"]["name"]

                # The fielding side's pitcher is the one on the mound. When the
                # API doesn't carry an active pitcher (preview/between innings),
                # this stays blank and the front-end shows the matchup starters.
                current_pitcher = ((line.get("defense") or {})
                                   .get("pitcher") or {}).get("fullName", "")

                games.append({
                    "home": home["team"]["name"],
                    "away": away["team"]["name"],
                    "state": state,
                    "start_time": game.get("gameDate", ""),
                    "detailed_state": game.get("status", {}).get("detailedState", ""),
                    "home_score": hs,
                    "away_score": as_,
                    "inning": line.get("currentInning"),
                    "inning_state": line.get("inningState", ""),
                    "is_top": line.get("isTopInning"),
                    "home_sp": (home.get("probablePitcher") or {}).get("fullName", ""),
                    "away_sp": (away.get("probablePitcher") or {}).get("fullName", ""),
                    "current_pitcher": current_pitcher,
                    "home_won": home_won,
                    "winner": winner,
                })
        return games

    def probable_starters(self, date_str):
        """Return {pitcher_id: name} for a date's announced probable starters."""
        url = f"{self.api}/schedule?sportId=1&date={date_str}&hydrate=probablePitcher"
        data = self._get(url)
        starters = {}
        for day in data.get("dates", []):
            for game in day.get("games", []):
                for side in ("home", "away"):
                    pp = game["teams"][side].get("probablePitcher")
                    if pp and pp.get("id"):
                        starters[pp["id"]] = pp.get("fullName", "")
        return starters

    # ----------------------------------------------------------------- #
    # Pitcher stats
    # ----------------------------------------------------------------- #
    # FIP constant: roughly centers league FIP on league ERA.
    _FIP_CONSTANT = 3.10

    @classmethod
    def _fip(cls, stat):
        """Fielding Independent Pitching from a season stat object, or -1.0 when
        the components are unavailable. FIP isolates the outcomes a pitcher
        controls (K, BB, HBP, HR) and is far less noisy than ERA, which is why
        the model can lean on it more confidently than on raw ERA."""
        ip = ip_to_float(stat.get("inningsPitched"))
        if ip <= 0:
            return -1.0
        hr = to_float(stat.get("homeRuns"))
        bb = to_float(stat.get("baseOnBalls"))
        hbp = to_float(stat.get("hitByPitch"))
        k = to_float(stat.get("strikeOuts"))
        return (13.0 * hr + 3.0 * (bb + hbp) - 2.0 * k) / ip + cls._FIP_CONSTANT

    def pitcher_season_stats(self, pid, season, use_cache=False):
        """Return {era, whip, k9, fip} for a pitcher's season, or None if
        unavailable. Any individual stat is -1.0 when it cannot be computed."""
        if not pid:
            return None
        data = self._get(
            f"{self.api}/people/{pid}/stats?stats=season&season={season}"
            f"&group=pitching", use_cache)
        stats = data.get("stats", [])
        if not stats or not stats[0].get("splits"):
            return None
        stat = stats[0]["splits"][0]["stat"]
        return {
            "era": to_float(stat.get("era"), -1.0),
            "whip": to_float(stat.get("whip"), -1.0),
            "k9": to_float(stat.get("strikeoutsPer9Inn"), -1.0),
            "fip": self._fip(stat),
        }

    # ----------------------------------------------------------------- #
    # Bullpen (relief-pitching split)
    # ----------------------------------------------------------------- #
    def team_bullpen_stats(self, season, use_cache=False):
        """Return {team_id: {bullpenEra, bullpenKbb}} from the relief-pitching
        split. The starter throws ~5 innings; the bullpen covers the rest and is
        one of the largest single-game swing factors, yet season RA/G blurs it
        into the staff total. Best-effort: any failure or shape mismatch yields
        an empty dict so the rest of the pipeline degrades gracefully."""
        try:
            data = self._get(
                f"{self.api}/teams/stats?stats=statSplits&group=pitching"
                f"&season={season}&sportId=1&sitCodes=rp", use_cache)
            splits = (data.get("stats") or [{}])[0].get("splits", [])
        except Exception:
            return {}

        result = {}
        for split in splits:
            team = split.get("team") or {}
            tid = team.get("id")
            if tid is None:
                continue
            stat = split.get("stat", {})
            k9 = to_float(stat.get("strikeoutsPer9Inn"), -1.0)
            bb9 = to_float(stat.get("walksPer9Inn"), -1.0)
            result[tid] = {
                "bullpenEra": to_float(stat.get("era"), -1.0),
                "bullpenKbb": (k9 - bb9) if (k9 >= 0 and bb9 >= 0) else -1.0,
            }
        return result

    def pitcher_game_log(self, pid, season, use_cache=False):
        """Return a pitcher's starts as [{date, er, ip}] sorted ascending by date."""
        if not pid:
            return []
        data = self._get(
            f"{self.api}/people/{pid}/stats?stats=gameLog&season={season}"
            f"&group=pitching", use_cache)
        stats = data.get("stats", [])
        if not stats:
            return []
        starts = []
        for split in stats[0].get("splits", []):
            stat = split.get("stat", {})
            if to_float(stat.get("gamesStarted")) < 1:
                continue
            starts.append({
                "date": split.get("date", ""),
                "er": to_float(stat.get("earnedRuns")),
                "ip": ip_to_float(stat.get("inningsPitched")),
            })
        starts.sort(key=lambda s: s["date"])
        return starts

    def recent_era(self, pid, season, before_date=None, n=3, use_cache=False):
        """ERA over a pitcher's last ``n`` starts (strictly before ``before_date``
        when given, else the most recent). Returns -1.0 when there is no data."""
        starts = self.pitcher_game_log(pid, season, use_cache)
        if before_date:
            starts = [s for s in starts if s["date"] < before_date]
        recent = starts[-n:]
        total_ip = sum(s["ip"] for s in recent)
        if total_ip <= 0:
            return -1.0
        total_er = sum(s["er"] for s in recent)
        return 9.0 * total_er / total_ip
