"""Tests for mlb.social — text post generation and the matchup image.

Pillow is a hard dependency of this module; if it is unavailable the whole
module import fails and these tests are skipped.
"""

import tempfile
import unittest
from pathlib import Path

try:
    from mlb import social
    HAVE_SOCIAL = True
except Exception:  # pragma: no cover - depends on Pillow being installed
    HAVE_SOCIAL = False


SAMPLE = (
    "New York Yankees @ Boston Red Sox\n"
    "New York Yankees 45.0%\n"
    "Boston Red Sox 55.0%\n"
    "Chicago Cubs @ St. Louis Cardinals\n"
    "Chicago Cubs 30.0%\n"
    "St. Louis Cardinals 70.0%\n"
)


@unittest.skipUnless(HAVE_SOCIAL, "mlb.social (Pillow) unavailable")
class TeamStyleServiceTests(unittest.TestCase):
    def test_known_abbreviation(self):
        self.assertEqual(social.TeamStyleService.abbreviation("Los Angeles Dodgers"),
                         "LAD")

    def test_unknown_abbreviation_from_initials(self):
        self.assertEqual(social.TeamStyleService.abbreviation("Springfield Isotopes"),
                         "SI")

    def test_known_colors(self):
        primary, _ = social.TeamStyleService.colors("New York Yankees")
        self.assertEqual(primary, "#0c2340")

    def test_unknown_colors_default(self):
        self.assertEqual(social.TeamStyleService.colors("Nobody United"),
                         ("#616161", "#f4f4f4"))


@unittest.skipUnless(HAVE_SOCIAL, "mlb.social (Pillow) unavailable")
class ParsePredictionsTests(unittest.TestCase):
    def setUp(self):
        with tempfile.TemporaryDirectory() as d:
            self.manager = social.SocialPostManager(Path(d))
        self.games = self.manager.parse_predictions(SAMPLE)

    def test_parses_all_games(self):
        self.assertEqual(len(self.games), 2)

    def test_sorted_by_favorite_prob_desc(self):
        self.assertGreaterEqual(self.games[0]["favorite_prob"],
                                self.games[1]["favorite_prob"])

    def test_favorite_and_swing(self):
        cards = {g["home"]: g for g in self.games}
        cubs_game = cards["St. Louis Cardinals"]
        self.assertEqual(cubs_game["favorite"], "St. Louis Cardinals")
        self.assertAlmostEqual(cubs_game["favorite_prob"], 70.0)
        self.assertAlmostEqual(cubs_game["swing"], 40.0)

    def test_ignores_unpaired_block(self):
        text = "Lonely @ Game\nLonely 50.0%\n"  # only one percent line
        self.assertEqual(self.manager.parse_predictions(text), [])


@unittest.skipUnless(HAVE_SOCIAL, "mlb.social (Pillow) unavailable")
class PostGeneratorTests(unittest.TestCase):
    def setUp(self):
        with tempfile.TemporaryDirectory() as d:
            mgr = social.SocialPostManager(Path(d))
        self.preds = mgr.parse_predictions(SAMPLE)

    def test_twitter_post_mentions_best_pick(self):
        post = social.TwitterPostGenerator(self.preds).generate_post()
        self.assertIn("Best pick:", post)
        self.assertIn("#MLB", post)

    def test_instagram_tiers(self):
        post = social.InstagramPostGenerator(self.preds).generate_post()
        self.assertIn("LOCK", post)  # 70% favorite -> LOCK

    def test_empty_predictions_handled(self):
        post = social.TwitterPostGenerator([]).generate_post()
        self.assertIn("No prediction data", post)

    def test_confidence_tiers(self):
        gen = social.InstagramPostGenerator([])
        self.assertEqual(gen.confidence_tier(70), "LOCK")
        self.assertEqual(gen.confidence_tier(60), "LEAN")
        self.assertEqual(gen.confidence_tier(50), "TOSS-UP")


@unittest.skipUnless(HAVE_SOCIAL, "mlb.social (Pillow) unavailable")
class SocialPostManagerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        self.manager = social.SocialPostManager(self.dir)

    def tearDown(self):
        self.tmp.cleanup()

    def test_generate_writes_all_artifacts(self):
        self.manager.generate_social_posts(SAMPLE)
        self.assertTrue((self.dir / "twitter_post.txt").exists())
        self.assertTrue((self.dir / "instagram_caption.txt").exists())
        self.assertTrue((self.dir / "matchup_preview.png").exists())

    def test_image_is_valid_png(self):
        from PIL import Image
        preds = self.manager.parse_predictions(SAMPLE)
        self.manager.generate_social_image(preds)
        with Image.open(self.dir / "matchup_preview.png") as img:
            self.assertEqual(img.format, "PNG")
            self.assertGreater(img.width, 0)

    def test_empty_predictions_skip_image(self):
        self.manager.generate_social_image([])
        self.assertFalse((self.dir / "matchup_preview.png").exists())


if __name__ == "__main__":
    unittest.main()
