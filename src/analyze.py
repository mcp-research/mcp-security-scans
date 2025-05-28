#!/usr/bin/env python3

import argparse
import datetime
import json
import logging
import mimetypes
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from dotenv import load_dotenv
from githubkit import GitHub
from githubkit.exception import RequestFailed
from githubkit.versions.latest.models import FullRepository
from githubkit import GitHub

from .functions import should_scan_repository
from .github import (
    get_github_client,
    list_all_repositories_for_org,
    list_all_repository_properties_for_org,
    update_repository_properties,
    show_rate_limit,
    handle_github_api_error,
    clone_repository,
    create_issue,
)
from .constants import Constants

# Configuration
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logging.getLogger("githubkit").setLevel(logging.DEBUG)
load_dotenv()

# Constants
TARGET_ORG = "mcp-research"  # The organization to scan
GHAS_STATUS_UPDATED = "GHAS_Status_Updated"  # Property name for last scan timestamp

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
SECRET_ALERTS_BY_TYPE = "SecretAlerts_By_Type"

# Property names for dependency alerts by severity
DEPENDENCY_ALERTS_CRITICAL = "DependencyAlerts_Critical"
DEPENDENCY_ALERTS_HIGH = "DependencyAlerts_High"
DEPENDENCY_ALERTS_MODERATE = "DependencyAlerts_Moderate"
DEPENDENCY_ALERTS_LOW = "DependencyAlerts_Low"

SCAN_FREQUENCY_DAYS = 7  # Minimum days between scans


def get_code_scanning_alerts(gh: Any, owner: str, repo: str) -> Dict[str, int]:
    """
    Gets the count of code scanning alerts for a repository, categorized by severity.

    Args:
        gh: Authenticated GitHub client instance.
        owner: Owner of the repository.
        repo: Repository name.

    Returns:
        Dictionary with counts of open code scanning alerts by severity.
    """
    # Initialize result dictionary with all severity counts set to 0
    result = {
        "total": 0,
        "critical": 0,
        "high": 0,
        "medium": 0,
        "low": 0,
    }

    try:
        # Get code scanning alerts with state=open
        alerts = list(gh.rest.paginate(
            gh.rest.code_scanning.list_alerts_for_repo,
            owner=owner,
            repo=repo,
            state='open'
        ))

        result["total"] = len(alerts)

        # Count alerts by severity
        for alert in alerts:
            # Convert severity to lowercase for case-insensitive comparison
            severity = alert.rule.severity.lower() if alert.rule and alert.rule.severity else "unknown"

            if severity == "critical":
                result["critical"] += 1
            elif severity == "high":
                result["high"] += 1
            elif severity == "medium":
                result["medium"] += 1
            elif severity == "low":
                result["low"] += 1
            # Map additional severity levels: warning, note -> low, error -> medium (as it needs attention)
            elif severity == "warning" or severity == "note":
                result["low"] += 1
            elif severity == "error":
                result["medium"] += 1

        logging.info(f"Found [{result['total']}] open code scanning alerts for [{owner}/{repo}], " +
                     f"by severity: Critical: {result['critical']}, High: {result['high']}, " +
                     f"Medium: {result['medium']} (includes 'medium' and 'error'), " +
                     f"Low: {result['low']} (includes 'low', 'warning', and 'note').")

        return result

    except RequestFailed as e:
        if e.response.status_code == 404:
            logging.info(f"Code scanning not enabled or no alerts found for [{owner}/{repo}]")
            return result
        else:
            handle_github_api_error(e, f"getting code scanning alerts for [{owner}/{repo}]")
            return result
    except Exception as e:
        logging.error(f"Unexpected error getting code scanning alerts for [{owner}/{repo}]: {e}")
        return result

