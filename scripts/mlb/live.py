"""Build the JSON payload that powers the live matchup dashboard.

This is the merge layer between three sources:

* the model's predictions (``outputs/predictions.txt``) -- who the model picked
  and with what probability,
* live game state from :meth:`mlb.MlbStatsApi.live_games` -- scores, inning, and
  the pitcher on the mound, and
* the team season stats already collected for the predictor
  (``data/rawData/<date>/Team*.txt``) -- for the matchup-detail panel.

The output is a plain dict (``{"date", "generated", "error", "games": [...]}``)
that the server hands to the browser as JSON. Keeping it a pure function of its
inputs (the API is injected) is what lets the tests exercise the correct/
incorrect/pending border logic and the score/pitcher passthrough without any
network or files.
"""

import re
from datetime import datetime, timezone
from pathlib import Path

from . import config
from .results_archive import ResultsArchive

# Full team name -> ESPN logo abbreviation. Mirrors the table baked into
# cpp/social_posts.cpp so the live page and the static social preview show the
# same logos; "Athletics" intentionally has no city prefix to match the feed.
TEAM_ABBR = {
    "Arizona Diamondbacks": "ari", "Atlanta Braves": "atl",
    "Baltimore Orioles": "bal", "Boston Red Sox": "bos",
    "Chicago Cubs": "chc", "Chicago White Sox": "chw",
    "Cincinnati Reds": "cin", "Cleveland Guardians": "cle",
    "Colorado Rockies": "col", "Detroit Tigers": "det",
    "Houston Astros": "hou", "Kansas City Royals": "kc",
    "Los Angeles Angels": "laa", "Los Angeles Dodgers": "lad",
    "Miami Marlins": "mia", "Milwaukee Brewers": "mil",
    "Minnesota Twins": "min", "New York Mets": "nym",
    "New York Yankees": "nyy", "Athletics": "oak",
    "Philadelphia Phillies": "phi", "Pittsburgh Pirates": "pit",
    "San Diego Padres": "sd", "San Francisco Giants": "sf",
    "Seattle Mariners": "sea", "St. Louis Cardinals": "stl",
    "Tampa Bay Rays": "tb", "Texas Rangers": "tex",
    "Toronto Blue Jays": "tor", "Washington Nationals": "wsh",
}


def logo_url(team):
    """ESPN CDN logo URL for a full team name (falls back to the generic mark)."""
    abbr = TEAM_ABBR.get(team, "mlb")
    return f"https://a.espncdn.com/i/teamlogos/mlb/500/{abbr}.png"


# A matchup header line: "Away Team @ Home Team" with no leading indentation.
_MATCHUP_RE = re.compile(r"^(?P<away>\S.*?) @ (?P<home>\S.*?)\s*$")
# A probability line: "Team Name            63.1%".
_PCT_RE = re.compile(r"^(?P<name>.*?)\s+(?P<pct>\d{1,2}(?:\.\d+)?)%\s*$")


def parse_predictions(text):
    """Parse predictions.txt into ``[{away, home, away_prob, home_prob,
    favorite}]`` (probabilities as fractions in 0..1).

    The predictor prints each matchup as an ``Away @ Home`` header followed by
    two ``Name  NN.N%`` lines in away-then-home order. We rely only on that
    ordering, so the debug preamble and separator lines are ignored.
    """
    lines = text.splitlines()
    games = []
    i = 0
    while i < len(lines):
        m = _MATCHUP_RE.match(lines[i].strip())
        # Guard against false positives like an email or "X @ Y" prose: require
        # the next non-empty lines to actually carry two percentages.
        if m:
            pcts = []
            for j in range(i + 1, min(i + 8, len(lines))):
                pm = _PCT_RE.match(lines[j].strip())
                if pm:
                    pcts.append(float(pm.group("pct")) / 100.0)
                if len(pcts) == 2:
                    break
            if len(pcts) == 2:
                away_prob, home_prob = pcts
                games.append({
                    "away": m.group("away"),
                    "home": m.group("home"),
                    "away_prob": away_prob,
                    "home_prob": home_prob,
                    "favorite": m.group("home") if home_prob >= away_prob
                    else m.group("away"),
                })
        i += 1
    return games


def _num(cells, idx):
    """Parse cell ``idx`` of a CSV row as float, or None when out of range/bad."""
    if idx >= len(cells):
        return None
    try:
        return float(cells[idx].strip())
    except (ValueError, AttributeError):
        return None


