#!/usr/bin/env python3

import argparse
import datetime
import json
import logging
import os
import sys
from collections import defaultdict, Counter
from pathlib import Path
from typing import Any, Dict, List
from dotenv import load_dotenv

from .github import (
    get_github_client,
    list_all_repository_properties_for_org,
    show_rate_limit
)
from .constants import Constants

# Configuration
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logging.getLogger("githubkit").setLevel(logging.WARNING)
load_dotenv()


def analyze_property_values(all_properties: List[Any]) -> Dict[str, Any]:
    """
    Analyzes all repository properties and generates a summary.

    Args:
        all_properties: List of repository property objects from GitHub API

    Returns:
        Dictionary containing analysis results
    """
    logging.info(f"Analyzing properties for [{len(all_properties)}] repositories...")

    # Initialize analysis structures with explicit typing
    property_stats: Dict[str, Dict[str, Any]] = {}

    repos_analyzed = 0
    repos_with_properties = 0
    total_properties_found = 0

    # Process each repository's properties
    for repo_data in all_properties:
        repos_analyzed += 1
        repo_name = repo_data.repository_full_name
        properties = repo_data.properties

        if properties:
            repos_with_properties += 1
            total_properties_found += len(properties)

            # Process each property for this repository
            for prop in properties:
                prop_name = prop.property_name
                prop_value = prop.value

                # Initialize property stats if not seen before
                if prop_name not in property_stats:
                    property_stats[prop_name] = {
                        'total_repos_with_property': 0,
                        'unique_values': set(),
                        'value_counts': Counter(),
                        'numeric_values': [],
                        'repositories': [],
                        'value_to_repos': defaultdict(list)
                    }

                # Update statistics for this property
                stats = property_stats[prop_name]
                stats['total_repos_with_property'] += 1
                stats['unique_values'].add(prop_value)
                stats['value_counts'][prop_value] += 1
                stats['repositories'].append(repo_name)
                stats['value_to_repos'][prop_value].append(repo_name)

                # Try to parse as numeric value for additional analysis
                try:
                    numeric_value = float(prop_value)
                    stats['numeric_values'].append(numeric_value)
                except (ValueError, TypeError):
                    # Not a numeric value, that's fine
                    pass

    # Calculate summary statistics for each property
    summary_stats = {}
    for prop_name, stats in property_stats.items():
        # Handle None values in sorting - put None values first, then sort the rest
        unique_values_list = list(stats['unique_values'])
        none_values = [v for v in unique_values_list if v is None]
        non_none_values = [v for v in unique_values_list if v is not None]

        # Sort non-None values, handling mixed types gracefully
        try:
            sorted_non_none = sorted(non_none_values)
        except TypeError:
            # If we can't sort due to mixed types, convert all to strings
            sorted_non_none = sorted(non_none_values, key=str)

        # Combine None values (first) with sorted non-None values
        all_sorted_values = none_values + sorted_non_none

        prop_summary = {
            'total_repos_with_property': stats['total_repos_with_property'],
            'unique_value_count': len(stats['unique_values']),
            'most_common_values': stats['value_counts'].most_common(10),
            'all_unique_values': all_sorted_values,
            'most_common_with_examples': []  # Will contain tuples of (value, count, example_repos)
        }

        # Create most common values with repository examples
        for value, count in stats['value_counts'].most_common(10):
            example_repos = stats['value_to_repos'][value][:5]  # Get up to 5 examples
            prop_summary['most_common_with_examples'].append((value, count, example_repos))

        # Add numeric statistics if we have numeric values
        if stats['numeric_values']:
            numeric_vals = stats['numeric_values']
            prop_summary['numeric_stats'] = {
                'min': min(numeric_vals),
                'max': max(numeric_vals),
                'avg': sum(numeric_vals) / len(numeric_vals),
                'total': sum(numeric_vals),
                'count_non_zero': len([v for v in numeric_vals if v != 0]),
                'count_zero': len([v for v in numeric_vals if v == 0])
            }

        summary_stats[prop_name] = prop_summary

    # Overall summary
    overall_summary = {
        'total_repositories_analyzed': repos_analyzed,
        'repositories_with_properties': repos_with_properties,
        'repositories_without_properties': repos_analyzed - repos_with_properties,
        'total_properties_found': total_properties_found,
        'unique_property_names': sorted(list(property_stats.keys())),
        'property_count': len(property_stats),
        'analysis_timestamp': datetime.datetime.now().isoformat()
    }

    return {
        'overall_summary': overall_summary,
        'property_details': summary_stats
    }


