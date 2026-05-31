"""Append-only history of model evaluation metrics.

Each backtest run appends one JSON line to ``data/metrics_history.jsonl`` capturing
*when* it ran, the *git commit* and a free-text *note* (so you can tie a number to
a model change), the headline metrics (accuracy / Brier / log-loss), and the full
weight set that produced them. Committing the history file lets you watch the
metrics move as you iterate on the model.

The file is plain JSON Lines so it stays diff-friendly and append-only -- a bad
or malformed line never corrupts earlier history.
"""

import json
import subprocess
from datetime import datetime, timezone

from . import config

HISTORY_PATH = config.ROOT / "data" / "metrics_history.jsonl"


def git_commit():
    """Short HEAD commit with a trailing ``*`` when the tree is dirty, or "" if
    git is unavailable / this isn't a repo. Best-effort and never raises."""
    try:
        sha = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=str(config.ROOT), capture_output=True, text=True, timeout=5)
        if sha.returncode != 0:
            return ""
        rev = sha.stdout.strip()
        dirty = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=str(config.ROOT), capture_output=True, text=True, timeout=5)
        return rev + ("*" if dirty.stdout.strip() else "")
    except Exception:
        return ""


def build_record(metrics, weights, *, note="", season=None,
                 window=None, use_pitchers=None, commit=None):
    """Assemble (but do not write) a history record from an ``evaluate`` metrics
    dict plus the weights and run metadata."""
    return {
        "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "note": note,
        "git": git_commit() if commit is None else commit,
        "season": season,
        "window": list(window) if window else None,
        "use_pitchers": use_pitchers,
        "games": metrics.get("games_evaluated"),
        "accuracy": metrics.get("accuracy"),
        "brier": metrics.get("brier_score"),
        "log_loss": metrics.get("log_loss"),
        "home_field_baseline": metrics.get("home_field_baseline"),
        "weights": dict(weights),
    }


def log_run(metrics, weights, *, path=HISTORY_PATH, **meta):
    """Append one run's metrics to the history file and return the record."""
    record = build_record(metrics, weights, **meta)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(record) + "\n")
    return record


def load_history(path=HISTORY_PATH):
    """Return all history records oldest-first. Malformed lines are skipped so a
    single bad row never blocks reading the rest."""
    records = []
    if not path.exists():
        return records
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                records.append(json.loads(line))
            except ValueError:
                continue
    return records


def _cell(value, fmt):
    # ASCII only: this prints to the terminal, including cp1252 Windows consoles.
    return format(value, fmt) if isinstance(value, (int, float)) else "-"


def format_table(records):
    """Render history records as a fixed-width table, with the Brier delta from
    the previous row so improvement/regression is visible at a glance."""
    if not records:
        return "No metrics history yet. Run a backtest with --log to record one."

    header = (f"{'date (UTC)':<17} {'git':<9} {'games':>5} "
              f"{'acc':>7} {'brier':>7} {'dbrier':>8} {'logloss':>8}  note")
    lines = [header, "-" * len(header)]
    prev_brier = None
    for r in records:
        brier = r.get("brier")
        if isinstance(brier, (int, float)) and isinstance(prev_brier, (int, float)):
            # Negative delta = Brier went down = improvement.
            delta = f"{brier - prev_brier:+.4f}"
        else:
            delta = "-"
        if isinstance(brier, (int, float)):
            prev_brier = brier
        date = (r.get("timestamp") or "")[:16].replace("T", " ")
        lines.append(
            f"{date:<17} {(r.get('git') or '-'):<9} "
            f"{_cell(r.get('games'), 'd'):>5} "
            f"{_cell(r.get('accuracy'), '.2%'):>7} "
            f"{_cell(brier, '.4f'):>7} {delta:>8} "
            f"{_cell(r.get('log_loss'), '.4f'):>8}  {r.get('note') or ''}")
    return "\n".join(lines)