def _read_csv(path):
    rows = []
    try:
        with open(path, encoding="utf-8") as f:
            for line in f:
                cells = line.rstrip("\n").split(",")
                if any(c.strip() for c in cells):
                    rows.append(cells)
    except OSError:
        return []
    return rows


def latest_stats_dir(base=None):
    """Most recent ``data/rawData/<date>/`` folder holding both Team files.

    Folder names are ``MM-DD-YY``; lexical max on that format is wrong across
    years, so sort by the file mtime instead (good enough -- the pipeline writes
    them together)."""
    base = Path(base) if base else (config.ROOT / "data" / "rawData")
    if not base.is_dir():
        return None
    candidates = [d for d in base.iterdir()
                  if d.is_dir()
                  and (d / "TeamStandardBatting.txt").exists()
                  and (d / "TeamFielding.txt").exists()]
    if not candidates:
        return None
    return max(candidates, key=lambda d: d.stat().st_mtime)


def load_team_stats(stats_dir=None):
    """Load per-team season stats keyed by full team name for the detail panel:
    ``{name: {rpg, obp, slg, hr, rag, fld}}``.

    Column contract matches the predictor's input files (and cpp/social_posts):
    batting [0]=Tm [3]=R/G [11]=HR [18]=OBP [19]=SLG; fielding [0]=Tm [2]=RA/G
    [13]=Fld%. Missing files/fields just leave that team (or stat) absent.
    """
    stats_dir = Path(stats_dir) if stats_dir else latest_stats_dir()
    stats = {}
    if not stats_dir:
        return stats

    for row in _read_csv(stats_dir / "TeamStandardBatting.txt")[1:]:
        team = row[0].strip() if row else ""
        if not team:
            continue
        s = stats.setdefault(team, {})
        s["rpg"], s["hr"] = _num(row, 3), _num(row, 11)
        s["obp"], s["slg"] = _num(row, 18), _num(row, 19)

    for row in _read_csv(stats_dir / "TeamFielding.txt")[1:]:
        team = row[0].strip() if row else ""
        if not team:
            continue
        s = stats.setdefault(team, {})
        s["rag"], s["fld"] = _num(row, 2), _num(row, 13)

    return stats


def _border_state(game, live):
    """Card border for a matchup: ``correct``/``incorrect`` once the game is
    final and decided, otherwise ``pending``."""
    if live and live.get("state") == "final" and live.get("winner"):
        return "correct" if live["winner"] == game["favorite"] else "incorrect"
    return "pending"


def build_live_payload(api, predictions_path, date_str=None, stats_dir=None):
    """Assemble the dashboard payload from predictions + live API + team stats.

    Returns ``{"date", "generated", "error", "games": [...]}``. A network/API
    failure is caught and reported via ``error`` with empty live fields so the
    page still renders the model's predictions and shows a banner.
    """
    date_str = date_str or datetime.now().strftime("%Y-%m-%d")
    predictions_path = Path(predictions_path)

    predictions = []
    if predictions_path.exists():
        predictions = parse_predictions(
            predictions_path.read_text(encoding="utf-8"))

    team_stats = load_team_stats(stats_dir)

    error = None
    live_by_key = {}
    try:
        for lg in api.live_games(date_str):
            live_by_key[(lg["away"], lg["home"])] = lg
    except Exception as exc:  # network/shape failure -> degrade gracefully
        error = f"Live data unavailable: {exc}"

    games = []
    for g in predictions:
        live = live_by_key.get((g["away"], g["home"]))
        games.append({
            "away": g["away"],
            "home": g["home"],
            "awayLogo": logo_url(g["away"]),
            "homeLogo": logo_url(g["home"]),
            "awayP": round(g["away_prob"] * 100.0, 1),
            "homeP": round(g["home_prob"] * 100.0, 1),
            "favorite": g["favorite"],
            "awayStats": team_stats.get(g["away"]),
            "homeStats": team_stats.get(g["home"]),
            "state": (live or {}).get("state", "preview"),
            "startTime": (live or {}).get("start_time", ""),
            "detailedState": (live or {}).get("detailed_state", ""),
            "awayScore": (live or {}).get("away_score"),
            "homeScore": (live or {}).get("home_score"),
            "inning": (live or {}).get("inning"),
            "inningState": (live or {}).get("inning_state", ""),
            "isTop": (live or {}).get("is_top"),
            "awaySp": (live or {}).get("away_sp", ""),
            "homeSp": (live or {}).get("home_sp", ""),
            "currentPitcher": (live or {}).get("current_pitcher", ""),
            "winner": (live or {}).get("winner"),
            "border": _border_state(g, live),
        })

    return {
        "date": date_str,
        "mode": "live",
        "generated": datetime.now(timezone.utc).isoformat(),
        "error": error,
        "games": games,
    }


