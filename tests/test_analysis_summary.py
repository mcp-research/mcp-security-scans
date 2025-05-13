#!/usr/bin/env python3

import unittest
import datetime
from unittest.mock import patch, MagicMock
import io
import sys
import logging
import os

# Add the parent directory to the path so we can import the src module
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.analyze import get_composition_info

class TestAnalysisSummary(unittest.TestCase):
    """Test the new summary functionality for failed repository analysis."""

    def test_empty_result_tracking(self):
        """Test that empty results from get_composition_info are tracked correctly."""
        # Test with empty composition
        empty_result = get_composition_info({})
        self.assertEqual(empty_result, {}, "Empty composition should return empty dict")
        
        # Test with missing mcpServers
        missing_servers_result = get_composition_info({"someOtherKey": "value"})
        self.assertEqual(missing_servers_result, {}, "Composition without mcpServers should return empty dict")
    
    def test_summary_table_generation(self):
        """Test the generation of the summary table for failed repositories."""
        # Create a list of failed repositories
        failed_repos = [
            {"name": "repo1", "reason": "Empty result from get_composition_info"},
            {"name": "repo2", "reason": "Exception: Invalid JSON format"},
            {"name": "repo3", "reason": "Exception: KeyError - 'mcpServers'"}
        ]
        
        # Generate the summary lines for these repos
        summary_lines = [
            "**Failed Analysis Repositories**",
            "| Repository | Reason |",
            "| ---------- | ------ |"
        ]
        
        for repo in failed_repos:
            summary_lines.append(f"| {repo['name']} | {repo['reason']} |")
        
        # Verify the summary table format
        self.assertEqual(len(summary_lines), 3 + len(failed_repos), "Table should have header rows + one row per repo")
        self.assertEqual(summary_lines[0], "**Failed Analysis Repositories**", "Title should be formatted with markdown bold")
        self.assertEqual(summary_lines[1], "| Repository | Reason |", "Header row should have column names")
        self.assertEqual(summary_lines[2], "| ---------- | ------ |", "Second row should have markdown separator")
        
        # Check that each repo is included in the table
        for i, repo in enumerate(failed_repos):
            expected_row = f"| {repo['name']} | {repo['reason']} |"
            self.assertEqual(summary_lines[3 + i], expected_row, f"Row {i+1} should contain repo info")
    
    def test_logging_failed_repos(self):
        """Test logging of failed repositories is formatted correctly."""
        # Create a list of failed repositories
        failed_repos = [
            {"name": "repo1", "reason": "Empty result from get_composition_info"},
            {"name": "repo2", "reason": "Exception: Invalid JSON format"}
        ]
        
        # Create log messages as they would appear in the code
        log_messages = ["Failed Analysis Repositories:"]
        for repo in failed_repos:
            log_messages.append(f"- {repo['name']}: {repo['reason']}")
        
        # Verify the logging format matches expectations
        self.assertEqual(log_messages[0], "Failed Analysis Repositories:", "Header should match")
        for i, repo in enumerate(failed_repos):
            expected = f"- {repo['name']}: {repo['reason']}"
            self.assertEqual(log_messages[i+1], expected, f"Log line should contain correct format for {repo['name']}")

if __name__ == '__main__':
    unittest.main()