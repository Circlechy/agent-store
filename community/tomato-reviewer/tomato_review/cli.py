#!/usr/bin/env python
"""Command-line interface for tomato-review.

Usage:
    tomato-review *.py
    tomato-review file1.py file2.py
    tomato-review --help
"""

import argparse
import asyncio
import glob
import os
import shutil
import signal
import subprocess
import sys
import warnings
from pathlib import Path
from typing import List

from tqdm import TqdmExperimentalWarning

try:
    from tqdm.rich import tqdm
except ImportError:
    from tqdm.auto import tqdm


from openjiuwen import __version__ as jiuwen_version
from openjiuwen.core.foundation.llm.model import Model
from openjiuwen.core.foundation.llm.schema.config import ModelClientConfig, ModelRequestConfig

from tomato_review import __version__
from tomato_review.agent import ReviewerAgent, SearcherAgent
from tomato_review.agent.utils import setup_tomato_directories
from tomato_review.config import get_kb_config, get_llm_config, load_config
from tomato_review.kb_utils import check_knowledge_base, setup_knowledge_base_if_needed
from tomato_review.pretty_printing import (
    CBLU,
    CEND,
    CRED,
    print_ascii_art,
    print_blue,
    print_cyan,
    print_error,
    print_green,
    print_success,
    print_warning,
)

# Filter out TqdmExperimentalWarning
warnings.filterwarnings("ignore", category=TqdmExperimentalWarning, module="tqdm")

# Global state for cleanup
_cleanup_state = {
    "backup_files": set(),
    "modified_files": set(),
    "tomato_dirs": None,
}


def signal_handler(signum, frame):  # noqa: ARG001
    """Handle Ctrl+C and restore files."""
    print_warning("\n\nInterrupted by user. Cleaning up...")

    # Restore modified files from backup
    tomato_dirs = _cleanup_state.get("tomato_dirs")
    if tomato_dirs:
        backup_dir = tomato_dirs["backup"]
        for modified_file in _cleanup_state["modified_files"]:
            try:
                source_path = Path(modified_file)
                # Find backup file
                try:
                    rel_path = source_path.relative_to(Path.cwd())
                except ValueError:
                    rel_path = source_path.name

                backup_path = backup_dir / rel_path
                if backup_path.exists():
                    shutil.copy2(backup_path, source_path)
                    print_success(f"Restored: {source_path}")
                else:
                    print_warning(f"Backup not found: {backup_path}")
            except (OSError, shutil.Error) as e:
                print_error(f"Failed to restore {modified_file}: {e}")

    print_cyan("Cleanup complete.")
    sys.exit(130)


def check_required_tools():
    """Check if required tools (pylint and mypy) are installed.

    Raises:
        SystemExit: If any required tool is not installed
    """
    missing_tools = []

    # Check pylint
    try:
        result = subprocess.run(
            ["pylint", "--version"],
            capture_output=True,
            timeout=5,
            check=False,
        )
        if result.returncode != 0:
            missing_tools.append("pylint")
    except (FileNotFoundError, subprocess.TimeoutExpired):
        missing_tools.append("pylint")

    # Check mypy
    try:
        result = subprocess.run(
            ["mypy", "--version"],
            capture_output=True,
            timeout=5,
            check=False,
        )
        if result.returncode != 0:
            missing_tools.append("mypy")
    except (FileNotFoundError, subprocess.TimeoutExpired):
        missing_tools.append("mypy")

    if missing_tools:
        print_error(f"\nRequired tools are not installed: {', '.join(missing_tools)}")
        print_cyan("\nPlease install the missing tools:")
        for tool in missing_tools:
            print_cyan(f"  pip install {tool}")
        sys.exit(1)


