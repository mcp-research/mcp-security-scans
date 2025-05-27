import datetime
import os
import json
import argparse
import logging
from pathlib import Path
import requests
from bs4 import BeautifulSoup
from githubkit.exception import RequestFailed
from githubkit.versions.latest.models import FullRepository
from dotenv import load_dotenv
from typing import Any  # Or replace with specific githubkit client type
import time

# Import the local functions
from .github import get_github_client, enable_ghas_features, check_dependabot_config, clone_or_update_repo, extract_repo_owner_name, get_repository_properties, handle_github_api_error, list_all_repositories_for_org, list_all_repository_properties_for_org, show_rate_limit, update_repository_properties

# Configuration
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logging.getLogger("githubkit").setLevel(logging.WARNING)  # Reduce verbosity from githubkit
load_dotenv()  # Load environment variables from .env file

# Constants
MCP_AGENTS_HUB_REPO_URL = "https://github.com/mcp-agents-ai/mcp-agents-hub.git"
LOCAL_REPO_PATH = Path("./cloned_mcp_agents_hub")
server_files_from_loader_DIR_IN_REPO = Path("server/src/data/split")
TARGET_ORG = "mcp-research"  # The organization to fork into

# Collection of MCP server list loader functions
MCP_SERVER_LOADERS = []

def load_mcp_servers_from_mcp_agents_hub() -> list[Path]:
    """
    Loads MCP server configurations from the MCP Agents Hub repository.
    
    This function clones or updates the MCP Agents Hub repository and finds
    all JSON files in the specified directory within the repository.
    
    Returns:
        A list of Path objects pointing to the JSON files containing server configurations.
        Returns an empty list if no files are found or if there's an error.
    """
    # Clone or Update MCP Agents Hub repo
    newly_cloned = clone_or_update_repo(MCP_AGENTS_HUB_REPO_URL, LOCAL_REPO_PATH)
    if newly_cloned:
        logging.info(f"MCP Agents Hub repository newly cloned to [{LOCAL_REPO_PATH}]")
    else:
        logging.info(f"MCP Agents Hub repository at [{LOCAL_REPO_PATH}] already exists and was updated")
    
    # Find JSON files in the MCP Agents Hub repo
    json_dir = LOCAL_REPO_PATH / server_files_from_loader_DIR_IN_REPO
    if not json_dir.is_dir():
        logging.error(f"JSON directory not found: [{json_dir}]")
        return []

    server_repo = sorted(list(json_dir.glob("*.json"))) # Sort for consistent runs
    if not server_repo:
        logging.warning(f"No JSON files found in [{json_dir}]")
        return []
    
    logging.info(f"Found [{len(server_repo)}] JSON files in MCP Agents Hub repository")

    all_server_repos = []
    for json_file_path in server_repo:
        with open(json_file_path, 'r') as f:
            data = json.load(f)
            github_url = data.get("githubUrl")
            if github_url:
                all_server_repos.append(github_url)
            else:
                logging.warning(f"Skipping [{json_file_path.name}]: 'githubUrl' not found.")

    return all_server_repos

# Register the MCP Agents Hub loader
MCP_SERVER_LOADERS.append(load_mcp_servers_from_mcp_agents_hub)

