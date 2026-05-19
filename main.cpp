#include "CSVReader.h"
#include "GamePredictor.h"
#include <iostream>

int main() {
    GamePredictor predictor;
    
    // Load prediction weights from configuration file
    predictor.loadConfig("config.json");
    
    // Load all team statistics from the data directory
    predictor.loadAllStats("rawData/05-13-26");
    
    // Load today's games from the schedule file
    auto games = predictor.loadGames("games.txt");
    if (!games.empty()) {
        std::cout << "=== Game Predictions ===" << std::endl;
        predictor.predictAllGames(games);
    } else {
        std::cout << "No games found or could not load games.txt" << std::endl;
    }
    
    return 0;
}
