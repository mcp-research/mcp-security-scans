#!/usr/bin/env python3

import datetime
import logging
import os
import sys
from typing import Any, Dict

from .constants import Constants


def parse_timestamp(timestamp_value: Any) -> datetime.datetime:
    """
    Parses a timestamp value into a datetime object.

    Args:
        timestamp_value: A timestamp value, can be a string or other type.

    Returns:
        datetime.datetime: The parsed timestamp.

    Raises:
        ValueError: If the timestamp cannot be parsed.
        TypeError: If the timestamp is not a valid type.
    """
    if not timestamp_value:
        raise ValueError("No timestamp provided")

    if timestamp_value == "Testing":
        raise ValueError("Testing flag")

    # Strip whitespace from timestamp before parsing to handle gracefully
    # Only call strip if timestamp_value is a string
    if isinstance(timestamp_value, str):
        timestamp_str = timestamp_value.strip()

        # Try parsing with fromisoformat first
        try:
            return datetime.datetime.fromisoformat(timestamp_str)
        except ValueError:
            # If that fails, try handling Z suffix (UTC indicator)
            if timestamp_str.endswith('Z'):
                # Replace 'Z' with '+00:00' for UTC timezone
                try:
                    return datetime.datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
                except ValueError:
                    # If that still fails, re-raise the original error
                    raise
            # If no 'Z' suffix and no timezone info, try adding UTC indicator
            elif '+' not in timestamp_str and timestamp_str.count(':') < 3:
                # Try adding 'Z' to indicate UTC, then convert to +00:00
                try:
                    return datetime.datetime.fromisoformat(timestamp_str + '+00:00')
                except ValueError:
                    # If that fails, re-raise the original error
                    raise
            else:
                # Already has timezone info or other format, re-raise the original error
                raise
    else:
        # Non-string values cannot be parsed by fromisoformat
        raise ValueError(f"Expected string timestamp, got {type(timestamp_value).__name__}")


def should_scan_repository_for_MCP_Composition(properties: Dict[str, Any], timestamp_property: str, days_threshold: int) -> bool:
    """
    Determines if a repository should be scanned for MCP composition based on its last update timestamp
    and whether MCP_Server_Runtime has been set.

    Args:
        properties: Dictionary of repository properties.
        timestamp_property: Name of the timestamp property to check (should be 'LastUpdated').
        days_threshold: Minimum days between scans.

    Returns:
        True if the repository should be scanned, False otherwise.
    """
    last_updated = properties.get(timestamp_property)

    if not last_updated:
        logging.info("Repository has never been updated. Scanning for MCP composition...")
        return True

    if last_updated == "Testing":
        logging.info("Repository is marked for testing. Scanning for MCP composition...")
        return True

    try:
        last_updated_time = parse_timestamp(last_updated)
        if datetime.datetime.now() - last_updated_time > datetime.timedelta(days=days_threshold):
            logging.info(f"Repository was last updated more than [{days_threshold}] days ago. Scanning...")
            return True
        else:
            mcp_server_runtime = properties.get("MCP_Server_Runtime")
            if mcp_server_runtime is None or mcp_server_runtime == "":
                logging.info("Repository is missing MCP_Server_Runtime value. Scanning...")
                return True
            logging.info(f"Repository was updated within the last [{days_threshold}] days and has MCP_Server_Runtime set. Skipping scanning for MCP composition...")
            return False
    except (ValueError, TypeError) as e:
        logging.warning(f"Error checking if this repo needs to be rescanned for MCP composition: [{e}]")
        return True


def _parse_alert_count(value: Any, alert_type: str) -> int:
    """Helper function to parse alert count values, handling 'None' strings."""
    if value == "None" or value is None:
        return 0
    try:
        return int(value)
    except (ValueError, TypeError):
        logging.info(f"Repository has invalid {alert_type} values. Scanning GHAS alerts...")
        return -1  # Special value to indicate parsing error


def _check_code_alerts_completeness(properties: Dict[str, Any]) -> bool:
    """Check if code alerts data is complete."""
    code_alerts = _parse_alert_count(properties.get("CodeAlerts", 0), "code alerts")
    if code_alerts == -1:
        return False  # Parsing error, need to scan

    if code_alerts > 0:
        # Check if any of the severity breakdowns are missing
        required_properties = ["CodeAlerts_Critical", "CodeAlerts_High", "CodeAlerts_Medium", "CodeAlerts_Low"]
        missing_properties = [prop for prop in required_properties if prop not in properties]
        if missing_properties:
            logging.info("Repository has code alerts but missing severity breakdowns. Scanning GHAS alerts...")
            return False
    return True


