"""Tests for the train_weights CLI's metrics-history logging.

Training itself (coordinate descent, log-loss) is covered by test_trainer; here
we only pin that a run records the held-out validation result to the history,
with no network and without touching the real config.json or history file.
"""

import io
import sys
import unittest
from contextlib import redirect_stdout
from unittest import mock

import train_weights


class FakeTrainer:
    """Stand-in for WeightTrainer: returns one neutral game and a no-op optimize
    so main() runs fully offline."""

    def __init__(self, api=None):
        pass

    def collect_inputs(self, seasons, use_pitchers, use_cache=True):
        return [{"home": {}, "away": {}, "home_sp": None,
                 "away_sp": None, "home_won": True}]

    def report(self, *args, **kwargs):
        pass

    def optimize(self, inputs, init, iters):
        return dict(init), 0.5


def run_main(argv, log_mock):
    with mock.patch.object(train_weights, "WeightTrainer", FakeTrainer), \
         mock.patch.object(train_weights.metrics_log, "log_run", log_mock), \
         mock.patch.object(train_weights.config, "save_weights") as save_mock, \
         mock.patch.object(sys, "argv", ["train_weights.py", *argv]):
        with redirect_stdout(io.StringIO()):
            train_weights.main()
    return save_mock


class TrainLoggingTests(unittest.TestCase):
    def test_logs_validation_metrics_with_note(self):
        log_mock = mock.Mock()
        run_main(["--dry-run", "-n", "added bullpen"], log_mock)

        log_mock.assert_called_once()
        args, kwargs = log_mock.call_args
        # First positional arg is the evaluate() metrics dict.
        self.assertIn("brier_score", args[0])
        self.assertIn("added bullpen", kwargs["note"])
        self.assertIn("[dry-run]", kwargs["note"])
        self.assertEqual(kwargs["season"], 2025)

    def test_no_log_flag_skips_recording(self):
        log_mock = mock.Mock()
        run_main(["--dry-run", "--no-log"], log_mock)
        log_mock.assert_not_called()

    def test_real_run_logs_without_dry_run_marker(self):
        log_mock = mock.Mock()
        save_mock = run_main([], log_mock)
        save_mock.assert_called_once()  # weights persisted on a real run
        log_mock.assert_called_once()
        self.assertNotIn("[dry-run]", log_mock.call_args.kwargs["note"])


if __name__ == "__main__":
    unittest.main()
