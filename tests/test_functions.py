#!/usr/bin/env python3

import datetime
import logging
import os
import sys
import unittest

# Find the project root directory
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Add the project root directory to the path so we can import our modules
sys.path.insert(0, project_root)

# Import the functions to be tested
from src.functions import parse_timestamp, should_scan_repository_for_GHAS_alerts


class TestShouldScanRepository(unittest.TestCase):
    """Test the should_scan_repository_for_GHAS_alerts function."""

    def test_timestamp_without_timezone_with_whitespace(self):
        """Test timestamp without timezone info but with whitespace."""
        yesterday = (datetime.datetime.now() - datetime.timedelta(days=1)).isoformat()
        # Remove timezone info and add whitespace
        timestamp_no_tz = yesterday.split('+')[0].split('Z')[0]  # Remove timezone if present
        timestamp = f" {timestamp_no_tz} "
        properties = {
            "CodeAlerts": 0,
            "SecretAlerts_Total": 0,
            "DependencyAlerts": 0,
            "SecretAlerts_By_Type": "{}",
            "CodeAlerts_Last_Scanned": timestamp,
            "SecretAlerts_Last_Scanned": timestamp,
            "DependencyAlerts_Last_Scanned": timestamp,
            "GHAS_Status_Updated": timestamp
        }
        # Should not scan due to recent timestamp, even without timezone
        result = should_scan_repository_for_GHAS_alerts(properties, "GHAS_Status_Updated", 7)
        self.assertFalse(result)

    def test_recent_timestamp(self):
        """Test with recent timestamp - should not scan."""
        recent_time = datetime.datetime.now() - datetime.timedelta(hours=1)
        timestamp = recent_time.isoformat() + "Z"
        properties = {
            "CodeAlerts": 5,
            "SecretAlerts_Total": 3,
            "DependencyAlerts": 2,
            "SecretAlerts_By_Type": '{"api_key": 1, "password": 2}',  # Proper JSON with types
            "CodeAlerts_Last_Scanned": timestamp,
            "SecretAlerts_Last_Scanned": timestamp,
            "DependencyAlerts_Last_Scanned": timestamp,
            "GHAS_Status_Updated": timestamp
        }
        result = should_scan_repository_for_GHAS_alerts(properties, "GHAS_Status_Updated", 7)
        self.assertFalse(result)

    def test_old_timestamp(self):
        """Test with old timestamp - should scan."""
        old_time = datetime.datetime.now() - datetime.timedelta(days=10)
        timestamp = old_time.isoformat() + "Z"
        properties = {
            "CodeAlerts": 0,
            "SecretAlerts_Total": 0,
            "DependencyAlerts": 0,
            "SecretAlerts_By_Type": "{}",
            "CodeAlerts_Last_Scanned": timestamp,
            "SecretAlerts_Last_Scanned": timestamp,
            "DependencyAlerts_Last_Scanned": timestamp,
            "GHAS_Status_Updated": timestamp
        }
        result = should_scan_repository_for_GHAS_alerts(properties, "GHAS_Status_Updated", 7)
        self.assertTrue(result)

    def test_no_timestamp(self):
        """Test with no timestamp - should scan."""
        properties = {
            "CodeAlerts": 0,
            "SecretAlerts_Total": 0,
            "DependencyAlerts": 0,
            "SecretAlerts_By_Type": "{}"
        }
        result = should_scan_repository_for_GHAS_alerts(properties, "GHAS_Status_Updated", 7)
        self.assertTrue(result)

    def test_empty_properties(self):
        """Test with empty properties - should scan."""
        properties = {}
        result = should_scan_repository_for_GHAS_alerts(properties, "GHAS_Status_Updated", 7)
        self.assertTrue(result)

    def test_code_alerts_no_alerts(self):
        """Test code alerts completeness when no alerts are found."""
        recent_time = datetime.datetime.now() - datetime.timedelta(hours=1)
        timestamp = recent_time.isoformat() + "Z"
        properties = {
            "CodeAlerts": 0,
            "SecretAlerts_Total": 0,  # Changed from 3 to 0 to avoid triggering rescan
            "DependencyAlerts": 0,
            "SecretAlerts_By_Type": "{}",
            "CodeAlerts_Last_Scanned": timestamp,
            "SecretAlerts_Last_Scanned": timestamp,
            "DependencyAlerts_Last_Scanned": timestamp,
            "GHAS_Status_Updated": timestamp
        }
        result = should_scan_repository_for_GHAS_alerts(properties, "GHAS_Status_Updated", 7)
        self.assertFalse(result)

    def test_secret_alerts_empty_types_should_rescan(self):
        """Test that SecretAlerts_By_Type being '{}' with existing alerts triggers rescan."""
        recent_time = datetime.datetime.now() - datetime.timedelta(hours=1)
        timestamp = recent_time.isoformat() + "Z"
        properties = {
            "CodeAlerts": 0,
            "SecretAlerts_Total": 3,  # Has secret alerts
            "DependencyAlerts": 0,
            "SecretAlerts_By_Type": "{}",  # But no types data - should trigger rescan
            "CodeAlerts_Last_Scanned": timestamp,
            "SecretAlerts_Last_Scanned": timestamp,
            "DependencyAlerts_Last_Scanned": timestamp,
            "GHAS_Status_Updated": timestamp
        }
        result = should_scan_repository_for_GHAS_alerts(properties, "GHAS_Status_Updated", 7)
        self.assertTrue(result)

    def test_secret_alerts_none_string_should_rescan(self):
        """Test that SecretAlerts_By_Type being 'None' (string) triggers rescan."""
        recent_time = datetime.datetime.now() - datetime.timedelta(hours=1)
        timestamp = recent_time.isoformat() + "Z"
        properties = {
            "CodeAlerts": 0,
            "SecretAlerts_Total": 2,
            "DependencyAlerts": 0,
            "SecretAlerts_By_Type": "None",  # String "None" - should trigger rescan
            "CodeAlerts_Last_Scanned": timestamp,
            "SecretAlerts_Last_Scanned": timestamp,
            "DependencyAlerts_Last_Scanned": timestamp,
            "GHAS_Status_Updated": timestamp
        }
        result = should_scan_repository_for_GHAS_alerts(properties, "GHAS_Status_Updated", 7)
        self.assertTrue(result)

    def test_dependency_alerts_string_none(self):
        """Test dependency alerts with string 'None' value."""
        recent_time = datetime.datetime.now() - datetime.timedelta(hours=1)
        timestamp = recent_time.isoformat() + "Z"
        properties = {
            "CodeAlerts": 0,
            "SecretAlerts_Total": 0,
            "DependencyAlerts": "None",  # String "None" - should trigger rescan
            "SecretAlerts_By_Type": "{}",
            "CodeAlerts_Last_Scanned": timestamp,
            "SecretAlerts_Last_Scanned": timestamp,
            "DependencyAlerts_Last_Scanned": timestamp,
            "GHAS_Status_Updated": timestamp
        }
        result = should_scan_repository_for_GHAS_alerts(properties, "GHAS_Status_Updated", 7)
        self.assertTrue(result)

    def test_code_alerts_string_none(self):
        """Test code alerts with string 'None' value."""
        recent_time = datetime.datetime.now() - datetime.timedelta(hours=1)
        timestamp = recent_time.isoformat() + "Z"
        properties = {
            "CodeAlerts": "None",  # String "None" - should trigger rescan
            "SecretAlerts_Total": 0,
            "DependencyAlerts": 0,
            "SecretAlerts_By_Type": "{}",
            "CodeAlerts_Last_Scanned": timestamp,
            "SecretAlerts_Last_Scanned": timestamp,
            "DependencyAlerts_Last_Scanned": timestamp,
            "GHAS_Status_Updated": timestamp
        }
        result = should_scan_repository_for_GHAS_alerts(properties, "GHAS_Status_Updated", 7)
        self.assertTrue(result)

    def test_mixed_string_none_values(self):
        """Test with multiple string 'None' values."""
        recent_time = datetime.datetime.now() - datetime.timedelta(hours=1)
        timestamp = recent_time.isoformat() + "Z"
        properties = {
            "CodeAlerts": "None",
            "SecretAlerts_Total": "None",
            "DependencyAlerts": "None",
            "SecretAlerts_By_Type": "None",
            "CodeAlerts_Last_Scanned": timestamp,
            "SecretAlerts_Last_Scanned": timestamp,
            "DependencyAlerts_Last_Scanned": timestamp,
            "GHAS_Status_Updated": timestamp
        }
        result = should_scan_repository_for_GHAS_alerts(properties, "GHAS_Status_Updated", 7)
        self.assertTrue(result)


