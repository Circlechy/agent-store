"""Utility functions for agent modules."""

import logging
import os
import re
import shutil
from pathlib import Path
from typing import Dict, List, Optional

from openjiuwen.core.single_agent import ReActAgentConfig


def parse_pylint_output(output: str) -> List[Dict[str, str]]:
    """Parse pylint output into structured error list.

    Args:
        output: pylint stdout text

    Returns:
        List of error dicts with 'file', 'line', 'column', 'type', 'code', 'message', 'symbol'

    Example:
        Input: "test.py:4:0: C0103: Constant name doesn't conform (invalid-name)"
        Output: [{
            "file": "test.py",
            "line": 4,
            "column": 0,
            "type": "C",
            "code": "C0103",
            "message": "Constant name doesn't conform",
            "symbol": "invalid-name"
        }]
    """
    errors = []

    # Pattern: file:line:column: code: message (symbol)
    # Example: test_code_base/bad_naming.py:4:0: C0103: Constant name "myVariable" doesn't conform to UPPER_CASE naming style (invalid-name)
    pattern = r"^(.+?):(\d+):(\d+):\s+([A-Z]\d+):\s+(.+?)\s+\(([A-Za-z0-9_\-]+?)\)$"

    for line in output.splitlines():
        # Skip module header lines and rating lines
        if line.startswith("*************") or line.startswith("---") or "rated at" in line.lower():
            continue

        # Skip empty lines
        if not line.strip():
            continue

        match = re.match(pattern, line, flags=re.UNICODE)
        if match:
            file_path_match, line_num, col_num, code, message, symbol = match.groups()
            # Extract error type from code (first letter: C, R, W, E, F)
            error_type = code[0] if code else "U"

            errors.append(
                {
                    "file": file_path_match,
                    "line": int(line_num),
                    "column": int(col_num),
                    "type": error_type,
                    "code": code,
                    "message": message,
                    "symbol": symbol,
                }
            )

    return errors


def normalize_filename(file_path: str) -> str:
    """Normalize a file path to a safe filename using only word characters.

    Args:
        file_path: Original file path

    Returns:
        Normalized filename with only word characters (a-z, A-Z, 0-9, _)
    """
    # Get the base name without extension
    path = Path(file_path)
    base_name = path.stem
    extension = path.suffix

    # Replace non-word characters with underscores
    normalized = re.sub(r"[^\w]", "_", base_name)

    # Remove consecutive underscores
    normalized = re.sub(r"_+", "_", normalized)

    # Remove leading/trailing underscores
    normalized = normalized.strip("_")

    # If empty after normalization, use a default name
    if not normalized:
        normalized = "file"

    return normalized + extension


def setup_tomato_directories(base_path: Optional[Path] = None) -> Dict[str, Path]:
    """Create tomato directory structure for backups, reviews, and logs.

    Args:
        base_path: Base path for tomato directory (default: current working directory)

    Returns:
        Dict with 'backup', 'reviews', 'logs' paths
    """
    if base_path is None:
        base_path = Path.cwd()

    tomato_dir = base_path / "tomato"
    backup_dir = tomato_dir / "backup"
    reviews_dir = tomato_dir / "reviews"
    logs_dir = base_path / "logs" / "tomato"

    if tomato_dir.exists():
        shutil.rmtree(tomato_dir)

    # Create directories
    backup_dir.mkdir(parents=True, exist_ok=True)
    reviews_dir.mkdir(parents=True, exist_ok=True)
    logs_dir.mkdir(parents=True, exist_ok=True)

    return {
        "backup": backup_dir,
        "reviews": reviews_dir,
        "logs": logs_dir,
    }


def backup_file(file_path: str, backup_base: Path) -> Path:
    """Backup a file preserving folder structure.

    Args:
        file_path: Path to the file to backup
        backup_base: Base directory for backups

    Returns:
        Path to the backed up file
    """
    source_path = Path(file_path).resolve()

    # Get relative path from current working directory or project root
    try:
        # Try to get relative path from cwd
        rel_path = source_path.relative_to(Path.cwd())
    except ValueError:
        # If not relative to cwd, use just the filename
        rel_path = source_path.name

    # Create backup path preserving structure
    backup_path = backup_base / rel_path
    backup_path.parent.mkdir(parents=True, exist_ok=True)

    # Copy file to backup location
    shutil.copy2(source_path, backup_path)

    return backup_path


def setup_file_logger(log_file_path: Path, logger_name: str = "tomato_review") -> logging.Logger:
    """Set up a file logger that writes to a file instead of stdout.

    Args:
        log_file_path: Path to the log file
        logger_name: Name for the logger

    Returns:
        Configured logger instance
    """
    logger = logging.getLogger(logger_name)
    logger.setLevel(logging.INFO)

    # Remove existing handlers to avoid duplicates
    logger.handlers.clear()

    # Create file handler
    log_file_path.parent.mkdir(parents=True, exist_ok=True)
    file_handler = logging.FileHandler(log_file_path, encoding="utf-8")
    file_handler.setLevel(logging.INFO)

    # Create formatter
    formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s", datefmt="%Y-%m-%d %H:%M:%S")
    file_handler.setFormatter(formatter)

    logger.addHandler(file_handler)

    return logger


def get_env_var(var_name: str, required: bool = True) -> str:
    """Get environment variable, raising error if required and not found.

    Args:
        var_name: Environment variable name
        required: Whether the variable is required

    Returns:
        Environment variable value

    Raises:
        ValueError: If required variable is not set
    """
    value = os.getenv(var_name)
    if required and not value:
        raise ValueError(
            f"Required environment variable '{var_name}' is not set. "
            f"Please set it in your .env.agent file or environment."
        )
    return value or ""


def configure_from_env(config: ReActAgentConfig) -> None:
    """Configure ReActAgentConfig from environment variables.

    Args:
        config: ReActAgentConfig instance to configure

    Raises:
        ValueError: If required environment variables are not set
    """
    api_base = get_env_var("API_BASE", required=True)
    api_key = get_env_var("API_KEY", required=True)
    model_name = get_env_var("MODEL_NAME", required=True)
    model_provider = get_env_var("MODEL_PROVIDER", required=True)
    verify_ssl = get_env_var("VERIFY_SSL", required=False)
    ssl_cert = get_env_var("SSL_CERT", required=False)

    config.configure_model_client(
        provider=model_provider,
        api_key=api_key,
        api_base=api_base,
        model_name=model_name,
        verify_ssl=verify_ssl == "true",
    )
    if ssl_cert == "true":
        config.model_client_config.ssl_cert = ssl_cert


def extract_reasoning_content(content: str, reasoning_pattern: str = r"<think>(.*)</think>") -> tuple[str, str]:
    """Extract reasoning content from LLM response"""
    reasoning = re.match(reasoning_pattern, content, flags=re.DOTALL)
    if reasoning:
        return content[reasoning.end() :].strip(), reasoning.group(1)
    return content.strip(), ""
