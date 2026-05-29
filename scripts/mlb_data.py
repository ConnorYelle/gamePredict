#!/usr/bin/env python3
"""Shared MLB Stats API helpers and the prediction model (Python port).

Single source of truth for:
- fetching team season stats, game results, and starting-pitcher stats
- computing a pitcher's recent-form ERA from game logs (date-aware, no leakage)
- the win-probability formula, kept identical to cpp/GamePredictor.cpp

Used by the backtest (validate_predictions.py), the self-learning trainer
(train_weights.py), and the live pitcher collector (collect_pitchers.py).

Responses are cached under data/cache/ so repeated training runs are fast.
"""

import hashlib
import json
import os
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CACHE_DIR = ROOT / "data" / "cache"
CONFIG_PATH = ROOT / "config" / "config.json"

API = "https://statsapi.mlb.com/api/v1"

# Weight names and defaults, mirroring GamePredictor.h. Pitcher weights start at
# 0 so an untrained model behaves exactly like the original team-only formula.
DEFAULT_WEIGHTS = {
    "runsPerGameWeight": 0.4,
    "onBasePercentageWeight": 50.0,
    "sluggingPercentageWeight": 30.0,
    "offenseWeight": 0.6,
    "defenseWeight": 0.4,
    "homeFieldAdvantage": 1.05,
    "pitcherEraWeight": 0.0,
    "pitcherWhipWeight": 0.0,
    "pitcherK9Weight": 0.0,
    "pitcherRecentFormWeight": 0.0,
}


# --------------------------------------------------------------------------- #
# Fetching + caching
# --------------------------------------------------------------------------- #
def fetch_json(url, use_cache=False):
    """GET JSON, optionally caching the response to disk (for past-season data)."""
    if use_cache:
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        key = hashlib.md5(url.encode("utf-8")).hexdigest()
        cache_file = CACHE_DIR / f"{key}.json"
        if cache_file.exists():
            try:
                return json.loads(cache_file.read_text(encoding="utf-8"))
            except ValueError:
                pass

    req = urllib.request.Request(url, headers={"User-Agent": "gamePrediction"})
    with urllib.request.urlopen(req, timeout=60) as resp:
        data = json.loads(resp.read().decode("utf-8"))

    if use_cache:
        cache_file.write_text(json.dumps(data), encoding="utf-8")
    return data


def _to_float(value, default=0.0):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def ip_to_float(ip):
    """Convert MLB innings-pitched notation ('6.2' = 6 + 2/3) to a float."""
    try:
        whole, _, frac = str(ip).partition(".")
        outs = int(frac) if frac else 0
        return int(whole) + outs / 3.0
    except (ValueError, TypeError):
        return 0.0


# --------------------------------------------------------------------------- #
# Team season stats (model inputs)
# --------------------------------------------------------------------------- #
def team_model_stats(season, use_cache=False):
    """Return {team_id: {runsPerGame, onBasePercentage, sluggingPercentage,
    runsAllowedPerGame, fieldingPercentage}} for the season."""
    stats = {}

    hitting = fetch_json(
        f"{API}/teams/stats?season={season}&group=hitting&stats=season&sportId=1",
        use_cache)
    for split in hitting["stats"][0]["splits"]:
        stat = split["stat"]
        games = _to_float(stat.get("gamesPlayed")) or 1.0
        stats[split["team"]["id"]] = {
            "runsPerGame": _to_float(stat.get("runs")) / games,
            "onBasePercentage": _to_float(stat.get("obp")),
            "sluggingPercentage": _to_float(stat.get("slg")),
        }

    pitching = fetch_json(
        f"{API}/teams/stats?season={season}&group=pitching&stats=season&sportId=1",
        use_cache)
    for split in pitching["stats"][0]["splits"]:
        stat = split["stat"]
        games = _to_float(stat.get("gamesPlayed")) or 1.0
        stats.setdefault(split["team"]["id"], {})["runsAllowedPerGame"] = \
            _to_float(stat.get("runs")) / games

    fielding = fetch_json(
        f"{API}/teams/stats?season={season}&group=fielding&stats=season&sportId=1",
        use_cache)
    for split in fielding["stats"][0]["splits"]:
        stats.setdefault(split["team"]["id"], {})["fieldingPercentage"] = \
            _to_float(split["stat"].get("fielding"))

    return stats


# --------------------------------------------------------------------------- #
# Game results (with starters)
# --------------------------------------------------------------------------- #
def season_games(start_date, end_date, season, use_cache=False):
    """Return completed regular-season games as dicts:
    {date, home_id, away_id, home_won, home_sp_id, away_sp_id}.

    Winner is taken from the final score (the API only flags ``isWinner`` on the
    winning side). Games are deduped by gamePk.
    """
    url = (f"{API}/schedule?sportId=1&gameType=R&season={season}"
           f"&startDate={start_date}&endDate={end_date}&hydrate=probablePitcher")
    data = fetch_json(url, use_cache)

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


