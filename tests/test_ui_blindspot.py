"""Session-level scotoma-test tests: keys, frames, export, safety (task 8.3)."""

import json
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest import mock

import numpy as np
from PIL import Image

from distortion_atlas import export, ui
from distortion_atlas.blindspot import BlindSpotSettings
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
            "r", "m", "w", "[", "]",
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
        self.assertIn(export.PHOTOSENSITIVITY_WARNING, ui.STARTUP_NOTICE)


if __name__ == "__main__":
    unittest.main()
