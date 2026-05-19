#!/usr/bin/env python3
"""
Advanced MLB Statistics Collector
Fetches comprehensive baseball analytics from baseball-reference.com
Includes traditional, advanced, and predictive metrics for game prediction
"""

import urllib.request
import urllib.parse
import json
import re
import csv
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional
import time

class BaseballStatsCollector:
    """Collects advanced baseball statistics for prediction modeling"""
    
    def __init__(self):
        self.base_url = "https://www.baseball-reference.com"
        self.stats_cache = {}
        self.session_delay = 0.5  # Respect rate limiting
        
    def fetch_url(self, url: str) -> Optional[str]:
        """Fetch URL with error handling and rate limiting"""
        try:
            print(f"Fetching: {url}")
            req = urllib.request.Request(
                url,
                headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
            )
            with urllib.request.urlopen(req, timeout=10) as response:
                time.sleep(self.session_delay)
                return response.read().decode('utf-8')
        except Exception as e:
            print(f"Error fetching {url}: {e}")
            return None

    def extract_table_data(self, html: str, table_id: str) -> List[Dict]:
        """Extract HTML table data into list of dictionaries"""
        try:
            # Find table by ID
            table_pattern = f'<table[^>]*id="{table_id}"[^>]*>.*?</table>'
            table_match = re.search(table_pattern, html, re.DOTALL)
            if not table_match:
                return []
            
            table_html = table_match.group(0)
            
            # Extract headers
            header_pattern = r'<th[^>]*scope="col"[^>]*>([^<]+)</th>'
            headers = re.findall(header_pattern, table_html)
            headers = [h.strip() for h in headers if h.strip()]
            
            # Extract rows
            rows_pattern = r'<tr[^>]*>.*?</tr>'
            rows = re.findall(rows_pattern, table_html, re.DOTALL)
            
            data = []
            for row in rows[1:]:  # Skip header row
                cells_pattern = r'<td[^>]*>([^<]*)</td>'
                cells = re.findall(cells_pattern, row)
                
                if cells and len(cells) >= len(headers):
                    row_dict = {}
                    for i, header in enumerate(headers):
                        if i < len(cells):
                            row_dict[header] = cells[i].strip()
                    data.append(row_dict)
            
            return data
        except Exception as e:
            print(f"Error extracting table {table_id}: {e}")
            return []

    def get_team_batting_stats(self, year: int = 2026) -> Dict:
        """Fetch comprehensive team batting statistics"""
        url = f"{self.base_url}/leagues/MLB/{year}/batting.shtml"
        html = self.fetch_url(url)
        if not html:
            return {}
        
        stats = self.extract_table_data(html, "teams_standard_batting")
        
        # Parse and enhance with derived metrics
        team_stats = {}
        for stat in stats:
            if 'Team' not in stat:
                continue
            
            team = stat.get('Team', '').strip()
            if not team:
                continue
            
            team_data = {
                'team': team,
                'games': self._to_num(stat.get('G')),
                'at_bats': self._to_num(stat.get('AB')),
                'runs': self._to_num(stat.get('R')),
                'hits': self._to_num(stat.get('H')),
                'doubles': self._to_num(stat.get('2B')),
                'triples': self._to_num(stat.get('3B')),
                'home_runs': self._to_num(stat.get('HR')),
                'rbis': self._to_num(stat.get('RBI')),
                'stolen_bases': self._to_num(stat.get('SB')),
                'caught_stealing': self._to_num(stat.get('CS')),
                'batting_avg': self._to_num(stat.get('BA')),
                'on_base_pct': self._to_num(stat.get('OBP')),
                'slugging_pct': self._to_num(stat.get('SLG')),
                'ops': self._to_num(stat.get('OPS')),
                'ops_plus': self._to_num(stat.get('OPS+')),
                'strikeouts': self._to_num(stat.get('SO')),
                'walks': self._to_num(stat.get('BB')),
            }
            
            # Calculate derived metrics
            if team_data['at_bats'] > 0:
                team_data['iso'] = team_data['slugging_pct'] - team_data['batting_avg']  # Isolated Power
                team_data['babip'] = self._calc_babip(team_data)
            
            team_stats[team] = team_data
        
        return team_stats

    def get_team_pitching_stats(self, year: int = 2026) -> Dict:
        """Fetch comprehensive team pitching statistics"""
        url = f"{self.base_url}/leagues/MLB/{year}/pitching.shtml"
        html = self.fetch_url(url)
        if not html:
            return {}
        
        stats = self.extract_table_data(html, "teams_standard_pitching")
        
        team_stats = {}
        for stat in stats:
            if 'Team' not in stat:
                continue
            
            team = stat.get('Team', '').strip()
            if not team:
                continue
            
            team_data = {
                'team': team,
                'games': self._to_num(stat.get('G')),
                'innings_pitched': self._to_num(stat.get('IP')),
                'wins': self._to_num(stat.get('W')),
                'losses': self._to_num(stat.get('L')),
                'era': self._to_num(stat.get('ERA')),
                'games_finished': self._to_num(stat.get('GF')),
                'saves': self._to_num(stat.get('SV')),
                'hits_allowed': self._to_num(stat.get('H')),
                'runs_allowed': self._to_num(stat.get('R')),
                'earned_runs': self._to_num(stat.get('ER')),
                'home_runs_allowed': self._to_num(stat.get('HR')),
                'walks': self._to_num(stat.get('BB')),
                'strikeouts': self._to_num(stat.get('SO')),
                'whip': self._to_num(stat.get('WHIP')),
                'k_per_9': self._to_num(stat.get('K/9')),
                'bb_per_9': self._to_num(stat.get('BB/9')),
                'quality_starts': self._to_num(stat.get('QS')),
            }
            
            # Calculate derived metrics
            if team_data['innings_pitched'] > 0:
                team_data['k_bb_ratio'] = self._safe_div(team_data['strikeouts'], 
                                                         team_data['walks'] + 1)
                # FIP approximation (Fielding Independent Pitching)
                team_data['fip'] = self._calc_fip(team_data)
                # LOB% (Left on Base percentage)
                team_data['lob_pct'] = self._calc_lob_pct(team_data)
            
            team_stats[team] = team_data
        
        return team_stats

    def get_team_fielding_stats(self, year: int = 2026) -> Dict:
        """Fetch team fielding statistics"""
        url = f"{self.base_url}/leagues/MLB/{year}/fielding.shtml"
        html = self.fetch_url(url)
        if not html:
            return {}
        
        stats = self.extract_table_data(html, "teams_standard_fielding")
        
        team_stats = {}
        for stat in stats:
            if 'Team' not in stat:
                continue
            
            team = stat.get('Team', '').strip()
            if not team:
                continue
            
            team_data = {
                'team': team,
                'innings': self._to_num(stat.get('Inning')),
                'games': self._to_num(stat.get('G')),
                'putouts': self._to_num(stat.get('PO')),
                'assists': self._to_num(stat.get('A')),
                'errors': self._to_num(stat.get('E')),
                'double_plays': self._to_num(stat.get('DP')),
                'fielding_pct': self._to_num(stat.get('Fld%')),
            }
            
            team_stats[team] = team_data
        
        return team_stats

    def calculate_strength_of_schedule(self, team: str, year: int = 2026) -> Dict:
        """Calculate strength of schedule and recent performance"""
        try:
            # Construct team schedule URL
            team_abbr = self._get_team_abbr(team)
            if not team_abbr:
                return {}
            
            url = f"{self.base_url}/teams/{team_abbr}/{year}-schedule-games.shtml"
            html = self.fetch_url(url)
            if not html:
                return {}
            
            # Extract recent games (last 10)
            recent_wins = 0
            recent_games = 0
            recent_runs_for = 0
            recent_runs_against = 0
            
            # Parse schedule table
            game_rows = re.findall(r'<tr[^>]*>.*?</tr>', html, re.DOTALL)[-10:]
            
            for row in game_rows:
                # Extract W/L
                result = re.search(r'<td[^>]*>([WL])</td>', row)
                if result:
                    recent_games += 1
                    if result.group(1) == 'W':
                        recent_wins += 1
                
                # Extract runs
                r_match = re.search(r'<td[^>]*>(\d+)</td>', row)
                ra_match = re.findall(r'<td[^>]*>(\d+)</td>', row)
                if ra_match and len(ra_match) >= 2:
                    recent_runs_for += int(ra_match[0])
                    recent_runs_against += int(ra_match[1])
            
            return {
                'recent_record': f"{recent_wins}-{recent_games - recent_wins}",
                'recent_win_pct': recent_wins / recent_games if recent_games > 0 else 0,
                'recent_avg_runs_for': recent_runs_for / recent_games if recent_games > 0 else 0,
                'recent_avg_runs_against': recent_runs_against / recent_games if recent_games > 0 else 0,
                'recent_run_differential': (recent_runs_for - recent_runs_against) / recent_games if recent_games > 0 else 0,
            }
        except Exception as e:
            print(f"Error calculating SOS for {team}: {e}")
            return {}

    def compile_team_comparison(self, team1: str, team2: str, 
                               batting: Dict, pitching: Dict, fielding: Dict) -> Dict:
        """Compile comprehensive comparison between two teams"""
        comparison = {
            'matchup': f"{team1} vs {team2}",
            'home_team': team1,
            'away_team': team2,
            'timestamp': datetime.now().isoformat(),
        }
        
        # Batting comparison
        if team1 in batting and team2 in batting:
            comparison['batting'] = {
                'home': batting[team1],
                'away': batting[team2],
                'home_ops_advantage': batting[team1].get('ops', 0) - batting[team2].get('ops', 0),
                'home_runs_diff': batting[team1].get('home_runs', 0) - batting[team2].get('home_runs', 0),
            }
        
        # Pitching comparison
        if team1 in pitching and team2 in pitching:
            comparison['pitching'] = {
                'home': pitching[team1],
                'away': pitching[team2],
                'home_era_advantage': pitching[team2].get('era', 0) - pitching[team1].get('era', 0),  # Lower is better
                'home_whip_advantage': pitching[team2].get('whip', 0) - pitching[team1].get('whip', 0),
            }
        
        # Fielding comparison
        if team1 in fielding and team2 in fielding:
            comparison['fielding'] = {
                'home': fielding[team1],
                'away': fielding[team2],
                'home_fielding_pct_advantage': fielding[team1].get('fielding_pct', 0) - fielding[team2].get('fielding_pct', 0),
            }
        
        return comparison

    def save_stats_to_csv(self, stats: Dict, filename: str, category: str):
        """Save statistics to CSV file"""
        try:
            if not stats:
                print(f"No data to save for {filename}")
                return
            
            # Get first item to determine keys
            first_item = next(iter(stats.values()))
            keys = first_item.keys()
            
            with open(filename, 'w', newline='') as f:
                writer = csv.DictWriter(f, fieldnames=keys)
                writer.writeheader()
                writer.writerows(stats.values())
            
            print(f"Saved {len(stats)} teams' {category} stats to {filename}")
        except Exception as e:
            print(f"Error saving to {filename}: {e}")

    def save_comparison_to_json(self, comparison: Dict, filename: str):
        """Save comparison data to JSON"""
        try:
            with open(filename, 'w') as f:
                json.dump(comparison, f, indent=2)
            print(f"Saved comparison to {filename}")
        except Exception as e:
            print(f"Error saving comparison: {e}")

    # Helper methods
    @staticmethod
    def _to_num(value: str, default: float = 0.0) -> float:
        """Convert string to number, handling empty/invalid values"""
        if not value or value == '':
            return default
        try:
            return float(value)
        except ValueError:
            return default

    @staticmethod
    def _safe_div(numerator: float, denominator: float, default: float = 0.0) -> float:
        """Safe division with default"""
        if denominator == 0:
            return default
        return numerator / denominator

    @staticmethod
    def _calc_babip(team_data: Dict) -> float:
        """Calculate BABIP (Batting Average on Balls In Play)"""
        hits = team_data.get('hits', 0)
        home_runs = team_data.get('home_runs', 0)
        at_bats = team_data.get('at_bats', 0)
        strikeouts = team_data.get('strikeouts', 0)
        
        denominator = at_bats - strikeouts - home_runs + 0.1
        numerator = hits - home_runs
        
        return BaseballStatsCollector._safe_div(numerator, denominator)

    @staticmethod
    def _calc_fip(team_data: Dict) -> float:
        """Calculate FIP (Fielding Independent Pitching)"""
        hr = team_data.get('home_runs_allowed', 0)
        walks = team_data.get('walks', 0)
        strikeouts = team_data.get('strikeouts', 0)
        innings = team_data.get('innings_pitched', 1)
        
        fip = ((13 * hr) + (3 * walks) - (2 * strikeouts)) / innings + 3.20
        return fip

    @staticmethod
    def _calc_lob_pct(team_data: Dict) -> float:
        """Calculate LOB% (Left On Base percentage)"""
        hits = team_data.get('hits_allowed', 0)
        hr = team_data.get('home_runs_allowed', 0)
        runs = team_data.get('runs_allowed', 0)
        
        numerator = hits + team_data.get('walks', 0) - (1.4 * runs)
        denominator = hits + team_data.get('walks', 0) - hr
        
        return BaseballStatsCollector._safe_div(numerator, denominator)

    @staticmethod
    def _get_team_abbr(team: str) -> Optional[str]:
        """Get team abbreviation from team name"""
        # Mapping of common team names to baseball-reference abbreviations
        abbr_map = {
            'Arizona Diamondbacks': 'ARI', 'Atlanta Braves': 'ATL', 'Baltimore Orioles': 'BAL',
            'Boston Red Sox': 'BOS', 'Chicago Cubs': 'CHC', 'Chicago White Sox': 'CWS',
            'Cincinnati Reds': 'CIN', 'Cleveland Guardians': 'CLE', 'Colorado Rockies': 'COL',
            'Detroit Tigers': 'DET', 'Houston Astros': 'HOU', 'Kansas City Royals': 'KCR',
            'Los Angeles Angels': 'LAA', 'Los Angeles Dodgers': 'LAD', 'Miami Marlins': 'MIA',
            'Milwaukee Brewers': 'MIL', 'Minnesota Twins': 'MIN', 'New York Mets': 'NYM',
            'New York Yankees': 'NYY', 'Oakland Athletics': 'OAK', 'Philadelphia Phillies': 'PHI',
            'Pittsburgh Pirates': 'PIT', 'San Diego Padres': 'SDP', 'San Francisco Giants': 'SFG',
            'Seattle Mariners': 'SEA', 'St. Louis Cardinals': 'STL', 'Tampa Bay Rays': 'TBR',
            'Texas Rangers': 'TEX', 'Toronto Blue Jays': 'TOR', 'Washington Nationals': 'WSH',
        }
        return abbr_map.get(team, None)


