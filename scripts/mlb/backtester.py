"""Backtest the model against actual MLB results from the Stats API.

Assembles per-game model inputs for a season window, then scores the current
weights with the same formula the C++ engine uses (including the starting-pitcher
term). Reports accuracy, Brier score, and a home-field baseline.
"""

from typing import Dict, List, Optional

from . import config
from .model import PredictionModel
from .stats_api import MlbStatsApi


def build_game_inputs(api: MlbStatsApi, season: int, start_date: str, end_date: str,
                      use_pitchers: bool = True, use_cache: bool = True) -> List[Dict]:
    """Assemble per-game model inputs (team stats, pitcher stats, label) for a
    season window, pulling everything needed from the Stats API."""
    team_stats = api.team_model_stats(season, use_cache=use_cache)
    games = api.season_games(start_date, end_date, season, use_cache=use_cache)

    season_cache: Dict[int, Optional[Dict]] = {}

    def pitcher_inputs(pid, date):
        if not use_pitchers or not pid:
            return None
        if pid not in season_cache:
            season_cache[pid] = api.pitcher_season_stats(pid, season, use_cache=use_cache)
        base = season_cache[pid]
        if base is None:
            return None
        p = dict(base)
        p["recentEra"] = api.recent_era(pid, season, before_date=date, use_cache=use_cache)
        return p

    inputs = []
    for g in games:
        if g["home_id"] not in team_stats or g["away_id"] not in team_stats:
            continue
        inputs.append({
            "home": team_stats[g["home_id"]],
            "away": team_stats[g["away_id"]],
            "home_sp": pitcher_inputs(g["home_sp_id"], g["date"]),
            "away_sp": pitcher_inputs(g["away_sp_id"], g["date"]),
            "home_won": g["home_won"],
        })
    return inputs


def evaluate(inputs: List[Dict], weights: Dict[str, float]) -> Dict:
    """Score ``inputs`` with ``weights`` and return summary metrics."""
    model = PredictionModel(weights)
    evaluated = correct = home_wins = 0
    brier_sum = winner_prob_sum = 0.0

    for g in inputs:
        p_home = model.home_win_probability(g["home"], g["away"],
                                            g["home_sp"], g["away_sp"])
        if (p_home >= 0.5) == g["home_won"]:
            correct += 1
        prob_for_winner = p_home if g["home_won"] else (1.0 - p_home)
        brier_sum += (1.0 - prob_for_winner) ** 2
        winner_prob_sum += prob_for_winner
        home_wins += g["home_won"]
        evaluated += 1

    return {
        "games_evaluated": evaluated,
        "accuracy": correct / evaluated if evaluated else 0.0,
        "home_field_baseline": home_wins / evaluated if evaluated else 0.0,
        "average_winner_prob": winner_prob_sum / evaluated if evaluated else 0.0,
        "brier_score": brier_sum / evaluated if evaluated else 0.0,
    }


def run_backtest(season: int, start_date: str, end_date: str,
                 use_pitchers: bool = True, api: Optional[MlbStatsApi] = None) -> None:
    api = api or MlbStatsApi()
    print("\n=== Model Backtest vs. Actual MLB Results ===")
    print(f"Season {season}, window {start_date} -> {end_date}")
    print("Model: cpp/GamePredictor.cpp formula with config/config.json weights")
    print(f"Starting pitcher: {'included' if use_pitchers else 'excluded'}")
    try:
        weights = config.load_weights()
        inputs = build_game_inputs(api, season, start_date, end_date, use_pitchers)
    except Exception as exc:  # network/API issues
        print(f"Could not reach the MLB Stats API: {exc}")
        return

    results = evaluate(inputs, weights)
    if not results["games_evaluated"]:
        print("No completed games found to validate against.")
        return

    print(f"Games evaluated:     {results['games_evaluated']}")
    print(f"Model accuracy:      {results['accuracy']:.2%}")
    print(f"Home-field baseline: {results['home_field_baseline']:.2%}")
    print(f"Edge over baseline:  {results['accuracy'] - results['home_field_baseline']:+.2%}")
    print(f"Avg prob on winners: {results['average_winner_prob']:.2%}")
    print(f"Brier score:         {results['brier_score']:.4f}")