def _to_int(value):
    """Parse an archived score cell (a string) into an int, or None."""
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def build_history_payload(date_str, archive=None, stats_dir=None):
    """Assemble a *past* day's dashboard payload from the results archive.

    This is the historical counterpart to :func:`build_live_payload`: instead of
    polling the MLB API for live state, it reads the day's archived
    ``final_scores.csv`` (actual scores + winner) and merges in the
    ``predictions.txt`` snapshot saved alongside it. Each pick is graded -- the
    card border is ``correct``/``incorrect`` once a final winner is known and a
    prediction exists, else ``pending`` -- and a day-level ``summary`` (record,
    accuracy, Brier) is computed over the graded games.

    Game dicts deliberately share the shape :func:`build_live_payload` emits so
    the dashboard renders both with the same code. ``awayP``/``homeP``/
    ``favorite`` are ``None`` for days archived before predictions were
    snapshotted (results show, but can't be graded). The ``archive`` and
    ``stats_dir`` are injectable so this stays unit-testable without the real
    data tree.
    """
    archive = archive or ResultsArchive()

    try:
        date = datetime.strptime(date_str, "%Y-%m-%d")
    except (TypeError, ValueError):
        return {"date": date_str, "mode": "history", "error":
                f"Invalid date: {date_str!r} (expected YYYY-MM-DD).",
                "summary": None, "hasPredictions": False, "games": []}

    results = archive.load_scores(date)
    pred_text = archive.load_predictions_text(date)
    predictions = parse_predictions(pred_text) if pred_text else []
    result_by_key = {(r.get("away", ""), r.get("home", "")): r for r in results}

    team_stats = load_team_stats(stats_dir) if stats_dir else {}

    # When the day's predictions are saved, drive off them (that's "my picks",
    # and they can be shown even before the day's finals are archived). Older
    # days hold results only, so fall back to listing those.
    if predictions:
        entries = [(p["away"], p["home"], p,
                    result_by_key.get((p["away"], p["home"]))) for p in predictions]
    else:
        entries = [(r.get("away", ""), r.get("home", ""), None, r) for r in results]

    games = []
    matched = correct = 0
    brier_sum = 0.0
    for away, home, pred, res in entries:
        res = res or {}
        has_result = bool(res)
        winner = res.get("winner") or None

        favorite = pred["favorite"] if pred else None
        away_p = round(pred["away_prob"] * 100.0, 1) if pred else None
        home_p = round(pred["home_prob"] * 100.0, 1) if pred else None

        border = "pending"
        if pred and winner:
            border = "correct" if winner == favorite else "incorrect"
            matched += 1
            p_win = pred["home_prob"] if winner == home else pred["away_prob"]
            brier_sum += (1.0 - p_win) ** 2
            if winner == favorite:
                correct += 1

        games.append({
            "away": away,
            "home": home,
            "awayLogo": logo_url(away),
            "homeLogo": logo_url(home),
            "awayP": away_p,
            "homeP": home_p,
            "favorite": favorite,
            "awayStats": team_stats.get(away),
            "homeStats": team_stats.get(home),
            "state": "final" if has_result else "preview",
            "startTime": "",
            "detailedState": "Final" if has_result else "Result pending",
            "awayScore": _to_int(res.get("away_score")),
            "homeScore": _to_int(res.get("home_score")),
            "inning": None,
            "inningState": "",
            "isTop": None,
            "awaySp": res.get("away_sp", ""),
            "homeSp": res.get("home_sp", ""),
            "currentPitcher": "",
            "winner": winner,
            "border": border,
        })

    summary = None
    if matched:
        summary = {
            "games": matched,
            "correct": correct,
            "incorrect": matched - correct,
            "accuracy": round(correct / matched * 100.0, 1),
            "brier": round(brier_sum / matched, 4),
        }

    return {
        "date": date_str,
        "mode": "history",
        "generated": datetime.now(timezone.utc).isoformat(),
        # Only a genuinely empty day (no predictions and no results) is an error.
        # A predictions-only or results-only day renders fine and is flagged via
        # summary/hasPredictions/hasResults for the front-end to message.
        "error": None if (predictions or results)
        else f"No archived data for {date_str}.",
        "summary": summary,
        "hasPredictions": bool(predictions),
        "hasResults": bool(results),
        "games": games,
    }