def get_secret_scanning_alerts(gh: Any, owner: str, repo: str) -> Dict[str, int]:
    """
    Gets the count of secret scanning alerts for a repository, categorized by type.

    Args:
        gh: Authenticated GitHub client instance.
        owner: Owner of the repository.
        repo: Repository name.

    Returns:
        Dictionary with count of open secret scanning alerts, both total and by type.
    """
    # Initialize result dictionary
    result = {
        "total": 0,
        "types": {}
    }

    try:
        # Get secret scanning alerts with state=open
        alerts = list(gh.rest.paginate(
            gh.rest.secret_scanning.list_alerts_for_repo,
            owner=owner,
            repo=repo,
            state='open'
        ))

        result["total"] = len(alerts)

        # Count alerts by secret type
        for alert in alerts:
            secret_type = alert.secret_type_display_name or alert.secret_type or "Unknown"
            if secret_type in result["types"]:
                result["types"][secret_type] += 1
            else:
                result["types"][secret_type] = 1

        logging.info(f"Found [{result['total']}] open secret scanning alerts for [{owner}/{repo}]")
        if result["total"] > 0:
            type_counts = ", ".join([f"{t}: {c}" for t, c in result["types"].items()])
            logging.info(f"Secret types for [{owner}/{repo}]: {type_counts}")
        return result

    except RequestFailed as e:
        if e.response.status_code == 404:
            logging.info(f"Secret scanning not enabled or no alerts found for [{owner}/{repo}]")
            return result
        else:
            handle_github_api_error(e, f"getting secret scanning alerts for [{owner}/{repo}]")
            return result
    except Exception as e:
        logging.error(f"Unexpected error getting secret scanning alerts for [{owner}/{repo}]: {e}")
        return result

def get_dependency_alerts(gh: Any, owner: str, repo: str) -> Dict[str, int]:
    """
    Gets the count of dependency vulnerability alerts for a repository, categorized by severity.

    Args:
        gh: Authenticated GitHub client instance.
        owner: Owner of the repository.
        repo: Repository name.

    Returns:
        Dictionary with counts of open dependency vulnerability alerts by severity.
    """
    # Initialize result dictionary with all severity counts set to 0
    result = {
        "total": 0,
        "critical": 0,
        "high": 0,
        "moderate": 0,
        "low": 0,
    }

    try:
        # Get dependency vulnerability alerts
        alerts = list(gh.rest.paginate(
            gh.rest.dependabot.list_alerts_for_repo,
            owner=owner,
            repo=repo,
            state='open'
        ))

        result["total"] = len(alerts)

        # Count alerts by severity
        for alert in alerts:
            # Get the severity from the vulnerability, normalized to lowercase
            severity = alert.security_vulnerability.severity.lower() if alert.security_vulnerability and alert.security_vulnerability.severity else "unknown"

            if severity == "critical":
                result["critical"] += 1
            elif severity == "high":
                result["high"] += 1
            elif severity == "moderate" or severity == "medium":
                result["moderate"] += 1
            elif severity == "low":
                result["low"] += 1

        logging.info(f"Found [{result['total']}] open dependency alerts for [{owner}/{repo}], " +
                     f"by severity: Critical: {result['critical']}, High: {result['high']}, " +
                     f"Moderate: {result['moderate']}, Low: {result['low']}")

        return result

    except RequestFailed as e:
        if e.response.status_code == 404:
            logging.info(f"Dependency scanning not enabled or no alerts found for [{owner}/{repo}]")
            return result
        else:
            handle_github_api_error(e, f"getting dependency alerts for [{owner}/{repo}]")
            return result
    except Exception as e:
        logging.error(f"Unexpected error getting dependency alerts for [{owner}/{repo}]: {e}")
        return result

