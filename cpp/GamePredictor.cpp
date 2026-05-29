#include "GamePredictor.h"
#include "CSVReader.h"
#include <algorithm>
#include <cmath>
#include <fstream>
#include <sstream>
#include <iostream>
#include <vector>

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
    pitcherEraWeight = extractJsonDouble(configJson, "pitcherEraWeight");
    pitcherWhipWeight = extractJsonDouble(configJson, "pitcherWhipWeight");
    pitcherK9Weight = extractJsonDouble(configJson, "pitcherK9Weight");
    pitcherRecentFormWeight = extractJsonDouble(configJson, "pitcherRecentFormWeight");
}

std::string GamePredictor::normalizeTeamName(const std::string& name) {
    std::string normalized = name;

    // Remove whitespace
    normalized.erase(0, normalized.find_first_not_of(" \t"));
    normalized.erase(normalized.find_last_not_of(" \t") + 1);

    // Team nickname -> full name mapping
    static std::map<std::string, std::string> teamMap = {
        {"Diamondbacks", "Arizona Diamondbacks"},
        {"Braves", "Atlanta Braves"},
        {"Orioles", "Baltimore Orioles"},
        {"Red Sox", "Boston Red Sox"},
        {"Cubs", "Chicago Cubs"},
        {"White Sox", "Chicago White Sox"},
        {"Reds", "Cincinnati Reds"},
        {"Guardians", "Cleveland Guardians"},
        {"Rockies", "Colorado Rockies"},
        {"Tigers", "Detroit Tigers"},
        {"Astros", "Houston Astros"},
        {"Royals", "Kansas City Royals"},
        {"Angels", "Los Angeles Angels"},
        {"Dodgers", "Los Angeles Dodgers"},
        {"Marlins", "Miami Marlins"},
        {"Brewers", "Milwaukee Brewers"},
        {"Twins", "Minnesota Twins"},
        {"Mets", "New York Mets"},
        {"Yankees", "New York Yankees"},
        {"Athletics", "Athletics"},
        {"Phillies", "Philadelphia Phillies"},
        {"Pirates", "Pittsburgh Pirates"},
        {"Padres", "San Diego Padres"},
        {"Giants", "San Francisco Giants"},
        {"Mariners", "Seattle Mariners"},
        {"Cardinals", "St. Louis Cardinals"},
        {"Rays", "Tampa Bay Rays"},
        {"Rangers", "Texas Rangers"},
        {"Blue Jays", "Toronto Blue Jays"},
        {"Nationals", "Washington Nationals"},
        {"D'backs", "Arizona Diamondbacks"}
    };

    auto it = teamMap.find(normalized);
    if (it != teamMap.end()) {
        return it->second;
    }

    return normalized;
}

