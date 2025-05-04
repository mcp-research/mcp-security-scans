#!/usr/bin/env python3

import os
import argparse
import logging
import datetime
import json
from pathlib import Path
from typing import Dict, List, Any, Optional
from collections import defaultdict
from dotenv import load_dotenv

# Import the local functions
from github import (
    get_github_client, list_all_repository_properties_for_org,
    show_rate_limit
)

# Configuration
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logging.getLogger("githubkit").setLevel(logging.WARNING)  # Reduce verbosity from githubkit
load_dotenv()  # Load environment variables from .env file

# Constants
DEFAULT_TARGET_ORG = "mcp-research"  # Default organization to scan
CODE_ALERTS = "CodeAlerts"  # Property name for code scanning alerts
SECRET_ALERTS = "SecretAlerts"  # Property name for secret scanning alerts
DEPENDENCY_ALERTS = "DependencyAlerts"  # Property name for dependency alerts
GHAS_STATUS_UPDATED = "GHAS_Status_Updated"  # Property name for last scan timestamp
REPORT_DIR = "reports"  # Directory to save reports

def parse_iso_date(date_string: str) -> Optional[datetime.datetime]:
    """
    Parse an ISO format date string to a datetime object.
    
    Args:
        date_string: ISO format date string.
        
    Returns:
        datetime object or None if parsing fails.
    """
    try:
        return datetime.datetime.fromisoformat(date_string)
    except (ValueError, TypeError):
        return None

def safe_int_convert(value, default=0):
    """
    Safely convert a value to integer, returning default if conversion fails.
    
    Args:
        value: Value to convert.
        default: Default value to return if conversion fails.
        
    Returns:
        Integer value or default.
    """
    if value is None:
        return default
    try:
        return int(value)
    except (ValueError, TypeError):
        return default

def get_report_filename(target_org: str, output_dir: str, extension: str) -> str:
    """
    Generate a standardized report filename.
    
    Args:
        target_org: Target organization name
        output_dir: Directory to save the report
        extension: File extension (e.g., 'json', 'md')
        
    Returns:
        Full path to the report file
    """
    date_str = datetime.datetime.now().strftime('%Y%m%d')
    return f"{output_dir}/ghas_report_{target_org}_{date_str}.{extension}"

