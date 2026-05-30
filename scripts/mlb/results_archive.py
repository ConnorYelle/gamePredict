"""Persist past days' schedules with final scores for ongoing validation.

Each day is archived to ``data/schedules/<mm-dd-yy>/``:

* ``final_scores.csv`` -- matchups with actual scores and the winner
* (optional) snapshots of that day's ``games.txt`` / ``predictions.txt``

Keeping a per-day record means the model's predictions can be graded against
real outcomes long after the games are played (see :mod:`mlb.slate_grader`).
"""

import csv
import shutil
from datetime import datetime, timedelta

from . import config

SCORE_FIELDS = ["date", "away", "home", "away_score", "home_score",
                "winner", "home_sp", "away_sp"]
DATE_FMT = "%m-%d-%y"


def parse_date(date_str):
    """Parse a YYYY-MM-DD string into a ``datetime``."""
    return datetime.strptime(date_str, "%Y-%m-%d")


class ResultsArchive:
    """Read/write the per-day ``data/schedules`` archive."""

    def __init__(self, root=None):
        self.base_dir = (root or config.ROOT) / "data" / "schedules"

    def day_dir(self, date):
        """Folder for a given ``datetime`` (created on demand by writers)."""
        return self.base_dir / date.strftime(DATE_FMT)

    def save_scores(self, rows, date):
        """Write ``rows`` (from MlbStatsApi.final_scores) to final_scores.csv."""
        out_dir = self.day_dir(date)
        out_dir.mkdir(parents=True, exist_ok=True)
        path = out_dir / "final_scores.csv"
        with path.open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=SCORE_FIELDS)
            writer.writeheader()
            for r in rows:
                writer.writerow({k: r.get(k, "") for k in SCORE_FIELDS})
        return path

    def load_scores(self, date):
        """Return archived score rows for ``date`` (empty list if none)."""
        path = self.day_dir(date) / "final_scores.csv"
        if not path.exists():
            return []
        with path.open(encoding="utf-8") as f:
            return list(csv.DictReader(f))

    def snapshot(self, date, *files):
        """Copy the given files (e.g. games.txt, predictions.txt) into the day
        folder so a prediction/result pair survives the next pipeline run."""
        out_dir = self.day_dir(date)
        out_dir.mkdir(parents=True, exist_ok=True)
        for src in files:
            if src and src.exists():
                shutil.copy(src, out_dir / src.name)
        return out_dir


def archive_day(api, date, archive=None):
    """Fetch a date's final scores via ``api`` and write them to the archive.
    Returns (rows, path) where ``path`` is None when there were no final games."""
    archive = archive or ResultsArchive()
    rows = api.final_scores(date.strftime("%Y-%m-%d"))
    if not rows:
        return rows, None
    return rows, archive.save_scores(rows, date)


def daterange(start, end):
    """Yield each ``datetime`` from ``start`` to ``end`` inclusive."""
    day = start
    while day <= end:
        yield day
        day += timedelta(days=1)
