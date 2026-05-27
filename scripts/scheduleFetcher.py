#!/usr/bin/env python3
"""
Script to fetch MLB games from baseball-reference.com and populate games.txt
Only fetches games for today's date. Uses a robust fallback that attempts to
match known MLB team names in the page HTML if structured game blocks aren't
present.
"""

import urllib.request
import re
from datetime import datetime
from pathlib import Path


def fetch_games():
    """Fetch today's games from baseball-reference.com"""
    try:
        # Get today's date
        today = datetime.now()
        today_str = today.strftime("%A, %B %d, %Y")
        date_param = today.strftime("%Y-%m-%d")

        print(f"\nFetching games for {today_str}...")

        # Try the specific date URL first
        url = f"https://www.baseball-reference.com/previews/{date_param}.shtml"

        html = ''
        try:
            with urllib.request.urlopen(url, timeout=10) as response:
                html = response.read().decode('utf-8')
        except Exception:
            # Fallback to generic previews page
            try:
                url = "https://www.baseball-reference.com/previews/"
                with urllib.request.urlopen(url, timeout=10) as response:
                    html = response.read().decode('utf-8')
            except Exception as e:
                print(f"Error fetching pages: {e}")
                html = ''

        games = []

        # Method 1: Find game summary divs and extract teams from each
        if html:
            game_pattern = r'<div class="game_summary[^>]*>.*?</div>'
            game_sections = re.findall(game_pattern, html, re.DOTALL)

            for idx, game_section in enumerate(game_sections):
                # Extract team links within this game - look for both full names and abbreviations
                team_pattern = r'<a href="/teams/[^"]+/[^"]*">([^<]+)</a>'
                teams = re.findall(team_pattern, game_section)

                # Each game should have 2 teams (home and away)
                if len(teams) >= 2:
                    home_team = teams[0].strip()
                    away_team = teams[1].strip()
                    # Avoid duplicates and obvious non-teams
                    if home_team and away_team and len(home_team) > 2 and len(away_team) > 2:
                        games.append(f"{home_team} | {away_team}")

        # Method 2: If method 1 found nothing, try a simpler approach using known team names
        if not games:
            print("Trying alternative extraction method...")
            # Known MLB team names (normalized)
            TEAM_NAMES = [
                'Arizona Diamondbacks','Atlanta Braves','Baltimore Orioles','Boston Red Sox',
                'Chicago Cubs','Chicago White Sox','Cincinnati Reds','Cleveland Guardians',
                'Colorado Rockies','Detroit Tigers','Houston Astros','Kansas City Royals',
                'Los Angeles Angels','Los Angeles Dodgers','Miami Marlins','Milwaukee Brewers',
                'Minnesota Twins','New York Mets','New York Yankees','Oakland Athletics',
                'Philadelphia Phillies','Pittsburgh Pirates','San Diego Padres','San Francisco Giants',
                'Seattle Mariners','St. Louis Cardinals','Tampa Bay Rays','Texas Rangers',
                'Toronto Blue Jays','Washington Nationals'
            ]

            # Find occurrences of team names in the HTML in order
            occurrences = []
            lowered = html.lower()
            for name in TEAM_NAMES:
                name_l = name.lower()
                idx = 0
                while True:
                    found = lowered.find(name_l, idx)
                    if found == -1:
                        break
                    occurrences.append((found, name))
                    idx = found + len(name_l)

            # Sort by position and pair them sequentially
            occurrences.sort(key=lambda x: x[0])
            names_in_order = [n for (_, n) in occurrences]

            for i in range(0, len(names_in_order) - 1, 2):
                home = names_in_order[i].strip()
                away = names_in_order[i+1].strip()
                if home and away and len(home) > 2 and len(away) > 2:
                    game = f"{home} | {away}"
                    if game not in games:
                        games.append(game)

        return games

    except Exception as e:
        print(f"Error fetching games: {e}")
        import traceback
        traceback.print_exc()
        return []


def save_games(games):
    """Save games to outputs/games.txt"""
    try:
        out_dir = Path('outputs')
        out_dir.mkdir(parents=True, exist_ok=True)
        games_path = out_dir / 'games.txt'
        with games_path.open('w', encoding='utf-8') as f:
            for game in games:
                f.write(game + '\n')

        print(f"\nLoaded {len(games)} games into {games_path.name}")
    except Exception as e:
        print(f"Error saving games: {e}")


if __name__ == "__main__":
    games = fetch_games()
    if games:
        save_games(games)
    else:
        print("\nNo games found. Manually add games to games.txt with the format:")
        print("  Home Team | Away Team")

