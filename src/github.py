import logging
from datetime import datetime
from githubkit import GitHub, AppInstallationAuthStrategy
from git import Repo, GitCommandError
from githubkit.exception import RequestError, RequestFailed, RequestTimeout
from pathlib import Path
from urllib.parse import urlparse
from githubkit.versions.latest.models import FullRepository
from typing import Any
import os
import subprocess
import magic
import time

def get_github_client(app_id: str, private_key: str) -> GitHub:
    """Authenticates using GitHub App credentials."""
    try:
        auth = AppInstallationAuthStrategy(app_id=int(app_id), private_key=private_key, installation_id=65023400) # Note: Hardcoded installation ID might need review
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

def list_all_repository_properties_for_org(gh: GitHub, org: str) -> list[dict[str, Any]]:
    """Lists all custom repository properties for a given organization.

    Args:
        gh: Authenticated GitHub client instance.
        org: The name of the GitHub organization.

    Returns:
        A list of dictionaries where keys are the names of the *custom* properties
        and values are the current values set for the organization's repositories.

    Raises:
        RequestFailed: If the API call fails.
        Exception: For other unexpected errors.
    """
    all_properties = []
    logging.info(f"Fetching all custom repository properties for organization [{org}]...")
    try:
        test = gh.rest.orgs.list_custom_properties_values_for_repos(org=org)
        paginated_properties = gh.paginate(gh.rest.orgs.list_custom_properties_values_for_repos, org=org)

        # iterate through the paginated results
        for prop in paginated_properties:
            all_properties.append(prop)

        logging.info(f"Successfully fetched [{len(all_properties)}] custom repository properties for organization [{org}].")
        return all_properties

    except RequestFailed as e:
        handle_github_api_error(e, f"listing all custom repository properties for org [{org}]")
        raise # re-raise the exception after logging
    except Exception as e:
        logging.error(f"An unexpected error occurred while listing custom repository properties for org [{org}]: [{e}]")
        raise # re-raise the exception

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


def clone_or_update_repo(repo_url: str, local_path: Path) -> bool:
    """Clones a repository if it doesn't exist locally, or pulls updates if it does.
    
    Args:
        repo_url: URL of the repository to clone or update.
        local_path: Local path where the repository should be cloned to.

    Returns:
        bool: True if the repository was newly cloned, False if it was updated.
    """
    newly_cloned = False
    
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
            newly_cloned = True
        except GitCommandError as e:
            logging.error(f"Error cloning repository: [{e}]")
            raise
        except Exception as e:
            logging.error(f"An unexpected error occurred during repo clone: [{e}]")
            raise
            
    return newly_cloned

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

def list_all_repositories_for_org(gh: GitHub, org: str) -> list[FullRepository]:
    """Lists all repositories for a given organization, handling pagination.

    Args:
        gh: Authenticated GitHub client instance.
        org: The name of the GitHub organization.

    Returns:
        A list of FullRepository objects for the organization.

    Raises:
        RequestFailed: If the API call fails.
        Exception: For other unexpected errors.
    """
    all_repos = []
    logging.info(f"Fetching all existing repositories for organization [{org}]...")
    try:
        paginated_repos = gh.paginate(gh.rest.repos.list_for_org, org=org, type="forks") # type='all' includes public, private, forks

        # iterate through the paginated results
        for repo in paginated_repos:
            all_repos.append(repo)

        logging.info(f"Successfully fetched [{len(all_repos)}] repositories for organization [{org}].")
        return all_repos

    except RequestFailed as e:
        handle_github_api_error(e, f"listing all repositories for org [{org}]")
        raise # re-raise the exception after logging
    except Exception as e:
        logging.error(f"An unexpected error occurred while listing repositories for org [{org}]: [{e}]")
        raise # re-raise the exception