void GamePredictor::loadAllStats(const std::string& baseDataPath) {
    // Load Batting Stats
    auto battingData = CSVReader::readCSV(baseDataPath + "/TeamStandardBatting.txt");
    if (battingData.size() > 2) {
        for (size_t i = 1; i + 2 < battingData.size(); i++) { // Skip header and league average rows
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
    }
    
    // Load Fielding Stats
    auto fieldingData = CSVReader::readCSV(baseDataPath + "/TeamFielding.txt");
    if (fieldingData.size() > 2) {
        for (size_t i = 1; i + 2 < fieldingData.size(); i++) {
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

    // Load starting pitcher stats (optional). Format: name,era,whip,k9,recentEra
    // Missing/blank values are stored as -1 ("unknown") and skipped in scoring.
    auto parseStat = [](const std::string& s) -> double {
        try {
            return s.empty() ? -1.0 : std::stod(s);
        } catch (...) {
            return -1.0;
        }
    };
    auto pitcherData = CSVReader::readCSV(baseDataPath + "/StartingPitchers.csv");
    if (pitcherData.size() > 1) {
        for (size_t i = 1; i < pitcherData.size(); i++) { // Skip header
            auto& row = pitcherData[i];
            if (row.size() < 2) continue;

            std::string name = row[0];
            name.erase(0, name.find_first_not_of(" \t"));
            name.erase(name.find_last_not_of(" \t") + 1);
            if (name.empty()) continue;

            Pitcher& p = pitchers[name];
            p.name = name;
            p.era = parseStat(row[1]);
            if (row.size() > 2) p.whip = parseStat(row[2]);
            if (row.size() > 3) p.k9 = parseStat(row[3]);
            if (row.size() > 4) p.recentEra = parseStat(row[4]);
        }
    }
}

double GamePredictor::pitcherScore(const Pitcher* pitcher) const {
    if (!pitcher) return 0.0;

    double score = 0.0;
    // Lower ERA/WHIP is better -> invert. K/9 higher is better -> direct.
    if (pitcher->era >= 0.0) score += (1.0 / (pitcher->era + 0.1)) * pitcherEraWeight;
    if (pitcher->whip >= 0.0) score += (1.0 / (pitcher->whip + 0.1)) * pitcherWhipWeight;
    if (pitcher->k9 >= 0.0) score += pitcher->k9 * pitcherK9Weight;
    if (pitcher->recentEra >= 0.0) score += (1.0 / (pitcher->recentEra + 0.1)) * pitcherRecentFormWeight;
    return score;
}

double GamePredictor::predictWinProbability(const Team& homeTeam, const Team& awayTeam,
                                            const Pitcher* homeStarter,
                                            const Pitcher* awayStarter) {
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

    // Starting pitcher contribution (0 when the starter is unknown or untuned)
    double homePitching = pitcherScore(homeStarter);
    double awayPitching = pitcherScore(awayStarter);

    // Combined team strength (home field advantage applied)
    double homeStrength = (homeOffense * offenseWeight + homeDefense * defenseWeight + homePitching) * homeFieldAdvantage;
    double awayStrength = (awayOffense * offenseWeight + awayDefense * defenseWeight + awayPitching);

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

Pitcher* GamePredictor::getPitcher(const std::string& pitcherName) {
    std::string name = pitcherName;
    name.erase(0, name.find_first_not_of(" \t"));
    name.erase(name.find_last_not_of(" \t") + 1);
    if (name.empty()) return nullptr;

    auto it = pitchers.find(name);
    if (it != pitchers.end()) {
        return &it->second;
    }
    return nullptr;
}

std::vector<Game> GamePredictor::loadGames(const std::string& gamesPath) {
    std::vector<Game> games;
    std::ifstream gamesFile(gamesPath);
    
    if (!gamesFile.is_open()) {
        return games;
    }
    
    std::string line;
    while (std::getline(gamesFile, line)) {
        // Skip empty lines
        if (line.empty()) continue;

        // Split on '|'. Format: Home | Away [| HomeStarter | AwayStarter]
        std::vector<std::string> fields;
        std::stringstream ss(line);
        std::string field;
        while (std::getline(ss, field, '|')) {
            field.erase(0, field.find_first_not_of(" \t\r"));
            field.erase(field.find_last_not_of(" \t\r") + 1);
            fields.push_back(field);
        }

        if (fields.size() < 2) continue;

        Game game;
        game.homeTeam = fields[0];
        game.awayTeam = fields[1];
        if (fields.size() > 2) game.homeStarter = fields[2];
        if (fields.size() > 3) game.awayStarter = fields[3];
        games.push_back(game);
    }

    return games;
}

void GamePredictor::predictAllGames(const std::vector<Game>& games) {
    std::cout << "                 MLB GAME PREDICTIONS\n";
    std::cout << "============================================================\n\n";

    for (const auto& game : games) {

        Team* home = getTeam(game.homeTeam);
        Team* away = getTeam(game.awayTeam);

        if (home && away) {

            Pitcher* homeSP = getPitcher(game.homeStarter);
            Pitcher* awaySP = getPitcher(game.awayStarter);

            double homeWinProb = predictWinProbability(*home, *away, homeSP, awaySP);
            double awayWinProb = 1.0 - homeWinProb;

            Team* favorite;
            double favoriteProb;

            if (homeWinProb >= awayWinProb) {
                favorite = home;
                favoriteProb = homeWinProb;
            } else {
                favorite = away;
                favoriteProb = awayWinProb;
            }

            std::cout << away->name
                      << " @ "
                      << home->name
                      << "\n";

            std::cout << "------------------------------------------------------------\n";

            if (!game.awayStarter.empty() || !game.homeStarter.empty()) {
                std::cout << "Starters: "
                          << (game.awayStarter.empty() ? "TBD" : game.awayStarter)
                          << " vs "
                          << (game.homeStarter.empty() ? "TBD" : game.homeStarter)
                          << "\n";
            }

            std::cout << std::left << std::setw(25)
                      << away->name
                      << std::right << std::setw(8)
                      << std::fixed << std::setprecision(1)
                      << (awayWinProb * 100) << "%\n";

            std::cout << std::left << std::setw(25)
                      << home->name
                      << std::right << std::setw(8)
                      << std::fixed << std::setprecision(1)
                      << (homeWinProb * 100) << "%\n";

            std::cout << "\n";

            std::cout << "Favorite: "
                      << favorite->name
                      << " ("
                      << std::fixed << std::setprecision(1)
                      << (favoriteProb * 100)
                      << "%)\n";

            std::cout << "\n============================================================\n\n";

        } else {

            std::cout << "[ERROR] Could not find teams: "
                      << game.homeTeam
                      << " vs "
                      << game.awayTeam
                      << "\n";
        }
    }
}
