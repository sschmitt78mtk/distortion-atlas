"""Tests for :mod:`distortion_atlas.params` — control map, steps, defaults (task 4.1)."""

import collections
import unittest

from distortion_atlas.params import (
    CONTROLS,
    CONTROL_BY_KEY,
    FAMILIES,
    LIMITS,
    Params,
    apply_control,
    family_actions,
    lookup,
)


class ControlMapTest(unittest.TestCase):
    def test_no_key_is_mapped_twice(self):
        keys = [key for control in CONTROLS for key in control.keys]
        duplicates = [
            key for key, count in collections.Counter(keys).items() if count > 1
        ]
        self.assertEqual(duplicates, [])
        self.assertEqual(len(CONTROL_BY_KEY), len(keys))

    def test_the_documented_actions_are_all_present(self):
        actions = {control.action for control in CONTROLS}
        expected = {
            "family_amsler",
            "family_lines",
            "family_dial",
            "family_halo",
            "family_veil",
            "family_ghost",
            "family_selfcheck",
            "variant_next",
            "variant_prev",
            "primary_up",
            "primary_down",
            "secondary_up",
            "secondary_down",
            "contrast_up",
            "contrast_down",
            "distance_up",
            "distance_down",
            "eye",
            "correction",
            "grade",
            "overlay",
            "fixation",
            "blindspot",
            "blindspot_inverse",
            "export",
            "fullscreen",
            "reset",
            "quit",
        }
        self.assertEqual(actions, expected)

    def test_every_family_can_be_selected_and_every_digit_grades(self):
        self.assertEqual(set(family_actions()), set(FAMILIES))
        for digit in range(10):
            self.assertEqual(lookup(str(digit)).action, "grade")

    def test_quit_is_reachable_on_two_keys(self):
        self.assertEqual(lookup("q").action, "quit")
        self.assertEqual(lookup("Esc").action, "quit")

    def test_the_inverse_variant_is_reachable_on_i(self):
        self.assertEqual(lookup("i").action, "blindspot_inverse")
        self.assertIsNone(apply_control(Params(), "i"))

    def test_unmapped_key_is_ignored(self):
        self.assertIsNone(lookup("z"))
        self.assertIsNone(apply_control(Params(), "z"))

    def test_session_owned_actions_are_left_to_the_session(self):
        params = Params()
        for key in ("0", "9", "s", "f", "q", "Esc", "h", "x"):
            self.assertIsNone(apply_control(params, key), key)


class StepTest(unittest.TestCase):
    def test_primary_geometry_steps_one_and_five(self):
        params = Params(family="amsler", squares=20)
        apply_control(params, "Up")
        self.assertEqual(params.squares, 21)
        apply_control(params, "Up", coarse=True)
        self.assertEqual(params.squares, 26)
        apply_control(params, "Down", coarse=True)
        self.assertEqual(params.squares, 21)

    def test_primary_follows_the_family(self):
        expected = {
            "amsler": "squares",
            "lines": "dot_pitch",
            "dial": "spoke_count",
            "halo": "source_px",
            "veil": "surround_px",
            "ghost": "ghost_offset",
        }
        for family, field in expected.items():
            with self.subTest(family=family):
                params = Params(family=family)
                before = getattr(params, field)
                apply_control(params, "Up")
                self.assertEqual(getattr(params, field), before + 1)

    def test_secondary_pitch_steps_one(self):
        params = Params(family="lines", line_count=7)
        apply_control(params, "Right")
        self.assertEqual(params.line_count, 8)
        apply_control(params, "Right", coarse=True)
        self.assertEqual(params.line_count, 13)

    def test_secondary_rotation_steps_fifteen_degrees(self):
        params = Params(family="dial", spoke_count=24, rotation_deg=0)
        apply_control(params, "Right")
        self.assertEqual(params.rotation_deg, 15)
        apply_control(params, "Right", coarse=True)
        self.assertEqual(params.rotation_deg, 90)
        apply_control(params, "Left", coarse=True)
        self.assertEqual(params.rotation_deg, 15)

    def test_rotation_wraps_inside_a_full_turn(self):
        params = Params(family="dial", rotation_deg=345)
        apply_control(params, "Right")
        self.assertEqual(params.rotation_deg, 0)

    def test_secondary_for_amsler_changes_the_field(self):
        params = Params(family="amsler", field_deg=20.0)
        apply_control(params, "Right")
        self.assertAlmostEqual(params.field_deg, 21.0)
        apply_control(params, "Right", coarse=True)
        self.assertAlmostEqual(params.field_deg, 26.0)

    def test_secondary_cycles_the_ghost_direction(self):
        params = Params(family="ghost", ghost_direction="right")
        apply_control(params, "Right")
        self.assertEqual(params.ghost_direction, "left")
        apply_control(params, "Right", coarse=True)
        self.assertEqual(params.ghost_direction, "up")

    def test_families_without_a_secondary_say_so(self):
        params = Params(family="halo")
        self.assertIn("no secondary", apply_control(params, "Right"))

    def test_contrast_steps_five_and_twenty(self):
        params = Params(family="amsler", contrast=50)
        apply_control(params, "+")
        self.assertEqual(params.contrast, 55)
        apply_control(params, "+", coarse=True)
        self.assertEqual(params.contrast, 75)
        apply_control(params, "-", coarse=True)
        self.assertEqual(params.contrast, 55)

    def test_contrast_keys_drive_brightness_per_family(self):
        halo = Params(family="halo", luminance=200)
        apply_control(halo, "-")
        self.assertEqual(halo.luminance, 195)
        veil = Params(family="veil", veil_contrast=20)
        apply_control(veil, "+")
        self.assertEqual(veil.veil_contrast, 25)
        ghost = Params(family="ghost", contrast=80)
        apply_control(ghost, "+")
        self.assertEqual(ghost.contrast, 85)

    def test_distance_steps_fifty_millimetres(self):
        params = Params(distance_mm=400)
        apply_control(params, "]")
        self.assertEqual(params.distance_mm, 450)
        apply_control(params, "[", coarse=True)
        self.assertEqual(params.distance_mm, 250)

    def test_values_stay_inside_their_limits(self):
        params = Params(family="amsler", squares=2)
        apply_control(params, "Down", coarse=True)
        self.assertEqual(params.squares, LIMITS["squares"][0])
        params.contrast = 100
        apply_control(params, "+", coarse=True)
        self.assertEqual(params.contrast, LIMITS["contrast"][1])