def update_repository_properties(gh: GitHub, target_org: str, target_repo_name: str, properties: dict[str, Any]):
    """Updates *custom* repository properties using the GitHub REST API.

    Args:
        gh: Authenticated GitHub client instance.
        target_org: The name of the organization owning the repository.
        target_repo_name: The name of the repository to update.
        properties: A dictionary where keys are the names of the *custom* properties
                    to update and values are the new values to set.
                    Properties must already exist for the organization or repository.

    Raises:
        RequestFailed: If the API call fails (e.g., property doesn't exist, invalid value, permissions).
        Exception: For other unexpected errors.
    """
    custom_properties_list = []
    property_names = list(properties.keys()) # For logging

    try:
        for property_name, value in properties.items():
            # Convert boolean to lowercase string to prevent API errors, stringify others
            if isinstance(value, bool):
                property_value = str(value).lower()
            else:
                property_value = str(value)

            custom_properties_list.append(
                {"property_name": property_name, "value": property_value}
            )

        logging.info(f"Attempting to update custom properties {property_names} for [{target_org}/{target_repo_name}]...")

        gh.rest.repos.create_or_update_custom_properties_values(
            owner=target_org,
            repo=target_repo_name,
            properties=custom_properties_list
        )
        logging.info(f"Successfully updated custom properties {property_names} for [{target_org}/{target_repo_name}].")

    except RequestFailed as e:
        # Enhanced logging for 422 errors
        if e.response.status_code == 422:
             logging.error(f"Failed to update custom properties {property_names} for [{target_org}/{target_repo_name}] with 422 Unprocessable Entity.")
             logging.error("This often means one or more custom property names do not exist for the organization/repo or a value is invalid for its property type.")
             logging.error(f"Error details: {e.response.json()}") # Log the response body if available
        handle_github_api_error(e, f"updating custom repository properties {property_names} for [{target_org}/{target_repo_name}]")
        raise
    except Exception as e:
        logging.error(f"An unexpected error occurred while updating custom repository properties {property_names} for [{target_org}/{target_repo_name}]: [{e}]")
        raise

def get_repository_properties(gh: GitHub, target_org: str, target_repo_name: str, existing_repos_properties: list[dict]) -> dict[str, Any]:
    """Retrieves *custom* repository properties using the GitHub REST API.

    Args:
        gh: Authenticated GitHub client instance.
        target_org: The name of the organization owning the repository.
        target_repo_name: The name of the repository to retrieve properties for.

    Returns:
        A dictionary where keys are the names of the *custom* properties
        and values are the current values set for the repository.
        An empty dictionary is returned if no properties are set.

    Raises:
        RequestFailed: If the API call fails (e.g., property doesn't exist, permissions).
        Exception: For other unexpected errors.
    """
    try:
        logging.info(f"Fetching custom properties for [{target_org}/{target_repo_name}]...")

        # first search in the existing properties list
        for repo_properties in existing_repos_properties:
            if repo_properties.repository_name == target_repo_name:
                # use the existing properties if found
                properties = repo_properties.properties
                logging.info(f"Found existing custom properties for [{target_org}/{target_repo_name}].")
                # Fix: Access attributes properly for CustomPropertyValue objects
                return {prop.property_name: prop.value for prop in properties}

        properties = gh.rest.repos.get_custom_properties_values(
            owner=target_org,
            repo=target_repo_name
        ).json()

        if properties:
            logging.info(f"Successfully fetched custom properties for [{target_org}/{target_repo_name}].")
            # Keep dictionary syntax here since this comes from json()
            return {prop["property_name"]: prop["value"] for prop in properties}
        else:
            logging.info(f"No custom properties found for [{target_org}/{target_repo_name}].")
            return {}

    except RequestFailed as e:
        handle_github_api_error(e, f"fetching custom repository properties for [{target_org}/{target_repo_name}]")
        raise
    except Exception as e:
        logging.error(f"An unexpected error occurred while fetching custom repository properties for [{target_org}/{target_repo_name}]: [{e}]")
        raise

def is_valid_tarball(file_path: str) -> bool:
    """
    Verify if the file is a valid gzipped tarball using magic module.
    
    Args:
        file_path: Path to the downloaded file
        
    Returns:
        Boolean indicating if the file is a valid gzipped tarball
    """
    try:
        # Check the file type using libmagic
        file_type = magic.from_file(file_path)
        logging.debug(f"File type for [{file_path}]: {file_type}")
        
        # Check if it's a gzip compressed file or tarball
        return ('gzip' in file_type.lower() or 
                'tar archive' in file_type.lower() or 
                'compressed data' in file_type.lower())
    except Exception as e:
        logging.error(f"Error checking file type for [{file_path}]: {e}")
        return False

