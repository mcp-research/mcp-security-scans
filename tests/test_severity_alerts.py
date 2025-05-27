#!/usr/bin/env python3

import os
import sys
import unittest
from unittest.mock import MagicMock, Mock

# Add src directory to path for imports
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

from src.analyze import get_code_scanning_alerts, get_dependency_alerts, get_secret_scanning_alerts


class TestSeverityAlerts(unittest.TestCase):
    """Test the retrieval and classification of security alerts by severity."""

    def test_code_scanning_alerts(self):
        """Test that code scanning alerts are correctly counted by severity."""
        # Mock GitHub client and response
        mock_gh = MagicMock()
        mock_alerts = [
            Mock(rule=Mock(severity="critical")),
            Mock(rule=Mock(severity="high")),
            Mock(rule=Mock(severity="high")),
            Mock(rule=Mock(severity="medium")),
        ]

        mock_gh.rest.paginate.return_value = mock_alerts

        # Test the function
        result = get_code_scanning_alerts(mock_gh, "owner", "repo")

        # Verify the results
        self.assertEqual(result["total"], 4, "Should have 4 total alerts")
        self.assertEqual(result["critical"], 1, "Should have 1 critical severity alert")
        self.assertEqual(result["high"], 2, "Should have 2 high severity alerts")
        self.assertEqual(result["medium"], 1, "Should have 1 medium severity alert")
        self.assertEqual(result["low"], 0, "Should have no low severity alerts")

    def test_code_scanning_alerts_empty(self):
        """Test handling of empty code scanning alerts."""
        mock_gh = MagicMock()
        mock_gh.rest.paginate.return_value = []

        result = get_code_scanning_alerts(mock_gh, "owner", "repo")

        self.assertEqual(result["total"], 0, "Should have no alerts")
        self.assertEqual(result["critical"], 0, "Should have no critical alerts")
        self.assertEqual(result["high"], 0, "Should have no high alerts")
        self.assertEqual(result["medium"], 0, "Should have no medium alerts")
        self.assertEqual(result["low"], 0, "Should have no low alerts")

    def test_dependency_alerts(self):
        """Test that dependency alerts are correctly counted by severity."""
        # Mock GitHub client and alerts
        mock_gh = MagicMock()
        mock_alerts = [
            Mock(security_advisory=Mock(severity="CRITICAL")),
            Mock(security_advisory=Mock(severity="HIGH")),
            Mock(security_advisory=Mock(severity="HIGH")),
        ]

        mock_gh.rest.dependabot.list_alerts_for_repo.return_value.parsed_data = (
            mock_alerts
        )

        # Test the function
        result = get_dependency_alerts(mock_gh, "owner", "repo")

        # Verify results
        self.assertEqual(result["total"], 3, "Should have 3 total alerts")
        self.assertEqual(result["critical"], 1, "Should have 1 critical severity alert")
        self.assertEqual(result["high"], 2, "Should have 2 high severity alerts")
        self.assertEqual(result["medium"], 0, "Should have no medium severity alerts")
        self.assertEqual(result["low"], 0, "Should have no low severity alerts")

    def test_secret_scanning_alerts(self):
        """Test that secret scanning alerts are correctly counted by type."""
        mock_gh = MagicMock()
        mock_alerts = [
            Mock(secret_type="GitHub Personal Access Token"),
            Mock(secret_type="GitHub Personal Access Token"),
            Mock(secret_type="Azure Storage Account Key"),
        ]

        mock_gh.rest.secret_scanning.list_alerts_for_repo.return_value.parsed_data = (
            mock_alerts
        )

        # Test the function with mocked alerts
        result = get_secret_scanning_alerts(mock_gh, "owner", "repo")

        types = result.get("types", {})
        self.assertEqual(result["total"], 3, "Should have 3 total alerts")
        self.assertEqual(len(types), 2, "Should have two different secret types")
        self.assertEqual(
            types.get("GitHub Personal Access Token", 0),
            2,
            "Should have 2 GitHub PAT alerts",
        )
        self.assertEqual(
            types.get("Azure Storage Account Key", 0),
            1,
            "Should have 1 Azure Storage key alert",
        )


if __name__ == "__main__":
    unittest.main()