def _check_secret_alerts_completeness(properties: Dict[str, Any]) -> bool:
    """Check if secret alerts data is complete."""
    if "SecretAlerts_Total" not in properties:
        logging.info("Repository is missing secret alerts total. Scanning GHAS alerts...")
        return False

    secret_alerts_total = _parse_alert_count(properties.get("SecretAlerts_Total", 0), "secret alerts")
    if secret_alerts_total == -1:
        return False  # Parsing error, need to scan

    if secret_alerts_total > 0:
        secret_alerts_by_type = properties.get("SecretAlerts_By_Type")
        # Handle case where SecretAlerts_By_Type is stored as string "None" or missing/empty
        if (secret_alerts_by_type is None or secret_alerts_by_type == "None"
                or secret_alerts_by_type == "{}" or secret_alerts_by_type == ""):
            logging.info("Repository has secret alerts but missing type breakdown. Scanning GHAS alerts...")
            return False
    return True


def _check_dependency_alerts_completeness(properties: Dict[str, Any]) -> bool:
    """Check if dependency alerts data is complete."""
    dependency_alerts = _parse_alert_count(properties.get("DependencyAlerts", 0), "dependency alerts")
    if dependency_alerts == -1:
        return False  # Parsing error, need to scan

    if dependency_alerts > 0:
        # Check if any of the severity breakdowns are missing
        required_properties = ["DependencyAlerts_Critical", "DependencyAlerts_High",
                               "DependencyAlerts_Moderate", "DependencyAlerts_Low"]
        missing_properties = [prop for prop in required_properties if prop not in properties]
        if missing_properties:
            logging.info("Repository has dependency alerts but missing severity breakdowns. Scanning GHAS alerts...")
            return False
    return True


def should_scan_repository_for_GHAS_alerts(properties: Dict[str, Any], timestamp_property: str, days_threshold: int) -> bool:
    """
    Determines if a repository should be scanned based on its last scan timestamp
    and completeness of alert data.

    Args:
        properties: Dictionary of repository properties.
        timestamp_property: Name of the timestamp property to check.
        days_threshold: Minimum days between scans.

    Returns:
        True if the repository should be scanned, False otherwise.
    """
    # Check if the repository has been scanned in the last X days
    last_scanned = properties.get(timestamp_property)

    if not last_scanned:
        logging.info("Repository has never been scanned. Scanning GHAS alerts...")
        return True

    if last_scanned == "Testing":
        logging.info("Repository is marked for testing. Scanning GHAS alerts...")
        return True

    try:
        last_scanned_time = parse_timestamp(last_scanned)

        if datetime.datetime.now() - last_scanned_time > datetime.timedelta(days=days_threshold):
            logging.info(f"Repository was last scanned more than [{days_threshold}] days ago. Scanning GHAS alerts...")
            return True
        else:
            # Additional conditions to check if we need to rescan despite recent timestamp
            # Check all alert types for completeness
            if not _check_code_alerts_completeness(properties):
                return True
            if not _check_secret_alerts_completeness(properties):
                return True
            if not _check_dependency_alerts_completeness(properties):
                return True

            logging.info(f"Repository was scanned within the last [{days_threshold}] days and has complete data. Skipping GHAS scan...")
            return False
    except (ValueError, TypeError) as e:
        logging.warning(f"Error checking if this repo needs to be rescanned or not: [{e}]")
        return True


def get_repository_properties(existing_repos_properties: list, repo, gh: Any) -> Dict[str, Any]:

    owner = repo.owner.login if repo.owner else Constants.Org.TARGET_ORG
    repo_name = repo.name

    # Get existing properties - fixed to handle the custom properties structure correctly
    properties = {}
    try:
        # Search in the existing properties list
        for repo_properties in existing_repos_properties:
            # todo: there has to be a quicker way to do this then a for loop?
            if (repo_properties.repository_name == repo_name):
                # Extract properties from the custom properties object
                for prop in repo_properties.properties:
                    properties[prop.property_name] = prop.value
                logging.info(f"Found existing custom properties for {owner}/{repo_name}")
                break

        # If no properties found in the cached list, fetch directly
        if not properties:
            response = gh.rest.repos.get_custom_properties_values(
                owner=owner,
                repo=repo_name
            )
            props = response.json()
            for prop in props:
                properties[prop["property_name"]] = prop["value"]

        return properties

    except Exception as prop_error:
        logging.warning(f"Error retrieving properties for {owner}/{repo_name}: {prop_error}")
        return {}


def is_running_interactively() -> bool:
    """
    Determines if the script is running in an interactive environment.

    Returns:
        True if running interactively (terminal, debugger, etc.), False in CI environments.
    """
    # Check for common CI environment variables
    if os.environ.get('GITHUB_ACTION') or os.environ.get('CI'):
        return False

    # Check if running in a terminal or if a debugger is attached
    is_tty = sys.stdin.isatty() and sys.stdout.isatty()
    has_debugger = sys.gettrace() is not None

    return is_tty or has_debugger


def log_separator():
    """
    Logs a separator line to visually separate log messages.
    """
    logging.info("------------------------------------------------------------")