def generate_report(repo_properties: List[Dict], target_org: str, output_dir: str = REPORT_DIR) -> Dict:
    """
    Generate a report from repository properties.
    
    Args:
        repo_properties: List of repository properties.
        target_org: Target organization name.
        output_dir: Directory to save report files.
        
    Returns:
        Dictionary with report statistics.
    """
    # Create reports directory if it doesn't exist
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    
    # Initialize counters and data structures
    total_repos = len(repo_properties)
    scanned_repos = 0
    repos_with_alerts = 0
    
    total_code_alerts = 0
    total_secret_alerts = 0
    total_dependency_alerts = 0
    
    # Dictionary to track alerts by date
    alerts_by_date = defaultdict(lambda: {
        'code': 0,
        'secret': 0,
        'dependency': 0,
        'total': 0
    })
    
    # Dictionary to store repositories with alerts
    repos_alerts = {}
    
    # Process each repository's properties
    for repo_prop in repo_properties:
        repo_name = repo_prop.repository_name
        full_name = f"{target_org}/{repo_name}"
        
        # Extract properties
        properties = {prop.property_name: prop.value for prop in repo_prop.properties}
        
        # Check if repo has been scanned
        if GHAS_STATUS_UPDATED in properties:
            scanned_repos += 1
            
            # Parse scan date
            scan_date_str = properties.get(GHAS_STATUS_UPDATED)
            scan_date = parse_iso_date(scan_date_str)
            
            # Get alert counts - use safe conversion to handle None values
            code_alerts = safe_int_convert(properties.get(CODE_ALERTS, 0))
            secret_alerts = safe_int_convert(properties.get(SECRET_ALERTS, 0))
            dependency_alerts = safe_int_convert(properties.get(DEPENDENCY_ALERTS, 0))
            
            # Add to totals
            total_code_alerts += code_alerts
            total_secret_alerts += secret_alerts
            total_dependency_alerts += dependency_alerts
            
            # Track repositories with alerts
            if code_alerts > 0 or secret_alerts > 0 or dependency_alerts > 0:
                repos_with_alerts += 1
                repos_alerts[full_name] = {
                    'code': code_alerts,
                    'secret': secret_alerts,
                    'dependency': dependency_alerts,
                    'total': code_alerts + secret_alerts + dependency_alerts,
                    'scan_date': scan_date_str
                }
            
            # Track alerts by date
            if scan_date:
                date_key = scan_date.strftime('%Y-%m-%d')
                alerts_by_date[date_key]['code'] += code_alerts
                alerts_by_date[date_key]['secret'] += secret_alerts
                alerts_by_date[date_key]['dependency'] += dependency_alerts
                alerts_by_date[date_key]['total'] += (code_alerts + secret_alerts + dependency_alerts)
    
    # Calculate totals
    total_alerts = total_code_alerts + total_secret_alerts + total_dependency_alerts
    
    # Generate summary statistics
    stats = {
        'organization': target_org,
        'total_repositories': total_repos,
        'scanned_repositories': scanned_repos,
        'repos_with_alerts': repos_with_alerts,
        'total_code_alerts': total_code_alerts,
        'total_secret_alerts': total_secret_alerts,
        'total_dependency_alerts': total_dependency_alerts,
        'total_alerts': total_alerts,
        'alerts_by_date': dict(alerts_by_date),
        'repos_alerts': repos_alerts,
        'report_date': datetime.datetime.now().isoformat(),
    }
    
    # Write JSON report
    report_file = get_report_filename(target_org, output_dir, 'json')
    with open(report_file, 'w') as f:
        json.dump(stats, f, indent=2)
    logging.info(f"JSON report saved to {report_file}")
    
    # Write Markdown report
    summary_file_path = os.getenv("GITHUB_STEP_SUMMARY")
    md_report_file = get_report_filename(target_org, output_dir, 'md')
    _write_markdown_report(stats, md_report_file, summary_file_path)
    #  when running in GitHub Actions, write the report also to the GITHUB_STEP_SUMMARY file
    if summary_file_path:
        try:
            with open(md_report_file, "r") as md_file:
                content = md_file.read()
                
            with open(summary_file_path, "a") as summary_file:
                summary_file.write(content + "\n\n")
            logging.info(f"Successfully appended summary to GITHUB_STEP_SUMMARY file")
        except Exception as e:
            logging.error(f"Failed to write to GITHUB_STEP_SUMMARY file: {e}")
    logging.info(f"Markdown report saved to {md_report_file}")
    
    return stats

def _write_markdown_report(stats: Dict, output_file, summary_file_path: str) -> None:
    """
    Write a markdown report from statistics.
    
    Args:
        stats: Dictionary with report statistics.
        output_file: File to write the report to.
    """
    with open(output_file, 'w') as f:
        f.write(f"# GHAS Security Report - {stats['organization']}\n\n")
        f.write(f"*Report generated on: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*\n\n")
        
        f.write("## Summary\n\n")
        f.write(f"- **Organization:** {stats['organization']}\n")
        f.write(f"- **Total Repositories:** {stats['total_repositories']}\n")
        f.write(f"- **Scanned Repositories:** {stats['scanned_repositories']}\n")
        f.write(f"- **Repositories with Alerts:** {stats['repos_with_alerts']}\n")
        f.write(f"- **Total Alerts:** {stats['total_alerts']}\n")
        f.write(f"  - Code Scanning Alerts: {stats['total_code_alerts']}\n")
        f.write(f"  - Secret Scanning Alerts: {stats['total_secret_alerts']}\n")
        f.write(f"  - Dependency Alerts: {stats['total_dependency_alerts']}\n\n")
        
        # Coverage statistics
        if stats['total_repositories'] > 0:
            scan_coverage = (stats['scanned_repositories'] / stats['total_repositories']) * 100
            f.write(f"## Coverage\n\n")
            f.write(f"- **Scan Coverage:** {scan_coverage:.1f}%\n")
        
        # Only show detailed repository section if not running in CI
        if not (os.getenv("CI")):
            f.write(f"\n## Top Repositories with Alerts\n\n")
            f.write("| Repository | Total Alerts | Code Alerts | Secret Alerts | Dependency Alerts | Last Scanned |\n")
            f.write("|------------|-------------|------------|--------------|-------------------|-------------|\n")
            
            # Sort repositories by total alerts
            top_repos = sorted(
                stats['repos_alerts'].items(), 
                key=lambda x: x[1]['total'], 
                reverse=True
            )
            
            # List top 10 repositories or all if less than 10
            for repo_name, repo_data in top_repos[:10]:
                f.write(f"| {repo_name} | {repo_data['total']} | {repo_data['code']} | {repo_data['secret']} | {repo_data['dependency']} | {repo_data['scan_date']} |\n")

