"""Tests for the unified ``gamePredict`` dispatcher.

Imports gamePredict.py from the repo root and stubs subprocess.run so command
routing (which script + which args) is verified without actually launching the
pipeline, tests, or a server.
"""

import io
import sys
import unittest
from contextlib import redirect_stdout
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import gamePredict  # noqa: E402


class FakeProc:
    def __init__(self, returncode=0):
        self.returncode = returncode


class DispatchTests(unittest.TestCase):
    def setUp(self):
        self.calls = []

        def fake_run(cmd, cwd=None, **kw):
            self.calls.append((list(cmd), cwd))
            return FakeProc(0)

        self._orig = gamePredict.subprocess.run
        gamePredict.subprocess.run = fake_run
        self.addCleanup(lambda: setattr(gamePredict.subprocess, "run", self._orig))

    def last_cmd(self):
        return self.calls[-1][0]

    def test_help_lists_commands(self):
        buf = io.StringIO()
        with redirect_stdout(buf):
            rc = gamePredict.main(["help"])
        out = buf.getvalue()
        self.assertEqual(rc, 0)
        for name in ("run", "live", "test", "train", "backtest"):
            self.assertIn(name, out)

    def test_no_args_shows_help(self):
        buf = io.StringIO()
        with redirect_stdout(buf):
            rc = gamePredict.main([])
        self.assertEqual(rc, 0)
        self.assertIn("Commands:", buf.getvalue())

    def test_unknown_command_errors(self):
        buf = io.StringIO()
        with redirect_stdout(buf):
            rc = gamePredict.main(["frobnicate"])
        self.assertEqual(rc, 2)
        self.assertIn("Unknown command", buf.getvalue())

    def test_run_routes_to_pipeline(self):
        gamePredict.main(["run"])
        cmd = self.last_cmd()
        self.assertTrue(cmd[-1].endswith("runPipeline.py"))

    def test_train_forwards_extra_args(self):
        gamePredict.main(["train", "--iters", "60", "--dry-run"])
        cmd = self.last_cmd()
        self.assertTrue(any(c.endswith("train_weights.py") for c in cmd))
        self.assertEqual(cmd[-3:], ["--iters", "60", "--dry-run"])

    def test_backtest_includes_baked_flag(self):
        gamePredict.main(["backtest", "--season", "2024"])
        cmd = self.last_cmd()
        self.assertIn("--backtest", cmd)
        self.assertEqual(cmd[-2:], ["--season", "2024"])

    def test_test_command_runs_unittest(self):
        rc = gamePredict.main(["test"])
        self.assertEqual(rc, 0)
        self.assertEqual(self.last_cmd()[1:4], ["-m", "unittest", "discover"])

    def test_coverage_falls_back_when_missing(self):
        import importlib.util
        orig = importlib.util.find_spec
        importlib.util.find_spec = lambda name: (None if name == "coverage"
                                                 else orig(name))
        self.addCleanup(lambda: setattr(importlib.util, "find_spec", orig))
        buf = io.StringIO()
        with redirect_stdout(buf):
            gamePredict.main(["test", "--coverage"])
        # Fell back to a plain unittest run (no coverage subcommand used).
        self.assertEqual(self.last_cmd()[1:4], ["-m", "unittest", "discover"])
        self.assertIn("coverage is not installed", buf.getvalue())


if __name__ == "__main__":
    unittest.main()
