#include "CSVReader.h"
#include "GamePredictor.h"
#include <iostream>

int main() {
    GamePredictor predictor;
    
    // Load configuration weights
    predictor.loadConfig("config.json");
    
    // Load all team statistics
    predictor.loadAllStats("rawData/05-13-26");
    
    // Load and predict all games from games.txt
    auto games = predictor.loadGames("games.txt");
    if (!games.empty()) {
        std::cout << "=== Game Predictions ===" << std::endl;
        predictor.predictAllGames(games);
    } else {
        std::cout << "No games found or could not load games.txt" << std::endl;
    }
    
    return 0;
}
