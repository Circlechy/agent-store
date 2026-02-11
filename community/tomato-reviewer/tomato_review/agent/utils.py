"""
Utility functions for agent modules.
"""

import logging
import os
import re
import shutil
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional

from openjiuwen import __version__ as openjiuwen_version
from openjiuwen.core.single_agent import ReActAgentConfig

from tomato_review import DEBUG_MODE

try:
    from openjiuwen.core.common.schema.param import Param
except ImportError:
    Param = None


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
    if logs_dir.exists():
        shutil.rmtree(logs_dir)

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


def configure_from_env(config: ReActAgentConfig, role: Literal["review", "search", "fix"] = "review") -> None:
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
    max_iter = get_env_var("REACT_MAX_ITER_" + role.upper(), required=True)

    config.configure_model_client(
        provider=model_provider,
        api_key=api_key,
        api_base=api_base,
        model_name=model_name,
        verify_ssl=verify_ssl == "true",
    )
    if ssl_cert == "true":
        config.model_client_config.ssl_cert = ssl_cert
    if max_iter:
        config.max_iterations = int(max_iter)


def extract_reasoning_content(content: str, reasoning_pattern: str = r"<think>(.*)</think>") -> tuple[str, str]:
    """Extract reasoning content from LLM response"""
    reasoning = re.match(reasoning_pattern, content, flags=re.DOTALL)
    if reasoning:
        return content[reasoning.end() :].strip(), reasoning.group(1)
    return content.strip(), ""


def get_pylint_config_path() -> Optional[str]:
    """Determine the pylint configuration file path for --rcfile option.

    Checks for pylint configuration files in the following order:
    1. .pylintrc in current working directory
    2. pyproject.toml in current working directory (if it contains [tool.pylint] section)
       Note: pylint auto-detects pyproject.toml, so we return None to let it auto-detect
    3. Falls back to the default pylintrc in tomato_review package

    Returns:
        Path to pylint config file as string for --rcfile option, or None if pylint should auto-detect
    """
    cwd = Path.cwd()

    # Check for pylintrc or .pylintrc in cwd
    for filename in ["pylintrc", ".pylintrc", "pyproject"]:
        pylintrc_path = cwd / filename
        if pylintrc_path.exists() and pylintrc_path.is_file():
            return

        # Check for pyproject.toml in cwd with pylint config
        toml_path = cwd / f"{filename}.toml"
        if toml_path.exists() and toml_path.is_file():
            try:
                # Check if pyproject.toml contains [tool.pylint] section
                content = toml_path.read_text(encoding="utf-8")
                if "[tool.pylint]" in content or '["tool.pylint"]' in content:
                    return
            except Exception:
                # If we can't read the file, continue to fallback
                pass

    # Fallback to default pylintrc in tomato_review package
    from tomato_review import PYLINT_FALLBACK

    if PYLINT_FALLBACK.exists():
        return str(PYLINT_FALLBACK)


def parse_mypy_output(output: str) -> List[Dict[str, str]]:
    """Parse mypy output into structured error list.

    Args:
        output: mypy stdout text

    Returns:
        List of error dicts with 'file', 'line', 'column', 'type', 'code', 'message', 'symbol'

    Example:
        Input: "test.py:4: error: Incompatible return type \"str\" (got \"int\")  [return-value]"
        Output: [{
            "file": "test.py",
            "line": 4,
            "column": 0,
            "type": "error",
            "code": "return-value",
            "message": "Incompatible return type \"str\" (got \"int\")",
            "symbol": "return-value"
        }]
    """
    errors = []

    # Pattern: file:line:column: type: message [code]
    # Example: test.py:4: error: Incompatible return type "str" (got "int")  [return-value]
    pattern = r"^(.+?):(\d+):(?:\d+:)?\s+(error|note|warning):\s+(.+?)(?:\s+\[([A-Za-z0-9_\-]+)\])?$"

    for line in output.splitlines():
        # Skip empty lines and summary lines
        match = re.match(pattern, line)
        if match:
            file_path_match, line_num, col_num, error_type, message, code = match.groups()
            errors.append(
                {
                    "file": file_path_match,
                    "line": int(line_num),
                    "column": int(col_num) if col_num else 0,
                    "type": error_type,
                    "code": code or "",
                    "message": message.strip(),
                    "symbol": code or "",
                }
            )
    if DEBUG_MODE:
        print(f"mypy {errors=} {output=}")
    return errors


def get_mypy_config_path() -> Optional[str]:
    """Determine the mypy configuration file path for --config-file option.

    Checks for mypy configuration files in the following order:
    1. .mypy.ini or mypy.ini in current working directory
    2. pyproject.toml in current working directory (if it contains [tool.mypy] section)
       Note: mypy auto-detects pyproject.toml, so we return None to let it auto-detect
    3. Falls back to the default .mypy.ini in tomato_review package

    Returns:
        Path to mypy config file as string for --config-file option, or None if mypy should auto-detect
    """
    cwd = Path.cwd()

    # Check for mypy.ini or .mypy.ini in cwd
    for filename in ["mypy.ini", ".mypy.ini"]:
        mypy_ini_path = cwd / filename
        if mypy_ini_path.exists() and mypy_ini_path.is_file():
            return

    # Check for pyproject.toml in cwd with mypy config
    pyproject_path = cwd / "pyproject.toml"
    if pyproject_path.exists() and pyproject_path.is_file():
        try:
            # Check if pyproject.toml contains [tool.mypy] section
            content = pyproject_path.read_text(encoding="utf-8")
            if "[tool.mypy]" in content or '["tool.mypy"]' in content:
                return
        except Exception:
            # If we can't read the file, continue to fallback
            pass

    # Fallback to default .mypy.ini in tomato_review package
    from tomato_review import MYPY_FALLBACK

    if MYPY_FALLBACK.exists():
        return str(MYPY_FALLBACK)


