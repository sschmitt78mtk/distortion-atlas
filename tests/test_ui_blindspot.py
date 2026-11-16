"""Session-level scotoma-test tests: keys, frames, export, safety (task 8.3)."""

import json
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest import mock

import numpy as np
from PIL import Image

from distortion_atlas import blindspot, export, ui
from distortion_atlas.blindspot import BlindSpotSettings
from distortion_atlas.fixation import fixation_mask, size_for_dot
from distortion_atlas.patterns import anchor
from distortion_atlas.ui import OVERLAY_HEIGHT_PX, Session

SIDE = 416


class FakeClock:
    """A monotonic clock in milliseconds, patched into ``ui.time``."""

    def __init__(self) -> None:
        self.now_ms = 0.0

    def monotonic(self) -> float:
        return self.now_ms / 1000.0


class SessionFixture(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.dir = Path(self._tmp.name)
        self.clock = FakeClock()
        patcher = mock.patch.object(ui.time, "monotonic", self.clock.monotonic)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.session = Session(width=SIDE, height=SIDE, export_dir=self.dir)

    def start(self, dot_pitch=50, **overrides):
        options = {
            "gap": (1000, 1000),
            "seed": 1,
            "outside_sample": 0,
            "dot_px": 8,
        }
        options.update(overrides)
        self.clock.now_ms = 0.0
        self.session.params.dot_pitch = dot_pitch
        return self.session.start_scotoma_test(BlindSpotSettings(**options))

    def advance_to_dot(self):
        test = self.session.scotoma
        self.clock.now_ms = float(test.gap_end_ms)
        self.assertTrue(self.session.tick_scotoma_test())
        self.assertTrue(test.lit)
        return test.current


class StartTest(SessionFixture):
    def test_b_starts_a_run_and_carries_the_session_context(self):
        self.session.params.eye = "right"
        self.session.params.correction = False
        self.session.params.distance_mm = 350
        self.session.params.fixation_visible = False
        result = self.session.handle_key("b")
        self.assertEqual(result.action, "blindspot_started")
        self.assertIsNotNone(self.session.scotoma)
        self.assertFalse(self.session.scotoma.finished)
        self.assertEqual(self.session.params.eye, "right")
        self.assertFalse(self.session.params.correction)
        self.assertEqual(self.session.params.distance_mm, 350)
        self.assertTrue(self.session.params.fixation_visible)
        self.assertIn("started", result.message)

    def test_the_run_uses_the_current_dot_pitch(self):
        test = self.start(dot_pitch=20)
        self.assertEqual(test.lattice.spacing_px, 40)

    def test_the_test_field_shows_no_lit_dot_before_the_first_gap(self):
        test = self.start()
        self.assertFalse(test.lit)
        self.assertEqual(int(np.all(self.session.buffer == 255, axis=2).sum()), 0)

    def test_b_keeps_the_standard_variant(self):
        result = self.session.handle_key("b")
        self.assertEqual(result.action, "blindspot_started")
        test = self.session.scotoma
        self.assertEqual(test.settings.variant, blindspot.STANDARD)
        self.assertEqual(test.settings.blink_ms, 0)
        self.assertIn("appears", result.message)
        self.assertEqual(tuple(self.session.buffer[0, 0]), (0, 0, 0))

    def test_i_starts_the_inverse_variant_on_a_bright_field(self):
        result = self.session.handle_key("i")
        self.assertEqual(result.action, "blindspot_started")
        test = self.session.scotoma
        self.assertEqual(test.settings.variant, blindspot.INVERSE)
        self.assertEqual(test.settings.blink_ms, blindspot.INVERSE_BLINK_MS)
        self.assertIn("blinks", result.message)
        self.assertEqual(tuple(self.session.buffer[0, 0]), (255, 255, 255))
        self.assertIn("INVERSE", self.session.overlay_text())

    def test_i_restarts_a_finished_inverse_run_with_the_same_variant(self):
        first = self.session.handle_key("i")
        self.assertEqual(first.action, "blindspot_started")
        finished = self.session.scotoma
        self.session.handle_key("q")
        self.clock.now_ms = 5000
        result = self.session.handle_key("i")
        self.assertEqual(result.action, "blindspot_started")
        self.assertIsNot(self.session.scotoma, finished)
        self.assertEqual(self.session.scotoma.settings.variant, blindspot.INVERSE)
        self.assertIn("i restarts", self.session.handle_key("q").message)


class InverseFixationTest(SessionFixture):
    """The centre dot must stay identifiable on the bright inverse field."""

    def start_inverse(self):
        self.session.params.dot_pitch = 50
        self.clock.now_ms = 0.0
        self.session.handle_key("i")
        return self.session.scotoma

    def red_mask(self):
        frame = self.session.buffer
        return (frame[:, :, 0] > 150) & (frame[:, :, 1] < 80) & (frame[:, :, 2] < 80)

    def test_i_clears_the_black_centre_dot_with_the_red_ring(self):
        test = self.start_inverse()
        cx, cy = anchor(SIDE, SIDE)
        self.assertEqual(tuple(self.session.buffer[cy, cx]), (0, 0, 0))
        red = self.red_mask()
        self.assertFalse(bool(red[cy - 4 : cy + 4, cx - 4 : cx + 4].any()))
        for step in (7, 8):
            self.assertTrue(red[cy - step, cx])
            self.assertTrue(red[cy + step, cx])
            self.assertTrue(red[cy, cx - step])
            self.assertTrue(red[cy, cx + step])
        expected = fixation_mask(
            SIDE, SIDE, cx, cy, "ring", size_for_dot(test.settings.dot_px)
        )
        self.assertTrue(np.array_equal(red, expected))

    def test_b_keeps_the_parameter_sized_fixation(self):
        self.session.params.dot_pitch = 50
        self.session.handle_key("b")
        cx, cy = anchor(SIDE, SIDE)
        expected = fixation_mask(
            SIDE, SIDE, cx, cy, "ring", self.session.params.fixation_px
        )
        self.assertTrue(np.array_equal(self.red_mask(), expected))

    def test_a_larger_user_ring_is_not_shrunk(self):
        self.session.params.fixation_px = 25
        self.start_inverse()
        cx, cy = anchor(SIDE, SIDE)
        expected = fixation_mask(SIDE, SIDE, cx, cy, "ring", 25)
        self.assertTrue(np.array_equal(self.red_mask(), expected))

    def test_the_results_frame_keeps_the_clearing_ring(self):
        self.start_inverse()
        self.session.handle_key("q")
        cx, cy = anchor(SIDE, SIDE)
        self.assertFalse(
            bool(self.red_mask()[cy - 4 : cy + 4, cx - 4 : cx + 4].any())
        )


class FinishTest(SessionFixture):
    def test_q_finishes_with_a_results_frame_and_keeps_running(self):
        test = self.start()
        result = self.session.handle_key("q")
        self.assertEqual(result.action, "scotoma_stop")
        self.assertTrue(test.finished)
        self.assertTrue(self.session.running)
        self.assertTrue(self.session.key_bar_allowed)
        grey = np.all(self.session.buffer == np.array([128, 128, 128]), axis=2)
        self.assertGreater(int(grey.sum()), 0)
        self.assertIn("scotoma results", self.session.overlay_text())
        self.assertIn("NOT INTERPRETABLE", self.session.overlay_text())
        self.assertIn("photosensitivity: flashing dots", self.session.overlay_text())

    def test_escape_quits_without_writing_a_record(self):
        self.start()
        result = self.session.handle_key("Esc")
        self.assertEqual(result.action, "quit")
        self.assertFalse(self.session.running)
        self.assertEqual(list(self.dir.iterdir()), [])

    def test_bare_q_after_a_run_still_quits(self):
        self.start()
        self.session.handle_key("q")
        result = self.session.handle_key("q")
        self.assertEqual(result.action, "quit")
        self.assertFalse(self.session.running)

    def test_b_restarts_a_finished_run_with_a_new_test(self):
        first = self.start()
        self.session.handle_key("q")
        self.clock.now_ms = 5000
        result = self.session.handle_key("b")
        self.assertEqual(result.action, "blindspot_started")
        self.assertIsNot(self.session.scotoma, first)
        self.assertFalse(self.session.scotoma.finished)

    def test_inverse_results_are_labelled_and_name_the_blink(self):
        self.session.handle_key("i")
        self.session.handle_key("q")
        text = self.session.overlay_text()
        self.assertIn("INVERSE", text)
        self.assertIn("one blinking dark dot", text)
        self.assertIn("i restart", text)


class PauseTest(SessionFixture):
    def test_p_pauses_and_resumes_the_run(self):
        test = self.start()
        result = self.session.handle_key("p")
        self.assertEqual(result.action, "scotoma_pause")
        self.assertTrue(test.paused)
        self.assertIn("PAUSED", self.session.overlay_text())
        self.session.handle_key("p")
        self.assertFalse(test.paused)
        self.assertEqual(test.state, "waiting")


class ResponseTest(SessionFixture):
    def test_space_scores_inside_the_window_and_only_once(self):
        test = self.start()
        position = self.advance_to_dot()
        onset = test.onset_ms
        self.clock.now_ms = onset + 400
        result = self.session.handle_key("Space")
        self.assertEqual(result.action, "scotoma_response")
        self.assertTrue(result.changed)
        self.assertEqual(position.verdict, "seen")
        self.assertIn("seen", result.message)
        self.assertEqual(test.counts()["seen"], 1)

        again = self.session.handle_key("Space")
        self.assertFalse(again.changed)
        self.assertEqual(test.late_responses, 1)
        self.assertIn("no dot lit", again.message)

    def test_space_before_the_window_is_not_attributed(self):
        test = self.start()
        result = self.session.handle_key("Space")
        self.assertFalse(result.changed)
        self.assertEqual(test.counts()["seen"], 0)
        self.assertEqual(test.late_responses, 1)


class IgnoredKeysTest(SessionFixture):
    def test_parameter_keys_cannot_change_the_pattern_mid_run(self):
        test = self.start()
        before = self.session.params.to_dict()
        for key in (
            "Up", "Down", "Left", "Right", "1", "a", "l", "d", "h", "x",
            "r", "m", "w", "[", "]", "i",
        ):
            with self.subTest(key=key):
                result = self.session.handle_key(key)
                self.assertFalse(result.changed, key)
                self.assertIn("running", result.message)
        self.assertEqual(self.session.params.to_dict(), before)
        self.assertFalse(test.finished)
        self.assertTrue(self.session.running)

    def test_export_is_refused_with_an_explanation(self):
        self.start()
        result = self.session.handle_key("s")
        self.assertEqual(result.action, "export_refused")
        self.assertIn("must end", result.message)
        self.assertEqual(list(self.dir.iterdir()), [])


class KeyBarTest(SessionFixture):
    def test_the_bar_is_hidden_during_a_run_and_returns_with_the_results(self):
        self.start()
        self.assertFalse(self.session.key_bar_allowed)
        self.assertFalse(self.session.show_key_bar())
        self.assertFalse(self.session.key_bar_visible)
        self.session.handle_key("q")
        self.assertTrue(self.session.key_bar_allowed)
        self.assertTrue(self.session.show_key_bar())
        self.assertTrue(self.session.key_bar_visible)


class HudTest(SessionFixture):
    def test_no_readout_strip_is_blended_while_a_dot_is_lit(self):
        self.start()
        self.session.params.overlay = True
        waiting = self.session.presented()
        self.session.params.overlay = False
        bare = self.session.presented()
        self.assertFalse(
            np.array_equal(waiting[:OVERLAY_HEIGHT_PX], bare[:OVERLAY_HEIGHT_PX])
        )

        self.session.params.overlay = True
        self.advance_to_dot()
        lit = self.session.presented()
        self.assertTrue(np.array_equal(lit, self.session.buffer))
        self.assertTrue(
            np.array_equal(lit[:OVERLAY_HEIGHT_PX], self.session.buffer[:OVERLAY_HEIGHT_PX])
        )


class BlinkTest(SessionFixture):
    def _inverse(self):
        return self.start(
            variant=blindspot.INVERSE, blink_ms=blindspot.INVERSE_BLINK_MS
        )

    def test_the_inverse_probe_alternates_between_absent_and_present(self):
        test = self._inverse()
        self.clock.now_ms = float(test.gap_end_ms)
        self.assertTrue(self.session.tick_scotoma_test())
        self.assertTrue(test.lit)
        self.assertTrue(test.probe_shown)
        probed = test.current
        self.assertEqual(
            tuple(self.session.buffer[probed.y_px, probed.x_px]), (255, 255, 255)
        )

        self.clock.now_ms = float(test.onset_ms) + 1
        self.assertFalse(self.session.tick_scotoma_test())

        self.clock.now_ms = float(test.onset_ms) + test.settings.blink_ms
        self.assertTrue(self.session.tick_scotoma_test())
        self.assertFalse(test.probe_shown)
        self.assertEqual(
            tuple(self.session.buffer[probed.y_px, probed.x_px]), (0, 0, 0)
        )

        self.clock.now_ms = float(test.onset_ms) + 2 * test.settings.blink_ms
        self.assertTrue(self.session.tick_scotoma_test())
        self.assertTrue(test.probe_shown)
        self.assertEqual(
            tuple(self.session.buffer[probed.y_px, probed.x_px]), (255, 255, 255)
        )

    def test_the_hud_stays_hidden_for_the_whole_blinking_window(self):
        test = self._inverse()
        self.session.params.overlay = True
        self.clock.now_ms = float(test.gap_end_ms)
        self.session.tick_scotoma_test()
        for offset in (0, test.settings.blink_ms, 2 * test.settings.blink_ms):
            self.clock.now_ms = float(test.onset_ms) + offset
            self.session.tick_scotoma_test()
            self.assertTrue(
                np.array_equal(self.session.presented(), self.session.buffer)
            )

    def test_a_response_inside_the_blink_scores_the_position(self):
        test = self._inverse()
        self.clock.now_ms = float(test.gap_end_ms)
        self.session.tick_scotoma_test()
        probed = test.current
        self.clock.now_ms = float(test.onset_ms) + 700
        result = self.session.handle_key("Space")
        self.assertTrue(result.changed)
        self.assertEqual(probed.verdict, "seen")
        self.assertIn("seen", result.message)


class ExportTest(SessionFixture):
    def test_export_mid_run_is_refused_without_writing_files(self):
        self.start()
        before = self.session.buffer.copy()
        result = self.session.export()
        self.assertFalse(result.ok)
        self.assertIn("finish the scotoma test", result.error)
        self.assertEqual(list(self.dir.iterdir()), [])
        self.assertTrue(np.array_equal(self.session.buffer, before))

    def test_export_after_the_run_writes_the_png_and_the_blindspot_block(self):
        self.session.params.eye = "right"
        test = self.start()
        seen = self.advance_to_dot()
        self.clock.now_ms = test.onset_ms + 400
        self.session.handle_key("Space")
        self.clock.now_ms = float(test.gap_end_ms)
        self.assertTrue(self.session.tick_scotoma_test())
        self.clock.now_ms = float(test.window_end_ms)
        self.assertTrue(self.session.tick_scotoma_test())
        self.session.handle_key("q")

        moment = datetime(2026, 11, 15, 21, 30, 0)
        result = self.session.export(timestamp=moment)
        self.assertTrue(result.ok, result.message())
        self.assertTrue(result.png_path.exists())
        record = json.loads(result.json_path.read_text(encoding="utf-8"))

        block = record["blindspot"]
        self.assertEqual(block["seed"], 1)
        self.assertEqual(block["settings"]["window_ms"], 1500)
        self.assertEqual(block["settings"]["gap_ms"], [1000, 1000])
        self.assertEqual(block["lattice"]["columns"], 5)
        self.assertEqual(block["context"]["eye"], "right")
        self.assertIn("Not a medical device", block["caveat"])
        self.assertEqual(block["summary"]["central_seen"], "1/24")
        self.assertEqual(block["summary"]["seen"], 1)
        self.assertEqual(block["summary"]["blind"], 0)
        self.assertEqual(block["summary"]["late_responses"], 0)
        self.assertIn("flashing", record["photosensitivity_warning"])
        self.assertIn("Not a medical device", record["non_diagnostic"])

        attempts = [
            attempt
            for position in block["positions"]
            for attempt in position["attempts"]
        ]
        self.assertTrue(any(item["outcome"] == "seen" for item in attempts))
        self.assertTrue(any(item["outcome"] == "miss" for item in attempts))
        seen_attempt = next(item for item in attempts if item["outcome"] == "seen")
        self.assertEqual(seen_attempt["response_ms"], 400)
        miss_attempt = next(item for item in attempts if item["outcome"] == "miss")
        self.assertIsNone(miss_attempt["response_ms"])

        with Image.open(result.png_path) as image:
            self.assertEqual(image.size, (SIDE, SIDE))
            exported = np.asarray(image)
        self.assertTrue(np.array_equal(exported, self.session.buffer))
        self.assertNotEqual(seen.key, (2, 2))


class SafetyTextTest(unittest.TestCase):
    def test_the_warning_names_the_flashing_dots_and_keeps_the_caveat(self):
        warning = export.PHOTOSENSITIVITY_WARNING.lower()
        self.assertIn("photosensitivity", warning)
        self.assertIn("flashing", warning)
        self.assertIn("dot", warning)
        self.assertNotIn("all current patterns are static", warning)
        self.assertIn("not a medical device", export.NON_DIAGNOSTIC.lower())

    def test_the_inverse_warning_names_the_bright_field_and_the_blink(self):
        warning = export.INVERSE_PHOTOSENSITIVITY_WARNING.lower()
        self.assertIn("bright field", warning)
        self.assertIn("blink", warning)
        self.assertIn("photosensitivity", warning)
        self.assertIn("discomfort", warning)

    def test_the_startup_notice_covers_both_variants(self):
        self.assertIn(export.COMBINED_PHOTOSENSITIVITY_WARNING, ui.STARTUP_NOTICE)
        notice = ui.STARTUP_NOTICE.lower()
        self.assertIn("standard variant", notice)
        self.assertIn("inverse variant", notice)
        self.assertIn("bright field", notice)
        self.assertIn(export.DISCLAIMER, ui.STARTUP_NOTICE)


if __name__ == "__main__":
    unittest.main()
