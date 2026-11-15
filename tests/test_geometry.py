"""Tests for :mod:`visiontest.geometry`."""

import unittest

from visiontest.geometry import (
    DEFAULT_MARGIN_PX,
    Scale,
    fit_field,
    max_field_deg,
    snap_pitch,
)

PITCH_MM = 0.178
PX_PER_MM = 1.0 / PITCH_MM
PANEL = (1920, 1080)


def scale_at(distance_mm: float) -> Scale:
    return Scale(px_per_mm=PX_PER_MM, distance_mm=distance_mm)


class ScaleTest(unittest.TestCase):
    def test_arcmin_per_pixel_at_400_mm(self):
        """0.178 mm pitch at 400 mm is the 1.53 arcmin/px the spec quotes."""
        scale = scale_at(400)
        self.assertAlmostEqual(scale.arcmin_per_px, 1.5298, places=4)
        self.assertEqual(round(scale.arcmin_per_px, 2), 1.53)
        self.assertAlmostEqual(scale.mm_per_px, PITCH_MM, places=9)

    def test_39_px_target_is_about_one_degree_and_seven_millimetres(self):
        scale = scale_at(400)
        self.assertAlmostEqual(scale.field_for_px(39), 1.0, delta=0.01)
        self.assertAlmostEqual(scale.mm_for_px(39), 6.95, delta=0.02)

    def test_distance_change_rescales_the_report_only(self):
        """400 mm -> 500 mm shrinks every angle by 400/500; pixels are unchanged."""
        near, far = scale_at(400), scale_at(500)
        self.assertAlmostEqual(far.arcmin_per_px / near.arcmin_per_px, 0.8, places=4)
        self.assertEqual(round(far.arcmin_per_px, 2), 1.22)
        self.assertEqual(near.mm_for_px(39), far.mm_for_px(39))
        self.assertAlmostEqual(
            far.px_for_degrees(20) / near.px_for_degrees(20), 1.25, places=4
        )

    def test_degree_and_arcmin_round_trip(self):
        scale = scale_at(400)
        px = scale.px_for_degrees(20.0)
        self.assertAlmostEqual(scale.field_for_px(px), 20.0, places=9)
        self.assertAlmostEqual(scale.arcmin_for_px(px), 1200.0, places=6)

    def test_scale_rejects_impossible_values(self):
        with self.assertRaises(ValueError):
            Scale(px_per_mm=0, distance_mm=400)
        with self.assertRaises(ValueError):
            Scale(px_per_mm=PX_PER_MM, distance_mm=0)
        with self.assertRaises(ValueError):
            Scale(px_per_mm=PX_PER_MM, distance_mm=400, source="guessed")

    def test_calibration_flips_the_source(self):
        calibrated = scale_at(400).with_calibration(5.6)
        self.assertEqual(calibrated.source, "calibrated")
        self.assertEqual(calibrated.px_per_mm, 5.6)
        self.assertEqual(scale_at(400).source, "panel_derived")


class SnapPitchTest(unittest.TestCase):
    def test_fractional_pitch_snaps_down(self):
        self.assertEqual(snap_pitch(39.3), 39)
        self.assertEqual(snap_pitch(58.83), 58)
        self.assertEqual(snap_pitch(52.0), 52)

    def test_pitch_never_below_one_pixel(self):
        self.assertEqual(snap_pitch(0.4), 1)
        self.assertEqual(snap_pitch(0.0), 1)


class FitFieldTest(unittest.TestCase):
    def test_requested_pitch_is_snapped_and_field_recomputed(self):
        """A 20° / 20-square request at 400 mm asks for 39.3 px per square."""
        scale = scale_at(400)
        self.assertAlmostEqual(scale.px_for_degrees(20) / 20, 39.2208, places=3)
        fit = fit_field(scale, field_deg=20.0, squares=20, width=1920, height=1080)
        self.assertEqual(fit.pitch_px, 39)
        self.assertTrue(fit.snapped)
        self.assertFalse(fit.fitted)
        self.assertEqual(fit.pixels, 780)
        self.assertAlmostEqual(fit.field_deg, 19.89, delta=0.01)
        self.assertAlmostEqual(fit.field_deg, fit.scale.field_for_px(780), places=9)

    def test_20_degrees_at_600_mm_overflows_the_buffer(self):
        """The largest field that fits is reported instead of a crop."""
        scale = scale_at(600)
        fit = fit_field(scale, field_deg=20.0, squares=20, width=1920, height=1080)
        self.assertTrue(fit.fitted)
        self.assertLess(fit.field_deg, 20.0)
        self.assertLessEqual(fit.pixels + 2 * fit.margin_px, PANEL[1])
        self.assertEqual(fit.pitch_px, (PANEL[1] - 2 * DEFAULT_MARGIN_PX) // 20)
        self.assertAlmostEqual(fit.field_deg, 18.02, delta=0.02)
        self.assertAlmostEqual(
            fit.reduction_deg, 20.0 - fit.field_deg, places=9
        )

    def test_fitted_field_always_keeps_the_margin(self):
        scale = scale_at(400)
        for squares in (4, 15, 20, 26, 40):
            with self.subTest(squares=squares):
                fit = fit_field(scale, 20.0, squares, 1920, 1080)
                self.assertLessEqual(fit.pixels + 2 * fit.margin_px, PANEL[1])
                self.assertGreaterEqual(fit.pitch_px, 1)

    def test_max_field_matches_the_fit_of_a_generous_request(self):
        scale = scale_at(600)
        limit = max_field_deg(scale, 20, 1920, 1080)
        fit = fit_field(scale, 20.0, 20, 1920, 1080)
        self.assertAlmostEqual(limit, fit.field_deg, places=6)

    def test_rejects_impossible_requests(self):
        scale = scale_at(400)
        with self.assertRaises(ValueError):
            fit_field(scale, 20.0, 0, 1920, 1080)
        with self.assertRaises(ValueError):
            fit_field(scale, 0.0, 20, 1920, 1080)
        with self.assertRaises(ValueError):
            fit_field(scale, 20.0, 20, 10, 10)


if __name__ == "__main__":
    unittest.main()
