#!/usr/bin/env python3

import sys
import os
import unittest
import logging
from pathlib import Path
import tempfile
import shutil

# Set up logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')

# Adjust sys.path to include the project root for src imports
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

from src.analyze import scan_repo_for_mcp_composition


class TestBinaryFiles(unittest.TestCase):
    """Test handling of binary files in scan_repo_for_mcp_composition."""

    def setUp(self):
        # Create a temporary directory
        self.test_dir = Path(tempfile.mkdtemp())
        
        # Create a valid text file with content
        self.text_file = self.test_dir / "valid.json"
        with open(self.text_file, 'w', encoding='utf-8') as f:
            json_content = '{"mcpServers": {"server1": {"command": "uv", "args": []}}}'
            f.write(json_content)
            print(f"Written content to {self.text_file}: {json_content}")
        
        # Create a binary file that would cause decoding errors
        self.binary_file = self.test_dir / ".DS_Store"
        with open(self.binary_file, 'wb') as f:
            f.write(os.urandom(1024))  # Write 1KB of random binary data
            print(f"Created binary file {self.binary_file}")
            
        # Create another binary file
        self.binary_file2 = self.test_dir / "bun.lockb"
        with open(self.binary_file2, 'wb') as f:
            f.write(os.urandom(1024))  # Write 1KB of random binary data
            print(f"Created binary file {self.binary_file2}")
        
        print(f"Test directory contains: {list(self.test_dir.iterdir())}")

    def test_binary_file_handling(self):
        """Test that scan_repo_for_mcp_composition can handle binary files gracefully."""
        # The function should skip binary files and find content in the text file
        result = scan_repo_for_mcp_composition(self.test_dir)
        
        # It should have found the MCPServers configuration in the valid.json file
        self.assertIsNotNone(result, "Failed to find MCP configuration in test directory")
        self.assertIn("mcpServers", result, "'mcpServers' key missing in result")
        self.assertIn("server1", result["mcpServers"], "'server1' key missing in mcpServers")

    def tearDown(self):
        # Clean up the temporary directory
        shutil.rmtree(self.test_dir)


if __name__ == "__main__":
    unittest.main()