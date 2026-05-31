#pragma once
#include <string>
#include <map>
#include <vector>
#include "Team.h"

struct Game {
    std::string homeTeam;
    std::string awayTeam;
    std::string homeStarter;  // probable/actual starting pitcher (optional)
    std::string awayStarter;  // probable/actual starting pitcher (optional)
};

// Starting pitcher stats. A value of -1 means "unknown" and is skipped in
// scoring, so an unannounced starter gracefully falls back to team-only.
struct Pitcher {
    std::string name;
    double era = -1.0;
    double whip = -1.0;
    double k9 = -1.0;         // strikeouts per 9 innings
    double recentEra = -1.0;  // ERA over the last few starts (recent form)
    double fip = -1.0;        // Fielding Independent Pitching (less noisy than ERA)
};

class GamePredictor {
private:
    std::map<std::string, Team> teams;
    std::map<std::string, Pitcher> pitchers;

    // Prediction weights
    double runsPerGameWeight = 0.4;
    double onBasePercentageWeight = 50.0;
    double sluggingPercentageWeight = 30.0;
    double offenseWeight = 0.6;
    double defenseWeight = 0.4;

    // Probability mapping: logistic on the home-vs-away strength difference.
    // probScale is the logistic slope; homeFieldLogit is the additive home edge
    // in log-odds. This calibrated mapping is what the Brier score rewards.
    double probScale = 0.1;
    double homeFieldLogit = 0.15;

    // Starting-pitcher weights (0 by default => no effect until tuned).
    double pitcherEraWeight = 0.0;
    double pitcherWhipWeight = 0.0;
    double pitcherK9Weight = 0.0;
    double pitcherRecentFormWeight = 0.0;
    double pitcherFipWeight = 0.0;

    // Bullpen weights.
    double bullpenEraWeight = 0.0;
    double bullpenKbbWeight = 0.0;

    // Park-factor weight: how much of the home park's (run index - 1) swing the
    // model applies to both offenses.
    double parkFactorWeight = 0.0;

    // Helper to normalize team names (handle abbreviations, spacing)
    std::string normalizeTeamName(const std::string& name);

    // Contribution of a starting pitcher to a team's strength.
    double pitcherScore(const Pitcher* pitcher) const;

    // Contribution of a team's bullpen to its strength.
    double bullpenScore(const Team& team) const;

    // Home park run index (1.0 = neutral / unknown) keyed by full team name.
    double parkFactor(const std::string& teamName) const;

public:
    void loadConfig(const std::string& configPath);

    void loadAllStats(const std::string& baseDataPath);

    double predictWinProbability(const Team& homeTeam, const Team& awayTeam,
                                 const Pitcher* homeStarter = nullptr,
                                 const Pitcher* awayStarter = nullptr);

    std::vector<Game> loadGames(const std::string& gamesPath);

    void predictAllGames(const std::vector<Game>& games);

    Team* getTeam(const std::string& teamName);
    Pitcher* getPitcher(const std::string& pitcherName);
};
