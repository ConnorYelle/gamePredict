#!/usr/bin/env python3
"""gamePredict -- one entry point for the whole project.

    gamePredict <command> [options]

Most commands are thin facades over the existing scripts (so their flags pass
straight through); ``live`` and ``test`` are handled here directly. Run
``gamePredict help`` for the full list. The ``gamePredict`` / ``gamePredict.cmd``
/ ``gamePredict.ps1`` wrappers next to this file let you call it by name once the
repo is on your PATH.
"""

import importlib.util
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
# Let "from mlb.* import ..." resolve the package under scripts/ for in-process
# commands (live), matching how the scripts/ entrypoints import it.
sys.path.insert(0, str(ROOT / "scripts"))

# name -> (help text, [script path relative to ROOT, baked-in args...])
# Trailing user args are appended, so e.g. `gamePredict train --iters 60` works.
SCRIPT_COMMANDS = {
    "run":      ("Run the full pipeline and print today's predictions",
                 ["runPipeline.py"]),
    "train":    ("Learn weights from past seasons -> config/config.json",
                 ["scripts/train_weights.py"]),
    "backtest": ("Measure accuracy by replaying a past season",
                 ["scripts/validate_predictions.py", "--backtest"]),
    "validate": ("Grade saved predictions against games/results",
                 ["scripts/validate_predictions.py"]),
    "fetch":    ("Fetch today's games + probable starters -> outputs/games.txt",
                 ["scripts/scheduleFetcher.py"]),
    "stats":    ("Collect team batting/pitching/fielding stats",
                 ["scripts/statsCollector.py"]),
    "pitchers": ("Fetch starting-pitcher stats -> StartingPitchers.csv",
                 ["scripts/collect_pitchers.py"]),
    "archive":  ("Save a day's games + final scores into data/schedules/",
                 ["scripts/archive_schedule.py"]),
    "metrics":  ("Backtest and record accuracy/Brier/log-loss to history",
                 ["scripts/track_metrics.py"]),
    "plot":     ("Render the metrics-history chart and refresh the README",
                 ["scripts/plot_metrics_history.py"]),
}

SPECIAL_HELP = {
    "live": "Serve the real-time dashboard (live scores, pitchers, win/loss borders)",
    "test": "Run the test suite (add --coverage for a coverage report)",
    "help": "Show this help",
}


def run_script(parts, extra):
    """Invoke a project script as a subprocess, forwarding the user's args."""
    cmd = [sys.executable, *[str(ROOT / parts[0])], *parts[1:], *extra]
    return subprocess.run(cmd, cwd=str(ROOT)).returncode


def cmd_live(extra):
    """Start the live dashboard server."""
    host, port, open_browser = "127.0.0.1", 8000, True
    predictions = None
    it = iter(extra)
    for arg in it:
        if arg == "--host":
            host = next(it, host)
        elif arg == "--port":
            port = int(next(it, port))
        elif arg == "--no-browser":
            open_browser = False
        elif arg == "--predictions":
            predictions = next(it, None)
        elif arg in ("-h", "--help"):
            print("gamePredict live [--host H] [--port N] [--no-browser] "
                  "[--predictions PATH]")
            return 0
        else:
            print(f"Unknown option for 'live': {arg}")
            return 2

    from mlb.live_server import serve, DEFAULT_PREDICTIONS
    serve(host=host, port=port, open_browser=open_browser,
          predictions_path=predictions or DEFAULT_PREDICTIONS)
    return 0


def cmd_test(extra):
    """Run the unittest suite, optionally under coverage.py."""
    use_coverage = "--coverage" in extra
    passthrough = [a for a in extra if a != "--coverage"]

    if use_coverage and importlib.util.find_spec("coverage") is None:
        print("coverage is not installed. Install it with:\n"
              "    pip install -r requirements-dev.txt\n"
              "Running tests without coverage...\n")
        use_coverage = False

    def py(*args):
        return subprocess.run([sys.executable, *args], cwd=str(ROOT)).returncode

    if not use_coverage:
        return py("-m", "unittest", "discover", *passthrough)

    rc = py("-m", "coverage", "run", "-m", "unittest", "discover", *passthrough)
    print("\n" + "=" * 60 + "\nCOVERAGE REPORT\n" + "=" * 60)
    py("-m", "coverage", "report", "-m")
    py("-m", "coverage", "html")
    print(f"\nHTML report: {ROOT / 'htmlcov' / 'index.html'}")
    return rc


def print_help():
    print(__doc__.strip() + "\n")
    print("Commands:")
    width = max(len(n) for n in {**SCRIPT_COMMANDS, **SPECIAL_HELP})
    order = ["run", "live", "test", "train", "backtest", "validate",
             "fetch", "stats", "pitchers", "archive", "metrics", "plot", "help"]
    helps = {**{k: v[0] for k, v in SCRIPT_COMMANDS.items()}, **SPECIAL_HELP}
    for name in order:
        print(f"  {name.ljust(width)}  {helps[name]}")
    print("\nAdd -h to most commands (e.g. `gamePredict train -h`) for their options.")


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv or argv[0] in ("help", "-h", "--help"):
        print_help()
        return 0

    command, extra = argv[0], argv[1:]
    if command == "live":
        return cmd_live(extra)
    if command == "test":
        return cmd_test(extra)
    if command in SCRIPT_COMMANDS:
        return run_script(SCRIPT_COMMANDS[command][1], extra)

    print(f"Unknown command: {command}\n")
    print_help()
    return 2


if __name__ == "__main__":
    sys.exit(main())
