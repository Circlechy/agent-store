#!/usr/bin/env python
"""Update requirements.txt and version.txt"""

from pathlib import Path

version_file = Path(__file__).parent.parent / "tomato_review" / "version.txt"
requirement = Path(__file__).parent.parent / "requirements.txt"
pyproject_file = Path(__file__).parent.parent / "pyproject.toml"
PACKAGE_DATA: dict[str, list] = {}
CLASSIFIERS: list[str] = []
VERSION: str = "0.0.0"

try:
    import tomllib

    # Fetch up-to-date data from pyproject.toml
    pyproject_content = tomllib.loads(pyproject_file.read_text())
    VERSION = pyproject_content["project"]["version"]

    # Update dependencies from pyproject.toml to requirements.txt and tomato_reviw/version.txt
    dependencies = pyproject_content["project"]["dependencies"]
    requirements_content = [f"# Auto-generated for tomato-review {VERSION}, based on pyproject.toml"] + dependencies
    requirement.write_text("\n".join(requirements_content))
    version_file.write_text(VERSION)
except ImportError as e:
    raise RuntimeError("Python 3.11+ (which ships with tomllib) is required") from e
