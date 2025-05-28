#!/usr/bin/env python3

import unittest
import tempfile
import shutil
import os
import sys
import logging
from pathlib import Path

# Find the project root directory
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Add the project root directory to the Python path
sys.path.insert(0, project_root)

# Import the functions to be tested
from src.analyze import scan_repo_for_mcp_composition, get_composition_info

# Set up logging
logging.basicConfig(level=logging.INFO)

class TestInvalidMcpJson(unittest.TestCase):
    """Tests for handling invalid MCP JSON configurations."""
    
    @classmethod
    def setUpClass(cls):
        """Set up paths and create temporary directory."""
        cls.temp_dir = Path(tempfile.mkdtemp())
        logging.info(f"Created temporary directory at {cls.temp_dir}")
        
        # Create sample invalid MCP configuration
        invalid_json = """{
  "mcpServers": {
    "filesystem": {
      "command": "npx",
      "args": [
        "-y",
        "@modelcontextprotocol/server-filesystem",
        "/Users/your-username/Desktop"
      ]
    },
    "agent-care": {
      "command": "node",
      "args": [
        "/Users/your-username/{agentcare-download-path}/agent-care-mcp/build/index.js"
      ],
      "env": {
        "OAUTH_CLIENT_ID": XXXXXX,
        "OAUTH_CLIENT_SECRET":XXXXXXX,
        "OAUTH_TOKEN_HOST":,
        "OAUTH_TOKEN_PATH":,
        "OAUTH_AUTHORIZE_PATH",
        "OAUTH_AUTHORIZATION_METHOD": ,
        "OAUTH_AUDIENCE":,
        "OAUTH_CALLBACK_URL":,
        "OAUTH_SCOPES":,
        "OAUTH_CALLBACK_PORT":,
        "FHIR_BASE_URL":,
        "PUBMED_API_KEY":,
        "CLINICAL_TRIALS_API_KEY":,
        "FDA_API_KEY":
      }
    }
  }
}"""
        
        # Create a markdown file with the invalid JSON
        cls.invalid_sample_file = cls.temp_dir / "invalid_env_vars.md"
        with open(cls.invalid_sample_file, "w") as f:
            f.write("# MCP Configuration with Invalid Environment Variables\n\n")
            f.write("```json\n")
            f.write(invalid_json)
            f.write("\n```\n")
            
    @classmethod
    def tearDownClass(cls):
        """Clean up the temporary directory."""
        if cls.temp_dir.exists():
            shutil.rmtree(cls.temp_dir)
            logging.info(f"Cleaned up temporary directory {cls.temp_dir}")
        
    def test_invalid_env_vars(self):
        """Test scanning a JSON with invalid environment variables."""
        # Use scan_repo_for_mcp_composition to scan the directory
        mcp_composition, error_details = scan_repo_for_mcp_composition(self.temp_dir)
        self.assertIsNotNone(mcp_composition, "scan_repo_for_mcp_composition failed to parse the invalid JSON")
        self.assertIsNone(error_details, f"scan_repo_for_mcp_composition returned error: {error_details}")
        self.assertIn("mcpServers", mcp_composition, "'mcpServers' key missing in parsed composition")
        self.assertIn("agent-care", mcp_composition["mcpServers"], "'agent-care' key missing in parsed composition")
        self.assertIn("env", mcp_composition["mcpServers"]["agent-care"], "'env' key missing in parsed composition")
        
        # Test: call get_composition_info to ensure it can process the previously invalid JSON
        info, analysis_error = get_composition_info(mcp_composition)
        self.assertIsNone(analysis_error, f"get_composition_info returned error: {analysis_error}")
        self.assertIsNotNone(info, "get_composition_info returned None")
        self.assertIn("command", info, "'command' key missing in composition info")
        
        # The first server in the config is "filesystem", so we expect the command to be "npx"
        self.assertEqual(info["command"], "npx", f"Expected 'npx' command but got {info['command']}")

if __name__ == "__main__":
    unittest.main()