def scan_repository_for_alerts(gh: Any, repo: FullRepository, existing_repos_properties: List[Dict]) -> Tuple[bool, Dict[str, int], Dict[str, int], Dict[str, int]]:
    """
    Scans a single repository for GHAS alerts and updates its properties.

    Args:
        gh: Authenticated GitHub client instance.
        repo: Repository object to scan.
        existing_repos_properties: List of all repository properties in the org.

    Returns:
        A tuple (success, code_alerts, secret_alerts, dependency_alerts):
        - success: True if scanning and updating were successful, False otherwise
        - code_alerts: Dictionary with code scanning alerts by severity
        - secret_alerts: Dictionary with secret scanning alerts count
        - dependency_alerts: Dictionary with dependency vulnerability alerts by severity
    """
    owner = repo.owner.login if repo.owner else Constants.Org.TARGET_ORG
    repo_name = repo.name

    # Initialize alert counts with empty dictionaries
    code_alerts = {
        "total": 0,
        "critical": 0,
        "high": 0,
        "medium": 0,
        "low": 0,
    }

    secret_alerts = {"total": 0}

    dependency_alerts = {
        "total": 0,
        "critical": 0,
        "high": 0,
        "moderate": 0,
        "low": 0,
    }

    try:
        # Check if this is a fork - we only want to scan forks
        if not repo.fork:
            logging.info(f"Repository {owner}/{repo_name} is not a fork. Skipping.")
            return False, code_alerts, secret_alerts, dependency_alerts

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
        if not should_scan_repository(properties, Constants.ScanSettings.GHAS_STATUS_UPDATED, Constants.ScanSettings.SCAN_FREQUENCY_DAYS):
            return False, code_alerts, secret_alerts, dependency_alerts

        logging.info(f"Scanning repository {owner}/{repo_name} for GHAS alerts...")

        # Get alert counts with severity breakdowns
        code_alerts = get_code_scanning_alerts(gh, owner, repo_name)
        secret_alerts = get_secret_scanning_alerts(gh, owner, repo_name)
        dependency_alerts = get_dependency_alerts(gh, owner, repo_name)

        # Update repository properties with counts and timestamp
        properties_to_update = {
            # Total counts for backward compatibility
            Constants.AlertProperties.CODE_ALERTS: code_alerts["total"],
            Constants.AlertProperties.SECRET_ALERTS: secret_alerts["total"],
            Constants.AlertProperties.DEPENDENCY_ALERTS: dependency_alerts["total"],
            
            # Code scanning alerts by severity
            Constants.AlertProperties.CODE_ALERTS_CRITICAL: code_alerts["critical"],
            Constants.AlertProperties.CODE_ALERTS_HIGH: code_alerts["high"],
            Constants.AlertProperties.CODE_ALERTS_MEDIUM: code_alerts["medium"],
            Constants.AlertProperties.CODE_ALERTS_LOW: code_alerts["low"],
            
            # Secret scanning alerts (only total for now)
            Constants.AlertProperties.SECRET_ALERTS_TOTAL: secret_alerts["total"],
            # Store secret types as a JSON string
            Constants.AlertProperties.SECRET_ALERTS_BY_TYPE: json.dumps(secret_alerts["types"]) if secret_alerts["types"] else "{}",
            
            # Dependency scanning alerts by severity
            Constants.AlertProperties.DEPENDENCY_ALERTS_CRITICAL: dependency_alerts["critical"],
            Constants.AlertProperties.DEPENDENCY_ALERTS_HIGH: dependency_alerts["high"],
            Constants.AlertProperties.DEPENDENCY_ALERTS_MODERATE: dependency_alerts["moderate"],
            Constants.AlertProperties.DEPENDENCY_ALERTS_LOW: dependency_alerts["low"],

            # Update timestamp
            Constants.ScanSettings.GHAS_STATUS_UPDATED: datetime.datetime.now().isoformat()
        }

        update_repository_properties(gh, owner, repo_name, properties_to_update)
        logging.info(f"Successfully updated GHAS alert counts for [{owner}/{repo_name}]")

        return True, code_alerts, secret_alerts, dependency_alerts

    except Exception as e:
        logging.error(f"Failed to scan repository [{owner}/{repo_name}]: {e}")
        return False, code_alerts, secret_alerts, dependency_alerts

