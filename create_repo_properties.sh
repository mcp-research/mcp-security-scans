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
    local property_type="$3"
    local required="$4"
    local default_value="$5"
    
    echo "Creating property: $property_name ($property_type)"
    
    # Construct JSON payload
    json_data="{\"name\":\"$property_name\",\"description\":\"$property_description\",\"type\":\"$property_type\""
    
    # Add required field if specified
    if [ -n "$required" ]; then
        json_data="$json_data,\"required\":$required"
    fi
    
    # Add default value if specified (for string type)
    if [ -n "$default_value" ] && [ "$property_type" = "string" ]; then
        json_data="$json_data,\"default\":\"$default_value\""
    fi
    
    # Add default value if specified (for number or boolean type)
    if [ -n "$default_value" ] && [ "$property_type" != "string" ]; then
        json_data="$json_data,\"default\":$default_value"
    fi
    
    # Make properties settable by repository actors
    json_data="$json_data,\"allowed_values_setter\":\"REPOSITORY\""
    
    # Close JSON object
    json_data="$json_data}"
    
    # Make API call to create the property
    response=$(curl -s -X POST "https://api.github.com/orgs/$ORG_NAME/properties/schema" \
        -H "Accept: application/vnd.github+json" \
        -H "Authorization: token $TOKEN" \
        -H "X-GitHub-Api-Version: 2022-11-28" \
        -d "$json_data")
    
    # Check for errors
    if echo "$response" | grep -q "message"; then
        error_message=$(echo "$response" | grep -o '"message":"[^"]*"' | cut -d'"' -f4)
        
        # If the error message indicates the property already exists, that's okay
        if echo "$error_message" | grep -q "already exists"; then
            echo "  Property already exists, skipping."
        else
            echo "  Error creating property: $error_message"
        fi
    else
        echo "  Property created successfully."
    fi
}

# Create all the repository properties needed

# Last scan timestamp properties
create_property "GHAS_Status_Updated" "Timestamp of last GHAS status update" "string" "false" ""

# Total alert count properties (for backward compatibility)
create_property "CodeAlerts" "Total number of code scanning alerts" "number" "false" "0"
create_property "SecretAlerts" "Total number of secret scanning alerts" "number" "false" "0"
create_property "DependencyAlerts" "Total number of dependency alerts" "number" "false" "0"

# Code scanning alerts by severity
create_property "CodeAlerts_Critical" "Number of critical code scanning alerts" "number" "false" "0"
create_property "CodeAlerts_High" "Number of high code scanning alerts" "number" "false" "0"
create_property "CodeAlerts_Medium" "Number of medium code scanning alerts" "number" "false" "0"
create_property "CodeAlerts_Low" "Number of low code scanning alerts" "number" "false" "0"

# Secret scanning alerts (total only, no severity levels)
create_property "SecretAlerts_Total" "Total number of secret scanning alerts" "number" "false" "0"

# Dependency alerts by severity
create_property "DependencyAlerts_Critical" "Number of critical dependency alerts" "number" "false" "0"
create_property "DependencyAlerts_High" "Number of high dependency alerts" "number" "false" "0"
create_property "DependencyAlerts_Moderate" "Number of moderate dependency alerts" "number" "false" "0"
create_property "DependencyAlerts_Low" "Number of low dependency alerts" "number" "false" "0"

echo "Repository properties creation completed."