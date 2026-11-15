"""Offscreen viewer tests: presentation, key dispatch, pixel-path guard (4.3/4.4)."""

import os
import time
import unittest

import numpy as np

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from visiontest import export  # noqa: E402
from visiontest.ui import OVERLAY_HEIGHT_PX, Session, check_pixel_path  # noqa: E402

try:  # pragma: no cover - the skip branch only runs without PyQt6
    from PyQt6.QtCore import QEvent, Qt
    from PyQt6.QtGui import QKeyEvent

    from visiontest.backends.qt import (
        QtPresenter,
        configure_scaling,
        create_application,
        is_coarse,
        key_name,
    )

    HAVE_QT = True
except Exception:  # pragma: no cover
    HAVE_QT = False

SIDE = 800


@unittest.skipUnless(HAVE_QT, "PyQt6 is not installed")
class ViewerTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        configure_scaling()
        cls.app = create_application()

    def setUp(self):
        self.session = Session(width=SIDE, height=SIDE)
        self.presenter = QtPresenter(self.session, app=self.app, fullscreen=False)

    def tearDown(self):
        self.presenter.close()

    def test_renders_a_pattern_through_the_presenter(self):
        self.presenter.show(self.session.presented())
        self.assertIsNotNone(self.presenter.widget._image)
        self.assertEqual(
            self.presenter.widget._image.width(), self.presenter.widget._image.height()
        )
        self.assertEqual(self.presenter.surface_size(), (SIDE, SIDE))

    def test_a_key_dispatch_re_renders_without_error(self):
        self.presenter.show(self.session.presented())
        before = self.session.buffer.copy()
        result = self.presenter.dispatch("d")
        self.assertTrue(result.changed)
        self.assertEqual(self.session.params.family, "dial")
        self.assertFalse(np.array_equal(before, self.session.buffer))
        self.assertIsNotNone(self.presenter.widget._image)

    def test_painting_includes_the_overlay_without_raising(self):
        self.presenter.show(self.session.presented())
        pixmap = self.presenter.widget.grab()
        self.assertFalse(pixmap.isNull())

    def test_offscreen_surface_matches_the_buffer(self):
        check = self.presenter.check_surface()
        self.assertTrue(check.ok, check.message)
        self.assertEqual(check.surface_size, (SIDE, SIDE))
        self.assertTrue(self.session.reliable)

    def test_arrows_step_and_shift_coarsens(self):
        self.session.params.family = "amsler"
        self.session.render()
        self.presenter.dispatch("Up")
        self.assertEqual(self.session.params.squares, 21)
        self.presenter.dispatch("Up", coarse=True)
        self.assertEqual(self.session.params.squares, 26)

    def test_quit_key_stops_the_session(self):
        result = self.presenter.dispatch("q")
        self.assertEqual(result.action, "quit")
        self.assertFalse(self.session.running)

    def test_hold_zero_returns_without_waiting(self):
        self.presenter.show(self.session.presented())
        started = time.monotonic()
        self.presenter.hold(0)
        self.assertLess(time.monotonic() - started, 0.5)
        self.assertTrue(self.presenter.widget.isVisible())

    def test_a_timed_hold_returns_after_the_delay(self):
        self.presenter.show(self.session.presented())
        started = time.monotonic()
        self.presenter.hold(0.05)
        elapsed = time.monotonic() - started
        self.assertGreaterEqual(elapsed, 0.03)
        self.assertLess(elapsed, 5.0)
        self.assertFalse(self.presenter.widget.isVisible())

    def test_a_hold_until_key_ends_on_any_key(self):
        from PyQt6.QtCore import QTimer
        from PyQt6.QtTest import QTest

        self.presenter.show(self.session.presented())
        widget = self.presenter.widget
        QTimer.singleShot(50, lambda: QTest.keyClick(widget, Qt.Key.Key_Space))
        self.presenter.hold(None)
        self.assertFalse(widget.isVisible())
        # A key pressed during the hold must not reach the session.
        self.assertEqual(self.session.params.family, "amsler")

    def test_a_real_key_event_reaches_the_session(self):
        from PyQt6.QtTest import QTest

        self.presenter.show(self.session.presented())
        QTest.keyClick(self.presenter.widget, Qt.Key.Key_D)
        self.assertEqual(self.session.params.family, "dial")
        QTest.keyClick(self.presenter.widget, Qt.Key.Key_H)
        self.assertFalse(self.session.params.overlay)
        QTest.keyClick(self.presenter.widget, Qt.Key.Key_F)
        self.assertFalse(self.session.fullscreen)
        QTest.keyClick(self.presenter.widget, Qt.Key.Key_F)
        self.assertTrue(self.session.fullscreen)
        QTest.keyClick(self.presenter.widget, Qt.Key.Key_X)
        self.assertFalse(self.session.params.fixation_visible)

    def test_a_real_arrow_key_steps_the_geometry(self):
        from PyQt6.QtTest import QTest

        self.presenter.show(self.session.presented())
        before = self.session.params.squares
        QTest.keyClick(self.presenter.widget, Qt.Key.Key_Up)
        self.assertEqual(self.session.params.squares, before + 1)
        QTest.keyClick(
            self.presenter.widget, Qt.Key.Key_Up, Qt.KeyboardModifier.ShiftModifier
        )
        self.assertEqual(self.session.params.squares, before + 6)


