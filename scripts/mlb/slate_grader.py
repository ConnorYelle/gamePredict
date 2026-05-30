"""Grade a saved prediction slate against actual outcomes.

Parses ``predictions.txt`` ("Team 55.2%" pairs) and ``games.txt`` (matchup
lines), fuzzy-matches the team names, and reports accuracy / Brier metrics. This
is the text-file counterpart to the live :mod:`mlb.backtester`.
"""

import re
from typing import Dict, List, Tuple


def parse_predictions(path: str) -> List[Dict]:
    """Parse "Team Name 55.2%" lines into [{team_a, prob_a, team_b, prob_b}]."""
    with open(path, encoding="utf-8") as f:
        lines = [l.rstrip() for l in f]

    preds = []
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
    """Parse matchup lines ("Home | Away ..." or "Away @ Home") into pairs."""
    games = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            if "|" in line:
                parts = [x.strip() for x in line.split("|")]
                games.append((parts[0], parts[1]))
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
    # require at least 2 meaningful tokens OR full substring match
    overlap = set(a.split()) & set(b.split())
    return len(overlap) >= 2 or a in b or b in a


def grade_against_results(pred_games: List[Dict], results_rows: List[Dict]) -> Dict:
    """Grade parsed predictions against archived final scores.

    Unlike :func:`validate`, this matches each result to its prediction by team
    name (order-independent), so a saved ``predictions.txt`` can be graded
    against a ``final_scores.csv`` regardless of row ordering. A pick is correct
    when the model assigned the actual winner the higher probability.
    """
    matched = correct = 0
    brier_sum = 0.0
    winner_probs = []

    for res in results_rows:
        home, away, winner = res.get("home", ""), res.get("away", ""), res.get("winner", "")
        if not winner:
            continue

        for pred in pred_games:
            ta, tb = pred["team_a"], pred["team_b"]
            teams_match = ((match_team(home, ta) or match_team(home, tb)) and
                           (match_team(away, ta) or match_team(away, tb)))
            if not teams_match:
                continue

            if match_team(winner, ta):
                p_win, p_other = pred["prob_a"], pred["prob_b"]
            elif match_team(winner, tb):
                p_win, p_other = pred["prob_b"], pred["prob_a"]
            else:
                continue

            matched += 1
            winner_probs.append(p_win)
            if p_win > p_other:
                correct += 1
            brier_sum += (1 - p_win) ** 2
            break

    return {
        "games_predicted": len(pred_games),
        "games_with_results": len(results_rows),
        "matched": matched,
        "accuracy": correct / matched if matched else 0.0,
        "average_winner_prob": sum(winner_probs) / len(winner_probs) if winner_probs else 0.0,
        "brier_score": brier_sum / matched if matched else 0.0,
    }


def validate(predictions_path: str, games_path: str) -> Dict:
    """Grade ``predictions_path`` against ``games_path`` and return metrics."""
    games_pred = parse_predictions(predictions_path)
    games_act = parse_games(games_path)

    matched = correct = 0
    brier_sum = 0.0
    probs_for_winner = []

    for i, pred in enumerate(games_pred):
        if i >= len(games_act):
            break
        winner, _loser = games_act[i]
        team_a, team_b = pred["team_a"], pred["team_b"]
        p_a, p_b = pred["prob_a"], pred["prob_b"]

        if match_team(winner, team_a):
            p_win = p_a
        elif match_team(winner, team_b):
            p_win = p_b
        else:
            continue  # couldn't match team

        matched += 1
        probs_for_winner.append(p_win)

        predicted_correct = (p_a > p_b and match_team(winner, team_a)) or \
                            (p_b > p_a and match_team(winner, team_b))
        if predicted_correct:
            correct += 1
        brier_sum += (1 - p_win) ** 2

    return {
        "games_predicted": len(games_pred),
        "games_actual": len(games_act),
        "matched": matched,
        "accuracy": correct / matched if matched else 0.0,
        "average_winner_prob": (sum(probs_for_winner) / len(probs_for_winner)
                                if probs_for_winner else 0.0),
        "brier_score": brier_sum / matched if matched else 0.0,
    }
