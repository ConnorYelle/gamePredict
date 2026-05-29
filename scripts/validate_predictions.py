#!/usr/bin/env python3
"""Validate model predictions against actual game outcomes.

Usage:
    python scripts/validate_predictions.py
        --predictions outputs/predictions.txt
        --games outputs/games.txt

Metrics:
- matched games
- accuracy (correct picks where model > 0.5)
- Brier score (proper binary form)
- average probability assigned to winners
"""

import argparse
import json
import os
import re
import urllib.request
from typing import List, Tuple, Dict, Optional


def parse_predictions(path: str) -> List[Dict]:
    with open(path, encoding="utf-8") as f:
        lines = [l.rstrip() for l in f]

    preds = []

    # Match: "Team Name 55.2%"
    pattern = re.compile(r"^(.+?)\s+(\d{1,2}(?:\.\d+)?)%$")

    for line in lines:
        line = line.strip()
        if not line.endswith("%"):
            continue

        m = pattern.match(line)
        if not m:
            continue

        name = m.group(1).strip()
        prob = float(m.group(2)) / 100.0
        preds.append((name, prob))

    # group into games (2 teams per game)
    games = []
    for i in range(0, len(preds), 2):
        if i + 1 >= len(preds):
            break

        team_a, prob_a = preds[i]
        team_b, prob_b = preds[i + 1]

        games.append({
            "team_a": team_a,
            "prob_a": prob_a,
            "team_b": team_b,
            "prob_b": prob_b,
        })

    return games


def parse_games(path: str) -> List[Tuple[str, str]]:
    games = []

    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue

            if "|" in line:
                left, right = [x.strip() for x in line.split("|", 1)]
                games.append((left, right))
            elif "@" in line:
                away, home = [x.strip() for x in line.split("@", 1)]
                games.append((away, home))

    return games


def normalize(name: str) -> str:
    return re.sub(r"[^a-z0-9 ]", "", name.lower()).strip()


def match_team(actual: str, predicted: str) -> bool:
    a = normalize(actual)
    b = normalize(predicted)

    if a == b:
        return True

    # stronger overlap requirement to avoid false positives
    a_tokens = set(a.split())
    b_tokens = set(b.split())

    overlap = a_tokens & b_tokens

    # require at least 2 meaningful tokens OR full substring match
    return len(overlap) >= 2 or a in b or b in a


def validate(predictions_path: str, games_path: str) -> Dict:
    games_pred = parse_predictions(predictions_path)
    games_act = parse_games(games_path)

    matched = 0
    correct = 0
    brier_sum = 0.0
    probs_for_winner = []

    for i, pred in enumerate(games_pred):
        if i >= len(games_act):
            break

        winner, loser = games_act[i]

        team_a = pred["team_a"]
        team_b = pred["team_b"]
        p_a = pred["prob_a"]
        p_b = pred["prob_b"]

        # determine winner side probability
        if match_team(winner, team_a):
            p_win = p_a
        elif match_team(winner, team_b):
            p_win = p_b
        else:
            continue  # couldn't match team

        matched += 1
        probs_for_winner.append(p_win)

        # accuracy: model picks higher probability team
        predicted_correct = (p_a > p_b and match_team(winner, team_a)) or \
                            (p_b > p_a and match_team(winner, team_b))

        if predicted_correct:
            correct += 1

        # proper binary Brier score
        brier_sum += (1 - p_win) ** 2

    accuracy = correct / matched if matched else 0.0
    avg_prob = sum(probs_for_winner) / len(probs_for_winner) if probs_for_winner else 0.0
    brier = brier_sum / matched if matched else 0.0

    return {
        "games_predicted": len(games_pred),
        "games_actual": len(games_act),
        "matched": matched,
        "accuracy": accuracy,
        "average_winner_prob": avg_prob,
        "brier_score": brier,
    }


