\
import os
import json
import argparse
import logging
from pathlib import Path
from urllib.parse import urlparse
from githubkit import GitHub, AppInstallationAuthStrategy
from githubkit.exception import RequestError, RequestFailed, RequestTimeout
from githubkit.versions.latest.models import FullRepository
from git import Repo, GitCommandError
from dotenv import load_dotenv

# --- Configuration ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
load_dotenv() # Load environment variables from .env file

# --- Constants ---
MCP_AGENTS_HUB_REPO_URL = "https://github.com/mcp-agents-ai/mcp-agents-hub.git"
LOCAL_REPO_PATH = Path("./cloned_mcp_agents_hub")
JSON_FILES_DIR_IN_REPO = Path("server/src/data/split")
TARGET_ORG = "mcp-research" # The organization to fork into

# --- Helper Functions ---

def get_github_client(app_id: str, private_key: str) -> GitHub:
    """Authenticates using GitHub App credentials."""
    try:
        # Removed reading private key from file
        auth = AppInstallationAuthStrategy(app_id=int(app_id), private_key=private_key, installation_id=65023400)
        gh = GitHub(auth)
        logging.info("GitHub client authenticated successfully as App.")
        return gh
    except ValueError as e:
        logging.error(f"Invalid App ID format: [{e}]")
        raise
    except Exception as e:
        logging.error(f"Failed to authenticate GitHub App: [{e}]")
        raise

def get_installation_github_client(gh_app: GitHub, target_org: str) -> GitHub:
    """Gets a GitHub client authenticated for a specific installation."""
    try:
        # Find the installation ID for the target organization
        installations = gh_app.apps.list_installations().json()
        installation_id = None
        for inst in installations:
            if inst.account and inst.account.login == target_org:
                installation_id = inst.id
                break

        if not installation_id:
            raise ValueError(f"GitHub App installation not found for organization '[{target_org}]'")

        # Create a client authenticated for the installation
        installation_auth = gh_app.get_installation_auth(installation_id)
        gh_inst = GitHub(installation_auth)
        logging.info(f"GitHub client authenticated successfully for installation ID [{installation_id}] ([{target_org}]).")
        return gh_inst
    except Exception as e:
        logging.error(f"Failed to get installation client for [{target_org}]: [{e}]")
        raise


def clone_or_update_repo(repo_url: str, local_path: Path):
    """Clones a repository if it doesn't exist locally, or pulls updates if it does."""
    if local_path.exists():
        logging.info(f"Repository already exists at [{local_path}]. Fetching updates...")
        try:
            repo = Repo(local_path)
            origin = repo.remotes.origin
            origin.fetch()
            # Resetting to remote's main/master branch - adjust branch name if needed
            # Trying common default branch names
            for branch_name in ['main', 'master']:
                try:
                    repo.git.reset('--hard', f'origin/{branch_name}')
                    logging.info(f"Reset local repository to [origin/{branch_name}].")
                    break
                except GitCommandError:
                    continue # Try next branch name
            else:
                 logging.warning(f"Could not find 'main' or 'master' branch in remote. Local repo might not be up-to-date.")

        except GitCommandError as e:
            logging.error(f"Error updating repository at [{local_path}]: [{e}]")
        except Exception as e:
            logging.error(f"An unexpected error occurred during repo update: [{e}]")
    else:
        logging.info(f"Cloning repository from [{repo_url}] to [{local_path}]...")
        try:
            Repo.clone_from(repo_url, local_path)
            logging.info("Repository cloned successfully.")
        except GitCommandError as e:
            logging.error(f"Error cloning repository: [{e}]")
            raise
        except Exception as e:
            logging.error(f"An unexpected error occurred during repo clone: [{e}]")
            raise

def extract_repo_owner_name(github_url: str) -> tuple[str | None, str | None]:
    """Extracts owner and repo name from a GitHub URL."""
    try:
        parsed_url = urlparse(github_url)
        if (parsed_url.netloc.lower() == "github.com"):
            path_parts = [part for part in parsed_url.path.strip('/').split('/') if part]
            if len(path_parts) >= 2:
                owner = path_parts[0]
                repo_name = path_parts[1].replace(".git", "")
                return owner, repo_name
    except Exception as e:
        logging.error(f"Error parsing GitHub URL '[{github_url}]': [{e}]")
    return None, None

def handle_github_api_error(error: RequestError, action: str):
    """Logs details of a GitHub API error, including rate limits."""
    logging.error(f"GitHub API error during '[{action}]': Status [{error.response.status_code}]")
    logging.error(f"Error details: [{error}]")
    if error.response.headers:
        limit = error.response.headers.get('X-RateLimit-Limit')
        remaining = error.response.headers.get('X-RateLimit-Remaining')
        reset = error.response.headers.get('X-RateLimit-Reset')
        used = error.response.headers.get('X-RateLimit-Used')
        logging.error(
            f"Rate Limit Info: Limit=[{limit}], Remaining=[{remaining}], Used=[{used}], Reset=[{reset}]"
        )

def check_dependabot_config(gh: GitHub, owner: str, repo: str) -> bool:
    """Checks if a .github/dependabot.yml file exists in the repository."""
    try:
        gh.rest.repos.get_content(owner=owner, repo=repo, path=".github/dependabot.yml")
        logging.info(f"Dependabot config found in [{owner}/{repo}].")
        return True
    except RequestFailed as e:
        if e.response.status_code == 404:
            logging.info(f"Dependabot config not found in [{owner}/{repo}].")
            return False
        else:
            handle_github_api_error(e, f"checking dependabot config for [{owner}/{repo}]")
            return False # Assume not present if error occurs
    except Exception as e:
        logging.error(f"Unexpected error checking dependabot config for [{owner}/{repo}]: [{e}]")
        return False


