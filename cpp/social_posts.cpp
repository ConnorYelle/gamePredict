#include <algorithm>
#include <cmath>
#include <cstdio>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <regex>
#include <sstream>
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

// Per-team season stats used to populate the matchup detail panel. NaN marks a
// value that could not be loaded, which the front-end renders as a dash.
struct TeamStats {
    double rpg = std::nan("");  // runs per game
    double obp = std::nan("");  // on-base percentage
    double slg = std::nan("");  // slugging percentage
    double hr  = std::nan("");  // home runs
    double rag = std::nan("");  // runs allowed per game
    double fld = std::nan("");  // fielding percentage
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

// ------------------------------------------------------------------ //
// Team stats (for the matchup detail panel)
// ------------------------------------------------------------------ //
static std::vector<std::vector<std::string>> read_csv(const fs::path &path) {
    std::vector<std::vector<std::string>> rows;
    std::ifstream f(path);
    if (!f) return rows;
    std::string line;
    while (std::getline(f, line)) {
        std::vector<std::string> row;
        std::stringstream ss(line);
        std::string cell;
        while (std::getline(ss, cell, ',')) row.push_back(cell);
        if (!row.empty()) rows.push_back(row);
    }
    return rows;
}

static double parse_num(const std::string &s) {
    try {
        return std::stod(trim(s));
    } catch (...) {
        return std::nan("");
    }
}

// Most recent data/rawData/<date>/ folder that has the batting + fielding files.
static fs::path latest_stats_dir() {
    fs::path base("data/rawData");
    if (!fs::exists(base) || !fs::is_directory(base)) return {};
    fs::path best;
    for (const auto &e : fs::directory_iterator(base)) {
        if (!e.is_directory()) continue;
        if (fs::exists(e.path() / "TeamStandardBatting.txt") &&
            fs::exists(e.path() / "TeamFielding.txt")) {
            if (best.empty() || e.path().filename() > best.filename())
                best = e.path();
        }
    }
    return best;
}

// Load per-team season stats keyed by full team name (matching the names in
// predictions.txt). Missing files/fields simply leave NaNs behind.
static std::unordered_map<std::string, TeamStats> load_team_stats() {
    std::unordered_map<std::string, TeamStats> stats;
    fs::path dir = latest_stats_dir();
    if (dir.empty()) return stats;

    // Batting: [0]=Tm [3]=R/G [11]=HR [18]=OBP [19]=SLG
    auto batting = read_csv(dir / "TeamStandardBatting.txt");
    for (size_t i = 1; i < batting.size(); ++i) {
        const auto &r = batting[i];
        if (r.size() < 20) continue;
        std::string team = trim(r[0]);
        if (team.empty()) continue;
        TeamStats &t = stats[team];
        t.rpg = parse_num(r[3]);
        t.hr  = parse_num(r[11]);
        t.obp = parse_num(r[18]);
        t.slg = parse_num(r[19]);
    }

    // Fielding: [0]=Tm [2]=RA/G [13]=Fld%
    auto fielding = read_csv(dir / "TeamFielding.txt");
    for (size_t i = 1; i < fielding.size(); ++i) {
        const auto &r = fielding[i];
        if (r.size() < 14) continue;
        std::string team = trim(r[0]);
        if (team.empty()) continue;
        TeamStats &t = stats[team];
        t.rag = parse_num(r[2]);
        t.fld = parse_num(r[13]);
    }

    return stats;
}

// Emit a team's stats as a JS object literal (or "null" when unknown).
static std::string stats_to_js(const std::unordered_map<std::string, TeamStats> &stats,
                               const std::string &team) {
    auto it = stats.find(team);
    if (it == stats.end()) return "null";
    const TeamStats &s = it->second;
    auto num = [](double v) -> std::string {
        if (std::isnan(v)) return "null";
        char b[32];
        std::snprintf(b, sizeof(b), "%.4f", v);
        return std::string(b);
    };
    return "{rpg:" + num(s.rpg) + ",obp:" + num(s.obp) + ",slg:" + num(s.slg) +
           ",hr:" + num(s.hr) + ",rag:" + num(s.rag) + ",fld:" + num(s.fld) + "}";
}
void write_html(const fs::path &out_path,
                const std::vector<GamePrediction> &games,
                const std::string &date_str,
                const std::unordered_map<std::string, TeamStats> &teamStats) {

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
    /* align-items: start keeps each card at its own height, so expanding one
       card's details never stretches its row-mates into tall empty boxes. */
    align-items: start;
}

.card {
    background: #1e293b;
    border-radius: 16px;
    padding: 20px;
    box-shadow: 0 4px 15px rgba(0,0,0,0.3);
    /* Flex column lets the details button pin to the bottom (margin-top:auto)
       so every collapsed card lines its button up at the same baseline. */
    display: flex;
    flex-direction: column;
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
    /* Reserve two lines so one- and two-line team names keep the logos,
       percentages and winner line vertically aligned across every card. */
    min-height: 2.6em;
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
    /* Reserve two lines for winners whose name wraps (e.g. "Washington
       Nationals") so the button below stays aligned card-to-card. */
    min-height: 2.6em;
}

.details-btn {
    /* auto top-margin pushes the button to the bottom of the flex card. */
    margin-top: auto;
    width: 100%;
    padding: 10px;
    background: #334155;
    color: #e2e8f0;
    border: none;
    border-radius: 10px;
    font-size: 14px;
    font-weight: bold;
    cursor: pointer;
    transition: background 0.15s ease;
}

.details-btn:hover {
    background: #3e4c63;
}

.details {
    margin-top: 14px;
    border-top: 1px solid #334155;
    padding-top: 10px;
}

.detail-row {
    display: grid;
    grid-template-columns: 1fr auto 1fr;
    align-items: center;
    gap: 10px;
    padding: 6px 0;
    font-size: 15px;
}

.detail-row .dl {
    color: #94a3b8;
    text-align: center;
    font-size: 12px;
    white-space: nowrap;
}

.detail-row .dv {
    font-variant-numeric: tabular-nums;
    color: #cbd5e1;
    font-weight: bold;
}

.detail-row .dv.away { text-align: right; }
.detail-row .dv.home { text-align: left; }

/* Arrows sit inside a .dv and inherit its computed gradient colour. */
.arrow {
    font-weight: bold;
}

.details-unavailable {
    color: #94a3b8;
    text-align: center;
    font-size: 13px;
    padding: 6px 0;
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
    homeLogo: ")" << logo_url(g.home) << R"(",
    awayStats: )" << stats_to_js(teamStats, g.away) << R"(,
    homeStats: )" << stats_to_js(teamStats, g.home) << R"(
},
)";
    }

    html << R"(
];

