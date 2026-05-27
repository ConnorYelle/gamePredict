#!/usr/bin/env python3
"""Validate model predictions against actual game outcomes.

Usage: python scripts/validate_predictions.py [--predictions outputs/predictions.txt] [--games outputs/games.txt]

Reports:
- number of games matched to outcomes
- pick accuracy (fraction of favorites that won)
- Brier score (mean squared error of predicted win probabilities)
- average probability assigned to actual winners
"""
import argparse
import os
import re
from typing import List, Tuple, Dict, Optional


def parse_predictions(path: str) -> List[Dict]:
    with open(path, encoding="utf-8") as f:
        lines = [l.rstrip() for l in f]

    preds = []
    # collect lines that contain a percentage like 'Team Name    55.2%'
    pct_re = re.compile(r"^(.*?)\s+(\d{1,2}\.\d)%$|^(.*?)\s+(\d{1,2}%)$")

    # Simpler approach: find lines that end with '%' and parse name and percent
    for i, line in enumerate(lines):
        if line.strip().endswith('%'):
            # split by runs of spaces before the percent value
            m = re.match(r"^(.+?)\s+(\d{1,2}\.\d)%$", line)
            if not m:
                m = re.match(r"^(.+?)\s+(\d{1,2})%$", line)
            if m:
                name = m.group(1).strip()
                pct = float(m.group(2)) / 100.0
                preds.append((name, pct))

    # preds contains alternating team/prob lines for each game
    games = []
    for i in range(0, len(preds), 2):
        try:
            team_a, prob_a = preds[i]
            team_b, prob_b = preds[i + 1]
        except IndexError:
            break
        games.append({
            'team_a': team_a,
            'prob_a': prob_a,
            'team_b': team_b,
            'prob_b': prob_b,
        })

    return games


def parse_games(path: str) -> List[Tuple[str, str]]:
    pairs = []
    with open(path, encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            if '|' in line:
                left, right = [p.strip() for p in line.split('|', 1)]
                # assume format Winner | Loser
                pairs.append((left, right))
            else:
                # fallback: try 'Team at Team' or similar
                parts = line.split('@')
                if len(parts) == 2:
                    away = parts[0].strip()
                    home = parts[1].strip()
                    pairs.append((away, home))
    return pairs


def match_team(win_label: str, pred_team: str) -> bool:
    # fuzzy but simple matching: check substrings and token overlap
    a = re.sub(r"[^a-z0-9 ]", "", win_label.lower())
    b = re.sub(r"[^a-z0-9 ]", "", pred_team.lower())
    if a == b:
        return True
    if a in b or b in a:
        return True
    a_tokens = set(a.split())
    b_tokens = set(b.split())
    if a_tokens & b_tokens:
        # require at least one meaningful token (non generic like 'team' etc.)
        return True
    return False


def validate(predictions_path: str, games_path: str) -> Dict:
    """Run validation and return metric dictionary instead of printing.

    Returns a dict with keys: predictions_parsed, actual_parsed, matched, unmatched,
    pick_accuracy, average_prob, brier, stats_dir
    """
    games_pred = parse_predictions(predictions_path)
    games_act = parse_games(games_path)

    matched = 0
    unmatched = 0
    correct = 0
    total = 0
    probs_for_winner = []
    brier_sum = 0.0

    # iterate through predictions and try to find a corresponding actual game in order
    for i, pred in enumerate(games_pred):
        total += 1
        # try to find the corresponding actual outcome by searching the list by index
        winner = None
        loser = None
        if i < len(games_act):
            winner, loser = games_act[i]

        p_a = pred['prob_a']
        p_b = pred['prob_b']
        team_a = pred['team_a']
        team_b = pred['team_b']

        matched_flag = False
        assigned_prob_for_winner: Optional[float] = None

        if winner:
            if match_team(winner, team_a):
                assigned_prob_for_winner = p_a
                matched_flag = True
            elif match_team(winner, team_b):
                assigned_prob_for_winner = p_b
                matched_flag = True

        if matched_flag and assigned_prob_for_winner is not None:
            matched += 1
            probs_for_winner.append(assigned_prob_for_winner)
            # consider a correct pick if assigned_prob_for_winner > 0.5
            if assigned_prob_for_winner > 0.5:
                correct += 1
            # brier contribution: (outcome - prob)^2 where outcome=1 for winner
            brier_sum += (1.0 - assigned_prob_for_winner) ** 2
        else:
            unmatched += 1

    acc = correct / matched if matched else 0.0
    avg_prob = sum(probs_for_winner) / len(probs_for_winner) if probs_for_winner else 0.0
    brier = brier_sum / matched if matched else 0.0

    # attempt to detect stats directory used by predictions file
    stats_dir = None
    with open(predictions_path, encoding='utf-8') as f:
        for line in f:
            if 'Loading stats from' in line:
                parts = line.split('Loading stats from', 1)[1].strip()
                stats_dir = parts
                break

    return {
        'predictions_parsed': len(games_pred),
        'actual_parsed': len(games_act),
        'matched': matched,
        'unmatched': unmatched,
        'pick_accuracy': acc,
        'average_prob': avg_prob,
        'brier': brier,
        'stats_dir': stats_dir,
    }


def main():
    p = argparse.ArgumentParser(description='Validate predictions against actual outcomes')
    p.add_argument('--predictions', default='outputs/predictions.txt')
    p.add_argument('--games', default='outputs/games.txt')
    args = p.parse_args()

    if not os.path.exists(args.predictions):
        print('Predictions file not found:', args.predictions)
        return
    if not os.path.exists(args.games):
        print('Games file not found:', args.games)
        return

    validate(args.predictions, args.games)


if __name__ == '__main__':
    main()
