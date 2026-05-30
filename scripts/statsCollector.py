#!/usr/bin/env python3
"""Collect today's team season stats from the MLB Stats API (CLI).

Writes ``data/rawData/<mm-dd-yy>/TeamStandardBatting.txt`` and
``TeamFielding.txt`` in the column layout the C++ predictor reads.

Idempotent by design: if today's stat files already exist, the API is NOT
called again, so re-running the pipeline later in the day reuses what was
already collected. Pass ``--force`` to refetch regardless.

CLI facade over :class:`mlb.MlbStatsApi` + :mod:`mlb.raw_stats`.
"""

import argparse
from datetime import datetime

from mlb import MlbStatsApi, config
from mlb import raw_stats


def stats_dir_for(today):
    """The data/rawData folder a given day's stats belong in."""
    return config.ROOT / "data" / "rawData" / today.strftime("%m-%d-%y")


def collect_team_stats(api, today=None, force=False):
    """Fetch and write today's team stat files.

    Returns ``(out_dir, wrote)`` where ``wrote`` is False when the step was
    skipped (already collected) or the API could not be reached.
    """
    today = today or datetime.now()
    out_dir = stats_dir_for(today)

    if not force and raw_stats.is_populated(out_dir):
        print(f"Team stats already collected for {today:%Y-%m-%d}; "
              f"skipping API call ({out_dir}).")
        return out_dir, False

    season = today.year
    print(f"Fetching {season} team stats from the MLB Stats API...")
    try:
        teams = api.team_standard_stats(season)
    except Exception as e:
        print(f"Could not fetch team stats from MLB Stats API: {e}")
        print("Predictor will fall back to the most recent local stats.")
        return out_dir, False

    rows = sorted((t for t in teams.values() if t.get("name")),
                  key=lambda t: t["name"])
    if not rows:
        print("MLB Stats API returned no team stats; nothing written.")
        return out_dir, False

    batting, fielding = raw_stats.write_stat_files(rows, out_dir)
    print(f"Wrote {len(rows)} teams' stats to {batting.name} / {fielding.name} "
          f"in {out_dir}")
    return out_dir, True


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--force", action="store_true",
                        help="refetch even if today's stat files already exist")
    args = parser.parse_args()
    collect_team_stats(MlbStatsApi(), force=args.force)


if __name__ == "__main__":
    main()
