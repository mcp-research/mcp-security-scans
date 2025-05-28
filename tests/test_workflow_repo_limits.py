#!/usr/bin/env python3

import unittest


class TestWorkflowRepoLimits(unittest.TestCase):
    """Test workflow repository limit logic for different trigger types."""

    def test_conditional_repo_limit_logic(self):
        """Test that the conditional logic for repository limits works correctly."""
        # Simulate the GitHub Actions conditional expression logic
        # ${{ (github.event_name == 'push' || github.event_name == 'pull_request') && '50' || '500' }}
        
        def get_repo_limit(event_name):
            """Simulate the GitHub Actions conditional expression."""
            return '50' if event_name in ['push', 'pull_request'] else '500'
        
        # Test push trigger
        self.assertEqual(get_repo_limit('push'), '50')
        
        # Test pull_request trigger
        self.assertEqual(get_repo_limit('pull_request'), '50')
        
        # Test schedule trigger
        self.assertEqual(get_repo_limit('schedule'), '500')
        
        # Test workflow_dispatch trigger (manual)
        self.assertEqual(get_repo_limit('workflow_dispatch'), '500')
        
        # Test other triggers
        self.assertEqual(get_repo_limit('issues'), '500')
        self.assertEqual(get_repo_limit('unknown'), '500')


if __name__ == '__main__':
    unittest.main()