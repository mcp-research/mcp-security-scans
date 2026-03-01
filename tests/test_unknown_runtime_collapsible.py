#!/usr/bin/env python3

import datetime
import os
import re
import sys
import unittest
from unittest.mock import MagicMock

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from src.report import generate_report
from src.constants import Constants


def _make_repo(name, scan_date, runtime):
    """Helper to build a mock repo property object."""
    mock_prop = MagicMock()
    mock_prop.repository_name = name
    mock_prop.properties = []

    status_prop = MagicMock()
    status_prop.property_name = Constants.ScanSettings.GHAS_STATUS_UPDATED
    status_prop.value = scan_date
    mock_prop.properties.append(status_prop)

    runtime_prop = MagicMock()
    runtime_prop.property_name = Constants.AlertProperties.MCP_SERVER_RUNTIME
    runtime_prop.value = runtime
    mock_prop.properties.append(runtime_prop)

    for alert_prop_name in [
        Constants.AlertProperties.CODE_ALERTS,
        Constants.AlertProperties.SECRET_ALERTS_TOTAL,
        Constants.AlertProperties.DEPENDENCY_ALERTS,
    ]:
        alert_mock = MagicMock()
        alert_mock.property_name = alert_prop_name
        alert_mock.value = "0"
        mock_prop.properties.append(alert_mock)

    return mock_prop


class TestUnknownRuntimeCollapsible(unittest.TestCase):
    """Tests for the collapsible 'unknown runtime' section in the markdown report."""

    def setUp(self):
        self.output_dir = "test-output"

    def _generate(self, repos):
        return generate_report(repos, "test-org", self.output_dir)

    def _read_md(self):
        date_str = datetime.datetime.now().strftime('%Y%m%d')
        path = f"{self.output_dir}/ghas_report_test-org_{date_str}.md"
        with open(path) as f:
            return f.read()

    def test_unknown_runtime_repos_tracked_in_stats(self):
        """Stats should contain the list of repos with unknown runtime."""
        repos = [
            _make_repo("repoA", "2024-06-01T00:00:00Z", "unknown"),
            _make_repo("repoB", "2024-06-02T00:00:00Z", "npx"),
            _make_repo("repoC", "2024-06-03T00:00:00Z", "unknown"),
        ]
        stats = self._generate(repos)

        unknown_repos = stats.get('unknown_runtime_repos', [])
        self.assertEqual(len(unknown_repos), 2)
        names = {r['name'] for r in unknown_repos}
        self.assertIn("test-org/repoA", names)
        self.assertIn("test-org/repoC", names)
        self.assertNotIn("test-org/repoB", names)

    def test_known_runtime_not_in_unknown_list(self):
        """Repos with known runtime types should not appear in unknown_runtime_repos."""
        repos = [
            _make_repo("repoX", "2024-06-01T00:00:00Z", "uv"),
            _make_repo("repoY", "2024-06-01T00:00:00Z", "npx"),
        ]
        stats = self._generate(repos)
        self.assertEqual(stats.get('unknown_runtime_repos', []), [])

    def test_collapsible_section_in_markdown(self):
        """Markdown report should contain a <details> collapsible section for unknown repos."""
        repos = [
            _make_repo("repoA", "2024-06-01T00:00:00Z", "unknown"),
            _make_repo("repoB", "2024-06-02T00:00:00Z", "npx"),
        ]
        self._generate(repos)
        content = self._read_md()

        self.assertIn("<details>", content)
        self.assertIn("<summary>Latest 10 repositories with unknown runtime</summary>", content)
        self.assertIn("test-org/repoA", content)
        self.assertNotIn("test-org/repoB", content)

    def test_collapsible_section_absent_when_no_unknown(self):
        """No collapsible section should appear when there are no unknown repos."""
        repos = [
            _make_repo("repoX", "2024-06-01T00:00:00Z", "uv"),
        ]
        self._generate(repos)
        content = self._read_md()

        self.assertNotIn("<details>", content)

    def test_collapsible_shows_at_most_10_repos(self):
        """Collapsible section should display at most 10 repos."""
        repos = [
            _make_repo(f"repo{i}", f"2024-06-{i:02d}T00:00:00Z", "unknown")
            for i in range(1, 16)
        ]
        self._generate(repos)
        content = self._read_md()

        # Count table rows inside the details block (each row contains a repo name)
        details_match = re.search(r"<details>(.*?)</details>", content, re.DOTALL)
        self.assertIsNotNone(details_match)
        rows = re.findall(r"\| test-org/repo\d+", details_match.group(1))
        self.assertEqual(len(rows), 10)

    def test_collapsible_sorted_by_latest_scan_date(self):
        """The collapsible section should list repos sorted by most recent scan date first."""
        repos = [
            _make_repo("repoOld", "2024-01-01T00:00:00Z", "unknown"),
            _make_repo("repoNew", "2024-12-31T00:00:00Z", "unknown"),
            _make_repo("repoMid", "2024-06-15T00:00:00Z", "unknown"),
        ]
        self._generate(repos)
        content = self._read_md()

        details_match = re.search(r"<details>(.*?)</details>", content, re.DOTALL)
        self.assertIsNotNone(details_match)
        rows = re.findall(r"\| (test-org/repo\w+)", details_match.group(1))
        self.assertEqual(rows[0], "test-org/repoNew")
        self.assertEqual(rows[1], "test-org/repoMid")
        self.assertEqual(rows[2], "test-org/repoOld")


if __name__ == "__main__":
    unittest.main()
