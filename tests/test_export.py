"""Tests for session export: PNG, JSON record, EDID panel identity (5.2 / 5.3)."""

import json
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

import numpy as np
from PIL import Image

from distortion_atlas import blindspot, export
from distortion_atlas.blindspot import BlindSpotSettings
from distortion_atlas.fixation import size_for_dot
from distortion_atlas.ui import Session

SIDE = 200


def make_edid(
    name: str = "Test Panel",
    manufacturer: str = "DEL",
    hactive: int = 1920,
    vactive: int = 1080,
    width_mm: int = 340,
    height_mm: int = 190,
) -> bytes:
    data = bytearray(128)
    data[0:8] = b"\x00\xff\xff\xff\xff\xff\xff\x00"
    codes = [ord(letter) - 64 for letter in manufacturer[:3].ljust(3)]
    value = (codes[0] << 10) | (codes[1] << 5) | codes[2]
    data[8] = (value >> 8) & 0xFF
    data[9] = value & 0xFF
    data[12] = width_mm & 0xFF
    data[13] = ((width_mm >> 8) & 0x0F) << 4
    data[14] = height_mm & 0xFF
    data[15] = ((height_mm >> 8) & 0x0F) << 4
    data[54:56] = (14850).to_bytes(2, "little")
    data[56] = hactive & 0xFF
    data[57] = 0x64
    data[58] = ((hactive >> 8) & 0x0F) << 4
    data[59] = vactive & 0xFF
    data[60] = 0x32
    data[61] = ((vactive >> 8) & 0x0F) << 4
    data[72:77] = bytes([0x00, 0x00, 0x00, 0xFC, 0x00])
    text = name.encode("ascii")[:13].ljust(13, b" ")
    data[77:90] = text
    data[90] = 0x0A
    return bytes(data)


