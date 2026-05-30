"""Tests for mlb.config — weight load/save with defaults and fallback."""

import json
import tempfile
import unittest
from pathlib import Path

from mlb import config


class LoadWeightsTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / "config.json"

    def tearDown(self):
        self.tmp.cleanup()

    def test_missing_file_returns_defaults(self):
        weights = config.load_weights(self.path)
        self.assertEqual(weights, config.DEFAULT_WEIGHTS)
        # must be a copy, not the module-level dict
        self.assertIsNot(weights, config.DEFAULT_WEIGHTS)

    def test_malformed_json_returns_defaults(self):
        self.path.write_text("{ not json ", encoding="utf-8")
        self.assertEqual(config.load_weights(self.path), config.DEFAULT_WEIGHTS)

    def test_partial_weights_fill_from_defaults(self):
        self.path.write_text(json.dumps({"weights": {"offenseWeight": 0.9}}),
                             encoding="utf-8")
        weights = config.load_weights(self.path)
        self.assertEqual(weights["offenseWeight"], 0.9)
        self.assertEqual(weights["defenseWeight"],
                         config.DEFAULT_WEIGHTS["defenseWeight"])

    def test_unknown_keys_ignored(self):
        self.path.write_text(json.dumps({"weights": {"bogus": 1.0}}),
                             encoding="utf-8")
        weights = config.load_weights(self.path)
        self.assertNotIn("bogus", weights)

    def test_string_values_coerced_to_float(self):
        self.path.write_text(json.dumps({"weights": {"offenseWeight": "0.75"}}),
                             encoding="utf-8")
        self.assertEqual(config.load_weights(self.path)["offenseWeight"], 0.75)


class SaveWeightsTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / "config.json"

    def tearDown(self):
        self.tmp.cleanup()

    def test_round_trip(self):
        weights = dict(config.DEFAULT_WEIGHTS, offenseWeight=1.23)
        config.save_weights(weights, self.path)
        self.assertEqual(config.load_weights(self.path), weights)

    def test_saved_shape(self):
        config.save_weights(config.DEFAULT_WEIGHTS, self.path)
        on_disk = json.loads(self.path.read_text(encoding="utf-8"))
        self.assertIn("weights", on_disk)
        self.assertEqual(on_disk["weights"], config.DEFAULT_WEIGHTS)


class DefaultsTests(unittest.TestCase):
    def test_pitcher_weights_default_zero(self):
        # An untrained model must behave exactly like the team-only formula.
        for key in ("pitcherEraWeight", "pitcherWhipWeight",
                    "pitcherK9Weight", "pitcherRecentFormWeight"):
            self.assertEqual(config.DEFAULT_WEIGHTS[key], 0.0)

    def test_repo_config_matches_default_keys(self):
        # The checked-in config must carry exactly the model's weight names.
        weights = config.load_weights()
        self.assertEqual(set(weights), set(config.DEFAULT_WEIGHTS))


if __name__ == "__main__":
    unittest.main()
