"""Session-level integration: every family at every working distance, plus export.

These cover the automatable half of the on-panel checks: each family renders at
300–600 mm with one eye selected, one grade per family survives the sweep, a
ruler calibration changes every reported value consistently, and the exported
PNG is identical to what the presenter shows apart from the readout strip.
"""

import json
import os
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest import mock

import numpy as np
from PIL import Image

from distortion_atlas import calibration
from distortion_atlas.params import CONTROLS, FAMILIES
from distortion_atlas.ui import OVERLAY_HEIGHT_PX, Session

DISTANCES = (300, 400, 500, 600)
SIDE = 1080


def key_for_family(family: str) -> str:
    action = f"family_{family}"
    for control in CONTROLS:
        if control.action == action:
            return control.keys[0]
    raise AssertionError(f"no key selects {family}")


class FamilySweepTest(unittest.TestCase):
    def test_every_family_renders_at_every_working_distance(self):
        for family in FAMILIES:
            for distance in DISTANCES:
                with self.subTest(family=family, distance=distance):
                    session = Session(width=SIDE, height=SIDE)
                    session.params.family = family
                    session.params.distance_mm = float(distance)
                    session.params.eye = "left"
                    buffer = session.render()

                    self.assertEqual(buffer.shape, (SIDE, SIDE, 3))
                    self.assertEqual(buffer.dtype, np.uint8)
                    self.assertEqual(session.shown_family, family)
                    self.assertIn(f"{distance} mm", session.overlay_text())
                    if family == "amsler":
                        fit = session.last_fit
                        self.assertIsNotNone(fit)
                        self.assertLessEqual(fit.pixels + 2 * fit.margin_px, SIDE)
                        self.assertGreater(fit.field_deg, 5.0)
                        self.assertLessEqual(fit.field_deg, 20.0)
                        # 600 mm cannot show a 20° field on a 1080-px buffer
                        self.assertEqual(fit.fitted, distance == 600)

    def test_one_grade_per_family_survives_the_sweep(self):
        session = Session(width=SIDE, height=SIDE)
        session.params.eye = "left"
        for index, family in enumerate(FAMILIES):
            with self.subTest(family=family):
                session.handle_key(key_for_family(family))
                self.assertEqual(session.params.family, family)
                result = session.grade(index % 10)
                self.assertTrue(result.changed, result.message)

        grades = session.ordered_grades()
        self.assertEqual(len(grades), len(FAMILIES))
        self.assertEqual({grade.family for grade in grades}, set(FAMILIES))
        self.assertEqual({grade.eye for grade in grades}, {"left"})

    def test_monocular_selection_is_reminded_for_left_and_right(self):
        for eye, expected in (("left", True), ("right", True), ("both", False)):
            with self.subTest(eye=eye):
                session = Session(width=SIDE, height=SIDE)
                session.params.eye = eye
                session.render()
                text = session.overlay_text()
                self.assertEqual("cover the other eye" in text, expected)

    def test_every_family_responds_to_its_own_brightness_key(self):
        """`+`/`-` must change the rendered frame for every family."""
        for family in FAMILIES:
            with self.subTest(family=family):
                session = Session(width=SIDE, height=SIDE)
                session.params.family = family
                before = session.render().copy()
                session.handle_key("-")
                session.handle_key("-")
                after = session.render()
                if family == "selfcheck":
                    self.assertTrue(np.array_equal(before, after))
                else:
                    self.assertFalse(np.array_equal(before, after))

    def test_switching_family_keeps_previous_parameters_in_the_sweep(self):
        session = Session(width=SIDE, height=SIDE)
        session.handle_key("a")
        session.params.squares = 14
        session.handle_key("d")
        session.params.spoke_count = 32
        session.handle_key("a")
        self.assertEqual(session.params.squares, 14)
        session.handle_key("d")
        self.assertEqual(session.params.spoke_count, 32)


class CalibrationIntegrationTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)
        patcher = mock.patch.dict(
            os.environ, {"XDG_CONFIG_HOME": str(self.root)}, clear=False
        )
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_a_ruler_calibration_changes_every_reported_value_consistently(self):
        session = Session(width=1920, height=1080, export_dir=self.root)
        before = session.scale
        self.assertAlmostEqual(before.px_for_mm(100), 566.56, delta=0.1)

        session.set_calibration(5.6)
        after = session.scale
        self.assertEqual(after.source, "calibrated")
        self.assertAlmostEqual(after.px_for_mm(100), 560.0)
        self.assertAlmostEqual(after.mm_for_px(after.px_for_mm(100)), 100.0)
        self.assertGreater(after.arcmin_per_px, before.arcmin_per_px)
        self.assertAlmostEqual(
            after.arcmin_per_px / before.arcmin_per_px, 5.665626 / 5.6, places=5
        )

        session.render()
        result = session.export(timestamp=datetime(2026, 5, 6, 7, 8, 9))
        record = json.loads(result.json_path.read_text(encoding="utf-8"))
        self.assertEqual(record["scale"]["source"], "calibrated")
        self.assertAlmostEqual(record["scale"]["px_per_mm"], 5.6, places=6)

    def test_an_implausible_ruler_value_is_refused_and_changes_nothing(self):
        session = Session(width=1920, height=1080)
        before = session.scale.px_per_mm
        with self.assertRaises(calibration.ImplausibleCalibration):
            session.set_calibration(before * 2)
        self.assertEqual(session.scale.px_per_mm, before)
        self.assertEqual(session.scale.source, "panel_derived")

        session.set_calibration(before * 2, confirm=True)
        self.assertEqual(session.scale.source, "calibrated")

    def test_a_stored_calibration_is_used_by_the_next_session(self):
        Session(width=1920, height=1080).set_calibration(5.5)
        fresh = Session(width=1920, height=1080)
        self.assertEqual(fresh.scale.source, "calibrated")
        self.assertAlmostEqual(fresh.scale.px_per_mm, 5.5)


class ExportIntegrationTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)

    def test_the_exported_png_matches_what_is_presented(self):
        session = Session(width=SIDE, height=SIDE, export_dir=self.root)
        session.handle_key("a")
        session.handle_key("m")
        session.handle_key("l")
        session.grade(6)
        presented = session.presented()

        result = session.export(timestamp=datetime(2026, 7, 8, 9, 10, 11))
        self.assertTrue(result.ok, result.message())
        exported = np.asarray(Image.open(result.png_path))

        self.assertEqual(exported.shape, presented.shape)
        self.assertTrue(
            np.array_equal(
                exported[OVERLAY_HEIGHT_PX:], presented[OVERLAY_HEIGHT_PX:]
            )
        )

        record = json.loads(result.json_path.read_text(encoding="utf-8"))
        self.assertEqual(record["context"]["eye"], "left")
        self.assertEqual(record["scale"]["source"], "panel_derived")
        self.assertEqual(record["scale"]["distance_mm"], 400.0)
        self.assertEqual(len(record["grades"]), 1)
        grade = record["grades"][0]
        self.assertEqual(grade["family"], "lines")
        self.assertEqual(grade["eye"], "left")
        self.assertEqual(grade["grade"], 6)
        self.assertIn("dot_pitch", grade["geometry"])
        self.assertEqual(result.png_path.name, "distortion-atlas-20260708-091011.png")


if __name__ == "__main__":
    unittest.main()
