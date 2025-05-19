#!/bin/bash

# Script to create all repository properties needed for MCP Security Scans
# Usage: ./create_repo_properties.sh <org_name> <github_token>

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

# Create all the repository properties needed

# Last scan timestamp properties
create_property "GHAS_Status_Updated" "Timestamp of last GHAS status update" "string" "false" "" "" "org_and_repo_actors"

# Total alert count properties
create_property "CodeAlerts" "Total number of code scanning alerts" "string" "false" "0" "" "org_and_repo_actors"
create_property "SecretAlerts" "Total number of secret scanning alerts" "string" "false" "0" "" "org_and_repo_actors"
create_property "DependencyAlerts" "Total number of dependency alerts" "string" "false" "0" "" "org_and_repo_actors"

# Code scanning alerts by severity
create_property "CodeAlerts_Critical" "Number of critical code scanning alerts" "string" "false" "0" "" "org_and_repo_actors"
create_property "CodeAlerts_High" "Number of high code scanning alerts" "string" "false" "0" "" "org_and_repo_actors"
create_property "CodeAlerts_Medium" "Number of medium code scanning alerts" "string" "false" "0" "" "org_and_repo_actors"
create_property "CodeAlerts_Low" "Number of low code scanning alerts" "string" "false" "0" "" "org_and_repo_actors"

# Secret scanning alerts (total only, no severity levels)
create_property "SecretAlerts_Total" "Total number of secret scanning alerts" "string" "false" "0" "" "org_and_repo_actors"

# Dependency alerts by severity
create_property "DependencyAlerts_Critical" "Number of critical dependency alerts" "string" "false" "0" "" "org_and_repo_actors"
create_property "DependencyAlerts_High" "Number of high dependency alerts" "string" "false" "0" "" "org_and_repo_actors"
create_property "DependencyAlerts_Moderate" "Number of moderate dependency alerts" "string" "false" "0" "" "org_and_repo_actors"
create_property "DependencyAlerts_Low" "Number of low dependency alerts" "string" "false" "0" "" "org_and_repo_actors"

echo "Repository properties creation completed."