class FamilyAndResetTest(unittest.TestCase):
    def test_switching_family_keeps_the_other_families_parameters(self):
        params = Params(family="amsler", squares=13, contrast=60)
        apply_control(params, "d")
        self.assertEqual(params.family, "dial")
        params.spoke_count = 30
        apply_control(params, "a")
        self.assertEqual(params.squares, 13)
        self.assertEqual(params.contrast, 60)
        apply_control(params, "d")
        self.assertEqual(params.spoke_count, 30)

    def test_switching_family_resets_the_variant_index(self):
        params = Params(family="amsler", variant=3)
        apply_control(params, "d")
        self.assertEqual(params.variant, 0)

    def test_variants_cycle_with_tab(self):
        params = Params(family="amsler", variant=0)
        apply_control(params, "Tab")
        self.assertEqual(params.variant_name, "white_on_black")
        apply_control(params, "Shift+Tab")
        self.assertEqual(params.variant_name, "black_on_white")
        apply_control(params, "Shift+Tab")
        self.assertEqual(params.variant_name, "blue_on_yellow")

    def test_single_variant_families_report_it(self):
        params = Params(family="dial")
        self.assertIn("single variant", apply_control(params, "Tab"))

    def test_reset_restores_family_defaults_and_keeps_the_session(self):
        params = Params(
            family="dial",
            spoke_count=60,
            rotation_deg=90,
            contrast=30,
            eye="left",
            distance_mm=550,
            ambient_note="dim room",
        )
        apply_control(params, "r")
        self.assertEqual(params.spoke_count, 24)
        self.assertEqual(params.rotation_deg, 0)
        self.assertEqual(params.contrast, 100)
        self.assertEqual(params.eye, "left")
        self.assertEqual(params.distance_mm, 550)
        self.assertEqual(params.ambient_note, "dim room")

    def test_eye_cycles_through_both_eyes_and_back(self):
        params = Params(eye="both")
        apply_control(params, "m")
        self.assertEqual(params.eye, "left")
        apply_control(params, "m")
        self.assertEqual(params.eye, "right")
        apply_control(params, "m")
        self.assertEqual(params.eye, "both")

    def test_correction_toggles(self):
        params = Params(correction=True)
        apply_control(params, "w")
        self.assertFalse(params.correction)
        apply_control(params, "w")
        self.assertTrue(params.correction)

    def test_item_index_tracks_the_line_selection(self):
        params = Params(family="lines", line_count=7, variant=0)
        self.assertEqual(params.item_count(), 7)
        self.assertEqual(params.current_item(), 0)
        params.variant = 6
        self.assertEqual(params.current_item(), 6)
        params.variant = 9
        self.assertEqual(params.current_item(), 2)
        self.assertEqual(Params(family="amsler").item_count(), 1)

    def test_summary_names_the_active_settings(self):
        self.assertIn("red_on_black", Params(family="amsler", variant=2).summary())
        self.assertIn("24 spokes", Params(family="dial").summary())
        self.assertIn("offset 6", Params(family="ghost").summary())

    def test_invalid_values_are_rejected(self):
        with self.assertRaises(ValueError):
            Params(family="nope")
        with self.assertRaises(ValueError):
            Params(eye="third")
        with self.assertRaises(ValueError):
            Params(fixation_kind="cross")
        with self.assertRaises(ValueError):
            Params(ghost_direction="sideways")

    def test_grade_round_trips_through_a_dict(self):
        from distortion_atlas.params import Grade

        grade = Grade(
            family="lines",
            item_index=3,
            value=6,
            geometry={"dot_pitch": 24},
            pairing="black_on_white",
            eye="left",
            fixation_visible=True,
        )
        payload = grade.to_dict()
        self.assertEqual(payload["grade"], 6)
        self.assertEqual(payload["item_index"], 3)
        self.assertEqual(grade.key(), ("lines", 3, "left"))


if __name__ == "__main__":
    unittest.main()
