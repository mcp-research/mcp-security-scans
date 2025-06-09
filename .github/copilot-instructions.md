# GitHub Copilot Instructions for MCP Security Scans

This document provides guidelines for GitHub Copilot when assisting with code development in this repository.

## Logging Formatting

Whenever you add a log instruction, always use brackets around variables inside of the log message:

```python
# CORRECT
logging.info(f"Enabled vulnerability alerts for [{owner}/{repo}].")
logging.error(f"Unexpected error enabling GHAS features for [{owner}/{repo}]: [{e}]")

# INCORRECT
logging.info(f"Enabled vulnerability alerts for {owner}/{repo}.")
logging.error(f"Unexpected error enabling GHAS features for {owner}/{repo}: {e}")
```

## Import Statements

Always add import statements at the top of the file, never in the middle of the file.
When you add a new import, do not add a comment to that line:

```python
# CORRECT
import os
import logging
from typing import Dict, List

# INCORRECT
import os  # for file operations
import logging  # for logging messages
```

## Testing Instructions

To run tests for this project, use the following commands from the repository root:

```bash
# Run main test module
python -m unittest tests.test_mcp_scan

# Run specific test modules
python -m unittest tests.test_analysis_summary
python -m unittest tests.test_fork_failures
python -m unittest tests.test_severity_alerts

# Run all tests
python -m unittest discover tests
```

## Repository Structure

- `/src`: Main source code
  - `process_mcp_repos.py`: Main script for forking repositories
  - `analyze.py`: Analyzes repositories for security issues
  - `report.py`: Generates reports based on repository analysis
  - `github.py`: GitHub API interaction functions
- `/tests`: Test files
- `/.github`: GitHub-related configuration (workflows, etc.)

## Environment Variables

The project uses the following environment variables:

- `GH_APP_ID`: GitHub App ID
- `GH_APP_PRIVATE_KEY`: GitHub App private key

These can be set in your shell or through a `.env` file.

## Coding guidelines
Follow the flake8 coding guidelines for this project when generating new code, see the [flake8 configuration](../.flake8) for the configured rules.
Do not make changes to code only for coding guidelines. Only apply the guidelines to new code.
