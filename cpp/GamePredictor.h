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
    double homeFieldAdvantage = 1.05;

    // Starting-pitcher weights (0 by default => pitcher has no effect until tuned)
    double pitcherEraWeight = 0.0;
    double pitcherWhipWeight = 0.0;
    double pitcherK9Weight = 0.0;
    double pitcherRecentFormWeight = 0.0;

    // Helper to normalize team names (handle abbreviations, spacing)
    std::string normalizeTeamName(const std::string& name);

    // Contribution of a starting pitcher to a team's strength.
    double pitcherScore(const Pitcher* pitcher) const;

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
