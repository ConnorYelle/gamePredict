#!/usr/bin/env python3
"""
Script to fetch MLB games from baseball-reference.com and populate games.txt
Only fetches games for today's date.
"""

import urllib.request
import re
from datetime import datetime

def fetch_games():
    """Fetch today's games from baseball-reference.com"""
    try:
        # Get today's date
        today = datetime.now()
        today_str = today.strftime("%A, %B %d, %Y")
        date_param = today.strftime("%Y-%m-%d")
        
        print(f"Fetching games for {today_str}...")
        
        # Try the specific date URL first
        url = f"https://www.baseball-reference.com/previews/{date_param}.shtml"
        print(f"Fetching from {url}")
        
        try:
            with urllib.request.urlopen(url, timeout=10) as response:
                html = response.read().decode('utf-8')
        except:
            # Fallback to generic previews page
            print("Trying generic previews page...")
            url = "https://www.baseball-reference.com/previews/"
            with urllib.request.urlopen(url, timeout=10) as response:
                html = response.read().decode('utf-8')
        
        games = []
        
        # Method 1: Find game summary divs and extract teams from each
        game_pattern = r'<div class="game_summary[^>]*>.*?</div>'
        game_sections = re.findall(game_pattern, html, re.DOTALL)
        
        print(f"Found {len(game_sections)} game sections")
        
        for idx, game_section in enumerate(game_sections):
            # Extract team links within this game - look for both full names and abbreviations
            team_pattern = r'<a href="/teams/[^"]+/[^"]*">([^<]+)</a>'
            teams = re.findall(team_pattern, game_section)
            
            # Debug output
            if teams:
                print(f"  Game {idx+1}: Found {len(teams)} teams: {teams}")
            
            # Each game should have 2 teams (home and away)
            if len(teams) >= 2:
                home_team = teams[0].strip()
                away_team = teams[1].strip()
                # Avoid duplicates and obvious non-teams
                if home_team and away_team and len(home_team) > 2 and len(away_team) > 2:
                    games.append(f"{home_team} | {away_team}")
        
        # Method 2: If method 1 found nothing, try a simpler approach
        if not games:
            print("\nTrying alternative extraction method...")
            # Find all team links in the entire page and pair them
            team_pattern = r'<a href="/teams/[^"]+/\d+\.shtml">([^<]+)</a>'
            all_teams = re.findall(team_pattern, html)
            
            print(f"Found {len(all_teams)} total team links")
            
            # Group into pairs
            for i in range(0, len(all_teams) - 1, 2):
                home = all_teams[i].strip()
                away = all_teams[i+1].strip()
                if home and away and len(home) > 2 and len(away) > 2:
                    game = f"{home} | {away}"
                    # Avoid duplicates
                    if game not in games:
                        games.append(game)
                        print(f"  Found: {game}")
        
        return games
        
    except Exception as e:
        print(f"Error fetching games: {e}")
        import traceback
        traceback.print_exc()
        return []

def save_games(games):
    """Save games to games.txt"""
    try:
        with open('games.txt', 'w') as f:
            for game in games:
                f.write(game + '\n')
        
        print(f"\n✓ Loaded {len(games)} games into games.txt")
        if games:
            print("\nGames:")
            for game in games:
                print(f"  {game}")
    except Exception as e:
        print(f"Error saving games: {e}")

if __name__ == "__main__":
    games = fetch_games()
    if games:
        save_games(games)
    else:
        print("\nNo games found. Manually add games to games.txt with the format:")
        print("  Home Team | Away Team")

