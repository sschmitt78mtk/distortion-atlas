"""Entry-point smoke test.

CPython 3.12 returns exit code 5 from ``unittest discover`` when *no* test ran,
so a working discovery entry point needs at least one test. This is that test.
"""

import unittest

import visiontest


class PackageTest(unittest.TestCase):
    def test_package_imports_and_reports_a_version(self):
        self.assertEqual(visiontest.__name__, "visiontest")
        self.assertTrue(visiontest.__version__)


if __name__ == "__main__":
    unittest.main()
