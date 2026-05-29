#!/usr/bin/env python3
"""
Fetch today's MLB games (with probable starting pitchers) and populate
outputs/games.txt.

Uses the public MLB Stats API, which exposes the announced probable starter for
each side. Output format (one game per line):

    Home Team | Away Team | Home Starter | Away Starter

Starter fields are left blank when a probable pitcher has not been announced;
the C++ predictor treats a blank/unknown starter as team-only.
"""

import json
import urllib.request
from datetime import datetime
from pathlib import Path

SCHEDULE_API = "https://statsapi.mlb.com/api/v1/schedule"


def fetch_json(url):
    req = urllib.request.Request(url, headers={"User-Agent": "gamePrediction"})
    with urllib.request.urlopen(req, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def fetch_games(date_str=None):
    """Return a list of 'Home | Away | HomeSP | AwaySP' strings for the date."""
    date_str = date_str or datetime.now().strftime("%Y-%m-%d")
    print(f"\nFetching games for {date_str}...")

    url = f"{SCHEDULE_API}?sportId=1&date={date_str}&hydrate=probablePitcher"
    try:
        data = fetch_json(url)
    except Exception as e:
        print(f"Error fetching schedule: {e}")
        return []

    games = []
    for day in data.get("dates", []):
        for game in day.get("games", []):
            home = game["teams"]["home"]["team"]["name"]
            away = game["teams"]["away"]["team"]["name"]
            home_sp = (game["teams"]["home"].get("probablePitcher") or {}).get("fullName", "")
            away_sp = (game["teams"]["away"].get("probablePitcher") or {}).get("fullName", "")
            games.append(f"{home} | {away} | {home_sp} | {away_sp}")

    return games


def save_games(games):
    """Save games to outputs/games.txt"""
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


if __name__ == "__main__":
    games = fetch_games()
    if games:
        save_games(games)
    else:
        print("\nNo games found. Manually add games to games.txt with the format:")
        print("  Home Team | Away Team | Home Starter | Away Starter")