@unittest.skipUnless(HAVE_QT, "PyQt6 is not installed")
class KeyMappingTest(unittest.TestCase):
    def _event(self, key, modifiers=Qt.KeyboardModifier.NoModifier, text=""):
        return QKeyEvent(QEvent.Type.KeyPress, key, modifiers, text)

    def test_letters_digits_and_esc_keep_their_names(self):
        self.assertEqual(key_name(self._event(Qt.Key.Key_A, text="a")), "a")
        self.assertEqual(key_name(self._event(Qt.Key.Key_5, text="5")), "5")
        self.assertEqual(key_name(self._event(Qt.Key.Key_Escape)), "Esc")
        self.assertEqual(key_name(self._event(Qt.Key.Key_Backtab)), "Shift+Tab")

    def test_arrows_and_brackets_are_named(self):
        self.assertEqual(key_name(self._event(Qt.Key.Key_Up)), "Up")
        self.assertEqual(key_name(self._event(Qt.Key.Key_Left)), "Left")
        self.assertEqual(key_name(self._event(Qt.Key.Key_BracketRight)), "]")
        self.assertEqual(key_name(self._event(Qt.Key.Key_Plus)), "+")

    def test_shift_coarsens_arrows_and_ctrl_coarsens_the_rest(self):
        shift_up = self._event(Qt.Key.Key_Up, Qt.KeyboardModifier.ShiftModifier)
        self.assertTrue(is_coarse(shift_up, "Up"))
        plain_up = self._event(Qt.Key.Key_Up)
        self.assertFalse(is_coarse(plain_up, "Up"))
        ctrl_plus = self._event(
            Qt.Key.Key_Plus, Qt.KeyboardModifier.ControlModifier, "+"
        )
        self.assertTrue(is_coarse(ctrl_plus, "+"))
        shift_plus = self._event(
            Qt.Key.Key_Plus, Qt.KeyboardModifier.ShiftModifier, "+"
        )
        self.assertFalse(is_coarse(shift_plus, "+"))

    def test_unknown_keys_are_ignored(self):
        self.assertEqual(key_name(self._event(Qt.Key.Key_Meta)), "")


class PixelPathTest(unittest.TestCase):
    def test_a_matching_surface_is_a_one_to_one_path(self):
        check = check_pixel_path((1920, 1080), (1920, 1080), 1.0)
        self.assertTrue(check.ok)
        self.assertIn("1:1", check.message)

    def test_a_size_mismatch_is_named_and_marks_the_session_unreliable(self):
        check = check_pixel_path((1920, 1080), (1600, 900), 1.0)
        self.assertFalse(check.ok)
        self.assertIn("1920×1080", check.message)

        session = Session(width=1920, height=1080)
        session.update_pixel_path((1600, 900), 1.0)
        self.assertFalse(session.reliable)
        self.assertIn("PIXEL PATH UNRELIABLE", session.overlay_text())

    def test_a_device_pixel_ratio_other_than_one_is_a_mismatch(self):
        check = check_pixel_path((1920, 1080), (1920, 1080), 1.5)
        self.assertFalse(check.ok)
        self.assertIn("1.5", check.message)

    def test_unreliable_flag_reaches_the_record(self):
        session = Session(width=1920, height=1080)
        session.render()
        session.update_pixel_path((1280, 720))
        record = export.build_record(session, panel={"name": "test"}, timestamp=None)
        self.assertFalse(record["pixel_path"]["ok"])
        self.assertFalse(record["pixel_path"]["session_reliable"])

    def test_headless_rendering_has_no_surface_to_compare(self):
        check = check_pixel_path((800, 800))
        self.assertTrue(check.ok)
        self.assertIsNone(check.surface_size)


class OverlayTest(unittest.TestCase):
    def test_the_exported_buffer_contains_no_overlay_pixels(self):
        session = Session(width=SIDE, height=SIDE)
        session.handle_key("c")  # self-check pattern
        session.params.overlay = True
        with_overlay = session.presented()
        session.params.overlay = False
        without_overlay = session.presented()

        self.assertFalse(
            np.array_equal(
                with_overlay[:OVERLAY_HEIGHT_PX], without_overlay[:OVERLAY_HEIGHT_PX]
            )
        )
        self.assertTrue(
            np.array_equal(
                with_overlay[OVERLAY_HEIGHT_PX:],
                without_overlay[OVERLAY_HEIGHT_PX:],
            )
        )
        self.assertTrue(np.array_equal(session.buffer, without_overlay))

    def test_hiding_the_overlay_leaves_the_pattern_untouched(self):
        session = Session(width=SIDE, height=SIDE)
        session.render()
        buffer = session.buffer.copy()
        session.handle_key("h")
        self.assertFalse(session.params.overlay)
        self.assertTrue(np.array_equal(session.buffer, buffer))
        self.assertTrue(np.array_equal(session.presented(), buffer))

    def test_toggling_the_fixation_mark_redraws_the_pattern(self):
        session = Session(width=SIDE, height=SIDE)
        session.render()
        marked = session.buffer.copy()
        session.handle_key("x")
        self.assertFalse(session.params.fixation_visible)
        self.assertFalse(np.array_equal(marked, session.buffer))
        session.handle_key("x")
        self.assertTrue(session.params.fixation_visible)
        self.assertTrue(np.array_equal(marked, session.buffer))

    def test_the_readout_names_the_eye_distance_and_scale_source(self):
        session = Session(width=SIDE, height=SIDE)
        session.render()
        text = session.overlay_text()
        self.assertIn("400 mm", text)
        self.assertIn("eye both eyes", text)
        self.assertIn("UNCALIBRATED", text)
        self.assertIn("not a medical device", text)
        session.handle_key("m")
        self.assertIn("cover the other eye", session.overlay_text())

    def test_a_calibrated_scale_is_marked_calibrated(self):
        session = Session(width=SIDE, height=SIDE)
        session._base_scale = session._base_scale.with_calibration(5.6)
        session.render()
        self.assertIn("calibrated", session.overlay_text())


if __name__ == "__main__":
    unittest.main()
