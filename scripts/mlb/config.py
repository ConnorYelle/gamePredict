"""Project paths and the model's weight configuration.

The win-probability weights are the only persisted state the model carries; they
live in ``config/config.json`` and are read by the C++ engine and written by the
self-learning trainer. Advanced-stat weights (pitcher FIP, bullpen, park factor)
default to 0 so an untrained model ignores them until the trainer fits them.

The win-probability formula maps a team-strength *difference* through a logistic
(see mlb.model / cpp/GamePredictor.cpp): ``probScale`` sets how sharply a strength
gap turns into a probability and ``homeFieldLogit`` is the additive home-field
edge in log-odds. This is what keeps the output calibrated for the Brier score.
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
    # Probability mapping: logistic on the home-vs-away strength difference.
    "probScale": 0.1,        # sharpness: logit units per unit of strength gap
    "homeFieldLogit": 0.15,  # additive home edge in log-odds (~0.54 baseline)
    # Starting-pitcher weights.
    "pitcherEraWeight": 0.0,
    "pitcherWhipWeight": 0.0,
    "pitcherK9Weight": 0.0,
    "pitcherRecentFormWeight": 0.0,
    "pitcherFipWeight": 0.0,  # FIP: defense-independent, less noisy than ERA
    # Bullpen weights (relief-pitching split).
    "bullpenEraWeight": 0.0,
    "bullpenKbbWeight": 0.0,  # bullpen K/9 minus BB/9 (net swing-and-miss)
    # Park factor: how much the home park's run index swings the offenses.
    "parkFactorWeight": 0.0,
}

# Early-season regression: team rate stats are shrunk toward the league mean as
# if every team had this many games of league-average play added in. Tames
# small-sample noise (the dominant Brier error early in a season) and gently
# regresses full-season rates toward true talent. 0 disables it.
REGRESSION_GAMES = 30.0

# Static park run-index priors keyed by full team name (1.00 = neutral). These
# are intentional priors, not fitted values; ``parkFactorWeight`` scales how much
# of the (factor - 1) swing the model actually applies. MUST stay in sync with
# the PARK_FACTORS table in cpp/GamePredictor.cpp.
PARK_FACTORS = {
    "Colorado Rockies": 1.15,
    "Cincinnati Reds": 1.07,
    "Boston Red Sox": 1.05,
    "Arizona Diamondbacks": 1.03,
    "Kansas City Royals": 1.02,
    "Chicago Cubs": 1.02,
    "Texas Rangers": 1.02,
    "Baltimore Orioles": 1.02,
    "Philadelphia Phillies": 1.02,
    "Toronto Blue Jays": 1.02,
    "Atlanta Braves": 1.01,
    "Washington Nationals": 1.01,
    "Chicago White Sox": 1.01,
    "New York Yankees": 1.01,
    "Los Angeles Angels": 1.00,
    "Houston Astros": 1.00,
    "Minnesota Twins": 1.00,
    "Milwaukee Brewers": 1.00,
    "St. Louis Cardinals": 0.99,
    "Pittsburgh Pirates": 0.99,
    "Los Angeles Dodgers": 0.99,
    "Cleveland Guardians": 0.98,
    "New York Mets": 0.98,
    "Detroit Tigers": 0.98,
    "Tampa Bay Rays": 0.97,
    "Miami Marlins": 0.97,
    "Athletics": 0.97,
    "San Diego Padres": 0.96,
    "San Francisco Giants": 0.96,
    "Seattle Mariners": 0.95,
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
