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
    def team_model_stats(self, season, use_cache=False):
        """Return {team_id: {runsPerGame, onBasePercentage, sluggingPercentage,
        runsAllowedPerGame, fieldingPercentage}} for the season."""
        stats = {}

        hitting = self._get(
            f"{self.api}/teams/stats?season={season}&group=hitting"
            f"&stats=season&sportId=1", use_cache)
        for split in hitting["stats"][0]["splits"]:
            stat = split["stat"]
            games = to_float(stat.get("gamesPlayed")) or 1.0
            stats[split["team"]["id"]] = {
                "runsPerGame": to_float(stat.get("runs")) / games,
                "onBasePercentage": to_float(stat.get("obp")),
                "sluggingPercentage": to_float(stat.get("slg")),
            }

        pitching = self._get(
            f"{self.api}/teams/stats?season={season}&group=pitching"
            f"&stats=season&sportId=1", use_cache)
        for split in pitching["stats"][0]["splits"]:
            stat = split["stat"]
            games = to_float(stat.get("gamesPlayed")) or 1.0
            stats.setdefault(split["team"]["id"], {})["runsAllowedPerGame"] = \
                to_float(stat.get("runs")) / games

        fielding = self._get(
            f"{self.api}/teams/stats?season={season}&group=fielding"
            f"&stats=season&sportId=1", use_cache)
        for split in fielding["stats"][0]["splits"]:
            stats.setdefault(split["team"]["id"], {})["fieldingPercentage"] = \
                to_float(split["stat"].get("fielding"))

        return stats

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
    def pitcher_season_stats(self, pid, season, use_cache=False):
        """Return {era, whip, k9} for a pitcher's season, or None if unavailable."""
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
        }

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
