"""Memory Reader module for DeepMemory MCP server."""

from typing import Any

from mcp.types import TextContent, Tool

import utils
from utils import list_all_memory_files, search_in_files


def get_memory_reader_tools() -> list[Tool]:
    """Get all memory reader tools."""
    return [
        Tool(
            name="list_memory_files",
            description="List all memory files in the memory file system. "
                       "Returns a list of files with their dates and paths.",
            inputSchema={
                "type": "object",
                "properties": {
                    "date_filter": {
                        "type": "string",
                        "description": "Optional date filter in ISO format (YYYY-MM-DD) to list files from a specific date",
                        "format": "date"
                    }
                }
            }
        ),
        Tool(
            name="read_memory_file",
            description="Read the content of a specific memory file.",
            inputSchema={
                "type": "object",
                "properties": {
                    "file_path": {
                        "type": "string",
                        "description": "Relative path to the memory file (e.g., '2025-1-1/conversation_20250101_120000.txt')"
                    }
                },
                "required": ["file_path"]
            }
        ),
        Tool(
            name="search_memory_files",
            description="Search for keywords across all memory files. "
                       "Returns brief content excerpts and the source file paths.",
            inputSchema={
                "type": "object",
                "properties": {
                    "keyword": {
                        "type": "string",
                        "description": "The keyword or phrase to search for"
                    },
                    "max_results": {
                        "type": "integer",
                        "description": "Maximum number of results to return (default: 10)",
                        "default": 10
                    }
                },
                "required": ["keyword"]
            }
        )
    ]


async def handle_list_memory_files(arguments: dict[str, Any]) -> list[TextContent]:
    """Handle listing all memory files."""
    from datetime import datetime
    
    date_filter_str = arguments.get("date_filter")
    files = list_all_memory_files()
    
    if date_filter_str:
        filter_date = datetime.fromisoformat(date_filter_str).date()
        files = [(path, date) for path, date in files if date.date() == filter_date]
    
    if not files:
        return [
            TextContent(
                type="text",
                text="No memory files found."
            )
        ]
    
    result_lines = ["Memory Files:"]
    result_lines.append("=" * 50)
    
    for file_path, date in files:
        rel_path = file_path.relative_to(utils.MEMORY_DIR)
        result_lines.append(f"Date: {date.strftime('%Y-%m-%d')}")
        result_lines.append(f"Path: {rel_path}")
        result_lines.append(f"Size: {file_path.stat().st_size} bytes")
        result_lines.append("-" * 50)
    
    return [
        TextContent(
            type="text",
            text="\n".join(result_lines)
        )
    ]


async def handle_read_memory_file(arguments: dict[str, Any]) -> list[TextContent]:
    """Handle reading a specific memory file."""
    file_path_str = arguments.get("file_path", "")
    file_path = utils.MEMORY_DIR / file_path_str
    
    if not file_path.exists():
        return [
            TextContent(
                type="text",
                text=f"Error: File {file_path_str} does not exist"
            )
        ]
    
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
        
        return [
            TextContent(
                type="text",
                text=f"File: {file_path_str}\n\n{content}"
            )
        ]
    except Exception as e:
        return [
            TextContent(
                type="text",
                text=f"Error reading file: {str(e)}"
            )
        ]


async def handle_search_memory_files(arguments: dict[str, Any]) -> list[TextContent]:
    """Handle searching memory files."""
    keyword = arguments.get("keyword", "")
    max_results = arguments.get("max_results", 10)
    
    if not keyword:
        return [
            TextContent(
                type="text",
                text="Error: keyword is required"
            )
        ]
    
    results = search_in_files(keyword, max_results)
    
    if not results:
        return [
            TextContent(
                type="text",
                text=f"No results found for keyword: {keyword}"
            )
        ]
    
    result_lines = [f"Search results for '{keyword}':"]
    result_lines.append("=" * 50)
    
    for i, result in enumerate(results, 1):
        result_lines.append(f"\nResult {i}:")
        result_lines.append(f"File: {result['full_path']}")
        result_lines.append(f"Date: {result['date']}")
        result_lines.append(f"Brief content:\n{result['brief_content']}")
        result_lines.append("-" * 50)
    
    return [
        TextContent(
            type="text",
            text="\n".join(result_lines)
        )
    ]
