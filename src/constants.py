#!/usr/bin/env python3

from pathlib import Path
from typing import Dict, List, Any

class Constants:
    """Central class for all constants used in the MCP Security Scans project."""

    class Org:
        """Organization related constants"""
        TARGET_ORG = "mcp-research"  # The organization to scan

    class ScanSettings:
        """Scan frequency and related settings"""
        SCAN_FREQUENCY_DAYS = 7  # Minimum days between scans
        GHAS_STATUS_UPDATED = "GHAS_Status_Updated"  # Property name for last scan timestamp

    class AlertProperties:
        """Repository property names for alert counts"""
        # Total alert counts
        CODE_ALERTS = "CodeAlerts"
        SECRET_ALERTS = "SecretAlerts"
        DEPENDENCY_ALERTS = "DependencyAlerts"

        # Code scanning alert severity levels
        CODE_ALERTS_CRITICAL = "CodeAlerts_Critical"
        CODE_ALERTS_HIGH = "CodeAlerts_High"
        CODE_ALERTS_MEDIUM = "CodeAlerts_Medium"
        CODE_ALERTS_LOW = "CodeAlerts_Low"

        # Secret scanning alerts (no standard severity levels)
        SECRET_ALERTS_TOTAL = "SecretAlerts_Total"
        SECRET_ALERTS_BY_TYPE = "SecretAlerts_By_Type"

        # Dependency alert severity levels
        DEPENDENCY_ALERTS_CRITICAL = "DependencyAlerts_Critical"
        DEPENDENCY_ALERTS_HIGH = "DependencyAlerts_High"
        DEPENDENCY_ALERTS_MODERATE = "DependencyAlerts_Moderate"
        DEPENDENCY_ALERTS_LOW = "DependencyAlerts_Low"

        @classmethod
        def get_all_properties(cls) -> List[Dict[str, str]]:
            """Return all property names as a list of dictionaries with name and description"""
            return [
                {"name": cls.CODE_ALERTS, "desc": "Total number of code scanning alerts"},
                {"name": cls.SECRET_ALERTS, "desc": "Total number of secret scanning alerts"},
                {"name": cls.DEPENDENCY_ALERTS, "desc": "Total number of dependency alerts"},
                {"name": cls.CODE_ALERTS_CRITICAL, "desc": "Number of critical code scanning alerts"},
                {"name": cls.CODE_ALERTS_HIGH, "desc": "Number of high code scanning alerts"},
                {"name": cls.CODE_ALERTS_MEDIUM, "desc": "Number of medium code scanning alerts"},
                {"name": cls.CODE_ALERTS_LOW, "desc": "Number of low code scanning alerts"},
                {"name": cls.SECRET_ALERTS_TOTAL, "desc": "Total number of secret scanning alerts"},
                {"name": cls.SECRET_ALERTS_BY_TYPE, "desc": "Number of secret scanning alerts by type"},
                {"name": cls.DEPENDENCY_ALERTS_CRITICAL, "desc": "Number of critical dependency alerts"},
                {"name": cls.DEPENDENCY_ALERTS_HIGH, "desc": "Number of high dependency alerts"},
                {"name": cls.DEPENDENCY_ALERTS_MODERATE, "desc": "Number of moderate dependency alerts"},
                {"name": cls.DEPENDENCY_ALERTS_LOW, "desc": "Number of low dependency alerts"},
            ]

    class AgentsHub:
        """MCP Agents Hub repository constants"""
        MCP_AGENTS_HUB_REPO_URL = "https://github.com/mcp-agents-ai/mcp-agents-hub.git"
        LOCAL_REPO_PATH = Path("./cloned_mcp_agents_hub")
        SERVER_FILES_DIR_PATH = Path("server/src/data/split")

    class Reports:
        """Report-related constants"""
        REPORT_DIR = "reports"  # Directory to save reports

# For backward compatibility, define global constants with the same names
# This allows existing code to continue working without changes, but
# new code should use the class-based constants
TARGET_ORG = Constants.Org.TARGET_ORG
GHAS_STATUS_UPDATED = Constants.ScanSettings.GHAS_STATUS_UPDATED
SCAN_FREQUENCY_DAYS = Constants.ScanSettings.SCAN_FREQUENCY_DAYS

CODE_ALERTS = Constants.AlertProperties.CODE_ALERTS
SECRET_ALERTS = Constants.AlertProperties.SECRET_ALERTS
DEPENDENCY_ALERTS = Constants.AlertProperties.DEPENDENCY_ALERTS

CODE_ALERTS_CRITICAL = Constants.AlertProperties.CODE_ALERTS_CRITICAL
CODE_ALERTS_HIGH = Constants.AlertProperties.CODE_ALERTS_HIGH
CODE_ALERTS_MEDIUM = Constants.AlertProperties.CODE_ALERTS_MEDIUM
CODE_ALERTS_LOW = Constants.AlertProperties.CODE_ALERTS_LOW

SECRET_ALERTS_TOTAL = Constants.AlertProperties.SECRET_ALERTS_TOTAL
SECRET_ALERTS_BY_TYPE = Constants.AlertProperties.SECRET_ALERTS_BY_TYPE

DEPENDENCY_ALERTS_CRITICAL = Constants.AlertProperties.DEPENDENCY_ALERTS_CRITICAL
DEPENDENCY_ALERTS_HIGH = Constants.AlertProperties.DEPENDENCY_ALERTS_HIGH
DEPENDENCY_ALERTS_MODERATE = Constants.AlertProperties.DEPENDENCY_ALERTS_MODERATE
DEPENDENCY_ALERTS_LOW = Constants.AlertProperties.DEPENDENCY_ALERTS_LOW

MCP_AGENTS_HUB_REPO_URL = Constants.AgentsHub.MCP_AGENTS_HUB_REPO_URL
LOCAL_REPO_PATH = Constants.AgentsHub.LOCAL_REPO_PATH
SERVER_FILES_DIR_PATH = Constants.AgentsHub.SERVER_FILES_DIR_PATH

REPORT_DIR = Constants.Reports.REPORT_DIR