def main():
    """Main execution"""
    collector = BaseballStatsCollector()
    year = 2026
    
    print("=" * 60)
    print("MLB ADVANCED STATISTICS COLLECTOR")
    print("=" * 60)
    print()
    
    # Fetch all statistics
    print("📊 Collecting batting statistics...")
    batting_stats = collector.get_team_batting_stats(year)
    
    print("📊 Collecting pitching statistics...")
    pitching_stats = collector.get_team_pitching_stats(year)
    
    print("📊 Collecting fielding statistics...")
    fielding_stats = collector.get_team_fielding_stats(year)
    
    # Save to CSV
    print()
    print("💾 Saving statistics...")
    collector.save_stats_to_csv(batting_stats, 'team_batting_stats.csv', 'batting')
    collector.save_stats_to_csv(pitching_stats, 'team_pitching_stats.csv', 'pitching')
    collector.save_stats_to_csv(fielding_stats, 'team_fielding_stats.csv', 'fielding')
    
    # Example: Create comparison for a hypothetical matchup
    print()
    print("📋 Creating sample team comparison...")
    if batting_stats and pitching_stats and fielding_stats:
        teams = list(batting_stats.keys())[:2]
        if len(teams) == 2:
            comparison = collector.compile_team_comparison(
                teams[0], teams[1],
                batting_stats, pitching_stats, fielding_stats
            )
            collector.save_comparison_to_json(comparison, 'sample_matchup.json')
    
    print()
    print("=" * 60)
    print("✓ Statistics collection complete!")
    print("=" * 60)
    print()
    print("Generated files:")
    print("  - team_batting_stats.csv")
    print("  - team_pitching_stats.csv")
    print("  - team_fielding_stats.csv")
    print("  - sample_matchup.json")
    print()
    print("Advanced metrics included:")
    print("  Batting: OPS+, ISO (Isolated Power), BABIP")
    print("  Pitching: K/BB ratio, FIP, LOB%")
    print("  Fielding: Error rates, double play efficiency")


if __name__ == "__main__":
    main()
