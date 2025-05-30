#!/usr/bin/env python3

import datetime
import logging
import os
import sys
import unittest

# Import the functions to be tested
from src.functions import parse_timestamp, should_scan_repository_for_GHAS_alerts

# Find the project root directory
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Add the project root directory to the Python path
sys.path.insert(0, project_root)

# Set up logging
logging.basicConfig(level=logging.INFO)


class TestParseTimestamp(unittest.TestCase):
    """Tests for the parse_timestamp function."""

    def test_none_timestamp(self):
        """Test when timestamp is None."""
        with self.assertRaises(ValueError) as context:
            parse_timestamp(None)
        self.assertEqual(str(context.exception), "No timestamp provided")

    def test_testing_flag(self):
        """Test when timestamp is set to 'Testing'."""
        with self.assertRaises(ValueError) as context:
            parse_timestamp("Testing")
        self.assertEqual(str(context.exception), "Testing flag")

    def test_valid_timestamp(self):
        """Test with a valid timestamp."""
        now = datetime.datetime.now()
        timestamp = now.isoformat()
        parsed = parse_timestamp(timestamp)
        self.assertEqual(parsed.year, now.year)
        self.assertEqual(parsed.month, now.month)
        self.assertEqual(parsed.day, now.day)

    def test_valid_timestamp_with_whitespace(self):
        """Test with a valid timestamp that has whitespace."""
        now = datetime.datetime.now()
        timestamp = f" {now.isoformat()} "
        parsed = parse_timestamp(timestamp)
        self.assertEqual(parsed.year, now.year)
        self.assertEqual(parsed.month, now.month)
        self.assertEqual(parsed.day, now.day)

    def test_timestamp_without_timezone(self):
        """Test with a timestamp that doesn't have timezone info."""
        timestamp = "2025-05-28T20:36:15.994131"
        parsed = parse_timestamp(timestamp)
        self.assertEqual(parsed.year, 2025)
        self.assertEqual(parsed.month, 5)
        self.assertEqual(parsed.day, 28)
        self.assertEqual(parsed.hour, 20)
        self.assertEqual(parsed.minute, 36)
        self.assertEqual(parsed.second, 15)

    def test_invalid_timestamp(self):
        """Test with an invalid timestamp."""
        with self.assertRaises(ValueError):
            parse_timestamp("not-a-timestamp")

    def test_non_string_timestamp(self):
        """Test with a non-string timestamp."""
        with self.assertRaises(ValueError):
            parse_timestamp(123)