def scan_repo_for_mcp_composition(local_repo_path: Path) -> tuple[Optional[Dict], Optional[Dict]]:
    """
    Scans a repository for MCP composition configuration.

    Args:
        local_repo_path: Path to the local repository.

    Returns:
        A tuple containing:
        - The parsed MCP composition as a Dict or None if not found
        - A Dict with error details if an error occurred, or None if successful
          Error details include: repo_path, filename, json_config, error_message
    """
    # scan the repo to find a txt file that defines "mcpServers": {

    # find any file that has either '"mcpServers":{' or '"mcp":{"servers":{' in it.
    # search without spaces in the file content
    mcp_composition = None
    error_details = None

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
                # Try reading with UTF-8 first
                with open(file_path, 'r', encoding='utf-8') as f:
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
                    continue  # Skip to the next file
            except Exception as e:
                logging.error(f"Error reading file [{file_path}]: {e}")
                continue  # Skip to the next file

            # strip all spaces/tabs/newlines from the content for searching
            stripped_content = content.replace(" ", "").replace("\n", "").replace("\t", "")
            if '"mcpServers":{' in stripped_content or '"mcp":{"servers":{' in stripped_content:
                # grab the json string that contains the mcpServers information
                # search for the first '{' and the last '}' from where we found the search string
                start = stripped_content.find('"mcpServers":{')
                if start == -1:
                    start = stripped_content.find('"mcp":{"servers":{')
                if start != -1:
                    # check if there was an opening bracket before the search string
                    if stripped_content[start - 1] == '{':
                        # if there was an opening bracket, find the start of the json string
                        start -= 1

                        # find the end of the json string by counting all the next opening { and finding as much } chars
                        end = start
                        open_brackets = 1
                        close_brackets = 0
                        while open_brackets != close_brackets:
                            end += 1
                            # Check if we've reached the end of the content
                            if end >= len(stripped_content):
                                error_msg = "Malformed JSON: Unclosed brackets in file"
                                logging.error(error_msg)
                                error_details = {
                                    "repo_path": str(local_repo_path),
                                    "filename": file_path,
                                    "json_config": stripped_content[start:],  # Include everything from start
                                    "error_message": error_msg
                                }
                                mcp_composition = None
                                break
                            if stripped_content[end] == '{':
                                open_brackets += 1
                            elif stripped_content[end] == '}':
                                close_brackets += 1

                        # If we didn't break out due to error
                        if error_details is None:
                            # extract the json string
                            json_str = stripped_content[start:end + 1]
                            logging.info(f"Found MCP composition in file [{file_path}]")
                            logging.debug(f"MCP composition: {json_str}")

                            # Store the original file content for error reporting
                            original_content = content

                            # read the object from the json string
                            try:
                                # Try to load the cleaned JSON string
                                mcp_composition = json.loads(json_str)
                            except json.JSONDecodeError as e:
                                # If first attempt fails, try parsing as a raw string literal
                                logging.debug(f"Failed to parse JSON: {e}")
                                try:
                                    # Try to evaluate as a raw string (useful for escaped sequences)
                                    import ast
                                    raw_str = ast.literal_eval(f"'''{json_str}'''")
                                    mcp_composition = json.loads(raw_str)
                                except Exception as e:
                                    error_msg = f"Failed to parse MCP composition JSON: {e}"
                                    logging.error(error_msg)
                                    error_details = {
                                        "repo_path": str(local_repo_path),
                                        "filename": file_path,
                                        "json_config": original_content,  # Use the original content for better context
                                        "error_message": error_msg
                                    }
                                    mcp_composition = None
                            break  # We found a composition file, so break the file loop

        # If we found a composition or hit an error, break the directory loop
        if mcp_composition is not None or error_details is not None:
            break

    return mcp_composition, error_details

def get_composition_info(composition: Dict) -> tuple[Dict, Optional[Dict]]:
    """
    Extracts runtime command info from the MCP composition dict.
    Returns a tuple containing:
    - A dict with the first server's command and args, or empty if not found.
    - A dict with error details if an error occurred, or None if successful
    """
    error_details = None

    try:
        if not composition:
            error_details = {
                "error_message": "Empty composition provided"
            }
            return {}, error_details

        if "mcpServers" not in composition:
            error_details = {
                "error_message": "Missing 'mcpServers' key in composition",
                "json_config": json.dumps(composition, indent=2)
            }
            return {}, error_details

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
            return {"server": server_name, "server_type": server_type, "command": command, "args": args}, None

        # If we get here, there were no servers in the mcpServers object
        error_details = {
            "error_message": "No servers found in 'mcpServers' object",
            "json_config": json.dumps(composition, indent=2)
        }
        return {}, error_details
    except Exception as e:
        error_details = {
            "error_message": f"Exception analyzing composition: {str(e)}",
            "json_config": json.dumps(composition, indent=2) if composition else "None"
        }
        return {}, error_details

