"""Tests for the toolkit-free key bar layout and hit-testing (tasks 1.1-1.4)."""

import unittest

from distortion_atlas import keybar
from distortion_atlas.params import CONTROLS, CONTROL_BY_KEY

STATE = {
    "family": "amsler",
    "eye": "both",
    "correction": True,
    "overlay": True,
    "fixation_visible": True,
    "grade": None,
}

ROW_COUNTS = (7, 10, 12, 6)


def rows(bar):
    """The bar's buttons split into its four rows, in on-screen order."""
    bounds = [0]
    for count in ROW_COUNTS:
        bounds.append(bounds[-1] + count)
    return [bar.buttons[start:stop] for start, stop in zip(bounds, bounds[1:])]


class ButtonSetTest(unittest.TestCase):
    def setUp(self):
        self.bar = keybar.build(1920, 1080, STATE)

    def test_every_key_owns_exactly_one_button(self):
        keys = [button.key for button in self.bar.buttons]
        expected = set(CONTROL_BY_KEY) - {"Esc"}  # Esc shares the quit button
        self.assertEqual(set(keys), expected)
        self.assertEqual(len(keys), len(set(keys)), "a key owns two buttons")
        self.assertEqual(len(self.bar.buttons), 35)

    def test_the_digits_each_own_one_button(self):
        for digit in "0123456789":
            owned = [
                button
                for button in self.bar.buttons
                if button.action == "grade" and button.key == digit
            ]
            self.assertEqual(len(owned), 1, digit)
            self.assertEqual(owned[0].caption, digit)

    def test_the_quit_control_folds_both_keys_into_one_button(self):
        quit_buttons = [b for b in self.bar.buttons if b.action == "quit"]
        self.assertEqual(len(quit_buttons), 1)
        self.assertEqual(quit_buttons[0].key, "q")
        self.assertEqual(quit_buttons[0].hint, "q / Esc")

    def test_every_action_has_a_caption(self):
        actions = {control.action for control in CONTROLS}
        self.assertEqual(set(keybar.CAPTIONS), actions)
        for button in self.bar.buttons:
            self.assertTrue(button.caption, button.action)

    def test_the_bar_has_four_rows_of_the_documented_size(self):
        self.assertEqual(len(keybar.ROW_ACTIONS), 4)
        self.assertEqual([len(row) for row in rows(self.bar)], [7, 10, 12, 6])


