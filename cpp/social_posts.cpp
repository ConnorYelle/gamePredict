#include <algorithm>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <regex>
#include <string>
#include <unordered_map>
#include <vector>

namespace fs = std::filesystem;

struct GamePrediction {
    std::string away;
    std::string home;
    double away_prob{0.0};
    double home_prob{0.0};
    std::string favorite;
    double favorite_prob{0.0};
};

static inline std::string trim(const std::string &s) {
    auto a = s.find_first_not_of(" \t\r\n");
    if (a == std::string::npos) return "";
    auto b = s.find_last_not_of(" \t\r\n");
    return s.substr(a, b - a + 1);
}

std::vector<GamePrediction> parse_predictions(const fs::path &pred_path) {
    std::vector<GamePrediction> out;
    std::ifstream f(pred_path);
    if (!f) return out;

    std::string line;
    std::vector<std::string> lines;
    while (std::getline(f, line)) lines.push_back(line);

    std::regex at_re("^(.*)@(.+)$");
    std::regex pct_re("^(.*)\\s+(\\d{1,2}\\.\\d)%$");

    for (size_t i = 0; i < lines.size(); ++i) {
        std::smatch m;
        std::string l = trim(lines[i]);
        if (std::regex_search(l, m, at_re)) {
            GamePrediction g;
            g.away = trim(m[1]);
            g.home = trim(m[2]);

            // find next two percentage lines
            double p1 = -1, p2 = -1;
            for (size_t j = i + 1; j < lines.size() && (p1 < 0 || p2 < 0); ++j) {
                std::smatch mm;
                std::string lj = trim(lines[j]);
                if (std::regex_search(lj, mm, pct_re)) {
                    double val = std::stod(mm[2]) / 100.0;
                    if (p1 < 0) p1 = val;
                    else if (p2 < 0) p2 = val;
                }
            }

            if (p1 >= 0 && p2 >= 0) {
                // assume percentages appear in same order as team lines (away then home)
                g.away_prob = p1;
                g.home_prob = p2;
                if (g.home_prob >= g.away_prob) {
                    g.favorite = g.home;
                    g.favorite_prob = g.home_prob * 100.0;
                } else {
                    g.favorite = g.away;
                    g.favorite_prob = g.away_prob * 100.0;
                }
                out.push_back(g);
            }
        }
    }

    return out;
}

std::string fmt_pct(double v) {
    char buf[32];
    std::snprintf(buf, sizeof(buf), "%.1f%%", v * 100.0);
    return std::string(buf);
}
void write_html(const fs::path &out_path,
                const std::vector<GamePrediction> &games,
                const std::string &date_str) {

    static const std::unordered_map<std::string,std::string> ABBR = {
        {"Arizona Diamondbacks","ari"},
        {"Atlanta Braves","atl"},
        {"Baltimore Orioles","bal"},
        {"Boston Red Sox","bos"},
        {"Chicago Cubs","chc"},
        {"Chicago White Sox","chw"},
        {"Cincinnati Reds","cin"},
        {"Cleveland Guardians","cle"},
        {"Colorado Rockies","col"},
        {"Detroit Tigers","det"},
        {"Houston Astros","hou"},
        {"Kansas City Royals","kc"},
        {"Los Angeles Angels","laa"},
        {"Los Angeles Dodgers","lad"},
        {"Miami Marlins","mia"},
        {"Milwaukee Brewers","mil"},
        {"Minnesota Twins","min"},
        {"New York Mets","nym"},
        {"New York Yankees","nyy"},
        {"Athletics","oak"},
        {"Philadelphia Phillies","phi"},
        {"Pittsburgh Pirates","pit"},
        {"San Diego Padres","sd"},
        {"San Francisco Giants","sf"},
        {"Seattle Mariners","sea"},
        {"St. Louis Cardinals","stl"},
        {"Tampa Bay Rays","tb"},
        {"Texas Rangers","tex"},
        {"Toronto Blue Jays","tor"},
        {"Washington Nationals","wsh"}
    };

    auto logo_url = [&](const std::string &team) -> std::string {
        auto it = ABBR.find(team);
        std::string abbr = (it != ABBR.end()) ? it->second : "mlb";

        return "https://a.espncdn.com/i/teamlogos/mlb/500/" +
               abbr + ".png";
    };

    std::ofstream html(out_path);

    html << R"(<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">

<title>MLB Predictions</title>

<style>

body {
    margin: 0;
    padding: 20px;
    font-family: Arial, sans-serif;
    background: #0f172a;
    color: white;
}

h1 {
    text-align: center;
    margin-bottom: 40px;
}

.games {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
    gap: 20px;
}

.card {
    background: #1e293b;
    border-radius: 16px;
    padding: 20px;
    box-shadow: 0 4px 15px rgba(0,0,0,0.3);
}

.teams {
    display: flex;
    justify-content: space-between;
    align-items: center;
}

.team {
    text-align: center;
    width: 40%;
}

.team img {
    width: 90px;
    height: 90px;
    object-fit: contain;
}

.team-name {
    margin-top: 10px;
    font-weight: bold;
}

.prob {
    margin-top: 8px;
    font-size: 24px;
    font-weight: bold;
}

.vs {
    font-size: 22px;
    font-weight: bold;
}

.favorite {
    margin-top: 20px;
    text-align: center;
    font-size: 18px;
    color: #60a5fa;
}

</style>
</head>

<body>

<h1>MLB Predictions - )" << date_str << R"(</h1>

<div class="games" id="games"></div>

<script>

const games = [
)";

    for (const auto &g : games) {

        html << R"(
{
    away: ")" << g.away << R"(",
    home: ")" << g.home << R"(",
    awayP: )" << (g.away_prob * 100.0) << R"(,
    homeP: )" << (g.home_prob * 100.0) << R"(,
    awayLogo: ")" << logo_url(g.away) << R"(",
    homeLogo: ")" << logo_url(g.home) << R"("
},
)";
    }

    html << R"(
];