class SessionFixture(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.dir = Path(self._tmp.name)
        self.session = Session(width=SIDE, height=SIDE, export_dir=self.dir)
        self.session.ambient_note = "dim room, evening"
        self.session.handle_key("a")
        self.session.grade(4)
        self.session.handle_key("m")
        self.session.grade(7)


class ExportTest(SessionFixture):
    def test_export_writes_a_png_and_a_json_record(self):
        moment = datetime(2026, 11, 15, 13, 45, 12)
        result = self.session.export(timestamp=moment)
        self.assertTrue(result.ok, result.message())
        self.assertTrue(result.png_path.exists())
        self.assertTrue(result.json_path.exists())
        self.assertEqual(result.png_path.name, "distortion-atlas-20261115-134512.png")
        self.assertEqual(result.json_path.name, "distortion-atlas-20261115-134512.json")

        with Image.open(result.png_path) as image:
            self.assertEqual(image.size, (SIDE, SIDE))
            self.assertEqual(image.mode, "RGB")

    def test_the_png_is_the_displayed_buffer_without_overlay(self):
        self.session.params.overlay = True
        result = self.session.export(timestamp=datetime(2026, 1, 2, 3, 4, 5))
        self.assertTrue(result.ok)
        exported = np.asarray(Image.open(result.png_path))
        self.assertTrue(np.array_equal(exported, self.session.buffer))

    def test_the_record_round_trips_and_names_the_session(self):
        result = self.session.export(timestamp=datetime(2026, 1, 2, 3, 4, 5))
        record = json.loads(result.json_path.read_text(encoding="utf-8"))

        self.assertEqual(record["tool"]["name"], "distortion-atlas")
        self.assertEqual(record["scale"]["source"], "panel_derived")
        self.assertAlmostEqual(record["scale"]["distance_mm"], 400.0)
        self.assertEqual(record["context"]["eye"], "left")
        self.assertEqual(record["context"]["correction"], "worn")
        self.assertEqual(record["context"]["ambient_note"], "dim room, evening")
        self.assertEqual(
            record["context"]["fixation"]["size_px"], self.session.params.fixation_px
        )
        self.assertEqual(
            record["context"]["fixation"]["effective_size_px"],
            self.session.params.fixation_px,
        )
        self.assertEqual(record["display"]["buffer_px"], [SIDE, SIDE])
        self.assertFalse(record["display"]["overlay_exported"])
        self.assertEqual(len(record["grades"]), 2)
        self.assertEqual({grade["eye"] for grade in record["grades"]}, {"both", "left"})
        self.assertIn("not a medical device", record["disclaimer"])
        self.assertIn("photosensitivity", record["photosensitivity_warning"])
        self.assertIn("Not a medical device", record["non_diagnostic"])
        self.assertTrue(record["pattern"]["parameters"]["family"])
        self.assertIn("field", record["pattern"])
        self.assertIsInstance(record["overlay_text"], str)

    def test_contrast_flags_report_the_display_limit(self):
        self.session.params.contrast = 1
        result = self.session.export(timestamp=datetime(2026, 1, 2, 3, 4, 5))
        record = json.loads(result.json_path.read_text(encoding="utf-8"))
        self.assertTrue(record["contrast_limits"]["display_limited"])
        self.assertLessEqual(record["contrast_limits"]["code_difference"], 3)

    def test_an_unwritable_location_fails_without_losing_the_session(self):
        blocked = self.dir / "blocked"
        blocked.write_text("not a directory", encoding="utf-8")
        before = [grade.to_dict() for grade in self.session.ordered_grades()]

        result = self.session.export(directory=blocked)
        self.assertFalse(result.ok)
        self.assertIn(str(blocked), self.session.message)
        self.assertEqual(
            [grade.to_dict() for grade in self.session.ordered_grades()], before
        )
        # still usable afterwards
        self.session.handle_key("d")
        self.session.grade(2)
        self.assertEqual(len(self.session.ordered_grades()), 3)

    def test_export_before_any_pattern_is_reported(self):
        fresh = Session(width=SIDE, height=SIDE, export_dir=self.dir)
        result = fresh.export()
        self.assertFalse(result.ok)
        self.assertIn("no pattern", result.error)

    def test_the_default_export_directory_is_used_when_none_is_given(self):
        session = Session(width=SIDE, height=SIDE)
        session.render()
        self.assertEqual(session.export_dir, export.DEFAULT_EXPORT_DIR)


class PanelIdentityTest(SessionFixture):
    def test_a_readable_edid_names_the_panel_and_its_resolution(self):
        path = self.dir / "edid.bin"
        path.write_bytes(make_edid())
        panel = export.panel_identity(path)
        self.assertEqual(panel["name"], "Test Panel")
        self.assertEqual(panel["manufacturer"], "DEL")
        self.assertEqual(panel["resolution"], "1920x1080")
        self.assertEqual(panel["size_mm"], [340, 190])
        self.assertEqual(panel["source"], "edid")

    def test_an_unreadable_edid_still_produces_a_complete_record(self):
        missing = self.dir / "nope.bin"
        panel = export.panel_identity(missing)
        self.assertEqual(panel["name"], "unknown")
        self.assertEqual(panel["source"], "unknown")

        result = self.session.export(
            timestamp=datetime(2026, 1, 2, 3, 4, 5), panel=panel
        )
        self.assertTrue(result.ok)
        record = json.loads(result.json_path.read_text(encoding="utf-8"))
        self.assertEqual(record["panel"]["name"], "unknown")
        for key in (
            "tool",
            "scale",
            "pattern",
            "context",
            "grades",
            "display",
            "pixel_path",
            "contrast_limits",
            "disclaimer",
        ):
            self.assertIn(key, record)

    def test_a_truncated_or_invalid_edid_is_ignored(self):
        path = self.dir / "short.bin"
        path.write_bytes(b"\x00\xff\xff")
        self.assertEqual(export.panel_identity(path)["source"], "unknown")

        path.write_bytes(b"X" * 128)
        self.assertEqual(export.panel_identity(path)["source"], "unknown")

    def test_the_monitor_name_descriptor_wins_over_free_text(self):
        data = bytearray(make_edid(name="Workshop LCD"))
        data[90:108] = bytes([0x00, 0x00, 0x00, 0xFE, 0x00]) + b"free text    " + b"\x0a"
        panel = export.parse_edid(bytes(data))
        self.assertEqual(panel["name"], "Workshop LCD")

    def test_the_exported_record_carries_the_panel_from_the_edid_file(self):
        path = self.dir / "edid.bin"
        path.write_bytes(make_edid(name="Bench Panel", hactive=2560, vactive=1440))
        panel = export.panel_identity(path)
        result = self.session.export(
            timestamp=datetime(2026, 1, 2, 3, 4, 5), panel=panel
        )
        record = json.loads(result.json_path.read_text(encoding="utf-8"))
        self.assertEqual(record["panel"]["name"], "Bench Panel")
        self.assertEqual(record["panel"]["resolution"], "2560x1440")


class BlindspotRecordTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.dir = Path(self._tmp.name)

    def test_a_finished_scotoma_test_adds_the_block_and_the_results_png(self):
        session = Session(width=200, height=200, export_dir=self.dir)
        session.params.eye = "left"
        session.params.dot_pitch = 20
        test = session.start_scotoma_test(
            BlindSpotSettings(gap=(1000, 1000), seed=5, outside_sample=0),
            now_ms=0,
        )
        self.assertTrue(test.tick(1000))
        self.assertTrue(test.respond(1300))
        test.stop(2000)
        session.render()

        result = session.export(timestamp=datetime(2026, 1, 2, 3, 4, 5))
        self.assertTrue(result.ok, result.message())
        record = json.loads(result.json_path.read_text(encoding="utf-8"))
        block = record["blindspot"]
        self.assertEqual(block["seed"], 5)
        self.assertEqual(block["settings"]["window_ms"], 1500)
        self.assertEqual(block["context"]["eye"], "left")
        self.assertEqual(block["summary"]["seen"], 1)
        self.assertEqual(block["summary"]["central_seen"], "1/24")
        self.assertEqual(len(block["positions"]), len(test.positions))
        attempts = [
            attempt
            for position in block["positions"]
            for attempt in position["attempts"]
        ]
        self.assertEqual(attempts[0]["outcome"], "seen")
        self.assertEqual(attempts[0]["response_ms"], 300)
        self.assertEqual(block["variant"], "standard")
        self.assertEqual(block["settings"]["blink_ms"], 0)
        self.assertEqual(
            record["photosensitivity_warning"],
            export.PHOTOSENSITIVITY_WARNING,
        )
        self.assertIn("flashing", record["photosensitivity_warning"])
        self.assertIn("Not a medical device", record["non_diagnostic"])

        with Image.open(result.png_path) as image:
            exported = np.asarray(image)
        self.assertTrue(np.array_equal(exported, session.buffer))

    def test_an_inverse_run_records_the_variant_and_the_bright_field_warning(self):
        session = Session(width=200, height=200, export_dir=self.dir)
        session.params.dot_pitch = 20
        session.start_scotoma_test(
            Session.scotoma_settings(blindspot.INVERSE), now_ms=0
        )
        session.scotoma.stop(100)
        session.render()

        result = session.export(timestamp=datetime(2026, 1, 2, 3, 4, 5))
        self.assertTrue(result.ok, result.message())
        record = json.loads(result.json_path.read_text(encoding="utf-8"))
        block = record["blindspot"]
        self.assertEqual(block["variant"], "inverse")
        self.assertEqual(block["settings"]["blink_ms"], 500)
        self.assertEqual(
            record["photosensitivity_warning"],
            export.INVERSE_PHOTOSENSITIVITY_WARNING,
        )
        warning = record["photosensitivity_warning"].lower()
        self.assertIn("bright field", warning)
        self.assertIn("blink", warning)
        self.assertIn("Not a medical device", record["non_diagnostic"])
        fixation = record["context"]["fixation"]
        self.assertEqual(fixation["size_px"], session.params.fixation_px)
        self.assertEqual(
            fixation["effective_size_px"],
            size_for_dot(session.scotoma.settings.dot_px),
        )
        # The results frame stays dark even though the test field was bright.
        self.assertEqual(tuple(session.buffer[0, 0]), (0, 0, 0))

        with Image.open(result.png_path) as image:
            exported = np.asarray(image)
        self.assertTrue(np.array_equal(exported, session.buffer))


if __name__ == "__main__":
    unittest.main()
