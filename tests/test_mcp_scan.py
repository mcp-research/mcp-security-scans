#!/usr/bin/env python3

import unittest
import tempfile
import shutil
import os
import sys
import json
import logging
from pathlib import Path

# Find the project root directory
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Add the project root directory to the Python path
sys.path.insert(0, project_root)

# Import the functions to be tested
from src.analyze import scan_repo_for_mcp_composition, get_composition_info, detect_runtime_from_package_files

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

    def test_malformed_json_missing_closing_bracket(self):
        """Test that malformed JSON missing closing brackets is handled gracefully."""
        temp_dir = Path(tempfile.mkdtemp())
        try:
            # Create a README.md file with malformed JSON (missing final closing bracket)
            malformed_content = '''# Ableton Live MCP Server

This is an example of malformed JSON:

```json
{
  "mcpServers": {
    "Ableton Live Controller": {
      "command": "/path/to/your/project/.venv/bin/python",
      "args": ["/path/to/your/project/mcp_ableton_server.py"]
    }
  
```

Notice the missing closing bracket.'''
            
            readme_file = temp_dir / "README.md"
            with open(readme_file, 'w') as f:
                f.write(malformed_content)
            
            # Test the fix behavior
            composition, error_details = scan_repo_for_mcp_composition(temp_dir)
            
            # After fix: should return valid composition with no error
            self.assertIsNotNone(composition, "Expected composition to be parsed after fixing malformed JSON")
            self.assertIsNone(error_details, "Expected no error details after successful fix")
            
            # Verify the composition structure
            self.assertIn("mcpServers", composition, "'mcpServers' key missing in fixed composition")
            self.assertIn("AbletonLiveController", composition["mcpServers"], "Expected server name missing")
            
            # Verify the specific content was preserved
            server_config = composition["mcpServers"]["AbletonLiveController"]
            self.assertEqual(server_config["command"], "/path/to/your/project/.venv/bin/python")
            self.assertEqual(server_config["args"], ["/path/to/your/project/mcp_ableton_server.py"])
            
            logging.info(f"Successfully fixed and parsed malformed JSON: [{composition}]")
        finally:
            # Clean up
            shutil.rmtree(temp_dir)

    def test_node_command_detected_in_composition(self):
        """Test that 'node' command is recognized as a known server type in get_composition_info."""
        example_dir = Path(project_root) / "tests" / "test_mcp_scan" / "examples" / "cosmix__linear-mcp"
        self.assertTrue(example_dir.exists(), f"Example directory [{example_dir}] does not exist.")

        mcp_composition, error_details = scan_repo_for_mcp_composition(example_dir)
        self.assertIsNotNone(mcp_composition, "scan_repo_for_mcp_composition returned None for the example directory.")
        self.assertIsNone(error_details, f"scan_repo_for_mcp_composition returned error: {error_details}")

        info, analysis_error = get_composition_info(mcp_composition)
        self.assertIsNone(analysis_error, f"get_composition_info returned error: {analysis_error}")
        self.assertIsNotNone(info, "get_composition_info returned None")
        self.assertEqual(info.get("server_type"), "node", f"Expected server_type 'node', got [{info.get('server_type')}]")
        self.assertEqual(info.get("command"), "node", f"Expected command 'node', got [{info.get('command')}]")
        logging.info(f"Node command detection test passed: [{info}]")

    def test_node_path_command_detected_in_composition(self):
        """Test that a path ending in 'node' (e.g. 'path-to/bin/node') is recognized as node server type."""
        composition = {
            "mcpServers": {
                "mcp-server-chatsum": {
                    "command": "path-to/bin/node",
                    "args": ["path-to/mcp-server-chatsum/build/index.js"]
                }
            }
        }
        info, analysis_error = get_composition_info(composition)
        self.assertIsNone(analysis_error, f"get_composition_info returned error: {analysis_error}")
        self.assertEqual(info.get("server_type"), "node",
                         f"Expected server_type 'node' for path-ending-in-node command, got [{info.get('server_type')}]")
        logging.info(f"Node path command detection test passed: [{info}]")

        # Also test with absolute path (e.g. /usr/local/bin/node)
        composition_abs = {
            "mcpServers": {
                "my-server": {
                    "command": "/usr/local/bin/node",
                    "args": ["/absolute/path/to/build/index.js"]
                }
            }
        }
        info_abs, analysis_error_abs = get_composition_info(composition_abs)
        self.assertIsNone(analysis_error_abs)
        self.assertEqual(info_abs.get("server_type"), "node",
                         f"Expected server_type 'node' for absolute node path, got [{info_abs.get('server_type')}]")
        logging.info(f"Absolute node path detection test passed: [{info_abs}]")

    def test_detect_runtime_from_package_json(self):
        """Test that detect_runtime_from_package_files detects 'node' from package.json with MCP SDK."""
        example_dir = Path(project_root) / "tests" / "test_mcp_scan" / "examples" / "mstfe__mcp-google-tasks"
        self.assertTrue(example_dir.exists(), f"Example directory [{example_dir}] does not exist.")

        runtime = detect_runtime_from_package_files(example_dir)
        self.assertIsNotNone(runtime, "detect_runtime_from_package_files returned None")
        self.assertTrue(bool(runtime), "detect_runtime_from_package_files returned empty dict")
        self.assertEqual(runtime.get("server_type"), "node",
                         f"Expected server_type 'node', got [{runtime.get('server_type')}]")
        logging.info(f"Package.json runtime detection test passed: [{runtime}]")

    def test_detect_runtime_no_mcp_sdk(self):
        """Test that detect_runtime_from_package_files returns empty dict when no MCP SDK is present."""
        temp_dir = Path(tempfile.mkdtemp())
        try:
            package_json = temp_dir / "package.json"
            with open(package_json, 'w') as f:
                json.dump({"name": "my-app", "dependencies": {"express": "^4.0.0"}}, f)

            runtime = detect_runtime_from_package_files(temp_dir)
            self.assertEqual(runtime, {}, f"Expected empty dict, got [{runtime}]")
            logging.info("No MCP SDK detection test passed: returned empty dict as expected")
        finally:
            shutil.rmtree(temp_dir)

    def test_detect_runtime_from_pyproject_toml(self):
        """Test that detect_runtime_from_package_files detects 'uv' from pyproject.toml with mcp package."""
        temp_dir = Path(tempfile.mkdtemp())
        try:
            pyproject = temp_dir / "pyproject.toml"
            pyproject.write_text('[project]\nname = "my-mcp-server"\ndependencies = ["mcp>=1.0.0"]\n')

            runtime = detect_runtime_from_package_files(temp_dir)
            self.assertIsNotNone(runtime, "detect_runtime_from_package_files returned None")
            self.assertTrue(bool(runtime), "detect_runtime_from_package_files returned empty dict")
            self.assertEqual(runtime.get("server_type"), "uv",
                             f"Expected server_type 'uv', got [{runtime.get('server_type')}]")
            logging.info(f"pyproject.toml runtime detection test passed: [{runtime}]")
        finally:
            shutil.rmtree(temp_dir)

    def test_detect_runtime_empty_directory(self):
        """Test that detect_runtime_from_package_files returns empty dict for empty directory."""
        temp_dir = Path(tempfile.mkdtemp())
        try:
            runtime = detect_runtime_from_package_files(temp_dir)
            self.assertEqual(runtime, {}, f"Expected empty dict for empty directory, got [{runtime}]")
            logging.info("Empty directory detection test passed: returned empty dict as expected")
        finally:
            shutil.rmtree(temp_dir)


if __name__ == "__main__":
    unittest.main()
