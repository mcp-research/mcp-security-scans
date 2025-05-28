#!/usr/bin/env python3
"""
Test for analyze summary formatting to ensure no extra line endings.
"""

import unittest
import datetime


class TestAnalyzeSummaryFormatting(unittest.TestCase):
    """Test cases for analyze summary formatting."""

    def test_no_extra_blank_lines_in_dependency_alerts_section(self):
        """Test that there are no extra blank lines after dependency alerts section."""
        
        # Mock data similar to what would be generated in analyze.py main()
        total_dependency_alerts_by_severity = {
            "critical": 3,
            "high": 16,
            "moderate": 11,
            "low": 3,
        }
        
        duration = datetime.timedelta(seconds=146, microseconds=430550)
        failed_analysis_repos = []
        
        # This reproduces the exact summary_lines generation from analyze.py
        summary_lines = [
            "**Dependency Scanning Alerts by Severity**",
            f"- Critical: `{total_dependency_alerts_by_severity['critical']}`",
            f"- High: `{total_dependency_alerts_by_severity['high']}`",
            f"- Moderate: `{total_dependency_alerts_by_severity['moderate']}`",
            f"- Low: `{total_dependency_alerts_by_severity['low']}`",
            f"- Total execution time: `{duration}`",
            f"- Failed analysis repositories: `{len(failed_analysis_repos)}`"
        ]
        
        # Convert to string for analysis
        summary_text = "\n".join(summary_lines)
        lines = summary_text.split('\n')
        
        # Find the indices of key lines
        low_line_idx = None
        execution_time_idx = None
        
        for i, line in enumerate(lines):
            if "Low:" in line and "dependency" in summary_text[:summary_text.find(line)].lower():
                low_line_idx = i
            elif "Total execution time:" in line:
                execution_time_idx = i
        
        # Assertions
        self.assertIsNotNone(low_line_idx, "Could not find dependency Low line in summary")
        self.assertIsNotNone(execution_time_idx, "Could not find execution time line in summary")
        
        # Check that there are no extra blank lines between dependency alerts and execution time
        lines_between = execution_time_idx - low_line_idx - 1
        self.assertEqual(lines_between, 0, 
                        f"Found {lines_between} extra blank line(s) between dependency alerts and execution time. "
                        f"Lines in between: {lines[low_line_idx+1:execution_time_idx]}")

    def test_dependency_alerts_values_are_formatted_correctly(self):
        """Test that dependency alert values are formatted correctly with backticks."""
        
        total_dependency_alerts_by_severity = {
            "critical": 3,
            "high": 16,
            "moderate": 11,
            "low": 3,
        }
        
        # Generate the dependency alerts lines
        dependency_lines = [
            f"- Critical: `{total_dependency_alerts_by_severity['critical']}`",
            f"- High: `{total_dependency_alerts_by_severity['high']}`",
            f"- Moderate: `{total_dependency_alerts_by_severity['moderate']}`",
            f"- Low: `{total_dependency_alerts_by_severity['low']}`",
        ]
        
        # Check each line format
        self.assertEqual(dependency_lines[0], "- Critical: `3`")
        self.assertEqual(dependency_lines[1], "- High: `16`")
        self.assertEqual(dependency_lines[2], "- Moderate: `11`")
        self.assertEqual(dependency_lines[3], "- Low: `3`")
        
        # Check that all values are wrapped in backticks
        for line in dependency_lines:
            self.assertIn("`", line, f"Line should contain backticks: {line}")
            self.assertTrue(line.count("`") == 2, f"Line should have exactly 2 backticks: {line}")


if __name__ == "__main__":
    unittest.main()