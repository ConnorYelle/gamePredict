#!/usr/bin/env python3
"""Track model metrics (accuracy / Brier / log-loss) across model changes.

Run this after each change to your model or weights. It backtests the current
config against real MLB results, appends the metrics to data/metrics_history.jsonl
with your note and the current git commit, then prints the full history so you can
see whether the change helped.

Usage:
    python scripts/track_metrics.py -n "added bullpen weight"   # backtest + record
    python scripts/track_metrics.py --show                      # just show history
    python scripts/track_metrics.py -n "tuned probScale" \
        --season 2025 --start 2025-05-01 --end 2025-10-31

CLI facade over :mod:`mlb.backtester` and :mod:`mlb.metrics_log`.
"""

import argparse

from mlb import config, metrics_log
from mlb.backtester import run_backtest


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("-n", "--note", default="",
                        help="label for this run (e.g. what you changed)")
    parser.add_argument("--show", action="store_true",
                        help="only print the recorded history; do not run a backtest")
    parser.add_argument("--season", type=int, default=2025)
    parser.add_argument("--start", default="2025-05-01")
    parser.add_argument("--end", default="2025-10-31")
    parser.add_argument("--no-pitchers", action="store_true",
                        help="backtest with team stats only (skip starting pitchers)")
    args = parser.parse_args()

    if not args.show:
        use_pitchers = not args.no_pitchers
        weights = config.load_weights()
        results = run_backtest(args.season, args.start, args.end,
                               use_pitchers=use_pitchers)
        if results:
            metrics_log.log_run(
                results, weights, note=args.note, season=args.season,
                window=(args.start, args.end), use_pitchers=use_pitchers)
            print(f"\nRecorded to {metrics_log.HISTORY_PATH}")
        else:
            print("\nNo metrics recorded (backtest produced no results).")

    print("\n=== Metrics history ===")
    print(metrics_log.format_table(metrics_log.load_history()))


if __name__ == "__main__":
    main()
