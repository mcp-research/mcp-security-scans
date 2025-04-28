#!/usr/bin/env python3

import os
import argparse
import logging
import datetime
from pathlib import Path
from typing import Any, Dict, List, Tuple, Optional
from dotenv import load_dotenv
from githubkit.exception import RequestFailed
from githubkit.versions.latest.models import FullRepository

# Import the local functions
from github import (
    get_github_client, list_all_repositories_for_org,
    list_all_repository_properties_for_org, get_repository_properties,
    update_repository_properties, show_rate_limit, handle_github_api_error
)
from functions import should_scan_repository

# --- Configuration ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logging.getLogger("githubkit").setLevel(logging.WARNING)  # Reduce verbosity from githubkit
load_dotenv()  # Load environment variables from .env file

# --- Constants ---
TARGET_ORG = "mcp-research"  # The organization to scan
GHAS_STATUS_UPDATED = "GHAS_Status_Updated"  # Property name for last scan timestamp
CODE_ALERTS = "CodeAlerts"  # Property name for code scanning alerts
SECRET_ALERTS = "SecretAlerts"  # Property name for secret scanning alerts
DEPENDENCY_ALERTS = "DependencyAlerts"  # Property name for dependency alerts
SCAN_FREQUENCY_DAYS = 7  # Minimum days between scans

def get_code_scanning_alerts(gh: Any, owner: str, repo: str) -> int:
    """
    Gets the count of code scanning alerts for a repository.
    
    Args:
        gh: Authenticated GitHub client instance.
        owner: Owner of the repository.
        repo: Repository name.
        
    Returns:
        Number of open code scanning alerts.
    """
    try:
        # Get code scanning alerts with state=open
        alerts = gh.paginate(
            gh.rest.code_scanning.list_alerts_for_repo,
            owner=owner,
            repo=repo,
            state='open'
        )
        
        # Count the alerts
        alert_count = sum(1 for _ in alerts)
        logging.info(f"Found [{alert_count}] open code scanning alerts for [{owner}/{repo}]")
        return alert_count
        
    except RequestFailed as e:
        if e.response.status_code == 404:
            logging.info(f"Code scanning not enabled or no alerts found for [{owner}/{repo}]")
            return 0
        else:
            handle_github_api_error(e, f"getting code scanning alerts for [{owner}/{repo}]")
            return 0
    except Exception as e:
        logging.error(f"Unexpected error getting code scanning alerts for [{owner}/{repo}]: {e}")
        return 0

def get_secret_scanning_alerts(gh: Any, owner: str, repo: str) -> int:
    """
    Gets the count of secret scanning alerts for a repository.
    
    Args:
        gh: Authenticated GitHub client instance.
        owner: Owner of the repository.
        repo: Repository name.
        
    Returns:
        Number of open secret scanning alerts.
    """
    try:
        # Get secret scanning alerts with state=open
        alerts = gh.paginate(
            gh.rest.secret_scanning.list_alerts_for_repo,
            owner=owner,
            repo=repo,
            state='open'
        )
        
        # Count the alerts
        alert_count = sum(1 for _ in alerts)
        logging.info(f"Found [{alert_count}] open secret scanning alerts for [{owner}/{repo}]")
        return alert_count
        
    except RequestFailed as e:
        if e.response.status_code == 404:
            logging.info(f"Secret scanning not enabled or no alerts found for [{owner}/{repo}]")
            return 0
        else:
            handle_github_api_error(e, f"getting secret scanning alerts for [{owner}/{repo}]")
            return 0
    except Exception as e:
        logging.error(f"Unexpected error getting secret scanning alerts for [{owner}/{repo}]: {e}")
        return 0

