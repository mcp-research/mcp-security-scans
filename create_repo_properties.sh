#!/bin/bash

# Script to create all repository properties needed for MCP Security Scans
# Usage: ./create_repo_properties.sh <org_name> <github_token>

# Generate constants.sh to make sure it has the latest values
rm -f constants.sh
python constants_bridge.py
if [ ! -f "./constants.sh" ]; then
    echo "Error: Failed to generate constants.sh. Exiting."
    exit 1
fi

# Source the constants file
source ./constants.sh

# Check if organization name and token are provided
if [ "$#" -lt 2 ]; then
    echo "Usage: $0 <org_name> <github_token>"
    echo "  <org_name>      - GitHub organization name"
    echo "  <github_token>  - GitHub token with admin:org permissions"
    exit 1
fi

ORG_NAME="$1"
TOKEN="$2"

echo "Creating repository properties for organization: $ORG_NAME"

# Helper function to create a property
create_property() {
    local property_name="$1"
    local property_description="$2"
    local value_type="$3"
    local required="$4"
    local default_value="$5"
    local allowed_values="$6"
    local values_editable_by="$7"

    echo "Creating property: $property_name ($value_type)"

    # Validate value_type
    if [[ ! "$value_type" =~ ^(string|single_select|multi_select|true_false)$ ]]; then
        echo "Error: Invalid value_type. Must be one of: string, single_select, multi_select, true_false"
        return 1
    fi

    # Construct JSON payload
    json_data="{\"value_type\":\"$value_type\""

    # Add description if specified
    if [ -n "$property_description" ]; then
        json_data="$json_data,\"description\":\"$property_description\""
    fi

    # Add required field if specified
    if [ -n "$required" ]; then
        json_data="$json_data,\"required\":$required"
    fi

    # Add default value if specified
    if [ -n "$default_value" ]; then
        json_data="$json_data,\"default_value\":\"\""
    fi

    # Add values_editable_by if specified
    if [ -n "$values_editable_by" ]; then
        if [[ "$values_editable_by" =~ ^(org_actors|org_and_repo_actors)$ ]]; then
            json_data="$json_data,\"values_editable_by\":\"$values_editable_by\""
        fi
    fi

    # Close JSON object
    json_data="$json_data}"

    echo "  JSON payload: $json_data"

    # Make API call to create the property
    response=$(curl -s -X PUT "https://api.github.com/orgs/$ORG_NAME/properties/schema/$property_name" \
        -H "Accept: application/vnd.github+json" \
        -H "Authorization: token $TOKEN" \
        -H "X-GitHub-Api-Version: 2022-11-28" \
        -d "$json_data")

    # Check for errors
    if echo "$response" | jq -e '.message' >/dev/null 2>&1; then
        error_message=$(echo "$response" | jq -r '.message')

        # If the error message indicates the property already exists, that's okay
        if [[ "$error_message" == *"already exists"* ]]; then
            echo "  Property already exists, skipping."
        else
            echo "  Error creating property: [$error_message]"
        fi
    else
        echo "  Property created successfully."
    fi
}

# Create last scan timestamp property
create_property "$GHAS_STATUS_UPDATED" "Timestamp of last GHAS status update" "string" "false" "" "" "org_and_repo_actors"

# Create repository properties from constants.sh
# First, get all property variable names from constants.sh
# Looking for non-comment lines that set variables with pattern: NAME="Value"
PROPERTY_VARS=$(grep -E '^[A-Z_]+=".+"' constants.sh | awk -F= '{print $1}')

for VAR_NAME in $PROPERTY_VARS; do
    # Skip the organization and timestamp variables
    if [[ "$VAR_NAME" == "TARGET_ORG" || "$VAR_NAME" == "GHAS_STATUS_UPDATED" ]]; then
        continue
    fi

    # Get the property name value
    PROP_NAME="${!VAR_NAME}"

    # Get property description from the comment line above each property
    DESCRIPTION=$(grep -B 1 "^$VAR_NAME=" constants.sh | head -n 1 | sed 's/^# //')

    # Create the property
    create_property "$PROP_NAME" "$DESCRIPTION" "string" "false" "0" "" "org_and_repo_actors"
done

echo "Repository properties creation completed."
