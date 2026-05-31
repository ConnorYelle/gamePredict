"""Tests for mlb.metrics_chart — the dependency-free SVG history chart."""

import unittest

from mlb import metrics_chart, metrics_log


def rec(note, acc, brier, ll, commit="c"):
    return metrics_log.build_record(
        {"games_evaluated": 2400, "accuracy": acc, "brier_score": brier,
         "log_loss": ll, "home_field_baseline": 0.529},
        {}, note=note, commit=commit)


class RenderSvgTests(unittest.TestCase):
    def test_empty_history_is_valid_svg_with_placeholder(self):
        svg = metrics_chart.render_svg([])
        self.assertTrue(svg.startswith("<svg"))
        self.assertTrue(svg.rstrip().endswith("</svg>"))
        self.assertIn("No runs recorded yet", svg)

    def test_single_point_renders_without_a_line(self):
        svg = metrics_chart.render_svg([rec("only", 0.58, 0.235, 0.66)])
        self.assertIn("<circle", svg)          # the lone marker
        self.assertNotIn("<polyline", svg)     # no line for one point
        self.assertIn("Brier score", svg)

    def test_many_points_draw_a_line_per_panel(self):
        recs = [rec("a", 0.565, 0.243, 0.679), rec("b", 0.596, 0.234, 0.660),
                rec("c", 0.590, 0.235, 0.661)]
        svg = metrics_chart.render_svg(recs)
        # one polyline for each of the three metric panels
        self.assertEqual(svg.count("<polyline"), 3)
        self.assertIn("Accuracy", svg)
        self.assertIn("Log-loss", svg)
        self.assertIn("oldest", svg)

    def test_improvement_direction_is_labelled(self):
        # Brier falling = improvement; accuracy rising = improvement.
        recs = [rec("a", 0.55, 0.245, 0.69), rec("b", 0.60, 0.230, 0.66)]
        svg = metrics_chart.render_svg(recs)
        self.assertIn("improved", svg)
        self.assertNotIn("worse", svg)

    def test_handles_missing_metric_values(self):
        # A run missing brier should not crash; other panels still render.
        partial = metrics_log.build_record(
            {"games_evaluated": 10, "accuracy": 0.58, "log_loss": 0.66},
            {}, note="partial", commit="c")
        svg = metrics_chart.render_svg([partial])
        self.assertTrue(svg.startswith("<svg"))
        self.assertIn("no data yet", svg)  # the brier panel has nothing to plot


if __name__ == "__main__":
    unittest.main()