class TestParseTimestamp(unittest.TestCase):
    """Test the parse_timestamp function."""

    def test_valid_iso_timestamp(self):
        """Test parsing valid ISO timestamp."""
        timestamp = "2025-06-07T10:30:00Z"
        result = parse_timestamp(timestamp)
        self.assertIsInstance(result, datetime.datetime)
        self.assertEqual(result.year, 2025)
        self.assertEqual(result.month, 6)
        self.assertEqual(result.day, 7)

    def test_timestamp_with_microseconds(self):
        """Test parsing timestamp with microseconds."""
        timestamp = "2025-06-07T10:30:00.123456"
        result = parse_timestamp(timestamp)
        self.assertIsInstance(result, datetime.datetime)
        self.assertEqual(result.microsecond, 123456)

    def test_timestamp_with_timezone_offset(self):
        """Test parsing timestamp with timezone offset."""
        timestamp = "2025-06-07T10:30:00+02:00"
        result = parse_timestamp(timestamp)
        self.assertIsInstance(result, datetime.datetime)

    def test_timestamp_without_timezone(self):
        """Test parsing timestamp without timezone info."""
        timestamp = "2025-06-07T10:30:00"
        result = parse_timestamp(timestamp)
        self.assertIsInstance(result, datetime.datetime)

    def test_timestamp_with_whitespace(self):
        """Test parsing timestamp with leading/trailing whitespace."""
        timestamp = "  2025-06-07T10:30:00Z  "
        result = parse_timestamp(timestamp)
        self.assertIsInstance(result, datetime.datetime)

    def test_invalid_timestamp_format(self):
        """Test parsing invalid timestamp format raises ValueError."""
        timestamp = "invalid-timestamp"
        with self.assertRaises(ValueError):
            parse_timestamp(timestamp)

    def test_empty_timestamp(self):
        """Test parsing empty timestamp raises ValueError."""
        timestamp = ""
        with self.assertRaises(ValueError):
            parse_timestamp(timestamp)

    def test_none_timestamp(self):
        """Test parsing None timestamp raises ValueError."""
        timestamp = None
        with self.assertRaises(ValueError):
            parse_timestamp(timestamp)

    def test_specific_problematic_timestamp(self):
        """Test the specific timestamp format that was causing issues."""
        timestamp = "2025-05-28T20:25:25"
        result = parse_timestamp(timestamp)
        self.assertIsInstance(result, datetime.datetime)
        self.assertEqual(result.year, 2025)
        self.assertEqual(result.month, 5)
        self.assertEqual(result.day, 28)


if __name__ == '__main__':
    # Set up logging to suppress debug messages during tests
    logging.basicConfig(level=logging.WARNING)
    unittest.main()
