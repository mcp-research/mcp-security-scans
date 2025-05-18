#!/usr/bin/env python3

import ast
import os
import argparse
import logging
import datetime
import sys
from pathlib import Path
from typing import Any, Dict, List, Tuple, Optional
import json
import mimetypes
from dotenv import load_dotenv
from githubkit.exception import RequestFailed
from githubkit.versions.latest.models import FullRepository

# Import the local functions
from .github import (
    get_github_client,
    list_all_repositories_for_org,
    list_all_repository_properties_for_org,
    update_repository_properties,
    show_rate_limit,
    handle_github_api_error,
    clone_repository,
)
from .functions import should_scan_repository

# Configuration
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logging.getLogger("githubkit").setLevel(logging.DEBUG)  # Reduce verbosity from githubkit
load_dotenv()  # Load environment variables from .env file

# Constants
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
        alerts = gh.rest.paginate(
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
        alerts = gh.rest.paginate(
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
        alerts = gh.rest.paginate(
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

def scan_repository_for_alerts(gh: Any, repo: FullRepository, existing_repos_properties: List[Dict]) -> Tuple[bool, int, int, int]:
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

def scan_repo_for_mcp_composition(local_repo_path: Path) -> Optional[Dict]:
    # scan the repo to find a txt file that defines "mcpServers": {

    # find any file that has either '"mcpServers":{' or '"mcp":{"servers":{' in it.
    # search without spaces in the file content
    mcp_composition = None
    
    # Ensure the repo path exists
    if not local_repo_path.exists():
        logging.error(f"Repository path does not exist: [{local_repo_path}]")
        return None
        
    # Check if it's actually a directory
    if not local_repo_path.is_dir():
        logging.error(f"Repository path is not a directory: [{local_repo_path}]")
        return None
    
    logging.info(f"Scanning repository at [{local_repo_path}] for MCP composition")
    
    for root, dirs, files in os.walk(local_repo_path):
        for file in files:
            file_path = os.path.join(root, file)

            # Guess the MIME type of the file
            mime_type, _ = mimetypes.guess_type(file_path)

            # Only process text files and files with JSON MIME type
            # Also, explicitly allow files with no discernible MIME type (e.g. files without extensions, like 'LICENSE')
            # as they are often text-based. The subsequent read attempt will handle actual binary content.
            if mime_type is not None and not (mime_type.startswith('text/') or mime_type == 'application/json'):
                logging.debug(f"Skipping non-text file [{file_path}] with MIME type [{mime_type}]")
                continue

            try:
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
            except UnicodeDecodeError:
                try:
                    # If UTF-8 fails, try 'latin-1', which is more permissive
                    logging.warning(f"UTF-8 decoding failed for [{file_path}]. Trying 'latin-1'.")
                    with open(file_path, 'r', encoding='latin-1') as f:
                        content = f.read()
                except Exception as e_latin1:
                    # If both fail, log and skip the file
                    logging.error(f"Could not read file [{file_path}] with UTF-8 or latin-1: {e_latin1}")
                    continue # Skip to the next file
            except Exception as e:
                logging.error(f"Error reading file [{file_path}]: {e}")
                continue # Skip to the next file
            
            # strip all spaces/tabs/newlines from the content
            content = content.replace(" ", "").replace("\n", "").replace("\t", "")
            if '"mcpServers":{' in content or '"mcp":{"servers":{' in content:
                # grab the json string that contains the mcpServers information
                # search for the first '{' and the last '}' from where we found the search string
                start = content.find('"mcpServers":{')
                if start == -1:
                    start = content.find('"mcp":{"servers":{')
                if start != -1:
                    # check if there was an opening bracket before the search string
                    if content[start-1] == '{':
                        # if there was an opening bracket, find the start of the json string
                        start -= 1

                        # find the end of the json string by counting all the next opening { and finding as much } chars
                        end = start
                        open_brackets = 1
                        close_brackets = 0
                        while open_brackets != close_brackets:
                            end += 1
                            # Check if we've reached the end of the content
                            if end >= len(content):
                                logging.error(
                                    "Malformed JSON: Unclosed brackets in file"
                                )
                                mcp_composition = None
                                break
                            if content[end] == '{':
                                open_brackets += 1
                            elif content[end] == '}':
                                close_brackets += 1
                        # extract the json string
                        mcp_composition = content[start:end+1]
                        logging.info(f"Found MCP composition in file [{file_path}]")
                        logging.debug(f"MCP composition: {mcp_composition}")
                        # read the object from the json string
                        # cleanup already done during reading
                        clean_json_str = mcp_composition
                        try:
                            # Try to load the cleaned JSON string
                            mcp_composition = json.loads(clean_json_str)
                        except json.JSONDecodeError as e:
                            # If first attempt fails, try parsing as a raw string literal
                            logging.debug(f"Failed to parse JSON: {e}")
                            try:
                                # Try to evaluate as a raw string (useful for escaped sequences)
                                raw_str = ast.literal_eval(f"'''{clean_json_str}'''")
                                mcp_composition = json.loads(raw_str)
                            except Exception as e:
                                logging.error(f"Failed to parse MCP composition JSON: {e}")
                                logging.debug(f"Problematic JSON: {clean_json_str}")
                                mcp_composition = None
                        break
                
        if mcp_composition:
            break
    
    return mcp_composition

def get_composition_info(composition: Dict) -> Dict:
    """
    Extracts runtime command info from the MCP composition dict.
    Returns a dict with the first server's command and args, or empty if not found.
    """
    if not composition or "mcpServers" not in composition:
        return {}
    servers = composition["mcpServers"]
    for server_name, server_info in servers.items():
        command = server_info.get("command", "")
        # Initialize server_type with a default value
        server_type = "unknown"
        # Check for different command types
        if command.endswith("uv"):
            server_type = "uv"
        elif command == "npx":
            server_type = "npx"
            
        args = server_info.get("args", [])
        # Return info for the first server found
        return {"server": server_name, "server_type": server_type, "command": command, "args": args}
    return {}

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
        sys.exit(1)
    
    if not private_key:
        logging.error("GH_APP_PRIVATE_KEY environment variable not set.")
        sys.exit(1)
    
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
        
        # Track repositories where get_composition_info fails
        failed_analysis_repos = []

        logging.info(f"Found [{total_repos}] repositories in organization [{args.target_org}]")

        # Process repositories
        for idx, repo in enumerate(existing_repos):
            if scanned_repos >= args.num_repos:
                logging.info(f"Reached scan limit of [{args.num_repos}] repositories.")
                break
                
            logging.info(f"Processing repository {scanned_repos+1}/{min(total_repos, args.num_repos)}: {repo.name}")
            
            # Updated scan_repository call to get alert counts
            success, code_alerts, secret_alerts, dep_alerts = scan_repository_for_alerts(gh, repo, existing_repos_properties)

            # temporarily scan all repos for mcp configs, as we did not do so before
            # this code needs to move in the if success block later on
            # locate the default branch of the fork
            fork_default_branch = repo.default_branch if repo.fork else None

            # create the tmp directory if it doesn't exist
            tmp_dir = Path("tmp")
            if not tmp_dir.exists():
                tmp_dir.mkdir(parents=True, exist_ok=True)

            # clone the repo to a temp directory
            local_repo_path = Path(f"tmp/{repo.name}")
            clone_repository(gh, repo.owner.login, repo.name, fork_default_branch, local_repo_path)

            # Scan repository for MCP composition
            composition = scan_repo_for_mcp_composition(local_repo_path)
            if composition:
                logging.info(f"Found MCP composition in repository [{repo.name}]: {composition}")
                try:
                    runtime = get_composition_info(composition)
                    if runtime:
                        logging.info(f"MCP runtime info for [{repo.name}]: {runtime}")
                    else:
                        # Track failed analysis where get_composition_info returns empty dict
                        logging.warning(f"Failed to analyze MCP composition for [{repo.name}]: get_composition_info returned empty result")
                        failed_analysis_repos.append({"name": repo.name, "reason": "Empty result from get_composition_info"})
                except Exception as e:
                    logging.error(f"Error analyzing MCP composition for [{repo.name}]: {e}")
                    failed_analysis_repos.append({"name": repo.name, "reason": str(e)})
                    runtime = {}
            
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
            "**GHAS Alert Scanning Summary**",
            "Security Scan Results",
            f"- Organization: `{args.target_org}`",
            f"- Total MCP server configs: `{total_repos}`",
            f"- Total MCP servers found: `{total_repos}`",
            f"- Scan limit (--num-repos): `{args.num_repos}`",
            f"- Total repositories in organization: `{total_repos}`",
            f"- Repositories processed: `{scanned_repos + skipped_repos}`",
            f"- Repositories scanned: `{scanned_repos}`",
            f"- Repositories skipped (not forks or recently scanned): `{skipped_repos}`",
            f"- Total code scanning alerts found: `{total_code_alerts}`",
            f"- Total secret scanning alerts found: `{total_secret_alerts}`",
            f"- Total dependency vulnerability alerts found: `{total_dependency_alerts}`",
            f"- Total GHAS alerts across all scanned repos: `{total_code_alerts + total_secret_alerts + total_dependency_alerts}`",
            f"- Total execution time: `{duration}`",
            f"- Failed analysis repositories: `{len(failed_analysis_repos)}`"
        ]
        
        # Add a table with failed analysis repositories if any
        if failed_analysis_repos:
            summary_lines.append("**Failed Analysis Repositories**")
            summary_lines.append("| Repository | Reason |")
            summary_lines.append("| ---------- | ------ |")
            for repo in failed_analysis_repos:
                summary_lines.append(f"| {repo['name']} | {repo['reason']} |")
            summary_lines.append("\n")
        
        # Log summary to console
        logging.info("Scanning Summary")
        for line in summary_lines[1:]:  # Skip the markdown title for console
            logging.info(line.replace('`', '').replace('*', ''))  # Clean markdown for console
        
        # Log failed analysis repositories in a more readable format in console
        if failed_analysis_repos:
            logging.info("Failed Analysis Repositories:")
            for repo in failed_analysis_repos:
                logging.info(f"1. {repo['name']}: {repo['reason']}")
        
        show_rate_limit(gh)
        
        # Write summary to GITHUB_STEP_SUMMARY if available
        summary_file_path = os.getenv("GITHUB_STEP_SUMMARY")
        if summary_file_path:
            try:
                with open(summary_file_path, "a") as summary_file:  # Append mode
                    summary_file.write("\n".join(summary_lines) + "\n\n")
                logging.info(
                    "Successfully appended summary to GITHUB_STEP_SUMMARY file"
                )
            except Exception as e:
                logging.error(f"Failed to write to GITHUB_STEP_SUMMARY file: {e}")
        else:
            logging.info("GITHUB_STEP_SUMMARY environment variable not set. Skipping summary file output.")
        
    except Exception as e:
        logging.error(f"Script failed with an error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()