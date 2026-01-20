"""Memory Writer module for DeepMemory MCP server."""

from datetime import datetime
from typing import Any

from mcp.types import TextContent, Tool

import utils
from utils import ensure_date_dir, ensure_month_dir, ensure_memory_dir, get_timestamp_filename


def get_memory_writer_tools() -> list[Tool]:
    """Get all memory writer tools."""
    return [
        Tool(
            name="write_raw_conversation",
            description="Write raw conversation history into the memory file system. "
                       "Generates a timestamped file and saves the conversation in the appropriate date directory.",
            inputSchema={
                "type": "object",
                "properties": {
                    "conversation": {
                        "type": "string",
                        "description": "The conversation history to save"
                    },
                    "date": {
                        "type": "string",
                        "description": "Date in ISO format (YYYY-MM-DD). If not provided, uses today's date.",
                        "format": "date"
                    }
                },
                "required": ["conversation"]
            }
        ),
        Tool(
            name="write_summarized_memory",
            description="Write summarized memory. The memory will be summarized by day/month/year "
                       "and saved in the corresponding directory.",
            inputSchema={
                "type": "object",
                "properties": {
                    "summary": {
                        "type": "string",
                        "description": "The summarized memory content"
                    },
                    "date": {
                        "type": "string",
                        "description": "Date in ISO format (YYYY-MM-DD) for the summary",
                        "format": "date"
                    },
                    "summary_type": {
                        "type": "string",
                        "enum": ["day", "month", "year"],
                        "description": "Type of summary: day, month, or year"
                    }
                },
                "required": ["summary", "date", "summary_type"]
            }
        ),
        Tool(
            name="modify_memory_file",
            description="Modify an existing memory file. You can append, replace, or update content.",
            inputSchema={
                "type": "object",
                "properties": {
                    "file_path": {
                        "type": "string",
                        "description": "Relative path to the memory file (e.g., '2025-1-1/conversation_20250101_120000.txt')"
                    },
                    "new_content": {
                        "type": "string",
                        "description": "The new content to write or append"
                    },
                    "mode": {
                        "type": "string",
                        "enum": ["replace", "append"],
                        "description": "Mode: 'replace' to overwrite the file, 'append' to add to the end",
                        "default": "append"
                    }
                },
                "required": ["file_path", "new_content"]
            }
        )
    ]


async def handle_write_raw_conversation(arguments: dict[str, Any]) -> list[TextContent]:
    """Handle writing raw conversation history."""
    conversation = arguments.get("conversation", "")
    date_str = arguments.get("date")
    
    if date_str:
        date = datetime.fromisoformat(date_str)
    else:
        date = datetime.now()
    
    date_dir = ensure_date_dir(date)
    filename = get_timestamp_filename()
    file_path = date_dir / filename
    
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(conversation)
    
    return [
        TextContent(
            type="text",
            text=f"Successfully saved conversation to {file_path.relative_to(utils.MEMORY_DIR)}"
        )
    ]


async def handle_write_summarized_memory(arguments: dict[str, Any]) -> list[TextContent]:
    """Handle writing summarized memory."""
    summary = arguments.get("summary", "")
    date_str = arguments.get("date", "")
    summary_type = arguments.get("summary_type", "day")
    
    date = datetime.fromisoformat(date_str)
    
    # Create appropriate filename and path based on summary type
    if summary_type == "day":
        date_dir = ensure_date_dir(date)
        filename = f"summary_day_{date.strftime('%Y%m%d')}.txt"
        file_path = date_dir / filename
    elif summary_type == "month":
        # Month summaries go in month directories (YYYY-M), not in date directories
        month_dir = ensure_month_dir(date)
        filename = f"summary_month_{date.strftime('%Y%m')}.txt"
        file_path = month_dir / filename
    elif summary_type == "year":
        # Year summaries go directly under memory_dir, not in a date directory
        ensure_memory_dir()
        filename = f"summary_year_{date.year}.txt"
        file_path = utils.MEMORY_DIR / filename
    else:
        date_dir = ensure_date_dir(date)
        filename = f"summary_{date.strftime('%Y%m%d')}.txt"
        file_path = date_dir / filename
    
    # Append to existing summary if it exists
    mode = "a" if file_path.exists() else "w"
    with open(file_path, mode, encoding="utf-8") as f:
        if mode == "a":
            f.write("\n\n---\n\n")
        f.write(f"[{datetime.now().isoformat()}] {summary}")
    
    return [
        TextContent(
            type="text",
            text=f"Successfully saved {summary_type} summary to {file_path.relative_to(utils.MEMORY_DIR)}"
        )
    ]


async def handle_modify_memory_file(arguments: dict[str, Any]) -> list[TextContent]:
    """Handle modifying an existing memory file."""
    file_path_str = arguments.get("file_path", "")
    new_content = arguments.get("new_content", "")
    mode = arguments.get("mode", "append")
    
    file_path = utils.MEMORY_DIR / file_path_str
    
    if not file_path.exists():
        return [
            TextContent(
                type="text",
                text=f"Error: File {file_path_str} does not exist"
            )
        ]
    
    if mode == "replace":
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(new_content)
        action = "replaced"
    else:  # append
        with open(file_path, "a", encoding="utf-8") as f:
            f.write(f"\n\n[{datetime.now().isoformat()}] {new_content}")
        action = "appended to"
    
    return [
        TextContent(
            type="text",
            text=f"Successfully {action} content to {file_path_str}"
        )
    ]
