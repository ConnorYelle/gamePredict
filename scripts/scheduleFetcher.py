#!/usr/bin/env python3
"""Fetch today's MLB games (with probable starting pitchers) into outputs/games.txt.

Output format (one game per line):

    Home Team | Away Team | Home Starter | Away Starter

Starter fields are left blank when a probable pitcher has not been announced;
the C++ predictor treats a blank/unknown starter as team-only.

CLI facade over :class:`mlb.MlbStatsApi`.
"""

from datetime import datetime
from pathlib import Path

from mlb import MlbStatsApi


def fetch_games(api=None, date_str=None):
    """Return a list of 'Home | Away | HomeSP | AwaySP' strings for the date."""
    api = api or MlbStatsApi()
    date_str = date_str or datetime.now().strftime("%Y-%m-%d")
    print(f"\nFetching games for {date_str}...")

    try:
        games = api.scheduled_games(date_str)
    except Exception as e:
        print(f"Error fetching schedule: {e}")
        return []

    return [f"{g['home']} | {g['away']} | {g['home_sp']} | {g['away_sp']}"
            for g in games]


def save_games(games):
    """Save games to outputs/games.txt."""
    try:
        out_dir = Path("outputs")
        out_dir.mkdir(parents=True, exist_ok=True)
        games_path = out_dir / "games.txt"
        with games_path.open("w", encoding="utf-8") as f:
            for game in games:
                f.write(game + "\n")
        print(f"\nLoaded {len(games)} games into {games_path.name}")
    except Exception as e:
        print(f"Error saving games: {e}")


def main():
    games = fetch_games()
    if games:
        save_games(games)
    else:
        print("\nNo games found. Manually add games to games.txt with the format:")
        print("  Home Team | Away Team | Home Starter | Away Starter")


if __name__ == "__main__":
    main()