def load_mcp_servers_from_awesome_mcp_servers() -> List[str]:
    """
    Loads MCP server configurations from the awesome-mcp-servers repository.
    
    This function fetches the README file from the awesome-mcp-servers repository
    and extracts GitHub URLs of MCP servers listed there.
    
    Returns:
        A list of GitHub URLs of MCP server repositories.
        Returns an empty list if no URLs are found or if there's an error.
    """
    awesome_mcp_repo_url = "https://github.com/punkpeye/awesome-mcp-servers"
    raw_readme_url = "https://raw.githubusercontent.com/punkpeye/awesome-mcp-servers/main/README.md"
    
    try:
        logging.info(f"Fetching awesome-mcp-servers list from [{raw_readme_url}]")
        
        # Fetch the raw README content
        response = requests.get(raw_readme_url)
        response.raise_for_status()  # Raise an exception for 4XX/5XX responses
        
        # Parse the content for URLs
        content = response.text
        
        # Get all GitHub repository URLs
        github_urls = []
        lines = content.split('\n')
        
        for line in lines:
            # Look for markdown links: [text](url)
            if '](https://github.com/' in line and not '](#' in line:  # Exclude internal links
                start_idx = line.find('](https://github.com/') + 2  # Position after ](
                end_idx = line.find(')', start_idx)
                if end_idx > start_idx:
                    url = line[start_idx:end_idx]
                    # Ensure it's a repo URL (contains exactly one / after github.com/)
                    parts = url.replace('https://github.com/', '').split('/')
                    if len(parts) >= 2 and parts[0] and parts[1]:  # Valid owner/repo format
                        github_urls.append(url)
        
        if not github_urls:
            logging.warning(f"No GitHub repository URLs found in awesome-mcp-servers README")
            return []
        
        logging.info(f"Found [{len(github_urls)}] GitHub URLs in awesome-mcp-servers README")
        return github_urls
        
    except requests.exceptions.RequestException as e:
        logging.error(f"Failed to fetch awesome-mcp-servers README: [{e}]")
        return []
    except Exception as e:
        logging.error(f"Error processing awesome-mcp-servers README: [{e}]")
        return []

# Register the awesome-mcp-servers loader
MCP_SERVER_LOADERS.append(load_mcp_servers_from_awesome_mcp_servers)

def ensure_repository_fork(
    existing_repos: list[FullRepository],
    gh: Any,
    source_owner: str,
    source_repo: str,
    target_org: str,
    target_repo_name: str,
    source_repo_full_name: str
) -> tuple[bool, bool, str]:
    """
    Checks if a fork exists in the target organization, creates it if not.

    Args:
        existing_repos: List of existing repositories in the target organization.
        gh: Authenticated GitHub client instance.
        source_owner: Owner of the source repository.
        source_repo: Name of the source repository.
        target_org: The target GitHub organization to fork into.
        target_repo_name: The desired name for the fork in the target organization.
        source_repo_full_name: The full name of the source repository (owner/repo).

    Returns:
        A tuple (fork_exists, fork_skipped, failure_reason):
        - fork_exists: True if the fork exists or was successfully created, False otherwise.
        - fork_skipped: True if a repository with the target name exists but is not the correct fork, False otherwise.
        - failure_reason: A string describing the reason for fork failure, empty if no failure occurred.
    """
    fork_exists = False
    fork_skipped = False
    failure_reason = ""  # Initialize failure reason string
    try:
        logging.info(f"Checking if fork exists for [{target_repo_name}] in [{target_org}]...")
        # check if the fork already exists in the exising_repos list
        search_name = f"{target_org}/{target_repo_name}".lower()
        target_repo_info = next((r for r in existing_repos if r.full_name.lower() == search_name), None)
        parent_full_name = get_parent_full_name(target_repo_info)

        # check if it's actually a fork of the correct source
        if target_repo_info and target_repo_info.fork and parent_full_name.lower() == source_repo_full_name.lower():
            logging.info(f"Fork [{target_org}/{target_repo_name}] already exists.")
            fork_exists = True
        elif target_repo_info: # repository exists but is not the correct fork
             logging.warning(f"Repository [{target_org}/{target_repo_name}] exists but is not a fork of [{source_repo_full_name}]. Skipping GHAS enablement.")
             fork_skipped = True # mark as skipped
        else: # repository does not exist
            logging.info(f"Fork [{target_org}/{target_repo_name}] does not exist. Creating fork...")
            try:
                # fork the repository
                gh.rest.repos.create_fork(
                    owner=source_owner,
                    repo=source_repo,
                    org=target_org, # specify the target organization
                    name=target_repo_name, # specify the new name for the fork
                    default_branch_only=True # fork only the default branch
                )
                logging.info(f"Fork creation initiated for [{source_repo_full_name}] into [{target_org}/{target_repo_name}]. API response status might be 202 Accepted.")
                # assume fork will be available shortly for subsequent steps
                fork_exists = True
            except RequestFailed as fork_error:
                # handle 404 specifically if the source repo doesn't exist or isn't accessible
                if fork_error.response.status_code == 404:
                    failure_reason = "Source repository not found or not accessible"
                    logging.error(f"Could not find source repository [{source_repo_full_name}] to fork.")
                else:
                    failure_reason = f"GitHub API error: {fork_error}"
                    handle_github_api_error(fork_error, f"forking [{source_repo_full_name}] to [{target_org}]")
                # fork creation failed
                fork_exists = False
            except Exception as fork_exc:
                failure_reason = f"Unexpected error: {fork_exc}"
                logging.error(f"Unexpected error forking [{source_repo_full_name}]: [{fork_exc}]")
                # fork creation failed
                fork_exists = False

    except RequestFailed as e:
        failure_reason = f"Error checking or creating fork: {e}"
        logging.error(f"Error checking or creating fork for [{source_repo_full_name}]: [{e}]")
        fork_exists = False
    except Exception as e:
        failure_reason = f"Unexpected error: {e}"
        logging.error(f"An unexpected error occurred checking or creating fork for [{source_repo_full_name}]: [{e}]")
        fork_exists = False

    return fork_exists, fork_skipped, failure_reason

