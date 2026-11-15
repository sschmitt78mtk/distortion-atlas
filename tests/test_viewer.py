"""Offscreen viewer tests: presentation, key dispatch, pixel-path guard (4.3/4.4)."""

import os
import tempfile
import time
import unittest
from pathlib import Path

import numpy as np

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from distortion_atlas import export, keybar  # noqa: E402
from distortion_atlas.ui import OVERLAY_HEIGHT_PX, Session, check_pixel_path  # noqa: E402

try:  # pragma: no cover - the skip branch only runs without PyQt6
    from PyQt6.QtCore import QEvent, QPoint, QPointF, Qt
    from PyQt6.QtGui import QImage, QKeyEvent, QMouseEvent
    from PyQt6.QtTest import QTest
    from PyQt6.QtWidgets import QApplication

    from distortion_atlas.backends.qt import (
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


def _rgb_array(pixmap):
    """A grabbed pixmap as an ``(height, width, 3)`` uint8 array."""
    image = pixmap.toImage().convertToFormat(QImage.Format.Format_RGB888)
    pointer = image.bits()
    pointer.setsize(image.sizeInBytes())
    height, width = image.height(), image.width()
    stride = image.bytesPerLine()
    raw = np.frombuffer(pointer, dtype=np.uint8, count=stride * height)
    rows = raw.reshape(height, stride)[:, : width * 3].reshape(height, width, 3)
    return rows.copy()


def _mouse_move(widget, point):
    """Move the pointer for real and deliver the move the offscreen platform skips.

    ``QTest.mouseMove`` only warps the cursor; the offscreen platform does not
    synthesize the follow-up event, so the widget is sent the same ``QMouseEvent``
    a real platform would deliver.
    """
    QTest.mouseMove(widget, point)
    event = QMouseEvent(
        QEvent.Type.MouseMove,
        QPointF(point),
        widget.mapToGlobal(point).toPointF(),
        Qt.MouseButton.NoButton,
        Qt.MouseButton.NoButton,
        Qt.KeyboardModifier.NoModifier,
    )
    QApplication.sendEvent(widget, event)



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

    def test_the_scotoma_run_starts_and_stops_the_sampling_timer(self):
        result = self.presenter.dispatch("b")
        self.assertEqual(result.action, "blindspot_started")
        self.assertTrue(self.presenter.widget._stimulus_timer.isActive())
        self.presenter.dispatch("q")
        self.assertFalse(self.presenter.widget._stimulus_timer.isActive())

    def test_a_left_click_responds_while_a_dot_is_lit(self):
        from PyQt6.QtTest import QTest

        self.presenter.dispatch("b")
        widget = self.presenter.widget
        widget._stimulus_timer.stop()
        test = self.session.scotoma
        now = time.monotonic() * 1000.0
        test.gap_end_ms = now - 1.0
        self.assertTrue(test.tick(now))
        self.assertTrue(test.lit)
        QTest.mouseClick(
            widget,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier,
            QPoint(SIDE // 2, SIDE // 2),
        )
        self.assertEqual(test.counts()["seen"], 1)
        self.presenter.dispatch("q")

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

    # -- key bar helpers ---------------------------------------------------
    def _bar(self):
        widget = self.presenter.widget
        return keybar.build(
            widget.width(), widget.height(), self.session.key_bar_state()
        )

    def _button(self, action, key=None):
        for button in self._bar().buttons:
            if button.action == action and (key is None or button.key == key):
                return button
        raise AssertionError(f"no button for {action!r} {key!r}")

    @staticmethod
    def _centre(button):
        x, y, width, height = button.rect
        return QPoint(x + width // 2, y + height // 2)

    def test_the_cursor_follows_the_bar_visibility(self):
        widget = self.presenter.widget
        self.assertEqual(widget.cursor().shape(), Qt.CursorShape.BlankCursor)
        _mouse_move(widget, QPoint(SIDE // 2, SIDE // 2))
        self.assertTrue(self.session.key_bar_visible)
        self.assertEqual(widget.cursor().shape(), Qt.CursorShape.ArrowCursor)
        _mouse_move(widget, self._centre(self._button("grade", "4")))
        self.assertEqual(widget.cursor().shape(), Qt.CursorShape.PointingHandCursor)

    def test_the_idle_timer_hides_the_bar_and_restarts_on_pointer_activity(self):
        presenter = QtPresenter(
            self.session, app=self.app, fullscreen=False, key_bar_idle_ms=60
        )
        self.addCleanup(presenter.close)
        presenter.show(self.session.presented())
        widget = presenter.widget
        _mouse_move(widget, QPoint(SIDE // 2, SIDE // 2))
        self.assertTrue(self.session.key_bar_visible)
        QTest.qWait(40)
        _mouse_move(widget, QPoint(SIDE // 2 + 1, SIDE // 2))
        QTest.qWait(40)
        self.assertTrue(self.session.key_bar_visible, "pointer activity restarted it")
        QTest.qWait(120)
        self.assertFalse(self.session.key_bar_visible)
        self.assertEqual(widget.cursor().shape(), Qt.CursorShape.BlankCursor)

    def test_the_bar_darkens_the_bottom_band_only_while_visible(self):
        self.presenter.show(self.session.presented())
        self.app.processEvents()
        hidden = _rgb_array(self.presenter.widget.grab())
        _mouse_move(self.presenter.widget, QPoint(SIDE // 2, SIDE // 2))
        self.app.processEvents()
        shown = _rgb_array(self.presenter.widget.grab())
        bar_top = self._bar().rect[1]
        self.assertLess(shown[bar_top:].mean(), hidden[bar_top:].mean() - 10)
        self.assertAlmostEqual(
            float(shown[:bar_top].mean()), float(hidden[:bar_top].mean()), delta=0.5
        )
        # Hidden: the band is the untouched buffer; shown: chrome only.
        self.assertTrue(np.array_equal(hidden[bar_top:], self.session.buffer[bar_top:]))
        self.assertFalse(np.array_equal(shown[bar_top:], self.session.buffer[bar_top:]))

    def test_keyboard_input_does_not_reveal_the_bar(self):
        self.presenter.show(self.session.presented())
        QTest.keyClick(self.presenter.widget, Qt.Key.Key_H)
        QTest.keyClick(self.presenter.widget, Qt.Key.Key_Up)
        self.assertFalse(self.session.key_bar_visible)
        self.assertEqual(
            self.presenter.widget.cursor().shape(), Qt.CursorShape.BlankCursor
        )

    # -- click parity ------------------------------------------------------
    def test_clicking_the_dial_button_matches_key_d(self):
        self.presenter.show(self.session.presented())
        QTest.mouseClick(
            self.presenter.widget,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier,
            self._centre(self._button("family_dial")),
        )
        self.assertEqual(self.session.params.family, "dial")
        self.assertIn("pattern: dial", self.session.overlay_text())

    def test_clicking_a_step_button_matches_its_key(self):
        self.presenter.show(self.session.presented())
        before = self.session.params.distance_mm
        QTest.mouseClick(
            self.presenter.widget,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier,
            self._centre(self._button("distance_up")),
        )
        self.assertEqual(self.session.params.distance_mm, before + 50)
        QTest.keyClick(self.presenter.widget, Qt.Key.Key_BracketRight)
        self.assertEqual(self.session.params.distance_mm, before + 100)

    def test_shift_clicking_a_step_button_applies_the_coarse_step(self):
        self.presenter.show(self.session.presented())
        before = self.session.params.squares
        QTest.mouseClick(
            self.presenter.widget,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.ShiftModifier,
            self._centre(self._button("primary_up")),
        )
        self.assertEqual(self.session.params.squares, before + 5)
        QTest.keyClick(self.presenter.widget, Qt.Key.Key_Up)
        self.assertEqual(self.session.params.squares, before + 6)

    def test_clicking_grade_and_export_matches_the_keys(self):
        with tempfile.TemporaryDirectory() as directory:
            self.session.export_dir = Path(directory)
            self.presenter.show(self.session.presented())
            QTest.mouseClick(
                self.presenter.widget,
                Qt.MouseButton.LeftButton,
                Qt.KeyboardModifier.NoModifier,
                self._centre(self._button("grade", "7")),
            )
            key = (
                self.session.params.family,
                self.session.params.current_item(),
                self.session.params.eye,
            )
            self.assertEqual(self.session.grades[key].value, 7)
            QTest.mouseClick(
                self.presenter.widget,
                Qt.MouseButton.LeftButton,
                Qt.KeyboardModifier.NoModifier,
                self._centre(self._button("export")),
            )
            self.assertEqual(len(list(Path(directory).glob("*.png"))), 1)
            self.assertEqual(len(list(Path(directory).glob("*.json"))), 1)

    def test_clicking_fullscreen_matches_key_f(self):
        self.presenter.show(self.session.presented())
        fullscreen = self._button("fullscreen")
        QTest.mouseClick(
            self.presenter.widget,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier,
            self._centre(fullscreen),
        )
        self.assertFalse(self.session.fullscreen)
        QTest.mouseClick(
            self.presenter.widget,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier,
            self._centre(fullscreen),
        )
        self.assertTrue(self.session.fullscreen)

    def test_clicking_quit_ends_the_session(self):
        self.presenter.show(self.session.presented())
        QTest.mouseClick(
            self.presenter.widget,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier,
            self._centre(self._button("quit")),
        )
        self.assertFalse(self.session.running)
        self.assertFalse(self.presenter.widget.isVisible())

    def test_a_click_that_hits_no_button_only_reveals_the_bar(self):
        self.presenter.show(self.session.presented())
        QTest.mouseClick(
            self.presenter.widget,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier,
            QPoint(4, 4),
        )
        self.assertEqual(self.session.params.family, "amsler")
        self.assertTrue(self.session.key_bar_visible)

    # -- hold to repeat ----------------------------------------------------
    def test_holding_a_geometry_button_repeats_the_step(self):
        self.presenter.show(self.session.presented())
        before = self.session.params.squares
        centre = self._centre(self._button("primary_up"))
        QTest.mousePress(
            self.presenter.widget,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier,
            centre,
        )
        QTest.qWait(700)
        QTest.mouseRelease(
            self.presenter.widget,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier,
            centre,
        )
        self.assertGreater(self.session.params.squares, before + 1)
        released = self.session.params.squares
        QTest.qWait(200)
        self.assertEqual(self.session.params.squares, released)

    def test_holding_a_grade_digit_records_one_grade(self):
        self.presenter.show(self.session.presented())
        centre = self._centre(self._button("grade", "5"))
        QTest.mousePress(
            self.presenter.widget,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier,
            centre,
        )
        QTest.qWait(700)
        QTest.mouseRelease(
            self.presenter.widget,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier,
            centre,
        )
        key = (
            self.session.params.family,
            self.session.params.current_item(),
            self.session.params.eye,
        )
        self.assertEqual(self.session.grades[key].value, 5)
        self.assertEqual(self.session.grades[key].attempts, 1)

    # -- suppression for the pixel-path judgement --------------------------
    def test_the_bar_never_appears_for_the_self_check_pattern(self):
        self.session.handle_key("c")
        self.presenter.show(self.session.presented())
        _mouse_move(self.presenter.widget, QPoint(SIDE // 2, SIDE // 2))
        self.assertFalse(self.session.key_bar_visible)
        self.assertEqual(
            self.presenter.widget.cursor().shape(), Qt.CursorShape.BlankCursor
        )

    def test_a_held_self_check_frame_has_no_bar_and_closes_on_a_click(self):
        from PyQt6.QtCore import QTimer

        self.session.handle_key("c")
        self.presenter.show(self.session.presented())
        widget = self.presenter.widget
        QTimer.singleShot(
            30,
            lambda: _mouse_move(widget, QPoint(SIDE // 2, SIDE // 2)),
        )
        QTimer.singleShot(
            80,
            lambda: QTest.mouseClick(
                widget,
                Qt.MouseButton.LeftButton,
                Qt.KeyboardModifier.NoModifier,
                QPoint(SIDE // 2, SIDE // 2),
            ),
        )
        self.presenter.hold(None)
        self.assertFalse(widget.isVisible())
        self.assertFalse(self.session.key_bar_visible)
        self.assertEqual(self.session.params.family, "selfcheck")


@unittest.skipUnless(HAVE_QT, "PyQt6 is not installed")
class KeyMappingTest(unittest.TestCase):
    def _event(self, key, modifiers=Qt.KeyboardModifier.NoModifier, text=""):
        return QKeyEvent(QEvent.Type.KeyPress, key, modifiers, text)

    def test_letters_digits_and_esc_keep_their_names(self):
        self.assertEqual(key_name(self._event(Qt.Key.Key_A, text="a")), "a")
        self.assertEqual(key_name(self._event(Qt.Key.Key_5, text="5")), "5")
        self.assertEqual(key_name(self._event(Qt.Key.Key_Escape)), "Esc")
        self.assertEqual(key_name(self._event(Qt.Key.Key_Backtab)), "Shift+Tab")

    def test_space_is_named_for_the_scotoma_response(self):
        self.assertEqual(key_name(self._event(Qt.Key.Key_Space, text=" ")), "Space")

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


class KeyBarStateTest(unittest.TestCase):
    """Session-side visibility and the state snapshot (tasks 2.1/2.2)."""

    def test_a_new_session_reports_the_bar_hidden_and_allowed(self):
        session = Session(width=SIDE, height=SIDE)
        self.assertFalse(session.key_bar_visible)
        self.assertTrue(session.key_bar_allowed)

    def test_show_and_hide_toggle_the_visibility_flag(self):
        session = Session(width=SIDE, height=SIDE)
        self.assertTrue(session.show_key_bar())
        self.assertTrue(session.key_bar_visible)
        session.hide_key_bar()
        self.assertFalse(session.key_bar_visible)

    def test_the_snapshot_reports_the_live_values_and_the_grade(self):
        session = Session(width=SIDE, height=SIDE)
        session.handle_key("m")  # eye -> left
        session.handle_key("w")  # correction not worn
        session.handle_key("h")  # HUD off
        session.handle_key("x")  # fixation mark off
        session.render()
        session.handle_key("3")
        self.assertEqual(
            session.key_bar_state(),
            {
                "family": "amsler",
                "eye": "left",
                "correction": False,
                "overlay": False,
                "fixation_visible": False,
                "grade": 3,
            },
        )

    def test_show_is_refused_while_the_self_check_family_is_displayed(self):
        session = Session(width=SIDE, height=SIDE)
        session.handle_key("c")
        self.assertFalse(session.key_bar_allowed)
        self.assertFalse(session.show_key_bar())
        self.assertFalse(session.key_bar_visible)


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
