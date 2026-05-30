#!/usr/bin/env python3
"""Archive past days' schedules with final scores for ongoing validation.

Writes data/schedules/<mm-dd-yy>/final_scores.csv (matchups + actual scores +
winner) for the requested date(s). Defaults to the previous day, so a daily
cron/run keeps building a record you can validate the model against.

Usage:
    python scripts/archive_schedule.py                      # yesterday
    python scripts/archive_schedule.py --date 2026-05-29
    python scripts/archive_schedule.py --start 2026-05-01 --end 2026-05-29

CLI facade over :class:`mlb.MlbStatsApi` + :mod:`mlb.results_archive`.
"""

import argparse
from datetime import datetime, timedelta

from mlb import MlbStatsApi
from mlb.results_archive import ResultsArchive, archive_day, daterange, parse_date


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", help="single date to archive (YYYY-MM-DD)")
    parser.add_argument("--start", help="start of date range (YYYY-MM-DD)")
    parser.add_argument("--end", help="end of date range (YYYY-MM-DD)")
    args = parser.parse_args()

    if args.start or args.end:
        if not (args.start and args.end):
            parser.error("--start and --end must be given together")
        days = list(daterange(parse_date(args.start), parse_date(args.end)))
    elif args.date:
        days = [parse_date(args.date)]
    else:
        days = [datetime.now() - timedelta(days=1)]  # previous day

    api = MlbStatsApi()
    archive = ResultsArchive()
    total = 0
    for day in days:
        try:
            rows, path = archive_day(api, day, archive)
        except Exception as e:
            print(f"{day:%Y-%m-%d}: could not fetch results: {e}")
            continue
        if path:
            print(f"{day:%Y-%m-%d}: saved {len(rows)} final games to {path}")
            total += len(rows)
        else:
            print(f"{day:%Y-%m-%d}: no completed games found")

    print(f"\nArchived {total} games across {len(days)} day(s) under {archive.base_dir}")


if __name__ == "__main__":
    main()
