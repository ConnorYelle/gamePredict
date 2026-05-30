// Unit tests for the C++ prediction engine (cpp/GamePredictor.cpp).
//
// Self-contained: no test framework, mirrors the style of
// tests/scheduleFetcherTest.cpp. Compile together with GamePredictor.cpp:
//
//   g++ -std=c++17 tests/test_game_predictor.cpp cpp/GamePredictor.cpp \
//       -I cpp -o build/game_predictor_test
//
// Exit code is the number of failed assertions (0 == all passed).

#include "GamePredictor.h"

#include <cmath>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <string>

namespace fs = std::filesystem;

struct TestRunner {
    int passed = 0;
    int failed = 0;

    void check(bool cond, const std::string& name) {
        if (cond) {
            std::cout << "[PASS] " << name << "\n";
            ++passed;
        } else {
            std::cout << "[FAIL] " << name << "\n";
            ++failed;
        }
    }

    int summary() {
        std::cout << "\n==========================\n";
        std::cout << "Passed: " << passed << "  Failed: " << failed << "\n";
        std::cout << (failed == 0 ? "ALL TESTS PASSED\n" : "SOME TESTS FAILED\n");
        return failed;
    }
};

static Team makeTeam(const std::string& name, double rpg, double obp,
                     double slg, double rag, double fld) {
    Team t(name);
    t.runsPerGame = rpg;
    t.onBasePercentage = obp;
    t.sluggingPercentage = slg;
    t.runsAllowedPerGame = rag;
    t.fieldingPercentage = fld;
    return t;
}

static void writeFile(const fs::path& path, const std::string& content) {
    std::ofstream f(path);
    f << content;
}

// ------------------------------------------------------------------ //
// predictWinProbability
// ------------------------------------------------------------------ //
static void testPrediction(TestRunner& tr) {
    GamePredictor predictor;  // default weights (HFA = 1.05)
    Team a = makeTeam("Home", 4.5, 0.320, 0.410, 4.0, 0.985);
    Team b = makeTeam("Away", 4.5, 0.320, 0.410, 4.0, 0.985);

    double p = predictor.predictWinProbability(a, b);
    tr.check(p > 0.5, "identical teams: home favored by home-field advantage");
    tr.check(p > 0.01 && p < 0.99, "probability within clamp bounds");

    Team strong = makeTeam("Strong", 50.0, 0.500, 3.000, 1.0, 0.999);
    Team weak = makeTeam("Weak", 0.0, 0.0, 0.0, 9.0, 0.900);
    double pStrong = predictor.predictWinProbability(strong, weak);
    tr.check(pStrong <= 0.99, "dominant home team clamped to ceiling");
    tr.check(pStrong > 0.5, "dominant home team is favored");

    Team zero = makeTeam("Zero", 0.0, 0.0, 0.0, 0.0, 0.0);
    double pZero = predictor.predictWinProbability(zero, zero);
    tr.check(std::abs(pZero - 0.5) < 1e-9, "zero-strength matchup returns 0.5");
}

// ------------------------------------------------------------------ //
// loadGames parsing
// ------------------------------------------------------------------ //
static void testLoadGames(TestRunner& tr, const fs::path& dir) {
    fs::path gamesPath = dir / "games.txt";
    writeFile(gamesPath,
              "Boston Red Sox | New York Yankees | Ace H | Ace A\n"
              "Chicago Cubs | St. Louis Cardinals\n"
              "\n"                       // blank line -> skipped
              "OnlyOneField\n");         // < 2 fields -> skipped

    GamePredictor predictor;
    auto games = predictor.loadGames(gamesPath.string());
    tr.check(games.size() == 2, "loadGames keeps only well-formed lines");
    tr.check(games[0].homeTeam == "Boston Red Sox", "home team parsed/trimmed");
    tr.check(games[0].awayTeam == "New York Yankees", "away team parsed/trimmed");
    tr.check(games[0].homeStarter == "Ace H", "home starter parsed");
    tr.check(games[0].awayStarter == "Ace A", "away starter parsed");
    tr.check(games[1].homeStarter.empty(), "missing starter is empty");

    auto none = predictor.loadGames((dir / "does_not_exist.txt").string());
    tr.check(none.empty(), "missing games file yields empty vector");
}

