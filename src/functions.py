#!/usr/bin/env python3

import datetime
import logging
import os
import sys
from typing import Any, Dict

def should_scan_repository(properties: Dict[str, Any], timestamp_property: str, days_threshold: int) -> bool:
    """
    Determines if a repository should be scanned based on its last scan timestamp.
    
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
        last_scanned_time = datetime.datetime.fromisoformat(last_scanned)
        if datetime.datetime.now() - last_scanned_time > datetime.timedelta(days=days_threshold):
            logging.info(f"Repository was last scanned more than {days_threshold} days ago. Scanning...")
            return True
        else:
            logging.info(f"Repository was scanned within the last {days_threshold} days. Skipping...")
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