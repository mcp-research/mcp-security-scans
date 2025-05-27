# MCP Security Scans

This project contains a Python script to automate the process of forking repositories listed in the `mcp-agents-ai/mcp-agents-hub` and enabling GitHub Advanced Security (GHAS) features on the forks.

## Features

*   Supports loading MCP server configurations from multiple repository sources.
  *   Currently includes support for the `mcp-agents-ai/mcp-agents-hub` repository.
*   Authenticates with GitHub using a GitHub App.
*   Forks the identified source repositories into a specified target organization (default: `mcp-research`).
*   Checks if a fork already exists before attempting to create one.
*   Enables the following GHAS features on the forks:
    *   Dependency Scanning (via Vulnerability Alerts)
    *   Automated Security Fixes
    *   Secret Scanning
    *   Code Scanning with Default Setup (if supported for the repository's language)
*   Checks if a `.github/dependabot.yml` file exists in each fork.
*   Reports the total number of repositories processed and the count of those with/without a Dependabot configuration.
*   Handles GitHub API errors and displays rate limit information.

## Setup

1.  **Clone this repository:**
    ```bash
    git clone <your-repo-url>
    cd mcp-security-scans
    ```

2.  **Create a Python virtual environment (recommended):**
    ```bash
    python -m venv .venv
    source .venv/bin/activate # On Windows use `.venv\Scripts\activate`
    ```

3.  **Install dependencies:**
    ```bash
    pip install -r requirements.txt
    pip install -r requirements-dev.txt
    ```

4.  **GitHub App Setup:**
    *   Create a GitHub App (e.g., under your user account or an organization).
    *   Grant it the necessary permissions for the *target* organization (e.g., `mcp-research`):
        *   **Repository Permissions:**
            *   Administration: Read & Write (to enable security features, create forks)
            *   Contents: Read & Write (to check for dependabot.yml, potentially needed for default setup)
            *   Metadata: Read-only (default)
            *   Secret scanning alerts: Read & Write
            *   Code scanning alerts: Read & Write
            *   Dependabot alerts: Read & Write
        *   **Organization Permissions:**
            *   Members: Read-only (to verify app installation)
    *   Install the App on the target organization (`mcp-research`).
    *   Generate a private key for the App and copy its *contents*.
    *   Note the App ID.

5.  **Set Environment Variables:**
    Set the following environment variables in your shell or using a `.env` file (which is automatically loaded by the script):
    ```bash
    export GH_APP_ID="YOUR_APP_ID"
    export GH_APP_PRIVATE_KEY="-----BEGIN RSA PRIVATE KEY-----\\nYOUR_KEY_CONTENT_HERE\\n-----END RSA PRIVATE KEY-----"
    ```
    *Replace `YOUR_APP_ID` with your App's ID.*
    *Replace the private key string with the actual content of your `.pem` file, ensuring newlines (`\\n`) are preserved if setting directly in the shell or kept as actual newlines in a `.env` file.*

## Usage

Ensure the environment variables `GH_APP_ID` and `GH_APP_PRIVATE_KEY` are set. Then, run the script from the root directory of this project:

```bash
python -m src.process_mcp_repos # will process all repos found and fork them into the target org
python -m src.analyze --num-repos x # will analyze the forks and store found information into the forks repository properties
python -m src.report # will generate a report of the forks based on the information stored in the forks repository properties

```

**Optional Arguments:**

*   `--target-org <org_name>`: Specify a different target organization to fork into (defaults to `mcp-research`).

**Example:**

```bash
# Assuming environment variables are set and the virtual environment is active
python -m src.process_mcp_repos --target-org my-testing-org
```

The script will log its progress to the console.

### Adding a New MCP Server Source

To add support for a new repository containing MCP server configurations:

1. Create a new function in `src/process_mcp_repos.py` that loads the MCP server list from your repository:

```python
def load_mcp_servers_from_my_custom_repo() -> list[Path]:
    """
    Loads MCP server configurations from your custom repository.

    Returns:
        A list of Path objects pointing to files containing server configurations.
    """
    repo_url = "https://github.com/your-org/your-repo.git"
    local_path = Path("./cloned_your_repo")
    json_dir_in_repo = Path("path/to/configs")

    # Clone or update the repository
    newly_cloned = clone_or_update_repo(repo_url, local_path)
    if newly_cloned:
        logging.info(f"Custom repository newly cloned to [{local_path}]")
    else:
        logging.info(f"Custom repository at [{local_path}] already exists and was updated")

    # Find configuration files in the repository
    json_dir = local_path / json_dir_in_repo
    if not json_dir.is_dir():
        logging.error(f"Config directory not found: [{json_dir}]")
        return []

    config_files = sorted(list(json_dir.glob("*.json")))  # Adjust the pattern as needed
    if not config_files:
        logging.warning(f"No configuration files found in [{json_dir}]")
        return []

    logging.info(f"Found [{len(config_files)}] configuration files in custom repository")
    return config_files
```

2. Register the new loader function to the `MCP_SERVER_LOADERS` list:

```python
# Register the custom loader
MCP_SERVER_LOADERS.append(load_mcp_servers_from_my_custom_repo)
```

The main function will automatically use all registered loaders to collect MCP server configurations.

## GitHub Workflows

This repository includes several GitHub workflows that automate various tasks:

* **Process MCP Repositories**: Automatically forks repositories and enables GHAS features.
* **Daily Security Report**: Generates daily security reports for the repositories.
* **Create Repository Properties**: Sets up required repository properties.
* **Tag @rajbos on New Issues**: Automatically tags @rajbos on new issues that were not created by them, ensuring timely attention to reported issues.

## Testing
```bash
python -m unittest tests.test_mcp_scan
```
