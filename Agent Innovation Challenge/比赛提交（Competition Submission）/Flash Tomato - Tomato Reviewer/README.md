# TomatoReviewer

**TomatoReviewer** is an intelligent Python code review tool that combines static analysis with LLM-powered reasoning to provide comprehensive code reviews and automatic fixes based on Python Enhancement Proposals (PEPs).

- [English Version](README.md)
- [中文版](README.zh.md)

## Overview

TomatoReviewer uses a multi-agent architecture powered by Large Language Models (LLMs) to review Python code, identify issues, and automatically apply fixes. Unlike traditional linters, it leverages a PEP knowledge base built on [openjiuwen's knowledge base framework](https://gitcode.com/openJiuwen/agent-core) to provide context-aware recommendations that align with Python best practices.

This project serves as a reference implementation, demonstrating how to build an automatically updatable and maintainable knowledge base system. By integrating the openjiuwen knowledge base framework, we have implemented automated indexing, retrieval, and application of Python PEP documents, providing developers with a complete knowledge base application example. We hope this project can serve as a catalyst, inspiring more developers to build their own knowledge base applications based on the openjiuwen knowledge base framework, exploring more possibilities for knowledge bases in scenarios such as code review, document retrieval, and intelligent Q&A, and promoting the wider adoption of knowledge base technology in software development toolchains.

## Key Features

- **LLM-Powered Review**: Uses ReActAgent framework for intelligent code analysis and reasoning
- **PEP-Aware**: Searches and references relevant PEP guidelines for each issue
- **Automatic Fixing**: Iteratively applies fixes based on reviewer recommendations
- **Comprehensive Reports**: Generates detailed markdown reports with PEP references
- **Safe Operation**: Creates backups before modifying files
- **Code Testing**: Verifies fixes by running code to ensure functionality is preserved

## Built With

TomatoReviewer is built on top of:

- **[openjiuwen](https://gitcode.com/openJiuwen/agent-core)**: Agent framework and knowledge base system. The PEP knowledge base feature leverages openjiuwen's knowledge base framework for vector storage, embeddings, and hybrid search capabilities.
- **pylint**: Static code analysis
- **ruff**: Fast Python linter and formatter

## How It Works

TomatoReviewer employs three specialized agents:

1. **ReviewerAgent**: Analyzes code using pylint, searches PEP knowledge base for relevant guidelines, and generates comprehensive review reports with proposed fixes
2. **SearcherAgent**: Searches the PEP knowledge base (powered by openjiuwen's knowledge base framework) to find relevant coding conventions and best practices
3. **FixerAgent**: Applies fixes using LLM reasoning, incorporating reviewer instructions and PEP context, and tests fixes to ensure code still works

The tool follows an iterative review-fix cycle: it reviews files, applies fixes, reviews again, and repeats until issues are resolved or the maximum iteration limit is reached.

The PEP knowledge base is built using [openjiuwen's knowledge base framework](https://gitcode.com/openJiuwen/agent-core), which provides vector storage, embedding models, and hybrid search capabilities for efficient retrieval of relevant PEP guidelines.

## Installation

With `pip`:
```bash
pip install git+https://gitcode.com/SushiNinja/TomatoReviewer.git@main
```

Same with `uv`:
```bash
uv pip install git+https://gitcode.com/SushiNinja/TomatoReviewer.git@main
```

## Usage

```bash
# Review all Python files in current directory
tomato-review *.py

# Review specific files
tomato-review file1.py file2.py

# Review all Python files in src/ recursively
tomato-review src/**/*.py

# Review without applying fixes
tomato-review *.py --no-fix

# Review with custom maximum iterations
tomato-review *.py --max-iter 5

# Review with custom mini batch size
tomato-review *.py --mini-batch 10

# Build Knowledge Base from scratch
tomato-review --build

# Use custom config file
tomato-review *.py --config-file /path/to/config.yaml
```

### Command-line Options

- `-h, --help`: Show help message and exit
- `-m MAX_ITER, --max-iter MAX_ITER`: Maximum iterations of file fixing (default: 10)
- `-b MINI_BATCH, --mini-batch MINI_BATCH`: Mini batch size for files to process at the same time (default: 20)
- `--no-fix`: Only review files without applying fixes
- `--build`: Builds Knowledge Base from scratch
- `--config-file CONFIG_FILE`: Path to config file (tomato.yaml, .tomato.yaml, or pyproject.toml)

## Configuration

Create a `.tomato.yaml`, `tomato.yaml`, or add configuration to `pyproject.toml` in your project root. The following is an example configuration - adjust the values to match your setup:

```yaml
tomato-review:
  kb_id: "edinburgh"
  milvus_uri: "http://your-milvus-host:19530"  # Update with your Milvus server URI
  milvus_token: ""  # Add your Milvus token if required
  database_name: "pep_kb"
  embedding_model_name: "your-embedding-model"  # Update with your embedding model name
  embedding_api_key: "sk-********************"  # Update with your API key
  embedding_base_url: "http://your-embedding-server/v1/embeddings"  # Update with your embedding API URL
  chunk_size: 512
  chunk_overlap: 128
  index_type: "hybrid"
  api_base: "http://your-api-server/v1/"  # Update with your LLM API server URL
  api_key: "sk-********************"  # Update with your LLM API key
  model_name: "your-model-name"  # Update with your LLM model name
  model_provider: "OpenAI"
  verify_ssl: false
  ssl_cert: null
```

## Output

- **Reviews**: `tomato/reviews/` - Markdown review reports
- **Backups**: `tomato/backup/` - Original files before modification
- **Logs**: `tomato/logs/` - Processing logs for each file

Files are modified in place after review and fixing (unless `--no-fix` is used).

## Acknowledgments

Special thanks to the [openjiuwen](https://gitcode.com/openJiuwen/agent-core) project for providing the knowledge base framework that powers TomatoReviewer's PEP search capabilities.
