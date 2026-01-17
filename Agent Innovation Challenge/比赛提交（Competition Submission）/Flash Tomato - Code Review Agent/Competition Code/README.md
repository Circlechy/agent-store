# Tomato Review

Python code review agent using pylint and PEP knowledge base.

## Installation

```bash
# Install from the project directory
pip install -e .

# Or install using setup.py
pip install -e . -f setup_tomato.py
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

Create a `.env.agent` file in your project root with the following variables:

```env
API_BASE=...
API_KEY=...
MODEL_NAME=...
MODEL_PROVIDER=...
PEP_KB_ID=...
MILVUS_URI=...
MILVUS_TOKEN=...
MILVUS_DATABASE=...
EMBEDDING_MODEL=...
EMBEDDING_API_KEY=...
EMBEDDING_BASE_URL=...
PEP_CHUNK_SIZE=...
PEP_CHUNK_OVERLAP=...
PEP_INDEX_TYPE=...
```

## Output

- **Reviews**: `tomato/reviews/` - Markdown review reports
- **Backups**: `tomato/backup/` - Original files before modification
- **Logs**: `tomato/logs/` - Processing logs for each file

Files are modified in place after review and fixing.
