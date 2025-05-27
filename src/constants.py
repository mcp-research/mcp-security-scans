#!/usr/bin/env python3

from pathlib import Path

# Target organization
TARGET_ORG = "mcp-research"  # The organization to scan

# Property name for last scan timestamp
GHAS_STATUS_UPDATED = "GHAS_Status_Updated"

# Scan frequency
SCAN_FREQUENCY_DAYS = 7  # Minimum days between scans

# Property names for total alert counts
CODE_ALERTS = "CodeAlerts"  # Property name for code scanning alerts
SECRET_ALERTS = "SecretAlerts"  # Property name for secret scanning alerts
DEPENDENCY_ALERTS = "DependencyAlerts"  # Property name for dependency alerts

# Property names for code scanning alerts by severity
CODE_ALERTS_CRITICAL = "CodeAlerts_Critical"
CODE_ALERTS_HIGH = "CodeAlerts_High"
CODE_ALERTS_MEDIUM = "CodeAlerts_Medium"
CODE_ALERTS_LOW = "CodeAlerts_Low"

# Property names for secret scanning alerts (no standard severity levels)
SECRET_ALERTS_TOTAL = "SecretAlerts_Total"
SECRET_ALERTS_BY_TYPE = "SecretAlerts_By_Type"  # Using the correct name that matches the shell script

# Property names for dependency alerts by severity
DEPENDENCY_ALERTS_CRITICAL = "DependencyAlerts_Critical"
DEPENDENCY_ALERTS_HIGH = "DependencyAlerts_High"
DEPENDENCY_ALERTS_MODERATE = "DependencyAlerts_Moderate"
DEPENDENCY_ALERTS_LOW = "DependencyAlerts_Low"

# MCP Agents Hub repository constants
MCP_AGENTS_HUB_REPO_URL = "https://github.com/mcp-agents-ai/mcp-agents-hub.git"
LOCAL_REPO_PATH = Path("./cloned_mcp_agents_hub")
SERVER_FILES_DIR_IN_REPO = "server/src/data/split"

# Report directory
REPORT_DIR = "reports"  # Directory to save reports