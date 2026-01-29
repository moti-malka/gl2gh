#!/usr/bin/env python3
"""
CLI entry point for the GitLab Discovery Agent.

Usage:
    # Scan a specific group:
    python -m discovery_agent --base-url https://gitlab.com --token TOKEN --root-group mygroup --out ./out
    
    # Scan ALL accessible groups (no --root-group):
    python -m discovery_agent --base-url https://gitlab.com --token TOKEN --out ./out
    
Or with environment variables in .env file:
    python -m discovery_agent
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from . import __version__
from .config import DiscoveryConfig
from .orchestrator import run_discovery
from .utils import setup_logging


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        prog="discovery_agent",
        description="GitLab Discovery Agent - Scan GitLab groups and produce migration readiness reports",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Scan a specific root group
  python -m discovery_agent --base-url https://gitlab.com --token glpat-xxx --root-group myorg --out ./output

  # Scan a SINGLE project (e.g., mygroup/myproject)
  python -m discovery_agent --project mygroup/myproject --out ./output

  # Scan ALL accessible groups (omit --root-group and --project)
  python -m discovery_agent --base-url https://gitlab.com --token glpat-xxx --out ./output

  # Using .env file (create .env with GITLAB_BASE_URL, GITLAB_TOKEN)
  python -m discovery_agent

  # Override .env with CLI arguments
  python -m discovery_agent --root-group different-group

Environment Variables (can be set in .env):
  GITLAB_BASE_URL                 GitLab instance URL
  GITLAB_TOKEN                    Personal Access Token  
  GITLAB_ROOT_GROUP               Root group to scan (optional - omit to scan all)
  GITLAB_PROJECT                  Single project path to scan (e.g., 'mygroup/myproject')
  OUTPUT_DIR                      Output directory (default: ./output)
  MAX_API_CALLS                   Maximum API calls (default: 5000)
  MAX_PER_PROJECT_CALLS           Maximum calls per project (default: 200)

Required Token Scopes:
  - read_api (for listing groups, projects, MRs, issues)
  - read_repository (for reading .gitlab-ci.yml, .gitattributes)
        """,
    )
    
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )
    
    # Connection settings
    parser.add_argument(
        "--base-url",
        metavar="URL",
        help="GitLab instance URL (e.g., https://gitlab.com)",
    )
    parser.add_argument(
        "--token",
        metavar="TOKEN",
        help="Personal Access Token for authentication",
    )
    parser.add_argument(
        "--root-group",
        metavar="GROUP",
        help="Root group path or ID to scan. If omitted, scans ALL accessible groups.",
    )
    parser.add_argument(
        "--project",
        metavar="PROJECT",
        help="Single project path or ID to scan (e.g., 'mygroup/myproject'). Overrides --root-group.",
    )
    
    # Output settings
    parser.add_argument(
        "--out",
        metavar="DIR",
        type=Path,
        help="Output directory for inventory.json (default: ./output)",
    )
    
    # Budget limits
    parser.add_argument(
        "--max-api-calls",
        metavar="N",
        type=int,
        help="Maximum total API calls (default: 5000)",
    )
    parser.add_argument(
        "--max-per-project-calls",
        metavar="N",
        type=int,
        help="Maximum API calls per project (default: 200)",
    )
    
    # Logging
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Enable verbose (debug) logging",
    )
    parser.add_argument(
        "-q", "--quiet",
        action="store_true",
        help="Suppress all output except errors",
    )
    
    # Deep analysis mode
    parser.add_argument(
        "--deep",
        action="store_true",
        help="Enable deep analysis with migration scoring per project",
    )
    parser.add_argument(
        "--deep-top-n",
        metavar="N",
        type=int,
        default=20,
        help="Limit deep analysis to top N projects by complexity (default: 20, 0=all)",
    )
    
    return parser.parse_args()


def main() -> int:
    """Main entry point."""
    args = parse_args()
    
    # Setup logging
    if args.quiet:
        log_level = logging.ERROR
    elif args.verbose:
        log_level = logging.DEBUG
    else:
        log_level = logging.INFO
    
    setup_logging(level=log_level)
    logger = logging.getLogger("discovery_agent")
    
    try:
        # Build configuration from args + env
        config = DiscoveryConfig.from_env(
            gitlab_base_url=args.base_url,
            gitlab_token=args.token,
            root_group=args.root_group,
            project_path=args.project,
            output_dir=str(args.out) if args.out else None,
            max_api_calls=args.max_api_calls,
            max_per_project_calls=args.max_per_project_calls,
            deep=args.deep if args.deep else None,
            deep_top_n=args.deep_top_n if args.deep else None,
        )
        
        if args.verbose:
            if config.single_project_mode:
                logger.debug(f"Configuration: base_url={config.gitlab_base_url}, project={config.project_path}, deep={config.deep}")
            else:
                logger.debug(f"Configuration: base_url={config.gitlab_base_url}, root_group={config.root_group or 'ALL'}, deep={config.deep}")
        
    except ValueError as e:
        logger.error(f"Configuration error: {e}")
        logger.error("Please provide required settings via CLI arguments or .env file")
        return 1
    
    try:
        # Run discovery
        inventory = run_discovery(config)
        
        # Report success
        stats = inventory["run"]["stats"]
        logger.info(
            f"Discovery complete: {stats['groups']} groups, "
            f"{stats['projects']} projects, {stats['errors']} errors"
        )
        
        return 0
        
    except KeyboardInterrupt:
        logger.warning("Discovery interrupted by user")
        return 130
        
    except Exception as e:
        logger.exception(f"Discovery failed: {e}")
        return 1


def serve() -> int:
    """Run the dashboard web server."""
    import argparse
    
    parser = argparse.ArgumentParser(
        prog="discovery_agent serve",
        description="Run the Discovery Agent web dashboard",
    )
    parser.add_argument(
        "--host",
        default="localhost",
        help="Host to bind to (default: localhost)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8080,
        help="Port to bind to (default: 8080)",
    )
    parser.add_argument(
        "--dir",
        type=Path,
        default=Path.cwd(),
        help="Directory containing scan outputs (default: current directory)",
    )
    
    args = parser.parse_args(sys.argv[2:])  # Skip 'discovery_agent' and 'serve'
    
    from .web.server import run_server
    run_server(host=args.host, port=args.port, scan_dir=args.dir)
    return 0


if __name__ == "__main__":
    # Check for subcommands
    if len(sys.argv) > 1 and sys.argv[1] == 'serve':
        sys.exit(serve())
    else:
        sys.exit(main())

