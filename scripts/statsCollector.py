#!/usr/bin/env python3
"""Advanced MLB statistics collector (CLI).

Fetches comprehensive batting/pitching/fielding analytics from
baseball-reference.com and writes them to CSV, with a fallback to the most
recent local data/rawData snapshot when scraping fails.

CLI facade over :class:`mlb.scraper.BaseballReferenceScraper`.
"""

import shutil
from pathlib import Path

from mlb.scraper import BaseballReferenceScraper


def _fallback_to_local_data():
    """Copy the most recent local stats snapshot into place when scraping fails."""
    print("No live stats fetched - attempting fallback to local data/rawData/...\n")
    raw_root = Path('data') / 'rawData'
    if not raw_root.exists():
        print('data/rawData directory not present')
        return

    candidates = [p for p in raw_root.iterdir() if p.is_dir()]
    if not candidates:
        print('No dated folders found under data/rawData')
        return

    latest = max(candidates, key=lambda p: p.name)
    print(f"Using existing stats from {latest}")
    for fn in ['team_batting_stats.csv', 'team_pitching_stats.csv', 'team_fielding_stats.csv']:
        src = latest / fn
        if src.exists():
            try:
                shutil.copy(src, Path(fn))
            except Exception as e:
                print(f"Could not copy {src}: {e}")


def main():
    collector = BaseballReferenceScraper()
    year = 2026

    print("\nCollecting batting statistics...")
    batting_stats = collector.get_team_batting_stats(year)

    print("Collecting pitching statistics...")
    pitching_stats = collector.get_team_pitching_stats(year)

    print("Collecting fielding statistics...")
    fielding_stats = collector.get_team_fielding_stats(year)

    if not batting_stats or not pitching_stats or not fielding_stats:
        _fallback_to_local_data()

    print("\nSaving statistics...")
    collector.save_stats_to_csv(batting_stats, 'team_batting_stats.csv', 'batting')
    collector.save_stats_to_csv(pitching_stats, 'team_pitching_stats.csv', 'pitching')
    collector.save_stats_to_csv(fielding_stats, 'team_fielding_stats.csv', 'fielding')

    print("Creating sample team comparison...")
    if batting_stats and pitching_stats and fielding_stats:
        teams = list(batting_stats.keys())[:2]
        if len(teams) == 2:
            comparison = collector.compile_team_comparison(
                teams[0], teams[1],
                batting_stats, pitching_stats, fielding_stats
            )
            collector.save_comparison_to_json(comparison, 'sample_matchup.json')

    print("\nStatistics collection complete!")
    print("Generated files:")
    print("  - team_batting_stats.csv")
    print("  - team_pitching_stats.csv")
    print("  - team_fielding_stats.csv")
    print("  - sample_matchup.json")


if __name__ == "__main__":
    main()
