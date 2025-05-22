#!/usr/bin/env python3

import sys
import unittest
import logging
import json
from pathlib import Path
from unittest.mock import MagicMock, patch

# Set up logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')

# Adjust sys.path to include the project root for src imports
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

from src.analyze import get_code_scanning_alerts, get_dependency_alerts, get_secret_scanning_alerts

class TestSeverityAlerts(unittest.TestCase):
    
    def test_code_scanning_alerts_severity(self):
        """Test that code scanning alerts are categorized by severity."""
        # Create mock GitHub client and response
        mock_gh = MagicMock()
        mock_alerts = [
            MagicMock(rule=MagicMock(severity="critical")),
            MagicMock(rule=MagicMock(severity="critical")),
            MagicMock(rule=MagicMock(severity="high")),
            MagicMock(rule=MagicMock(severity="medium")),
            MagicMock(rule=MagicMock(severity="low")),
        ]
        
        # Set up the mock to return our list
        mock_gh.rest.paginate.return_value = mock_alerts
        
        # Call the function with the mock
        result = get_code_scanning_alerts(mock_gh, "owner", "repo")
        
        # Verify the results
        self.assertEqual(result["total"], 5)
        self.assertEqual(result["critical"], 2)
        self.assertEqual(result["high"], 1)
        self.assertEqual(result["medium"], 1)
        self.assertEqual(result["low"], 1)
        
    def test_dependency_alerts_severity(self):
        """Test that dependency alerts are categorized by severity."""
        # Create mock GitHub client and response
        mock_gh = MagicMock()
        mock_alerts = [
            MagicMock(security_vulnerability=MagicMock(severity="critical")),
            MagicMock(security_vulnerability=MagicMock(severity="critical")),
            MagicMock(security_vulnerability=MagicMock(severity="high")),
            MagicMock(security_vulnerability=MagicMock(severity="high")),
            MagicMock(security_vulnerability=MagicMock(severity="moderate")),
            MagicMock(security_vulnerability=MagicMock(severity="medium")),  # Test medium -> moderate mapping
            MagicMock(security_vulnerability=MagicMock(severity="low")),
        ]
        
        # Set up the mock to return our list
        mock_gh.rest.paginate.return_value = mock_alerts
        
        # Call the function with the mock
        result = get_dependency_alerts(mock_gh, "owner", "repo")
        
        # Verify the results
        self.assertEqual(result["total"], 7)
        self.assertEqual(result["critical"], 2)
        self.assertEqual(result["high"], 2)
        self.assertEqual(result["moderate"], 2)  # 1 moderate + 1 medium
        self.assertEqual(result["low"], 1)
        
    def test_code_scanning_alerts_with_additional_severity_levels(self):
        """Test that code scanning alerts with additional severity levels are categorized correctly."""
        # Create mock GitHub client and response
        mock_gh = MagicMock()
        mock_alerts = [
            MagicMock(rule=MagicMock(severity="critical")),
            MagicMock(rule=MagicMock(severity="high")),
            MagicMock(rule=MagicMock(severity="medium")),
            MagicMock(rule=MagicMock(severity="low")),
            MagicMock(rule=MagicMock(severity="warning")), # Should map to low
            MagicMock(rule=MagicMock(severity="note")),    # Should map to low
            MagicMock(rule=MagicMock(severity="error")),   # Should map to medium
        ]
        
        # Set up the mock to return our list
        mock_gh.rest.paginate.return_value = mock_alerts
        
        # Call the function with the mock
        result = get_code_scanning_alerts(mock_gh, "owner", "repo")
        
        # Verify the results
        self.assertEqual(result["total"], 7)
        self.assertEqual(result["critical"], 1)
        self.assertEqual(result["high"], 1)
        self.assertEqual(result["medium"], 2)  # medium + error
        self.assertEqual(result["low"], 3)     # low + warning + note
        
    def test_secret_scanning_alerts(self):
        """Test that secret scanning alerts are counted and categorized by type."""
        # Create mock GitHub client and response
        mock_gh = MagicMock()
        mock_alerts = [
            MagicMock(secret_type="github_personal_access_token", secret_type_display_name="GitHub Personal Access Token"),
            MagicMock(secret_type="azure_storage_account_key", secret_type_display_name="Azure Storage Account Key"),
            MagicMock(secret_type="github_personal_access_token", secret_type_display_name="GitHub Personal Access Token"),
        ]
        
        # Set up the mock to return our list
        mock_gh.rest.paginate.return_value = mock_alerts
        
        # Call the function with the mock
        result = get_secret_scanning_alerts(mock_gh, "owner", "repo")
        
        # Verify the results
        self.assertEqual(result["total"], 3)
        self.assertEqual(len(result["types"]), 2, "Should have two different secret types")
        self.assertEqual(result["types"]["GitHub Personal Access Token"], 2, "Should have 2 GitHub PAT alerts")
        self.assertEqual(result["types"]["Azure Storage Account Key"], 1, "Should have 1 Azure Storage key alert")

if __name__ == "__main__":
    unittest.main()