def compare_version(version_str: str, target: str) -> bool:
    """Compare version strings using zip for robust comparison.

    Compares version strings element by element, stopping when one iterator
    reaches the end. This handles cases where versions have different numbers
    of parts (e.g., "0.1" vs "0.1.5").

    Args:
        version_str: Version string to compare (e.g., "0.1.5")
        target: Target version string (e.g., "0.1.5")

    Returns:
        True if version_str >= target, False otherwise
    """
    try:

        def version_parts(v: str) -> List[int]:
            """Parse version string into list of integers."""
            return [int(part) for part in v.split(".")]

        v_parts = version_parts(version_str)
        t_parts = version_parts(target)

        # Compare common parts using zip (stops when one iterator ends)
        for v_part, t_part in zip(v_parts, t_parts):
            if v_part > t_part:
                return True
            if v_part < t_part:
                return False
            # If equal, continue to next part

        # If all common parts are equal, longer version is considered greater
        # (e.g., "0.1.5" >= "0.1" is True)
        return len(v_parts) >= len(t_parts)

    except (ValueError, AttributeError):
        # If version parsing fails, default to using Param format (older behavior)
        return False


def _convert_schema_to_params(schema: Dict[str, Any]) -> List[Param]:
    """Convert JSON schema dict to list of Param objects using Param shorthand methods.

    Args:
        schema: JSON schema dict with 'properties' and 'required' fields

    Returns:
        List of Param objects

    Raises:
        ImportError: If Param class is not available
    """
    if Param is None:
        raise ImportError("Param class not available from openjiuwen.core.common.schema.param")

    params = []
    properties = schema.get("properties", {})
    required = set(schema.get("required", []))

    for param_name, param_schema in properties.items():
        is_required = param_name in required

        # Convert nested schema to Param recursively
        param = _convert_single_param(param_name, param_schema, is_required)
        params.append(param)

    return params


def _convert_single_param(name: str, schema: Dict[str, Any], required: bool) -> Param:
    """Convert a single parameter schema to Param object using shorthand methods.

    Args:
        name: Parameter name
        schema: Parameter schema dict
        required: Whether the parameter is required

    Returns:
        Param object
    """
    if Param is None:
        raise ImportError("Param class not available from openjiuwen.core.common.schema.param")

    param_type = schema.get("type", "string")
    description = schema.get("description", "")

    # Get the Param shorthand method using getattr
    # Map JSON schema types to Param methods
    type_mapping = {
        "string": "string",
        "integer": "integer",
        "number": "number",
        "boolean": "boolean",
        "array": "array",
        "object": "object",
    }

    param_method_name = type_mapping.get(param_type, "string")
    param_method = getattr(Param, param_method_name, None)

    if param_method is None:
        # Fallback to string if method doesn't exist
        param_method = getattr(Param, "string")

    # Build base kwargs
    kwargs = {
        "name": name,
        "description": description,
        "required": required,
    }

    # Handle array type - need to convert items
    if param_type == "array" and "items" in schema:
        items_schema = schema["items"]
        if isinstance(items_schema, dict):
            # Recursively convert items schema
            # Items in arrays don't have 'name' in JSON schema, use default
            # For objects, use a descriptive name based on the array param name or "item"
            items_name = items_schema.get("name", "item")
            # Items in arrays are typically not required (the array itself can be required)
            items_required = items_schema.get("required", False)
            if isinstance(items_required, list):
                # If required is a list (for objects), check if items_name is in it
                items_required = items_name in items_required
            items_param = _convert_single_param(items_name, items_schema, items_required)
            kwargs["items"] = items_param
        else:
            # If items is not a dict, treat as simple type string
            items_type = str(items_schema)
            items_method_name = type_mapping.get(items_type, "string")
            items_method = getattr(Param, items_method_name, Param.string)
            kwargs["items"] = items_method(name="item", description="", required=False)

    # Handle object type - need to convert properties
    elif param_type == "object" and "properties" in schema:
        object_properties = schema.get("properties", {})
        object_required = set(schema.get("required", []))
        properties_list = []
        for prop_name, prop_schema in object_properties.items():
            prop_required = prop_name in object_required
            prop_param = _convert_single_param(prop_name, prop_schema, prop_required)
            properties_list.append(prop_param)
        kwargs["properties"] = properties_list

    # Create Param using the shorthand method
    return param_method(**kwargs)


def get_input_params(schema: Dict[str, Any]) -> Any:
    """Get input_params based on openjiuwen version.

    Args:
        schema: JSON schema dict

    Returns:
        Either the schema dict (if version >= 0.1.5) or list[Param] (if version < 0.1.5)
    """
    if compare_version(openjiuwen_version, "0.1.5"):
        return schema
    return _convert_schema_to_params(schema)
