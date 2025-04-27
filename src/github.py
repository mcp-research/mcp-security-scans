import logging
from githubkit import GitHub, AppInstallationAuthStrategy
from git import Repo, GitCommandError
from githubkit.exception import RequestError, RequestFailed, RequestTimeout
from pathlib import Path
from urllib.parse import urlparse

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

