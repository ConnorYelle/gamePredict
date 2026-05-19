#pragma once
#include <string>

class Team {
public:
    std::string name;
    
    // === BATTING STATS ===
    double runsPerGame = 0.0;
    double battingAvg = 0.0;
    double onBasePercentage = 0.0;
    double sluggingPercentage = 0.0;
    int homeRuns = 0;
    double ops = 0.0;
    double opsPlus = 0.0;
    double strikeouts = 0.0;
    double walks = 0.0;
    
    // Advanced batting metrics
    double iso = 0.0;              // Isolated Power
    double babip = 0.0;            // Batting Average on Balls In Play
    int stolenBases = 0;
    int caughtStealing = 0;
    double wrc = 0.0;              // Weighted Runs Created
    
    // === PITCHING STATS ===
    double era = 0.0;
    int strikeoutsAllowed = 0;
    double whip = 0.0;             // Walks + Hits per IP
    int wins = 0;
    int losses = 0;
    double kPer9 = 0.0;            // K/9 innings
    double bbPer9 = 0.0;           // BB/9 innings
    int saves = 0;
    double runsAllowedPerGame = 0.0;
    
    // Advanced pitching metrics
    double kBbRatio = 0.0;         // Strikeout to Walk ratio
    double fip = 0.0;              // Fielding Independent Pitching
    double lobPct = 0.0;           // Left On Base percentage
    double qualityStarts = 0.0;    // QS percentage
    int hitsAllowed = 0;
    
    // === FIELDING STATS ===
    double fieldingPercentage = 0.0;
    int errors = 0;
    int assists = 0;
    int putouts = 0;
    int doublePlays = 0;
    
    // === RECENT PERFORMANCE ===
    double recentWinPct = 0.0;     // Last 10 games
    double recentRunDiff = 0.0;    // Run differential
    std::string recentRecord = "";
    
    // === STREAK INFO ===
    int winStreak = 0;
    bool isWinStreak = true;
    
    Team() = default;
    Team(const std::string& teamName) : name(teamName) {}
    
    // Calculate composite offensive rating (0-100)
    double getOffensiveRating() const {
        double rating = 0.0;
        if (opsPlus > 0) rating += (opsPlus / 100.0) * 30.0;  // 30 points max
        if (babip > 0) rating += (babip * 100.0) * 20.0;       // 20 points max
        if (iso > 0) rating += (iso * 100.0) * 25.0;           // 25 points max
        if (battingAvg > 0) rating += (battingAvg * 100.0) * 25.0;  // 25 points max
        return std::min(rating, 100.0);
    }
    
    // Calculate composite defensive/pitching rating (0-100)
    double getDefensiveRating() const {
        double rating = 100.0;
        if (era > 0) rating -= (era * 10.0);                   // Penalize for ERA
        if (whip > 0) rating -= (whip * 8.0);                  // Penalize for WHIP
        if (fieldingPercentage > 0) rating += (fieldingPercentage - 0.97) * 500.0;  // Reward good fielding
        return std::max(0.0, std::min(rating, 100.0));
    }
    
    // Get win probability contribution (0-1)
    double getWinProbabilityScore() const {
        double offensive = getOffensiveRating() / 100.0;
        double defensive = getDefensiveRating() / 100.0;
        return (offensive * 0.6) + (defensive * 0.4);  // 60% offense, 40% defense
    }
};
