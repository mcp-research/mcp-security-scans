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
            json_with_comments = (
                '{"mcpServers":{"thirdweb-mcp":{"command":"thirdweb-mcp","args":[],'
                '//add`--chain-id`optionally"env":{"THIRDWEB_SECRET_KEY":"yourthirdwebsecretkeyfromdashboard",'
                '"THIRDWEB_ENGINE_URL":"(OPTIONAL)yourengineurl",'
                '"THIRDWEB_ENGINE_AUTH_JWT":"(OPTIONAL)yourengineauthjwt",'
                '"THIRDWEB_ENGINE_BACKEND_WALLET_ADDRESS":"(OPTIONAL)yourenginebackendwalletaddress",'
                '},}}}'
            )
            
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

    def test_json_with_python_style_literals(self):
        """Test scanning a JSON with Python-style boolean and None literals (e.g. Redis MCP README)."""
        py_literals_temp_dir = Path(tempfile.mkdtemp())

        try:
            json_with_python_literals = """{
  "mcpServers": {
    "redis": {
      "command": "uvx",
      "args": ["mcp-redis"],
      "env": {
        "REDIS_HOST": "127.0.0.1",
        "REDIS_PORT": "6379",
        "REDIS_USERNAME": "default",
        "REDIS_PWD": "",
        "REDIS_SSL": False,
        "REDIS_CA_PATH": None,
        "REDIS_SSL_KEYFILE": None,
        "REDIS_SSL_CERTFILE": None,
        "REDIS_CERT_REQS": "required",
        "REDIS_CA_CERTS": None,
        "REDIS_CLUSTER_MODE": False
      }
    }
  }
}"""

            py_literals_file = py_literals_temp_dir / "python_literals_test.md"
            with open(py_literals_file, "w") as f:
                f.write("# Redis MCP Server\n\n")
                f.write("```json\n")
                f.write(json_with_python_literals)
                f.write("\n```\n")

            mcp_composition, error_details = scan_repo_for_mcp_composition(py_literals_temp_dir)

            self.assertIsNotNone(mcp_composition,
                                 "scan_repo_for_mcp_composition failed to parse JSON with Python-style literals")
            self.assertIsNone(error_details,
                              f"scan_repo_for_mcp_composition returned error: {error_details}")
            self.assertIn("mcpServers", mcp_composition, "'mcpServers' key missing in parsed composition")
            self.assertIn("redis", mcp_composition["mcpServers"], "'redis' key missing in parsed composition")

            redis_server = mcp_composition["mcpServers"]["redis"]
            self.assertEqual(redis_server["command"], "uvx",
                             f"Expected 'uvx' command but got {redis_server['command']}")
            self.assertIn("env", redis_server, "'env' key missing in parsed composition")
            self.assertEqual(redis_server["env"]["REDIS_HOST"], "127.0.0.1",
                             f"Expected '127.0.0.1' but got {redis_server['env']['REDIS_HOST']}")

            info, analysis_error = get_composition_info(mcp_composition)
            self.assertIsNone(analysis_error, f"get_composition_info returned error: {analysis_error}")
            self.assertIsNotNone(info, "get_composition_info returned None")
            self.assertEqual(info["command"], "uvx", f"Expected 'uvx' command but got {info['command']}")

        finally:
            if py_literals_temp_dir.exists():
                shutil.rmtree(py_literals_temp_dir)


    def test_missing_commas_between_properties(self):
        """Test scanning a JSON with missing commas between properties (e.g. evalstate/mcp-hfspace README)."""
        temp_dir = Path(tempfile.mkdtemp())

        try:
            # Mirrors the evalstate README pattern: missing commas between "command":"npx" and "args":[...]
            # and between array elements, plus a parenthetical placeholder comment
            json_missing_commas = """{
  "mcpServers": {
    "mcp-hfspace": {
      "command": "npx"
      "args": [
        "-y",
        "@llmindset/mcp-hfspace",
        "--HF_TOKEN=HF_{optional token}"
        "Qwen/Qwen2-72B-Instruct",
        "black-forest-labs/FLUX.1-schnell"
        (... and so on)
        ]
    }
  }
}"""

            test_file = temp_dir / "missing_commas_test.md"
            with open(test_file, "w") as f:
                f.write("# MCP Configuration with Missing Commas\n\n")
                f.write("```json\n")
                f.write(json_missing_commas)
                f.write("\n```\n")

            mcp_composition, error_details = scan_repo_for_mcp_composition(temp_dir)

            self.assertIsNotNone(mcp_composition,
                                 "scan_repo_for_mcp_composition failed to parse JSON with missing commas")
            self.assertIsNone(error_details,
                              f"scan_repo_for_mcp_composition returned error: {error_details}")
            self.assertIn("mcpServers", mcp_composition, "'mcpServers' key missing in parsed composition")
            self.assertIn("mcp-hfspace", mcp_composition["mcpServers"],
                          "'mcp-hfspace' key missing in parsed composition")

            server = mcp_composition["mcpServers"]["mcp-hfspace"]
            self.assertEqual(server["command"], "npx",
                             f"Expected 'npx' command but got {server['command']}")
            self.assertIn("args", server, "'args' key missing in parsed composition")
            self.assertIn("-y", server["args"], "'-y' missing from parsed args")

        finally:
            if temp_dir.exists():
                shutil.rmtree(temp_dir)

    def test_missing_comma_after_array_close(self):
        """Test scanning a JSON with a missing comma between an array and the next property
        (e.g. runekaagaard/mcp-notmuch-sendmail README)."""
        temp_dir = Path(tempfile.mkdtemp())

        try:
            # Mirrors the runekaagaard README pattern: missing comma between args:[...] and "env":{...}
            json_missing_comma = """{
  "mcpServers": {
    "email": {
      "command": "uvx",
      "args": ["--from", "mcp-notmuch-sendmail==2025.04.09", "--python", "3.10",
               "--refresh", "mcp-notmuch-sendmail"]
      "env": {
        "NOTMUCH_DATABASE_PATH": "/path/to/notmuch/db",
        "SENDMAIL_FROM_EMAIL": "your.email@example.com"
      }
    }
  }
}"""

            test_file = temp_dir / "missing_comma_after_array.md"
            with open(test_file, "w") as f:
                f.write("# MCP Notmuch Sendmail\n\n")
                f.write("```json\n")
                f.write(json_missing_comma)
                f.write("\n```\n")

            mcp_composition, error_details = scan_repo_for_mcp_composition(temp_dir)

            self.assertIsNotNone(mcp_composition,
                                 "scan_repo_for_mcp_composition failed to parse JSON with missing comma after array")
            self.assertIsNone(error_details,
                              f"scan_repo_for_mcp_composition returned error: {error_details}")
            self.assertIn("mcpServers", mcp_composition, "'mcpServers' key missing in parsed composition")
            self.assertIn("email", mcp_composition["mcpServers"],
                          "'email' key missing in parsed composition")

            server = mcp_composition["mcpServers"]["email"]
            self.assertEqual(server["command"], "uvx",
                             f"Expected 'uvx' command but got {server['command']}")
            self.assertIn("env", server, "'env' key missing in parsed composition")
            self.assertEqual(server["env"]["NOTMUCH_DATABASE_PATH"], "/path/to/notmuch/db",
                             "NOTMUCH_DATABASE_PATH value incorrect")

        finally:
            if temp_dir.exists():
                shutil.rmtree(temp_dir)

    def test_hash_comment_with_quoted_text_in_array(self):
        """Test scanning a JSON with a hash comment containing quoted text inside an array
        (e.g. isaacwasserman/mcp-vegalite-server README)."""
        temp_dir = Path(tempfile.mkdtemp())

        try:
            # Mirrors the isaacwasserman README pattern: a Python code block with
            # "png" # or "text" as a commented-out alternative value in an array
            json_hash_comment = """{
  "mcpServers": {
    "datavis": {
        "command": "uv",
        "args": [
            "--directory",
            "/absolute/path/to/mcp-datavis-server",
            "run",
            "mcp_server_datavis",
            "--output_type",
            "png" # or "text"
        ]
    }
  }
}"""

            test_file = temp_dir / "hash_comment_in_array.md"
            with open(test_file, "w") as f:
                f.write("# Data Visualization MCP Server\n\n")
                f.write("```python\n")
                f.write("# Add the server to your claude_desktop_config.json\n")
                f.write(json_hash_comment)
                f.write("\n```\n")

            mcp_composition, error_details = scan_repo_for_mcp_composition(temp_dir)

            self.assertIsNotNone(mcp_composition,
                                 "scan_repo_for_mcp_composition failed to parse JSON with quoted hash comment")
            self.assertIsNone(error_details,
                              f"scan_repo_for_mcp_composition returned error: {error_details}")
            self.assertIn("mcpServers", mcp_composition, "'mcpServers' key missing in parsed composition")
            self.assertIn("datavis", mcp_composition["mcpServers"],
                          "'datavis' key missing in parsed composition")

            server = mcp_composition["mcpServers"]["datavis"]
            self.assertEqual(server["command"], "uv",
                             f"Expected 'uv' command but got {server['command']}")
            self.assertIn("args", server, "'args' key missing in parsed composition")
            self.assertIn("png", server["args"], "'png' missing from parsed args")
            self.assertNotIn("text", server["args"], "'text' should have been removed as part of a comment")

        finally:
            if temp_dir.exists():
                shutil.rmtree(temp_dir)

    def test_inline_comment_with_empty_string_value(self):
        """Test scanning a JSON where a // comment follows an empty string value.

        Regression test for: acryldata__mcp-server-datahub README.md
        Failed to parse MCP composition JSON: Expecting property name enclosed
        in double quotes: line 1 column 58 (char 57)

        The preprocessing step that adds missing commas between consecutive quoted
        strings must not corrupt structurally-valid JSON that contains empty string
        values followed by a // comment, e.g.:
            "command": "",  //e.g./Users/hsheth/.local/bin/uvx
        After whitespace stripping and comment removal this becomes
            "command":"","args":
        which is already valid and must not be modified further.
        """
        temp_dir = Path(tempfile.mkdtemp())

        try:
            # This JSON mirrors what the scanner extracts from the datahub README after
            # stripping all whitespace.  The original README contained a multi-line block
            # like:
            #   "command": "",  //e.g./Users/hsheth/.local/bin/uvx
            #   "args": ["mcp-server-datahub"],
            # After whitespace stripping this collapses to the single-line form below,
            # where the // comment is immediately followed by the next JSON key.
            issue_json = (
                '{"mcpServers":{"datahub":{"command":"",//e.g./Users/hsheth/.local/bin/uvx'
                '"args":["mcp-server-datahub"],"env":{"DATAHUB_GMS_URL":"","DATAHUB_GMS_TOKEN":""}}}}'
            )

            test_file = temp_dir / "README.md"
            with open(test_file, "w") as f:
                f.write("# DataHub MCP Server\n\n")
                f.write("```json\n")
                f.write(issue_json)
                f.write("\n```\n")

            mcp_composition, error_details = scan_repo_for_mcp_composition(temp_dir)

            self.assertIsNotNone(mcp_composition,
                                 "scan_repo_for_mcp_composition failed to parse JSON "
                                 "with // comment after empty string value")
            self.assertIsNone(error_details,
                              f"scan_repo_for_mcp_composition returned error: {error_details}")
            self.assertIn("mcpServers", mcp_composition, "'mcpServers' key missing")
            self.assertIn("datahub", mcp_composition["mcpServers"], "'datahub' key missing")

            datahub_server = mcp_composition["mcpServers"]["datahub"]
            # The command value must be the empty string, not a comma injected by the
            # missing-comma preprocessing step.
            self.assertEqual(datahub_server["command"], "",
                             f"Expected empty string command but got {datahub_server['command']!r}")
            self.assertIn("args", datahub_server, "'args' key missing")
            self.assertEqual(datahub_server["args"], ["mcp-server-datahub"],
                             f"Unexpected args: {datahub_server['args']}")
            self.assertIn("env", datahub_server, "'env' key missing")
            self.assertEqual(datahub_server["env"]["DATAHUB_GMS_URL"], "",
                             "DATAHUB_GMS_URL should be empty string")

            info, analysis_error = get_composition_info(mcp_composition)
            self.assertIsNone(analysis_error, f"get_composition_info returned error: {analysis_error}")
            self.assertIsNotNone(info, "get_composition_info returned None")

        finally:
            if temp_dir.exists():
                shutil.rmtree(temp_dir)


    def test_json_with_ellipsis_placeholder(self):
        """Test scanning a JSON with an ellipsis placeholder comment (e.g. lzsheng__Yapi-MCP README).

        Regression test for: lzsheng__Yapi-MCP README.md
        Failed to parse MCP composition JSON: Expecting property name enclosed in
        double quotes: line 1 column 63 (char 62)

        The JSON contains `,...其它MCPServer配置` (Chinese text meaning "other MCP server
        configurations") as a placeholder after a real server entry.  This must be stripped
        before the JSON is parsed.
        """
        temp_dir = Path(tempfile.mkdtemp())

        try:
            issue_json = (
                '{"mcpServers":{"yapi-mcp":{"url":"http://localhost:3388/sse"},...其它MCPServer配置}}'
            )

            test_file = temp_dir / "README.md"
            with open(test_file, "w", encoding="utf-8") as f:
                f.write("# Yapi MCP Server\n\n")
                f.write("```json\n")
                f.write(issue_json)
                f.write("\n```\n")

            mcp_composition, error_details = scan_repo_for_mcp_composition(temp_dir)

            self.assertIsNotNone(mcp_composition,
                                 "scan_repo_for_mcp_composition failed to parse JSON "
                                 "with ellipsis placeholder")
            self.assertIsNone(error_details,
                              f"scan_repo_for_mcp_composition returned error: {error_details}")
            self.assertIn("mcpServers", mcp_composition, "'mcpServers' key missing")
            self.assertIn("yapi-mcp", mcp_composition["mcpServers"], "'yapi-mcp' key missing")

            yapi_server = mcp_composition["mcpServers"]["yapi-mcp"]
            self.assertEqual(yapi_server["url"], "http://localhost:3388/sse",
                             f"Unexpected url: {yapi_server.get('url')!r}")

        finally:
            if temp_dir.exists():
                shutil.rmtree(temp_dir)

    def test_unquoted_python_variable_values(self):
        """Test scanning a JSON where values are unquoted Python variable names with underscores.

        Regression test for: GongRzhe__Audio-MCP-Server setup_mcp.py
        Failed to parse MCP composition JSON: Expecting value: line 1 column 45 (char 44)

        The JSON contains Python variable names like python_path and server_script_path as
        unquoted values instead of quoted strings.
        """
        temp_dir = Path(tempfile.mkdtemp())

        try:
            issue_json = (
                '{"mcpServers":{"audio-interface":{"command":python_path,'
                '"args":[server_script_path],"env":{"PYTHONPATH":base_path,'
                '"GOOGLE_API_KEY":"XXX"}}}}'
            )

            test_file = temp_dir / "setup_mcp.py"
            with open(test_file, "w", encoding="utf-8") as f:
                f.write('# MCP setup script\n')
                f.write('config = ' + issue_json + '\n')

            mcp_composition, error_details = scan_repo_for_mcp_composition(temp_dir)

            self.assertIsNotNone(
                mcp_composition,
                "scan_repo_for_mcp_composition failed to parse JSON with unquoted Python variable names"
            )
            self.assertIsNone(error_details, f"scan_repo_for_mcp_composition returned error: {error_details}")
            self.assertIn("mcpServers", mcp_composition, "'mcpServers' key missing")
            self.assertIn("audio-interface", mcp_composition["mcpServers"], "'audio-interface' key missing")

            server = mcp_composition["mcpServers"]["audio-interface"]
            self.assertIn("command", server, "'command' key missing")
            self.assertIn("args", server, "'args' key missing")
            self.assertIn("env", server, "'env' key missing")

        finally:
            if temp_dir.exists():
                shutil.rmtree(temp_dir)


    def test_windows_path_backslashes(self):
        """Test scanning a JSON with unescaped Windows-style paths.

        Regression test for: punkpeye__mcp-filesystem-python claude_desktop_config_windows.json
        Failed to parse MCP composition JSON: (unicode error) 'unicodeescape' codec can't
        decode bytes in position 75-76: truncated \\UXXXXXXXX escape

        Windows paths like C:\\Users\\username\\Desktop use backslashes that are not valid
        JSON escape sequences, causing the parser to fail.
        """
        temp_dir = Path(tempfile.mkdtemp())

        try:
            issue_json = """{
  "mcpServers": {
    "filesystem": {
      "command": "npx",
      "args": [
        "-y",
        "@modelcontextprotocol/server-filesystem",
        "C:\\Users\\username\\Desktop",
        "C:\\Users\\username\\Documents"
      ]
    }
  }
}"""

            test_file = temp_dir / "claude_desktop_config_windows.json"
            with open(test_file, "w", encoding="utf-8") as f:
                f.write(issue_json)

            mcp_composition, error_details = scan_repo_for_mcp_composition(temp_dir)

            self.assertIsNotNone(
                mcp_composition,
                "scan_repo_for_mcp_composition failed to parse JSON with Windows-style paths"
            )
            self.assertIsNone(error_details, f"scan_repo_for_mcp_composition returned error: {error_details}")
            self.assertIn("mcpServers", mcp_composition, "'mcpServers' key missing")
            self.assertIn("filesystem", mcp_composition["mcpServers"], "'filesystem' key missing")

            server = mcp_composition["mcpServers"]["filesystem"]
            self.assertEqual(server["command"], "npx", f"Expected 'npx' but got {server['command']}")
            self.assertIn("args", server, "'args' key missing")
            # Verify that the Windows-style paths are preserved correctly after preprocessing
            self.assertIn("C:\\Users\\username\\Desktop", server["args"],
                          "Windows Desktop path missing from args")
            self.assertIn("C:\\Users\\username\\Documents", server["args"],
                          "Windows Documents path missing from args")

            info, analysis_error = get_composition_info(mcp_composition)
            self.assertIsNone(analysis_error, f"get_composition_info returned error: {analysis_error}")
            self.assertIsNotNone(info, "get_composition_info returned None")

        finally:
            if temp_dir.exists():
                shutil.rmtree(temp_dir)


    def test_inline_comment_before_closing_braces(self):
        """Test scanning a JSON where a // comment is the last item before closing braces.

        Regression test for: Spathodea-Network__opencti-mcp README.md
        Failed to parse MCP composition JSON: Expecting property name enclosed in
        double quotes: line 1 column 131 (char 130)

        The JSON contains inline // comments where the trailing comment is immediately
        followed by closing braces (no newline), e.g.:
            "OPENCTI_TOKEN":"${OPENCTI_TOKEN}"//Willbeloadedfrom.env}}}}
        The multiline // removal regex (//.*$) was greedily consuming the closing braces
        along with the comment, producing broken JSON.
        """
        temp_dir = Path(tempfile.mkdtemp())

        try:
            issue_json = (
                '{"mcpServers":{"opencti":{"command":"node",'
                '"args":["path/to/opencti-server/build/index.js"],'
                '"env":{"OPENCTI_URL":"${OPENCTI_URL}",//Willbeloadedfrom.env'
                '"OPENCTI_TOKEN":"${OPENCTI_TOKEN}"//Willbeloadedfrom.env}}}}'
            )

            test_file = temp_dir / "README.md"
            with open(test_file, "w") as f:
                f.write("# OpenCTI MCP Server\n\n")
                f.write("```json\n")
                f.write(issue_json)
                f.write("\n```\n")

            mcp_composition, error_details = scan_repo_for_mcp_composition(temp_dir)

            self.assertIsNotNone(mcp_composition,
                                 "scan_repo_for_mcp_composition failed to parse JSON "
                                 "with // comment before closing braces")
            self.assertIsNone(error_details,
                              f"scan_repo_for_mcp_composition returned error: {error_details}")
            self.assertIn("mcpServers", mcp_composition, "'mcpServers' key missing")
            self.assertIn("opencti", mcp_composition["mcpServers"], "'opencti' key missing")

            server = mcp_composition["mcpServers"]["opencti"]
            self.assertEqual(server["command"], "node",
                             f"Expected 'node' command but got {server['command']}")
            self.assertIn("env", server, "'env' key missing")
            self.assertIn("OPENCTI_URL", server["env"], "'OPENCTI_URL' missing from env")
            self.assertIn("OPENCTI_TOKEN", server["env"], "'OPENCTI_TOKEN' missing from env")

            info, analysis_error = get_composition_info(mcp_composition)
            self.assertIsNone(analysis_error, f"get_composition_info returned error: {analysis_error}")
            self.assertIsNotNone(info, "get_composition_info returned None")
            self.assertEqual(info["command"], "node",
                             f"Expected 'node' command but got {info['command']}")

        finally:
            if temp_dir.exists():
                shutil.rmtree(temp_dir)


    def test_hash_comment_at_array_start_with_windows_path(self):
        """Test scanning a JSON where a hash comment appears at the start of an array
        followed by consecutive string values including Windows paths.

        Regression test for: daobataotie__mssql-mcp README.md
        Failed to parse MCP composition JSON: Expecting value: line 1 column 52 (char 51)

        The args array contains a hash comment before the first quoted value:
            "args":[#yourpath，e.g.："C:\\\\mssql-mcp\\\\src\\\\server.py""~/server.py"]
        This needs two fixes:
        1. Remove the [#comment" prefix (new pattern for array-start hash comments)
        2. Add a missing comma between the two consecutive string values
        """
        temp_dir = Path(tempfile.mkdtemp())

        try:
            # \uff0c and \uff1a are fullwidth comma and colon from the original Chinese README
            issue_json = (
                '{"mcpServers":{"mssql":{"command":"python","args":'
                '[#yourpath\uff0ce.g.\uff1a"C:\\\\mssql-mcp\\\\src\\\\server.py""~/server.py"]}}}'
            )

            test_file = temp_dir / "README.md"
            with open(test_file, "w", encoding="utf-8") as f:
                f.write("# MSSQL MCP Server\n\n")
                f.write("```json\n")
                f.write(issue_json)
                f.write("\n```\n")

            mcp_composition, error_details = scan_repo_for_mcp_composition(temp_dir)

            self.assertIsNotNone(
                mcp_composition,
                "scan_repo_for_mcp_composition failed to parse JSON with hash comment at array start"
            )
            self.assertIsNone(error_details,
                               f"scan_repo_for_mcp_composition returned error: {error_details}")
            self.assertIn("mcpServers", mcp_composition, "'mcpServers' key missing")
            self.assertIn("mssql", mcp_composition["mcpServers"], "'mssql' key missing")

            server = mcp_composition["mcpServers"]["mssql"]
            self.assertEqual(server["command"], "python",
                             f"Expected 'python' but got {server['command']}")
            self.assertIn("args", server, "'args' key missing")
            self.assertIn("~/server.py", server["args"],
                          "'~/server.py' missing from parsed args")

        finally:
            if temp_dir.exists():
                shutil.rmtree(temp_dir)


    def test_hash_comment_between_array_elements_with_windows_path(self):
        """Test scanning a JSON with a hash comment between array elements where the
        preceding element is a single-backslash Windows path.

        Regression test for: truaxki__mcp-variance-log README.md
        Failed to parse MCP composition JSON: Invalid \escape: line 1 column 76 (char 75)

        The args array contains a Windows path with unescaped backslashes followed by an
        inline hash comment before the next array element:
            "args":["--directory","C:\\Users\\username\\source\\repos\\mcp-variance-log",
                    #Update this path
                    "run","mcp-variance-log"]
        After whitespace stripping this becomes:
            "args":["--directory","C:\\Users\\username\\source\\repos\\mcp-variance-log",
                    #Updatethispath"run","mcp-variance-log"]
        This requires two fixes:
        1. Remove the ,#Updatethispath" pattern (hash comment between array elements)
        2. Double the unescaped Windows path backslashes (including the \\r in "\\repos")
        """
        temp_dir = Path(tempfile.mkdtemp())

        try:
            # The README uses single backslashes in the Windows path.
            # The path contains \repos where \r would otherwise be treated
            # as a carriage-return JSON escape if not correctly doubled.
            readme_content = (
                '# mcp-variance-log\n\n'
                '```json\n'
                '{\n'
                '  "mcpServers": {\n'
                '    "mcp-variance-log": {\n'
                '      "command": "uv",\n'
                '      "args": [\n'
                '        "--directory",\n'
                '        "C:\\Users\\username\\source\\repos\\mcp-variance-log", #Update this path\n'
                '        "run",\n'
                '        "mcp-variance-log"\n'
                '      ]\n'
                '    }\n'
                '  }\n'
                '}\n'
                '```\n'
            )

            test_file = temp_dir / "README.md"
            with open(test_file, "w") as f:
                f.write(readme_content)

            mcp_composition, error_details = scan_repo_for_mcp_composition(temp_dir)

            self.assertIsNotNone(
                mcp_composition,
                "scan_repo_for_mcp_composition failed to parse JSON with hash comment "
                "between array elements containing a Windows path"
            )
            self.assertIsNone(error_details,
                               f"scan_repo_for_mcp_composition returned error: {error_details}")
            self.assertIn("mcpServers", mcp_composition, "'mcpServers' key missing")
            self.assertIn("mcp-variance-log", mcp_composition["mcpServers"],
                          "'mcp-variance-log' key missing")

            server = mcp_composition["mcpServers"]["mcp-variance-log"]
            self.assertEqual(server["command"], "uv",
                             f"Expected 'uv' but got {server['command']}")
            self.assertIn("args", server, "'args' key missing")
            self.assertIn("--directory", server["args"],
                          "'--directory' missing from parsed args")
            self.assertIn("run", server["args"], "'run' missing from parsed args")
            self.assertIn("mcp-variance-log", server["args"],
                          "'mcp-variance-log' missing from parsed args")
            # Verify that the Windows path is preserved with correct backslashes,
            # including \repos where \r must not be treated as a carriage-return escape.
            self.assertIn(
                "C:\\Users\\username\\source\\repos\\mcp-variance-log",
                server["args"],
                "Windows path with \\repos missing or incorrectly parsed from args"
            )

            info, analysis_error = get_composition_info(mcp_composition)
            self.assertIsNone(analysis_error, f"get_composition_info returned error: {analysis_error}")
            self.assertIsNotNone(info, "get_composition_info returned None")
            self.assertEqual(info["command"], "uv",
                             f"Expected 'uv' command but got {info['command']}")
            self.assertEqual(info["server_type"], "uv",
                             f"Expected server_type 'uv' but got {info['server_type']}")

        finally:
            if temp_dir.exists():
                shutil.rmtree(temp_dir)


    def test_brackets_inside_string_values(self):
        """Test scanning a JSON where string values contain curly brackets.

        Regression test for: jango-blockchained__advanced-homeassistant-mcp README.md
        Failed analysis: Malformed JSON: Unclosed brackets in file

        The args array contained shell commands with ${workspaceRoot} and \\{\"jsonrpc\"
        which include { and } characters inside JSON string values.
        The naive bracket counting algorithm incorrectly counted these as structural
        brackets, causing it to believe closing brackets were missing.
        """
        temp_dir = Path(tempfile.mkdtemp())

        try:
            issue_json = json.dumps({
                "mcpServers": {
                    "homeassistant-mcp": {
                        "command": "bash",
                        "args": ["-c", 'cd${workspaceRoot}&&bunrundist/index.js--stdio2>/dev/null|grep-E\'\\{"jsonrpc":"2\\.0"\''],
                        "env": {
                            "NODE_ENV": "development",
                            "USE_STDIO_TRANSPORT": "true",
                            "DEBUG_STDIO": "true"
                        }
                    }
                }
            }, separators=(',', ':'))

            test_file = temp_dir / "README.md"
            with open(test_file, "w", encoding="utf-8") as f:
                f.write("# Home Assistant MCP\n\n")
                f.write("```json\n")
                f.write(issue_json)
                f.write("\n```\n")

            mcp_composition, error_details = scan_repo_for_mcp_composition(temp_dir)

            self.assertIsNotNone(
                mcp_composition,
                "scan_repo_for_mcp_composition failed to parse JSON with brackets inside string values"
            )
            self.assertIsNone(error_details, f"scan_repo_for_mcp_composition returned error: {error_details}")
            self.assertIn("mcpServers", mcp_composition, "'mcpServers' key missing")
            self.assertIn("homeassistant-mcp", mcp_composition["mcpServers"], "'homeassistant-mcp' key missing")

            server = mcp_composition["mcpServers"]["homeassistant-mcp"]
            self.assertEqual(server["command"], "bash", f"Expected 'bash' but got {server['command']}")
            self.assertIn("env", server, "'env' key missing")
            self.assertEqual(server["env"]["NODE_ENV"], "development")

            info, analysis_error = get_composition_info(mcp_composition)
            self.assertIsNone(analysis_error, f"get_composition_info returned error: {analysis_error}")
            self.assertIsNotNone(info, "get_composition_info returned None")

        finally:
            if temp_dir.exists():
                shutil.rmtree(temp_dir)


if __name__ == "__main__":
    unittest.main()
