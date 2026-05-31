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

    // Bullpen (relief-pitching split). -1 means "unknown" and is skipped in
    // scoring, so a team without a loaded bullpen split falls back gracefully.
    double bullpenEra = -1.0;
    double bullpenKbb = -1.0;  // bullpen K/9 minus BB/9

    Team() = default;
    Team(const std::string& teamName) : name(teamName) {}
};
