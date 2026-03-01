#!/usr/bin/env python3

import os
import sys
import unittest
from unittest.mock import MagicMock, patch

# Add src directory to path for imports
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))


class TestReportMainExitsOnError(unittest.TestCase):
    """Test that report.main() exits with code 1 on error."""

    @patch('src.report.get_github_client')
    @patch('src.report.list_all_repository_properties_for_org')
    def test_main_exits_on_api_error(self, mock_list_props, mock_get_client):
        """Test that main() calls sys.exit(1) when list_all_repository_properties_for_org raises."""
        mock_get_client.return_value = MagicMock()
        mock_list_props.side_effect = AttributeError(
            "'OrgsClient' object has no attribute 'list_custom_properties_values_for_repos'"
        )

        with patch.dict(os.environ, {'GH_APP_ID': '12345', 'GH_APP_PRIVATE_KEY': 'fake-key'}):
            with patch('sys.argv', ['report']):
                with self.assertRaises(SystemExit) as ctx:
                    from src.report import main
                    main()

        self.assertEqual(ctx.exception.code, 1)


class TestListAllRepositoryPropertiesForOrg(unittest.TestCase):
    """Test that list_all_repository_properties_for_org uses the correct API method."""

    def test_uses_correct_api_method(self):
        """Test that the function calls custom_properties_for_repos_get_organization_values."""
        mock_gh = MagicMock()
        mock_gh.paginate.return_value = []

        from src.github import list_all_repository_properties_for_org
        list_all_repository_properties_for_org(mock_gh, "test-org")

        mock_gh.paginate.assert_called_once_with(
            mock_gh.rest.orgs.custom_properties_for_repos_get_organization_values,
            org="test-org"
        )

    def test_returns_all_properties(self):
        """Test that the function returns the paginated results."""
        mock_gh = MagicMock()
        mock_prop_1 = MagicMock()
        mock_prop_2 = MagicMock()
        mock_gh.paginate.return_value = [mock_prop_1, mock_prop_2]

        from src.github import list_all_repository_properties_for_org
        result = list_all_repository_properties_for_org(mock_gh, "test-org")

        self.assertEqual(len(result), 2)
        self.assertIn(mock_prop_1, result)
        self.assertIn(mock_prop_2, result)


if __name__ == "__main__":
    unittest.main()
