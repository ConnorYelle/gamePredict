#!/usr/bin/env python3
"""Self-learning trainer for the MLB prediction model.

Fits the C++ model's weights to real historical results and writes them back to
config/config.json, so re-running this script lets the model "re-teach" itself.

It optimizes the same win-probability formula the C++ engine uses (including the
starting-pitcher term) by minimizing log-loss on past seasons via a dependency-
free coordinate-descent search, then reports out-of-sample accuracy on a held-out
season.

Usage:
    python scripts/train_weights.py                      # train 2024, validate 2025
    python scripts/train_weights.py --train-seasons 2023,2024 --val-season 2025
    python scripts/train_weights.py --no-pitchers --dry-run
"""

import argparse
import math
import random

import mlb_data
import validate_predictions as vp


def season_window(season):
    """Full regular-season date window for a season."""
    return f"{season}-03-01", f"{season}-11-30"


def collect_inputs(seasons, use_pitchers, use_cache=True):
    inputs = []
    for season in seasons:
        start, end = season_window(season)
        print(f"  loading {season} ...", flush=True)
        inputs.extend(vp.build_game_inputs(season, start, end,
                                           use_pitchers=use_pitchers, use_cache=use_cache))
    return inputs


def log_loss(inputs, weights):
    total = 0.0
    for g in inputs:
        p = mlb_data.home_win_probability(g["home"], g["away"],
                                          g["home_sp"], g["away_sp"], weights)
        p = min(1 - 1e-9, max(1e-9, p))
        total += -(math.log(p) if g["home_won"] else math.log(1 - p))
    return total / len(inputs) if inputs else float("inf")


def optimize(inputs, init, iters):
    """Coordinate descent with adaptive, per-weight step sizes."""
    keys = list(init)
    weights = dict(init)
    best = log_loss(inputs, weights)
    step = {k: (abs(v) if abs(v) > 1e-6 else 1.0) for k, v in weights.items()}
    random.seed(0)

    for sweep in range(iters):
        improved = False
        for k in keys:
            for delta in (step[k], -step[k]):
                candidate = dict(weights)
                candidate[k] = weights[k] + delta
                loss = log_loss(inputs, candidate)
                if loss < best - 1e-12:
                    best, weights, improved = loss, candidate, True
                    break
            else:
                step[k] *= 0.5  # neither direction helped -> refine this weight
        if not improved and max(step.values()) < 1e-3:
            print(f"  converged after {sweep + 1} sweeps")
            break
    return weights, best


def report(label, inputs, weights):
    metrics = vp.evaluate(inputs, weights)
    print(f"  {label}: accuracy {metrics['accuracy']:.2%}, "
          f"Brier {metrics['brier_score']:.4f}, "
          f"log-loss {log_loss(inputs, weights):.4f} "
          f"({metrics['games_evaluated']} games)")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--train-seasons", default="2024",
                        help="comma-separated seasons to train on")
    parser.add_argument("--val-season", type=int, default=2025,
                        help="held-out season for out-of-sample evaluation")
    parser.add_argument("--iters", type=int, default=40,
                        help="max coordinate-descent sweeps")
    parser.add_argument("--no-pitchers", action="store_true",
                        help="train with team stats only")
    parser.add_argument("--dry-run", action="store_true",
                        help="do not write config.json")
    args = parser.parse_args()

    use_pitchers = not args.no_pitchers
    train_seasons = [int(s) for s in args.train_seasons.split(",") if s.strip()]

    print("=" * 60)
    print("Self-learning weight trainer")
    print(f"Train seasons: {train_seasons} | Validation: {args.val_season}")
    print(f"Starting pitcher: {'included' if use_pitchers else 'excluded'}")
    print("=" * 60)

    print("Loading training data...")
    train_inputs = collect_inputs(train_seasons, use_pitchers)
    print("Loading validation data...")
    val_inputs = collect_inputs([args.val_season], use_pitchers)

    if not train_inputs:
        print("No training data available.")
        return

    init = mlb_data.load_weights()
    print("\nBefore training:")
    report("train", train_inputs, init)
    report("val  ", val_inputs, init)

    print("\nOptimizing...")
    learned, best_loss = optimize(train_inputs, init, args.iters)
    print(f"Best train log-loss: {best_loss:.4f}")

    print("\nAfter training:")
    report("train", train_inputs, learned)
    report("val  ", val_inputs, learned)

    print("\nLearned weights:")
    for k, v in learned.items():
        print(f"  {k}: {v:.4f}")

    if args.dry_run:
        print("\n[dry-run] config.json not modified.")
    else:
        mlb_data.save_weights(learned)
        print("\nWrote learned weights to config/config.json")


if __name__ == "__main__":
    main()
