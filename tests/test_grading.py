"""Tests for grading capture (task 5.1)."""

import unittest

from visiontest.ui import Session

SIDE = 400


def session(family: str = "amsler", **params) -> Session:
    made = Session(width=SIDE, height=SIDE)
    made.params.family = family
    for name, value in params.items():
        setattr(made.params, name, value)
    return made


class GradeStoreTest(unittest.TestCase):
    def test_grading_before_any_pattern_is_rejected(self):
        subject = session()
        result = subject.grade(5)
        self.assertFalse(result.changed)
        self.assertIn("no pattern shown yet", result.message)
        self.assertEqual(subject.ordered_grades(), [])

    def test_a_grade_is_stored_with_the_item_identity(self):
        subject = session()
        subject.handle_key("a")
        result = subject.grade(6)
        self.assertTrue(result.changed)
        grade = subject.ordered_grades()[0]
        self.assertEqual(grade.family, "amsler")
        self.assertEqual(grade.item_index, 0)
        self.assertEqual(grade.value, 6)
        self.assertEqual(grade.eye, "both")
        self.assertTrue(grade.fixation_visible)
        self.assertEqual(grade.pairing, "black_on_white")
        self.assertEqual(grade.attempts, 1)

    def test_the_grade_carries_the_geometry_in_force(self):
        subject = session(squares=13, contrast=60, field_deg=25.0)
        subject.handle_key("a")
        subject.grade(3)
        geometry = subject.ordered_grades()[0].geometry
        self.assertEqual(geometry["squares"], 13)
        self.assertEqual(geometry["contrast"], 60)
        self.assertEqual(geometry["distance_mm"], 400.0)
        self.assertIn("arcmin_per_px", geometry)
        self.assertEqual(geometry["scale_source"], "panel_derived")
        self.assertIn("field", geometry)
        self.assertEqual(geometry["field"]["squares"], 13)

    def test_regrading_replaces_the_value_and_counts_the_attempt(self):
        subject = session()
        subject.handle_key("a")
        subject.grade(4)
        result = subject.grade(7)
        self.assertIn("regraded", result.message)
        grades = subject.ordered_grades()
        self.assertEqual(len(grades), 1)
        self.assertEqual(grades[0].value, 7)
        self.assertEqual(grades[0].attempts, 2)
        subject.grade(2)
        self.assertEqual(subject.ordered_grades()[0].attempts, 3)

    def test_each_eye_keeps_its_own_grade(self):
        subject = session()
        subject.handle_key("a")
        subject.grade(1)
        subject.handle_key("m")
        self.assertEqual(subject.params.eye, "left")
        subject.grade(8)
        self.assertEqual(len(subject.ordered_grades()), 2)
        self.assertEqual({grade.eye for grade in subject.ordered_grades()}, {"both", "left"})

    def test_a_grade_taken_without_the_fixation_mark_says_so(self):
        subject = session()
        subject.handle_key("a")
        subject.handle_key("x")
        self.assertFalse(subject.params.fixation_visible)
        result = subject.grade(5)
        self.assertIn("fixation", result.message)
        self.assertFalse(subject.ordered_grades()[0].fixation_visible)

    def test_a_grade_key_press_records_a_grade(self):
        subject = session()
        subject.handle_key("a")
        result = subject.handle_key("3")
        self.assertTrue(result.changed)
        self.assertEqual(subject.ordered_grades()[0].value, 3)

    def test_out_of_range_grades_are_rejected(self):
        subject = session()
        subject.handle_key("a")
        with self.assertRaises(ValueError):
            subject.grade(10)
        with self.assertRaises(ValueError):
            subject.grade(-1)

    def test_the_line_family_grades_the_selected_line(self):
        subject = session("lines", line_count=5)
        subject.handle_key("l")
        subject.grade(2)
        subject.handle_key("Tab")
        self.assertEqual(subject.params.current_item(), 1)
        subject.grade(6)
        subject.handle_key("Tab")
        subject.grade(9)

        grades = subject.ordered_grades()
        self.assertEqual([grade.item_index for grade in grades], [0, 1, 2])
        self.assertEqual([grade.value for grade in grades], [2, 6, 9])
        self.assertEqual(
            {grade.geometry["dot_pitch"] for grade in grades}, {subject.params.dot_pitch}
        )

    def test_the_line_selection_stays_inside_the_line_count(self):
        subject = session("lines", line_count=3)
        subject.handle_key("l")
        for _ in range(4):
            subject.handle_key("Tab")
        self.assertLess(subject.params.current_item(), 3)
        subject.grade(4)
        self.assertEqual(subject.ordered_grades()[0].item_index, 1)

    def test_grades_for_other_families_do_not_collide(self):
        subject = session()
        subject.handle_key("a")
        subject.grade(1)
        subject.handle_key("d")
        subject.grade(9)
        self.assertEqual(len(subject.ordered_grades()), 2)
        self.assertEqual(
            {grade.family for grade in subject.ordered_grades()}, {"amsler", "dial"}
        )

    def test_ordered_grades_keep_the_first_grading_order(self):
        subject = session()
        subject.handle_key("a")
        subject.grade(1)
        subject.handle_key("m")
        subject.grade(2)
        subject.handle_key("m")
        subject.grade(3)
        self.assertEqual([grade.eye for grade in subject.ordered_grades()], ["both", "left", "right"])


if __name__ == "__main__":
    unittest.main()
