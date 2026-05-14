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
        
        # Parse game_summary divs, each containing a table with teams
        games = []
        
        # Find all game summary sections
        game_pattern = r'<div class="game_summary[^"]*">.*?<table class="teams">.*?</table>.*?</div>'
        game_sections = re.findall(game_pattern, html, re.DOTALL)
        
        print(f"Found {len(game_sections)} game sections")
        
        for game_section in game_sections:
            # Extract team links within this game
            team_pattern = r'<a href="/teams/[^"]+/">([^<]+)</a>'
            teams = re.findall(team_pattern, game_section)
            
            # Each game should have 2 teams (home and away)
            if len(teams) >= 2:
                home_team = teams[0]
                away_team = teams[1]
                games.append(f"{home_team} | {away_team}")
                print(f"  Found: {home_team} vs {away_team}")
        
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
