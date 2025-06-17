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


class TestRuntimeDistributionMismatch(unittest.TestCase):
    """Tests for the runtime distribution mismatch issue."""

    def test_runtime_distribution_total_matches_scanned_repos(self):
        """Test that runtime distribution total matches scanned repositories, not all repositories."""
        # Create mock repository properties with mixed scenarios
        mock_repo_properties = []
        
        # Repository 1: Scanned for GHAS with runtime info
        mock_prop1 = MagicMock()
        mock_prop1.repository_name = "repo1"
        mock_prop1.properties = []
        
        # Add GHAS scan status property
        status_prop1 = MagicMock()
        status_prop1.property_name = Constants.ScanSettings.GHAS_STATUS_UPDATED
        status_prop1.value = "2024-01-01T00:00:00Z"
        mock_prop1.properties.append(status_prop1)
        
        # Add runtime property
        runtime_prop1 = MagicMock()
        runtime_prop1.property_name = Constants.AlertProperties.MCP_SERVER_RUNTIME
        runtime_prop1.value = "uv"
        mock_prop1.properties.append(runtime_prop1)
        
        # Add alert properties
        for alert_prop in [
            Constants.AlertProperties.CODE_ALERTS,
            Constants.AlertProperties.SECRET_ALERTS_TOTAL,
            Constants.AlertProperties.DEPENDENCY_ALERTS
        ]:
            alert_prop_mock = MagicMock()
            alert_prop_mock.property_name = alert_prop
            alert_prop_mock.value = "0"
            mock_prop1.properties.append(alert_prop_mock)
        
        mock_repo_properties.append(mock_prop1)

        # Repository 2: Scanned for GHAS with different runtime info
        mock_prop2 = MagicMock()
        mock_prop2.repository_name = "repo2"
        mock_prop2.properties = []
        
        # Add GHAS scan status property
        status_prop2 = MagicMock()
        status_prop2.property_name = Constants.ScanSettings.GHAS_STATUS_UPDATED
        status_prop2.value = "2024-01-01T00:00:00Z"
        mock_prop2.properties.append(status_prop2)
        
        # Add runtime property
        runtime_prop2 = MagicMock()
        runtime_prop2.property_name = Constants.AlertProperties.MCP_SERVER_RUNTIME
        runtime_prop2.value = "npx"
        mock_prop2.properties.append(runtime_prop2)
        
        # Add alert properties
        for alert_prop in [
            Constants.AlertProperties.CODE_ALERTS,
            Constants.AlertProperties.SECRET_ALERTS_TOTAL,
            Constants.AlertProperties.DEPENDENCY_ALERTS
        ]:
            alert_prop_mock = MagicMock()
            alert_prop_mock.property_name = alert_prop
            alert_prop_mock.value = "0"
            mock_prop2.properties.append(alert_prop_mock)
        
        mock_repo_properties.append(mock_prop2)

        # Repository 3: NOT scanned for GHAS (no GHAS_STATUS_UPDATED property)
        mock_prop3 = MagicMock()
        mock_prop3.repository_name = "repo3"
        mock_prop3.properties = []
        # This repository has no scan status or runtime info
        mock_repo_properties.append(mock_prop3)

        # Repository 4: Scanned for GHAS with unknown runtime
        mock_prop4 = MagicMock()
        mock_prop4.repository_name = "repo4"
        mock_prop4.properties = []
        
        # Add GHAS scan status property
        status_prop4 = MagicMock()
        status_prop4.property_name = Constants.ScanSettings.GHAS_STATUS_UPDATED
        status_prop4.value = "2024-01-01T00:00:00Z"
        mock_prop4.properties.append(status_prop4)
        
        # Add runtime property as unknown
        runtime_prop4 = MagicMock()
        runtime_prop4.property_name = Constants.AlertProperties.MCP_SERVER_RUNTIME
        runtime_prop4.value = "unknown"
        mock_prop4.properties.append(runtime_prop4)
        
        # Add alert properties
        for alert_prop in [
            Constants.AlertProperties.CODE_ALERTS,
            Constants.AlertProperties.SECRET_ALERTS_TOTAL,
            Constants.AlertProperties.DEPENDENCY_ALERTS
        ]:
            alert_prop_mock = MagicMock()
            alert_prop_mock.property_name = alert_prop
            alert_prop_mock.value = "0"
            mock_prop4.properties.append(alert_prop_mock)
        
        mock_repo_properties.append(mock_prop4)

        # Generate report
        stats = generate_report(mock_repo_properties, "test-org", "test-output")

        # Verify the issue exists: total repositories vs runtime distribution total
        total_repos = stats['total_repositories']  # Should be 4 (all repos)
        scanned_repos = stats['scanned_repositories']  # Should be 3 (repos with GHAS_STATUS_UPDATED)
        runtime_total = sum(stats['runtime_types'].values())  # Should be 3 (only scanned repos have runtime info)

        print(f"Total repositories: {total_repos}")
        print(f"Scanned repositories: {scanned_repos}")
        print(f"Runtime distribution total: {runtime_total}")
        print(f"Runtime types: {stats['runtime_types']}")

        # The issue: runtime_total should equal scanned_repos, not total_repos
        self.assertEqual(total_repos, 4, "Should have 4 total repositories")
        self.assertEqual(scanned_repos, 3, "Should have 3 scanned repositories")
        self.assertEqual(runtime_total, 3, "Runtime distribution should only include scanned repositories")
        
        # Verify specific runtime counts
        self.assertEqual(stats['runtime_types']['uv'], 1)
        self.assertEqual(stats['runtime_types']['npx'], 1)
        self.assertEqual(stats['runtime_types']['unknown'], 1)

        # The mismatch: runtime_total != total_repos (this is the issue)
        # But runtime_total == scanned_repos (this is correct behavior)
        self.assertNotEqual(runtime_total, total_repos, "This demonstrates the mismatch issue")
        self.assertEqual(runtime_total, scanned_repos, "Runtime total should match scanned repos")

        print("Runtime distribution mismatch test completed!")


if __name__ == "__main__":
    unittest.main()