def generate_property_summary_report(analysis_results: Dict[str, Any], target_org: str, output_dir: str = "reports") -> str:
    """
    Generates a detailed report from the property analysis results.

    Args:
        analysis_results: Results from analyze_property_values()
        target_org: Target organization name
        output_dir: Directory to save the report

    Returns:
        Path to the generated report file
    """
    # Create reports directory if it doesn't exist
    Path(output_dir).mkdir(parents=True, exist_ok=True)

    overall = analysis_results['overall_summary']
    properties = analysis_results['property_details']

    # Generate report filename with timestamp
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    report_filename = f"property_summary_{target_org}_{timestamp}.txt"
    report_path = Path(output_dir) / report_filename

    with open(report_path, 'w') as f:
        # Write header
        f.write("=" * 80 + "\n")
        f.write("REPOSITORY PROPERTY SUMMARY REPORT\n")
        f.write(f"Organization: [{target_org}]\n")
        f.write(f"Generated: [{overall['analysis_timestamp']}]\n")
        f.write("=" * 80 + "\n\n")

        # Write overall summary
        f.write("OVERALL SUMMARY\n")
        f.write("-" * 40 + "\n")
        f.write(f"Total repositories analyzed: [{overall['total_repositories_analyzed']}]\n")
        f.write(f"Repositories with properties: [{overall['repositories_with_properties']}]\n")
        f.write(f"Repositories without properties: [{overall['repositories_without_properties']}]\n")
        f.write(f"Total properties found: [{overall['total_properties_found']}]\n")
        f.write(f"Unique property names: [{overall['property_count']}]\n")
        f.write(f"Property coverage: [{(overall['repositories_with_properties']/overall['total_repositories_analyzed']*100):.1f}%]\n")
        f.write("\n")

        # Write property names list
        f.write("PROPERTY NAMES FOUND\n")
        f.write("-" * 40 + "\n")
        for i, prop_name in enumerate(overall['unique_property_names'], 1):
            f.write(f"  [{i:2d}]. [{prop_name}]\n")
        f.write("\n")

        # Write detailed property analysis
        f.write("DETAILED PROPERTY ANALYSIS\n")
        f.write("=" * 80 + "\n")

        for prop_name in sorted(properties.keys()):
            prop_data = properties[prop_name]
            f.write(f"\nProperty: [{prop_name}]\n")
            f.write("-" * (len(prop_name) + 12) + "\n")
            f.write(f"Repositories with this property: [{prop_data['total_repos_with_property']}]\n")
            f.write(f"Unique values: [{prop_data['unique_value_count']}]\n")

            # Write numeric statistics if available
            if 'numeric_stats' in prop_data:
                stats = prop_data['numeric_stats']
                f.write("Numeric Statistics:\n")
                f.write(f"  Total sum: [{stats['total']:.1f}]\n")
                f.write(f"  Average: [{stats['avg']:.2f}]\n")
                f.write(f"  Min: [{stats['min']:.1f}]\n")
                f.write(f"  Max: [{stats['max']:.1f}]\n")
                f.write(f"  Non-zero values: [{stats['count_non_zero']}]\n")
                f.write(f"  Zero values: [{stats['count_zero']}]\n")

            # Write most common values with repository examples
            f.write("Most common values:\n")
            for value, count, example_repos in prop_data['most_common_with_examples']:
                percentage = (count / prop_data['total_repos_with_property']) * 100
                f.write(f"  '{value}': [{count}] repositories ([{percentage:.1f}%])\n")

                # Show repository examples, with special attention to SecretAlerts_Total
                if example_repos:
                    if prop_name == "SecretAlerts_Total" or len(example_repos) > 0:
                        example_text = ", ".join(example_repos)
                        if len(example_repos) < count:
                            f.write(f"    Example repositories: [{example_text}]... (and [{count - len(example_repos)}] others)\n")
                        else:
                            f.write(f"    Example repositories: [{example_text}]\n")
                f.write("\n")

            # If there are few unique values, list them all
            if prop_data['unique_value_count'] <= 20:
                f.write(f"All unique values: {prop_data['all_unique_values']}\n")

            f.write("\n")

    logging.info(f"Property summary report saved to [{report_path}]")
    return str(report_path)