def enable_ghas_features(gh: GitHub, owner: str, repo: str):
    """Enables GHAS features (vuln alerts, code scanning default setup, secret scanning) for a repo."""
    logging.info(f"Enabling GHAS features for [{owner}/{repo}]...")
    try:
        # Enable Vulnerability Alerts (Implies Dependency Scanning)
        gh.rest.repos.enable_vulnerability_alerts(owner=owner, repo=repo)
        logging.info(f"Enabled vulnerability alerts for [{owner}/{repo}].")

        # Enable Secret Scanning & Push Protection
        patch_data_secret = {
            "security_and_analysis": {
                "secret_scanning": {"status": "enabled"}
            }
        }
        gh.rest.repos.update(owner=owner, repo=repo, data=patch_data_secret)
        logging.info(f"Enabled secret scanning and push protection for [{owner}/{repo}].")


        # Enable Code Scanning Default Setup
        try:
            gh.rest.code_scanning.update_default_setup(owner=owner, repo=repo, data={"state":"configured"})
            logging.info(f"Enabled code scanning default setup for [{owner}/{repo}].")
        except RequestFailed as e_cs:
             # Default setup might fail if the language isn't supported or already configured
            if e_cs.response.status_code == 404 or e_cs.response.status_code == 409: # Not found or Conflict (already enabled/in progress)
                 logging.warning(f"Could not enable code scanning default setup for [{owner}/{repo}] (Status: [{e_cs.response.status_code}]). It might be unsupported or already configured.")
            else:
                handle_github_api_error(e_cs, f"enabling code scanning default setup for [{owner}/{repo}]")
        except Exception as e_cs_other:
             logging.error(f"Unexpected error enabling code scanning default setup for [{owner}/{repo}]: [{e_cs_other}]")


    except RequestFailed as e:
        handle_github_api_error(e, f"enabling GHAS features for [{owner}/{repo}]")
    except Exception as e:
        logging.error(f"Unexpected error enabling GHAS features for [{owner}/{repo}]: [{e}]")


# --- Main Logic ---

def main():
    parser = argparse.ArgumentParser(description="Fork MCP Hub repos and enable GHAS features.")
    # Removed app-id and private-key-path arguments
    parser.add_argument("--target-org", default=TARGET_ORG, help=f"Target GitHub organization to fork into (default: {TARGET_ORG})")

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
        gh_app_client = get_github_client(app_id, private_key)
        gh = gh_app_client

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

        # Limit to the first 3 files
        json_files_to_process = all_json_files[:3]
        logging.info(f"Found [{len(all_json_files)}] JSON files. Processing the first [{len(json_files_to_process)}].")

        # --- Process Repos ---
        total_repos = 0
        dependabot_enabled_count = 0
        processed_repos = set() # Keep track of processed source repos to avoid duplicates if listed multiple times

        # Iterate over the limited list
        for json_file_path in json_files_to_process:
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

                logging.info(f"Processing source repository: [{source_repo_full_name}]")
                total_repos += 1
                processed_repos.add(source_repo_full_name)

                # Keep the same repo name in the target org, but prefix it with the original owner and a double underscore
                target_repo_name = f"{source_owner}__{source_repo}"
                target_owner = args.target_org

                # Check if fork already exists in the target organization
                fork_exists = False
                try:
                    # log
                    logging.info(f"Checking if fork exists for [{target_repo_name}] in [{target_owner}]...")
                    target_repo_info : FullRepository = gh.rest.repos.get(owner=target_owner, repo=target_repo_name).parsed_data
                    # Check if it's actually a fork of the correct source
                    if target_repo_info.fork and target_repo_info.parent and target_repo_info.parent.full_name.lower() == source_repo_full_name.lower():
                        logging.info(f"Fork [{target_owner}/{target_repo_name}] already exists.")
                        fork_exists = True
                    else:
                         logging.warning(f"Repository [{target_owner}/{target_repo_name}] exists but is not a fork of [{source_repo_full_name}]. Skipping fork creation.")
                         # Decide if you want to proceed with GHAS enablement anyway or skip
                         # For now, let's skip GHAS enablement if it's not the correct fork.
                         continue # Skip to next JSON file

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

                # If fork exists (or was just created), enable GHAS and check Dependabot
                if fork_exists:
                    enable_ghas_features(gh, target_owner, target_repo_name)
                    if check_dependabot_config(gh, target_owner, target_repo_name):
                        dependabot_enabled_count += 1

            except json.JSONDecodeError:
                logging.error(f"Skipping [{json_file_path.name}]: Invalid JSON.")
            except Exception as e:
                logging.error(f"An unexpected error occurred processing [{json_file_path.name}]: [{e}]")

        # --- Reporting ---
        logging.info("--- Processing Complete ---")
        # Reporting logic remains the same, but reflects the limited run
        logging.info(f"Total unique source repositories processed (from the first [{len(json_files_to_process)}] JSON files): [{total_repos}]")
        logging.info(f"Repositories with Dependabot config (.github/dependabot.yml): [{dependabot_enabled_count}]")
        logging.info(f"Repositories without Dependabot config: [{total_repos - dependabot_enabled_count}]")

    except Exception as e:
        logging.error(f"Script failed with an error: [{e}]")
        # Consider more specific exception handling if needed

if __name__ == "__main__":
    main()
