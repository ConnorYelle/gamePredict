#include <iostream>
#include <fstream>
#include <vector>
#include <string>
#include <set>
#include <regex>
#include <cstdlib>

using namespace std;

class TestRunner {
private:
    int passed = 0;
    int failed = 0;

public:
    void assertTrue(bool condition, const string& testName) {
        if (condition) {
            cout << "[PASS] " << testName << endl;
            passed++;
        } else {
            cout << "[FAIL] " << testName << endl;
            failed++;
        }
    }

    void summary() {
        cout << "\n==========================" << endl;
        cout << "TEST SUMMARY" << endl;
        cout << "==========================" << endl;
        cout << "Passed: " << passed << endl;
        cout << "Failed: " << failed << endl;

        if (failed == 0) {
            cout << "\nALL TESTS PASSED" << endl;
        } else {
            cout << "\nSOME TESTS FAILED" << endl;
        }
    }
};

vector<string> readGamesFile() {
    vector<string> games;

    ifstream file("games.txt");

    if (!file.is_open()) {
        return games;
    }

    string line;

    while (getline(file, line)) {
        if (!line.empty()) {
            games.push_back(line);
        }
    }

    file.close();

    return games;
}

bool fileExists(const string& filename) {
    ifstream file(filename);
    return file.good();
}

bool validGameFormat(const string& line) {
    regex pattern(R"(^.+\s\|\s.+$)");
    return regex_match(line, pattern);
}

bool noDuplicateGames(const vector<string>& games) {
    set<string> uniqueGames(games.begin(), games.end());
    return uniqueGames.size() == games.size();
}

bool teamsAreNonEmpty(const string& line) {
    size_t pos = line.find('|');

    if (pos == string::npos) {
        return false;
    }

    string home = line.substr(0, pos);
    string away = line.substr(pos + 1);

    return !home.empty() && !away.empty();
}

void testPythonScriptRuns(TestRunner& tr) {
#ifdef _WIN32
    int result = system("python fetch_games.py");
#else
    int result = system("python3 fetch_games.py");
#endif

    tr.assertTrue(result == 0, "Python script executes successfully");
}

void testGamesFileCreated(TestRunner& tr) {
    tr.assertTrue(fileExists("games.txt"),
                  "games.txt file created");
}

void testGamesFileNotEmpty(TestRunner& tr) {
    vector<string> games = readGamesFile();

    tr.assertTrue(!games.empty(),
                  "games.txt contains at least one game");
}

void testValidFormatting(TestRunner& tr) {
    vector<string> games = readGamesFile();

    bool allValid = true;

    for (const string& game : games) {
        if (!validGameFormat(game)) {
            cout << "  Invalid format: " << game << endl;
            allValid = false;
        }
    }

    tr.assertTrue(allValid,
                  "All games follow 'Team | Team' format");
}

void testNoDuplicateEntries(TestRunner& tr) {
    vector<string> games = readGamesFile();

    tr.assertTrue(noDuplicateGames(games),
                  "No duplicate games exist");
}

void testTeamsNotEmpty(TestRunner& tr) {
    vector<string> games = readGamesFile();

    bool allValid = true;

    for (const string& game : games) {
        if (!teamsAreNonEmpty(game)) {
            cout << "  Empty team found: " << game << endl;
            allValid = false;
        }
    }

    tr.assertTrue(allValid,
                  "No empty team names");
}

void testReasonableGameCount(TestRunner& tr) {
    vector<string> games = readGamesFile();

    // MLB typically has <= 15 games/day
    bool reasonable = games.size() <= 20;

    tr.assertTrue(reasonable,
                  "Reasonable number of games detected");
}

void testNoMalformedSeparators(TestRunner& tr) {
    vector<string> games = readGamesFile();

    bool valid = true;

    for (const string& game : games) {
        int pipeCount = 0;

        for (char c : game) {
            if (c == '|') {
                pipeCount++;
            }
        }

        if (pipeCount != 1) {
            cout << "  Malformed separator count: "
                 << game << endl;
            valid = false;
        }
    }

    tr.assertTrue(valid,
                  "Each line contains exactly one separator");
}

void testWhitespaceHandling(TestRunner& tr) {
    vector<string> games = readGamesFile();

    bool valid = true;

    for (const string& game : games) {

        if (game.front() == ' ' ||
            game.back() == ' ') {

            cout << "  Leading/trailing whitespace: "
                 << game << endl;

            valid = false;
        }
    }

    tr.assertTrue(valid,
                  "No leading/trailing whitespace");
}

void testFileCanBeReadMultipleTimes(TestRunner& tr) {
    vector<string> games1 = readGamesFile();
    vector<string> games2 = readGamesFile();

    tr.assertTrue(games1 == games2,
                  "games.txt stable across multiple reads");
}

int main() {
    TestRunner tr;
    testPythonScriptRuns(tr);
    testGamesFileCreated(tr);
    testGamesFileNotEmpty(tr);
    testValidFormatting(tr);
    testNoDuplicateEntries(tr);
    testTeamsNotEmpty(tr);
    testReasonableGameCount(tr);
    testNoMalformedSeparators(tr);
    testWhitespaceHandling(tr);
    testFileCanBeReadMultipleTimes(tr);
    tr.summary();
    return 0;
}