def generate_json_summary(analysis_results: Dict[str, Any], target_org: str, output_dir: str = "reports") -> str:
    """
    Generates a JSON summary file for programmatic access.

    Args:
        analysis_results: Results from analyze_property_values()
        target_org: Target organization name
        output_dir: Directory to save the JSON file

    Returns:
        Path to the generated JSON file
    """
    # Create reports directory if it doesn't exist
    Path(output_dir).mkdir(parents=True, exist_ok=True)

    # Generate JSON filename with timestamp
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    json_filename = f"property_summary_{target_org}_{timestamp}.json"
    json_path = Path(output_dir) / json_filename

    # Convert sets to lists for JSON serialization
    json_data = {}
    for key, value in analysis_results.items():
        if key == 'property_details':
            json_data[key] = {}
            for prop_name, prop_data in value.items():
                json_prop_data = dict(prop_data)
                # Convert set to list and handle None values in sorting
                unique_values_list = list(prop_data['all_unique_values'])
                none_values = [v for v in unique_values_list if v is None]
                non_none_values = [v for v in unique_values_list if v is not None]

                # Sort non-None values, handling mixed types gracefully
                try:
                    sorted_non_none = sorted(non_none_values)
                except TypeError:
                    # If we can't sort due to mixed types, convert all to strings
                    sorted_non_none = sorted(non_none_values, key=str)

                # Combine None values (first) with sorted non-None values
                json_prop_data['all_unique_values'] = none_values + sorted_non_none

                # Convert most_common_with_examples tuples to dictionaries for JSON
                json_prop_data['most_common_with_examples'] = [
                    {
                        'value': value,
                        'count': count,
                        'percentage': round((count / prop_data['total_repos_with_property']) * 100, 1),
                        'example_repositories': example_repos
                    }
                    for value, count, example_repos in prop_data['most_common_with_examples']
                ]

                json_data[key][prop_name] = json_prop_data
        else:
            json_data[key] = value

    with open(json_path, 'w') as f:
        json.dump(json_data, f, indent=2, default=str)

    logging.info(f"Property summary JSON saved to [{json_path}]")
    return str(json_path)


def main():
    """Main execution function."""
    start_time = datetime.datetime.now()

    parser = argparse.ArgumentParser(description="Generate a summary of all repository properties in an organization.")
    parser.add_argument("--target-org", default=Constants.Org.TARGET_ORG,
                        help=f"Target GitHub organization to analyze (default: [{Constants.Org.TARGET_ORG}])")
    parser.add_argument("--output-dir", default="reports",
                        help="Directory to save report files (default: reports)")
    parser.add_argument("--json-only", action="store_true",
                        help="Generate only JSON output, skip text report")
    parser.add_argument("--verbose", "-v", action="store_true",
                        help="Enable verbose logging")

    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
        logging.getLogger("githubkit").setLevel(logging.INFO)

    # Load credentials from environment variables
    app_id = os.getenv("GH_APP_ID")
    private_key = os.getenv("GH_APP_PRIVATE_KEY")

    if not app_id:
        logging.error("GH_APP_ID environment variable not set.")
        sys.exit(1)

    if not private_key:
        logging.error("GH_APP_PRIVATE_KEY environment variable not set.")
        sys.exit(1)

    try:
        # --- Authentication ---
        gh = get_github_client(app_id, private_key)

        # Show initial rate limit
        show_rate_limit(gh)

        # --- Load all repository properties ---
        logging.info(f"Loading all repository properties for organization [{args.target_org}]...")
        all_properties = list_all_repository_properties_for_org(gh, args.target_org)

        if not all_properties:
            logging.warning(f"No repository properties found for organization [{args.target_org}]")
            sys.exit(0)

        # --- Analyze properties ---
        logging.info("Analyzing repository properties...")
        analysis_results = analyze_property_values(all_properties)

        # --- Generate reports ---
        logging.info("Generating summary reports...")

        # Always generate JSON
        json_path = generate_json_summary(analysis_results, args.target_org, args.output_dir)

        # Generate text report unless json-only is specified
        if not args.json_only:
            text_path = generate_property_summary_report(analysis_results, args.target_org, args.output_dir)
            logging.info(f"Text report generated: [{text_path}]")

        logging.info(f"JSON summary generated: [{json_path}]")

        # Show final rate limit
        show_rate_limit(gh)

        # Print execution summary
        end_time = datetime.datetime.now()
        execution_time = end_time - start_time

        overall = analysis_results['overall_summary']
        logging.info(f"Property analysis completed in [{execution_time}]")
        logging.info(f"Analyzed [{overall['total_repositories_analyzed']}] repositories")
        logging.info(f"Found [{overall['property_count']}] unique property types")
        logging.info(f"Total properties: [{overall['total_properties_found']}]")

    except KeyboardInterrupt:
        logging.info("Operation cancelled by user.")
        sys.exit(1)
    except Exception as e:
        logging.error(f"An error occurred: [{e}]")
        if args.verbose:
            import traceback
            traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
