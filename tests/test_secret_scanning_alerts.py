#!/usr/bin/env python3
import unittest
from unittest.mock import Mock, patch
import sys
import os
from src.analyze import get_secret_scanning_alerts
from githubkit.exception import RequestFailed

# Add the parent directory to the path so we can import the src module
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

class TestGetSecretScanningAlerts(unittest.TestCase):
    """Test the get_secret_scanning_alerts function."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.mock_gh = Mock()
        self.owner = "test-org"
        self.repo = "test-repo"
    
    def test_secret_scanning_alerts_with_multiple_types(self):
        """Test when repository has secret scanning alerts with different types."""
        # Create mock alert objects
        mock_alerts = [
            Mock(secret_type_display_name="GitHub Personal Access Token", secret_type="github_personal_access_token"),
            Mock(secret_type_display_name="GitHub Personal Access Token", secret_type="github_personal_access_token"),
            Mock(secret_type_display_name="AWS Access Key ID", secret_type="aws_access_key_id"),
            Mock(secret_type_display_name="Slack Token", secret_type="slack_token"),
            Mock(secret_type_display_name="Slack Token", secret_type="slack_token"),
            Mock(secret_type_display_name="Slack Token", secret_type="slack_token"),
        ]
        
        # Mock the paginate method to return our mock alerts
        self.mock_gh.rest.paginate.return_value = mock_alerts
        
        # Call the function
        result = get_secret_scanning_alerts(self.mock_gh, self.owner, self.repo)
        
        # Verify the results
        self.assertEqual(result["total"], 6)
        self.assertEqual(len(result["types"]), 3)
        self.assertEqual(result["types"]["GitHub Personal Access Token"], 2)
        self.assertEqual(result["types"]["AWS Access Key ID"], 1)
        self.assertEqual(result["types"]["Slack Token"], 3)
        
        # Verify the API was called correctly
        self.mock_gh.rest.paginate.assert_called_once_with(
            self.mock_gh.rest.secret_scanning.list_alerts_for_repo,
            owner=self.owner,
            repo=self.repo,
            state='open'
        )
    
    def test_secret_scanning_alerts_with_missing_display_name(self):
        """Test when alerts have missing secret_type_display_name."""
        # Create mock alerts with various missing fields
        mock_alerts = [
            Mock(secret_type_display_name=None, secret_type="github_pat"),
            Mock(secret_type_display_name="", secret_type="aws_key"),
            Mock(secret_type_display_name="Slack Token", secret_type="slack_token"),
            Mock(secret_type_display_name=None, secret_type=None),  # Both None
        ]
        
        self.mock_gh.rest.paginate.return_value = mock_alerts
        
        result = get_secret_scanning_alerts(self.mock_gh, self.owner, self.repo)
        
        # Verify results - should fall back to secret_type or "Unknown"
        self.assertEqual(result["total"], 4)
        self.assertEqual(result["types"]["github_pat"], 1)
        self.assertEqual(result["types"]["aws_key"], 1)
        self.assertEqual(result["types"]["Slack Token"], 1)
        self.assertEqual(result["types"]["Unknown"], 1)
    
    def test_secret_scanning_no_alerts(self):
        """Test when repository has no secret scanning alerts."""
        # Mock empty alerts list
        self.mock_gh.rest.paginate.return_value = []
        
        result = get_secret_scanning_alerts(self.mock_gh, self.owner, self.repo)
        
        # Verify results
        self.assertEqual(result["total"], 0)
        self.assertEqual(result["types"], {})
    
    def test_secret_scanning_not_enabled_404(self):
        """Test when secret scanning is not enabled (404 response)."""
        # Create mock response with 404 status
        mock_response = Mock()
        mock_response.status_code = 404
        
        # Mock the paginate method to raise RequestFailed
        self.mock_gh.rest.paginate.side_effect = RequestFailed(mock_response)
        
        result = get_secret_scanning_alerts(self.mock_gh, self.owner, self.repo)
        
        # Should return empty results without raising exception
        self.assertEqual(result["total"], 0)
        self.assertEqual(result["types"], {})
    
    @patch('src.analyze.handle_github_api_error')
    def test_secret_scanning_api_error(self, mock_handle_error):
        """Test when API returns non-404 error."""
        # Create mock response with 403 status (forbidden)
        mock_response = Mock()
        mock_response.status_code = 403
        
        # Mock the paginate method to raise RequestFailed
        self.mock_gh.rest.paginate.side_effect = RequestFailed(mock_response)
        
        result = get_secret_scanning_alerts(self.mock_gh, self.owner, self.repo)
        
        # Should return empty results
        self.assertEqual(result["total"], 0)
        self.assertEqual(result["types"], {})
        
        # Verify error handler was called
        mock_handle_error.assert_called_once()
        args = mock_handle_error.call_args[0]
        self.assertIsInstance(args[0], RequestFailed)
        self.assertIn("getting secret scanning alerts", args[1])
    
    @patch('src.analyze.logging')
    def test_secret_scanning_unexpected_error(self, mock_logging):
        """Test when an unexpected exception occurs."""
        # Mock the paginate method to raise generic exception
        self.mock_gh.rest.paginate.side_effect = Exception("Unexpected error")
        
        result = get_secret_scanning_alerts(self.mock_gh, self.owner, self.repo)
        
        # Should return empty results
        self.assertEqual(result["total"], 0)
        self.assertEqual(result["types"], {})
        
        # Verify error was logged
        mock_logging.error.assert_called_once()
        error_msg = mock_logging.error.call_args[0][0]
        self.assertIn("Unexpected error getting secret scanning alerts", error_msg)
        self.assertIn("test-org/test-repo", error_msg)
    
    def test_secret_scanning_alerts_with_missing_attributes(self):
        """Test when alerts have completely missing secret type attributes."""
        # Create mock alerts where attributes are missing entirely
        mock_alerts = [
            Mock(secret_type_display_name="GitHub Personal Access Token", secret_type="github_pat"),  # Normal alert
            Mock(),  # Alert with missing attributes
            Mock(),  # Another alert with missing attributes
        ]
        
        # Remove attributes from the Mock objects to simulate missing fields
        for alert in mock_alerts[1:]:  # Skip the first one
            if hasattr(alert, 'secret_type_display_name'):
                delattr(alert, 'secret_type_display_name')
            if hasattr(alert, 'secret_type'):
                delattr(alert, 'secret_type')
        
        self.mock_gh.rest.paginate.return_value = mock_alerts
        
        result = get_secret_scanning_alerts(self.mock_gh, self.owner, self.repo)
        
        # Verify results - should categorize missing attributes as "Unknown"
        self.assertEqual(result["total"], 3)
        self.assertEqual(len(result["types"]), 2)  # "GitHub Personal Access Token" and "Unknown"
        self.assertEqual(result["types"]["GitHub Personal Access Token"], 1)
        self.assertEqual(result["types"]["Unknown"], 2)

    def test_real_world_scenario_github_repo(self):
        """Test with data similar to a real GitHub repository with secrets."""
        # Mock alerts similar to what might be found in a real repo
        mock_alerts = [
            Mock(secret_type_display_name="GitHub Personal Access Token", secret_type="github_personal_access_token"),
            Mock(secret_type_display_name="GitHub OAuth Access Token", secret_type="github_oauth_access_token"),
            Mock(secret_type_display_name="GitHub App Installation Access Token", secret_type="github_app_installation_access_token"),
            Mock(secret_type_display_name="GitHub Personal Access Token", secret_type="github_personal_access_token"),
            Mock(secret_type_display_name="npm Access Token", secret_type="npm_access_token"),
        ]
        
        self.mock_gh.rest.paginate.return_value = mock_alerts
        
        result = get_secret_scanning_alerts(self.mock_gh, "mcp-research", "example-server")
        
        # Verify results match expected counts
        self.assertEqual(result["total"], 5)
        self.assertEqual(len(result["types"]), 4)  # 4 unique types
        self.assertEqual(result["types"]["GitHub Personal Access Token"], 2)
        self.assertEqual(result["types"]["GitHub OAuth Access Token"], 1)
        self.assertEqual(result["types"]["GitHub App Installation Access Token"], 1)
        self.assertEqual(result["types"]["npm Access Token"], 1)

if __name__ == '__main__':
    # For interactive debugging in VS Code, you can set breakpoints
    # and run with: python -m pytest src/test_analyze.py::TestGetSecretScanningAlerts::test_real_world_scenario_github_repo -s
    unittest.main()