# Tomato Review

Python code review agent using pylint and PEP knowledge base.

## Installation

```bash
pip install .
```

## Usage

```bash
# Review all Python files in current directory
tomato-review *.py

# Review specific files
tomato-review file1.py file2.py

# Review without applying fixes
tomato-review *.py --no-fix

# Review with custom environment file
tomato-review *.py --env-file /path/to/.env.agent
```

## Configuration

Create a `.tomato.yaml` or `tomato.yaml` file in your project root with the following variables:
```yaml
tomato-review:
  kb_id: "edinburgh"
  milvus_uri: "http://localhost:19530"
  milvus_token: ""
  database_name: "pep_kb"
  embedding_model_name: "qwen3-embedding-8b"
  embedding_api_key: "sk-********************"
  embedding_base_url: "http://localhost:11450/v1/embeddings"
  chunk_size: 512
  chunk_overlap: 128
  index_type: "hybrid"
  api_base: "http://localhost:11451/v1/"
  api_key: "sk-********************"
  model_name: "qwen3-8b"
  model_provider: "OpenAI"
  verify_ssl: false
  ssl_cert: null
```

## Output

- **Reviews**: `tomato/reviews/` - Markdown review reports
- **Backups**: `tomato/backup/` - Original files before modification
- **Logs**: `tomato/logs/` - Processing logs for each file

Files are modified in place after review and fixing.
