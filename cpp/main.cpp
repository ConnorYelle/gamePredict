#include "CSVReader.h"
#include "GamePredictor.h"
#include <chrono>
#include <ctime>
#include <filesystem>
#include <iomanip>
#include <iostream>

namespace fs = std::filesystem;

static bool isValidStatsDirectory(const fs::path& dir) {
    if (!fs::exists(dir) || !fs::is_directory(dir)) {
        return false;
    }

    fs::path battingFile = dir / "TeamStandardBatting.txt";
    fs::path fieldingFile = dir / "TeamFielding.txt";
    return fs::exists(battingFile) && fs::file_size(battingFile) > 0
        && fs::exists(fieldingFile) && fs::file_size(fieldingFile) > 0;
}

std::string getLatestStatsDirectory() {
    fs::path baseDir("data/rawData");
    if (!fs::exists(baseDir) || !fs::is_directory(baseDir)) {
        return "";
    }

    fs::path latestDir;
    for (auto& entry : fs::directory_iterator(baseDir)) {
        if (!entry.is_directory()) {
            continue;
        }
        if (!isValidStatsDirectory(entry.path())) {
            continue;
        }
        if (latestDir.empty() || entry.path().filename() > latestDir.filename()) {
            latestDir = entry.path();
        }
    }

    return latestDir.empty() ? "" : latestDir.string();
}

int main() {
    GamePredictor predictor;
    
    // Load prediction weights from configuration file
    std::cout << "[DEBUG] Loading config from config/config.json" << std::endl;
    predictor.loadConfig("config/config.json");
    
    // Load all team statistics from the current data directory
    auto now = std::chrono::system_clock::now();
    std::time_t now_c = std::chrono::system_clock::to_time_t(now);
    std::tm local_tm;
    #ifdef _WIN32
        localtime_s(&local_tm, &now_c);
    #else
        localtime_r(&now_c, &local_tm);
    #endif
    char stats_dir[64];
    std::strftime(stats_dir, sizeof(stats_dir), "data/rawData/%m-%d-%y", &local_tm);
    fs::path statsPath(stats_dir);
    if (!isValidStatsDirectory(statsPath)) {
        std::cout << "[DEBUG] Today's stats directory invalid or empty: " << statsPath.string() << std::endl;
        std::string fallback = getLatestStatsDirectory();
        if (!fallback.empty()) {
            std::cout << "[DEBUG] Falling back to latest valid stats directory: " << fallback << std::endl;
            statsPath = fallback;
        }
    }

    std::cout << "[DEBUG] Loading stats from " << statsPath.string() << std::endl;
    predictor.loadAllStats(statsPath.string());
    
    // Load today's games from the schedule file
    std::cout << "[DEBUG] Loading games from outputs/games.txt" << std::endl;
    auto games = predictor.loadGames("outputs/games.txt");
    std::cout << "[DEBUG] Loaded games count=" << games.size() << std::endl;
    if (!games.empty()) {
        std::cout << "=== Game Predictions ===" << std::endl;
        predictor.predictAllGames(games);
    } else {
        std::cout << "No games found or could not load games.txt" << std::endl;
    }
    
    return 0;
}