// ------------------------------------------------------------------ //
// loadAllStats + getTeam/getPitcher + name normalization
// ------------------------------------------------------------------ //
static void testLoadStats(TestRunner& tr, const fs::path& dir) {
    // Batting: header + 1 data row + 2 trailing league rows (loop skips last 2).
    // Columns used: [0]=team [3]=R/G [11]=HR [17]=BA [18]=OBP [19]=SLG (>=20 cols).
    // Layout: column header + 1 data row + 2 trailing league rows. The reader's
    // loop skips row 0 (header) and the final 2 rows, leaving just the data row.
    std::string battingRow = "Red Sox,x,x,5.0,x,x,x,x,x,x,x,60,x,x,x,x,x,0.265,0.330,0.430";
    writeFile(dir / "TeamStandardBatting.txt",
              "Team,h2,h3,RG,h5,h6,h7,h8,h9,h10,h11,HR,h13,h14,h15,h16,h17,BA,OBP,SLG\n" +
              battingRow + "\n" +
              "LeagueAvg,x,x,4.5,x,x,x,x,x,x,x,30,x,x,x,x,x,0.250,0.320,0.400\n" +
              "LeagueTotal,x,x,4.5,x,x,x,x,x,x,x,30,x,x,x,x,x,0.250,0.320,0.400\n");

    // Fielding: columns [0]=team [2]=RA/G [11]=E [13]=Fld% (>=14 cols).
    writeFile(dir / "TeamFielding.txt",
              "Team,h2,RAG,h4,h5,h6,h7,h8,h9,h10,h11,E,h13,Fld\n"
              "Red Sox,x,4.0,x,x,x,x,x,x,x,x,50,x,0.985\n"
              "LeagueAvg,x,4.5,x,x,x,x,x,x,x,x,60,x,0.980\n"
              "LeagueTotal,x,4.5,x,x,x,x,x,x,x,x,60,x,0.980\n");

    writeFile(dir / "StartingPitchers.csv",
              "name,era,whip,k9,recentEra\n"
              "Ace,2.50,1.10,9.0,3.0\n"
              "Blank,,,,\n");

    GamePredictor predictor;
    predictor.loadAllStats(dir.string());

    Team* bos = predictor.getTeam("Boston Red Sox");
    tr.check(bos != nullptr, "team stored under normalized full name");
    if (bos) {
        tr.check(std::abs(bos->runsPerGame - 5.0) < 1e-9, "R/G parsed");
        tr.check(std::abs(bos->onBasePercentage - 0.330) < 1e-9, "OBP parsed");
        tr.check(std::abs(bos->sluggingPercentage - 0.430) < 1e-9, "SLG parsed");
        tr.check(std::abs(bos->runsAllowedPerGame - 4.0) < 1e-9, "RA/G parsed");
        tr.check(std::abs(bos->fieldingPercentage - 0.985) < 1e-9, "Fld% parsed");
    }

    // Nickname query resolves to the same stored team.
    tr.check(predictor.getTeam("Red Sox") == bos, "nickname query normalizes");
    tr.check(predictor.getTeam("Nonexistent Team") == nullptr,
             "unknown team returns nullptr");

    Pitcher* ace = predictor.getPitcher("Ace");
    tr.check(ace != nullptr, "pitcher loaded");
    if (ace) {
        tr.check(std::abs(ace->era - 2.50) < 1e-9, "pitcher ERA parsed");
        tr.check(std::abs(ace->k9 - 9.0) < 1e-9, "pitcher K/9 parsed");
    }

    Pitcher* blank = predictor.getPitcher("Blank");
    tr.check(blank != nullptr && blank->era < 0.0,
             "blank pitcher stats stored as unknown (-1)");
    tr.check(predictor.getPitcher("   ") == nullptr,
             "whitespace pitcher name returns nullptr");
}

// ------------------------------------------------------------------ //
// loadConfig affects predictions
// ------------------------------------------------------------------ //
static void testLoadConfig(TestRunner& tr, const fs::path& dir) {
    fs::path cfg = dir / "config.json";
    writeFile(cfg, R"({
      "weights": {
        "runsPerGameWeight": 0.4,
        "onBasePercentageWeight": 50.0,
        "sluggingPercentageWeight": 30.0,
        "offenseWeight": 0.6,
        "defenseWeight": 0.4,
        "homeFieldAdvantage": 100.0,
        "pitcherEraWeight": 0.0,
        "pitcherWhipWeight": 0.0,
        "pitcherK9Weight": 0.0,
        "pitcherRecentFormWeight": 0.0
      }
    })");

    GamePredictor predictor;
    predictor.loadConfig(cfg.string());
    Team a = makeTeam("Home", 4.5, 0.320, 0.410, 4.0, 0.985);
    Team b = makeTeam("Away", 4.5, 0.320, 0.410, 4.0, 0.985);
    double p = predictor.predictWinProbability(a, b);
    tr.check(p > 0.98, "huge home-field advantage pushes prob toward ceiling");

    GamePredictor missing;
    missing.loadConfig((dir / "no_such_config.json").string());
    double pDefault = missing.predictWinProbability(a, b);
    tr.check(pDefault > 0.5 && pDefault < 0.6,
             "missing config falls back to default weights");
}

int main() {
    fs::path dir = fs::temp_directory_path() / "gp_cpp_tests";
    fs::create_directories(dir);

    TestRunner tr;
    testPrediction(tr);
    testLoadGames(tr, dir);
    testLoadStats(tr, dir);
    testLoadConfig(tr, dir);

    int failed = tr.summary();
    fs::remove_all(dir);
    return failed;
}
