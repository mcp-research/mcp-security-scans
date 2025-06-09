#!/usr/bin/env python3

import unittest
import sys
import os
from unittest.mock import Mock, patch
import tempfile
import json

# Add the parent directory to the path so we can import the src module
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.report import generate_report
from src.constants import Constants


class MockRepoProperty:
    """Mock repository property for testing."""
    def __init__(self, repo_name, properties):
        self.repository_name = repo_name
        self.properties = [MockProperty(name, value) for name, value in properties.items()]


class MockProperty:
    """Mock property for testing."""
    def __init__(self, name, value):
        self.property_name = name
        self.value = value


class TestSecretTypesDiagnostic(unittest.TestCase):
    """Test the secret types diagnostic functionality with mock data."""
    
    def test_repos_with_secret_alerts_but_no_types(self):
        """Test scenario where repos have secret alerts but no categorized types."""
        
        # Create mock repository data
        mock_repos = [
            MockRepoProperty("repo1", {
                Constants.ScanSettings.GHAS_STATUS_UPDATED: "2023-01-01T00:00:00",
                Constants.AlertProperties.SECRET_ALERTS_TOTAL: "5",
                Constants.AlertProperties.SECRET_ALERTS_BY_TYPE: "{}",  # Empty JSON
                Constants.AlertProperties.CODE_ALERTS: "0",
                Constants.AlertProperties.DEPENDENCY_ALERTS: "0",
            }),
            MockRepoProperty("repo2", {
                Constants.ScanSettings.GHAS_STATUS_UPDATED: "2023-01-01T00:00:00", 
                Constants.AlertProperties.SECRET_ALERTS_TOTAL: "3",
                # Missing SECRET_ALERTS_BY_TYPE property entirely
                Constants.AlertProperties.CODE_ALERTS: "0",
                Constants.AlertProperties.DEPENDENCY_ALERTS: "0",
            }),
            MockRepoProperty("repo3", {
                Constants.ScanSettings.GHAS_STATUS_UPDATED: "2023-01-01T00:00:00",
                Constants.AlertProperties.SECRET_ALERTS_TOTAL: "2",
                Constants.AlertProperties.SECRET_ALERTS_BY_TYPE: '{"GitHub PAT": 2}',  # Properly categorized
                Constants.AlertProperties.CODE_ALERTS: "0",
                Constants.AlertProperties.DEPENDENCY_ALERTS: "0",
            }),
            MockRepoProperty("repo4", {
                Constants.ScanSettings.GHAS_STATUS_UPDATED: "2023-01-01T00:00:00",
                Constants.AlertProperties.SECRET_ALERTS_TOTAL: "0",  # No secret alerts
                Constants.AlertProperties.SECRET_ALERTS_BY_TYPE: "{}",
                Constants.AlertProperties.CODE_ALERTS: "0",
                Constants.AlertProperties.DEPENDENCY_ALERTS: "0",
            }),
        ]
        
        # Generate report
        with tempfile.TemporaryDirectory() as temp_dir:
            stats = generate_report(mock_repos, "test-org", temp_dir)
            
            # Verify stats
            self.assertEqual(stats['total_repositories'], 4)
            self.assertEqual(stats['scanned_repositories'], 4)
            self.assertEqual(stats['total_secret_alerts'], 10)  # 5 + 3 + 2 + 0
            
            # Check secret types breakdown
            secret_types = stats['secret_alerts_by_type']
            self.assertEqual(len(secret_types), 1)  # Only one type categorized
            self.assertEqual(secret_types.get('GitHub PAT'), 2)
            
            # This means 8 out of 10 secret alerts are not categorized (repo1: 5, repo2: 3)
            total_categorized = sum(secret_types.values())
            total_uncategorized = stats['total_secret_alerts'] - total_categorized
            self.assertEqual(total_uncategorized, 8)
            
    def test_empty_secret_types_json_parsing(self):
        """Test different variations of empty/invalid secret types JSON."""
        
        mock_repos = [
            MockRepoProperty("repo_empty_json", {
                Constants.ScanSettings.GHAS_STATUS_UPDATED: "2023-01-01T00:00:00",
                Constants.AlertProperties.SECRET_ALERTS_TOTAL: "3",
                Constants.AlertProperties.SECRET_ALERTS_BY_TYPE: "{}",  # Empty JSON object
            }),
            MockRepoProperty("repo_null_json", {
                Constants.ScanSettings.GHAS_STATUS_UPDATED: "2023-01-01T00:00:00",
                Constants.AlertProperties.SECRET_ALERTS_TOTAL: "2",
                Constants.AlertProperties.SECRET_ALERTS_BY_TYPE: "",  # Empty string
            }),
            MockRepoProperty("repo_invalid_json", {
                Constants.ScanSettings.GHAS_STATUS_UPDATED: "2023-01-01T00:00:00",
                Constants.AlertProperties.SECRET_ALERTS_TOTAL: "1", 
                Constants.AlertProperties.SECRET_ALERTS_BY_TYPE: "invalid json",  # Invalid JSON
            }),
        ]
        
        with tempfile.TemporaryDirectory() as temp_dir:
            stats = generate_report(mock_repos, "test-org", temp_dir)
            
            # Verify that all secret alerts are uncategorized
            self.assertEqual(stats['total_secret_alerts'], 6)  # 3 + 2 + 1
            self.assertEqual(len(stats['secret_alerts_by_type']), 0)  # No types categorized
            
    def test_successful_secret_types_categorization(self):
        """Test repositories with properly categorized secret types."""
        
        mock_repos = [
            MockRepoProperty("repo1", {
                Constants.ScanSettings.GHAS_STATUS_UPDATED: "2023-01-01T00:00:00",
                Constants.AlertProperties.SECRET_ALERTS_TOTAL: "5",
                Constants.AlertProperties.SECRET_ALERTS_BY_TYPE: '{"GitHub PAT": 3, "AWS Key": 2}',
            }),
            MockRepoProperty("repo2", {
                Constants.ScanSettings.GHAS_STATUS_UPDATED: "2023-01-01T00:00:00",
                Constants.AlertProperties.SECRET_ALERTS_TOTAL: "2",
                Constants.AlertProperties.SECRET_ALERTS_BY_TYPE: '{"Slack Token": 2}',
            }),
        ]
        
        with tempfile.TemporaryDirectory() as temp_dir:
            stats = generate_report(mock_repos, "test-org", temp_dir)
            
            # Verify all alerts are categorized
            self.assertEqual(stats['total_secret_alerts'], 7)  # 5 + 2
            
            secret_types = stats['secret_alerts_by_type']
            self.assertEqual(len(secret_types), 3)
            self.assertEqual(secret_types['GitHub PAT'], 3)
            self.assertEqual(secret_types['AWS Key'], 2)
            self.assertEqual(secret_types['Slack Token'], 2)
            
            # Verify total categorized equals total alerts
            total_categorized = sum(secret_types.values())
            self.assertEqual(total_categorized, stats['total_secret_alerts'])


if __name__ == '__main__':
    unittest.main()