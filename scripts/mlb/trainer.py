"""Self-learning trainer: fit the model's weights to historical results.

``WeightTrainer`` minimizes log-loss on past seasons via a dependency-free
coordinate-descent search over the same win-probability formula the C++ engine
uses (including the starting-pitcher term), then reports out-of-sample metrics.
"""

import math
import random

from . import backtester
from .model import PredictionModel
from .stats_api import MlbStatsApi


def season_window(season):
    """Full regular-season date window for a season."""
    return f"{season}-03-01", f"{season}-11-30"


class WeightTrainer:
    def __init__(self, api=None):
        self.api = api or MlbStatsApi()

    def collect_inputs(self, seasons, use_pitchers, use_cache=True):
        inputs = []
        for season in seasons:
            start, end = season_window(season)
            print(f"  loading {season} ...", flush=True)
            inputs.extend(backtester.build_game_inputs(
                self.api, season, start, end,
                use_pitchers=use_pitchers, use_cache=use_cache))
        return inputs

    @staticmethod
    def log_loss(inputs, weights):
        model = PredictionModel(weights)
        total = 0.0
        for g in inputs:
            p = model.home_win_probability(g["home"], g["away"],
                                           g["home_sp"], g["away_sp"])
            p = min(1 - 1e-9, max(1e-9, p))
            total += -(math.log(p) if g["home_won"] else math.log(1 - p))
        return total / len(inputs) if inputs else float("inf")

    def optimize(self, inputs, init, iters):
        """Coordinate descent with adaptive, per-weight step sizes."""
        keys = list(init)
        weights = dict(init)
        best = self.log_loss(inputs, weights)
        step = {k: (abs(v) if abs(v) > 1e-6 else 1.0) for k, v in weights.items()}
        random.seed(0)

        for sweep in range(iters):
            improved = False
            for k in keys:
                for delta in (step[k], -step[k]):
                    candidate = dict(weights)
                    candidate[k] = weights[k] + delta
                    loss = self.log_loss(inputs, candidate)
                    if loss < best - 1e-12:
                        best, weights, improved = loss, candidate, True
                        break
                else:
                    step[k] *= 0.5  # neither direction helped -> refine this weight
            if not improved and max(step.values()) < 1e-3:
                print(f"  converged after {sweep + 1} sweeps")
                break
        return weights, best

    def report(self, label, inputs, weights):
        metrics = backtester.evaluate(inputs, weights)
        print(f"  {label}: accuracy {metrics['accuracy']:.2%}, "
              f"Brier {metrics['brier_score']:.4f}, "
              f"log-loss {self.log_loss(inputs, weights):.4f} "
              f"({metrics['games_evaluated']} games)")