def get_dependency_alerts(gh: Any, owner: str, repo: str) -> int:
    """
    Gets the count of dependency vulnerability alerts for a repository.
    
    Args:
        gh: Authenticated GitHub client instance.
        owner: Owner of the repository.
        repo: Repository name.
        
    Returns:
        Number of open dependency vulnerability alerts.
    """
    try:
        # Get dependency vulnerability alerts
        alerts = gh.paginate(
            gh.rest.dependabot.list_alerts_for_repo,
            owner=owner,
            repo=repo,
            state='open'
        )
        
        # Count the alerts
        alert_count = sum(1 for _ in alerts)
        logging.info(f"Found [{alert_count}] open dependency alerts for [{owner}/{repo}]")
        return alert_count
        
    except RequestFailed as e:
        if e.response.status_code == 404:
            logging.info(f"Dependency scanning not enabled or no alerts found for [{owner}/{repo}]")
            return 0
        else:
            handle_github_api_error(e, f"getting dependency alerts for [{owner}/{repo}]")
            return 0
    except Exception as e:
        logging.error(f"Unexpected error getting dependency alerts for [{owner}/{repo}]: {e}")
        return 0

def scan_repository(gh: Any, repo: FullRepository, existing_repos_properties: List[Dict]) -> Tuple[bool, int, int, int]:
    """
    Scans a single repository for GHAS alerts and updates its properties.
    
    Args:
        gh: Authenticated GitHub client instance.
        repo: Repository object to scan.
        existing_repos_properties: List of all repository properties in the org.
        
    Returns:
        A tuple (success, code_alerts, secret_alerts, dependency_alerts):
        - success: True if scanning and updating were successful, False otherwise
        - code_alerts: Number of code scanning alerts found
        - secret_alerts: Number of secret scanning alerts found
        - dependency_alerts: Number of dependency vulnerability alerts found
    """
    owner = repo.owner.login if repo.owner else TARGET_ORG
    repo_name = repo.name
    
    # Initialize alert counts to 0
    code_alerts = 0
    secret_alerts = 0
    dependency_alerts = 0
    
    try:
        # Check if this is a fork - we only want to scan forks
        if not repo.fork:
            logging.info(f"Repository {owner}/{repo_name} is not a fork. Skipping.")
            return False, 0, 0, 0
            
        # Get existing properties - fixed to handle the custom properties structure correctly
        properties = {}
        try:
            # Search in the existing properties list
            for repo_properties in existing_repos_properties:
                if (repo_properties.repository_full_name == f"{owner}/{repo_name}"):
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
                logging.info(f"Fetched custom properties for {owner}/{repo_name}")
        except Exception as prop_error:
            logging.warning(f"Error retrieving properties for {owner}/{repo_name}: {prop_error}")
            # Continue with empty properties
        
        # Check if we should scan this repository based on timestamp
        if not should_scan_repository(properties, GHAS_STATUS_UPDATED, SCAN_FREQUENCY_DAYS):
            return False, 0, 0, 0
            
        logging.info(f"Scanning repository {owner}/{repo_name} for GHAS alerts...")
        
        # Get alert counts
        code_alerts = get_code_scanning_alerts(gh, owner, repo_name)
        secret_alerts = get_secret_scanning_alerts(gh, owner, repo_name)
        dependency_alerts = get_dependency_alerts(gh, owner, repo_name)
        
        # Update repository properties with counts and timestamp
        properties_to_update = {
            CODE_ALERTS: code_alerts,
            SECRET_ALERTS: secret_alerts,
            DEPENDENCY_ALERTS: dependency_alerts,
            GHAS_STATUS_UPDATED: datetime.datetime.now().isoformat()
        }
        
        update_repository_properties(gh, owner, repo_name, properties_to_update)
        logging.info(f"Successfully updated GHAS alert counts for [{owner}/{repo_name}]")
        
        return True, code_alerts, secret_alerts, dependency_alerts
        
    except Exception as e:
        logging.error(f"Failed to scan repository [{owner}/{repo_name}]: {e}")
        return False, 0, 0, 0

