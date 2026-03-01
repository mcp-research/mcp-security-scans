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


class TestUnknownRuntimeSummary(unittest.TestCase):
    """Test unknown runtime repository summary functionality."""

    def test_unknown_runtime_repos_tracking(self):
        """Test that unknown runtime repositories are properly tracked and included in stats."""
        mock_repo_properties = []
        
        # Repository 1: Known runtime type (uv)
        mock_prop1 = MagicMock()
        mock_prop1.repository_name = "known_runtime_repo"
        mock_prop1.properties = []
        
        # Add GHAS scan status
        status_prop1 = MagicMock()
        status_prop1.property_name = Constants.ScanSettings.GHAS_STATUS_UPDATED
        status_prop1.value = "2024-01-01T00:00:00Z"
        mock_prop1.properties.append(status_prop1)
        
        # Add uv runtime property
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

        # Repository 2: Unknown runtime type (explicit)
        mock_prop2 = MagicMock()
        mock_prop2.repository_name = "unknown_runtime_repo1"
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

        # Repository 3: Unknown runtime type (empty string)
        mock_prop3 = MagicMock()
        mock_prop3.repository_name = "unknown_runtime_repo2"
        mock_prop3.properties = []
        
        # Add GHAS scan status
        status_prop3 = MagicMock()
        status_prop3.property_name = Constants.ScanSettings.GHAS_STATUS_UPDATED
        status_prop3.value = "2024-01-01T00:00:00Z"
        mock_prop3.properties.append(status_prop3)
        
        # Add empty runtime property (should be treated as unknown)
        runtime_prop3 = MagicMock()
        runtime_prop3.property_name = Constants.AlertProperties.MCP_SERVER_RUNTIME
        runtime_prop3.value = ""
        mock_prop3.properties.append(runtime_prop3)
        
        # Add alert properties
        for alert_prop in [Constants.AlertProperties.CODE_ALERTS, Constants.AlertProperties.SECRET_ALERTS_TOTAL, Constants.AlertProperties.DEPENDENCY_ALERTS]:
            alert_prop_mock = MagicMock()
            alert_prop_mock.property_name = alert_prop
            alert_prop_mock.value = "0"
            mock_prop3.properties.append(alert_prop_mock)
        
        mock_repo_properties.append(mock_prop3)

        # Repository 4: Another known runtime type (npx)
        mock_prop4 = MagicMock()
        mock_prop4.repository_name = "known_runtime_repo2"
        mock_prop4.properties = []
        
        # Add GHAS scan status
        status_prop4 = MagicMock()
        status_prop4.property_name = Constants.ScanSettings.GHAS_STATUS_UPDATED
        status_prop4.value = "2024-01-01T00:00:00Z"
        mock_prop4.properties.append(status_prop4)
        
        # Add npx runtime property
        runtime_prop4 = MagicMock()
        runtime_prop4.property_name = Constants.AlertProperties.MCP_SERVER_RUNTIME
        runtime_prop4.value = "npx"
        mock_prop4.properties.append(runtime_prop4)
        
        # Add alert properties
        for alert_prop in [Constants.AlertProperties.CODE_ALERTS, Constants.AlertProperties.SECRET_ALERTS_TOTAL, Constants.AlertProperties.DEPENDENCY_ALERTS]:
            alert_prop_mock = MagicMock()
            alert_prop_mock.property_name = alert_prop
            alert_prop_mock.value = "0"
            mock_prop4.properties.append(alert_prop_mock)
        
        mock_repo_properties.append(mock_prop4)

        # Generate report
        stats = generate_report(mock_repo_properties, "test-org", "test-output")

        # Verify unknown runtime repos are tracked
        unknown_repos = stats.get('unknown_runtime_repos', [])
        
        print(f"Unknown runtime repos: {unknown_repos}")
        print(f"Runtime types: {stats['runtime_types']}")

        # Should have 2 unknown runtime repos
        self.assertEqual(len(unknown_repos), 2, "Should have 2 repositories with unknown runtime")
        
        # Check that runtime distribution is correct
        expected_runtime_counts = {
            'unknown': 2,  # repo2 (explicit "unknown") + repo3 (empty "" converted to "unknown")
            'uv': 1,       # repo1
            'npx': 1,      # repo4
        }
        
        for runtime_type, expected_count in expected_runtime_counts.items():
            actual_count = stats['runtime_types'].get(runtime_type, 0)
            self.assertEqual(actual_count, expected_count, 
                           f"Runtime type '{runtime_type}' should have {expected_count} repos, got {actual_count}")

        # Verify unknown repos contain expected information
        unknown_repo_names = [repo['repo_name'] for repo in unknown_repos]
        self.assertIn('unknown_runtime_repo1', unknown_repo_names)
        self.assertIn('unknown_runtime_repo2', unknown_repo_names)
        
        # Verify each unknown repo has required fields
        for repo in unknown_repos:
            self.assertIn('name', repo)
            self.assertIn('repo_name', repo)
            self.assertIn('github_url', repo)
            self.assertIn('search_url', repo)
            self.assertTrue(repo['github_url'].startswith('https://github.com/test-org/'))
            self.assertTrue(repo['search_url'].endswith('/search?q=mcpServers'))

        print("Unknown runtime repos tracking test completed!")

    def test_unknown_runtime_in_markdown_report(self):
        """Test that unknown runtime repos are included in markdown report."""
        # Create a simple test case with unknown repos
        mock_repo_properties = []
        
        for i in range(3):
            mock_prop = MagicMock()
            mock_prop.repository_name = f"unknown_repo_{i}"
            mock_prop.properties = []
            
            # Add GHAS scan status
            status_prop = MagicMock()
            status_prop.property_name = Constants.ScanSettings.GHAS_STATUS_UPDATED
            status_prop.value = "2024-01-01T00:00:00Z"
            mock_prop.properties.append(status_prop)
            
            # Add unknown runtime property
            runtime_prop = MagicMock()
            runtime_prop.property_name = Constants.AlertProperties.MCP_SERVER_RUNTIME
            runtime_prop.value = "unknown"
            mock_prop.properties.append(runtime_prop)
            
            # Add alert properties
            for alert_prop in [Constants.AlertProperties.CODE_ALERTS, Constants.AlertProperties.SECRET_ALERTS_TOTAL, Constants.AlertProperties.DEPENDENCY_ALERTS]:
                alert_prop_mock = MagicMock()
                alert_prop_mock.property_name = alert_prop
                alert_prop_mock.value = "0"
                mock_prop.properties.append(alert_prop_mock)
            
            mock_repo_properties.append(mock_prop)

        # Generate report
        stats = generate_report(mock_repo_properties, "test-org", "test-output")
        
        # Read the generated markdown file
        md_file_path = "test-output/ghas_report_test-org_20250718.md"
        self.assertTrue(os.path.exists(md_file_path), "Markdown report should be generated")
        
        with open(md_file_path, 'r') as f:
            markdown_content = f.read()
        
        # Verify collapsible section is present
        self.assertIn('<details>', markdown_content, "Should contain collapsible details section")
        self.assertIn('<summary>Show unknown runtime repositories (3 total)</summary>', markdown_content, 
                     "Should contain summary with count")
        self.assertIn('test-org/unknown_repo_0', markdown_content, "Should contain repository names")
        self.assertIn('search?q=mcpServers', markdown_content, "Should contain search links")
        
        print("Markdown report test completed!")

    def test_truncation_of_unknown_repos_in_markdown(self):
        """Test that more than 10 unknown repos are properly truncated in markdown report."""
        # Create 15 repos with unknown runtime
        mock_repo_properties = []
        
        for i in range(15):
            mock_prop = MagicMock()
            mock_prop.repository_name = f"unknown_repo_{i:02d}"
            mock_prop.properties = []
            
            # Add GHAS scan status
            status_prop = MagicMock()
            status_prop.property_name = Constants.ScanSettings.GHAS_STATUS_UPDATED
            status_prop.value = "2024-01-01T00:00:00Z"
            mock_prop.properties.append(status_prop)
            
            # Add unknown runtime property
            runtime_prop = MagicMock()
            runtime_prop.property_name = Constants.AlertProperties.MCP_SERVER_RUNTIME
            runtime_prop.value = "unknown"
            mock_prop.properties.append(runtime_prop)
            
            # Add alert properties
            for alert_prop in [Constants.AlertProperties.CODE_ALERTS, Constants.AlertProperties.SECRET_ALERTS_TOTAL, Constants.AlertProperties.DEPENDENCY_ALERTS]:
                alert_prop_mock = MagicMock()
                alert_prop_mock.property_name = alert_prop
                alert_prop_mock.value = "0"
                mock_prop.properties.append(alert_prop_mock)
            
            mock_repo_properties.append(mock_prop)

        # Generate report
        stats = generate_report(mock_repo_properties, "test-org", "test-output")
        
        # Read the generated markdown file
        md_file_path = "test-output/ghas_report_test-org_20250718.md"
        self.assertTrue(os.path.exists(md_file_path), "Markdown report should be generated")
        
        with open(md_file_path, 'r') as f:
            markdown_content = f.read()
        
        # Verify correct truncation message
        self.assertIn('<summary>Show unknown runtime repositories (15 total)</summary>', markdown_content, 
                     "Should show total count of 15")
        self.assertIn('*Showing 10 of 15 repositories with unknown runtime type.*', markdown_content, 
                     "Should show truncation message")
        
        # Count how many repo bullet points are actually shown (look for markdown list items)
        repo_lines = [line for line in markdown_content.split('\n') if line.startswith('- [test-org/unknown_repo_')]
        self.assertEqual(len(repo_lines), 10, "Should show exactly 10 repository list items")
        
        # Check that the first 10 repos are shown (00-09)
        for i in range(10):
            repo_name = f"unknown_repo_{i:02d}"
            self.assertIn(repo_name, markdown_content, f"Should contain {repo_name}")
        
        # Check that repos 10-14 are NOT shown
        for i in range(10, 15):
            repo_name = f"unknown_repo_{i:02d}"
            self.assertNotIn(repo_name, markdown_content, f"Should NOT contain {repo_name}")
        
        print("Truncation test completed!")

    def test_no_unknown_repos_section_not_shown(self):
        """Test that when there are no unknown repos, the collapsible section is not shown."""
        # Create repos with only known runtime types
        mock_repo_properties = []
        
        runtime_types = ["uv", "npx"]
        for i, runtime_type in enumerate(runtime_types):
            mock_prop = MagicMock()
            mock_prop.repository_name = f"known_repo_{i}"
            mock_prop.properties = []
            
            # Add GHAS scan status
            status_prop = MagicMock()
            status_prop.property_name = Constants.ScanSettings.GHAS_STATUS_UPDATED
            status_prop.value = "2024-01-01T00:00:00Z"
            mock_prop.properties.append(status_prop)
            
            # Add known runtime property
            runtime_prop = MagicMock()
            runtime_prop.property_name = Constants.AlertProperties.MCP_SERVER_RUNTIME
            runtime_prop.value = runtime_type
            mock_prop.properties.append(runtime_prop)
            
            # Add alert properties
            for alert_prop in [Constants.AlertProperties.CODE_ALERTS, Constants.AlertProperties.SECRET_ALERTS_TOTAL, Constants.AlertProperties.DEPENDENCY_ALERTS]:
                alert_prop_mock = MagicMock()
                alert_prop_mock.property_name = alert_prop
                alert_prop_mock.value = "0"
                mock_prop.properties.append(alert_prop_mock)
            
            mock_repo_properties.append(mock_prop)

        # Generate report
        stats = generate_report(mock_repo_properties, "test-org", "test-output")
        
        # Verify no unknown repos
        unknown_repos = stats.get('unknown_runtime_repos', [])
        self.assertEqual(len(unknown_repos), 0, "Should have no unknown runtime repos")
        
        # Read the generated markdown file
        md_file_path = "test-output/ghas_report_test-org_20250718.md"
        self.assertTrue(os.path.exists(md_file_path), "Markdown report should be generated")
        
        with open(md_file_path, 'r') as f:
            markdown_content = f.read()
        
        # Verify no collapsible section
        self.assertNotIn('<details>', markdown_content, "Should NOT contain collapsible details section")
        self.assertNotIn('<summary>Show unknown runtime repositories', markdown_content, 
                        "Should NOT contain unknown repos summary")
        
        print("No unknown repos test completed!")


if __name__ == "__main__":
    unittest.main()