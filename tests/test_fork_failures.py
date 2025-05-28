#!/usr/bin/env python3

import os
import sys
import unittest
from unittest.mock import MagicMock

from githubkit.exception import RequestFailed

# Add src directory to path for imports
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from src.process_mcp_repos import ensure_repository_fork


class TestForkFailures(unittest.TestCase):
    """Test the fork failure reasons are correctly captured."""

    def test_fork_failure_reasons(self):
        """Test that appropriate failure reasons are returned."""
        # Mock the dependencies
        mock_gh = MagicMock()
        mock_repos = []

        # Test with 404 error
        response_mock = MagicMock()
        response_mock.status_code = 404

        mock_gh.rest.repos.create_fork.side_effect = RequestFailed(
            response=response_mock
        )

        # Call the function with mocked dependencies
        fork_exists, fork_skipped, failure_reason = ensure_repository_fork(
            mock_repos, mock_gh, "owner", "repo", "target-org", "target-repo", "owner/repo"
        )

        # Verify the result
        self.assertFalse(fork_exists)
        self.assertFalse(fork_skipped)
        self.assertTrue("not found" in failure_reason.lower() or "not accessible" in failure_reason.lower())


if __name__ == "__main__":
    unittest.main()
