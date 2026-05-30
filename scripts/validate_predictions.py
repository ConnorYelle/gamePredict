#!/usr/bin/env python3
"""Validate model predictions against actual game outcomes (CLI).

Two modes:

1. Default - grade a saved slate (predictions.txt vs games.txt):
       python scripts/validate_predictions.py
           --predictions outputs/predictions.txt
           --games outputs/games.txt

2. Backtest - compare the current model against actual MLB results from the
   Stats API, using the same formula/weights the C++ engine uses:
       python scripts/validate_predictions.py --backtest
           --season 2025 --start 2025-05-01 --end 2025-10-31

3. Results - grade saved predictions against an archived final_scores.csv
   (see scripts/archive_schedule.py), matching games by team name:
       python scripts/validate_predictions.py
           --predictions data/schedules/05-29-26/predictions.txt
           --results data/schedules/05-29-26/final_scores.csv

CLI facade over :mod:`mlb.slate_grader` and :mod:`mlb.backtester`.
"""

import argparse
import csv
import os

from mlb.backtester import run_backtest
from mlb.slate_grader import grade_against_results, parse_predictions, validate


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--predictions", default="outputs/predictions.txt")
    parser.add_argument("--games", default="outputs/games.txt")
    parser.add_argument("--results",
                        help="Grade --predictions against an archived final_scores.csv")
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

    if args.results:
        if not os.path.exists(args.predictions):
            print("Missing predictions file:", args.predictions)
            return
        if not os.path.exists(args.results):
            print("Missing results file:", args.results)
            return
        with open(args.results, encoding="utf-8") as f:
            results_rows = list(csv.DictReader(f))
        pred_games = parse_predictions(args.predictions)
        results = grade_against_results(pred_games, results_rows)
        print("\n=== Validation vs. Archived Scores ===")
        for k, v in results.items():
            print(f"{k}: {v}")
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
