import unittest
from unittest.mock import patch, MagicMock
import os
import sys
from pathlib import Path

# Get the path to the project root
project_root = Path(os.path.abspath(os.path.dirname(os.path.dirname(__file__))))
sys.path.append(str(project_root))

# Import the functions to be tested
from src.github import create_issue
from src.analyze import scan_repo_for_mcp_composition, get_composition_info

class TestIssueCreation(unittest.TestCase):
    """Test the issue creation functionality for MCP composition check failures."""
    
    @patch('src.github.GitHub')
    def test_create_issue(self, mock_github_class):
        """Test that the create_issue function works as expected."""
        # Setup mock
        mock_gh = MagicMock()
        mock_response = MagicMock()
        mock_response.status_code = 201
        mock_response.json.return_value = {"number": 123}

        mock_search_response = MagicMock()
        mock_search_response.json.return_value = {"total_count": 0}
        
        mock_gh.rest.search.issues_and_pull_requests.return_value = mock_search_response
        mock_gh.rest.issues.create.return_value = mock_response
        
        # Call function under test
        result = create_issue(
            mock_gh,
            "test-org",
            "test-repo",
            "Failed analysis: Test error",
            "This is a test issue body",
            ["analysis-failure"]
        )
        
        # Assert
        self.assertTrue(result)
        mock_gh.rest.search.issues_and_pull_requests.assert_called_once()
        mock_gh.rest.issues.create.assert_called_once_with(
            owner="test-org",
            repo="test-repo",
            title="Failed analysis: Test error",
            body="This is a test issue body",
            labels=["analysis-failure"]
        )
    
    @patch('src.github.GitHub')
    def test_create_issue_existing(self, mock_github_class):
        """Test create_issue when a similar issue already exists."""
        # Setup mock
        mock_gh = MagicMock()
        mock_search_response = MagicMock()
        mock_search_response.json.return_value = {"total_count": 1}
        
        mock_gh.rest.search.issues_and_pull_requests.return_value = mock_search_response
        
        # Call function under test
        result = create_issue(
            mock_gh,
            "test-org",
            "test-repo",
            "Failed analysis: Test error",
            "This is a test issue body",
            ["analysis-failure"]
        )
        
        # Assert
        self.assertTrue(result)  # Should return True even if issue exists
        mock_gh.rest.search.issues_and_pull_requests.assert_called_once()
        mock_gh.rest.issues.create.assert_not_called()  # Should not create a new issue
    
    def test_scan_repo_for_mcp_composition_error(self):
        """Test scan_repo_for_mcp_composition returns error details when parsing fails."""
        # Create a temporary directory with a malformed JSON file
        test_dir = Path("tmp/test_scan_error")
        test_dir.mkdir(parents=True, exist_ok=True)
        
        # Create a file with extra content before and after the JSON to test
        # that only the JSON configuration is included in error details
        file_content = '''This is documentation before the JSON.

Some more text and comments.

{"mcpServers": {"server1": {"command": "npx", "args": ["start"]},}}

And this is documentation after the JSON.
More comments here.
'''
        
        test_file = test_dir / "malformed_mcp.json"
        with open(test_file, 'w') as f:
            f.write(file_content)
        
        # Call function under test
        composition, error_details = scan_repo_for_mcp_composition(test_dir)
        
        # Cleanup
        os.remove(test_file)
        
        # Assert
        self.assertIsNone(composition)
        self.assertIsNotNone(error_details)
        self.assertIn("error_message", error_details)
        self.assertIn("filename", error_details)
        self.assertIn("json_config", error_details)
        
        # Verify that only the JSON configuration is included, not the entire file content
        json_config = error_details["json_config"]
        self.assertNotIn("This is documentation before", json_config, 
                         "Error details should not include content before JSON")
        self.assertNotIn("And this is documentation after", json_config,
                         "Error details should not include content after JSON")
        self.assertIn("mcpServers", json_config,
                      "Error details should include the JSON configuration")
        # Verify the JSON config is much shorter than the entire file
        self.assertLess(len(json_config), len(file_content),
                        "JSON config should be shorter than entire file content")
    
    def test_get_composition_info_error(self):
        """Test get_composition_info returns error details when analysis fails."""
        # Create a malformed composition dictionary
        malformed_composition = {
            "mcpServers": {}  # Empty servers object
        }
        
        # Call function under test
        info, error_details = get_composition_info(malformed_composition)
        
        # Assert
        self.assertEqual(info, {})
        self.assertIsNotNone(error_details)
        self.assertIn("error_message", error_details)
        self.assertIn("json_config", error_details)
        self.assertIn("No servers found", error_details["error_message"])
    
    @patch('src.github.GitHub')
    def test_create_issue_json_parsing_error(self, mock_github_class):
        """Test create_issue with similar JSON parsing errors at different positions."""
        # Setup mock
        mock_gh = MagicMock()
        mock_search_response = MagicMock()
        mock_search_response.json.return_value = {"total_count": 1}  # Found an existing issue
        
        mock_gh.rest.search.issues_and_pull_requests.return_value = mock_search_response
        
        # Call function with a JSON parsing error title (character position 119)
        result = create_issue(
            mock_gh,
            "test-org",
            "test-repo",
            "Failed analysis: Failed to parse MCP composition JSON: Expecting ',' delimiter: line 1 column 119 (char 118)",
            "This is a test issue body",
            ["analysis-failure"]
        )
        
        # Assert that a search was performed and no new issue was created
        self.assertTrue(result)
        mock_gh.rest.search.issues_and_pull_requests.assert_called_once()
        
        # Verify that the search query didn't include the exact character position
        call_args = mock_gh.rest.search.issues_and_pull_requests.call_args[1]
        self.assertIn('q', call_args)
        search_query = call_args['q']
        self.assertIn("Failed to parse MCP composition JSON", search_query)
        self.assertNotIn("char 118", search_query)
        self.assertNotIn("column 119", search_query)
        
        mock_gh.rest.issues.create.assert_not_called()  # Should not create a new issue

if __name__ == "__main__":
    unittest.main()