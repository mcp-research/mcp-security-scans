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

    def test_trailing_comma_in_env_object(self):
        """Test scanning a JSON with trailing commas in env object."""
        # Create a separate temporary directory for this test to avoid interference
        import tempfile
        trailing_comma_temp_dir = Path(tempfile.mkdtemp())
        
        try:
            # Create a test JSON with trailing commas before closing braces - simplified version
            invalid_json_with_trailing_commas = """{
  "mcpServers": {
    "test-server": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-test"],
      "env": {
        "OUTPUT_MODE": "file",
        "API_KEY": "test-key",
      }
    }
  }
}"""
            
            # Create a temporary test file with the invalid JSON
            trailing_comma_file = trailing_comma_temp_dir / "trailing_comma_test.md"
            with open(trailing_comma_file, "w") as f:
                f.write("# MCP Configuration with Trailing Comma\n\n")
                f.write("```json\n")
                f.write(invalid_json_with_trailing_commas)
                f.write("\n```\n")
            
            # Use scan_repo_for_mcp_composition to scan the directory
            mcp_composition, error_details = scan_repo_for_mcp_composition(trailing_comma_temp_dir)
            
            # The scan should succeed after preprocessing fixes the trailing comma
            self.assertIsNotNone(mcp_composition, "scan_repo_for_mcp_composition failed to parse JSON with trailing comma")
            self.assertIsNone(error_details, f"scan_repo_for_mcp_composition returned error: {error_details}")
            self.assertIn("mcpServers", mcp_composition, "'mcpServers' key missing in parsed composition")
            self.assertIn("test-server", mcp_composition["mcpServers"], "'test-server' key missing in parsed composition")
            self.assertIn("env", mcp_composition["mcpServers"]["test-server"], "'env' key missing in parsed composition")
            
            # Verify the env object was parsed correctly despite the trailing comma
            env_obj = mcp_composition["mcpServers"]["test-server"]["env"]
            self.assertIn("OUTPUT_MODE", env_obj, "'OUTPUT_MODE' key missing in env object")
            self.assertIn("API_KEY", env_obj, "'API_KEY' key missing in env object")
            self.assertEqual(env_obj["OUTPUT_MODE"], "file", f"Expected 'file' but got {env_obj['OUTPUT_MODE']}")
            self.assertEqual(env_obj["API_KEY"], "test-key", f"Expected 'test-key' but got {env_obj['API_KEY']}")
            
            # Test: call get_composition_info to ensure it can process the composition
            info, analysis_error = get_composition_info(mcp_composition)
            self.assertIsNone(analysis_error, f"get_composition_info returned error: {analysis_error}")
            self.assertIsNotNone(info, "get_composition_info returned None")
            self.assertIn("command", info, "'command' key missing in composition info")
            self.assertEqual(info["command"], "npx", f"Expected 'npx' command but got {info['command']}")
            
        finally:
            # Clean up the temporary directory
            if trailing_comma_temp_dir.exists():
                shutil.rmtree(trailing_comma_temp_dir)

    def test_json_with_comments(self):
        """Test scanning a JSON with comments using // and # syntax."""
        # Create a separate temporary directory for this test
        import tempfile
        comments_temp_dir = Path(tempfile.mkdtemp())
        
        try:
            # Create the exact JSON from the issue that should fail without comment removal
            json_with_comments = """{"mcpServers":{"thirdweb-mcp":{"command":"thirdweb-mcp","args":[],//add`--chain-id`optionally"env":{"THIRDWEB_SECRET_KEY":"yourthirdwebsecretkeyfromdashboard","THIRDWEB_ENGINE_URL":"(OPTIONAL)yourengineurl","THIRDWEB_ENGINE_AUTH_JWT":"(OPTIONAL)yourengineauthjwt","THIRDWEB_ENGINE_BACKEND_WALLET_ADDRESS":"(OPTIONAL)yourenginebackendwalletaddress",},}}}"""
            
            # Create a temporary test file with the JSON containing comments
            comments_file = comments_temp_dir / "comments_test.md"
            with open(comments_file, "w") as f:
                f.write("# MCP Configuration with Comments\n\n")
                f.write("```json\n")
                f.write(json_with_comments)
                f.write("\n```\n")
            
            # Use scan_repo_for_mcp_composition to scan the directory
            mcp_composition, error_details = scan_repo_for_mcp_composition(comments_temp_dir)
            
            # The scan should succeed after preprocessing removes the comments
            self.assertIsNotNone(mcp_composition, "scan_repo_for_mcp_composition failed to parse JSON with comments")
            self.assertIsNone(error_details, f"scan_repo_for_mcp_composition returned error: {error_details}")
            self.assertIn("mcpServers", mcp_composition, "'mcpServers' key missing in parsed composition")
            self.assertIn("thirdweb-mcp", mcp_composition["mcpServers"], "'thirdweb-mcp' key missing in parsed composition")
            
            # Verify the parsed data is correct
            thirdweb_server = mcp_composition["mcpServers"]["thirdweb-mcp"]
            self.assertEqual(thirdweb_server["command"], "thirdweb-mcp", f"Expected 'thirdweb-mcp' command but got {thirdweb_server['command']}")
            self.assertIn("env", thirdweb_server, "'env' key missing in parsed composition")
            
            # Test: call get_composition_info to ensure it can process the composition
            info, analysis_error = get_composition_info(mcp_composition)
            self.assertIsNone(analysis_error, f"get_composition_info returned error: {analysis_error}")
            self.assertIsNotNone(info, "get_composition_info returned None")
            self.assertIn("command", info, "'command' key missing in composition info")
            self.assertEqual(info["command"], "thirdweb-mcp", f"Expected 'thirdweb-mcp' command but got {info['command']}")
            
        finally:
            # Clean up the temporary directory
            if comments_temp_dir.exists():
                shutil.rmtree(comments_temp_dir)

    def test_json_with_hash_comments(self):
        """Test scanning a JSON with # style comments."""
        # Create a separate temporary directory for this test
        import tempfile
        hash_comments_temp_dir = Path(tempfile.mkdtemp())
        
        try:
            # Create JSON with # style comments
            json_with_hash_comments = """{
  "mcpServers": {
    "test-server": {
      "command": "npx", # This is the command to run
      "args": ["-y", "@modelcontextprotocol/server-test"], # These are the arguments
      "env": { # Environment variables
        "API_KEY": "test-key" # The API key
      }
    }
  }
}"""
            
            # Create a temporary test file with the JSON containing # comments
            hash_comments_file = hash_comments_temp_dir / "hash_comments_test.md"
            with open(hash_comments_file, "w") as f:
                f.write("# MCP Configuration with Hash Comments\n\n")
                f.write("```json\n")
                f.write(json_with_hash_comments)
                f.write("\n```\n")
            
            # Use scan_repo_for_mcp_composition to scan the directory
            mcp_composition, error_details = scan_repo_for_mcp_composition(hash_comments_temp_dir)
            
            # The scan should succeed after preprocessing removes the comments
            self.assertIsNotNone(mcp_composition, "scan_repo_for_mcp_composition failed to parse JSON with # comments")
            self.assertIsNone(error_details, f"scan_repo_for_mcp_composition returned error: {error_details}")
            self.assertIn("mcpServers", mcp_composition, "'mcpServers' key missing in parsed composition")
            self.assertIn("test-server", mcp_composition["mcpServers"], "'test-server' key missing in parsed composition")
            
            # Verify the parsed data is correct
            test_server = mcp_composition["mcpServers"]["test-server"]
            self.assertEqual(test_server["command"], "npx", f"Expected 'npx' command but got {test_server['command']}")
            self.assertIn("env", test_server, "'env' key missing in parsed composition")
            self.assertEqual(test_server["env"]["API_KEY"], "test-key", f"Expected 'test-key' but got {test_server['env']['API_KEY']}")
            
        finally:
            # Clean up the temporary directory
            if hash_comments_temp_dir.exists():
                shutil.rmtree(hash_comments_temp_dir)

if __name__ == "__main__":
    unittest.main()
