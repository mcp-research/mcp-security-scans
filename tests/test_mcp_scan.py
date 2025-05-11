#!/usr/bin/env python3

import sys
import os
import unittest
import logging
import json
import shutil
from pathlib import Path
from dotenv import load_dotenv
from unittest.mock import MagicMock
from githubkit.versions.latest.models import FullRepository

# Set up logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')

# Adjust sys.path to include the project root for src imports
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

from src.analyze import clone_repository, scan_repo_for_mcp_composition
from src.github import get_github_client

class TestMcpScan(unittest.TestCase):
    
    @classmethod
    def setUpClass(cls):
        # Load environment variables
        load_dotenv()
        
        # Set up test repository information
        cls.test_repo_url = "https://github.com/topoteretes/cognee"
        # Base temporary directory for all test clones
        cls.base_temp_dir = Path("/workspaces/mcp-security-scans/tmp/")
        
        # Clean up any existing base temp directory from previous test runs
        if cls.base_temp_dir.exists():
            shutil.rmtree(cls.base_temp_dir)
            logging.info(f"Removed existing base temp directory {cls.base_temp_dir}")

        # Create the base temp directory
        cls.base_temp_dir.mkdir(parents=True, exist_ok=True)

        # Initialize GitHub client
        cls.gh = None
        app_id = os.getenv("GH_APP_ID")
        private_key = os.getenv("GH_APP_PRIVATE_KEY")
        if app_id and private_key:
            try:
                cls.gh = get_github_client(app_id, private_key)
                logging.info("GitHub client initialized for tests.")
            except Exception as e:
                logging.warning(f"Failed to initialize GitHub client for tests: {e}. Some tests may not run correctly.")
        else:
            logging.warning("GH_APP_ID and/or GH_APP_PRIVATE_KEY environment variables not set. GitHub client not initialized.")

    def test_clone_and_scan_for_mcp_composition(self):
        """Test cloning a repository using analyze.clone_repository and scanning it for MCP composition using analyze.scan_repo_for_mcp_composition."""
        if not self.gh:
            self.skipTest("GitHub client not initialized. Skipping test that requires GitHub API access.")

        repo_owner = self.test_repo_url.split("/")[-2]
        repo_name = self.test_repo_url.split("/")[-1]
        
        # Specific path for this test's cloned repository
        cloned_repo_path = self.base_temp_dir / repo_name
        
        # Ensure the specific repo path is clean before cloning
        if cloned_repo_path.exists():
            shutil.rmtree(cloned_repo_path)
        # clone_repository expects the directory to exist
        cloned_repo_path.mkdir(parents=True, exist_ok=True) 

        # Mock FullRepository object
        mock_repo = MagicMock(spec=FullRepository)
        mock_repo.owner = MagicMock()
        mock_repo.owner.login = repo_owner
        mock_repo.name = repo_name
        mock_repo.default_branch = "main" # Assuming default branch for cognee repo

        logging.info(f"Attempting to clone {repo_owner}/{repo_name} using analyze.clone_repository to {cloned_repo_path}")
        try:
            clone_repository(self.gh, repo_owner, repo_name, mock_repo.default_branch, cloned_repo_path)
            logging.info(f"Repository {repo_name} should be cloned to {cloned_repo_path}")
            
            # Verify that the directory is not empty and contains the expected extracted folder
            # GitHub tarballs usually extract to a directory like <owner>-<repo>-<commit_sha>
            # We need to check if *any* subdirectory was created by the tar extraction.
            extracted_dirs = [d for d in cloned_repo_path.iterdir() if d.is_dir()]
            self.assertTrue(extracted_dirs, f"Repository was not cloned properly by clone_repository. No subdirectories found in {cloned_repo_path}.")
            # The actual content will be in one of these extracted_dirs. For os.walk in scan_repo_for_mcp_composition,
            # starting at cloned_repo_path is correct as it will traverse into this subdirectory.
            logging.info(f"Cloned content likely in: {extracted_dirs[0]}")

        except Exception as e:
            self.fail(f"analyze.clone_repository failed: {e}")

        logging.info(f"Scanning [{cloned_repo_path}] for MCP composition using analyze.scan_repo_for_mcp_composition")
        # Assuming existing_repos_properties can be an empty list for this specific test
        mcp_composition = scan_repo_for_mcp_composition(self.gh, mock_repo, [], cloned_repo_path)

        # The cognee repository (https://github.com/topoteretes/cognee) might not have an MCP file.
        # If it's expected to have one, this assertion is correct.
        # If not, the test or the target repository needs adjustment.
        # Based on previous errors, scan_repo_for_mcp_composition was returning None.
        self.assertIsNotNone(mcp_composition, "analyze.scan_repo_for_mcp_composition returned None. Check the function's logic and if the test repo contains a valid MCP file.")
        
        if mcp_composition: # Only proceed if not None
            logging.info(f"Found MCP composition: {json.dumps(mcp_composition, indent=2)}")
            if "mcpServers" in mcp_composition:
                self.assertIsInstance(mcp_composition["mcpServers"], dict, "mcpServers is not a dictionary")
            elif "mcp" in mcp_composition and "servers" in mcp_composition["mcp"]:
                self.assertIsInstance(mcp_composition["mcp"]["servers"], dict, "mcp.servers is not a dictionary")
            else:
                self.fail(f"MCP composition does not have the expected structure: {mcp_composition}")
    
    @classmethod
    def tearDownClass(cls):
        # Clean up the base temporary directory
        if cls.base_temp_dir.exists():
            try:
                shutil.rmtree(cls.base_temp_dir)
                logging.info(f"Cleaned up temporary directory {cls.base_temp_dir}")
            except Exception as e:
                logging.error(f"Error cleaning up temporary directory {cls.base_temp_dir}: {e}")

if __name__ == "__main__":
    unittest.main()
