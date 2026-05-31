"""Write team season stats in the layout the C++ engine reads.

The predictor (cpp/GamePredictor.cpp) and the HTML detail panel
(cpp/social_posts.cpp) parse ``TeamStandardBatting.txt`` / ``TeamFielding.txt``
by fixed column index, originally the raw baseball-reference table format. Two
properties of that loader must be honoured here:

* rows are comma-separated with a header row first, and
* the loader skips the final two rows (baseball-reference's league
  average/total rows), so we append two filler rows to keep every team in range.

Keeping this format in one place means the column contract with the C++ side
lives in exactly one file.
"""

from pathlib import Path

BATTING_HEADER = ["Tm", "#Bat", "BatAge", "R/G", "G", "PA", "AB", "R", "H",
                  "2B", "3B", "HR", "RBI", "SB", "CS", "BB", "SO", "BA", "OBP",
                  "SLG", "OPS", "OPS+", "TB", "GDP", "HBP", "SH", "SF", "IBB", "LOB"]
FIELDING_HEADER = ["Tm", "#Fld", "RA/G", "DefEff", "G", "GS", "CG", "Inn", "Ch",
                   "PO", "A", "E", "DP", "Fld%", "Rtot", "Rtot/yr", "Rdrs",
                   "Rdrs/yr", "Rgood"]

# Column indices the C++ loader reads. MUST stay in sync with
# GamePredictor::loadAllStats and social_posts.cpp::load_team_stats.
B_TM, B_RG, B_HR, B_BA, B_OBP, B_SLG = 0, 3, 11, 17, 18, 19
F_TM, F_RAG, F_FLD = 0, 2, 13

# Two trailing rows the C++ loader discards; their names never match a game.
_FILLER_NAMES = ("League Average", "League Totals")

BATTING_FILE = "TeamStandardBatting.txt"
FIELDING_FILE = "TeamFielding.txt"

# Bullpen split, read by GamePredictor::loadAllStats. Header + one row per team
# (no filler rows: the C++ bullpen loader reads every data row). Blank cells mean
# "unknown" and are skipped in scoring, matching StartingPitchers.csv.
BULLPEN_FILE = "TeamBullpen.csv"
BULLPEN_HEADER = ["name", "era", "kbb"]


def _blank_row(width):
    return ["0"] * width


def _stat_or_blank(value):
    """Format a stat for CSV: blank when unknown (None or negative sentinel)."""
    if value is None:
        return ""
    value = float(value)
    return "" if value < 0 else f"{value:.3f}"


def batting_rows(teams):
    """Build header + per-team + filler rows for TeamStandardBatting.txt.

    ``teams`` is an iterable of dicts with name/runsPerGame/battingAvg/
    onBasePercentage/sluggingPercentage/homeRuns (missing values default to 0).
    """
    rows = [list(BATTING_HEADER)]
    for t in teams:
        row = _blank_row(len(BATTING_HEADER))
        row[B_TM] = t.get("name", "")
        row[B_RG] = f"{float(t.get('runsPerGame', 0.0)):.2f}"
        row[B_HR] = str(int(round(float(t.get("homeRuns", 0.0)))))
        row[B_BA] = f"{float(t.get('battingAvg', 0.0)):.3f}"
        row[B_OBP] = f"{float(t.get('onBasePercentage', 0.0)):.3f}"
        row[B_SLG] = f"{float(t.get('sluggingPercentage', 0.0)):.3f}"
        rows.append(row)
    for name in _FILLER_NAMES:
        row = _blank_row(len(BATTING_HEADER))
        row[B_TM] = name
        rows.append(row)
    return rows


def fielding_rows(teams):
    """Build header + per-team + filler rows for TeamFielding.txt.

    Uses runsAllowedPerGame/fieldingPercentage (missing values default to 0).
    """
    rows = [list(FIELDING_HEADER)]
    for t in teams:
        row = _blank_row(len(FIELDING_HEADER))
        row[F_TM] = t.get("name", "")
        row[F_RAG] = f"{float(t.get('runsAllowedPerGame', 0.0)):.2f}"
        row[F_FLD] = f"{float(t.get('fieldingPercentage', 0.0)):.3f}"
        rows.append(row)
    for name in _FILLER_NAMES:
        row = _blank_row(len(FIELDING_HEADER))
        row[F_TM] = name
        rows.append(row)
    return rows


def bullpen_rows(teams):
    """Build header + per-team rows for TeamBullpen.csv.

    Uses bullpenEra/bullpenKbb (missing or negative values written blank).
    """
    rows = [list(BULLPEN_HEADER)]
    for t in teams:
        rows.append([
            t.get("name", ""),
            _stat_or_blank(t.get("bullpenEra")),
            _stat_or_blank(t.get("bullpenKbb")),
        ])
    return rows


def _write_csv(path, rows):
    path.write_text("\n".join(",".join(r) for r in rows) + "\n", encoding="utf-8")


def write_stat_files(teams, out_dir):
    """Write all stat files into ``out_dir`` and return the batting/fielding paths."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    batting = out_dir / BATTING_FILE
    fielding = out_dir / FIELDING_FILE
    _write_csv(batting, batting_rows(teams))
    _write_csv(fielding, fielding_rows(teams))
    _write_csv(out_dir / BULLPEN_FILE, bullpen_rows(teams))
    return batting, fielding


def is_populated(out_dir):
    """True when ``out_dir`` already holds non-empty batting + fielding files.

    The bullpen file is optional (the predictor degrades gracefully without it),
    so it is not part of the populated check.
    """
    out_dir = Path(out_dir)
    for name in (BATTING_FILE, FIELDING_FILE):
        f = out_dir / name
        if not f.exists() or f.stat().st_size == 0:
            return False
    return True
