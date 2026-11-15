"""Tests for the pure scotoma-test state machine (tasks 8.1)."""

import unittest

from distortion_atlas import blindspot
from distortion_atlas.blindspot import BlindSpotSettings, BlindSpotTest
from distortion_atlas.geometry import Scale

#: A 416x416 buffer at pitch 50 gives a 5x5 lattice (spacing 100, margin 8).
SIDE = 416
PITCH = 50
GAP = (1000, 1000)


def make_test(settings=None, now_ms=0, side=SIDE, pitch=PITCH):
    return BlindSpotTest(
        settings or BlindSpotSettings(gap=GAP, seed=7),
        width=side,
        height=side,
        dot_pitch=pitch,
        now_ms=now_ms,
    )


def only(test, key):
    """Force the next presentation to be exactly ``key``."""
    test.queue = [(key[0], key[1], 1)]
    test._queued = {key}
    test.state = "waiting"
    test.gap_end_ms = 0.0
    return test


def start_next(test):
    """Advance to the next presentation and return it."""
    test.tick(float(test.gap_end_ms))
    return test.current


class LatticeTest(unittest.TestCase):
    def test_the_lattice_is_anchored_and_spaced_twice_the_dot_pitch(self):
        test = make_test()
        lattice = test.lattice
        self.assertEqual(lattice.origin_px, (SIDE // 2, SIDE // 2))
        self.assertEqual(lattice.spacing_px, 2 * PITCH)
        self.assertEqual((lattice.columns, lattice.rows), (5, 5))
        for position in test.positions:
            self.assertEqual(
                (position.x_px - lattice.origin_px[0]) % lattice.spacing_px, 0
            )
            self.assertEqual(
                (position.y_px - lattice.origin_px[1]) % lattice.spacing_px, 0
            )
            self.assertLessEqual(
                abs(position.x_px - lattice.origin_px[0]), lattice.x_half_px
            )
            self.assertLessEqual(
                abs(position.y_px - lattice.origin_px[1]), lattice.y_half_px
            )

    def test_the_reference_panel_builds_the_documented_lattice(self):
        test = BlindSpotTest(
            BlindSpotSettings(seed=1), width=1920, height=1080, dot_pitch=50
        )
        self.assertEqual((test.lattice.columns, test.lattice.rows), (19, 11))
        self.assertEqual(len(test.positions), 209)

    def test_a_buffer_too_small_for_the_margin_is_rejected(self):
        with self.assertRaises(ValueError):
            blindspot.build_lattice(10, 10, 50)


class TrialPlanTest(unittest.TestCase):
    def test_all_24_inner_positions_are_queued_and_the_centre_is_not(self):
        test = make_test(BlindSpotSettings(gap=GAP, seed=7, outside_sample=75))
        keys = blindspot.position_keys(test.queue)
        self.assertEqual(len(keys), 24)
        self.assertEqual(len(set(keys)), 24)
        self.assertEqual(test.inner_ring_total, 24)
        self.assertNotIn((2, 2), keys)
        for col in (1, 2, 3):
            for row in (1, 2, 3):
                if (col, row) != (2, 2):
                    self.assertIn((col, row), keys)

    def test_the_outside_sample_is_disjoint_unique_and_seeded(self):
        settings = BlindSpotSettings(gap=GAP, seed=11, outside_sample=10)
        first = make_test(settings, side=1920, pitch=50)
        second = make_test(settings, side=1920, pitch=50)
        keys = blindspot.position_keys(first.queue)
        self.assertEqual(len(keys), 34)  # 24 inner + 10 sampled
        self.assertEqual(len(set(keys)), 34)
        self.assertEqual(keys, blindspot.position_keys(second.queue))
        self.assertEqual(first.seed, 11)
        outside = [key for key in keys if key not in first._inner_keys]
        self.assertEqual(len(outside), 10)

    def test_a_random_seed_is_recorded(self):
        test = make_test(BlindSpotSettings(gap=GAP))
        self.assertIsInstance(test.seed, int)
        self.assertGreaterEqual(test.seed, 0)

    def test_the_initial_order_is_shuffled_once(self):
        ordered = make_test(BlindSpotSettings(gap=GAP, seed=3, outside_sample=0))
        keys = blindspot.position_keys(ordered.queue)
        self.assertNotEqual(keys, sorted(keys, key=lambda key: (key[1], key[0])))


class TimingTest(unittest.TestCase):
    def test_the_gap_is_sampled_inside_the_configured_bounds(self):
        for seed in range(25):
            test = make_test(BlindSpotSettings(seed=seed))
            gap = test.gap_end_ms
            self.assertGreaterEqual(gap, 500, seed)
            self.assertLessEqual(gap, 3000, seed)

    def test_the_window_expires_into_a_miss(self):
        test = make_test()
        self.assertFalse(test.tick(999))
        self.assertTrue(test.tick(1000))
        self.assertTrue(test.lit)
        position = test.current
        self.assertFalse(test.tick(2499))
        self.assertTrue(test.tick(2500))
        self.assertFalse(test.lit)
        self.assertEqual(position.verdict, blindspot.UNSEEN)
        self.assertEqual(len(position.attempts), 1)
        self.assertEqual(position.attempts[0].outcome, blindspot.MISS_OUTCOME)
        self.assertIsNone(position.attempts[0].response_ms)
        self.assertEqual(test.state, "waiting")

    def test_a_response_inside_the_window_marks_the_position_seen(self):
        test = make_test()
        test.tick(1000)
        onset = test.onset_ms
        position = test.current
        self.assertTrue(test.respond(onset + 400))
        self.assertEqual(position.verdict, blindspot.SEEN)
        self.assertEqual(test.last_latency_ms, 400)
        self.assertEqual(position.attempts[0].outcome, blindspot.SEEN_OUTCOME)
        self.assertEqual(position.attempts[0].response_ms, 400)
        self.assertFalse(test.lit)
        self.assertEqual(test.state, "waiting")

    def test_the_window_end_is_inclusive(self):
        test = make_test()
        test.tick(1000)
        self.assertTrue(test.respond(test.window_end_ms))

    def test_an_early_press_is_not_attributed(self):
        test = make_test()
        self.assertFalse(test.respond(10))
        self.assertEqual(test.late_responses, 1)
        for position in test.positions:
            self.assertEqual(position.attempts, [])

    def test_a_late_press_is_counted_and_the_window_still_misses(self):
        test = make_test()
        test.tick(1000)
        position = test.current
        self.assertFalse(test.respond(test.window_end_ms + 1))
        self.assertEqual(test.late_responses, 1)
        self.assertEqual(position.attempts, [])
        self.assertTrue(test.tick(test.window_end_ms + 1))
        self.assertEqual(position.attempts[0].outcome, blindspot.MISS_OUTCOME)


class RetryTest(unittest.TestCase):
    def _first_miss(self, test):
        start_next(test)
        key = test.current.key
        test.tick(test.window_end_ms)
        return key

    def test_a_miss_is_retried_exactly_five_slots_later(self):
        test = make_test()
        key = self._first_miss(test)
        entry = test.queue[5]
        self.assertEqual(entry[:2], key)
        self.assertEqual(entry[2], 2)
        self.assertNotIn(key, [item[:2] for item in test.queue[:5]])

    def test_a_second_miss_marks_blind_and_queues_the_eight_neighbours(self):
        test = only(make_test(side=616), (2, 1))
        test.tick(0)
        position = test.current
        test.tick(test.window_end_ms)
        start_next(test)
        test.tick(test.window_end_ms)
        self.assertEqual(position.verdict, blindspot.BLIND)
        self.assertEqual(
            [attempt.outcome for attempt in position.attempts],
            [blindspot.MISS_OUTCOME, blindspot.MISS_OUTCOME],
        )
        neighbours = {
            (1, 0), (2, 0), (3, 0),
            (1, 1), (3, 1),
            (1, 2), (2, 2), (3, 2),
        }
        queued = {entry[:2] for entry in test.queue}
        self.assertEqual(queued, neighbours)
        self.assertEqual(len(test.queue), 8)
        self.assertTrue(all(entry[2] == 1 for entry in test.queue))

    def test_an_edge_position_only_queues_neighbours_inside_the_field(self):
        test = only(make_test(side=616), (0, 0))
        test.tick(0)
        position = test.current
        test.tick(test.window_end_ms)
        start_next(test)
        test.tick(test.window_end_ms)
        self.assertEqual(position.verdict, blindspot.BLIND)
        queued = {entry[:2] for entry in test.queue}
        self.assertEqual(queued, {(1, 0), (0, 1), (1, 1)})

    def test_the_fixation_centre_is_never_probed(self):
        test = only(make_test(), (1, 1))
        test.tick(0)
        position = test.current
        test.tick(test.window_end_ms)
        start_next(test)
        test.tick(test.window_end_ms)
        self.assertEqual(position.verdict, blindspot.BLIND)
        queued = {entry[:2] for entry in test.queue}
        self.assertNotIn((2, 2), queued)
        self.assertEqual(len(queued), 7)
        self.assertEqual(test.position(2, 2).verdict, blindspot.UNSEEN)

    def test_neighbours_already_queued_or_presented_are_not_duplicated(self):
        test = only(make_test(side=616), (2, 1))
        test.tick(0)
        position = test.current
        test.tick(test.window_end_ms)
        test.queue = [(2, 1, 2), (0, 0, 1)]
        test._queued = {(2, 1), (0, 0)}
        test._presented.add((3, 2))
        test.position(3, 2).verdict = blindspot.SEEN
        start_next(test)
        test.tick(test.window_end_ms)
        self.assertEqual(position.verdict, blindspot.BLIND)
        keys = [entry[:2] for entry in test.queue]
        self.assertEqual(len(keys), len(set(keys)))
        self.assertEqual(keys.count((0, 0)), 1)
        self.assertNotIn((3, 2), keys)
        self.assertEqual(len(keys), 8)


class PauseTest(unittest.TestCase):
    def test_pausing_during_a_gap_freezes_the_remaining_time(self):
        test = make_test()
        self.assertTrue(test.pause(100))
        self.assertTrue(test.paused)
        self.assertFalse(test.tick(5000))
        self.assertTrue(test.resume(5000))
        self.assertAlmostEqual(test.gap_end_ms, 5900)
        self.assertFalse(test.tick(5899))
        self.assertTrue(test.tick(5900))

    def test_pausing_a_lit_dot_discards_it_without_a_miss(self):
        test = only(make_test(), (1, 1))
        test.tick(0)
        position = test.current
        self.assertTrue(test.pause(100))
        self.assertFalse(test.lit)
        self.assertIsNone(test.current)
        self.assertEqual(position.verdict, blindspot.UNSEEN)
        self.assertEqual(
            [attempt.outcome for attempt in position.attempts],
            [blindspot.ABORTED_OUTCOME],
        )
        self.assertEqual(test.queue[-1][:2], (1, 1))
        self.assertTrue(test.resume(5000))
        self.assertAlmostEqual(test.gap_end_ms, 6000)
        self.assertTrue(test.tick(6000))
        self.assertEqual(test.current.key, (1, 1))

    def test_pause_and_resume_are_rejected_in_the_wrong_state(self):
        test = make_test()
        self.assertFalse(test.resume(10))
        self.assertTrue(test.pause(10))
        self.assertFalse(test.pause(20))
        self.assertTrue(test.resume(30))
        self.assertFalse(test.resume(40))


class StopTest(unittest.TestCase):
    def test_stop_finishes_and_leaves_the_queue_untested(self):
        test = make_test()
        test.tick(1000)
        position = test.current
        self.assertTrue(test.stop(1200))
        self.assertTrue(test.finished)
        self.assertFalse(test.lit)
        self.assertEqual(position.verdict, blindspot.UNSEEN)
        self.assertEqual(
            [attempt.outcome for attempt in position.attempts],
            [blindspot.ABORTED_OUTCOME],
        )
        counts = test.counts()
        self.assertEqual(counts["untested"], len(test.positions))
        self.assertFalse(test.tick(99999))
        self.assertFalse(test.stop(99999))

    def test_the_trial_cap_ends_the_run(self):
        settings = BlindSpotSettings(
            gap=(0, 0), seed=1, trial_cap=2, outside_sample=0
        )
        test = make_test(settings)
        self.assertTrue(test.tick(0))
        self.assertTrue(test.lit)
        test.tick(1500)
        self.assertEqual(test.presentations, 2)
        self.assertTrue(test.tick(3000))
        self.assertTrue(test.finished)
        self.assertEqual(test.presentations, 2)

    def test_the_deadline_ends_the_run(self):
        settings = BlindSpotSettings(gap=(0, 0), seed=1, deadline_ms=1000)
        test = make_test(settings)
        test.tick(0)
        self.assertTrue(test.tick(1000))
        self.assertTrue(test.finished)


class ResultsTest(unittest.TestCase):
    def setUp(self):
        self.scale = Scale(px_per_mm=5.666, distance_mm=400)
        self.test = make_test(
            BlindSpotSettings(gap=GAP, seed=1, outside_sample=0)
        )

    def _set(self, keys, verdict):
        for col, row in keys:
            self.test.position(col, row).verdict = verdict

    def test_counts_and_the_attention_check(self):
        self._set([(1, 1), (2, 1), (3, 1)], blindspot.SEEN)
        self._set([(1, 3), (2, 3), (1, 4), (4, 4)], blindspot.BLIND)
        summary = self.test.results(self.scale)
        self.assertEqual(summary["seen"], 3)
        self.assertEqual(summary["blind"], 4)
        self.assertEqual(summary["untested"], 18)
        self.assertEqual(summary["central_seen"], "3/24")
        self.assertTrue(summary["interpretable"])

    def test_two_or_fewer_inner_dots_make_the_run_uninterpretable(self):
        self._set([(1, 1), (2, 1)], blindspot.SEEN)
        self.assertFalse(self.test.interpretable())
        self.assertFalse(self.test.results(self.scale)["interpretable"])

    def test_blind_positions_form_eight_connected_clusters_in_degrees(self):
        self._set([(1, 3), (2, 3), (1, 4), (4, 4)], blindspot.BLIND)
        clusters = self.test.clusters(self.scale)
        self.assertEqual(len(clusters), 2)
        first, second = clusters
        self.assertEqual(first["dots"], 3)
        extent = self.scale.degrees_for_px(100)
        self.assertEqual(first["extent_deg"], [round(extent, 1), round(extent, 1)])
        centre_x = self.scale.degrees_for_px((108 + 208 + 108) / 3 - 208)
        centre_y = self.scale.degrees_for_px((308 + 308 + 408) / 3 - 208)
        self.assertEqual(
            first["centre_deg"], [round(centre_x, 1), round(centre_y, 1)]
        )
        self.assertEqual(second["dots"], 1)

    def test_latencies_and_late_responses_are_summarised(self):
        for latency, key in ((300, (1, 1)), (500, (2, 1)), (700, (3, 1))):
            position = self.test.position(*key)
            position.verdict = blindspot.SEEN
            position.attempts.append(
                blindspot.Attempt(0, latency, blindspot.SEEN_OUTCOME)
            )
        self.test.respond(0)  # no window open
        summary = self.test.results(self.scale)
        self.assertEqual(summary["median_latency_ms"], 500)
        self.assertEqual(summary["late_responses"], 1)

    def test_the_record_contains_settings_seed_lattice_and_positions(self):
        self.test.tick(1000)
        record = self.test.record(self.scale)
        self.assertEqual(record["seed"], 1)
        self.assertEqual(record["settings"]["window_ms"], 1500)
        self.assertEqual(record["settings"]["gap_ms"], [1000, 1000])
        self.assertEqual(record["lattice"]["columns"], 5)
        self.assertEqual(record["lattice"]["rows"], 5)
        self.assertEqual(len(record["positions"]), 25)
        self.assertIn("attempts", record["positions"][0])
        self.assertEqual(record["summary"]["central_seen"], "0/24")


if __name__ == "__main__":
    unittest.main()
