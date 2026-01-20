# DeepMemory MCP Server API Documentation

## Overview

DeepMemory MCP Server is a Model Context Protocol (MCP) server that provides tools for processing and managing memory files organized by date. The server organizes memory files in a hierarchical date-based structure and provides comprehensive tools for writing, reading, searching, and managing these files.

**Server Name:** `DeepMemoryMcp`  
**Version:** `0.1.0`

## File System Structure

Memory files are organized by date in the following structure:

```
./memory_dir/
├── summary_year_YYYY.txt          # Year summaries at root level
├── YYYY-M/                        # Month directories
│   ├── summary_month_YYYYMM.txt   # Month summaries
│   ├── YYYY-M-D/                  # Date directories (nested under month)
│   │   ├── conversation_YYYYMMDD_HHMMSS.txt
│   │   └── summary_day_YYYYMMDD.txt
│   └── YYYY-M-D/                  # More date directories
│       └── ...
└── ...
```

- **Month directories:** Format `YYYY-M` (e.g., `2025-1`, `2025-3`) - contain month summaries and date subdirectories
- **Date directories:** Format `YYYY-M-D` (e.g., `2025-1-15`, `2025-3-20`) - nested under month directories, contain conversations and day summaries
- **Conversation files:** Timestamped files with format `conversation_YYYYMMDD_HHMMSS.txt`
- **Summary files:** Organized by day (in date directories), month (in month directories), or year (at root level)

## Tools

The server provides 9 tools organized into three categories:

### 1. Memory Writer Tools

Tools for writing and modifying memory files.

#### 1.1 `write_raw_conversation`

Write raw conversation history into the memory file system. Generates a timestamped file and saves the conversation in the appropriate date directory.

**Parameters:**
- `conversation` (string, required): The conversation history to save
- `date` (string, optional): Date in ISO format (YYYY-MM-DD). If not provided, uses today's date.

**Example Request:**
```json
{
  "conversation": "User: Hello\nAssistant: Hi there! How can I help you?",
  "date": "2025-01-15"
}
```

**Example Response:**
```
Successfully saved conversation to 2025-1/2025-1-15/conversation_20250115_143022.txt
```

**File Created:**
- Path: `./memory_dir/2025-1/2025-1-15/conversation_20250115_143022.txt`
- Content: The raw conversation text

---

#### 1.2 `write_summarized_memory`

Write summarized memory. The memory will be summarized by day/month/year and saved in the corresponding directory.

**Parameters:**
- `summary` (string, required): The summarized memory content
- `date` (string, required): Date in ISO format (YYYY-MM-DD) for the summary
- `summary_type` (string, required): Type of summary. Must be one of: `"day"`, `"month"`, `"year"`

**Example Request:**
```json
{
  "summary": "Today we discussed project planning and set up the development environment.",
  "date": "2025-01-15",
  "summary_type": "day"
}
```

**Example Response:**
```
Successfully saved day summary to 2025-1-15/summary_day_20250115.txt
```

**File Created:**
- Day summary: `./memory_dir/2025-1/2025-1-15/summary_day_20250115.txt` (in date directory, nested under month)
- Month summary: `./memory_dir/2025-1/summary_month_202501.txt` (in month directory)
- Year summary: `./memory_dir/summary_year_2025.txt` (at root level)

**Note:** If a summary file already exists, new content will be appended with a separator.

---

#### 1.3 `modify_memory_file`

Modify an existing memory file. You can append or replace content.

**Parameters:**
- `file_path` (string, required): Relative path to the memory file (e.g., `'2025-1/2025-1-15/conversation_20250115_143022.txt'`)
- `new_content` (string, required): The new content to write or append
- `mode` (string, optional): Mode of operation. Must be one of: `"replace"`, `"append"`. Default: `"append"`

**Example Request (Append):**
```json
{
  "file_path": "2025-1/2025-1-15/conversation_20250115_143022.txt",
  "new_content": "Additional notes: Follow up on this topic tomorrow.",
  "mode": "append"
}
```

**Example Request (Replace):**
```json
{
  "file_path": "2025-1/2025-1-15/conversation_20250115_143022.txt",
  "new_content": "Updated conversation content",
  "mode": "replace"
}
```

**Example Response:**
```
Successfully appended to content to 2025-1/2025-1-15/conversation_20250115_143022.txt
```

**Note:** When appending, a timestamp is automatically added to the new content.

---

### 2. Memory Reader Tools

Tools for reading and searching memory files.

#### 2.1 `list_memory_files`

List all memory files in the memory file system. Returns a list of files with their dates and paths.

**Parameters:**
- `date_filter` (string, optional): Optional date filter in ISO format (YYYY-MM-DD) to list files from a specific date

**Example Request:**
```json
{
  "date_filter": "2025-01-15"
}
```

**Example Request (All Files):**
```json
{}
```

**Example Response:**
```
Memory Files:
==================================================
Date: 2025-01-15
Path: 2025-1/2025-1-15/conversation_20250115_143022.txt
Size: 1024 bytes
--------------------------------------------------
Date: 2025-01-15
Path: 2025-1/2025-1-15/summary_day_20250115.txt
Size: 512 bytes
--------------------------------------------------
```

---

#### 2.2 `read_memory_file`

Read the content of a specific memory file.

**Parameters:**
- `file_path` (string, required): Relative path to the memory file (e.g., `'2025-1/2025-1-15/conversation_20250115_143022.txt'`)

