#include "GamePredictor.h"
#include "CSVReader.h"
#include <algorithm>
#include <cmath>
#include <fstream>
#include <sstream>

// Simple JSON value extractor for doubles
double extractJsonDouble(const std::string& json, const std::string& key) {
    size_t keyPos = json.find("\"" + key + "\"");
    if (keyPos == std::string::npos) return 0.0;
    
    size_t colonPos = json.find(':', keyPos);
    if (colonPos == std::string::npos) return 0.0;
    
    size_t valueStart = json.find_first_not_of(" \t\n\r", colonPos + 1);
    size_t valueEnd = json.find_first_of(",}", valueStart);
    
    if (valueStart == std::string::npos || valueEnd == std::string::npos) return 0.0;
    
    std::string valueStr = json.substr(valueStart, valueEnd - valueStart);
    try {
        return std::stod(valueStr);
    } catch (...) {
        return 0.0;
    }
}

void GamePredictor::loadConfig(const std::string& configPath) {
    std::ifstream configFile(configPath);
    if (!configFile.is_open()) {
        // Use defaults if config file not found
        return;
    }
    
    std::stringstream buffer;
    buffer << configFile.rdbuf();
    std::string configJson = buffer.str();
    
    runsPerGameWeight = extractJsonDouble(configJson, "runsPerGameWeight");
    onBasePercentageWeight = extractJsonDouble(configJson, "onBasePercentageWeight");
    sluggingPercentageWeight = extractJsonDouble(configJson, "sluggingPercentageWeight");
    offenseWeight = extractJsonDouble(configJson, "offenseWeight");
    defenseWeight = extractJsonDouble(configJson, "defenseWeight");
    homeFieldAdvantage = extractJsonDouble(configJson, "homeFieldAdvantage");
}

std::string GamePredictor::normalizeTeamName(const std::string& name) {
    std::string normalized = name;
    // Remove leading/trailing whitespace
    normalized.erase(0, normalized.find_first_not_of(" \t"));
    normalized.erase(normalized.find_last_not_of(" \t") + 1);
    return normalized;
}

void GamePredictor::loadAllStats(const std::string& baseDataPath) {
    // Load Batting Stats
    auto battingData = CSVReader::readCSV(baseDataPath + "/TeamStandardBatting.txt");
    for (size_t i = 1; i < battingData.size() - 2; i++) { // Skip header and league average rows
        auto& row = battingData[i];
        if (row.size() < 20) continue;
        
        std::string teamName = normalizeTeamName(row[0]);
        Team& team = teams[teamName];
        team.name = teamName;
        
        // Parse batting stats: R/G, BA, OBP, SLG, HR
        try {
            team.runsPerGame = std::stod(row[3]);      // R/G
            team.battingAvg = std::stod(row[17]);      // BA
            team.onBasePercentage = std::stod(row[18]); // OBP
            team.sluggingPercentage = std::stod(row[19]); // SLG
            team.homeRuns = std::stoi(row[11]);        // HR
        } catch (...) {
            // Skip on parse error
        }
    }
    
    // Load Fielding Stats
    auto fieldingData = CSVReader::readCSV(baseDataPath + "/TeamFielding.txt");
    for (size_t i = 1; i < fieldingData.size() - 2; i++) {
        auto& row = fieldingData[i];
        if (row.size() < 14) continue;
        
        std::string teamName = normalizeTeamName(row[0]);
        if (teams.find(teamName) == teams.end()) {
            teams[teamName].name = teamName;
        }
        Team& team = teams[teamName];
        
        try {
            team.runsAllowedPerGame = std::stod(row[2]); // RA/G
            team.fieldingPercentage = std::stod(row[13]); // Fld%
            team.errors = std::stoi(row[11]);             // E
        } catch (...) {
            // Skip on parse error
        }
    }
}

double GamePredictor::predictWinProbability(const Team& homeTeam, const Team& awayTeam) {
    // Calculate offensive strength (higher is better)
    double homeOffense = (homeTeam.runsPerGame * runsPerGameWeight) + 
                         (homeTeam.onBasePercentage * onBasePercentageWeight) + 
                         (homeTeam.sluggingPercentage * sluggingPercentageWeight);
    double awayOffense = (awayTeam.runsPerGame * runsPerGameWeight) + 
                         (awayTeam.onBasePercentage * onBasePercentageWeight) + 
                         (awayTeam.sluggingPercentage * sluggingPercentageWeight);
    
    // Calculate defensive strength (lower RA/G is better, higher Fld% is better)
    double homeDefense = (1.0 / (homeTeam.runsAllowedPerGame + 0.1)) * homeTeam.fieldingPercentage * 100;
    double awayDefense = (1.0 / (awayTeam.runsAllowedPerGame + 0.1)) * awayTeam.fieldingPercentage * 100;
    
    // Combined team strength (home field advantage applied)
    double homeStrength = (homeOffense * offenseWeight + homeDefense * defenseWeight) * homeFieldAdvantage;
    double awayStrength = (awayOffense * offenseWeight + awayDefense * defenseWeight);
    
    // Calculate win probability using logistic function
    double totalStrength = homeStrength + awayStrength;
    if (totalStrength == 0) return 0.5;
    
    double winProbability = homeStrength / totalStrength;
    return std::min(0.99, std::max(0.01, winProbability));
}

Team* GamePredictor::getTeam(const std::string& teamName) {
    auto normalized = normalizeTeamName(teamName);
    auto it = teams.find(normalized);
    if (it != teams.end()) {
        return &it->second;
    }
    return nullptr;
}