def clone_repository(gh: Any, owner: str, repo_name: str, branch: str, local_repo_path: Path) -> None:
    """
    Clones a repository to a local path using the GitHub API tarball download.
    
    Args:
        gh: Authenticated GitHub client instance.
        owner: Owner of the repository.
        repo_name: Repository name.
        branch: Branch to clone (usually the default branch).
        local_repo_path: Path where the repository will be cloned.
    """
    # check if the folder already exists
    if local_repo_path.exists():
        import shutil
        logging.info(f"Cleaning existing directory [{local_repo_path}]")
        shutil.rmtree(local_repo_path)
    
    # Create a temporary directory for extraction
    temp_extract_path = Path(f"{local_repo_path}_temp")
    if temp_extract_path.exists():
        import shutil
        shutil.rmtree(temp_extract_path)
    temp_extract_path.mkdir(parents=True)
    
    # Ensure parent directory exists for the final repo path
    local_repo_path.parent.mkdir(parents=True, exist_ok=True)

    logging.info(f"Cloning repository [{repo_name}] to [{local_repo_path}]")
    
    max_retries = 3
    retry_delay = 2  # seconds
    for attempt in range(1, max_retries + 1):
        try:
            # Get tarball URL from GitHub
            tarball_json = gh.rest.repos.download_tarball_archive(owner=owner, repo=repo_name, ref=branch)
            tarball_url = str(tarball_json.url)
            
            # download the tarball
            logging.info(f"Downloading tarball from [{tarball_url}] (Attempt {attempt}/{max_retries})")
            tarball_file = f"{local_repo_path}.tar.gz"
            curl_command = ["curl", "-L", tarball_url, "-o", tarball_file]
            
            process = subprocess.run(curl_command, capture_output=True, text=True, check=True)
            logging.debug(f"Curl command output: {process.stdout}")
            
            # Verify that the downloaded file is a valid tarball
            if not is_valid_tarball(tarball_file):
                logging.warning(f"Downloaded file for [{repo_name}] is not a valid gzipped tarball (Attempt {attempt}/{max_retries})")
                if attempt < max_retries:
                    logging.info(f"Retrying download in {retry_delay} seconds...")
                    time.sleep(retry_delay)
                    continue
                else:
                    logging.error(f"Failed to download valid tarball for [{repo_name}] after {max_retries} attempts")
                    return
            
            # extract the tarball
            logging.info(f"Extracting tarball for [{repo_name}]")
            tar_command = ["tar", "-xvf", tarball_file, "-C", str(local_repo_path)]
            try:
                process = subprocess.run(tar_command, capture_output=True, text=True, check=True)
                logging.debug(f"Tar command output: {process.stdout}")
                # If we got here, extraction succeeded, so break out of the retry loop
                break
            except subprocess.CalledProcessError as e:
                logging.error(f"Error extracting tarball for [{repo_name}]: {e}")
                logging.error(f"Tar stderr: {e.stderr}")
                if attempt < max_retries:
                    logging.info(f"Retrying download in {retry_delay} seconds...")
                    time.sleep(retry_delay)
                else:
                    logging.error(f"Failed to extract tarball for [{repo_name}] after {max_retries} attempts")
        
        except subprocess.CalledProcessError as e:
            logging.error(f"Error downloading tarball for [{repo_name}]: {e}")
            logging.error(f"Curl stderr: {e.stderr}")
            if attempt < max_retries:
                logging.info(f"Retrying download in {retry_delay} seconds...")
                time.sleep(retry_delay)
            else:
                logging.error(f"Failed to download tarball for [{repo_name}] after {max_retries} attempts")
                return
        except Exception as e:
            logging.error(f"Unexpected error processing tarball for [{repo_name}]: {e}")
            if attempt < max_retries:
                logging.info(f"Retrying in {retry_delay} seconds...")
                time.sleep(retry_delay)
            else:
                logging.error(f"Failed to process repository [{repo_name}] after {max_retries} attempts")
                return
        finally:
            # Clean up the tarball if it exists
            if os.path.exists(tarball_file):
                try:
                    os.remove(tarball_file)
                    logging.debug(f"Removed tarball file [{tarball_file}]")
                except OSError as e:
                    logging.error(f"Error removing tarball file [{tarball_file}]: {e}")

def show_rate_limit(gh: GitHub):
    """Displays the current rate limit status for the authenticated GitHub client."""
    try:
        rate_limit = gh.rest.rate_limit.get().json()
        core_limit = rate_limit["resources"]["core"]
        reset_timestamp = core_limit["reset"]
        # Convert Unix timestamp to readable datetime
        reset_datetime = datetime.fromtimestamp(reset_timestamp)
        reset_str = reset_datetime.strftime("%Y-%m-%d %H:%M:%S %Z") # Format the datetime
        logging.info(f"Rate Limit Info: Core - Limit: {core_limit['limit']}, Remaining: {core_limit['remaining']}, Reset: {reset_str}")
    except RequestFailed as e:
        handle_github_api_error(e, "fetching rate limit status")
    except Exception as e:
        logging.error(f"An unexpected error occurred while fetching rate limit status: [{e}]")