class TestShouldScanRepository(unittest.TestCase):
    """Tests for the should_scan_repository function."""

    def test_no_timestamp(self):
        """Test when no timestamp is provided."""
        properties = {}
        self.assertTrue(should_scan_repository_for_GHAS_alerts(properties, "GHAS_Status_Updated", 7))

    def test_testing_flag(self):
        """Test when timestamp is set to 'Testing'."""
        properties = {"GHAS_Status_Updated": "Testing"}
        self.assertTrue(should_scan_repository_for_GHAS_alerts(properties, "GHAS_Status_Updated", 7))

    def test_old_timestamp(self):
        """Test when timestamp is older than threshold."""
        eight_days_ago = (datetime.datetime.now() - datetime.timedelta(days=8)).isoformat()
        properties = {"GHAS_Status_Updated": eight_days_ago}
        self.assertTrue(should_scan_repository_for_GHAS_alerts(properties, "GHAS_Status_Updated", 7))

    def test_recent_timestamp(self):
        """Test when timestamp is newer than threshold."""
        yesterday = (datetime.datetime.now() - datetime.timedelta(days=1)).isoformat()
        properties = {
            "GHAS_Status_Updated": yesterday,
            "CodeAlerts": 5,
            "CodeAlerts_Critical": 1,
            "CodeAlerts_High": 2,
            "CodeAlerts_Medium": 1,
            "CodeAlerts_Low": 1,
            "SecretAlerts_Total": 3,
            "SecretAlerts_By_Type": "{}",
            "DependencyAlerts": 4,
            "DependencyAlerts_Critical": 1,
            "DependencyAlerts_High": 1,
            "DependencyAlerts_Moderate": 1,
            "DependencyAlerts_Low": 1
        }
        self.assertFalse(should_scan_repository_for_GHAS_alerts(properties, "GHAS_Status_Updated", 7))

    def test_invalid_timestamp(self):
        """Test when timestamp is invalid."""
        properties = {"GHAS_Status_Updated": "not-a-timestamp"}
        self.assertTrue(should_scan_repository_for_GHAS_alerts(properties, "GHAS_Status_Updated", 7))

    def test_code_alerts_missing_breakdown(self):
        """Test when code alerts are present but severity breakdown is missing."""
        yesterday = (datetime.datetime.now() - datetime.timedelta(days=1)).isoformat()
        properties = {
            "GHAS_Status_Updated": yesterday,
            "CodeAlerts": 5,  # > 0
            # Missing CodeAlerts_Critical
            "CodeAlerts_High": 2,
            "CodeAlerts_Medium": 1,
            "CodeAlerts_Low": 1,
            "SecretAlerts_Total": 3,
            "SecretAlerts_By_Type": "{}",
            "DependencyAlerts": 4,
            "DependencyAlerts_Critical": 1,
            "DependencyAlerts_High": 1,
            "DependencyAlerts_Moderate": 1,
            "DependencyAlerts_Low": 1
        }
        self.assertTrue(should_scan_repository_for_GHAS_alerts(properties, "GHAS_Status_Updated", 7))

    def test_code_alerts_all_missing_breakdown(self):
        """Test when code alerts are present but all severity breakdowns are missing."""
        yesterday = (datetime.datetime.now() - datetime.timedelta(days=1)).isoformat()
        properties = {
            "GHAS_Status_Updated": yesterday,
            "CodeAlerts": 5,  # > 0
            # All severity breakdowns are missing
            "SecretAlerts_Total": 3,
            "SecretAlerts_By_Type": "{}",
            "DependencyAlerts": 4,
            "DependencyAlerts_Critical": 1,
            "DependencyAlerts_High": 1,
            "DependencyAlerts_Moderate": 1,
            "DependencyAlerts_Low": 1
        }
        self.assertTrue(should_scan_repository_for_GHAS_alerts(properties, "GHAS_Status_Updated", 7))

    def test_code_alerts_no_alerts(self):
        """Test when code alerts are zero, we don't require the severity breakdowns."""
        yesterday = (datetime.datetime.now() - datetime.timedelta(days=1)).isoformat()
        properties = {
            "GHAS_Status_Updated": yesterday,
            "CodeAlerts": 0,  # Zero, so we don't care about missing breakdowns
            # Missing severity breakdowns shouldn't trigger a rescan when alerts = 0
            "SecretAlerts_Total": 3,
            "SecretAlerts_By_Type": "{}",
            "DependencyAlerts": 4,
            "DependencyAlerts_Critical": 1,
            "DependencyAlerts_High": 1,
            "DependencyAlerts_Moderate": 1,
            "DependencyAlerts_Low": 1
        }
        self.assertFalse(should_scan_repository_for_GHAS_alerts(properties, "GHAS_Status_Updated", 7))

    def test_secret_alerts_missing_types(self):
        """Test when secret alerts are present but types are missing."""
        yesterday = (datetime.datetime.now() - datetime.timedelta(days=1)).isoformat()
        properties = {
            "GHAS_Status_Updated": yesterday,
            "CodeAlerts": 5,
            "CodeAlerts_Critical": 1,
            "CodeAlerts_High": 2,
            "CodeAlerts_Medium": 1,
            "CodeAlerts_Low": 1,
            "SecretAlerts_Total": 3,  # > 0
            # Missing SecretAlerts_By_Type
            "DependencyAlerts": 4,
            "DependencyAlerts_Critical": 1,
            "DependencyAlerts_High": 1,
            "DependencyAlerts_Moderate": 1,
            "DependencyAlerts_Low": 1
        }
        self.assertTrue(should_scan_repository_for_GHAS_alerts(properties, "GHAS_Status_Updated", 7))

    def test_missing_secret_total(self):
        """Test when secret alerts total is missing but types are present."""
        yesterday = (datetime.datetime.now() - datetime.timedelta(days=1)).isoformat()
        properties = {
            "GHAS_Status_Updated": yesterday,
            "CodeAlerts": 5,
            "CodeAlerts_Critical": 1,
            "CodeAlerts_High": 2,
            "CodeAlerts_Medium": 1,
            "CodeAlerts_Low": 1,
            # Missing SecretAlerts_Total
            "SecretAlerts_By_Type": "{}",  # Present
            "DependencyAlerts": 4,
            "DependencyAlerts_Critical": 1,
            "DependencyAlerts_High": 1,
            "DependencyAlerts_Moderate": 1,
            "DependencyAlerts_Low": 1
        }
        self.assertTrue(should_scan_repository_for_GHAS_alerts(properties, "GHAS_Status_Updated", 7))

    def test_secret_alerts_no_alerts(self):
        """Test when secret alerts are zero, we don't require the types breakdown."""
        yesterday = (datetime.datetime.now() - datetime.timedelta(days=1)).isoformat()
        properties = {
            "GHAS_Status_Updated": yesterday,
            "CodeAlerts": 0,
            "SecretAlerts_Total": 0,  # Zero, so we don't care about missing types
            # Missing SecretAlerts_By_Type shouldn't trigger a rescan when alerts = 0
            "DependencyAlerts": 4,
            "DependencyAlerts_Critical": 1,
            "DependencyAlerts_High": 1,
            "DependencyAlerts_Moderate": 1,
            "DependencyAlerts_Low": 1
        }
        self.assertFalse(should_scan_repository_for_GHAS_alerts(properties, "GHAS_Status_Updated", 7))

    def test_dependency_alerts_missing_breakdown(self):
        """Test when dependency alerts are present but severity breakdown is missing."""
        yesterday = (datetime.datetime.now() - datetime.timedelta(days=1)).isoformat()
        properties = {
            "GHAS_Status_Updated": yesterday,
            "CodeAlerts": 5,
            "CodeAlerts_Critical": 1,
            "CodeAlerts_High": 2,
            "CodeAlerts_Medium": 1,
            "CodeAlerts_Low": 1,
            "SecretAlerts_Total": 3,
            "SecretAlerts_By_Type": "{}",
            "DependencyAlerts": 4,  # > 0
            # Missing DependencyAlerts_Critical
            "DependencyAlerts_High": 1,
            "DependencyAlerts_Moderate": 1,
            "DependencyAlerts_Low": 1
        }
        self.assertTrue(should_scan_repository_for_GHAS_alerts(properties, "GHAS_Status_Updated", 7))

    def test_dependency_alerts_all_missing_breakdown(self):
        """Test when dependency alerts are present but all severity breakdowns are missing."""
        yesterday = (datetime.datetime.now() - datetime.timedelta(days=1)).isoformat()
        properties = {
            "GHAS_Status_Updated": yesterday,
            "CodeAlerts": 5,
            "CodeAlerts_Critical": 1,
            "CodeAlerts_High": 2,
            "CodeAlerts_Medium": 1,
            "CodeAlerts_Low": 1,
            "SecretAlerts_Total": 3,
            "SecretAlerts_By_Type": "{}",
            "DependencyAlerts": 4,  # > 0
            # All severity breakdowns are missing
        }
        self.assertTrue(should_scan_repository_for_GHAS_alerts(properties, "GHAS_Status_Updated", 7))

    def test_dependency_alerts_no_alerts(self):
        """Test when dependency alerts are zero, we don't require the severity breakdowns."""
        yesterday = (datetime.datetime.now() - datetime.timedelta(days=1)).isoformat()
        properties = {
            "GHAS_Status_Updated": yesterday,
            "CodeAlerts": 0,
            "SecretAlerts_Total": 0,
            "DependencyAlerts": 0,  # Zero, so we don't care about missing breakdowns
            # Missing severity breakdowns shouldn't trigger a rescan when alerts = 0
        }
        self.assertFalse(should_scan_repository_for_GHAS_alerts(properties, "GHAS_Status_Updated", 7))

    def test_timestamp_with_leading_whitespace(self):
        """Test timestamp with leading whitespace should be handled gracefully."""
        yesterday = (datetime.datetime.now() - datetime.timedelta(days=1)).isoformat()
        properties = {
            "GHAS_Status_Updated": " " + yesterday,
            "CodeAlerts": 0,
            "SecretAlerts_Total": 0,
            "DependencyAlerts": 0
        }
        # Should parse successfully after stripping whitespace and return False (recently scanned)
        self.assertFalse(should_scan_repository_for_GHAS_alerts(properties, "GHAS_Status_Updated", 7))

    def test_timestamp_with_trailing_whitespace(self):
        """Test timestamp with trailing whitespace should be handled gracefully."""
        yesterday = (datetime.datetime.now() - datetime.timedelta(days=1)).isoformat()
        properties = {
            "GHAS_Status_Updated": yesterday + " ",
            "CodeAlerts": 0,
            "SecretAlerts_Total": 0,
            "DependencyAlerts": 0
        }
        # Should parse successfully after stripping whitespace and return False (recently scanned)
        self.assertFalse(should_scan_repository_for_GHAS_alerts(properties, "GHAS_Status_Updated", 7))

    def test_timestamp_with_both_whitespace(self):
        """Test timestamp with both leading and trailing whitespace should be handled gracefully."""
        yesterday = (datetime.datetime.now() - datetime.timedelta(days=1)).isoformat()
        properties = {
            "GHAS_Status_Updated": " " + yesterday + " ",
            "CodeAlerts": 0,
            "SecretAlerts_Total": 0,
            "DependencyAlerts": 0
        }
        # Should parse successfully after stripping whitespace and return False (recently scanned)
        self.assertFalse(should_scan_repository_for_GHAS_alerts(properties, "GHAS_Status_Updated", 7))

    def test_timestamp_with_newline(self):
        """Test timestamp with newline should be handled gracefully."""
        yesterday = (datetime.datetime.now() - datetime.timedelta(days=1)).isoformat()
        properties = {
            "GHAS_Status_Updated": yesterday + "\n",
            "CodeAlerts": 0,
            "SecretAlerts_Total": 0,
            "DependencyAlerts": 0
        }
        # Should parse successfully after stripping whitespace and return False (recently scanned)
        self.assertFalse(should_scan_repository_for_GHAS_alerts(properties, "GHAS_Status_Updated", 7))

    def test_specific_problematic_timestamp_format(self):
        """Test the specific timestamp format mentioned in the issue."""
        # This is the exact format that was causing issues according to the problem statement
        problematic_timestamp = "2025-05-28T19:09:13.010962"
        properties = {
            "GHAS_Status_Updated": problematic_timestamp,
            "CodeAlerts": 0,
            "SecretAlerts_Total": 0,
            "DependencyAlerts": 0
        }
        # Should parse successfully (this timestamp is in the future, so should return False for "recently scanned")
        self.assertFalse(should_scan_repository_for_GHAS_alerts(properties, "GHAS_Status_Updated", 7))

    def test_specific_problematic_timestamp_with_whitespace(self):
        """Test the specific timestamp format with whitespace that was causing the warning."""
        # This simulates the actual issue where whitespace causes parsing to fail
        problematic_timestamp = " 2025-05-28T19:09:13.010962 "
        properties = {
            "GHAS_Status_Updated": problematic_timestamp,
            "CodeAlerts": 0,
            "SecretAlerts_Total": 0,
            "DependencyAlerts": 0
        }
        # Should parse successfully after stripping whitespace (this timestamp is in the future, so should return False)
        self.assertFalse(should_scan_repository_for_GHAS_alerts(properties, "GHAS_Status_Updated", 7))

    def test_non_string_timestamp(self):
        """Test that non-string timestamps are handled gracefully."""
        properties = {"GHAS_Status_Updated": 123}  # Integer instead of string
        # Should return True (scan) because it can't parse the integer as a timestamp
        self.assertTrue(should_scan_repository_for_GHAS_alerts(properties, "GHAS_Status_Updated", 7))

    def test_timestamp_without_timezone_latest(self):
        """Test the latest timestamp format mentioned in comment - 2025-05-28T20:36:15.994131."""
        # This is the timestamp mentioned in the latest comment from @rajbos
        timestamp = "2025-05-28T20:36:15.994131"
        properties = {
            "GHAS_Status_Updated": timestamp,
            "CodeAlerts": 0,
            "SecretAlerts_Total": 0,
            "DependencyAlerts": 0
        }
        # Should parse successfully (this timestamp is in the future, so should return False for "recently scanned")
        self.assertFalse(should_scan_repository_for_GHAS_alerts(properties, "GHAS_Status_Updated", 7))

    def test_timestamp_without_timezone_with_whitespace(self):
        """Test timestamp without timezone info but with whitespace."""
        timestamp = " 2025-05-28T20:36:15.994131 "
        properties = {
            "GHAS_Status_Updated": timestamp,
            "CodeAlerts": 0,
            "SecretAlerts_Total": 0,
            "DependencyAlerts": 0
        }
        # Should parse successfully after stripping whitespace
        self.assertFalse(should_scan_repository_for_GHAS_alerts(properties, "GHAS_Status_Updated", 7))


if __name__ == "__main__":
    unittest.main()