const container = document.getElementById("games");

// Stats shown in the matchup detail panel.
//   better: 'high' = larger value is superior, 'low' = smaller is superior.
//   scale : the absolute gap that maps to a fully-saturated colour. Tuned per
//           stat (their natural ranges differ by orders of magnitude) so a
//           decisive edge in any stat reads as a strong colour while a marginal
//           edge stays pale.
const STAT_DEFS = [
    { key: "rpg", label: "Runs / Game",          better: "high", dp: 2, scale: 1.5   },
    { key: "obp", label: "On-Base %",            better: "high", dp: 3, scale: 0.030 },
    { key: "slg", label: "Slugging %",           better: "high", dp: 3, scale: 0.060 },
    { key: "hr",  label: "Home Runs",            better: "high", dp: 0, scale: 25    },
    { key: "rag", label: "Runs Allowed / Game",  better: "low",  dp: 2, scale: 1.5   },
    { key: "fld", label: "Fielding %",           better: "high", dp: 3, scale: 0.010 },
];

// Gradient endpoints: superior -> green, inferior -> red, ties/unknown -> grey.
const C_NEUTRAL = [148, 163, 184];
const C_BETTER  = [34, 197, 94];
const C_WORSE   = [239, 68, 68];

function isNum(v) {
    return typeof v === "number" && !Number.isNaN(v);
}

function fmtStat(v, dp) {
    return isNum(v) ? Number(v).toFixed(dp) : "—";
}

function mixRgb(from, to, t) {
    const c = from.map((v, i) => Math.round(v + (to[i] - v) * t));
    return `rgb(${c[0]}, ${c[1]}, ${c[2]})`;
}

// Colour one side's value relative to the other: green if it is the better
// number, red if worse, with intensity scaled by how big the gap is.
function gradeColor(def, self, other) {
    if (!isNum(self) || !isNum(other) || self === other) return mixRgb(C_NEUTRAL, C_NEUTRAL, 0);
    const t = Math.min(1, Math.abs(self - other) / def.scale);
    const selfBetter = def.better === "high" ? self > other : self < other;
    return mixRgb(C_NEUTRAL, selfBetter ? C_BETTER : C_WORSE, t);
}

function detailRow(def, av, hv) {
    // winner: -1 away superior, 1 home superior, 0 tie/unknown.
    let winner = 0;
    if (isNum(av) && isNum(hv) && av !== hv) {
        const homeBetter = def.better === "high" ? hv > av : hv < av;
        winner = homeBetter ? 1 : -1;
    }

    const awayArrow = winner === -1 ? ` <span class="arrow">&#9664;</span>` : "";
    const homeArrow = winner === 1  ? `<span class="arrow">&#9654;</span> ` : "";

    return `
        <div class="detail-row">
            <div class="dv away" style="color:${gradeColor(def, av, hv)}">${fmtStat(av, def.dp)}${awayArrow}</div>
            <div class="dl">${def.label}</div>
            <div class="dv home" style="color:${gradeColor(def, hv, av)}">${homeArrow}${fmtStat(hv, def.dp)}</div>
        </div>`;
}

function buildDetails(g) {
    const a = g.awayStats, h = g.homeStats;
    if (!a && !h) {
        return `<div class="details-unavailable">Detailed stats unavailable for this matchup.</div>`;
    }
    return STAT_DEFS.map(def => detailRow(def, a ? a[def.key] : null,
                                               h ? h[def.key] : null)).join("");
}

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

        <button class="details-btn" type="button">Matchup details &#9662;</button>
        <div class="details" style="display:none">${buildDetails(g)}</div>
    `;

    const btn = card.querySelector(".details-btn");
    const panel = card.querySelector(".details");

    btn.addEventListener("click", () => {
        const isOpen = panel.style.display !== "none";
        panel.style.display = isOpen ? "none" : "block";
        btn.innerHTML = isOpen ? "Matchup details &#9662;" : "Hide details &#9652;";
    });

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
    auto team_stats = load_team_stats();
    write_html(outdir / "matchup_preview.html", games, date_str, team_stats);

    std::cout << "Generated social posts in " << outdir << "\n";
    return 0;
}
