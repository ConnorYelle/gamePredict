#!/usr/bin/env python3
"""Validate model predictions against actual game outcomes.

Two modes:

1. Default - grade a saved slate (predictions.txt vs games.txt):
       python scripts/validate_predictions.py
           --predictions outputs/predictions.txt
           --games outputs/games.txt

2. Backtest - compare the current model against actual MLB results pulled from
   the Stats API, using the same formula/weights the C++ engine uses
   (cpp/GamePredictor.cpp), including the starting-pitcher term:
       python scripts/validate_predictions.py --backtest
           --season 2025 --start 2025-05-01 --end 2025-10-31

Metrics: accuracy, Brier score, average probability assigned to winners, and a
home-field baseline (backtest only).
"""

import argparse
import os
import re
from typing import List, Tuple, Dict, Optional

import mlb_data


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
                # Format: Home | Away [| HomeStarter | AwayStarter]
                parts = [x.strip() for x in line.split("|")]
                left, right = parts[0], parts[1]
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
# Backtest mode
# ---------------------------------------------------------------------------
def build_game_inputs(season: int, start_date: str, end_date: str,
                      use_pitchers: bool = True, use_cache: bool = True) -> List[Dict]:
    """Assemble per-game model inputs (team stats, pitcher stats, label) for a
    season window, pulling everything needed from the Stats API."""
    team_stats = mlb_data.team_model_stats(season, use_cache=use_cache)
    games = mlb_data.season_games(start_date, end_date, season, use_cache=use_cache)

    season_cache: Dict[int, Optional[Dict]] = {}

    def pitcher_inputs(pid, date):
        if not use_pitchers or not pid:
            return None
        if pid not in season_cache:
            season_cache[pid] = mlb_data.pitcher_season_stats(pid, season, use_cache=use_cache)
        base = season_cache[pid]
        if base is None:
            return None
        p = dict(base)
        p["recentEra"] = mlb_data.recent_era(pid, season, before_date=date,
                                              use_cache=use_cache)
        return p

    inputs = []
    for g in games:
        if g["home_id"] not in team_stats or g["away_id"] not in team_stats:
            continue
        inputs.append({
            "home": team_stats[g["home_id"]],
            "away": team_stats[g["away_id"]],
            "home_sp": pitcher_inputs(g["home_sp_id"], g["date"]),
            "away_sp": pitcher_inputs(g["away_sp_id"], g["date"]),
            "home_won": g["home_won"],
        })
    return inputs


def evaluate(inputs: List[Dict], weights: Dict[str, float]) -> Dict:
    evaluated = correct = home_wins = 0
    brier_sum = winner_prob_sum = 0.0

    for g in inputs:
        p_home = mlb_data.home_win_probability(g["home"], g["away"],
                                               g["home_sp"], g["away_sp"], weights)
        if (p_home >= 0.5) == g["home_won"]:
            correct += 1
        prob_for_winner = p_home if g["home_won"] else (1.0 - p_home)
        brier_sum += (1.0 - prob_for_winner) ** 2
        winner_prob_sum += prob_for_winner
        home_wins += g["home_won"]
        evaluated += 1

    return {
        "games_evaluated": evaluated,
        "accuracy": correct / evaluated if evaluated else 0.0,
        "home_field_baseline": home_wins / evaluated if evaluated else 0.0,
        "average_winner_prob": winner_prob_sum / evaluated if evaluated else 0.0,
        "brier_score": brier_sum / evaluated if evaluated else 0.0,
    }


def run_backtest(season: int, start_date: str, end_date: str,
                 use_pitchers: bool = True) -> None:
    print("\n=== Model Backtest vs. Actual MLB Results ===")
    print(f"Season {season}, window {start_date} -> {end_date}")
    print("Model: cpp/GamePredictor.cpp formula with config/config.json weights")
    print(f"Starting pitcher: {'included' if use_pitchers else 'excluded'}")
    try:
        weights = mlb_data.load_weights()
        inputs = build_game_inputs(season, start_date, end_date, use_pitchers)
    except Exception as exc:  # network/API issues
        print(f"Could not reach the MLB Stats API: {exc}")
        return

    results = evaluate(inputs, weights)
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
    parser.add_argument("--no-pitchers", action="store_true",
                        help="Backtest with team stats only (skip starting pitchers)")
    args = parser.parse_args()

    if args.backtest:
        run_backtest(args.season, args.start, args.end, use_pitchers=not args.no_pitchers)
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
