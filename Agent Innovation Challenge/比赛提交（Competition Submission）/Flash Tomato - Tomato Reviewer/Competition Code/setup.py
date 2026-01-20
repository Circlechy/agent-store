"""Setup script for tomato-review package."""

from pathlib import Path

from setuptools import find_packages, setup

# Read README if it exists
readme_file = Path(__file__).parent / "README.md"
version_file = Path(__file__).parent / "tomato_review" / "version.txt"
requirement = Path(__file__).parent / "requirements.txt"
pyproject_file = Path(__file__).parent / "pyproject.toml"
PACKAGE_DATA: dict[str, list] = {}
CLASSIFIERS: list[str] = []
AUTHORS: str = "Flash Tomato Team"
VERSION: str = "0.0.0"

try:
    import tomllib

    # Fetch up-to-date data from pyproject.toml
    pyproject_content = tomllib.loads(pyproject_file.read_text())
    PACKAGE_DATA = pyproject_content["tool"]["setuptools"]["package-data"]
    CLASSIFIERS = pyproject_content["project"]["classifiers"]
    AUTHORS = ", ".join(a["name"] for a in pyproject_content["project"]["authors"])
    VERSION = pyproject_content["project"]["version"]

    # Update dependencies from pyproject.toml to requirements.txt and tomato_reviw/version.txt
    dependencies = pyproject_content["project"]["dependencies"]
    requirements_content = ["# Auto-generated via setup.py, based on pyproject.toml"] + dependencies
    requirement.write_text("\n".join(requirements_content))
    version_file.write_text(VERSION)
except ImportError as e:
    raise RuntimeError("Python 3.11+ (which ships with tomllib) is required") from e

setup(
    name="tomato-review",
    version=VERSION,
    description="Python code review agent using pylint and PEP knowledge base",
    long_description=readme_file.read_text(encoding="utf-8"),
    long_description_content_type="text/markdown",
    author=AUTHORS,
    python_requires=">=3.11",
    packages=find_packages(include=["tomato_review", "tomato_review.*"]),
    install_requires=dependencies,
    entry_points={
        "console_scripts": [
            "tomato-review=tomato_review.cli:cli_entry",
        ],
    },
    include_package_data=False,
    package_data=PACKAGE_DATA,
    classifiers=CLASSIFIERS,
)