def print_console_summary(stats: Dict) -> None:
    """
    Print a summary of the report to the console.
    
    Args:
        stats: Dictionary with report statistics.
    """
    print("\nGHAS Security Report Summary")
    print("=" * 30)
    print(f"Organization: {stats['organization']}")
    print(f"Total Repositories: {stats['total_repositories']}")
    print(f"Scanned Repositories: {stats['scanned_repositories']}")
    print(f"Repositories with Alerts: {stats['repos_with_alerts']}")
    print(f"Total Alerts: {stats['total_alerts']}")
    print(f"  - Code Scanning Alerts: {stats['total_code_alerts']}")
    print(f"  - Secret Scanning Alerts: {stats['total_secret_alerts']}")
    print(f"  - Dependency Alerts: {stats['total_dependency_alerts']}")
    
    # Calculate percentages if possible
    if stats['total_repositories'] > 0:
        scan_coverage = (stats['scanned_repositories'] / stats['total_repositories']) * 100
        print(f"Scan Coverage: {scan_coverage:.1f}%")
    
    # Only show sensitive data if not running in CI
    if not (os.getenv("CI")):
        print("\nTop 5 Repositories with Most Alerts:")
        top_repos = sorted(
            stats['repos_alerts'].items(), 
            key=lambda x: x[1]['total'], 
            reverse=True
        )
        
        for i, (repo_name, repo_data) in enumerate(top_repos[:5], 1):
            print(f"{i}. {repo_name}: {repo_data['total']} alerts")
    
    print(f"\nDetailed reports saved to {REPORT_DIR}/ directory")

def main() -> None:
    """
    Main execution function.
    """
    start_time = datetime.datetime.now()
    
    parser = argparse.ArgumentParser(description="Generate GHAS security reports from repository properties")
    parser.add_argument("--target-org", default=DEFAULT_TARGET_ORG, 
                       help=f"Target GitHub organization (default: {DEFAULT_TARGET_ORG})")
    parser.add_argument("--output-dir", default=REPORT_DIR, 
                       help=f"Directory to save reports (default: {REPORT_DIR})")
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
        return
    
    if not private_key:
        logging.error("GH_APP_PRIVATE_KEY environment variable not set.")
        return
    
    try:
        # Authentication
        gh = get_github_client(app_id, private_key)
        
        # Load repository properties
        logging.info(f"Loading repository properties for organization [{args.target_org}]...")
        repo_properties = list_all_repository_properties_for_org(gh, args.target_org)
        
        logging.info(f"Found properties for {len(repo_properties)} repositories in organization {args.target_org}")
        
        # Generate report
        stats = generate_report(repo_properties, args.target_org, args.output_dir)
        
        # Print summary to console
        print_console_summary(stats)
        
        # Show GitHub API rate limit
        show_rate_limit(gh)
        
        # Log execution time
        end_time = datetime.datetime.now()
        duration = end_time - start_time
        logging.info(f"Report generation completed in {duration}")
        
    except Exception as e:
        logging.error(f"Script failed with an error: {e}")

if __name__ == "__main__":
    main()