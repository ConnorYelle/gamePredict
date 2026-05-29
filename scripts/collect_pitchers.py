#!/usr/bin/env python3
"""Collect today's probable starting pitchers and their stats.

Writes data/rawData/<mm-dd-yy>/StartingPitchers.csv with columns:
    name,era,whip,k9,recentEra
which the C++ predictor loads alongside the team CSVs. ``recentEra`` is the ERA
over the pitcher's most recent starts (recent form). Blank values mean unknown
and are ignored by the model.
"""

import csv
from datetime import datetime
from pathlib import Path

import mlb_data

API = mlb_data.API
ROOT = Path(__file__).resolve().parent.parent


def probable_starters(date_str):
    """Return {pitcher_id: name} for today's announced probable starters."""
    url = f"{API}/schedule?sportId=1&date={date_str}&hydrate=probablePitcher"
    data = mlb_data.fetch_json(url)
    starters = {}
    for day in data.get("dates", []):
        for game in day.get("games", []):
            for side in ("home", "away"):
                pp = game["teams"][side].get("probablePitcher")
                if pp and pp.get("id"):
                    starters[pp["id"]] = pp.get("fullName", "")
    return starters


def _fmt(value):
    """Format a stat for CSV: blank when unknown (negative sentinel)."""
    return "" if value is None or value < 0 else f"{value:.3f}"


def main():
    today = datetime.now()
    date_str = today.strftime("%Y-%m-%d")
    season = today.year

    print(f"Collecting probable starters for {date_str}...")
    try:
        starters = probable_starters(date_str)
    except Exception as e:
        print(f"Could not fetch schedule: {e}")
        starters = {}

    rows = []
    for pid, name in starters.items():
        season_stats = mlb_data.pitcher_season_stats(pid, season) or {}
        rows.append({
            "name": name,
            "era": _fmt(season_stats.get("era")),
            "whip": _fmt(season_stats.get("whip")),
            "k9": _fmt(season_stats.get("k9")),
            "recentEra": _fmt(mlb_data.recent_era(pid, season)),
        })

    out_dir = ROOT / "data" / "rawData" / today.strftime("%m-%d-%y")
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "StartingPitchers.csv"
    with out_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["name", "era", "whip", "k9", "recentEra"])
        writer.writeheader()
        writer.writerows(rows)

    print(f"Wrote {len(rows)} starting pitchers to {out_path}")


if __name__ == "__main__":
    main()
