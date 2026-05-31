#!/usr/bin/env python3
"""Collect today's probable starting pitchers and their stats.

Writes data/rawData/<mm-dd-yy>/StartingPitchers.csv with columns:
    name,era,whip,k9,recentEra,fip
which the C++ predictor loads alongside the team CSVs. ``recentEra`` is the ERA
over the pitcher's most recent starts (recent form); ``fip`` is Fielding
Independent Pitching (a less noisy talent estimate than ERA). Blank values mean
unknown and are ignored by the model.

CLI facade over :class:`mlb.MlbStatsApi`.
"""

import csv
from datetime import datetime

from mlb import MlbStatsApi, config


def _fmt(value):
    """Format a stat for CSV: blank when unknown (negative sentinel)."""
    return "" if value is None or value < 0 else f"{value:.3f}"


def collect_starting_pitchers(api, today=None):
    """Return [{name, era, whip, k9, recentEra}] rows for the day's starters."""
    today = today or datetime.now()
    date_str = today.strftime("%Y-%m-%d")
    season = today.year

    print(f"Collecting probable starters for {date_str}...")
    try:
        starters = api.probable_starters(date_str)
    except Exception as e:
        print(f"Could not fetch schedule: {e}")
        starters = {}

    rows = []
    for pid, name in starters.items():
        season_stats = api.pitcher_season_stats(pid, season) or {}
        rows.append({
            "name": name,
            "era": _fmt(season_stats.get("era")),
            "whip": _fmt(season_stats.get("whip")),
            "k9": _fmt(season_stats.get("k9")),
            "recentEra": _fmt(api.recent_era(pid, season)),
            "fip": _fmt(season_stats.get("fip")),
        })
    return rows


def main():
    today = datetime.now()
    rows = collect_starting_pitchers(MlbStatsApi(), today)

    out_dir = config.ROOT / "data" / "rawData" / today.strftime("%m-%d-%y")
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "StartingPitchers.csv"
    with out_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f, fieldnames=["name", "era", "whip", "k9", "recentEra", "fip"])
        writer.writeheader()
        writer.writerows(rows)

    print(f"Wrote {len(rows)} starting pitchers to {out_path}")


if __name__ == "__main__":
    main()
