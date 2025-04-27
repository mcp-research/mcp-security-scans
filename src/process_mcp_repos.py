import os
import json
import argparse
import logging
from pathlib import Path
from githubkit.exception import RequestError, RequestFailed, RequestTimeout
from githubkit.versions.latest.models import FullRepository
from dotenv import load_dotenv

# Import the local functions
from github import get_github_client, get_installation_github_client, enable_ghas_features, check_dependabot_config, clone_or_update_repo, extract_repo_owner_name, handle_github_api_error

# --- Configuration ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
load_dotenv() # Load environment variables from .env file

# --- Constants ---
MCP_AGENTS_HUB_REPO_URL = "https://github.com/mcp-agents-ai/mcp-agents-hub.git"
LOCAL_REPO_PATH = Path("./cloned_mcp_agents_hub")
JSON_FILES_DIR_IN_REPO = Path("server/src/data/split")
TARGET_ORG = "mcp-research" # The organization to fork into

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

        # --- Clone or Update MCP Agents Hub Repo ---
        clone_or_update_repo(MCP_AGENTS_HUB_REPO_URL, LOCAL_REPO_PATH)

        # --- Find JSON files ---
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

        # --- Process Repos ---
        unique_source_repos_attempted = 0
        processed_repo_count = 0 # Counter for successfully processed repos (forked/found + GHAS attempted)
        dependabot_enabled_count = 0
        processed_repos = set() # Keep track of processed source repos to avoid duplicates

        # Iterate over all JSON files until the desired number is processed
        for json_file_path in all_json_files:
            # Check if we have processed enough repos
            if processed_repo_count >= num_to_process:
                logging.info(f"Reached processing limit of [{num_to_process}] repositories.")
                break

            try:
                with open(json_file_path, 'r') as f:
                    data = json.load(f)

                github_url = data.get("githubUrl")
                if not github_url:
                    logging.warning(f"Skipping [{json_file_path.name}]: 'githubUrl' not found.")
                    continue

                source_owner, source_repo = extract_repo_owner_name(github_url)
                if not source_owner or not source_repo:
                    logging.warning(f"Skipping [{json_file_path.name}]: Could not parse owner/repo from URL '[{github_url}]'.")
                    continue

                source_repo_full_name = f"{source_owner}/{source_repo}"
                if source_repo_full_name in processed_repos:
                    logging.info(f"Skipping duplicate source repository: [{source_repo_full_name}]")
                    continue

                # Keep the same repo name in the target org, but prefix it with the original owner and a double underscore
                target_repo_name = f"{source_owner}__{source_repo}"
                target_owner = args.target_org

                # Check if fork already exists in the target organization
                fork_exists = False
                fork_skipped = False # Flag to indicate if we skipped due to non-fork repo existing
                try:
                    # log
                    logging.info(f"Checking if fork exists for [{target_repo_name}] in [{target_owner}]...")
                    target_repo_info : FullRepository = gh.rest.repos.get(owner=target_owner, repo=target_repo_name).parsed_data
                    # Check if it's actually a fork of the correct source
                    if target_repo_info.fork and target_repo_info.parent and target_repo_info.parent.full_name.lower() == source_repo_full_name.lower():
                        logging.info(f"Fork [{target_owner}/{target_repo_name}] already exists.")
                        fork_exists = True
                    else:
                         logging.warning(f"Repository [{target_owner}/{target_repo_name}] exists but is not a fork of [{source_repo_full_name}]. Skipping GHAS enablement.")
                         # Skip GHAS enablement and don't count this towards the processed limit
                         fork_skipped = True # Mark as skipped
                         continue # Skip to next JSON file
                    
                    # continue debugging why we still process the same 3 repos during debugging from here
                    logging.info(f"Processing source repository: [{source_repo_full_name}]")
                    unique_source_repos_attempted += 1
                    processed_repos.add(source_repo_full_name)

                except RequestFailed as e:
                    if e.response.status_code == 404:
                        logging.info(f"Fork [{target_owner}/{target_repo_name}] does not exist. Creating fork...")
                        try:
                            # Fork the repository
                            fork_response = gh.rest.repos.create_fork(
                                owner=source_owner,
                                repo=source_repo,
                                org=target_owner, # Specify the target organization
                                name=target_repo_name, # Can specify name if needed, defaults to source repo name
                                default_branch_only=False # Fork all branches
                            )
                            # Forking can take time, GitHub API returns 202 Accepted
                            logging.info(f"Fork creation initiated for [{source_repo_full_name}] into [{target_owner}]. Status: [{fork_response.parsed_data}]")
                            # We might need to wait or poll here, but for now, assume it will be created shortly
                            # and proceed with GHAS enablement. If it fails, the enablement step will likely fail too.
                            fork_exists = True # Assume it will exist soon for GHAS steps
                        except RequestFailed as fork_error:
                            handle_github_api_error(fork_error, f"forking [{source_repo_full_name}] to [{target_owner}]")
                            continue # Skip to next JSON file if fork fails
                        except Exception as fork_exc:
                             logging.error(f"Unexpected error forking [{source_repo_full_name}]: [{fork_exc}]")
                             continue
                    else:
                        handle_github_api_error(e, f"checking fork existence for [{target_owner}/{target_repo_name}]")
                        continue # Skip if we can't determine existence

                # If fork exists (or was just created) and wasn't skipped, enable GHAS, check Dependabot, and count it.
                if fork_exists and not fork_skipped:
                    enable_ghas_features(gh, target_owner, target_repo_name)
                    if check_dependabot_config(gh, target_owner, target_repo_name):
                        dependabot_enabled_count += 1
                    processed_repo_count += 1 # Increment the counter for successfully processed repos
                    # The check to break the loop is now at the beginning of the outer loop

            except json.JSONDecodeError:
                logging.error(f"Skipping [{json_file_path.name}]: Invalid JSON.")
            except Exception as e:
                logging.error(f"An unexpected error occurred processing [{json_file_path.name}]: [{e}]")

        # --- Reporting ---
        logging.info("--- Processing Complete ---")
        logging.info(f"Total unique source repositories attempted (from JSON files): [{unique_source_repos_attempted}]")
        logging.info(f"Successfully processed repositories (fork found/created and GHAS attempted): [{processed_repo_count}] (Limit was [{num_to_process}])")
        logging.info(f"Repositories among processed with Dependabot config (.github/dependabot.yml): [{dependabot_enabled_count}]")
        if processed_repo_count > 0:
             logging.info(f"Repositories among processed without Dependabot config: [{processed_repo_count - dependabot_enabled_count}]")
        else:
             logging.info("No repositories were successfully processed to check for Dependabot config.")


    except Exception as e:
        logging.error(f"Script failed with an error: [{e}]")
        # Consider more specific exception handling if needed

if __name__ == "__main__":
    main()