def get_target_repo_name(source_owner: str, source_repo: str) -> str:
    """
    Generates the target repository name in the target organization.

    The target repository name is the same as the source repository name,
    but prefixed with the original owner and a double underscore.

    Args:
        source_owner: Owner of the source repository.
        source_repo: Name of the source repository.

    Returns:
        The target repository name in the target organization.
    """
    return f"{source_owner}__{source_repo}"

def get_parent_full_name(repo_info: FullRepository) -> str:
    """
    Extracts the full name of the parent repository from a fork.

    Args:
        repo_info: FullRepository object representing the fork.

    Returns:
        The full name of the parent repository if available in owner/repo setup, an empty string otherwise.
    """
    # split name on double underscore to get the original owner and repo
    if repo_info and repo_info.name:
        parts = repo_info.name.split("__")
        if len(parts) == 2:
            return f"{parts[0]}/{parts[1]}"
        
    return ""

def reprocess_repository(properties: dict) -> bool:
    """
    Checks if a repository should be reprocessed based on its properties.

    Args:
        properties: Dictionary of repository properties.

    Returns:
        True if the repository should be reprocessed, False otherwise.
    """
    # Check if the repository has been updated in the last 24 hours
    last_updated = properties.get("LastUpdated")
    if last_updated:
        if last_updated == "Testing":
            return True
        
        last_updated_time = datetime.datetime.fromisoformat(last_updated)
        if datetime.datetime.now() - last_updated_time < datetime.timedelta(days=7):
            logging.info("Repository was last updated within the last 7 days. Skipping reprocessing.")
            return False

    # Check if GHAS is already enabled
    ghas_enabled = properties.get("GHAS_Enabled")
    if ghas_enabled:
        logging.info("GHAS features are already enabled. Skipping reprocessing.")
        return False

    # Check if Dependabot config is already present
    dependabot_configured = properties.get("HasDependabotConfig")
    if dependabot_configured:
        logging.info("Dependabot configuration is already present. Skipping reprocessing.")
        return False

    # Reprocess if none of the above conditions are met
    return True

def update_forked_repo(gh: Any, target_org: str, target_repo_name: str):
    """
    Updates the forked repository with changes from the upstream source.

    Args:
        gh: Authenticated GitHub client instance.
        target_org: The target GitHub organization where the fork is located.
        target_repo_name: The name of the forked repository in the target organization.
    """
    try:
        # first we need to locate the default branch of the fork
        fork_info = gh.rest.repos.get(
            owner=target_org,
            repo=target_repo_name
        )

        fork_default_branch = None
        if not fork_info.default_branch:
            logging.warning(f"Could not find default branch for [{target_org}/{target_repo_name}]. Skipping update.")
            return
        else:
            fork_default_branch = fork_info.default_branch

        if fork_default_branch:
            logging.info(f"Updating forked repository: [{target_org}/{target_repo_name}]")
            gh.rest.repos.update_branch(
                owner=target_org,
                repo=target_repo_name,
                branch=fork_default_branch, # update the default branch
                expected_head=fork_default_branch # ensure the branch is at the default head
            )
            logging.info(f"Successfully updated forked repository: [{target_org}/{target_repo_name}]")
    except RequestFailed as e:
        handle_github_api_error(e, f"updating forked repository [{target_org}/{target_repo_name}]")
    except Exception as e:
        logging.error(f"An unexpected error occurred updating forked repository [{target_org}/{target_repo_name}]: [{e}]")

