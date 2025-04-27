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
from github import get_github_client, get_installation_github_client, enable_ghas_features, check_dependabot_config, clone_or_update_repo, extract_repo_owner_name, handle_github_api_error, list_all_repositories_for_org, update_repository_properties 

# --- Configuration ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
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
        target_repo_info = next((r for r in existing_repos if r.full_name.lower() == f"{target_org}/{target_repo_name}".lower()), None)
        # if not target_repo_info:
        #     target_repo_info : FullRepository = gh.rest.repos.get(owner=target_org, repo=target_repo_name).parsed_data

        # check if it's actually a fork of the correct source
        if target_repo_info and target_repo_info.fork and target_repo_info.parent and target_repo_info.parent.full_name.lower() == source_repo_full_name.lower():
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


def process_repository_from_json(
    existing_repos: list[FullRepository],
    json_file_path: Path,
    gh: Any, # Replace Any with the actual type of the GitHub client
    target_org: str,
    processed_repos: set[str]
) -> tuple[int, int]:
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
        A tuple (processed_increment, dependabot_increment):
        - processed_increment: 1 if the repository was successfully processed (forked/found + GHAS attempted), 0 otherwise.
        - dependabot_increment: 1 if Dependabot config was found, 0 otherwise.
    """
    processed_increment = 0
    dependabot_increment = 0
    source_repo_full_name = None # Keep track of the source repo name for adding to the set

    try:
        with open(json_file_path, 'r') as f:
            data = json.load(f)

        github_url = data.get("githubUrl")
        if not github_url:
            logging.warning(f"Skipping [{json_file_path.name}]: 'githubUrl' not found.")
            return 0, 0

        source_owner, source_repo = extract_repo_owner_name(github_url)
        if not source_owner or not source_repo:
            logging.warning(f"Skipping [{json_file_path.name}]: Could not parse owner/repo from URL '[{github_url}]'.")
            return 0, 0

        source_repo_full_name = f"{source_owner}/{source_repo}"
        if source_repo_full_name in processed_repos:
            logging.info(f"Skipping duplicate source repository: [{source_repo_full_name}]")
            return 0, 0

        # Keep the same repo name in the target org, but prefix it with the original owner and a double underscore
        target_repo_name = f"{source_owner}__{source_repo}"

        # Check if fork exists or create it
        fork_exists, fork_skipped = ensure_repository_fork(
            existing_repos, gh, source_owner, source_repo, target_org, target_repo_name, source_repo_full_name
        )

        # If fork creation failed or check failed, ensure_repository_fork returns fork_exists=False
        if not fork_exists and not fork_skipped:
            logging.error(f"Failed to ensure fork exists for [{source_repo_full_name}]. Skipping further processing.")
            return 0, 0 # Don't add to processed_repos

        # If the repo was skipped because it exists but isn't the correct fork, return early.
        if fork_skipped:
            # Don't add to processed_repos as we didn't process it
            return 0, 0

        # If fork exists (or was just created), add to processed set and proceed.
        # The check for fork_exists is implicitly handled by the previous checks
        # Add the *source* repo name to the set to track processed sources
        processed_repos.add(source_repo_full_name)
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
        processed_increment = 1 # Mark as successfully processed

    except json.JSONDecodeError:
        logging.error(f"Skipping [{json_file_path.name}]: Invalid JSON.")
    except Exception as e:
        logging.error(f"An unexpected error occurred processing [{json_file_path.name}]: [{e}]")
        # Ensure we don't count this as processed if an error occurred mid-way
        processed_increment = 0
        dependabot_increment = 0
        # We might have added to processed_repos before the error,
        # but the logic prevents reprocessing anyway.

    return processed_increment, dependabot_increment


# --- Main Logic ---

def main():
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

        # Iterate over all JSON files until the desired number is processed
        for json_file_path in all_json_files:
            # Check if we have processed enough repos
            if processed_repo_count >= num_to_process:
                logging.info(f"Reached processing limit of [{num_to_process}] repositories.")
                break

            # Call the helper function to process this specific repo
            processed_inc, dependabot_inc = process_repository_from_json(
                existing_repos,
                json_file_path,
                gh,
                args.target_org,
                processed_repos # Pass the set (it will be modified in place)
            )

            # Update counters based on the result from the helper function
            processed_repo_count += processed_inc
            dependabot_enabled_count += dependabot_inc

        # Reporting
        logging.info("")
        logging.info("Processing Complete")
        # unique_source_repos_attempted is implicitly len(processed_repos) now + any skipped non-forks (which isn't tracked explicitly anymore, but wasn't the primary metric)
        logging.info(f"New repositories successfully processed: [{processed_repo_count}] (Limit was [{num_to_process}])")
        logging.info(f"Total repositories in target organization [{args.target_org}]: [{len(existing_repos) + processed_repo_count}]")
        logging.info(f"Unique repositories encountered (including duplicates and skips): [{len(processed_repos)}]") # This reflects unique sources added to the set
        logging.info(f"Repositories among processed with Dependabot config (.github/dependabot.yml): [{dependabot_enabled_count}]")
        if processed_repo_count > 0:
             logging.info(f"Repositories among processed without Dependabot config: [{processed_repo_count - dependabot_enabled_count}]")
        else:
             logging.info("No repositories were successfully processed to check for Dependabot config.")


    except Exception as e:
        logging.error(f"Script failed with an error: [{e}]")

if __name__ == "__main__":
    main()
