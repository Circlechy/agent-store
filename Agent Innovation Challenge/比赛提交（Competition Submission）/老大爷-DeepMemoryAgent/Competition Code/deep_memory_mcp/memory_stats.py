"""Memory Statistics and additional utility tools for DeepMemory MCP server."""

from datetime import datetime
from typing import Any

from mcp.types import TextContent, Tool

import utils
from utils import list_all_memory_files


def get_memory_stats_tools() -> list[Tool]:
    """Get additional utility tools."""
    return [
        Tool(
            name="get_memory_statistics",
            description="Get statistics about the memory file system including total files, "
                       "total size, date range, and files per date.",
            inputSchema={
                "type": "object",
                "properties": {}
            }
        ),
        Tool(
            name="delete_memory_file",
            description="Delete a specific memory file from the memory file system.",
            inputSchema={
                "type": "object",
                "properties": {
                    "file_path": {
                        "type": "string",
                        "description": "Relative path to the memory file to delete"
                    }
                },
                "required": ["file_path"]
            }
        ),
        Tool(
            name="get_memory_by_date_range",
            description="Get all memory files within a date range.",
            inputSchema={
                "type": "object",
                "properties": {
                    "start_date": {
                        "type": "string",
                        "description": "Start date in ISO format (YYYY-MM-DD)",
                        "format": "date"
                    },
                    "end_date": {
                        "type": "string",
                        "description": "End date in ISO format (YYYY-MM-DD)",
                        "format": "date"
                    }
                },
                "required": ["start_date", "end_date"]
            }
        )
    ]


async def handle_get_memory_statistics(arguments: dict[str, Any]) -> list[TextContent]:
    """Handle getting memory statistics."""
    files = list_all_memory_files()
    
    if not files:
        return [
            TextContent(
                type="text",
                text="No memory files found."
            )
        ]
    
    total_files = len(files)
    total_size = sum(f.stat().st_size for f, _ in files)
    
    dates = [date for _, date in files]
    if dates:
        earliest_date = min(dates)
        latest_date = max(dates)
    else:
        earliest_date = latest_date = None
    
    # Count files per date
    files_per_date = {}
    for _, date in files:
        date_str = date.strftime("%Y-%m-%d")
        files_per_date[date_str] = files_per_date.get(date_str, 0) + 1
    
    result_lines = ["Memory Statistics:"]
    result_lines.append("=" * 50)
    result_lines.append(f"Total files: {total_files}")
    result_lines.append(f"Total size: {total_size:,} bytes ({total_size / 1024 / 1024:.2f} MB)")
    
    if earliest_date and latest_date:
        result_lines.append(f"Date range: {earliest_date.strftime('%Y-%m-%d')} to {latest_date.strftime('%Y-%m-%d')}")
    
    result_lines.append("\nFiles per date:")
    for date_str in sorted(files_per_date.keys()):
        result_lines.append(f"  {date_str}: {files_per_date[date_str]} file(s)")
    
    return [
        TextContent(
            type="text",
            text="\n".join(result_lines)
        )
    ]


async def handle_delete_memory_file(arguments: dict[str, Any]) -> list[TextContent]:
    """Handle deleting a memory file."""
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
        file_path.unlink()
        return [
            TextContent(
                type="text",
                text=f"Successfully deleted file: {file_path_str}"
            )
        ]
    except Exception as e:
        return [
            TextContent(
                type="text",
                text=f"Error deleting file: {str(e)}"
            )
        ]


async def handle_get_memory_by_date_range(arguments: dict[str, Any]) -> list[TextContent]:
    """Handle getting memory files by date range."""
    start_date_str = arguments.get("start_date", "")
    end_date_str = arguments.get("end_date", "")
    
    start_date = datetime.fromisoformat(start_date_str).date()
    end_date = datetime.fromisoformat(end_date_str).date()
    
    files = list_all_memory_files()
    filtered_files = [
        (path, date) for path, date in files
        if start_date <= date.date() <= end_date
    ]
    
    if not filtered_files:
        return [
            TextContent(
                type="text",
                text=f"No files found in date range {start_date_str} to {end_date_str}"
            )
        ]
    
    result_lines = [f"Memory files from {start_date_str} to {end_date_str}:"]
    result_lines.append("=" * 50)
    
    for file_path, date in sorted(filtered_files, key=lambda x: x[1]):
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
