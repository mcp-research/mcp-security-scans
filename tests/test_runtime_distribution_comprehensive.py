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


class TestRuntimeDistributionComprehensive(unittest.TestCase):
    """Comprehensive tests for runtime distribution tracking edge cases."""

    def test_runtime_distribution_handles_all_scenarios(self):
        """Test that runtime distribution properly handles various scanning scenarios."""
        mock_repo_properties = []
        
        # Scenario 1: Repository scanned for GHAS recently with runtime info
        mock_prop1 = MagicMock()
        mock_prop1.repository_name = "repo1_ghas_with_runtime"
        mock_prop1.properties = []
        
        # Add GHAS scan status
        status_prop1 = MagicMock()
        status_prop1.property_name = Constants.ScanSettings.GHAS_STATUS_UPDATED
        status_prop1.value = "2024-01-01T00:00:00Z"
        mock_prop1.properties.append(status_prop1)
        
        # Add runtime property from previous MCP composition scan
        runtime_prop1 = MagicMock()
        runtime_prop1.property_name = Constants.AlertProperties.MCP_SERVER_RUNTIME
        runtime_prop1.value = "uv"
        mock_prop1.properties.append(runtime_prop1)
        
        # Add alert properties
        for alert_prop in [Constants.AlertProperties.CODE_ALERTS, Constants.AlertProperties.SECRET_ALERTS_TOTAL, Constants.AlertProperties.DEPENDENCY_ALERTS]:
            alert_prop_mock = MagicMock()
            alert_prop_mock.property_name = alert_prop
            alert_prop_mock.value = "0"
            mock_prop1.properties.append(alert_prop_mock)
        
        mock_repo_properties.append(mock_prop1)

        # Scenario 2: Repository scanned for GHAS with unknown runtime (no MCP composition found)
        mock_prop2 = MagicMock()
        mock_prop2.repository_name = "repo2_ghas_unknown_runtime"
        mock_prop2.properties = []
        
        # Add GHAS scan status
        status_prop2 = MagicMock()
        status_prop2.property_name = Constants.ScanSettings.GHAS_STATUS_UPDATED
        status_prop2.value = "2024-01-01T00:00:00Z"
        mock_prop2.properties.append(status_prop2)
        
        # Add unknown runtime property
        runtime_prop2 = MagicMock()
        runtime_prop2.property_name = Constants.AlertProperties.MCP_SERVER_RUNTIME
        runtime_prop2.value = "unknown"
        mock_prop2.properties.append(runtime_prop2)
        
        # Add alert properties
        for alert_prop in [Constants.AlertProperties.CODE_ALERTS, Constants.AlertProperties.SECRET_ALERTS_TOTAL, Constants.AlertProperties.DEPENDENCY_ALERTS]:
            alert_prop_mock = MagicMock()
            alert_prop_mock.property_name = alert_prop
            alert_prop_mock.value = "0"
            mock_prop2.properties.append(alert_prop_mock)
        
        mock_repo_properties.append(mock_prop2)

        # Scenario 3: Repository has old runtime info but was NOT scanned for GHAS recently
        # (this could happen if it was scanned before but now doesn't meet GHAS scan criteria)
        mock_prop3 = MagicMock()
        mock_prop3.repository_name = "repo3_old_runtime_no_recent_ghas"
        mock_prop3.properties = []
        
        # No GHAS scan status property - this repo was never scanned for GHAS or scan status was removed
        
        # But has old runtime property from previous scans
        runtime_prop3 = MagicMock()
        runtime_prop3.property_name = Constants.AlertProperties.MCP_SERVER_RUNTIME
        runtime_prop3.value = "npx"
        mock_prop3.properties.append(runtime_prop3)
        
        mock_repo_properties.append(mock_prop3)

        # Scenario 4: Repository with no properties at all (never scanned)
        mock_prop4 = MagicMock()
        mock_prop4.repository_name = "repo4_never_scanned"
        mock_prop4.properties = []
        mock_repo_properties.append(mock_prop4)

        # Scenario 5: Repository with empty runtime value
        mock_prop5 = MagicMock()
        mock_prop5.repository_name = "repo5_ghas_empty_runtime"
        mock_prop5.properties = []
        
        # Add GHAS scan status
        status_prop5 = MagicMock()
        status_prop5.property_name = Constants.ScanSettings.GHAS_STATUS_UPDATED
        status_prop5.value = "2024-01-01T00:00:00Z"
        mock_prop5.properties.append(status_prop5)
        
        # Add empty runtime property
        runtime_prop5 = MagicMock()
        runtime_prop5.property_name = Constants.AlertProperties.MCP_SERVER_RUNTIME
        runtime_prop5.value = ""
        mock_prop5.properties.append(runtime_prop5)
        
        # Add alert properties
        for alert_prop in [Constants.AlertProperties.CODE_ALERTS, Constants.AlertProperties.SECRET_ALERTS_TOTAL, Constants.AlertProperties.DEPENDENCY_ALERTS]:
            alert_prop_mock = MagicMock()
            alert_prop_mock.property_name = alert_prop
            alert_prop_mock.value = "0"
            mock_prop5.properties.append(alert_prop_mock)
        
        mock_repo_properties.append(mock_prop5)

        # Generate report
        stats = generate_report(mock_repo_properties, "test-org", "test-output")

        # Analyze results
        total_repos = stats['total_repositories']  # Should be 5 (all repos)
        scanned_repos = stats['scanned_repositories']  # Should be 3 (repos 1, 2, 5 have GHAS_STATUS_UPDATED)
        runtime_total = sum(stats['runtime_types'].values())

        print(f"Total repositories: {total_repos}")
        print(f"Scanned repositories: {scanned_repos}")
        print(f"Runtime distribution total: {runtime_total}")
        print(f"Runtime types: {stats['runtime_types']}")

        # Verify basic counts
        self.assertEqual(total_repos, 5, "Should have 5 total repositories")
        self.assertEqual(scanned_repos, 3, "Should have 3 scanned repositories (with GHAS_STATUS_UPDATED)")
        
        # Key insight: Only repositories that are marked as scanned (have GHAS_STATUS_UPDATED) 
        # should be included in runtime distribution, even if they have runtime properties
        self.assertEqual(runtime_total, scanned_repos, "Runtime total should match scanned repos")
        
        # Verify specific runtime counts - only from scanned repos
        expected_runtime_counts = {
            'uv': 1,      # repo1
            'unknown': 2, # repo2 (explicit "unknown") + repo5 (empty "" converted to "unknown")
            # repo3 has 'npx' but no GHAS_STATUS_UPDATED, so it shouldn't be counted
            # repo4 has no properties, so not counted
        }
        
        for runtime_type, expected_count in expected_runtime_counts.items():
            actual_count = stats['runtime_types'].get(runtime_type, 0)
            self.assertEqual(actual_count, expected_count, 
                           f"Runtime type '{runtime_type}' should have {expected_count} repos, got {actual_count}")

        print("Comprehensive runtime distribution test completed!")
        
        # This test should reveal any issues with how runtime information is tracked
        # relative to scanning status


if __name__ == "__main__":
    unittest.main()