#!/usr/bin/env python3

import unittest
import sys
import os
from unittest.mock import MagicMock

# Find the project root directory
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Add the project root directory to the Python path
sys.path.insert(0, project_root)

# Import the functions to be tested
from src.report import generate_report
from src.constants import Constants


class TestRuntimeTracking(unittest.TestCase):
    """Tests for MCP server runtime tracking functionality."""

    def test_runtime_tracking_in_report(self):
        """Test that runtime types are correctly tracked and reported."""
        # Create mock repository properties with runtime information
        mock_repo_properties = []
        
        # Create a mock property object for each repository
        for i, (repo_name, runtime) in enumerate([
            ("repo1", "uv"),
            ("repo2", "npx"),
            ("repo3", "uv"),
            ("repo4", "unknown"),
            ("repo5", "npx")
        ]):
            mock_prop = MagicMock()
            mock_prop.repository_name = repo_name
            mock_prop.properties = []
            
            # Add runtime property
            runtime_prop = MagicMock()
            runtime_prop.property_name = Constants.AlertProperties.MCP_SERVER_RUNTIME
            runtime_prop.value = runtime
            mock_prop.properties.append(runtime_prop)
            
            # Add scan status property
            status_prop = MagicMock()
            status_prop.property_name = Constants.ScanSettings.GHAS_STATUS_UPDATED
            status_prop.value = "2024-01-01T00:00:00Z"
            mock_prop.properties.append(status_prop)
            
            # Add zero alert properties to keep it simple
            for alert_prop in [
                Constants.AlertProperties.CODE_ALERTS,
                Constants.AlertProperties.SECRET_ALERTS_TOTAL,
                Constants.AlertProperties.DEPENDENCY_ALERTS
            ]:
                alert_prop_mock = MagicMock()
                alert_prop_mock.property_name = alert_prop
                alert_prop_mock.value = "0"
                mock_prop.properties.append(alert_prop_mock)
            
            mock_repo_properties.append(mock_prop)

        # Generate report
        stats = generate_report(mock_repo_properties, "test-org", "test-output")

        # Verify runtime tracking
        self.assertIn('runtime_types', stats)
        self.assertEqual(stats['runtime_types']['uv'], 2)
        self.assertEqual(stats['runtime_types']['npx'], 2)
        self.assertEqual(stats['runtime_types']['unknown'], 1)
        self.assertEqual(len(stats['runtime_types']), 3)

        print("Runtime tracking test passed!")
        print(f"Runtime types found: {stats['runtime_types']}")

    def test_runtime_tracking_empty_values(self):
        """Test that empty or missing runtime values are handled correctly."""
        # Create mock repository properties with missing runtime information
        mock_repo_properties = []
        
        mock_prop = MagicMock()
        mock_prop.repository_name = "repo1"
        mock_prop.properties = []
        
        # Add scan status property but no runtime property
        status_prop = MagicMock()
        status_prop.property_name = Constants.ScanSettings.GHAS_STATUS_UPDATED
        status_prop.value = "2024-01-01T00:00:00Z"
        mock_prop.properties.append(status_prop)
        
        # Add zero alert properties
        for alert_prop in [
            Constants.AlertProperties.CODE_ALERTS,
            Constants.AlertProperties.SECRET_ALERTS_TOTAL,
            Constants.AlertProperties.DEPENDENCY_ALERTS
        ]:
            alert_prop_mock = MagicMock()
            alert_prop_mock.property_name = alert_prop
            alert_prop_mock.value = "0"
            mock_prop.properties.append(alert_prop_mock)
        
        mock_repo_properties.append(mock_prop)

        # Generate report
        stats = generate_report(mock_repo_properties, "test-org", "test-output")

        # Verify that unknown is used for missing runtime
        self.assertIn('runtime_types', stats)
        self.assertEqual(stats['runtime_types']['unknown'], 1)

        print("Empty runtime values test passed!")


if __name__ == "__main__":
    unittest.main()
