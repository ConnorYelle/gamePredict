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
import os
import re
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


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--predictions", default="outputs/predictions.txt")
    parser.add_argument("--games", default="outputs/games.txt")
    args = parser.parse_args()

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