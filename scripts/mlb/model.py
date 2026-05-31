"""The win-probability model (Python port of cpp/GamePredictor.cpp).

``PredictionModel`` is a Strategy parameterized by a weight dict: construct it
with a set of weights and call ``home_win_probability``. Keeping the formula
identical to the C++ engine is what lets the trainer and backtester reason about
the same model the production predictor runs.

The model builds an additive "strength" for each side (offense + defense +
starting pitcher + bullpen) and maps the home-minus-away *difference* through a
logistic. Mapping a difference through a logistic -- rather than taking a ratio
of strengths -- is what makes the output a calibrated probability, which is what
the Brier score rewards. ``probScale`` is the logistic slope and
``homeFieldLogit`` is the additive home-field edge in log-odds.
"""

import math


class PredictionModel:
    def __init__(self, weights):
        self.w = weights

    def pitcher_score(self, p):
        """``p`` is {era, whip, k9, recentEra, fip} (or None). Missing values
        are < 0 and contribute nothing."""
        if not p:
            return 0.0
        w = self.w
        score = 0.0
        if p.get("era", -1) >= 0:
            score += (1.0 / (p["era"] + 0.1)) * w["pitcherEraWeight"]
        if p.get("whip", -1) >= 0:
            score += (1.0 / (p["whip"] + 0.1)) * w["pitcherWhipWeight"]
        if p.get("k9", -1) >= 0:
            score += p["k9"] * w["pitcherK9Weight"]
        if p.get("recentEra", -1) >= 0:
            score += (1.0 / (p["recentEra"] + 0.1)) * w["pitcherRecentFormWeight"]
        if p.get("fip", -1) >= 0:
            score += (1.0 / (p["fip"] + 0.1)) * w["pitcherFipWeight"]
        return score

    def bullpen_score(self, t):
        """Relief-pitching contribution from a team's bullpen split. Uses the
        same -1 = "unknown" sentinel convention as the starter stats, so a team
        without a fetched bullpen split simply contributes nothing."""
        w = self.w
        score = 0.0
        if t.get("bullpenEra", -1) >= 0:
            score += (1.0 / (t["bullpenEra"] + 0.1)) * w["bullpenEraWeight"]
        if t.get("bullpenKbb", -1) >= 0:
            score += t["bullpenKbb"] * w["bullpenKbbWeight"]
        return score

    def _park_mult(self, home):
        """Multiplier applied to *both* offenses, derived from the home park's
        run index. ``parkFactorWeight`` interpolates how much of the (factor - 1)
        swing is applied (0 => parks ignored)."""
        pf = home.get("parkFactor", 1.0)
        return 1.0 + (pf - 1.0) * self.w.get("parkFactorWeight", 0.0)

    def home_win_probability(self, home, away, home_sp, away_sp):
        """Win probability for the home team. ``home``/``away`` are team-stat
        dicts; ``home_sp``/``away_sp`` are pitcher dicts (or None)."""
        w = self.w
        park = self._park_mult(home)

        def offense(t):
            return ((t.get("runsPerGame", 0.0) * w["runsPerGameWeight"]
                     + t.get("onBasePercentage", 0.0) * w["onBasePercentageWeight"]
                     + t.get("sluggingPercentage", 0.0) * w["sluggingPercentageWeight"])
                    * park)

        def defense(t):
            return (1.0 / (t.get("runsAllowedPerGame", 0.0) + 0.1)) \
                * t.get("fieldingPercentage", 0.0) * 100

        def strength(t, sp):
            return (offense(t) * w["offenseWeight"]
                    + defense(t) * w["defenseWeight"]
                    + self.pitcher_score(sp)
                    + self.bullpen_score(t))

        home_strength = strength(home, home_sp)
        away_strength = strength(away, away_sp)

        # No data on either side -> coin flip (keeps the degenerate case clean).
        if home_strength + away_strength == 0:
            return 0.5

        logit = w["probScale"] * (home_strength - away_strength) + w["homeFieldLogit"]
        p = 1.0 / (1.0 + math.exp(-logit))
        return min(0.99, max(0.01, p))
