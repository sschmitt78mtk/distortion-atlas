"""Tests for the halo, veiling-glare and ghost targets (task 3.4)."""

import types
import unittest

import numpy as np

from distortion_atlas.patterns import BLACK, WHITE, anchor, disc_mask
from distortion_atlas.patterns.glare import (
    GHOST_DIRECTIONS,
    GHOST_LINE_PX,
    ghost_edge_position,
    halo_value,
    measured_diameter,
    render_ghost,
    render_halo,
    render_veil,
    source_diameter_px,
    surround_side_px,
    veil_target_diameter_px,
    veil_target_value,
)

SIDE = 200


def glare_params(**overrides):
    base = dict(
        variant=0,
        contrast=20,
        source_px=48,
        surround_px=160,
        surround_luminance=235.0,
        luminance=200.5,
        ghost_offset=7,
        ghost_direction="right",
    )
    base.update(overrides)
    return types.SimpleNamespace(**base)


class HaloTest(unittest.TestCase):
    def test_source_luminance_is_dithered_to_the_requested_mean(self):
        params = glare_params(luminance=200.5)
        frame = render_halo(params, SIDE, SIDE)
        cx, cy = anchor(SIDE, SIDE)
        disc = disc_mask(SIDE, SIDE, cx, cy, params.source_px)
        values = frame[disc][:, 0]
        self.assertAlmostEqual(float(values.mean()), 200.5, delta=3.0)
        self.assertEqual(set(np.unique(values).tolist()), {200, 201})

    def test_source_diameter_matches_the_readout(self):
        params = glare_params()
        frame = render_halo(params, SIDE, SIDE)
        lit = np.any(frame != BLACK, axis=2)
        self.assertEqual(source_diameter_px(params), 47)
        self.assertEqual(measured_diameter(lit), source_diameter_px(params))
        self.assertEqual(measured_diameter(lit, row=anchor(SIDE, SIDE)[1]), 47)

    def test_field_outside_the_source_stays_black(self):
        frame = render_halo(glare_params(), SIDE, SIDE)
        self.assertEqual(tuple(frame[0, 0]), BLACK)
        self.assertEqual(tuple(frame[SIDE - 1, SIDE - 1]), BLACK)

    def test_a_full_intensity_source_is_white(self):
        frame = render_halo(glare_params(luminance=255), SIDE, SIDE)
        cx, cy = anchor(SIDE, SIDE)
        self.assertEqual(tuple(frame[cy, cx]), WHITE)
        self.assertAlmostEqual(halo_value(glare_params(luminance=255)), 255.0)


class VeilTest(unittest.TestCase):
    def test_surround_and_target_luminances(self):
        params = glare_params()
        frame = render_veil(params, SIDE, SIDE)
        cx, cy = anchor(SIDE, SIDE)
        side = surround_side_px(params)
        x0, y0 = cx - side // 2, cy - side // 2

        ring = frame[y0 + 4 : y0 + 12, x0 + 4 : x0 + 12, 0]
        self.assertEqual(float(ring.mean()), 235.0)

        disc = disc_mask(SIDE, SIDE, cx, cy, veil_target_diameter_px(params))
        self.assertAlmostEqual(
            float(frame[disc][:, 0].mean()), veil_target_value(params), delta=1.0
        )
        self.assertAlmostEqual(veil_target_value(params), 47.0, places=6)

    def test_outside_the_surround_is_black(self):
        frame = render_veil(glare_params(), SIDE, SIDE)
        self.assertEqual(tuple(frame[0, 0]), BLACK)

    def test_surround_side_is_even_and_matches_the_readout(self):
        for requested in (160, 161, 200):
            with self.subTest(requested=requested):
                params = glare_params(surround_px=requested)
                side = surround_side_px(params)
                self.assertEqual(side % 2, 0)
                frame = render_veil(params, SIDE, SIDE)
                row = anchor(SIDE, SIDE)[1] - side // 2 + 1
                lit = np.flatnonzero(frame[row, :, 0] > 0)
                self.assertEqual(int(lit[-1] - lit[0] + 1), side)

    def test_target_diameter_is_the_source_diameter(self):
        self.assertEqual(veil_target_diameter_px(glare_params()), 47)

    def test_target_uses_veil_contrast_when_the_parameter_is_present(self):
        params = glare_params(contrast=100, veil_contrast=20)
        self.assertAlmostEqual(veil_target_value(params), 47.0, places=6)
        params.veil_contrast = 40
        self.assertAlmostEqual(veil_target_value(params), 94.0, places=6)


class GhostTest(unittest.TestCase):
    def test_ghost_band_sits_exactly_offset_from_the_edge(self):
        params = glare_params(ghost_offset=7, ghost_direction="right", contrast=100)
        frame = render_ghost(params, SIDE, SIDE)
        cx, _ = anchor(SIDE, SIDE)
        row = 40
        self.assertEqual(tuple(frame[row, cx - 1]), BLACK)
        self.assertEqual(tuple(frame[row, cx]), WHITE)
        self.assertEqual(tuple(frame[row, cx + 6]), WHITE)
        self.assertEqual(tuple(frame[row, cx + 7]), BLACK)
        self.assertEqual(tuple(frame[row, cx + 7 + GHOST_LINE_PX - 1]), BLACK)
        self.assertEqual(tuple(frame[row, cx + 7 + GHOST_LINE_PX]), WHITE)

    def test_every_direction_displaces_by_the_same_offset(self):
        for direction in GHOST_DIRECTIONS:
            with self.subTest(direction=direction):
                params = glare_params(ghost_offset=7, ghost_direction=direction)
                edge, ghost_start, axis = ghost_edge_position(params, SIDE, SIDE)
                if direction in ("right", "down"):
                    displacement = ghost_start - edge
                else:
                    displacement = edge - (ghost_start + GHOST_LINE_PX)
                self.assertEqual(displacement, 7)
                self.assertEqual(
                    axis, "x" if direction in ("right", "left") else "y"
                )

    def test_vertical_directions_use_rows(self):
        params = glare_params(ghost_offset=5, ghost_direction="down", contrast=100)
        frame = render_ghost(params, SIDE, SIDE)
        _, cy = anchor(SIDE, SIDE)
        column = 40
        self.assertEqual(tuple(frame[cy - 1, column]), BLACK)
        self.assertEqual(tuple(frame[cy, column]), WHITE)
        self.assertEqual(tuple(frame[cy + 5, column]), BLACK)
        self.assertEqual(tuple(frame[cy + 5 + GHOST_LINE_PX, column]), WHITE)

    def test_zero_offset_has_no_ghost(self):
        params = glare_params(ghost_offset=0, contrast=100)
        frame = render_ghost(params, SIDE, SIDE)
        row = frame[40, :, 0].astype(np.int16)
        transitions = np.flatnonzero(np.diff(row) != 0)
        self.assertEqual(len(transitions), 1)

    def test_unknown_direction_is_rejected(self):
        with self.assertRaises(ValueError):
            render_ghost(glare_params(ghost_direction="sideways"), SIDE, SIDE)
        with self.assertRaises(ValueError):
            ghost_edge_position(glare_params(ghost_direction="sideways"), SIDE, SIDE)


if __name__ == "__main__":
    unittest.main()
