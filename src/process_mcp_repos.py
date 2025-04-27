import datetime
import os
import json
import argparse
import logging
from pathlib import Path
from githubkit.exception import RequestError, RequestFailed, RequestTimeout
from githubkit.versions.latest.models import FullRepository
from dotenv import load_dotenv
from typing import Any # Or replace with specific githubkit client type

# Import the local functions
from github import get_github_client, get_installation_github_client, enable_ghas_features, check_dependabot_config, clone_or_update_repo, extract_repo_owner_name, get_repository_properties, handle_github_api_error, list_all_repositories_for_org, show_rate_limit, update_repository_properties 

# --- Configuration ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logging.getLogger("githubkit").setLevel(logging.WARNING) # Reduce verbosity from githubkit
load_dotenv() # Load environment variables from .env file

# --- Constants ---
MCP_AGENTS_HUB_REPO_URL = "https://github.com/mcp-agents-ai/mcp-agents-hub.git"
LOCAL_REPO_PATH = Path("./cloned_mcp_agents_hub")
JSON_FILES_DIR_IN_REPO = Path("server/src/data/split")
TARGET_ORG = "mcp-research" # The organization to fork into

def ensure_repository_fork(
    existing_repos: list[FullRepository],
    gh: Any,
    source_owner: str,
    source_repo: str,
    target_org: str,
    target_repo_name: str,
    source_repo_full_name: str
) -> tuple[bool, bool]:
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
        A tuple (fork_exists, fork_skipped):
        - fork_exists: True if the fork exists or was successfully created, False otherwise.
        - fork_skipped: True if a repository with the target name exists but is not the correct fork, False otherwise.
    """
    fork_exists = False
    fork_skipped = False
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
                fork_response = gh.rest.repos.create_fork(
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
                     logging.error(f"Could not find source repository [{source_repo_full_name}] to fork.")
                else:
                    handle_github_api_error(fork_error, f"forking [{source_repo_full_name}] to [{target_org}]")
                # fork creation failed
                fork_exists = False
            except Exception as fork_exc:
                 logging.error(f"Unexpected error forking [{source_repo_full_name}]: [{fork_exc}]")
                 # fork creation failed
                 fork_exists = False

    except RequestFailed as e:
        logging.error(f"Error checking or creating fork for [{source_repo_full_name}]: [{e}]")
        fork_exists = False
    except Exception as e:
        logging.error(f"An unexpected error occurred checking or creating fork for [{source_repo_full_name}]: [{e}]")
        fork_exists = False

    return fork_exists, fork_skipped

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

def process_repository_from_json(
    existing_repos: list[FullRepository],
    json_file_path: Path,
    gh: Any, # Replace Any with the actual type of the GitHub client
    target_org: str,
    processed_repos: set[str]
) -> tuple[int, int, bool, bool]: # Added bool returns for skipped_non_fork and failed_fork
    """
    Processes a single repository based on data from a JSON file.

    Checks for duplicates, handles forking, enables GHAS, checks Dependabot,
    and updates the set of processed repositories.

    Args:
        existing_repos: List of existing repositories in the target organization.
        json_file_path: Path to the JSON file containing repository info.
        gh: Authenticated GitHub client instance.
        target_org: The target GitHub organization to fork into.
        processed_repos: A set of already processed source repository full names (e.g., "owner/repo").
                         This set will be modified by this function.

    Returns:
        A tuple (processed_increment, dependabot_increment, skipped_non_fork, failed_fork):
        - processed_increment: 1 if the repository was successfully processed (forked/found + GHAS attempted), 0 otherwise.
        - dependabot_increment: 1 if Dependabot config was found among processed, 0 otherwise.
        - skipped_non_fork: True if skipped because repo exists but isn't correct fork, False otherwise.
        - failed_fork: True if fork creation/check failed, False otherwise.
    """
    processed_increment = 0
    dependabot_increment = 0
    skipped_non_fork = False
    failed_fork = False
    source_repo_full_name = None # Keep track of the source repo name for adding to the set

    try:
        with open(json_file_path, 'r') as f:
            data = json.load(f)

        github_url = data.get("githubUrl")
        if not github_url:
            logging.warning(f"Skipping [{json_file_path.name}]: 'githubUrl' not found.")
            return 0, 0, False, False # No processing, not skipped/failed in the specific ways tracked

        source_owner, source_repo = extract_repo_owner_name(github_url)
        if not source_owner or not source_repo:
            logging.warning(f"Skipping [{json_file_path.name}]: Could not parse owner/repo from URL '[{github_url}]'.")
            return 0, 0, False, False # No processing

        source_repo_full_name = f"{source_owner}/{source_repo}"
        if source_repo_full_name in processed_repos:
            logging.info(f"Skipping duplicate source repository: [{source_repo_full_name}]")
            # Return 0,0 but indicate it was processed previously (not skipped/failed *this time*)
            return 0, 0, False, False

        # Keep the same repo name in the target org, but prefix it with the original owner and a double underscore
        target_repo_name = get_target_repo_name(source_owner, source_repo)

        # Check if fork exists or create it
        fork_exists, fork_skipped_flag = ensure_repository_fork(
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
                # Don't add to processed_repos because we might want to retry later
                return 0, 0, False, failed_fork # Return failed status

        # --- If we reach here, fork_exists is True ---

        # Add the *source* repo name to the set to track processed sources *before* checking properties/reprocessing
        # This ensures even if we skip due to recent update/GHAS already enabled, we count it as "encountered"
        processed_repos.add(source_repo_full_name)

        # load the repository properties to check if we need to do something
        properties = get_repository_properties(gh, target_org, target_repo_name)
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
        logging.error(f"Skipping [{json_file_path.name}]: Invalid JSON.")
        # Mark as failed for reporting purposes, although it's a data issue
        failed_fork = True # Use failed_fork flag to indicate *some* failure occurred for this item
    except Exception as e:
        logging.error(f"An unexpected error occurred processing [{json_file_path.name}]: [{e}]")
        # Ensure we don't count this as processed if an error occurred mid-way
        processed_increment = 0
        dependabot_increment = 0
        failed_fork = True # Mark as failed
        # We might have added to processed_repos before the error,
        # but the logic prevents reprocessing anyway.

    # Return all counts and flags
    return processed_increment, dependabot_increment, skipped_non_fork, failed_fork

# --- Main Logic ---

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
        # --- Authentication ---
        # Pass private key content directly
        gh = get_github_client(app_id, private_key)

        # Load all existing repos from the target org
        existing_repos = list_all_repositories_for_org(gh, args.target_org)
        initial_repo_count = len(existing_repos) # Store initial count

        # Clone or Update MCP Agents Hub repo
        clone_or_update_repo(MCP_AGENTS_HUB_REPO_URL, LOCAL_REPO_PATH)

        # Find JSON files in the MCP Agents Hub repo
        json_dir = LOCAL_REPO_PATH / JSON_FILES_DIR_IN_REPO
        if not json_dir.is_dir():
            logging.error(f"JSON directory not found: [{json_dir}]")
            return

        all_json_files = sorted(list(json_dir.glob("*.json"))) # Sort for consistent runs
        if not all_json_files:
            logging.warning(f"No JSON files found in [{json_dir}]")
            return

        # Limit based on the --num-repos argument
        num_to_process = args.num_repos
        # Removed slicing: json_files_to_process = all_json_files[:num_to_process]
        logging.info(f"Found [{len(all_json_files)}] JSON files. Will process up to [{num_to_process}] repositories based on --num-repos.")

        # Process Repos
        processed_repo_count = 0 # Counter for successfully processed repos (forked/found + GHAS attempted)
        dependabot_enabled_count = 0
        processed_repos = set() # Keep track of processed source repos to avoid duplicates
        skipped_non_fork_count = 0 # Track repos skipped because they exist but aren't the correct fork
        failed_fork_count = 0 # Track repos where fork creation/check failed

        # Iterate over all JSON files until the desired number is processed
        for json_file_path in all_json_files:
            # Check if we have processed enough repos
            if processed_repo_count >= num_to_process:
                logging.info(f"Reached processing limit of [{num_to_process}] repositories.")
                break

            # Call the helper function to process this specific repo
            processed_inc, dependabot_inc, skipped_non_fork, failed_fork = process_repository_from_json(
                existing_repos,
                json_file_path,
                gh,
                args.target_org,
                processed_repos # Pass the set (it will be modified in place)
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
            f"-----------------------------------",
            f"- Processing Limit (--num-repos): `{num_to_process}`",
            f"- Total JSON files found: `{len(all_json_files)}`",
            f"- Unique source repositories encountered: `{len(processed_repos)}`",
            f"- New repositories successfully processed (forked/found & GHAS enabled): `{processed_repo_count}`",
            f"- Repositories skipped (exist but not correct fork): `{skipped_non_fork_count}`",
            f"- Repositories failed (fork creation/check error): `{failed_fork_count}`",
            f"- Repositories among processed with Dependabot config: `{dependabot_enabled_count}`",
            f"- Initial repositories in target org `{args.target_org}`: `{initial_repo_count}`",
            f"- Final repositories in target org `{args.target_org}`: `{final_repo_count}`",
            f"- Total execution time: `{duration}`"
        ]

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
