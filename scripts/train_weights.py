#!/usr/bin/env python3
"""Self-learning trainer for the MLB prediction model (CLI).

Fits the C++ model's weights to real historical results and writes them back to
config/config.json, so re-running this script lets the model "re-teach" itself.
It minimizes log-loss on past seasons via coordinate descent, then reports
out-of-sample accuracy on a held-out season.

Usage:
    python scripts/train_weights.py                      # train 2024, validate 2025
    python scripts/train_weights.py --train-seasons 2023,2024 --val-season 2025
    python scripts/train_weights.py --no-pitchers --dry-run

CLI facade over :class:`mlb.trainer.WeightTrainer`.
"""

import argparse

from mlb import config
from mlb.trainer import WeightTrainer


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

    trainer = WeightTrainer()

    print("Loading training data...")
    train_inputs = trainer.collect_inputs(train_seasons, use_pitchers)
    print("Loading validation data...")
    val_inputs = trainer.collect_inputs([args.val_season], use_pitchers)

    if not train_inputs:
        print("No training data available.")
        return

    init = config.load_weights()
    print("\nBefore training:")
    trainer.report("train", train_inputs, init)
    trainer.report("val  ", val_inputs, init)

    print("\nOptimizing...")
    learned, best_loss = trainer.optimize(train_inputs, init, args.iters)
    print(f"Best train log-loss: {best_loss:.4f}")

    print("\nAfter training:")
    trainer.report("train", train_inputs, learned)
    trainer.report("val  ", val_inputs, learned)

    print("\nLearned weights:")
    for k, v in learned.items():
        print(f"  {k}: {v:.4f}")

    if args.dry_run:
        print("\n[dry-run] config.json not modified.")
    else:
        config.save_weights(learned)
        print("\nWrote learned weights to config/config.json")


if __name__ == "__main__":
    main()
