import logging
from datetime import datetime
from githubkit import GitHub, AppInstallationAuthStrategy
from git import Repo, GitCommandError
from githubkit.exception import RequestError, RequestFailed, RequestTimeout
from pathlib import Path
from urllib.parse import urlparse
from githubkit.versions.latest.models import FullRepository
from typing import Any

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