#include "CSVReader.h"
#include "GamePredictor.h"
#include <iostream>

int main() {
    GamePredictor predictor;
    
    // Load all team statistics
    predictor.loadAllStats("rawData/05-13-26");
    
    // Example predictions
    Team* braves = predictor.getTeam("Atlanta Braves");
    Team* yankees = predictor.getTeam("New York Yankees");
    
    if (braves && yankees) {
        double winProb = predictor.predictWinProbability(*braves, *yankees);
        std::cout << "Atlanta Braves vs New York Yankees" << std::endl;
        std::cout << "Braves win probability (home): " << (winProb * 100) << "%" << std::endl;
        std::cout << std::endl;
    }

    Team* dodgers = predictor.getTeam("Los Angeles Dodgers");
    Team* astros = predictor.getTeam("Houston Astros");
    
    if (dodgers && astros) {
        double winProb = predictor.predictWinProbability(*dodgers, *astros);
        std::cout << "Los Angeles Dodgers vs Houston Astros" << std::endl;
        std::cout << "Dodgers win probability (home): " << (winProb * 100) << "%" << std::endl;
    }
    
    return 0;
}
