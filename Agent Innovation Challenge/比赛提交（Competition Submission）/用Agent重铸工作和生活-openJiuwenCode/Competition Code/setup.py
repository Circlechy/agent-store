"""
openjiuwen-code setup.py
"""

from setuptools import setup, find_packages
import os

# 读取 README
def read_readme():
    readme_path = os.path.join(os.path.dirname(__file__), 'README.md')
    if os.path.exists(readme_path):
        with open(readme_path, 'r', encoding='utf-8') as f:
            return f.read()
    return ''

setup(
    name="openjiuwen-code",
    version="0.2.0",
    description="AI 编程助手 - 基于 openJiuwen SDK",
    long_description=read_readme(),
    long_description_content_type="text/markdown",
    author="SnapeK",
    url="https://gitcode.com/SnapeK/openjiuwen-code",
    packages=find_packages(exclude=['tests', 'tests.*', 'agent-core', 'python11venv', '*.venv']),
    include_package_data=True,
    install_requires=[
        "rich>=13.7.0",
        "prompt-toolkit>=3.0.0",
        "aiohttp>=3.9.0",
        "aiofiles>=23.2.0",
        "pyyaml>=6.0",
        "anthropic>=0.18.0",
        "openai>=1.12.0",
    ],
    extras_require={
        "dev": [
            "pytest>=7.4.0",
            "pytest-asyncio>=0.21.0",
            "black>=23.12.0",
            "mypy>=1.8.0",
            "flake8>=6.1.0",
        ],
    },
    entry_points={
        "console_scripts": [
            "jiuwen=packages.cli.main:main",
        ],
    },
    python_requires=">=3.10",
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
    ],
)
