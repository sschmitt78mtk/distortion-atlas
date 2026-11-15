"""Tests for the central fixation mark (task 4.2)."""

import types
import unittest

import numpy as np

from distortion_atlas.fixation import (
    DEFAULT_COLOUR,
    DEFAULT_KIND,
    DEFAULT_SIZE_PX,
    RING_THICKNESS_PX,
    apply_fixation,
    covers_centre,
    draw_fixation,
    fixation_mask,
    snap_size,
)
from distortion_atlas.patterns import BLACK, GREY, WHITE, anchor, blank

SIDE = 120


def fixation_params(**overrides):
    base = dict(
        fixation_visible=True,
        fixation_kind=DEFAULT_KIND,
        fixation_px=DEFAULT_SIZE_PX,
    )
    base.update(overrides)
    return types.SimpleNamespace(**base)


class FixationMaskTest(unittest.TestCase):
    def test_size_is_always_odd(self):
        self.assertEqual(snap_size(11), 11)
        self.assertEqual(snap_size(12), 11)
        self.assertEqual(snap_size(2), 3)

    def test_ring_does_not_cover_the_centre_pixel(self):
        for size in (7, 9, 11, 17, 25):
            with self.subTest(size=size):
                self.assertFalse(covers_centre(size, "ring"))
        self.assertFalse(covers_centre(DEFAULT_SIZE_PX, DEFAULT_KIND))

    def test_dot_covers_the_centre_pixel(self):
        self.assertTrue(covers_centre(7, "dot"))

    def test_mark_is_symmetric_about_the_anchor(self):
        cx, cy = anchor(SIDE, SIDE)
        for kind in ("ring", "dot"):
            with self.subTest(kind=kind):
                mask = fixation_mask(SIDE, SIDE, cx, cy, kind, 11)
                radius = 11 // 2
                for step in range(1, radius + 1):
                    self.assertEqual(mask[cy, cx + step], mask[cy, cx - step])
                    self.assertEqual(mask[cy + step, cx], mask[cy - step, cx])
                    self.assertEqual(mask[cy + step, cx + step], mask[cy - step, cx - step])

    def test_ring_is_a_hollow_circle_of_the_requested_size(self):
        cx, cy = anchor(SIDE, SIDE)
        mask = fixation_mask(SIDE, SIDE, cx, cy, "ring", 11)
        rows, columns = np.nonzero(mask)
        self.assertEqual(int(columns.max() - columns.min()) + 1, 11)
        self.assertEqual(int(rows.max() - rows.min()) + 1, 11)
        self.assertFalse(mask[cy, cx])
        self.assertGreaterEqual(RING_THICKNESS_PX, 1)

    def test_dot_is_filled(self):
        cx, cy = anchor(SIDE, SIDE)
        mask = fixation_mask(SIDE, SIDE, cx, cy, "dot", 9)
        self.assertTrue(mask[cy, cx])
        self.assertEqual(int(mask.sum()), 49)
        row_counts = mask.sum(axis=1)
        self.assertEqual(int(row_counts[cy]), 9)
        self.assertEqual(row_counts[cy - 4], row_counts[cy + 4])
        self.assertEqual(row_counts[cy - 1], row_counts[cy + 1])

    def test_unknown_kind_is_rejected(self):
        with self.assertRaises(ValueError):
            fixation_mask(SIDE, SIDE, 60, 60, "cross", 11)


class FixationDrawTest(unittest.TestCase):
    def test_drawing_touches_only_the_mark(self):
        frame = blank(SIDE, SIDE, GREY)
        painted = draw_fixation(frame, *anchor(SIDE, SIDE))
        changed = np.any(painted != frame, axis=2)
        self.assertTrue(np.array_equal(changed, fixation_mask(SIDE, SIDE, *anchor(SIDE, SIDE))))
        self.assertEqual(tuple(painted[anchor(SIDE, SIDE)[1], anchor(SIDE, SIDE)[0]]), GREY)

    def test_hiding_the_mark_leaves_every_other_pixel_unchanged(self):
        frame = blank(SIDE, SIDE, GREY)
        hidden = apply_fixation(frame, fixation_params(fixation_visible=False))
        self.assertTrue(np.array_equal(hidden, frame))
        self.assertFalse(np.any(np.any(hidden != GREY, axis=2)))

    def test_showing_the_mark_changes_only_the_ring(self):
        frame = blank(SIDE, SIDE, GREY)
        shown = apply_fixation(frame, fixation_params())
        changed = np.any(shown != frame, axis=2)
        expected = fixation_mask(SIDE, SIDE, *anchor(SIDE, SIDE), "ring", DEFAULT_SIZE_PX)
        self.assertTrue(np.array_equal(changed, expected))
        self.assertEqual(tuple(shown[0, 0]), GREY)
        self.assertEqual(
            tuple(shown[anchor(SIDE, SIDE)[1], anchor(SIDE, SIDE)[0] + 5]), DEFAULT_COLOUR
        )

    def test_kind_and_size_come_from_the_parameters(self):
        frame = blank(SIDE, SIDE, WHITE)
        painted = apply_fixation(
            frame, fixation_params(fixation_kind="dot", fixation_px=7)
        )
        centre = anchor(SIDE, SIDE)[1], anchor(SIDE, SIDE)[0]
        self.assertEqual(tuple(painted[centre]), DEFAULT_COLOUR)
        changed = np.any(painted != frame, axis=2)
        self.assertEqual(int(changed.sum()), int(fixation_mask(SIDE, SIDE, *anchor(SIDE, SIDE), "dot", 7).sum()))

    def test_drawing_never_mutates_the_input(self):
        frame = blank(SIDE, SIDE, BLACK)
        frame_copy = frame.copy()
        draw_fixation(frame, *anchor(SIDE, SIDE))
        self.assertTrue(np.array_equal(frame, frame_copy))


if __name__ == "__main__":
    unittest.main()