**Example Request:**
```json
{
  "file_path": "2025-1/2025-1-15/conversation_20250115_143022.txt"
}
```

**Example Response:**
```
File: 2025-1/2025-1-15/conversation_20250115_143022.txt

User: Hello
Assistant: Hi there! How can I help you?
```

**Error Response:**
```
Error: File 2025-1/2025-1-15/nonexistent.txt does not exist
```

---

#### 2.3 `search_memory_files`

Search for keywords across all memory files. Returns brief content excerpts and the source file paths.

**Parameters:**
- `keyword` (string, required): The keyword or phrase to search for
- `max_results` (integer, optional): Maximum number of results to return. Default: `10`

**Example Request:**
```json
{
  "keyword": "project planning",
  "max_results": 5
}
```

**Example Response:**
```
Search results for 'project planning':
==================================================

Result 1:
File: 2025-1/2025-1-15/conversation_20250115_143022.txt
Date: 2025-01-15T14:30:22
Brief content:
We discussed the project planning phase
and set up the development environment.
--------------------------------------------------
```

**Note:** The search is case-insensitive and returns a brief excerpt (3 lines) around the keyword match.

---

### 3. Memory Statistics Tools

Additional utility tools for managing and analyzing memory files.

#### 3.1 `get_memory_statistics`

Get statistics about the memory file system including total files, total size, date range, and files per date.

**Parameters:**
None

**Example Request:**
```json
{}
```

**Example Response:**
```
Memory Statistics:
==================================================
Total files: 25
Total size: 245,760 bytes (0.23 MB)
Date range: 2025-01-01 to 2025-01-15

Files per date:
  2025-01-01: 3 file(s)
  2025-01-02: 2 file(s)
  2025-01-15: 5 file(s)
```

---

#### 3.2 `delete_memory_file`

Delete a specific memory file from the memory file system.

**Parameters:**
- `file_path` (string, required): Relative path to the memory file to delete

**Example Request:**
```json
{
  "file_path": "2025-1/2025-1-15/conversation_20250115_143022.txt"
}
```

**Example Response:**
```
Successfully deleted file: 2025-1/2025-1-15/conversation_20250115_143022.txt
```

**Error Response:**
```
Error: File 2025-1/2025-1-15/nonexistent.txt does not exist
```

---

#### 3.3 `get_memory_by_date_range`

Get all memory files within a date range.

**Parameters:**
- `start_date` (string, required): Start date in ISO format (YYYY-MM-DD)
- `end_date` (string, required): End date in ISO format (YYYY-MM-DD)

**Example Request:**
```json
{
  "start_date": "2025-01-01",
  "end_date": "2025-01-07"
}
```

**Example Response:**
```
Memory files from 2025-01-01 to 2025-01-07:
==================================================
Date: 2025-01-01
Path: 2025-1/2025-1-1/conversation_20250101_120000.txt
Size: 2048 bytes
--------------------------------------------------
Date: 2025-01-02
Path: 2025-1/2025-1-2/conversation_20250102_130000.txt
Size: 1536 bytes
--------------------------------------------------
```

---

## Error Handling

All tools return error messages in a consistent format:

```
Error: <error description>
```

Common error scenarios:
- File not found: `Error: File <path> does not exist`
- Invalid date format: Handled by the MCP protocol validation
- Missing required parameters: Handled by the MCP protocol validation

## Response Format

All tools return responses in the MCP `TextContent` format:

```json
{
  "type": "text",
  "text": "<response content>"
}
```

## Usage Examples

### Example 1: Save a Conversation

```json
{
  "name": "write_raw_conversation",
  "arguments": {
    "conversation": "User: What is the weather today?\nAssistant: I don't have access to real-time weather data."
  }
}
```

### Example 2: Search for a Topic

```json
{
  "name": "search_memory_files",
  "arguments": {
    "keyword": "weather",
    "max_results": 10
  }
}
```

### Example 3: Get Weekly Summary

```json
{
  "name": "get_memory_by_date_range",
  "arguments": {
    "start_date": "2025-01-01",
    "end_date": "2025-01-07"
  }
}
```

### Example 4: Update a Memory File

```json
{
  "name": "modify_memory_file",
  "arguments": {
    "file_path": "2025-1/2025-1-15/conversation_20250115_143022.txt",
    "new_content": "Updated information: The project deadline has been extended.",
    "mode": "append"
  }
}
```

## Implementation Details

### Date Format
- Input dates: ISO format `YYYY-MM-DD` (e.g., `2025-01-15`)
- Directory names: Format `YYYY-M-D` (e.g., `2025-1-15`)
- File timestamps: Format `YYYYMMDD_HHMMSS` (e.g., `20250115_143022`)

### Summary File Locations
- **Day summaries**: Stored in date directories (nested under month): `YYYY-M/YYYY-M-D/summary_day_YYYYMMDD.txt`
- **Month summaries**: Stored in month directories: `YYYY-M/summary_month_YYYYMM.txt` (at month level, as they cover the entire month)
- **Year summaries**: Stored at root level: `summary_year_YYYY.txt` (at root level, as they cover the entire year)

### File Encoding
All files are saved and read using UTF-8 encoding.

### Directory Creation
Date directories are automatically created when needed. The parent `memory_dir` directory is created on first use.

### Search Behavior
- Case-insensitive search
- Returns up to 3 lines of context around matches
- Searches across all files in the memory directory
- Results are limited by `max_results` parameter

## Version History

- **0.1.0** (Current): Initial release with 9 tools for memory management
