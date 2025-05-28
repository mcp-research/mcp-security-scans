#!/usr/bin/env python3

import datetime
import logging
import os
import sys
from typing import Any, Dict

def should_scan_repository(properties: Dict[str, Any], timestamp_property: str, days_threshold: int) -> bool:
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
        logging.info("Repository has never been scanned. Scanning...")
        return True
        
    if last_scanned == "Testing":
        logging.info("Repository is marked for testing. Scanning...")
        return True
    
    try:
        # Strip whitespace from timestamp before parsing to handle gracefully
        # Only call strip if last_scanned is a string
        if isinstance(last_scanned, str):
            timestamp_str = last_scanned.strip()
            
            # Try parsing with fromisoformat first
            try:
                last_scanned_time = datetime.datetime.fromisoformat(timestamp_str)
            except ValueError:
                # If that fails, try adding UTC timezone indicator and parse again
                # This handles timestamps without timezone info like "2025-05-28T20:36:15.994131"
                if timestamp_str.endswith('Z') or '+' in timestamp_str or timestamp_str.count(':') >= 3:
                    # Already has timezone info, re-raise the original error
                    raise
                else:
                    # Try adding 'Z' to indicate UTC
                    last_scanned_time = datetime.datetime.fromisoformat(timestamp_str + 'Z')
        else:
            # If it's not a string, try to parse it directly (this will likely fail for non-string types)
            last_scanned_time = datetime.datetime.fromisoformat(last_scanned)
        if datetime.datetime.now() - last_scanned_time > datetime.timedelta(days=days_threshold):
            logging.info(f"Repository was last scanned more than {days_threshold} days ago. Scanning...")
            return True
        else:
            # Additional conditions to check if we need to rescan despite recent timestamp
            
            # Check code scanning alerts
            code_alerts = properties.get("CodeAlerts", 0)
            if code_alerts > 0:
                # Check if any of the severity breakdowns are missing
                has_critical = "CodeAlerts_Critical" in properties
                has_high = "CodeAlerts_High" in properties
                has_medium = "CodeAlerts_Medium" in properties
                has_low = "CodeAlerts_Low" in properties
                
                if not (has_critical and has_high and has_medium and has_low):
                    logging.info("Repository has code alerts but missing severity breakdowns. Scanning...")
                    return True
            
            # Check secret scanning alerts
            # Both conditions: SecretAlerts_Total not set OR (SecretAlerts_Total > 0 and SecretAlerts_By_Type not set)
            secret_alerts_total = properties.get("SecretAlerts_Total")
            secret_alerts_by_type = properties.get("SecretAlerts_By_Type")
            
            if secret_alerts_total is None:
                logging.info("Repository is missing secret alerts total. Scanning...")
                return True
                
            if secret_alerts_total > 0 and secret_alerts_by_type is None:
                logging.info("Repository has secret alerts but missing type breakdown. Scanning...")
                return True
            
            # Check dependency alerts
            dependency_alerts = properties.get("DependencyAlerts", 0)
            if dependency_alerts > 0:
                # Check if any of the severity breakdowns are missing
                has_critical = "DependencyAlerts_Critical" in properties
                has_high = "DependencyAlerts_High" in properties
                has_moderate = "DependencyAlerts_Moderate" in properties
                has_low = "DependencyAlerts_Low" in properties
                
                if not (has_critical and has_high and has_moderate and has_low):
                    logging.info("Repository has dependency alerts but missing severity breakdowns. Scanning...")
                    return True
            
            logging.info(f"Repository was scanned within the last {days_threshold} days and has complete data. Skipping...")
            return False
    except (ValueError, TypeError):
        logging.warning(f"Invalid timestamp format: {last_scanned}. Scanning...")
        return True

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