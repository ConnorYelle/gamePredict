"""The win-probability model (Python port of cpp/GamePredictor.cpp).

``PredictionModel`` is a Strategy parameterized by a weight dict: construct it
with a set of weights and call ``home_win_probability``. Keeping the formula
identical to the C++ engine is what lets the trainer and backtester reason about
the same model the production predictor runs.
"""


class PredictionModel:
    def __init__(self, weights):
        self.w = weights

    def pitcher_score(self, p):
        """``p`` is {era, whip, k9, recentEra} (or None). Missing values are < 0."""
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
        return score

    def home_win_probability(self, home, away, home_sp, away_sp):
        """Win probability for the home team. ``home``/``away`` are team-stat
        dicts; ``home_sp``/``away_sp`` are pitcher dicts (or None)."""
        w = self.w

        def offense(t):
            return (t.get("runsPerGame", 0.0) * w["runsPerGameWeight"]
                    + t.get("onBasePercentage", 0.0) * w["onBasePercentageWeight"]
                    + t.get("sluggingPercentage", 0.0) * w["sluggingPercentageWeight"])

        def defense(t):
            return (1.0 / (t.get("runsAllowedPerGame", 0.0) + 0.1)) \
                * t.get("fieldingPercentage", 0.0) * 100

        home_strength = (offense(home) * w["offenseWeight"]
                         + defense(home) * w["defenseWeight"]
                         + self.pitcher_score(home_sp)) * w["homeFieldAdvantage"]
        away_strength = (offense(away) * w["offenseWeight"]
                         + defense(away) * w["defenseWeight"]
                         + self.pitcher_score(away_sp))

        total = home_strength + away_strength
        if total == 0:
            return 0.5
        return min(0.99, max(0.01, home_strength / total))