def expand_file_patterns(patterns: List[str]) -> List[str]:
    """Expand glob patterns and return list of existing Python files.

    Args:
        patterns: List of file patterns (may contain glob patterns like *.py)

    Returns:
        List of resolved file paths
    """
    files = []
    for pattern in patterns:
        # Check if pattern contains glob characters
        has_glob = "*" in pattern or "?" in pattern or "[" in pattern

        if has_glob:
            # Expand glob pattern
            # Try recursive first (for patterns like **/*.py)
            matches = glob.glob(pattern, recursive=True)
            # If no matches with recursive, try non-recursive
            if not matches:
                matches = glob.glob(pattern, recursive=False)
        else:
            # No glob characters, treat as literal file path
            if os.path.isfile(pattern):
                matches = [pattern]
            elif os.path.isdir(pattern):
                # If it's a directory, find all Python files in it
                matches = list(Path(pattern).rglob("*.py"))
                matches = [str(m) for m in matches]
            else:
                matches = []

        if not matches:
            print_warning(f"No files found matching pattern: {pattern}")
            continue

        # Filter to only Python files
        for match in matches:
            path = Path(match)
            if path.is_file() and path.suffix == ".py":
                files.append(str(path.resolve()))
            elif path.is_file():
                print_warning(f"Skipping non-Python file: {match}")

    # Remove duplicates while preserving order
    seen = set()
    unique_files = []
    for f in files:
        if f not in seen:
            seen.add(f)
            unique_files.append(f)

    return unique_files


