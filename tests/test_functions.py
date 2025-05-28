#!/usr/bin/env python3

import unittest
import datetime
import logging
import os
import sys

# Find the project root directory
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Add the project root directory to the Python path
sys.path.insert(0, project_root)

# Import the functions to be tested
from src.functions import should_scan_repository

# Set up logging
logging.basicConfig(level=logging.INFO)

class TestShouldScanRepository(unittest.TestCase):
    """Tests for the should_scan_repository function."""

    def test_no_timestamp(self):
        """Test when no timestamp is provided."""
        properties = {}
        self.assertTrue(should_scan_repository(properties, "GHAS_Status_Updated", 7))

    def test_testing_flag(self):
        """Test when timestamp is set to 'Testing'."""
        properties = {"GHAS_Status_Updated": "Testing"}
        self.assertTrue(should_scan_repository(properties, "GHAS_Status_Updated", 7))

    def test_old_timestamp(self):
        """Test when timestamp is older than threshold."""
        eight_days_ago = (datetime.datetime.now() - datetime.timedelta(days=8)).isoformat()
        properties = {"GHAS_Status_Updated": eight_days_ago}
        self.assertTrue(should_scan_repository(properties, "GHAS_Status_Updated", 7))

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
        self.assertFalse(should_scan_repository(properties, "GHAS_Status_Updated", 7))

    def test_invalid_timestamp(self):
        """Test when timestamp is invalid."""
        properties = {"GHAS_Status_Updated": "not-a-timestamp"}
        self.assertTrue(should_scan_repository(properties, "GHAS_Status_Updated", 7))

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
        self.assertTrue(should_scan_repository(properties, "GHAS_Status_Updated", 7))

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
        self.assertTrue(should_scan_repository(properties, "GHAS_Status_Updated", 7))

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
        self.assertFalse(should_scan_repository(properties, "GHAS_Status_Updated", 7))

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
        self.assertTrue(should_scan_repository(properties, "GHAS_Status_Updated", 7))

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
        self.assertTrue(should_scan_repository(properties, "GHAS_Status_Updated", 7))

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
        self.assertFalse(should_scan_repository(properties, "GHAS_Status_Updated", 7))

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
        self.assertTrue(should_scan_repository(properties, "GHAS_Status_Updated", 7))

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
        self.assertTrue(should_scan_repository(properties, "GHAS_Status_Updated", 7))

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
        self.assertFalse(should_scan_repository(properties, "GHAS_Status_Updated", 7))


if __name__ == "__main__":
    unittest.main()
