"""Tests for the scotoma-test renderers (task 8.2)."""

import unittest

import numpy as np

from distortion_atlas import blindspot
from distortion_atlas.blindspot import BlindSpotSettings, BlindSpotTest
from distortion_atlas.geometry import Scale
from distortion_atlas.params import Params
from distortion_atlas.patterns import BLACK, anchor
from distortion_atlas.patterns import blindspot as renderer

SIDE = 416
PITCH = 50
GAP = (1000, 1000)


def make_test(width=SIDE, height=SIDE):
    return BlindSpotTest(
        BlindSpotSettings(gap=GAP, seed=1, outside_sample=0, dot_px=8),
        width=width,
        height=height,
        dot_pitch=PITCH,
    )


def count_colour(frame, colour):
    return int(np.all(frame == np.array(colour, dtype=np.uint8), axis=2).sum())


class LatticeTest(unittest.TestCase):
    def test_the_field_is_aligned_to_the_anchor_and_the_dot_pitch(self):
        test = make_test()
        params = Params(family="lines", dot_pitch=PITCH)
        frame = renderer.render_lattice(params, SIDE, SIDE, test.positions)
        origin = anchor(SIDE, SIDE)
        self.assertEqual(test.lattice.origin_px, origin)
        self.assertEqual(test.lattice.spacing_px, 2 * params.dot_pitch)
        for position in test.positions:
            self.assertEqual((position.x_px - origin[0]) % (2 * PITCH), 0)
            self.assertEqual((position.y_px - origin[1]) % (2 * PITCH), 0)
            self.assertEqual(
                tuple(frame[position.y_px, position.x_px]),
                renderer.LATTICE_COLOUR,
            )

    def test_the_field_is_rectangular_and_clipped_to_the_margin(self):
        width, height = 616, 416
        test = make_test(width=width, height=height)
        self.assertGreater(test.lattice.columns, test.lattice.rows)
        origin_x, origin_y = anchor(width, height)
        for position in test.positions:
            self.assertLessEqual(abs(position.x_px - origin_x), width // 2 - 8)
            self.assertLessEqual(abs(position.y_px - origin_y), height // 2 - 8)
        self.assertEqual(
            max(position.x_px for position in test.positions),
            origin_x + test.lattice.x_half_px,
        )
        self.assertEqual(
            max(position.y_px for position in test.positions),
            origin_y + test.lattice.y_half_px,
        )

    def test_the_renderer_draws_the_lattice_but_not_the_fixation(self):
        test = make_test()
        frame = renderer.render_lattice(Params(), SIDE, SIDE, test.positions)
        self.assertEqual(tuple(frame[0, 0]), BLACK)
        self.assertEqual(count_colour(frame, (255, 0, 0)), 0)


class TestFrameTest(unittest.TestCase):
    def test_exactly_one_dot_is_lit_at_full_contrast(self):
        test = make_test()
        lit = test.position(1, 1)
        frame = renderer.render_test_frame(
            Params(), SIDE, SIDE, test.positions, lit=lit, settings=test.settings
        )
        self.assertEqual(
            count_colour(frame, renderer.LIT_COLOUR), test.settings.dot_px ** 2
        )
        half = test.settings.dot_px // 2
        for position in test.positions:
            expected = (
                renderer.LIT_COLOUR if position is lit else renderer.LATTICE_COLOUR
            )
            self.assertEqual(
                tuple(frame[position.y_px - half, position.x_px - half]), expected
            )

    def test_an_xy_pair_can_be_lit_and_none_leaves_every_dot_dim(self):
        test = make_test()
        point = test.position(3, 3)
        frame = renderer.render_test_frame(
            Params(),
            SIDE,
            SIDE,
            test.positions,
            lit=(point.x_px, point.y_px),
            settings=test.settings,
        )
        self.assertEqual(
            count_colour(frame, renderer.LIT_COLOUR), test.settings.dot_px ** 2
        )
        dim = renderer.render_test_frame(Params(), SIDE, SIDE, test.positions)
        self.assertEqual(count_colour(dim, renderer.LIT_COLOUR), 0)


class ResultsFrameTest(unittest.TestCase):
    def setUp(self):
        self.test = make_test()
        self.scale = Scale(px_per_mm=5.666, distance_mm=400)

    def _summary(self):
        return self.test.results(self.scale)

    def test_seen_blind_and_untested_positions_use_their_colours(self):
        self.test.position(1, 1).verdict = blindspot.SEEN
        self.test.position(3, 3).verdict = blindspot.BLIND
        frame = renderer.render_results_frame(
            Params(),
            SIDE,
            SIDE,
            self.test.positions,
            self._summary(),
            lattice=self.test.lattice,
            settings=self.test.settings,
        )
        self.assertGreater(count_colour(frame, renderer.SEEN_COLOUR), 0)
        self.assertGreater(count_colour(frame, renderer.BLIND_COLOUR), 0)
        self.assertGreater(count_colour(frame, renderer.UNTESTED_COLOUR), 0)
        self.assertGreater(count_colour(frame, renderer.CAPTION_COLOUR), 0)

    def test_the_caption_names_counts_clusters_and_the_caveat(self):
        self.test.position(1, 1).verdict = blindspot.SEEN
        self.test.position(3, 3).verdict = blindspot.BLIND
        lines = renderer._caption_lines(self._summary())
        text = " | ".join(line for line, _ in lines)
        self.assertIn("SEEN 1", text)
        self.assertIn("BLIND 1", text)
        self.assertIn("INNER RING 1/24 SEEN", text)
        self.assertIn("CLUSTER 1: 1 DOTS", text)
        self.assertIn("CENTRE", text)
        self.assertIn("EXTENT", text)
        self.assertIn("PHOTOSENSITIVITY", text)
        self.assertIn("FLASHING DOTS", text)
        self.assertIn("NOT A MEDICAL DIAGNOSIS", text)

    def test_an_uninterpretable_run_says_so(self):
        lines = renderer._caption_lines(self._summary())
        self.assertIn("NOT INTERPRETABLE", lines[0][0])

    def test_the_cluster_centroid_and_extent_are_in_degrees(self):
        self.test.position(1, 3).verdict = blindspot.BLIND
        self.test.position(2, 3).verdict = blindspot.BLIND
        clusters = self.test.clusters(self.scale)
        self.assertEqual(len(clusters), 1)
        cluster = clusters[0]
        self.assertEqual(cluster["dots"], 2)
        spacing_deg = self.scale.degrees_for_px(self.test.lattice.spacing_px)
        self.assertEqual(cluster["extent_deg"], [round(spacing_deg, 1), 0.0])


if __name__ == "__main__":
    unittest.main()
