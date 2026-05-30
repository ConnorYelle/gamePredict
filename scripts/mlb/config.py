"""Project paths and the model's weight configuration.

The win-probability weights are the only persisted state the model carries; they
live in ``config/config.json`` and are read by the C++ engine and written by the
self-learning trainer. Pitcher weights default to 0 so an untrained model behaves
exactly like the original team-only formula.
"""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CACHE_DIR = ROOT / "data" / "cache"
CONFIG_PATH = ROOT / "config" / "config.json"

API = "https://statsapi.mlb.com/api/v1"

# Weight names and defaults, mirroring cpp/GamePredictor.h.
DEFAULT_WEIGHTS = {
    "runsPerGameWeight": 0.4,
    "onBasePercentageWeight": 50.0,
    "sluggingPercentageWeight": 30.0,
    "offenseWeight": 0.6,
    "defenseWeight": 0.4,
    "homeFieldAdvantage": 1.05,
    "pitcherEraWeight": 0.0,
    "pitcherWhipWeight": 0.0,
    "pitcherK9Weight": 0.0,
    "pitcherRecentFormWeight": 0.0,
}


def load_weights(config_path=CONFIG_PATH):
    """Return the persisted weights, falling back to defaults for any missing
    or malformed entries."""
    weights = dict(DEFAULT_WEIGHTS)
    try:
        with open(config_path, encoding="utf-8") as f:
            cfg = json.load(f)
        for key, val in cfg.get("weights", {}).items():
            if key in weights:
                weights[key] = float(val)
    except (OSError, ValueError):
        pass
    return weights


def save_weights(weights, config_path=CONFIG_PATH):
    """Persist ``weights`` to ``config_path`` as ``{"weights": {...}}``."""
    with open(config_path, "w", encoding="utf-8") as f:
        json.dump({"weights": weights}, f, indent=2)
        f.write("\n")
