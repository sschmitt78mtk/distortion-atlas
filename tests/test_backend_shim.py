"""The GLib schema shim that lets Qt 6.6 start on a GNOME 45+ desktop."""

import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from visiontest.backends import qt


class SchemaShimTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.shim = Path(self._tmp.name)
        (self.shim / "org.gnome.qtshim.gschema.xml").write_text(
            "<schemalist/>", encoding="utf-8"
        )
        patcher = mock.patch.dict(
            os.environ,
            {"GSETTINGS_SCHEMA_DIR": "/usr/share/glib-2.0/schemas"},
            clear=False,
        )
        patcher.start()
        self.addCleanup(patcher.stop)
        shim_patcher = mock.patch.object(qt, "schema_shim_dir", lambda: self.shim)
        shim_patcher.start()
        self.addCleanup(shim_patcher.stop)

    def test_a_working_schema_needs_no_shim(self):
        with mock.patch.object(qt, "_schema_key_present", return_value=True):
            self.assertEqual(qt.ensure_gnome_schema(), "ok")
        self.assertEqual(
            os.environ["GSETTINGS_SCHEMA_DIR"], "/usr/share/glib-2.0/schemas"
        )

    def test_a_broken_schema_is_prepended_to_the_existing_search_path(self):
        (self.shim / "gschemas.compiled").write_bytes(b"compiled")
        with mock.patch.object(
            qt, "_schema_key_present", side_effect=[False, True]
        ):
            self.assertEqual(qt.ensure_gnome_schema(), "shimmed")
        parts = os.environ["GSETTINGS_SCHEMA_DIR"].split(os.pathsep)
        self.assertEqual(parts[0], str(self.shim))
        self.assertEqual(parts[1], "/usr/share/glib-2.0/schemas")

    def test_a_missing_compiled_file_is_built_on_demand(self):
        done = subprocess.CompletedProcess(args=[], returncode=0)
        with mock.patch(
            "visiontest.backends.qt.subprocess.run", return_value=done
        ) as run, mock.patch.object(
            qt, "_schema_key_present", side_effect=[False, True]
        ):
            self.assertEqual(qt.ensure_gnome_schema(), "shimmed")
        self.assertEqual(run.call_args[0][0][0], "glib-compile-schemas")

    def test_a_failed_compile_is_reported_instead_of_crashing(self):
        with mock.patch(
            "visiontest.backends.qt.subprocess.run",
            side_effect=OSError("glib-compile-schemas missing"),
        ), mock.patch.object(qt, "_schema_key_present", return_value=False):
            self.assertEqual(qt.ensure_gnome_schema(), "unavailable")

    def test_a_missing_shim_file_is_reported_instead_of_crashing(self):
        (self.shim / "org.gnome.qtshim.gschema.xml").unlink()
        with mock.patch.object(qt, "_schema_key_present", return_value=False):
            self.assertEqual(qt.ensure_gnome_schema(), "unavailable")

    def test_a_probe_that_cannot_run_leaves_the_environment_alone(self):
        with mock.patch.object(
            qt, "_schema_key_present", return_value=True
        ), mock.patch(
            "visiontest.backends.qt.subprocess.run",
            side_effect=OSError("no gsettings"),
        ):
            self.assertEqual(qt.ensure_gnome_schema(), "ok")

class RealDesktopSchemaTest(unittest.TestCase):
    """Uses the checked-in shim and the real ``gsettings`` binary."""

    @unittest.skipUnless(
        sys.platform == "linux", "the shim only exists for Linux desktops"
    )
    def test_this_desktop_ends_up_with_a_readable_schema(self):
        with mock.patch.dict(os.environ, {}, clear=False):
            status = qt.ensure_gnome_schema()
        self.assertIn(status, {"ok", "shimmed"})


if __name__ == "__main__":
    unittest.main()