# ---------------------------------------------------------------------------
# Backtest mode: compare the current model against actual MLB game results.
#
# Instead of grading a single day's slate (predictions.txt vs games.txt), this
# pulls real regular-season results and season team stats from the public MLB
# Stats API and runs the *same* win-probability formula the C++ engine uses
# (cpp/GamePredictor.cpp), loading the live weights from config/config.json.
# Defaults to the heart of the 2025 season, May through October.
# ---------------------------------------------------------------------------

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG_PATH = os.path.join(ROOT, "config", "config.json")

STATS_API = "https://statsapi.mlb.com/api/v1/teams/stats"
SCHEDULE_API = "https://statsapi.mlb.com/api/v1/schedule"

# Defaults mirror GamePredictor.h so a missing/partial config still works.
DEFAULT_WEIGHTS = {
    "runsPerGameWeight": 0.4,
    "onBasePercentageWeight": 50.0,
    "sluggingPercentageWeight": 30.0,
    "offenseWeight": 0.6,
    "defenseWeight": 0.4,
    "homeFieldAdvantage": 1.05,
}


def load_weights(config_path: str = CONFIG_PATH) -> Dict[str, float]:
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


def _fetch_json(url: str) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": "gamePrediction-validator"})
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _to_float(value, default=0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def fetch_team_model_stats(season: int) -> Dict[int, Dict[str, float]]:
    """Return {team_id: model inputs} for the given season.

    Mirrors the inputs GamePredictor reads from the scraped CSVs:
    runs/game and OBP/SLG (offense), runs-allowed/game and fielding% (defense).
    """
    stats: Dict[int, Dict[str, float]] = {}

    hitting = _fetch_json(f"{STATS_API}?season={season}&group=hitting&stats=season&sportId=1")
    for split in hitting["stats"][0]["splits"]:
        stat = split["stat"]
        games = _to_float(stat.get("gamesPlayed")) or 1.0
        stats[split["team"]["id"]] = {
            "runsPerGame": _to_float(stat.get("runs")) / games,
            "onBasePercentage": _to_float(stat.get("obp")),
            "sluggingPercentage": _to_float(stat.get("slg")),
        }

    pitching = _fetch_json(f"{STATS_API}?season={season}&group=pitching&stats=season&sportId=1")
    for split in pitching["stats"][0]["splits"]:
        stat = split["stat"]
        games = _to_float(stat.get("gamesPlayed")) or 1.0
        team = stats.setdefault(split["team"]["id"], {})
        team["runsAllowedPerGame"] = _to_float(stat.get("runs")) / games

    fielding = _fetch_json(f"{STATS_API}?season={season}&group=fielding&stats=season&sportId=1")
    for split in fielding["stats"][0]["splits"]:
        team = stats.setdefault(split["team"]["id"], {})
        team["fieldingPercentage"] = _to_float(split["stat"].get("fielding"))

    return stats


def fetch_results(start_date: str, end_date: str, season: int) -> List[Tuple[int, int, bool]]:
    """Return [(home_id, away_id, home_won)] for completed regular-season games.

    The winner comes from the final score: the API only sets ``isWinner`` on the
    winning side, so reading that flag would silently drop every away win. The
    schedule can also list a game under multiple date buckets, so dedupe by gamePk.
    """
    url = (f"{SCHEDULE_API}?sportId=1&gameType=R&season={season}"
           f"&startDate={start_date}&endDate={end_date}")
    data = _fetch_json(url)
    games: List[Tuple[int, int, bool]] = []
    seen = set()
    for day in data.get("dates", []):
        for game in day.get("games", []):
            game_pk = game.get("gamePk")
            if game_pk in seen:
                continue
            if game.get("status", {}).get("abstractGameState") != "Final":
                continue
            home = game["teams"]["home"]
            away = game["teams"]["away"]
            home_score = home.get("score")
            away_score = away.get("score")
            if home_score is None or away_score is None or home_score == away_score:
                continue
            seen.add(game_pk)
            games.append((home["team"]["id"], away["team"]["id"], home_score > away_score))
    return games


def home_win_probability(home: Dict[str, float], away: Dict[str, float],
                         w: Dict[str, float]) -> float:
    """Python port of GamePredictor::predictWinProbability."""
    def offense(t):
        return (t.get("runsPerGame", 0.0) * w["runsPerGameWeight"]
                + t.get("onBasePercentage", 0.0) * w["onBasePercentageWeight"]
                + t.get("sluggingPercentage", 0.0) * w["sluggingPercentageWeight"])

    def defense(t):
        return (1.0 / (t.get("runsAllowedPerGame", 0.0) + 0.1)) * t.get("fieldingPercentage", 0.0) * 100

    home_strength = (offense(home) * w["offenseWeight"]
                     + defense(home) * w["defenseWeight"]) * w["homeFieldAdvantage"]
    away_strength = offense(away) * w["offenseWeight"] + defense(away) * w["defenseWeight"]

    total = home_strength + away_strength
    if total == 0:
        return 0.5
    return min(0.99, max(0.01, home_strength / total))


def backtest(season: int, start_date: str, end_date: str,
             config_path: str = CONFIG_PATH) -> Dict:
    weights = load_weights(config_path)
    team_stats = fetch_team_model_stats(season)
    results = fetch_results(start_date, end_date, season)

    evaluated = correct = home_wins = 0
    brier_sum = 0.0
    winner_prob_sum = 0.0

    for home_id, away_id, home_won in results:
        if home_id not in team_stats or away_id not in team_stats:
            continue
        p_home = home_win_probability(team_stats[home_id], team_stats[away_id], weights)
        if (p_home >= 0.5) == home_won:
            correct += 1
        prob_for_winner = p_home if home_won else (1.0 - p_home)
        brier_sum += (1.0 - prob_for_winner) ** 2
        winner_prob_sum += prob_for_winner
        home_wins += home_won
        evaluated += 1

    return {
        "season": season,
        "window": f"{start_date}..{end_date}",
        "games_evaluated": evaluated,
        "accuracy": correct / evaluated if evaluated else 0.0,
        "home_field_baseline": home_wins / evaluated if evaluated else 0.0,
        "average_winner_prob": winner_prob_sum / evaluated if evaluated else 0.0,
        "brier_score": brier_sum / evaluated if evaluated else 0.0,
    }


def run_backtest(season: int, start_date: str, end_date: str) -> None:
    print("\n=== Model Backtest vs. Actual MLB Results ===")
    print(f"Season {season}, window {start_date} -> {end_date}")
    print("Model: cpp/GamePredictor.cpp formula with config/config.json weights")
    try:
        results = backtest(season, start_date, end_date)
    except Exception as exc:  # network/API issues
        print(f"Could not reach the MLB Stats API: {exc}")
        return

    if not results["games_evaluated"]:
        print("No completed games found to validate against.")
        return

    print(f"Games evaluated:     {results['games_evaluated']}")
    print(f"Model accuracy:      {results['accuracy']:.2%}")
    print(f"Home-field baseline: {results['home_field_baseline']:.2%}")
    print(f"Edge over baseline:  {results['accuracy'] - results['home_field_baseline']:+.2%}")
    print(f"Avg prob on winners: {results['average_winner_prob']:.2%}")
    print(f"Brier score:         {results['brier_score']:.4f}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--predictions", default="outputs/predictions.txt")
    parser.add_argument("--games", default="outputs/games.txt")
    parser.add_argument("--backtest", action="store_true",
                        help="Backtest the model against actual MLB results from the Stats API")
    parser.add_argument("--season", type=int, default=2025)
    parser.add_argument("--start", default="2025-05-01")
    parser.add_argument("--end", default="2025-10-31")
    args = parser.parse_args()

    if args.backtest:
        run_backtest(args.season, args.start, args.end)
        return

    if not os.path.exists(args.predictions):
        print("Missing predictions file:", args.predictions)
        return

    if not os.path.exists(args.games):
        print("Missing games file:", args.games)
        return

    results = validate(args.predictions, args.games)

    print("\n=== Validation Results ===")
    for k, v in results.items():
        print(f"{k}: {v}")


if __name__ == "__main__":
    main()