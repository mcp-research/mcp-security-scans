#!/usr/bin/env python3

import unittest
import os
import sys
from unittest.mock import patch, MagicMock, ANY

# Find the project root directory
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Add the project root directory to the Python path
sys.path.insert(0, project_root)

# Import the module to be tested
from src.process_mcp_repos import main, MCP_SERVER_LOADERS

class TestSourceCounts(unittest.TestCase):
    """Tests for source counts in the workflow summary"""
    
    @patch('src.process_mcp_repos.get_github_client')
    @patch('src.process_mcp_repos.list_all_repositories_for_org')
    @patch('src.process_mcp_repos.list_all_repository_properties_for_org')
    @patch('sys.argv', ['src.process_mcp_repos', '--num-repos=0'])
    def test_source_counts_in_summary(self, mock_list_props, mock_list_repos, mock_client):
        """Test that source counts are included in the workflow summary"""
        # Mock GitHub client and repositories
        mock_client.return_value = MagicMock()
        mock_list_repos.return_value = []
        mock_list_props.return_value = []
        
        # Setup mocks for the environment and file operations
        with patch('os.getenv') as mock_getenv, \
             patch('builtins.open', MagicMock()) as mock_open, \
             patch('src.process_mcp_repos.load_mcp_servers_from_mcp_agents_hub') as mock_load_1, \
             patch('src.process_mcp_repos.load_mcp_servers_from_awesome_mcp_servers') as mock_load_2, \
             patch('src.process_mcp_repos.clone_or_update_repo', return_value=True):
            
            # Mock environment variables
            mock_getenv.side_effect = lambda x: {
                'GH_APP_ID': 'test-app-id',
                'GH_APP_PRIVATE_KEY': 'test-key',
                'GITHUB_STEP_SUMMARY': 'test-summary-path'
            }.get(x, None)
            
            # Mock the loader functions to return specific counts
            mock_load_1.return_value = ["repo1", "repo2"]
            mock_load_2.return_value = ["repo3", "repo4", "repo5"]
            mock_load_1.__name__ = "load_mcp_servers_from_mcp_agents_hub"
            mock_load_2.__name__ = "load_mcp_servers_from_awesome_mcp_servers"
            
            # Run the main function
            main()
            
            # Check that open was called with the summary file path
            mock_open.assert_called()
            
            # Extract the summary_lines content from the write calls
            summary_content = ""
            for call in mock_open().write.call_args_list:
                summary_content += call[0][0]
            
            # Verify source counts are in the summary content
            self.assertIn("Distinct Source Counts:", summary_content)
            self.assertIn("mcp_agents_hub", summary_content)
            self.assertIn("awesome_mcp_servers", summary_content)

if __name__ == "__main__":
    unittest.main()

if __name__ == "__main__":
    unittest.main()

if __name__ == "__main__":
    unittest.main()