def process_repository(
    existing_repos: list[FullRepository],
    github_url: str,
    gh: Any, # Replace Any with the actual type of the GitHub client
    target_org: str,
    existing_repos_properties: list[dict],
    processed_repos: set[str],
    failed_forks: dict[str, str] # Changed to dict to store repo name -> failure reason
) -> tuple[int, int, bool, bool]:
    """
    Processes a single repository based on data from a JSON file.

    Args:
        existing_repos: List of existing repositories in the target organization.
        githubUrl: url to the GitHub url to analyze.
        gh: Authenticated GitHub client instance.
        target_org: The target GitHub organization to fork into.
        existing_repos_properties: List of repository properties.
        processed_repos: A set of already processed source repository full names (e.g., "owner/repo").
        failed_forks: A dict mapping repository names to their failure reasons.

    Returns:
        A tuple (processed_increment, dependabot_increment, skipped_non_fork, failed_fork)
    """
    processed_increment = 0
    dependabot_increment = 0
    skipped_non_fork = False
    failed_fork = False
    source_repo_full_name = None # Keep track of the source repo name for adding to the set

    try:
        if not github_url:
            logging.warning(f"Skipping empty githubUrl.")
            return 0, 0, False, False # No processing, not skipped/failed in the specific ways tracked

        source_owner, source_repo = extract_repo_owner_name(github_url)
        if not source_owner or not source_repo:
            logging.warning(f"Could not parse owner/repo from URL '[{github_url}]'.")
            return 0, 0, False, False # No processing

        source_repo_full_name = f"{source_owner}/{source_repo}"
        if source_repo_full_name in processed_repos:
            logging.info(f"Skipping duplicate source repository: [{source_repo_full_name}]")
            # Return 0,0 but indicate it was processed previously (not skipped/failed *this time*)
            return 0, 0, False, False

        # Keep the same repo name in the target org, but prefix it with the original owner and a double underscore
        target_repo_name = get_target_repo_name(source_owner, source_repo)

        # Check if fork exists or create it
        fork_exists, fork_skipped_flag, failure_reason = ensure_repository_fork(
            existing_repos, gh, source_owner, source_repo, target_org, target_repo_name, source_repo_full_name
        )

        # If fork creation failed or check failed, ensure_repository_fork returns fork_exists=False
        if not fork_exists:
            if fork_skipped_flag:
                # Repo exists but isn't the correct fork. Mark as skipped.
                skipped_non_fork = True
                logging.warning(f"Skipping GHAS enablement for [{target_org}/{target_repo_name}] as it's not the correct fork.")
                # Add to processed_repos so we don't try again with this source
                processed_repos.add(source_repo_full_name)
                return 0, 0, skipped_non_fork, False # Return skipped status
            else:
                # Fork creation/check genuinely failed.
                failed_fork = True
                logging.error(f"Failed to ensure fork exists for [{source_repo_full_name}]. Skipping further processing.")
                # Add to failed_forks with the specific reason
                failed_forks[source_repo_full_name] = failure_reason or "Fork creation/check failed"
                # Don't add to processed_repos because we might want to retry later
                return 0, 0, False, failed_fork # Return failed status

        # --- If we reach here, fork_exists is True ---

        # Add the *source* repo name to the set to track processed sources *before* checking properties/reprocessing
        # This ensures even if we skip due to recent update/GHAS already enabled, we count it as "encountered"
        processed_repos.add(source_repo_full_name)

        # load the repository properties to check if we need to do something
        properties = get_repository_properties(gh, target_org, target_repo_name, existing_repos_properties)
        if properties:
            # check if we still need to process this repository or not
            if not reprocess_repository(properties):
                 logging.info(f"Skipping reprocessing for [{target_org}/{target_repo_name}] based on properties.")
                 # It was processed successfully before, return 0 for *new* processing this run
                 # Return False for skipped/failed as it was handled correctly
                 return 0, 0, False, False
        else:
            # properties not found, so have not been set yet
            logging.info(f"No properties found for [{target_org}/{target_repo_name}]. Processing...")

        # If fork exists and needs processing (or properties check passed)
        logging.info(f"Processing source repository: [{source_repo_full_name}] (Target: [{target_org}/{target_repo_name}])")

        # Update the fork with upstream changes
        update_forked_repo(gh, target_org, target_repo_name)

        # Wait 3 seconds to allow the fork to update with latest alerts
        logging.info("Waiting for fork to update with latest changes...")
        time.sleep(3)

        enable_ghas_features(gh, target_org, target_repo_name)
        dependabot_configured = check_dependabot_config(gh, target_org, target_repo_name)
        if dependabot_configured:
            dependabot_increment = 1

        properties_to_update = {
            "GHAS_Enabled": True,
            "LastUpdated": datetime.datetime.now().isoformat(),
            "HasDependabotConfig": dependabot_configured
        }
        update_repository_properties(gh, target_org, target_repo_name, properties_to_update)
        processed_increment = 1 # Mark as successfully processed *this run*

    except json.JSONDecodeError:
        error_reason = f"Invalid JSON in file {json_file_path.name}"
        logging.error(f"Skipping [{json_file_path.name}]: Invalid JSON.")
        failed_forks[source_repo_full_name] = error_reason if source_repo_full_name else error_reason
        failed_fork = True
    except Exception as e:
        error_reason = f"Unexpected error: {str(e)}"
        logging.error(f"An unexpected error occurred processing [{json_file_path.name}]: [{e}]")
        if source_repo_full_name:
            failed_forks[source_repo_full_name] = error_reason
        processed_increment = 0
        dependabot_increment = 0
        failed_fork = True

    # Return all counts and flags
    return processed_increment, dependabot_increment, skipped_non_fork, failed_fork

