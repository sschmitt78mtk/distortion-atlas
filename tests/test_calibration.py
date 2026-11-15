"""Tests for :mod:`distortion_atlas.calibration` — always against a temporary config."""

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from distortion_atlas import calibration
from distortion_atlas.calibration import (
    ImplausibleCalibration,
    default_scale,
    is_plausible,
    load_calibration,
    panel_derived_px_per_mm,
    save_calibration,
)


class CalibrationTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.config_home = Path(self._tmp.name)
        patcher = mock.patch.dict(
            os.environ, {"XDG_CONFIG_HOME": str(self.config_home)}, clear=False
        )
        patcher.start()
        self.addCleanup(patcher.stop)
        self.path = self.config_home / "distortion-atlas" / "config.json"

    def test_config_path_follows_xdg_config_home(self):
        self.assertEqual(calibration.config_path(), self.path)

    def test_a_pre_rename_calibration_is_still_read(self):
        legacy = self.config_home / "visiontest" / "config.json"
        legacy.parent.mkdir(parents=True)
        legacy.write_text(json.dumps({"px_per_mm": 5.4}), encoding="utf-8")
        loaded = load_calibration()
        self.assertIsNotNone(loaded)
        self.assertAlmostEqual(loaded.px_per_mm, 5.4)
        self.assertEqual(calibration.legacy_config_path(), legacy)

    def test_missing_file_yields_no_calibration_and_the_derived_fallback(self):
        self.assertIsNone(load_calibration())
        scale = default_scale(distance_mm=400)
        self.assertEqual(scale.source, "panel_derived")
        self.assertAlmostEqual(
            scale.px_per_mm, panel_derived_px_per_mm(1920, 1080, (340.0, 190.0))
        )

    def test_save_then_load_round_trips_a_calibrated_value(self):
        saved = save_calibration(5.6, reference=5.666)
        self.assertTrue(self.path.exists())
        loaded = load_calibration()
        self.assertIsNotNone(loaded)
        self.assertAlmostEqual(loaded.px_per_mm, 5.6)
        self.assertEqual(loaded.source, "calibrated")
        self.assertEqual(loaded.stored_at, saved.stored_at)

        scale = default_scale(distance_mm=400)
        self.assertEqual(scale.source, "calibrated")
        self.assertAlmostEqual(scale.arcmin_per_px, 1.5347, places=3)

    def test_corrupt_file_is_ignored(self):
        self.path.parent.mkdir(parents=True)
        self.path.write_text("{not json", encoding="utf-8")
        self.assertIsNone(load_calibration())
        self.path.write_text(json.dumps({"px_per_mm": "wide"}), encoding="utf-8")
        self.assertIsNone(load_calibration())
        self.path.write_text(json.dumps({"px_per_mm": 0}), encoding="utf-8")
        self.assertIsNone(load_calibration())

    def test_implausible_calibration_is_rejected_and_not_stored(self):
        reference = calibration.panel_derived_px_per_mm()
        with self.assertRaises(ImplausibleCalibration):
            save_calibration(reference * 1.4, reference=reference)
        self.assertFalse(self.path.exists())
        self.assertIsNone(load_calibration())

    def test_implausible_calibration_is_stored_once_confirmed(self):
        reference = calibration.panel_derived_px_per_mm()
        saved = save_calibration(reference * 1.4, reference=reference, confirm=True)
        self.assertAlmostEqual(saved.px_per_mm, reference * 1.4)
        self.assertIsNotNone(load_calibration())

    def test_plausibility_window_is_plus_minus_25_percent(self):
        reference = 5.6
        self.assertTrue(is_plausible(5.6 * 1.24, reference))
        self.assertTrue(is_plausible(5.6 * 0.76, reference))
        self.assertFalse(is_plausible(5.6 * 1.26, reference))
        self.assertFalse(is_plausible(5.6 * 0.74, reference))

    def test_panel_derived_pitch_of_the_target_panel(self):
        self.assertAlmostEqual(
            panel_derived_px_per_mm(1920, 1080, (340.0, 190.0)), 5.6656, places=4
        )
        self.assertAlmostEqual(
            panel_derived_px_per_mm(1920, 1080, (340.0, 190.0)) ** -1,
            0.17650,
            places=4,
        )

    def test_save_rejects_a_non_positive_pitch(self):
        with self.assertRaises(ValueError):
            save_calibration(0.0)


if __name__ == "__main__":
    unittest.main()