async def main():
    """Main CLI entry point."""
    print_ascii_art()
    print_cyan(f"Tomato Reviewer version: {__version__}")
    print_cyan(f"Using openJiuwen version: {jiuwen_version}")

    # Set up signal handler for cleanup
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    parser = argparse.ArgumentParser(
        description="Tomato Review - Python code review agent using pylint and PEP knowledge base",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  tomato-review *.py                    # Review all Python files in current directory
  tomato-review file1.py file2.py       # Review specific files
  tomato-review src/**/*.py             # Review all Python files in src/ recursively
        """,
    )

    parser.add_argument(
        "files",
        nargs="*",
        help="Python files or glob patterns to review (e.g., *.py, file1.py file2.py)",
    )

    parser.add_argument(
        "-m",
        "--max-iter",
        type=int,
        default=5,
        help="Maximum iterations of file review-fix cycles (default: 5)",
    )

    parser.add_argument(
        "-s",
        "--searcher-max-iter",
        type=int,
        default=5,
        help="Maximum iterations of searcher agent (default: 5)",
    )

    parser.add_argument(
        "-f",
        "--fixer-max-iter",
        type=int,
        default=50,
        help="Maximum iterations of fixer agent (default: 50)",
    )

    parser.add_argument(
        "-b",
        "--mini-batch",
        type=int,
        default=20,
        help="Mini batch size for files to process at the same time (default: 20)",
    )

    parser.add_argument(
        "--no-fix",
        action="store_true",
        help="Only review files without applying fixes",
    )

    parser.add_argument(
        "--build",
        action="store_true",
        help="Builds Knowledge Base from scratch",
    )

    parser.add_argument(
        "--config-file",
        type=str,
        default=None,
        help="Path to config file (tomato.yaml, .tomato.yaml, or pyproject.toml)",
    )

    args = parser.parse_args()
    if not args.build and not args.files:
        parser.error("files are required unless --build is used")

    # Check required tools (pylint and mypy)
    check_required_tools()

    # Load configuration
    config = load_config()
    if not config:
        print_warning("No configuration file found (tomato.yaml, .tomato.yaml, or pyproject.toml)")
        print_warning("Some features may not work.")

    # Get KB and LLM configs
    kb_config = get_kb_config(config)
    llm_config = get_llm_config(config)

    # Map config keys to environment variable names (agents expect specific names)
    env_var_mapping = {
        # LLM config
        "api_base": "API_BASE",
        "api_key": "API_KEY",
        "model_name": "MODEL_NAME",
        "model_provider": "MODEL_PROVIDER",
        "verify_ssl": "VERIFY_SSL",
        "ssl_cert": "SSL_CERT",
        # KB config
        "kb_id": "PEP_KB_ID",
        "milvus_uri": "MILVUS_URI",
        "milvus_token": "MILVUS_TOKEN",
        "database_name": "MILVUS_DATABASE",
        "embedding_model_name": "EMBEDDING_MODEL",
        "embedding_api_key": "EMBEDDING_API_KEY",
        "embedding_base_url": "EMBEDDING_BASE_URL",
        "embedding_dimension": "EMBEDDING_DIMENSION",
        "chunk_size": "PEP_CHUNK_SIZE",
        "chunk_overlap": "PEP_CHUNK_OVERLAP",
        "index_type": "PEP_INDEX_TYPE",
    }

    # Set environment variables for agents (they read from os.getenv)
    all_config = {**kb_config, **llm_config}
    for key, value in all_config.items():
        if value:
            env_var_name = env_var_mapping.get(key, key.upper())
            os.environ[env_var_name] = str(value) if not isinstance(value, bool) else str(value).lower()

    # Check and setup knowledge base
    print_blue("Checking knowledge base...")
    is_valid, error, should_continue = check_knowledge_base(kb_config)
    build_kb = args.build

    if build_kb or not is_valid:
        if build_kb or should_continue:
            # KB just needs to be created - offer to create it
            if build_kb:
                print_cyan("Knowledge base will be rebuilt.")
                response = "y"
            else:
                print_warning(f"Knowledge base not found: {error}")
                response = ""
            while response not in {"", "y"}:
                response = input(f"\r{CRED}Create knowledge base now? (y/n, default=y): {CEND}").strip().lower()
                if response == "n":
                    print_error("Cannot continue without knowledge base.")
                    sys.exit(1)
            try:
                await setup_knowledge_base_if_needed(kb_config)
            except Exception as e:
                print_error("Error setting up knowledge base")
                raise e
        else:
            # Configuration or connection issue - show error and help, then exit
            print_error(f"\n{error}")
            print_cyan("\nPlease check your configuration:")
            print_cyan("  1. Ensure Milvus is running and accessible")
            print_cyan("  2. Verify your configuration file (tomato.yaml, .tomato.yaml, or pyproject.toml)")
            print_cyan("  3. Check that all required fields are set:")
            print_cyan("     - kb_id")
            print_cyan("     - milvus_uri")
            print_cyan("     - database_name")
            print_cyan("\nExample configuration in tomato.yaml:")
            print_cyan("  tomato-review:")
            print_cyan('    kb_id: "edinburgh"')
            print_cyan('    milvus_uri: "http://localhost:19530"')
            print_cyan('    database_name: "pep_kb"')
            sys.exit(1)
    else:
        print_success("Knowledge base is accessible")
        # Still update changed PEPs
        try:
            from tomato_review.pep_kb.pep_knowledge_base import create_pep_knowledge_base

            pep_kb = await create_pep_knowledge_base(**kb_config)
            print_blue("Getting latest PEPs...")
            stats = await pep_kb.update_changed_peps(filter_status=True)
            if stats["updated"] or stats["added"]:
                print_success(f"Updated: {len(stats['updated'])} PEPs, Added: {len(stats['added'])} PEPs")
        except Exception as e:
            print_warning(f"Could not update PEPs: {e}")

    print()

    # Expand file patterns
    files = expand_file_patterns(args.files)

    if not files:
        print_error("No Python files found to review.")
        sys.exit(1)

    print_blue(f"Found {len(files)} file(s) to review:")
    cwd = Path.cwd()
    for f in files:
        file_path = Path(f)
        try:
            # Try to show relative path
            rel_path = file_path.relative_to(cwd)
            print_cyan(f"  - {rel_path}")
        except ValueError:
            # If not relative to cwd, show absolute path
            print_cyan(f"  - {file_path}")
    print()

    # Set up tomato directories
    _cleanup_state["tomato_dirs"] = setup_tomato_directories()

    # Validate configuration before initializing agents
    missing_llm_config = [k for k, v in llm_config.items() if v == ""]
    if missing_llm_config:
        print_error(f"\nMissing required LLM configuration: {', '.join(missing_llm_config)}")
        print_cyan("\nPlease check your configuration file (tomato.yaml, .tomato.yaml, or pyproject.toml)")
        print_cyan("Required LLM settings:")
        print_cyan("  - api_base")
        print_cyan("  - api_key")
        print_cyan("  - model_name")
        print_cyan("  - model_provider")
        sys.exit(1)

    # Verify LLM connectivity before initializing agents
    print_blue("Verifying LLM connectivity...")
    try:
        # Parse verify_ssl
        verify_ssl_value = llm_config.get("verify_ssl")
        if isinstance(verify_ssl_value, str):
            verify_ssl = verify_ssl_value.lower() == "true"
        else:
            verify_ssl = verify_ssl_value if verify_ssl_value is not None else True

        # Get ssl_cert if provided
        ssl_cert = llm_config.get("ssl_cert")

        # Create Model configs from llm_config
        model_client_config = ModelClientConfig(
            client_provider=llm_config.get("model_provider", "OpenAI"),
            api_key=llm_config.get("api_key", ""),
            api_base=llm_config.get("api_base", ""),
            verify_ssl=verify_ssl,
            ssl_cert=ssl_cert,
        )
        model_request_config = ModelRequestConfig(
            model_name=llm_config.get("model_name", ""),
        )

        # Create Model instance
        test_model = Model(
            model_client_config=model_client_config,
            model_config=model_request_config,
        )

        # Test with minimal invocation (1 token input, 1 token output)
        test_response = await test_model.invoke(
            "test",
            model=llm_config.get("model_name", ""),
            max_tokens=1,
            timeout=10.0,
        )

        if not test_response or not test_response.content:
            raise ValueError("LLM returned empty response")

        print_success("LLM connectivity verified")
    except Exception as e:
        error_msg = str(e).lower()
        print_error(f"\nLLM connectivity verification failed: {e}")

        # Provide helpful messages for common errors
        if "api" in error_msg or "key" in error_msg or "auth" in error_msg or "unauthorized" in error_msg:
            print_cyan("\nThis appears to be an API authentication error.")
            print_cyan("Please check:")
            print_cyan("  1. Your API key is correct and valid")
            print_cyan("  2. Your API base URL is correct")
            print_cyan("  3. Your API key has the necessary permissions")
        elif "connection" in error_msg or "timeout" in error_msg or "network" in error_msg:
            print_cyan("\nThis appears to be a connection error.")
            print_cyan("Please check:")
            print_cyan("  1. Your network connection")
            print_cyan("  2. The API base URL is reachable")
            print_cyan("  3. There are no firewall restrictions")
        elif "model" in error_msg or "not found" in error_msg:
            print_cyan("\nThis appears to be a model configuration error.")
            print_cyan("Please check:")
            print_cyan("  1. Your model name is correct")
            print_cyan("  2. The model is available in your API provider")

        raise e

    # Initialize agents
    os.environ["REACT_MAX_ITER_REVIEW"] = str(args.max_iter)
    os.environ["REACT_MAX_ITER_SEARCH"] = str(args.searcher_max_iter)
    os.environ["REACT_MAX_ITER_FIX"] = str(args.fixer_max_iter)
    with tqdm(total=len(files), desc="Reviewing files", unit="file") as pbar:
        try:
            print_blue("\nInitializing agents...")
            searcher = SearcherAgent()
            reviewer = ReviewerAgent(
                searcher_agent=searcher,
                generate_fixed_files=not args.no_fix,
                pbar=pbar,
            )
            print_success("Agents initialized\n")
        except Exception as e:
            error_msg = str(e).lower()
            print_error(f"\nError initializing agents: {e}")

            # Provide helpful messages for common errors
            if "api" in error_msg or "key" in error_msg or "auth" in error_msg or "unauthorized" in error_msg:
                print_cyan("\nThis appears to be an API authentication error.")
                print_cyan("Please check:")
                print_cyan("  1. Your API key is correct and valid")
                print_cyan("  2. Your API base URL is correct")
                print_cyan("  3. Your API key has the necessary permissions")
            elif "connection" in error_msg or "timeout" in error_msg or "network" in error_msg:
                print_cyan("\nThis appears to be a connection error.")
                print_cyan("Please check:")
                print_cyan("  1. Your network connection")
                print_cyan("  2. The API base URL is reachable")
                print_cyan("  3. There are no firewall restrictions")
            elif "embedding" in error_msg or "milvus" in error_msg:
                print_cyan("\nThis appears to be a knowledge base or embedding error.")
                print_cyan("Please check:")
                print_cyan("  1. Your embedding API configuration")
                print_cyan("  2. Milvus connection settings")

            import traceback

            traceback.print_exc()
            sys.exit(1)

        # Run review with progress bar
        try:
            print_blue(f"Starting review process (batch size: {args.mini_batch})...")
            print(f"{CBLU}{'=' * 80}{CEND}")

            for i in range(0, len(files), args.mini_batch):
                j = i + args.mini_batch
                _cleanup_state["modified_files"].update(files[i:j])
                result = await reviewer.invoke({"files": files[i:j]})

                # Check for errors in result
                if not result:
                    print_error("\nReview returned no results")
                    sys.exit(1)

                # Check if any files failed to process
                reports = result.get("reports", [])
                if reports:
                    failed_files = []
                    for report in reports:
                        if report.get("errors") and isinstance(report.get("errors"), str):
                            # Error message instead of error list
                            failed_files.append(report.get("file_path", "Unknown"))
                        elif "Error" in str(report.get("report", "")):
                            failed_files.append(report.get("file_path", "Unknown"))

                    if failed_files:
                        print_warning(f"\n{len(failed_files)} file(s) had errors during review:")
                        for f in failed_files:
                            print_warning(f"  - {f}")

                # Check if review actually processed files
                files_reviewed = result.get("files_reviewed", 0)
                if files_reviewed == 0 and files:
                    print_error("\nNo files were successfully reviewed")
                    print_cyan("This may indicate:")
                    print_cyan("  1. API authentication failure (check your API key)")
                    print_cyan("  2. Network connectivity issues")
                    print_cyan("  3. Configuration errors")
                    print_cyan("\nCheck the logs in tomato/logs/ for more details.")
                    sys.exit(1)

            print(f"\n{CBLU}{'=' * 80}{CEND}")
            print_green("Review completed!")
            print(f"{CBLU}{'=' * 80}{CEND}")
            print()

            # Track modified files for cleanup
            if result.get("fixed_files"):
                _cleanup_state["modified_files"].update(result["fixed_files"])
            elif not args.no_fix and result.get("files_reviewed"):
                # If fixes were applied, track all reviewed files as potentially modified
                _cleanup_state["modified_files"].update(files)

            # Print summary
            if result.get("report_files"):
                print_cyan("Review reports saved to: tomato/reviews/")
                print_cyan(f"  ({len(result['report_files'])} report(s) generated)")

            if result.get("fixed_files") and not args.no_fix:
                print_green(f"\nModified {len(result['fixed_files'])} file(s) in place")
                print_cyan("Original files backed up to: tomato/backup/")

            if result.get("files_reviewed"):
                print_cyan(f"\nTotal files reviewed: {result['files_reviewed']}")

            print_cyan("\nLogs saved to: tomato/logs/")
            print()

            # Print combined report
            if result.get("output"):
                print(result["output"])

        except KeyboardInterrupt:
            # Signal handler will take care of cleanup
            raise

        except Exception as e:
            error_msg = str(e).lower()
            print_error(f"\nError during review: {e}")

            # Provide helpful messages for common errors
            if (
                "api" in error_msg
                or "key" in error_msg
                or "auth" in error_msg
                or "unauthorized" in error_msg
                or "401" in error_msg
                or "403" in error_msg
            ):
                print_cyan("\nThis appears to be an API authentication error.")
                print_cyan("Please check:")
                print_cyan("  1. Your API key is correct and valid")
                print_cyan("  2. Your API base URL is correct")
                print_cyan("  3. Your API key has the necessary permissions")
                print_cyan("  4. Your embedding API key (if different) is also valid")
            elif (
                "connection" in error_msg or "timeout" in error_msg or "network" in error_msg or "refused" in error_msg
            ):
                print_cyan("\nThis appears to be a connection error.")
                print_cyan("Please check:")
                print_cyan("  1. Your network connection")
                print_cyan("  2. The API base URL is reachable")
                print_cyan("  3. There are no firewall restrictions")
            elif "embedding" in error_msg or "milvus" in error_msg:
                print_cyan("\nThis appears to be a knowledge base or embedding error.")
                print_cyan("Please check:")
                print_cyan("  1. Your embedding API configuration")
                print_cyan("  2. Milvus connection settings")

            print_cyan("\nCheck the logs in tomato/logs/ for more details.")
            import traceback

            traceback.print_exc()
            sys.exit(1)


def cli_entry():
    """Entry point for the CLI command."""
    asyncio.run(main())


if __name__ == "__main__":
    cli_entry()