# Main Logic

def main():
    start_time = datetime.datetime.now() # Record start time
    parser = argparse.ArgumentParser(description="Fork MCP Hub repos and enable GHAS features.")
    # Removed app-id and private-key-path arguments
    parser.add_argument("--target-org", default=TARGET_ORG, help=f"Target GitHub organization to fork into (default: {TARGET_ORG})")
    parser.add_argument("--num-repos", type=int, default=3, help="Number of repositories to process (default: 3 for local runs)")

    args = parser.parse_args()

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
        # Authentication
        gh = get_github_client(app_id, private_key)

        # Load all existing repos from the target org
        existing_repos = list_all_repositories_for_org(gh, args.target_org)
        existing_repos_properties = list_all_repository_properties_for_org(gh, args.target_org)
        initial_repo_count = len(existing_repos) # Store initial count

        # Use all registered MCP server loaders to collect JSON files
        all_server_repos = []
        
        # Loop through all registered MCP server loaders
        for loader_func in MCP_SERVER_LOADERS:
            logging.info(f"Loading MCP servers using: {loader_func.__name__}")
            server_files_from_loader = loader_func()
            if server_files_from_loader:
                all_server_repos.extend(server_files_from_loader)
        
        # Deduplicate JSON files (in case multiple sources have the same file)
        all_server_repos = sorted(list(set(all_server_repos)))
        
        if not all_server_repos:
            logging.error("No MCP server configurations found. Exiting.")
            return

        # Limit based on the --num-repos argument
        num_to_process = args.num_repos
        logging.info(f"Found a total of [{len(all_server_repos)}] JSON files from all sources. Will process up to [{num_to_process}] repositories based on --num-repos.")

        # Process Repos
        processed_repo_count = 0 # Counter for successfully processed repos (forked/found + GHAS attempted)
        dependabot_enabled_count = 0
        processed_repos = set() # Keep track of processed source repos to avoid duplicates
        skipped_non_fork_count = 0 # Track repos skipped because they exist but aren't the correct fork
        failed_fork_count = 0 # Track repos where fork creation/check failed
        failed_forks = dict() # Dict to collect repositories that failed to fork with reasons

        # Iterate over all JSON files until the desired number is processed
        for github_url in all_server_repos:
            # Check if we have processed enough repos
            if processed_repo_count >= num_to_process:
                logging.info(f"Reached processing limit of [{num_to_process}] repositories.")
                break

            # Call the helper function to process this specific repo
            processed_inc, dependabot_inc, skipped_non_fork, failed_fork = process_repository(
                existing_repos,
                github_url,
                gh,
                args.target_org,
                existing_repos_properties,
                processed_repos, # Pass the set (it will be modified in place)
                failed_forks # Pass the dict to collect failed forks with reasons
            )

            # Update counters based on the result from the helper function
            processed_repo_count += processed_inc
            dependabot_enabled_count += dependabot_inc
            skipped_non_fork_count += 1 if skipped_non_fork else 0
            failed_fork_count += 1 if failed_fork else 0
            if processed_inc or skipped_non_fork or failed_fork: # Log separator only if something happened
                 logging.info("")

        # Reporting
        logging.info("")
        end_time = datetime.datetime.now() # Record end time
        duration = end_time - start_time
        final_repo_count = len(list_all_repositories_for_org(gh, args.target_org)) # Get updated count

        # Prepare summary messages
        summary_lines = [
            f"**MCP Repository Processing Summary**",
            "Security Scan Results",
            f"- Total MCP server configs found: `{len(all_server_repos)}`",
            f"- Total MCP servers found: `{len(processed_repos)}`",
            f"- Processing Limit (--num-repos): `{num_to_process}`",
            f"- Unique source repositories encountered: `{len(processed_repos)}`",
            f"- New repositories successfully processed (forked/found & GHAS enabled): `{processed_repo_count}`",
            f"- Repositories skipped (exist but not correct fork): `{skipped_non_fork_count}`",
            f"- Repositories failed (fork creation/check error): `{failed_fork_count}`",
            f"- Repositories among processed with Dependabot config: `{dependabot_enabled_count}`",
            f"- Initial repositories in target org `{args.target_org}`: `{initial_repo_count}`",
            f"- Final repositories in target org `{args.target_org}`: `{final_repo_count}`",
            f"- Total execution time: `{duration}`"
        ]

        # Add failed forks list with reasons if any exist
        if failed_forks:
            summary_lines.append("Failed Repository Details:")
            for failed_repo, reason in sorted(failed_forks.items()): # Sort for consistent output
                summary_lines.append(f"1. `{failed_repo}`: {reason}")

        # Log summary to console
        logging.info("Processing Summary")
        for line in summary_lines[1:]: # Skip the markdown title for console
            logging.info(line.replace('`', '').replace('*', '')) # Clean markdown for console
        show_rate_limit(gh)
        logging.info(f"Total execution time: [{duration}]") # Repeat duration for clarity

        # Write summary to GITHUB_STEP_SUMMARY if available
        summary_file_path = os.getenv("GITHUB_STEP_SUMMARY")
        if summary_file_path:
            try:
                with open(summary_file_path, "a") as summary_file: # Append mode
                    summary_file.write("\n".join(summary_lines) + "\n\n")
                logging.info(f"Successfully appended summary to GITHUB_STEP_SUMMARY file: [{summary_file_path}]")
            except Exception as e:
                logging.error(f"Failed to write to GITHUB_STEP_SUMMARY file [{summary_file_path}]: [{e}]")
        else:
            logging.info("GITHUB_STEP_SUMMARY environment variable not set. Skipping summary file output.")


    except Exception as e:
        logging.error(f"Script failed with an error: [{e}]")

if __name__ == "__main__":
    main()