def main():
    """Main execution function."""
    start_time = datetime.datetime.now()
    
    parser = argparse.ArgumentParser(description="Scan repositories for GHAS alerts and store in repository properties.")
    parser.add_argument("--target-org", default=TARGET_ORG, 
                        help=f"Target GitHub organization to scan (default: [{TARGET_ORG}])")
    parser.add_argument("--num-repos", type=int, default=10, 
                        help="Maximum number of repositories to scan (default: 10)")
    parser.add_argument("--verbose", "-v", action="store_true", 
                        help="Enable verbose logging")
    
    args = parser.parse_args()
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
        logging.getLogger("githubkit").setLevel(logging.INFO)
    
    # Load credentials from environment variables
    app_id = os.getenv("GH_APP_ID")
    private_key = os.getenv("GH_APP_PRIVATE_KEY")
    
    if not app_id:
        logging.error("GH_APP_ID environment variable not set.")
        return
    
    if not private_key:
        logging.error("GH_APP_PRIVATE_KEY environment variable not set.")
        return
    
    try:
        # --- Authentication ---
        gh = get_github_client(app_id, private_key)
        
        # --- Load repositories and properties ---
        logging.info(f"Loading repositories and properties for organization [{args.target_org}]...")
        existing_repos = list_all_repositories_for_org(gh, args.target_org)
        existing_repos_properties = list_all_repository_properties_for_org(gh, args.target_org)
        
        # Initialize counters
        total_repos = len(existing_repos)
        scanned_repos = 0
        skipped_repos = 0
        
        # Initialize alert counters
        total_code_alerts = 0
        total_secret_alerts = 0
        total_dependency_alerts = 0
        
        logging.info(f"Found {total_repos} repositories in organization {args.target_org}")
        
        # Process repositories
        for idx, repo in enumerate(existing_repos):
            if scanned_repos >= args.num_repos:
                logging.info(f"Reached scan limit of [{args.num_repos}] repositories.")
                break
                
            logging.info(f"Processing repository {idx+1}/{min(total_repos, args.num_repos)}: {repo.name}")
            
            # Updated scan_repository call to get alert counts
            success, code_alerts, secret_alerts, dep_alerts = scan_repository(gh, repo, existing_repos_properties)
            
            if success:
                scanned_repos += 1
                # Add alerts to totals if scan was successful
                total_code_alerts += code_alerts
                total_secret_alerts += secret_alerts
                total_dependency_alerts += dep_alerts
            else:
                skipped_repos += 1
                
            logging.info("") # Add a blank line for readability
        
        # --- Generate summary ---
        end_time = datetime.datetime.now()
        duration = end_time - start_time
        
        summary_lines = [
            f"**GHAS Alert Scanning Summary**",
            f"---------------------------",
            f"- Organization: `{args.target_org}`",
            f"- Scan limit (--num-repos): `{args.num_repos}`",
            f"- Total repositories in organization: `{total_repos}`",
            f"- Repositories processed: `{scanned_repos + skipped_repos}`",
            f"- Repositories scanned: `{scanned_repos}`",
            f"- Repositories skipped (not forks or recently scanned): `{skipped_repos}`",
            f"- Total code scanning alerts found: `{total_code_alerts}`",
            f"- Total secret scanning alerts found: `{total_secret_alerts}`",
            f"- Total dependency vulnerability alerts found: `{total_dependency_alerts}`",
            f"- Total GHAS alerts across all scanned repos: `{total_code_alerts + total_secret_alerts + total_dependency_alerts}`",
            f"- Total execution time: `{duration}`"
        ]
        
        # Log summary to console
        logging.info("Scanning Summary")
        for line in summary_lines[1:]:  # Skip the markdown title for console
            logging.info(line.replace('`', '').replace('*', ''))  # Clean markdown for console
        
        show_rate_limit(gh)
        
        # Write summary to GITHUB_STEP_SUMMARY if available
        summary_file_path = os.getenv("GITHUB_STEP_SUMMARY")
        if summary_file_path:
            try:
                with open(summary_file_path, "a") as summary_file:  # Append mode
                    summary_file.write("\n".join(summary_lines) + "\n\n")
                logging.info(f"Successfully appended summary to GITHUB_STEP_SUMMARY file")
            except Exception as e:
                logging.error(f"Failed to write to GITHUB_STEP_SUMMARY file: {e}")
        else:
            logging.info("GITHUB_STEP_SUMMARY environment variable not set. Skipping summary file output.")
        
    except Exception as e:
        logging.error(f"Script failed with an error: {e}")

if __name__ == "__main__":
    main()