#pragma once
#include <string>
#include <map>
#include "Team.h"

class GamePredictor {
private:
    std::map<std::string, Team> teams;
    
    // Helper to normalize team names (handle abbreviations, spacing)
    std::string normalizeTeamName(const std::string& name);
    
public:
    void loadAllStats(const std::string& baseDataPath);
    
    double predictWinProbability(const Team& homeTeam, const Team& awayTeam);
    
    Team* getTeam(const std::string& teamName);
};
