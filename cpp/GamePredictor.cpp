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
    
    // Only overwrite a default when the key is actually present, so a partial
    // config still benefits from the built-in defaults for missing keys.
    auto load = [&](const std::string& key, double& target) {
        if (configJson.find("\"" + key + "\"") != std::string::npos) {
            target = extractJsonDouble(configJson, key);
        }
    };

    load("runsPerGameWeight", runsPerGameWeight);
    load("onBasePercentageWeight", onBasePercentageWeight);
    load("sluggingPercentageWeight", sluggingPercentageWeight);
    load("offenseWeight", offenseWeight);
    load("defenseWeight", defenseWeight);
    load("probScale", probScale);
    load("homeFieldLogit", homeFieldLogit);
    load("pitcherEraWeight", pitcherEraWeight);
    load("pitcherWhipWeight", pitcherWhipWeight);
    load("pitcherK9Weight", pitcherK9Weight);
    load("pitcherRecentFormWeight", pitcherRecentFormWeight);
    load("pitcherFipWeight", pitcherFipWeight);
    load("bullpenEraWeight", bullpenEraWeight);
    load("bullpenKbbWeight", bullpenKbbWeight);
    load("parkFactorWeight", parkFactorWeight);
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
            if (row.size() > 5) p.fip = parseStat(row[5]);
        }
    }

    // Load bullpen split (optional). Format: name,era,kbb. Blank => -1 ("unknown").
    auto bullpenData = CSVReader::readCSV(baseDataPath + "/TeamBullpen.csv");
    if (bullpenData.size() > 1) {
        for (size_t i = 1; i < bullpenData.size(); i++) { // Skip header
            auto& row = bullpenData[i];
            if (row.size() < 2) continue;

            std::string teamName = normalizeTeamName(row[0]);
            if (teamName.empty()) continue;
            if (teams.find(teamName) == teams.end()) {
                teams[teamName].name = teamName;
            }
            Team& team = teams[teamName];
            team.bullpenEra = parseStat(row[1]);
            if (row.size() > 2) team.bullpenKbb = parseStat(row[2]);
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
    if (pitcher->fip >= 0.0) score += (1.0 / (pitcher->fip + 0.1)) * pitcherFipWeight;
    return score;
}

double GamePredictor::bullpenScore(const Team& team) const {
    double score = 0.0;
    // Lower bullpen ERA is better -> invert. Net K-BB higher is better -> direct.
    if (team.bullpenEra >= 0.0) score += (1.0 / (team.bullpenEra + 0.1)) * bullpenEraWeight;
    if (team.bullpenKbb >= 0.0) score += team.bullpenKbb * bullpenKbbWeight;
    return score;
}

double GamePredictor::parkFactor(const std::string& teamName) const {
    // Static park run-index priors (1.0 = neutral). MUST stay in sync with
    // PARK_FACTORS in scripts/mlb/config.py.
    static const std::map<std::string, double> parkFactors = {
        {"Colorado Rockies", 1.15}, {"Cincinnati Reds", 1.07},
        {"Boston Red Sox", 1.05}, {"Arizona Diamondbacks", 1.03},
        {"Kansas City Royals", 1.02}, {"Chicago Cubs", 1.02},
        {"Texas Rangers", 1.02}, {"Baltimore Orioles", 1.02},
        {"Philadelphia Phillies", 1.02}, {"Toronto Blue Jays", 1.02},
        {"Atlanta Braves", 1.01}, {"Washington Nationals", 1.01},
        {"Chicago White Sox", 1.01}, {"New York Yankees", 1.01},
        {"Los Angeles Angels", 1.00}, {"Houston Astros", 1.00},
        {"Minnesota Twins", 1.00}, {"Milwaukee Brewers", 1.00},
        {"St. Louis Cardinals", 0.99}, {"Pittsburgh Pirates", 0.99},
        {"Los Angeles Dodgers", 0.99}, {"Cleveland Guardians", 0.98},
        {"New York Mets", 0.98}, {"Detroit Tigers", 0.98},
        {"Tampa Bay Rays", 0.97}, {"Miami Marlins", 0.97},
        {"Athletics", 0.97}, {"San Diego Padres", 0.96},
        {"San Francisco Giants", 0.96}, {"Seattle Mariners", 0.95},
    };
    auto it = parkFactors.find(teamName);
    return it != parkFactors.end() ? it->second : 1.0;
}

double GamePredictor::predictWinProbability(const Team& homeTeam, const Team& awayTeam,
                                            const Pitcher* homeStarter,
                                            const Pitcher* awayStarter) {
    // The home park's run index swings both lineups; parkFactorWeight scales how
    // much of the (factor - 1) swing is applied (0 => parks ignored).
    double park = 1.0 + (parkFactor(homeTeam.name) - 1.0) * parkFactorWeight;

    auto offense = [&](const Team& t) {
        return ((t.runsPerGame * runsPerGameWeight) +
                (t.onBasePercentage * onBasePercentageWeight) +
                (t.sluggingPercentage * sluggingPercentageWeight)) * park;
    };
    // Defensive strength: lower RA/G is better, higher Fld% is better.
    auto defense = [](const Team& t) {
        return (1.0 / (t.runsAllowedPerGame + 0.1)) * t.fieldingPercentage * 100;
    };

    double homeStrength = offense(homeTeam) * offenseWeight + defense(homeTeam) * defenseWeight
                          + pitcherScore(homeStarter) + bullpenScore(homeTeam);
    double awayStrength = offense(awayTeam) * offenseWeight + defense(awayTeam) * defenseWeight
                          + pitcherScore(awayStarter) + bullpenScore(awayTeam);

    // No data on either side -> coin flip.
    if (homeStrength + awayStrength == 0) return 0.5;

    // Map the strength *difference* through a logistic for a calibrated
    // probability (homeFieldLogit is the additive home edge in log-odds).
    double logit = probScale * (homeStrength - awayStrength) + homeFieldLogit;
    double winProbability = 1.0 / (1.0 + std::exp(-logit));
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
