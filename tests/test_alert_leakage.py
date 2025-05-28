#!/usr/bin/env python3

import unittest
import sys
import os
import tempfile
import shutil
import json
from pathlib import Path
from unittest.mock import patch

# Add the parent directory to the path so we can import the src module
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.report import generate_report  # noqa: E402
from src.constants import Constants  # noqa: E402


class MockRepositoryProperty:
    """Mock class for repository properties."""
    def __init__(self, property_name, value):
        self.property_name = property_name
        self.value = value


class MockRepositoryPropertyObject:
    """Mock class for repository property object."""
    def __init__(self, repository_name, properties):
        self.repository_name = repository_name
        self.properties = [MockRepositoryProperty(name, value) for name, value in properties.items()]


class TestAlertLeakage(unittest.TestCase):
    """Test that alert numbers are not leaked in CI environment."""

    def setUp(self):
        """Set up a temporary directory for test files."""
        self.temp_dir = Path(tempfile.mkdtemp())

    def tearDown(self):
        """Clean up the temporary directory."""
        shutil.rmtree(self.temp_dir)

    def test_repos_alerts_included_in_non_ci_environment(self):
        """Test that repos_alerts are included in JSON when not in CI."""
        # Create mock repository properties with alerts
        repo_properties = [
            MockRepositoryPropertyObject("test-repo-1", {
                Constants.ScanSettings.GHAS_STATUS_UPDATED: "2023-01-01T00:00:00Z",
                Constants.AlertProperties.CODE_ALERTS: "5",
                Constants.AlertProperties.SECRET_ALERTS_TOTAL: "3",
                Constants.AlertProperties.DEPENDENCY_ALERTS: "2",
                Constants.AlertProperties.CODE_ALERTS_CRITICAL: "1",
                Constants.AlertProperties.CODE_ALERTS_HIGH: "2",
                Constants.AlertProperties.CODE_ALERTS_MEDIUM: "1",
                Constants.AlertProperties.CODE_ALERTS_LOW: "1",
                Constants.AlertProperties.DEPENDENCY_ALERTS_CRITICAL: "1",
                Constants.AlertProperties.DEPENDENCY_ALERTS_HIGH: "1",
                Constants.AlertProperties.DEPENDENCY_ALERTS_MODERATE: "0",
                Constants.AlertProperties.DEPENDENCY_ALERTS_LOW: "0",
            })
        ]

        # Ensure CI environment variable is not set
        with patch.dict(os.environ, {}, clear=True):
            # Generate report
            stats = generate_report(repo_properties, "test-org", str(self.temp_dir))

            # Verify repos_alerts is included
            self.assertIn('repos_alerts', stats)
            self.assertIn('test-org/test-repo-1', stats['repos_alerts'])
            self.assertEqual(stats['repos_alerts']['test-org/test-repo-1']['code'], 5)
            self.assertEqual(stats['repos_alerts']['test-org/test-repo-1']['secret'], 3)
            self.assertEqual(stats['repos_alerts']['test-org/test-repo-1']['dependency'], 2)

            # Check that JSON file contains repos_alerts
            # The file should exist since we just generated it
            json_files = list(self.temp_dir.glob("ghas_report_test-org_*.json"))
            self.assertEqual(len(json_files), 1)

            with open(json_files[0], 'r') as f:
                json_data = json.load(f)

            self.assertIn('repos_alerts', json_data)
            self.assertIn('test-org/test-repo-1', json_data['repos_alerts'])

    def test_repos_alerts_excluded_in_ci_environment(self):
        """Test that repos_alerts are excluded from JSON when in CI."""
        # Create mock repository properties with alerts
        repo_properties = [
            MockRepositoryPropertyObject("test-repo-1", {
                Constants.ScanSettings.GHAS_STATUS_UPDATED: "2023-01-01T00:00:00Z",
                Constants.AlertProperties.CODE_ALERTS: "5",
                Constants.AlertProperties.SECRET_ALERTS_TOTAL: "3",
                Constants.AlertProperties.DEPENDENCY_ALERTS: "2",
                Constants.AlertProperties.CODE_ALERTS_CRITICAL: "1",
                Constants.AlertProperties.CODE_ALERTS_HIGH: "2",
                Constants.AlertProperties.CODE_ALERTS_MEDIUM: "1",
                Constants.AlertProperties.CODE_ALERTS_LOW: "1",
                Constants.AlertProperties.DEPENDENCY_ALERTS_CRITICAL: "1",
                Constants.AlertProperties.DEPENDENCY_ALERTS_HIGH: "1",
                Constants.AlertProperties.DEPENDENCY_ALERTS_MODERATE: "0",
                Constants.AlertProperties.DEPENDENCY_ALERTS_LOW: "0",
            })
        ]

        # Set CI environment variable
        with patch.dict(os.environ, {'CI': 'true'}):
            # Generate report
            stats = generate_report(repo_properties, "test-org", str(self.temp_dir))

            # Verify repos_alerts is still in stats (for internal processing)
            # but should be excluded from JSON output
            self.assertIn('repos_alerts', stats)

            # Check that JSON file does NOT contain repos_alerts
            json_files = list(self.temp_dir.glob("ghas_report_test-org_*.json"))
            self.assertEqual(len(json_files), 1)

            with open(json_files[0], 'r') as f:
                json_data = json.load(f)

            # repos_alerts should be excluded from JSON when in CI
            self.assertNotIn('repos_alerts', json_data)

            # But other stats should still be present
            self.assertIn('total_code_alerts', json_data)
            self.assertIn('total_secret_alerts', json_data)
            self.assertIn('total_dependency_alerts', json_data)
            self.assertEqual(json_data['total_code_alerts'], 5)
            self.assertEqual(json_data['total_secret_alerts'], 3)
            self.assertEqual(json_data['total_dependency_alerts'], 2)


if __name__ == '__main__':
    unittest.main()
