"""Configuration loading utilities for tomato-review."""

import os
import tomllib
from pathlib import Path
from typing import Any, Dict, Optional

try:
    import yaml
except ImportError:
    yaml = None


def load_config() -> Dict[str, Any]:
    """Load configuration from tomato.yaml, .tomato.yaml, or pyproject.toml.

    Priority order:
    1. tomato.yaml (in current directory)
    2. .tomato.yaml (in current directory)
    3. pyproject.toml (in current directory, look for [tool.tomato-review] section)
    4. Check parent directory for same files

    Returns:
        Dict with configuration values
    """
    config = {}

    # Search paths
    search_paths = [
        Path.cwd(),
        Path.cwd().parent,
    ]

    # File names to check (in priority order)
    config_files = [
        ("tomato.yaml", _load_yaml),
        (".tomato.yaml", _load_yaml),
        ("pyproject.toml", _load_pyproject),
    ]

    for search_path in search_paths:
        for filename, loader in config_files:
            config_path = search_path / filename
            if config_path.exists():
                try:
                    loaded = loader(config_path)
                    if loaded:
                        config.update(loaded)
                        # Return first found config
                        return config
                except Exception:
                    # Continue to next file if this one fails
                    continue

    return config


def _load_yaml(config_path: Path) -> Optional[Dict[str, Any]]:
    """Load YAML configuration file."""
    if yaml is None:
        return None

    with open(config_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    if not isinstance(data, dict):
        return None

    # Extract tomato-review section if present, otherwise use root
    return data.get("tomato-review", data)


def _load_pyproject(config_path: Path) -> Optional[Dict[str, Any]]:
    """Load pyproject.toml and extract [tool.tomato-review] section."""
    with open(config_path, "rb") as f:
        data = tomllib.load(f)

    # Look for [tool.tomato-review] section
    tool_section = data.get("tool", {})
    return tool_section.get("tomato-review")


def get_kb_config(config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Extract knowledge base configuration from config dict.

    Args:
        config: Configuration dict (if None, will load from files)

    Returns:
        Dict with KB configuration keys
    """
    if config is None:
        config = load_config()

    # Map config keys to environment variable names
    kb_config = {}

    # Knowledge base settings
    kb_config["kb_id"] = config.get("kb_id") or os.getenv("PEP_KB_ID")
    kb_config["milvus_uri"] = config.get("milvus_uri") or os.getenv("MILVUS_URI")
    kb_config["milvus_token"] = config.get("milvus_token") or os.getenv("MILVUS_TOKEN", "")
    kb_config["database_name"] = config.get("database_name") or os.getenv("MILVUS_DATABASE")
    kb_config["embedding_model_name"] = config.get("embedding_model_name") or os.getenv("EMBEDDING_MODEL")
    kb_config["embedding_api_key"] = config.get("embedding_api_key") or os.getenv("EMBEDDING_API_KEY")
    kb_config["embedding_base_url"] = config.get("embedding_base_url") or os.getenv("EMBEDDING_BASE_URL")
    kb_config["chunk_size"] = int(config.get("chunk_size") or os.getenv("PEP_CHUNK_SIZE", "512"))
    kb_config["chunk_overlap"] = int(config.get("chunk_overlap") or os.getenv("PEP_CHUNK_OVERLAP", "128"))
    kb_config["index_type"] = config.get("index_type") or os.getenv("PEP_INDEX_TYPE", "hybrid")

    return kb_config


def get_llm_config(config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Extract LLM configuration from config dict.

    Args:
        config: Configuration dict (if None, will load from files)

    Returns:
        Dict with LLM configuration keys
    """
    if config is None:
        config = load_config()

    llm_config = {}

    # LLM settings
    llm_config["api_base"] = config.get("api_base") or os.getenv("API_BASE")
    llm_config["api_key"] = config.get("api_key") or os.getenv("API_KEY")
    llm_config["model_name"] = config.get("model_name") or os.getenv("MODEL_NAME")
    llm_config["model_provider"] = config.get("model_provider") or os.getenv("MODEL_PROVIDER")
    llm_config["verify_ssl"] = config.get("verify_ssl") or (os.getenv("VERIFY_SSL") == "true")
    if "ssl_cert" in config:
        llm_config["ssl_cert"] = config.get("ssl_cert")
    else:
        llm_config["ssl_cert"] = os.getenv("SSL_CERT")

    return llm_config