def main():
    """Main execution function."""
    start_time = datetime.datetime.now()

    parser = argparse.ArgumentParser(description="Scan repositories for GHAS alerts and store in repository properties.")
    parser.add_argument("--target-org", default=Constants.Org.TARGET_ORG,
                        help=f"Target GitHub organization to scan (default: [{Constants.Org.TARGET_ORG}])")
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

        # Initialize alert counters for total counts
        total_code_alerts = 0
        total_secret_alerts = 0
        total_dependency_alerts = 0

        # Initialize alert counters for severity breakdowns
        total_code_alerts_by_severity = {
            "critical": 0,
            "high": 0,
            "medium": 0,
            "low": 0,
        }

        total_dependency_alerts_by_severity = {
            "critical": 0,
            "high": 0,
            "moderate": 0,
            "low": 0,
        }

        # Track repositories where get_composition_info fails
        failed_analysis_repos = []

        logging.info(f"Found [{total_repos}] repositories in organization [{args.target_org}]")

        # Process repositories
        for idx, repo in enumerate(existing_repos):
            if scanned_repos >= args.num_repos:
                logging.info(f"Reached scan limit of [{args.num_repos}] repositories.")
                break

            logging.info(f"Processing repository {scanned_repos + 1}/{min(total_repos, args.num_repos)}: {repo.name}")

            # Updated scan_repository call to get alert counts
            success, code_alerts, secret_alerts, dependency_alerts = scan_repository_for_alerts(gh, repo, existing_repos_properties)

            if success:
                scanned_repos += 1

                # Get the default branch and GitHub token
                fork_default_branch = repo.default_branch if repo else "main"
                github_token = os.getenv("GITHUB_TOKEN")
                token_auth_gh = None

                if github_token:
                    # Create a GitHub client authenticated with the token for issue creation
                    token_auth_gh = GitHub(github_token)
                    logging.info("Created GitHub client with token for issue creation if needed")
                else:
                    logging.warning("GITHUB_TOKEN environment variable not set. Cannot create issues for analysis failures if needed.")

                # clone the repo to a temp directory
                local_repo_path = Path(f"tmp/{repo.name}")
                clone_repository(gh, repo.owner.login, repo.name, fork_default_branch, local_repo_path)

                # Scan repository for MCP composition
                composition, scan_error = scan_repo_for_mcp_composition(local_repo_path)

                # Handle scan errors (when scan finds a file but fails to parse it)
                if scan_error:
                    error_msg = scan_error.get("error_message", "Unknown error")
                    logging.error(f"Failed to scan MCP composition in repository [{repo.name}]: {error_msg}")

                    # Add to failed analysis repos list
                    failed_analysis_repos.append({
                        "name": repo.name,
                        "reason": error_msg,
                        "file": os.path.basename(scan_error.get("filename", "unknown"))
                    })

                    # Create a GitHub issue for the failure if token is available
                    if token_auth_gh:
                        issue_title = f"Failed analysis: {error_msg}"
                        issue_body = f"""
# MCP Composition Analysis Failure

- **Repository**: {repo.name}
- **File**: {os.path.basename(scan_error.get("filename", "unknown"))}
- **Error**: {error_msg}

## JSON Configuration
```json
{scan_error.get("json_config", "Not available")}
```
                        """

                        create_issue(token_auth_gh, args.target_org, "mcp-security-scans",
                                     issue_title, issue_body, ["analysis-failure"])

                # If scan was successful but found a composition
                elif composition:
                    logging.info(f"Found MCP composition in repository [{repo.name}]")
                    try:
                        runtime, analysis_error = get_composition_info(composition)

                        # Handle analysis errors
                        if analysis_error or not runtime:
                            error_msg = analysis_error.get("error_message", "Unknown error") if analysis_error else "Empty result from get_composition_info"
                            logging.warning(f"Failed to analyze MCP composition for [{repo.name}]: {error_msg}")

                            # Add to failed analysis repos list
                            failed_analysis_repos.append({
                                "name": repo.name,
                                "reason": error_msg
                            })

                            # Create a GitHub issue for the failure if token is available
                            if token_auth_gh:
                                issue_title = f"Failed analysis: {error_msg}"
                                json_config = analysis_error.get("json_config", json.dumps(composition, indent=2)) if analysis_error else json.dumps(composition, indent=2)

                                issue_body = f"""
# MCP Composition Analysis Failure

- **Repository**: {repo.name}
- **Error**: {error_msg}

## JSON Configuration
```json
{json_config}
```
                                """

                                create_issue(token_auth_gh, args.target_org, "mcp-security-scans", issue_title, issue_body, ["analysis-failure"])
                        else:
                            logging.info(f"MCP runtime info for [{repo.name}]: {runtime}")
                    except Exception as e:
                        # Catch any unexpected exceptions during the analysis
                        error_msg = f"Unexpected error: {str(e)}"
                        logging.error(f"Error analyzing MCP composition for [{repo.name}]: {e}")

                        # Add to failed analysis repos list
                        failed_analysis_repos.append({
                            "name": repo.name,
                            "reason": error_msg
                        })

                        # Create a GitHub issue for the failure if token is available
                        if token_auth_gh:
                            issue_title = f"Failed analysis: {error_msg}"
                            issue_body = f"""
# MCP Composition Analysis Failure

- **Repository**: {repo.name}
- **Error**: {error_msg}

## JSON Configuration
```json
{json.dumps(composition, indent=2)}
```
                            """

                            create_issue(token_auth_gh, args.target_org, "mcp-security-scans", issue_title, issue_body, ["analysis-failure"])
                else:
                    logging.info(f"No MCP composition found in repository [{repo.name}]")
                    runtime = {}

                # Add alerts to totals if scan was successful
                total_code_alerts += code_alerts["total"]
                total_secret_alerts += secret_alerts["total"]
                total_dependency_alerts += dependency_alerts["total"]

                # Add alerts by severity
                for severity in total_code_alerts_by_severity:
                    total_code_alerts_by_severity[severity] += code_alerts.get(severity, 0)

                for severity in total_dependency_alerts_by_severity:
                    total_dependency_alerts_by_severity[severity] += dependency_alerts.get(severity, 0)
            else:
                skipped_repos += 1

            logging.info("")  # Add a blank line for readability

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
            "",
            "**Code Scanning Alerts by Severity**",
            f"- Critical: `{total_code_alerts_by_severity['critical']}`",
            f"- High: `{total_code_alerts_by_severity['high']}`",
            f"- Medium: `{total_code_alerts_by_severity['medium']}`",
            f"- Low: `{total_code_alerts_by_severity['low']}`",
            "",
            "**Dependency Scanning Alerts by Severity**",
            f"- Critical: `{total_dependency_alerts_by_severity['critical']}`",
            f"- High: `{total_dependency_alerts_by_severity['high']}`",
            f"- Moderate: `{total_dependency_alerts_by_severity['moderate']}`",
            f"- Low: `{total_dependency_alerts_by_severity['low']}`",
            "",
            f"- Total execution time: `{duration}`",
            f"- Failed analysis repositories: `{len(failed_analysis_repos)}`"
        ]

        # Add a table with failed analysis repositories if any
        if failed_analysis_repos:
            summary_lines.append("")  # Add empty line for proper markdown rendering
            summary_lines.append("**Failed Analysis Repositories**")
            summary_lines.append("")
            summary_lines.append("| Repository | File | Reason |")
            summary_lines.append("| ---------- | ---- | ------ |")
            for repo in failed_analysis_repos:
                file_name = repo.get('file', '')
                file_col = f" {file_name} " if file_name else " - "
                summary_lines.append(f"| {repo['name']} |{file_col}| {repo['reason']} |")
            summary_lines.append("\n")

        # Log summary to console
        logging.info("Scanning Summary")
        for line in summary_lines[1:]:  # Skip the markdown title for console
            logging.info(line.replace('`', '').replace('*', ''))  # Clean markdown for console

        # Log failed analysis repositories in a more readable format in console
        if failed_analysis_repos:
            logging.info("Failed Analysis Repositories:")
            for repo in failed_analysis_repos:
                file_str = f" (file: {repo.get('file')})" if 'file' in repo else ""
                logging.info(f"1. {repo['name']}{file_str}: {repo['reason']}")

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
