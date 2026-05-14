#pragma once
#include <string>
#include <map>
#include <vector>
#include "Team.h"

struct Game {
    std::string homeTeam;
    std::string awayTeam;
};

class GamePredictor {
private:
    std::map<std::string, Team> teams;
    
    // Prediction weights
    double runsPerGameWeight = 0.4;
    double onBasePercentageWeight = 50.0;
    double sluggingPercentageWeight = 30.0;
    double offenseWeight = 0.6;
    double defenseWeight = 0.4;
    double homeFieldAdvantage = 1.05;
    
    // Helper to normalize team names (handle abbreviations, spacing)
    std::string normalizeTeamName(const std::string& name);
    
public:
    void loadConfig(const std::string& configPath);
    
    void loadAllStats(const std::string& baseDataPath);
    
    double predictWinProbability(const Team& homeTeam, const Team& awayTeam);
    
    std::vector<Game> loadGames(const std::string& gamesPath);
    
    void predictAllGames(const std::vector<Game>& games);
    
    Team* getTeam(const std::string& teamName);
};