# --------------------------------------------------------------------------- #
# Pitcher stats
# --------------------------------------------------------------------------- #
def pitcher_season_stats(pid, season, use_cache=False):
    """Return {era, whip, k9} for a pitcher's season, or None if unavailable."""
    if not pid:
        return None
    data = fetch_json(
        f"{API}/people/{pid}/stats?stats=season&season={season}&group=pitching",
        use_cache)
    stats = data.get("stats", [])
    if not stats or not stats[0].get("splits"):
        return None
    stat = stats[0]["splits"][0]["stat"]
    return {
        "era": _to_float(stat.get("era"), -1.0),
        "whip": _to_float(stat.get("whip"), -1.0),
        "k9": _to_float(stat.get("strikeoutsPer9Inn"), -1.0),
    }


def pitcher_game_log(pid, season, use_cache=False):
    """Return a pitcher's starts as [{date, er, ip}] sorted ascending by date."""
    if not pid:
        return []
    data = fetch_json(
        f"{API}/people/{pid}/stats?stats=gameLog&season={season}&group=pitching",
        use_cache)
    stats = data.get("stats", [])
    if not stats:
        return []
    starts = []
    for split in stats[0].get("splits", []):
        stat = split.get("stat", {})
        if _to_float(stat.get("gamesStarted")) < 1:
            continue
        starts.append({
            "date": split.get("date", ""),
            "er": _to_float(stat.get("earnedRuns")),
            "ip": ip_to_float(stat.get("inningsPitched")),
        })
    starts.sort(key=lambda s: s["date"])
    return starts


def recent_era(pid, season, before_date=None, n=3, use_cache=False):
    """ERA over a pitcher's last ``n`` starts (strictly before ``before_date``
    when given, else the most recent). Returns -1.0 when there is no data."""
    starts = pitcher_game_log(pid, season, use_cache)
    if before_date:
        starts = [s for s in starts if s["date"] < before_date]
    recent = starts[-n:]
    total_ip = sum(s["ip"] for s in recent)
    if total_ip <= 0:
        return -1.0
    total_er = sum(s["er"] for s in recent)
    return 9.0 * total_er / total_ip


# --------------------------------------------------------------------------- #
# The model (Python port of cpp/GamePredictor.cpp)
# --------------------------------------------------------------------------- #
def load_weights(config_path=CONFIG_PATH):
    weights = dict(DEFAULT_WEIGHTS)
    try:
        with open(config_path, encoding="utf-8") as f:
            cfg = json.load(f)
        for key, val in cfg.get("weights", {}).items():
            if key in weights:
                weights[key] = float(val)
    except (OSError, ValueError):
        pass
    return weights


def save_weights(weights, config_path=CONFIG_PATH):
    with open(config_path, "w", encoding="utf-8") as f:
        json.dump({"weights": weights}, f, indent=2)
        f.write("\n")


def _pitcher_score(p, w):
    """p is {era, whip, k9, recentEra} (or None). Missing values are < 0."""
    if not p:
        return 0.0
    score = 0.0
    if p.get("era", -1) >= 0:
        score += (1.0 / (p["era"] + 0.1)) * w["pitcherEraWeight"]
    if p.get("whip", -1) >= 0:
        score += (1.0 / (p["whip"] + 0.1)) * w["pitcherWhipWeight"]
    if p.get("k9", -1) >= 0:
        score += p["k9"] * w["pitcherK9Weight"]
    if p.get("recentEra", -1) >= 0:
        score += (1.0 / (p["recentEra"] + 0.1)) * w["pitcherRecentFormWeight"]
    return score


def home_win_probability(home, away, home_sp, away_sp, w):
    """Win probability for the home team. ``home``/``away`` are team-stat dicts;
    ``home_sp``/``away_sp`` are pitcher dicts (or None)."""
    def offense(t):
        return (t.get("runsPerGame", 0.0) * w["runsPerGameWeight"]
                + t.get("onBasePercentage", 0.0) * w["onBasePercentageWeight"]
                + t.get("sluggingPercentage", 0.0) * w["sluggingPercentageWeight"])

    def defense(t):
        return (1.0 / (t.get("runsAllowedPerGame", 0.0) + 0.1)) \
            * t.get("fieldingPercentage", 0.0) * 100

    home_strength = (offense(home) * w["offenseWeight"]
                     + defense(home) * w["defenseWeight"]
                     + _pitcher_score(home_sp, w)) * w["homeFieldAdvantage"]
    away_strength = (offense(away) * w["offenseWeight"]
                     + defense(away) * w["defenseWeight"]
                     + _pitcher_score(away_sp, w))

    total = home_strength + away_strength
    if total == 0:
        return 0.5
    return min(0.99, max(0.01, home_strength / total))
