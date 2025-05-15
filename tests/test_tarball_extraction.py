#!/usr/bin/env python3

import unittest
import os
import tempfile
import shutil
import subprocess
from pathlib import Path
from unittest.mock import patch, MagicMock
from src.github import is_valid_tarball, clone_repository

class TestTarballExtraction(unittest.TestCase):
    
    def setUp(self):
        # Create a temporary directory for testing
        self.test_dir = tempfile.mkdtemp()
        self.temp_file = os.path.join(self.test_dir, "test.tar.gz")
        
    def tearDown(self):
        # Clean up the temporary directory
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)
    
    @patch('magic.from_file')
    def test_is_valid_tarball_gzip(self, mock_from_file):
        # Test with a valid gzip tarball type
        mock_from_file.return_value = "gzip compressed data"
        self.assertTrue(is_valid_tarball(self.temp_file))
        
    @patch('magic.from_file')
    def test_is_valid_tarball_tar(self, mock_from_file):
        # Test with a valid tar archive type
        mock_from_file.return_value = "tar archive"
        self.assertTrue(is_valid_tarball(self.temp_file))
    
    @patch('magic.from_file')
    def test_is_valid_tarball_invalid(self, mock_from_file):
        # Test with an invalid type
        mock_from_file.return_value = "ASCII text"
        self.assertFalse(is_valid_tarball(self.temp_file))
    
    @patch('magic.from_file')
    def test_is_valid_tarball_exception(self, mock_from_file):
        # Test with an exception
        mock_from_file.side_effect = Exception("Test exception")
        self.assertFalse(is_valid_tarball(self.temp_file))
    
    @patch('subprocess.run')
    @patch('src.github.is_valid_tarball')
    @patch('src.github.time.sleep')  # Mock sleep to avoid waiting in tests
    def test_clone_repository_success(self, mock_sleep, mock_is_valid, mock_run):
        # Mock a successful download and extraction
        mock_is_valid.return_value = True
        mock_run.return_value = MagicMock(stdout="", stderr="")
        
        # Create a mock GitHub client
        mock_gh = MagicMock()
        mock_gh.rest.repos.download_tarball_archive.return_value = MagicMock(url="https://example.com/tarball.tar.gz")
        
        # Call the function
        clone_repository(mock_gh, "test-owner", "test-repo", "main", Path(self.test_dir))
        
        # Check that the required functions were called
        mock_gh.rest.repos.download_tarball_archive.assert_called_once()
        self.assertEqual(mock_run.call_count, 2)  # Once for curl, once for tar
        mock_is_valid.assert_called_once()
    
    @patch('subprocess.run')
    @patch('src.github.is_valid_tarball')
    @patch('src.github.time.sleep')  # Mock sleep to avoid waiting in tests
    def test_clone_repository_invalid_tarball(self, mock_sleep, mock_is_valid, mock_run):
        # Mock an invalid tarball
        mock_is_valid.return_value = False
        mock_run.return_value = MagicMock(stdout="", stderr="")
        
        # Create a mock GitHub client
        mock_gh = MagicMock()
        mock_gh.rest.repos.download_tarball_archive.return_value = MagicMock(url="https://example.com/tarball.tar.gz")
        
        # Call the function
        clone_repository(mock_gh, "test-owner", "test-repo", "main", Path(self.test_dir))
        
        # Check that the required functions were called with retries
        self.assertEqual(mock_gh.rest.repos.download_tarball_archive.call_count, 3)  # Should retry 3 times
        self.assertEqual(mock_is_valid.call_count, 3)  # Should check validity 3 times
        self.assertEqual(mock_run.call_count, 3)  # Only curl should be called, not tar
    
    @patch('subprocess.run')
    @patch('src.github.is_valid_tarball')
    @patch('src.github.time.sleep')  # Mock sleep to avoid waiting in tests
    def test_clone_repository_extraction_failure(self, mock_sleep, mock_is_valid, mock_run):
        # Mock valid tarball but extraction failure
        mock_is_valid.return_value = True
        
        # First call for curl succeeds, second call for tar fails
        def side_effect_function(*args, **kwargs):
            if args[0][0] == "curl":
                return MagicMock(stdout="", stderr="")
            elif args[0][0] == "tar":
                raise subprocess.CalledProcessError(1, args[0], "Error", "Tar extraction failed")
            return MagicMock()
        
        mock_run.side_effect = side_effect_function
        
        # Create a mock GitHub client
        mock_gh = MagicMock()
        mock_gh.rest.repos.download_tarball_archive.return_value = MagicMock(url="https://example.com/tarball.tar.gz")
        
        # Call the function
        clone_repository(mock_gh, "test-owner", "test-repo", "main", Path(self.test_dir))
        
        # Check that the required functions were called with retries
        self.assertEqual(mock_gh.rest.repos.download_tarball_archive.call_count, 3)  # Should retry 3 times
        self.assertEqual(mock_is_valid.call_count, 3)  # Should check validity 3 times
        self.assertEqual(mock_run.call_count, 6)  # 3 times curl, 3 times tar

if __name__ == "__main__":
    unittest.main()