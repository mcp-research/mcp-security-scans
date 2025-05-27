#!/usr/bin/env python3

import unittest
from unittest.mock import patch, MagicMock
import io
import os
import sys
import logging
from pathlib import Path
import requests

# Add the src directory to the path so we can import from it
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Import the function to test
from src.process_mcp_repos import load_mcp_servers_from_awesome_mcp_servers

class TestAwesomeMcpServersLoader(unittest.TestCase):
    
    @patch('requests.get')
    def test_load_mcp_servers_from_awesome_mcp_servers_success(self, mock_get):
        # Mock response with sample README content containing GitHub links
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = """
# Awesome MCP Servers

A curated list of MCP servers and projects.

## MCP Servers

- [MCP Server 1](https://github.com/user1/mcp-server-1) - Description
- [MCP Server 2](https://github.com/user2/mcp-server-2) - Description
- [Internal Link](#mcp-servers) - Not a GitHub repo
- [GitHub Profile](https://github.com/user3) - Not a repo

## Other Projects

- [Another Project](https://github.com/user4/another-project) - Description
"""
        mock_get.return_value = mock_response
        
        # Test the function
        result = load_mcp_servers_from_awesome_mcp_servers()
        
        # Verify the results
        self.assertEqual(len(result), 3)  # Should find 3 GitHub repository URLs
        self.assertIn("https://github.com/user1/mcp-server-1", result)
        self.assertIn("https://github.com/user2/mcp-server-2", result)
        self.assertIn("https://github.com/user4/another-project", result)
        self.assertNotIn("https://github.com/user3", result)  # Should not include GitHub profiles
        
    @patch('requests.get')
    def test_load_mcp_servers_from_awesome_mcp_servers_no_links(self, mock_get):
        # Mock response with README content that has no GitHub links
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = """
# Awesome MCP Servers

A curated list of MCP servers and projects.

No links to servers here.
"""
        mock_get.return_value = mock_response
        
        # Test the function
        result = load_mcp_servers_from_awesome_mcp_servers()
        
        # Verify the results
        self.assertEqual(len(result), 0)  # Should find no GitHub repository URLs
        
    @patch('requests.get')
    def test_load_mcp_servers_from_awesome_mcp_servers_request_error(self, mock_get):
        # Mock a request exception
        mock_get.side_effect = requests.exceptions.RequestException("Failed to fetch URL")
        
        # Test the function
        result = load_mcp_servers_from_awesome_mcp_servers()
        
        # Verify the results
        self.assertEqual(len(result), 0)  # Should return empty list on error


if __name__ == '__main__':
    unittest.main()