const container = document.getElementById("games");

games.forEach(g => {

    const favorite =
        g.homeP >= g.awayP
        ? g.home
        : g.away;

    const card = document.createElement("div");

    card.className = "card";

    card.innerHTML = `
        <div class="teams">

            <div class="team">
                <img src="${g.awayLogo}" alt="${g.away}">
                <div class="team-name">${g.away}</div>
                <div class="prob">${g.awayP.toFixed(1)}%</div>
            </div>

            <div class="vs">VS</div>

            <div class="team">
                <img src="${g.homeLogo}" alt="${g.home}">
                <div class="team-name">${g.home}</div>
                <div class="prob">${g.homeP.toFixed(1)}%</div>
            </div>

        </div>

        <div class="favorite">
            Predicted Winner: ${favorite}
        </div>
    `;

    container.appendChild(card);

});

</script>

</body>
</html>
)";
}
int main(int argc, char **argv) {
    fs::path predictions = "outputs/predictions.txt";
    fs::path outdir = "outputs/social_posts";
    fs::path logos_dir = "mlb_logos";

    if (argc > 1) predictions = argv[1];
    if (argc > 2) outdir = argv[2];
    if (argc > 3) logos_dir = argv[3];

    try {
        fs::create_directories(outdir);
    } catch (...) {}

    auto games = parse_predictions(predictions);

    // write twitter_post.txt
    std::ofstream tw(outdir / "twitter_post.txt");
    tw << "MLB predictions for today\n\n";
    tw << "Top matchups:\n";

    // top 3 by favorite_prob
    std::sort(games.begin(), games.end(), [](const GamePrediction &a, const GamePrediction &b){
        return a.favorite_prob > b.favorite_prob;
    });

    size_t topn = std::min<size_t>(3, games.size());
    for (size_t i = 0; i < topn; ++i) {
        auto &g = games[i];
        // format: Away @ Home: HomeProb / AwayProb
        tw << g.away << " @ " << g.home << ": "
           << (g.home_prob * 100.0) << "% / " << (g.away_prob * 100.0) << "%\n";
    }

    if (!games.empty()) {
        auto &best = games.front();
        tw << "\nBest pick: " << best.favorite << " at " << best.favorite_prob << "%\n";
    }

    tw << "#MLB #Baseball #ProbableWinner\n\n";
    tw << "Data-driven MLB predictions from gamePredict\n";
    tw.close();

    // instagram caption
    std::ofstream ig(outdir / "instagram_caption.txt");
    ig << "Today's MLB prediction recap\n\n";
    size_t ig_top = std::min<size_t>(5, games.size());
    for (size_t i = 0; i < ig_top; ++i) {
        auto &g = games[i];
        ig << "• " << g.away << " @ " << g.home << " — " << g.favorite << " (" << g.favorite_prob << "%)\n";
    }
    ig << "\nTap for more MLB analytics and daily predictions.\n";
    ig << "#MLBPrediction #BaseballAnalytics #GameDay\n";
    ig.close();

    std::string date_str = "today";
    write_html(outdir / "matchup_preview.html", games, date_str);

    std::cout << "Generated social posts in " << outdir << "\n";
    return 0;
}
