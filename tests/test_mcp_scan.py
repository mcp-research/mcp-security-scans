#!/usr/bin/env python3

import unittest
import tempfile
import shutil
import os
import sys
import json
import logging
from pathlib import Path
from typing import Dict

# Find the project root directory
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Add the project root directory to the Python path
sys.path.insert(0, project_root)

# Import the functions to be tested
from src.analyze import scan_repo_for_mcp_composition, get_composition_info

# Set up logging
logging.basicConfig(level=logging.INFO)

class TestMcpScan(unittest.TestCase):
    """Tests for MCP scan functionality."""
    
    @classmethod
    def setUpClass(cls):
        """Set up paths and create temporary directory."""
        cls.temp_dir = Path(tempfile.mkdtemp())
        logging.info(f"Created temporary directory at {cls.temp_dir}")
        
        # Create sample MCP configuration
        mcp_config = {
            "mcpServers": {
                "memory": {"command": "npx", "args": ["-y", "@modelcontextprotocol/server-memory"]},
                "filesystem": {"command": "npx", "args": ["-y", "@modelcontextprotocol/server-filesystem", "/path/to/allowed/files"]},
            }
        }
        
        sample_file = cls.temp_dir / "sample.json"
        with open(sample_file, "w") as f:
            json.dump(mcp_config, f)
            
    @classmethod
    def tearDownClass(cls):
        """Clean up the temporary directory."""
        if cls.temp_dir.exists():
            shutil.rmtree(cls.temp_dir)
            logging.info(f"Cleaned up temporary directory {cls.temp_dir}")
        
    def test_mcp_scan_functions_exist(self):
        """Check that the MCP scan functions exist."""
        self.assertTrue(callable(scan_repo_for_mcp_composition), "scan_repo_for_mcp_composition function not found")
        self.assertTrue(callable(get_composition_info), "get_composition_info function not found")

    def test_mcp_composition_cognee_example(self):
        """Test scanning the example directory for MCP composition using scan_repo_for_mcp_composition and get_composition_info."""
        # Path to the directory containing the example config
        example_dir = Path(project_root) / "tests" / "test_mcp_scan" / "examples" / "cognee"
        self.assertTrue(example_dir.exists(), f"Example directory [{example_dir}] does not exist.")
        # Use scan_repo_for_mcp_composition to scan the directory
        mcp_composition, error_details = scan_repo_for_mcp_composition(example_dir)
        self.assertIsNotNone(mcp_composition, "scan_repo_for_mcp_composition returned None for the example directory.")
        self.assertIsNone(error_details, f"scan_repo_for_mcp_composition returned error: {error_details}")
        self.assertIn("mcpServers", mcp_composition, "'mcpServers' key missing in scanned composition.")
        logging.info(f"Loaded and validated cognee example using scan_repo_for_mcp_composition: [{mcp_composition}]")

        # Test: call get_composition_info and check for 'uv' in the result
        info, analysis_error = get_composition_info(mcp_composition)
        self.assertIsNone(analysis_error, f"get_composition_info returned error: {analysis_error}")
        if info is not None:
            # If info is a dict or str, check if 'uv' is present in any value
            if isinstance(info, dict):
                found_uv = any('uv' in str(v) for v in info.values())
            else:
                found_uv = 'uv' in str(info)
            self.assertTrue(found_uv, f"get_composition_info did not return or contain 'uv': [{info}]")
        else:
            self.fail("get_composition_info returned None, expected a result containing 'uv'.")
    
    def test_mcp_composition_lux_example(self):
        """Test scanning the example directory for MCP composition using scan_repo_for_mcp_composition and get_composition_info."""
        # Path to the directory containing the example config
        example_dir = Path(project_root) / "tests" / "test_mcp_scan" / "examples" / "lux159__mcp-server-kubernetes-4834df2"
        self.assertTrue(example_dir.exists(), f"Example directory [{example_dir}] does not exist.")
        # Use scan_repo_for_mcp_composition to scan the directory
        mcp_composition, error_details = scan_repo_for_mcp_composition(example_dir)
        self.assertIsNotNone(mcp_composition, "scan_repo_for_mcp_composition returned None for the example directory.")
        self.assertIsNone(error_details, f"scan_repo_for_mcp_composition returned error: {error_details}")
        self.assertIn("mcpServers", mcp_composition, "'mcpServers' key missing in scanned composition.")
        logging.info(f"Loaded and validated lux example using scan_repo_for_mcp_composition: [{mcp_composition}]")
        
        # Test: call get_composition_info and check for kubernetes-readonly server
        info, analysis_error = get_composition_info(mcp_composition)
        self.assertIsNone(analysis_error, f"get_composition_info returned error: {analysis_error}")
        if info is not None:
            # If info is a dict or str, check if 'npx' is present in any value
            if isinstance(info, dict):
                found_npx = any('npx' in str(v) for v in info.values())
            else:
                found_npx = 'npx' in str(info)
            self.assertTrue(found_npx, f"get_composition_info did not return or contain 'npx': [{info}]")
        else:
            self.fail("get_composition_info returned None, expected a result containing 'npx'.")
    
    def test_mcp_composition_taylor_example(self):
        """Test scanning the example directory for MCP composition using scan_repo_for_mcp_composition and get_composition_info."""
        # Path to the directory containing the example config
        example_dir = Path(project_root) / "tests" / "test_mcp_scan" / "examples" / "taylor-lindores-reeves__mcp-github-projects"
        self.assertTrue(example_dir.exists(), f"Example directory [{example_dir}] does not exist.")
        # Use scan_repo_for_mcp_composition to scan the directory
        mcp_composition, error_details = scan_repo_for_mcp_composition(example_dir)
        self.assertIsNotNone(mcp_composition, "scan_repo_for_mcp_composition returned None for the example directory.")
        self.assertIsNone(error_details, f"scan_repo_for_mcp_composition returned error: {error_details}")
        self.assertIn("mcpServers", mcp_composition, "'mcpServers' key missing in scanned composition.")
        logging.info(f"Loaded and validated taylor example using scan_repo_for_mcp_composition: [{mcp_composition}]")
        
        # Test: call get_composition_info and verify it works with multiple servers
        info, analysis_error = get_composition_info(mcp_composition)
        self.assertIsNone(analysis_error, f"get_composition_info returned error: {analysis_error}")
        if info is not None:
            # If info is a dict or str, check if 'npx' is present in any value
            if isinstance(info, dict):
                found_npx = any('npx' in str(v) for v in info.values())
            else:
                found_npx = 'npx' in str(info)
            self.assertTrue(found_npx, f"get_composition_info did not return or contain 'npx': [{info}]")
            # Also verify server_type is present in the result
            self.assertIn("server_type", info, "'server_type' key missing in composition info")
        else:
            self.fail("get_composition_info returned None, expected a result containing 'npx'.")

if __name__ == "__main__":
    unittest.main()
