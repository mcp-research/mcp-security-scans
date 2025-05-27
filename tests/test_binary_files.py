#!/usr/bin/env python3

import os
import sys
import unittest
from pathlib import Path

# Add the src directory to the path so we can import the src module
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

from src.analyze import scan_repo_for_mcp_composition


class TestScanBinaryFiles(unittest.TestCase):
    """Test the scanning of repositories for MCP composition."""

    def test_scan_with_binary_file(self):
        """Test that binary files are skipped during scanning."""
        test_dir = os.path.join(os.path.dirname(__file__), "test_files", "binary_test")
        os.makedirs(test_dir, exist_ok=True)
        test_file = os.path.join(test_dir, "test.md")

        try:
            # Create a binary file
            with open(test_file, "wb") as f:
                f.write(b"\x00\x01\x02\x03")

            # Run the scan
            result, error = scan_repo_for_mcp_composition(Path(test_dir))

            # Verify result
            self.assertIsNotNone(result)
            self.assertIn(
                "mcpServers", result or {}, "'mcpServers' key missing in result"
            )
            mcpServers = result.get("mcpServers", {}) if result else {}
            self.assertIn("server1", mcpServers, "'server1' key missing in mcpServers")

        finally:
            # Clean up
            try:
                os.unlink(test_file)
                os.rmdir(test_dir)
            except Exception:
                pass


if __name__ == "__main__":
    unittest.main()