class LayoutTest(unittest.TestCase):
    def test_rectangles_stay_inside_the_bar_and_the_screen(self):
        for width, height in ((800, 800), (1920, 1080)):
            with self.subTest(size=(width, height)):
                bar = keybar.build(width, height, STATE)
                left, top, bar_width, bar_height = bar.rect
                self.assertEqual((left, bar_width), (0, width))
                self.assertEqual(top + bar_height, height)
                self.assertLessEqual(bar_height, height)
                for button in bar.buttons:
                    x, y, w, h = button.rect
                    self.assertGreaterEqual(x, left, button)
                    self.assertGreaterEqual(y, top, button)
                    self.assertLessEqual(x + w, left + bar_width, button)
                    self.assertLessEqual(y + h, top + bar_height, button)
                    self.assertLessEqual(x + w, width, button)
                    self.assertLessEqual(y + h, height, button)

    def test_rectangles_never_overlap(self):
        for width, height in ((800, 800), (1920, 1080)):
            with self.subTest(size=(width, height)):
                buttons = keybar.build(width, height, STATE).buttons
                for index, first in enumerate(buttons):
                    ax, ay, aw, ah = first.rect
                    for second in buttons[index + 1:]:
                        bx, by, bw, bh = second.rect
                        overlap = (
                            ax < bx + bw
                            and bx < ax + aw
                            and ay < by + bh
                            and by < ay + ah
                        )
                        self.assertFalse(overlap, (first, second))

    def test_slots_are_equal_width_within_a_row(self):
        for width, height in ((800, 800), (1920, 1080)):
            with self.subTest(size=(width, height)):
                for row in rows(keybar.build(width, height, STATE)):
                    widths = {button.rect[2] for button in row}
                    self.assertEqual(len(widths), 1, widths)

    def test_long_captions_are_elided_and_narrow_slots_drop_the_hint(self):
        bar = keybar.build(800, 800, STATE)
        grade_row = rows(bar)[2]
        for button in grade_row:
            self.assertEqual(button.hint, "", button.caption)
        for button in bar.buttons:
            slot = button.rect[2]
            limit = max(1, (slot - keybar.SLOT_PADDING_PX) // keybar.GLYPH_PX)
            self.assertLessEqual(len(button.caption), limit, button)
        captions = {button.caption for button in bar.buttons}
        self.assertIn("correc…", captions)
        self.assertIn("eye: b…", captions)

    def test_wide_screens_keep_every_hint(self):
        bar = keybar.build(1920, 1080, STATE)
        self.assertTrue(all(button.hint for button in bar.buttons))
        for button in bar.buttons:
            slot = button.rect[2]
            limit = max(1, (slot - keybar.SLOT_PADDING_PX) // keybar.GLYPH_PX)
            self.assertLessEqual(len(button.caption), limit, button)


class StateTest(unittest.TestCase):
    def test_only_the_ten_step_actions_repeat(self):
        bar = keybar.build(1920, 1080, STATE)
        repeatable = {button.action for button in bar.buttons if button.repeatable}
        steps = {
            "variant_prev",
            "variant_next",
            "primary_up",
            "primary_down",
            "secondary_up",
            "secondary_down",
            "contrast_up",
            "contrast_down",
            "distance_up",
            "distance_down",
        }
        self.assertEqual(repeatable, steps)
        self.assertEqual(set(keybar.STEP_ACTIONS), steps)
        never = {
            "grade",
            "eye",
            "correction",
            "overlay",
            "fixation",
            "export",
            "fullscreen",
            "reset",
            "quit",
        }
        self.assertFalse(repeatable & never)

    def test_the_active_family_and_toggles_are_flagged(self):
        bar = keybar.build(800, 800, dict(STATE, grade=3))
        active = {
            (button.action, button.key) for button in bar.buttons if button.active
        }
        self.assertEqual(
            active,
            {
                ("family_amsler", "a"),
                ("overlay", "h"),
                ("fixation", "x"),
                ("grade", "3"),
            },
        )

    def test_an_inactive_state_flags_nothing(self):
        bar = keybar.build(
            800,
            800,
            {
                "family": "lines",
                "eye": "both",
                "correction": True,
                "overlay": False,
                "fixation_visible": False,
                "grade": None,
            },
        )
        active = [button for button in bar.buttons if button.active]
        self.assertEqual(
            [(button.action, button.key) for button in active],
            [("family_lines", "l")],
        )

    def test_eye_and_correction_captions_carry_the_value(self):
        bar = keybar.build(1920, 1080, dict(STATE, eye="left", correction=False))
        captions = {button.action: button.caption for button in bar.buttons}
        self.assertEqual(captions["eye"], "eye: left")
        self.assertEqual(captions["correction"], "correction: not worn")

    def test_hit_test_finds_a_button_and_ignores_gaps(self):
        bar = keybar.build(800, 800, STATE)
        first = bar.buttons[0]
        x, y, width, height = first.rect
        found = keybar.hit_test(bar, x + width / 2, y + height / 2)
        self.assertIs(found, first)
        self.assertIsNone(keybar.hit_test(bar, x + width + keybar.GAP_PX // 2, y + 1))
        self.assertIsNone(keybar.hit_test(bar, 0, 0))
        self.assertIsNone(keybar.hit_test(None, 10, 10))


if __name__ == "__main__":
    unittest.main()
