"""Tests for the Amsler grid and M-chart renderers (tasks 3.1 and 3.2)."""

import types
import unittest

import numpy as np

from visiontest.patterns import BLACK, WHITE
from visiontest.patterns.grids import (
    DOT_PX,
    PAIRINGS,
    PAIRING_NAMES,
    field_extent,
    grading_marker_offset,
    grid_cuts,
    line_positions,
    pairing_colours,
    pairing_name,
    render_amsler,
    render_lines,
)

SIDE = 400


def pattern_params(**overrides):
    base = dict(
        variant=0,
        squares=20,
        contrast=100,
        dot_pitch=20,
        line_count=7,
        source_px=1,
    )
    base.update(overrides)
    return types.SimpleNamespace(**base)


def runs(row_mask):
    """(start, end) pairs of runs of True in a 1-D boolean array."""
    padded = np.concatenate(([False], row_mask, [False]))
    edges = np.flatnonzero(padded[1:] != padded[:-1])
    return list(zip(edges[0::2], edges[1::2]))


class AmslerGridTest(unittest.TestCase):
    def test_pairing_names_are_stable(self):
        self.assertEqual(
            PAIRING_NAMES,
            ("black_on_white", "white_on_black", "red_on_black", "blue_on_yellow"),
        )
        self.assertEqual(pairing_name(2), "red_on_black")
        self.assertEqual(pairing_name(6), "red_on_black")

    def test_pairing_switch_keeps_the_geometry(self):
        """The same grid drawn in another pairing lights the same pixels."""
        black_on_white = render_amsler(pattern_params(variant=0), SIDE, SIDE)
        red_on_black = render_amsler(pattern_params(variant=2), SIDE, SIDE)
        mask_a = np.any(black_on_white != WHITE, axis=2)
        mask_b = np.any(red_on_black != BLACK, axis=2)
        self.assertTrue(np.array_equal(mask_a, mask_b))
        self.assertEqual(tuple(red_on_black[0, 0]), BLACK)
        self.assertEqual(
            tuple(red_on_black[SIDE // 2, SIDE // 2]), PAIRINGS["red_on_black"][1]
        )

    def test_grid_lines_are_symmetric_about_the_centre(self):
        cx = 200
        for squares in (4, 10, 13, 20, 33):
            with self.subTest(squares=squares):
                cuts = grid_cuts(cx, 384, squares)
                self.assertEqual(len(cuts), squares + 1)
                for left, right in zip(cuts, reversed(cuts)):
                    self.assertEqual(left + right, 2 * cx)

    def test_outer_boundary_does_not_move_with_the_square_count(self):
        for count in (10, 13, 20, 26):
            with self.subTest(squares=count):
                cuts = grid_cuts(200, 384, count)
                self.assertEqual(cuts[0], 200 - 192)
                self.assertEqual(cuts[-1], 200 + 192)

    def test_pitch_is_exact_when_the_extent_divides_evenly(self):
        cuts = grid_cuts(200, 40, 20)
        self.assertEqual({b - a for a, b in zip(cuts, cuts[1:])}, {2})

    def test_pitch_is_never_fractional(self):
        for squares in (7, 11, 13, 26, 33):
            with self.subTest(squares=squares):
                cuts = grid_cuts(200, 384, squares)
                self.assertTrue(all(isinstance(cut, int) for cut in cuts))
                diffs = {b - a for a, b in zip(cuts, cuts[1:])}
                self.assertLessEqual(max(diffs) - min(diffs), 1)
                self.assertGreaterEqual(min(diffs), 1)

    def test_rendered_lines_are_one_pixel_wide_and_bilevel(self):
        frame = render_amsler(pattern_params(squares=10), SIDE, SIDE)
        self.assertEqual(len(np.unique(frame.reshape(-1, 3), axis=0)), 2)
        background, stroke = PAIRINGS["black_on_white"]
        extent = field_extent(SIDE, SIDE)
        cuts = grid_cuts(SIDE // 2, extent, 10)
        top, bottom = SIDE // 2 - extent // 2, SIDE // 2 + extent // 2
        self.assertTrue(np.all(frame[top:bottom, cuts[3]] == stroke))
        self.assertTrue(np.all(frame[:top, cuts[3]] == background))
        self.assertTrue(np.all(frame[bottom + 1 :, cuts[3]] == background))

        # Inside a cell, the vertical stroke is exactly one pixel wide.
        row = (cuts[2] + cuts[3]) // 2
        self.assertTrue(np.all(frame[row, cuts[2]] == stroke))
        self.assertTrue(np.all(frame[row, cuts[2] + 1] == background))
        self.assertTrue(np.all(frame[row, cuts[3] - 1] == background))
        self.assertTrue(np.all(frame[row, cuts[3]] == stroke))
        self.assertTrue(np.all(frame[row, cuts[3] + 1] == background))

    def test_contrast_fades_the_line_without_moving_it(self):
        full = render_amsler(pattern_params(contrast=100), SIDE, SIDE)
        faded = render_amsler(pattern_params(contrast=40), SIDE, SIDE)
        self.assertTrue(
            np.array_equal(
                np.any(full != WHITE, axis=2), np.any(faded != WHITE, axis=2)
            )
        )
        cuts = grid_cuts(SIDE // 2, field_extent(SIDE, SIDE), 20)
        line_pixel = tuple(faded[SIDE // 2, cuts[5]])
        self.assertLess(line_pixel[0], 255)
        self.assertGreater(line_pixel[0], 128)
        self.assertLess(255 - line_pixel[0], line_pixel[0])

    def test_background_follows_the_pairing(self):
        frame = render_amsler(pattern_params(variant=3), SIDE, SIDE)
        self.assertEqual(tuple(frame[0, 0]), PAIRINGS["blue_on_yellow"][0])

    def test_settings_outside_the_canvas_are_clipped(self):
        frame = render_amsler(pattern_params(squares=2), 40, 20)
        self.assertEqual(frame.shape, (20, 40, 3))

    def test_contrast_zero_reports_the_background_stroke(self):
        background, stroke = pairing_colours(0, 0)
        self.assertEqual(background, WHITE)
        self.assertEqual(stroke, background)


class MChartTest(unittest.TestCase):
    def test_dot_pitch_is_exact_whole_pixels(self):
        for pitch in (8, 20, 37):
            with self.subTest(pitch=pitch):
                frame = render_lines(
                    pattern_params(dot_pitch=pitch, line_count=5), SIDE, SIDE
                )
                row = SIDE // 2
                centres = [
                    (start + end - 1) / 2.0
                    for start, end in runs(np.all(frame[row] == BLACK, axis=1))
                ]
                right = [centre for centre in centres if centre > SIDE // 2]
                self.assertGreaterEqual(len(right), 2)
                gaps = {round(b - a) for a, b in zip(right, right[1:])}
                self.assertEqual(gaps, {pitch})

    def test_line_set_is_centred_on_the_fixation_anchor(self):
        for count in (1, 4, 7, 11):
            with self.subTest(count=count):
                positions = line_positions(SIDE // 2, 384, count)
                self.assertEqual(len(positions), count)
                self.assertEqual(sum(positions) / count, SIDE // 2)

    def test_line_positions_are_whole_pixels_for_any_count(self):
        for count in (2, 3, 8, 13):
            with self.subTest(count=count):
                positions = line_positions(200, 384, count)
                self.assertTrue(all(isinstance(p, int) for p in positions))
                if count > 2:
                    diffs = {b - a for a, b in zip(positions, positions[1:])}
                    self.assertLessEqual(max(diffs) - min(diffs), 1)

    def test_a_dot_sits_on_the_anchor_and_nothing_shifts_by_a_fraction(self):
        frame = render_lines(pattern_params(dot_pitch=24, line_count=7), SIDE, SIDE)
        anchor_row = SIDE // 2
        self.assertTrue(np.all(frame[anchor_row, SIDE // 2] == BLACK))
        starts = [
            start for start, _ in runs(np.all(frame[anchor_row] == BLACK, axis=1))
        ]
        self.assertTrue(starts)
        for start in starts:
            if start > SIDE // 2:
                centre = start + DOT_PX // 2
                self.assertEqual((centre - SIDE // 2) % 24, 0)

    def test_orientation_variants_change_the_direction_only(self):
        horizontal = render_lines(pattern_params(variant=0), SIDE, SIDE)
        vertical = render_lines(pattern_params(variant=1), SIDE, SIDE)
        self.assertTrue(np.all(horizontal[SIDE // 2, SIDE // 2] == BLACK))
        self.assertTrue(np.all(vertical[SIDE // 2, SIDE // 2] == BLACK))
        self.assertEqual(
            int(np.count_nonzero(np.any(vertical != WHITE, axis=2))),
            int(np.count_nonzero(np.any(horizontal != WHITE, axis=2))),
        )

    def test_grading_reference_grows_with_the_line_index(self):
        frame = render_lines(pattern_params(line_count=5, contrast=100), SIDE, SIDE)
        left_edge = SIDE // 2 - field_extent(SIDE, SIDE) // 2
        positions = line_positions(SIDE // 2, field_extent(SIDE, SIDE), 5)
        lengths = []
        for position in positions:
            row = np.all(frame[position + grading_marker_offset()] == BLACK, axis=1)
            run = runs(row)
            self.assertTrue(run, f"no reference dash for the line at {position}")
            first_start, first_end = run[0]
            self.assertEqual(first_start, left_edge)
            lengths.append(first_end - first_start)
        self.assertEqual(lengths, [DOT_PX * (index + 1) for index in range(5)])

    def test_faded_contrast_keeps_dot_positions(self):
        full = render_lines(pattern_params(contrast=100, line_count=5), SIDE, SIDE)
        faded = render_lines(pattern_params(contrast=30, line_count=5), SIDE, SIDE)
        self.assertTrue(
            np.array_equal(
                np.any(full != WHITE, axis=2), np.any(faded != WHITE, axis=2)
            )
        )

    def test_single_line_lands_on_the_centre(self):
        frame = render_lines(pattern_params(line_count=1), SIDE, SIDE)
        self.assertTrue(np.all(frame[SIDE // 2, SIDE // 2] == BLACK))


if __name__ == "__main__":
    unittest.main()
