#!/usr/bin/env python3

import unittest
import sys
import os
import tempfile
import shutil
from pathlib import Path

# Add the parent directory to the path so we can import the src module
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.report import _write_markdown_report

class TestSecretTypesReport(unittest.TestCase):
    """Test the secret types reporting functionality."""
    
    def setUp(self):
        """Set up a temporary directory for test files."""
        self.temp_dir = Path(tempfile.mkdtemp())
        self.output_file = self.temp_dir / "test_report.md"
    
    def tearDown(self):
        """Clean up the temporary directory."""
        shutil.rmtree(self.temp_dir)
    
    def test_secret_types_displayed_when_exists(self):
        """Test that secret types are displayed in the report when they exist."""
        stats = {
            'organization': 'test-org',
            'total_repositories': 10,
            'scanned_repositories': 10,
            'repos_with_alerts': 5,
            'total_code_alerts': 10,
            'total_secret_alerts': 5,
            'total_dependency_alerts': 15,
            'total_alerts': 30,
            'code_alerts_by_severity': {'critical': 2, 'high': 3, 'medium': 3, 'low': 2},
            'dependency_alerts_by_severity': {'critical': 3, 'high': 4, 'moderate': 5, 'low': 3},
            'secret_alerts_by_type': {'GitHub PAT': 3, 'AWS Key': 2},
            'alerts_by_date': {},
            'repos_alerts': {},
            'report_date': '2023-01-01T00:00:00'
        }
        
        # Write the report
        _write_markdown_report(stats, self.output_file, None)
        
        # Read the output file
        with open(self.output_file, 'r') as f:
            content = f.read()
        
        # Verify secret types section is present with the correct details
        self.assertIn("## Secret Scanning Alerts by Type", content)
        self.assertIn("- GitHub PAT: 3", content)
        self.assertIn("- AWS Key: 2", content)
        self.assertNotIn("Secrets found but types not categorized", content)
    
    def test_empty_secret_types_with_alerts(self):
        """Test that a proper message is displayed when there are secret alerts but no types."""
        stats = {
            'organization': 'test-org',
            'total_repositories': 10,
            'scanned_repositories': 10,
            'repos_with_alerts': 5,
            'total_code_alerts': 10,
            'total_secret_alerts': 5,  # We have secret alerts
            'total_dependency_alerts': 15,
            'total_alerts': 30,
            'code_alerts_by_severity': {'critical': 2, 'high': 3, 'medium': 3, 'low': 2},
            'dependency_alerts_by_severity': {'critical': 3, 'high': 4, 'moderate': 5, 'low': 3},
            'secret_alerts_by_type': {},  # But no categorized types (empty dict)
            'alerts_by_date': {},
            'repos_alerts': {},
            'report_date': '2023-01-01T00:00:00'
        }
        
        # Write the report
        _write_markdown_report(stats, self.output_file, None)
        
        # Read the output file
        with open(self.output_file, 'r') as f:
            content = f.read()
        
        # Verify message for secrets without categorized types is present
        self.assertIn("## Secret Scanning Alerts by Type", content)
        self.assertIn("Secrets found but types not categorized", content)
    
    def test_no_secret_alerts(self):
        """Test that a proper message is displayed when there are no secret alerts."""
        stats = {
            'organization': 'test-org',
            'total_repositories': 10,
            'scanned_repositories': 10,
            'repos_with_alerts': 5,
            'total_code_alerts': 10,
            'total_secret_alerts': 0,  # No secret alerts
            'total_dependency_alerts': 15,
            'total_alerts': 25,
            'code_alerts_by_severity': {'critical': 2, 'high': 3, 'medium': 3, 'low': 2},
            'dependency_alerts_by_severity': {'critical': 3, 'high': 4, 'moderate': 5, 'low': 3},
            'secret_alerts_by_type': {},  # Empty dict is expected
            'alerts_by_date': {},
            'repos_alerts': {},
            'report_date': '2023-01-01T00:00:00'
        }
        
        # Write the report
        _write_markdown_report(stats, self.output_file, None)
        
        # Read the output file
        with open(self.output_file, 'r') as f:
            content = f.read()
        
        # Verify message for no secret alerts is present
        self.assertIn("## Secret Scanning Alerts by Type", content)
        self.assertIn("No secret scanning alerts found", content)
        self.assertNotIn("Secrets found but types not categorized", content)

if __name__ == '__main__':
    unittest.main()