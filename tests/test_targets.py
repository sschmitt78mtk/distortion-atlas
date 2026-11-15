"""Tests for the checkerboard self-check and flat field (task 3.5)."""

import types
import unittest

import numpy as np

from visiontest.patterns.targets import (
    block_average,
    checkerboard,
    mean_code_value,
    render_flat,
    render_self_check,
)

SIDE = 256


def target_params(**overrides):
    base = dict(variant=0, contrast=100, source_px=41, luminance=127.5)
    base.update(overrides)
    return types.SimpleNamespace(**base)


class CheckerboardTest(unittest.TestCase):
    def test_every_neighbour_alternates(self):
        frame = checkerboard(SIDE, SIDE)
        self.assertTrue(np.all(frame[:, :-1] != frame[:, 1:]))
        self.assertTrue(np.all(frame[:-1, :] != frame[1:, :]))
        self.assertEqual(set(np.unique(frame).tolist()), {0, 255})

    def test_one_pixel_cells_are_exactly_one_pixel_wide(self):
        frame = checkerboard(8, 8)
        expected = np.array(
            [[255, 0] * 4 if row % 2 == 0 else [0, 255] * 4 for row in range(8)],
            dtype=np.uint8,
        )
        self.assertTrue(np.array_equal(frame[:, :, 0], expected))
        self.assertTrue(np.array_equal(frame[:, :, 1], expected))
        self.assertTrue(np.array_equal(frame[:, :, 2], expected))

    def test_exact_fifty_percent_mean(self):
        frame = checkerboard(SIDE, SIDE)
        self.assertEqual(mean_code_value(frame), 127.5)

    def test_two_pixel_block_average_is_uniform_mid_grey(self):
        blocks = block_average(checkerboard(SIDE, SIDE), block=2)
        self.assertTrue(np.allclose(blocks, 127.5))

    def test_larger_cells_stay_square(self):
        frame = checkerboard(16, 16, cell_px=2)
        self.assertTrue(
            np.array_equal(frame[0:2, 0:2], np.full((2, 2, 3), 255, np.uint8))
        )
        self.assertTrue(np.array_equal(frame[0:2, 2:4], np.zeros((2, 2, 3), np.uint8)))
        self.assertEqual(mean_code_value(frame), 127.5)

    def test_self_check_pattern_is_the_plain_checkerboard(self):
        plain = checkerboard(SIDE, SIDE)
        rendered = render_self_check(target_params(), SIDE, SIDE)
        self.assertTrue(np.array_equal(plain, rendered))

    def test_reference_patch_is_optional_and_flat_grey(self):
        params = target_params(reference_patch=True, source_px=41)
        frame = render_self_check(params, SIDE, SIDE)
        centre = SIDE // 2
        self.assertEqual(int(frame[centre, centre, 0]), 128)
        self.assertFalse(
            np.array_equal(frame, checkerboard(SIDE, SIDE)),
        )


class FlatFieldTest(unittest.TestCase):
    def test_integer_luminance_is_exact(self):
        frame = render_flat(target_params(luminance=100), 64, 64)
        self.assertEqual(set(np.unique(frame).tolist()), {100})

    def test_fractional_luminance_is_dithered_to_the_requested_mean(self):
        frame = render_flat(target_params(luminance=127.5), 64, 64)
        self.assertEqual(set(np.unique(frame).tolist()), {127, 128})
        self.assertEqual(mean_code_value(frame), 127.5)

    def test_each_two_by_two_block_reports_the_mean(self):
        frame = render_flat(target_params(luminance=127.5), 64, 64)
        blocks = block_average(frame, block=2)
        self.assertTrue(np.all(blocks >= 127.0))
        self.assertTrue(np.all(blocks <= 128.0))

    def test_flat_field_is_uniform_across_channels(self):
        frame = render_flat(target_params(luminance=80), 32, 32)
        self.assertTrue(np.array_equal(frame[:, :, 0], frame[:, :, 2]))
        self.assertEqual(tuple(frame[0, 0]), (80, 80, 80))

    def test_black_and_white_extremes(self):
        self.assertEqual(
            set(np.unique(render_flat(target_params(luminance=0), 16, 16)).tolist()),
            {0},
        )
        self.assertEqual(
            set(np.unique(render_flat(target_params(luminance=255), 16, 16)).tolist()),
            {255},
        )


if __name__ == "__main__":
    unittest.main()
