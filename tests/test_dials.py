"""Tests for the astigmatism clock dial (task 3.3)."""

import math
import types
import unittest

import numpy as np

from distortion_atlas.patterns import BLACK, WHITE, spoke_mask
from distortion_atlas.patterns.dials import (
    CROSSED_RATIO,
    SPOKE_WIDTH_PX,
    angle_step_deg,
    crossed_angles,
    dial_angles,
    render_dial,
    spoke_endpoint,
    spoke_radius,
)

SIDE = 400
RADIUS = spoke_radius(SIDE, SIDE)


def dial_params(**overrides):
    base = dict(
        variant=0,
        spoke_count=12,
        rotation_deg=0,
        contrast=100,
        source_px=1,
    )
    base.update(overrides)
    return types.SimpleNamespace(**base)


def lit_near(frame, x, y, reach=2):
    """True when any pixel within ``reach`` of (x, y) is not black."""
    height, width = frame.shape[:2]
    xs = slice(max(0, x - reach), min(width, x + reach + 1))
    ys = slice(max(0, y - reach), min(height, y + reach + 1))
    return bool(np.any(frame[ys, xs] != BLACK))


class DialAngleTest(unittest.TestCase):
    def test_angles_are_regular_steps(self):
        self.assertEqual(dial_angles(4), (0.0, 90.0, 180.0, 270.0))
        self.assertEqual(dial_angles(12)[1], 30.0)
        self.assertEqual(angle_step_deg(8), 45.0)
        self.assertEqual(angle_step_deg(7), 360.0 / 7.0)

    def test_rotation_shifts_every_spoke_by_the_same_step(self):
        base = dial_angles(12, 0)
        rotated = dial_angles(12, 15)
        for before, after in zip(base, rotated):
            self.assertAlmostEqual((after - before) % 360.0, 15.0, places=9)

    def test_rotation_wraps_and_is_modular(self):
        self.assertEqual(dial_angles(4, 360), dial_angles(4, 0))
        self.assertEqual(dial_angles(4, 375), dial_angles(4, 15))

    def test_crossed_target_shares_the_dial_orientations(self):
        self.assertEqual(crossed_angles(9, 30), dial_angles(9, 30))

    def test_zero_spokes_is_rejected(self):
        with self.assertRaises(ValueError):
            dial_angles(0)


class DialGeometryTest(unittest.TestCase):
    def test_spoke_length_is_constant_across_angles(self):
        lengths = []
        for angle in dial_angles(8, 0):
            mask = spoke_mask(SIDE, SIDE, 200, 200, angle, RADIUS, SPOKE_WIDTH_PX)
            rows, columns = np.nonzero(mask)
            self.assertGreater(rows.size, 0)
            distances = np.hypot(columns - 200, rows - 200)
            lengths.append(distances.max())
        self.assertTrue(all(abs(length - RADIUS) <= 1.5 for length in lengths), lengths)
        self.assertLessEqual(max(lengths) - min(lengths), 2.0)

    def test_spoke_reads_pixels_from_the_centre_outwards(self):
        counts = []
        for angle in dial_angles(12, 0):
            mask = spoke_mask(SIDE, SIDE, 200, 200, angle, 100, SPOKE_WIDTH_PX)
            counts.append(int(np.count_nonzero(mask)))
        mean = sum(counts) / len(counts)
        for count in counts:
            self.assertLess(abs(count - mean) / mean, 0.1, counts)
        self.assertGreater(mean, 100)

    def test_endpoint_rounds_to_a_whole_pixel_on_the_right_axis(self):
        self.assertEqual(spoke_endpoint(200, 200, 0.0, 50), (250, 200))
        self.assertEqual(spoke_endpoint(200, 200, 90.0, 50), (200, 150))
        self.assertEqual(spoke_endpoint(200, 200, 180.0, 50), (150, 200))

    def test_rotation_does_not_change_length_or_width(self):
        first = spoke_mask(SIDE, SIDE, 200, 200, 0, 120, SPOKE_WIDTH_PX)
        second = spoke_mask(SIDE, SIDE, 200, 200, 15, 120, SPOKE_WIDTH_PX)
        self.assertLess(
            abs(int(first.sum()) - int(second.sum())) / max(1, int(first.sum())), 0.1
        )


class DialRenderTest(unittest.TestCase):
    def test_dial_is_bilevel_and_centred(self):
        frame = render_dial(dial_params(spoke_count=8), SIDE, SIDE)
        colours = np.unique(frame.reshape(-1, 3), axis=0)
        self.assertEqual(len(colours), 2)
        self.assertIn(tuple(colours[0]), (BLACK, WHITE))
        self.assertTrue(lit_near(frame, 200, 200, reach=1))

    def test_spokes_point_outwards_only(self):
        """With 5 spokes the opposite direction is empty except for the cross."""
        frame = render_dial(dial_params(spoke_count=5), SIDE, SIDE)
        far = int(RADIUS * 0.6)
        near = int(RADIUS * CROSSED_RATIO) - 4
        aim = math.radians(180.0)
        x_far = 200 + int(round(far * math.cos(aim)))
        y_far = 200 - int(round(far * math.sin(aim)))
        self.assertFalse(lit_near(frame, x_far, y_far))
        x_near = 200 + int(round(near * math.cos(aim)))
        y_near = 200 - int(round(near * math.sin(aim)))
        self.assertTrue(lit_near(frame, x_near, y_near))

    def test_rotation_redraws_without_moving_the_spokes(self):
        base = render_dial(dial_params(spoke_count=8, rotation_deg=0), SIDE, SIDE)
        turned = render_dial(dial_params(spoke_count=8, rotation_deg=15), SIDE, SIDE)
        self.assertFalse(np.array_equal(base, turned))
        lit_base = int(np.count_nonzero(np.any(base != BLACK, axis=2)))
        lit_turned = int(np.count_nonzero(np.any(turned != BLACK, axis=2)))
        self.assertLess(abs(lit_base - lit_turned) / lit_base, 0.05)

    def test_lower_contrast_fades_the_stroke(self):
        frame = render_dial(dial_params(contrast=40), SIDE, SIDE)
        self.assertEqual(int(frame[0, 0, 0]), 0)
        stroke_pixel = int(frame[200, 200 + 40, 0])
        self.assertGreater(stroke_pixel, 0)
        self.assertLess(stroke_pixel, 255)


if __name__ == "__main__":
    unittest.main()
