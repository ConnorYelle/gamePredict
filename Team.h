#pragma once
#include <string>

class Team {
public:
    std::string name;
    
    // Batting stats
    double runsPerGame = 0.0;
    double battingAvg = 0.0;
    double onBasePercentage = 0.0;
    double sluggingPercentage = 0.0;
    int homeRuns = 0;
    
    // Fielding stats
    double fieldingPercentage = 0.0;
    int errors = 0;
    double runsAllowedPerGame = 0.0;
    
    // Pitching stats
    double era = 0.0;
    int strikeouts = 0;
    
    Team() = default;
    Team(const std::string& teamName) : name(teamName) {}
};
