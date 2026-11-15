"""Command-line surface: the --hold policy of the self-check (6.1)."""

import argparse
import unittest

from distortion_atlas import ui


class HoldArgumentTest(unittest.TestCase):
    def test_key_means_wait_for_a_key_press(self):
        self.assertIsNone(ui._parse_hold("key"))
        self.assertIsNone(ui._parse_hold("KEY"))

    def test_numbers_are_seconds(self):
        self.assertEqual(ui._parse_hold("0"), 0.0)
        self.assertEqual(ui._parse_hold("2.5"), 2.5)

    def test_nonsense_is_rejected(self):
        for text in ("abc", "-1", ""):
            with self.subTest(text=text), self.assertRaises(
                argparse.ArgumentTypeError
            ):
                ui._parse_hold(text)

    def test_the_hint_names_the_mode(self):
        self.assertIn("until a key press", ui._describe_hold(None))
        self.assertIn("immediately", ui._describe_hold(0.0))
        self.assertIn("2 s", ui._describe_hold(2.0))


class ParseArgsTest(unittest.TestCase):
    def test_the_self_check_waits_for_a_key_by_default(self):
        args = ui._parse_args(["--self-check"])
        self.assertTrue(args.self_check)
        self.assertIsNone(args.hold)

    def test_zero_is_available_for_scripted_runs(self):
        self.assertEqual(ui._parse_args(["--hold", "0"]).hold, 0.0)

    def test_a_seconds_value_is_accepted(self):
        self.assertEqual(ui._parse_args(["--self-check", "--hold", "3"]).hold, 3.0)

    def test_an_invalid_hold_is_a_usage_error(self):
        with self.assertRaises(SystemExit):
            ui._parse_args(["--self-check", "--hold", "later"])


if __name__ == "__main__":
    unittest.main()
