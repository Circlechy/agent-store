"""DeepMemory MCP Server - Main entry point using FastMCP."""

from fastmcp import FastMCP

from memory_writer import (
    handle_write_raw_conversation,
    handle_write_summarized_memory,
    handle_modify_memory_file
)
from memory_reader import (
    handle_list_memory_files,
    handle_read_memory_file,
    handle_search_memory_files
)
from memory_stats import (
    handle_get_memory_statistics,
    handle_delete_memory_file,
    handle_get_memory_by_date_range
)

# Create the FastMCP server
mcp = FastMCP("DeepMemoryMcp")


# Memory Writer Tools
@mcp.tool()
async def write_raw_conversation(
    conversation: str,
    date: str = None
) -> str:
    """
    Write raw conversation history into the memory file system.
    Generates a timestamped file and saves the conversation in the appropriate date directory.
    
    Args:
        conversation: The conversation history to save
        date: Date in ISO format (YYYY-MM-DD). If not provided, uses today's date.
    """
    result = await handle_write_raw_conversation({
        "conversation": conversation,
        "date": date
    })
    return result[0].text if result else "Successfully saved conversation"


@mcp.tool()
async def write_summarized_memory(
    summary: str,
    date: str,
    summary_type: str
) -> str:
    """
    Write summarized memory. The memory will be summarized by day/month/year
    and saved in the corresponding directory.
    
    Args:
        summary: The summarized memory content
        date: Date in ISO format (YYYY-MM-DD) for the summary
        summary_type: Type of summary: day, month, or year
    """
    result = await handle_write_summarized_memory({
        "summary": summary,
        "date": date,
        "summary_type": summary_type
    })
    return result[0].text if result else "Successfully saved summary"


@mcp.tool()
async def modify_memory_file(
    file_path: str,
    new_content: str,
    mode: str = "append"
) -> str:
    """
    Modify an existing memory file. You can append, replace, or update content.
    
    Args:
        file_path: Relative path to the memory file (e.g., '2025-1-1/conversation_20250101_120000.txt')
        new_content: The new content to write or append
        mode: Mode: 'replace' to overwrite the file, 'append' to add to the end
    """
    result = await handle_modify_memory_file({
        "file_path": file_path,
        "new_content": new_content,
        "mode": mode
    })
    return result[0].text if result else "Successfully modified file"


# Memory Reader Tools
@mcp.tool()
async def list_memory_files(
    date_filter: str = None
) -> str:
    """
    List all memory files in the memory file system.
    Returns a list of files with their dates and paths.
    
    Args:
        date_filter: Optional date filter in ISO format (YYYY-MM-DD) to list files from a specific date
    """
    result = await handle_list_memory_files({
        "date_filter": date_filter
    } if date_filter else {})
    return result[0].text if result else "No memory files found"


@mcp.tool()
async def read_memory_file(
    file_path: str
) -> str:
    """
    Read the content of a specific memory file.
    
    Args:
        file_path: Relative path to the memory file (e.g., '2025-1-1/conversation_20250101_120000.txt')
    """
    result = await handle_read_memory_file({
        "file_path": file_path
    })
    return result[0].text if result else "File not found"


@mcp.tool()
async def search_memory_files(
    keyword: str,
    max_results: int = 10
) -> str:
    """
    Search for keywords across all memory files. Good key words including a name, a definition, a location, etc.
    Returns brief content excerpts and the source file paths.
    
    Args:
        keyword: The keyword or phrase to search for
        max_results: Maximum number of results to return (default: 10)
    """
    result = await handle_search_memory_files({
        "keyword": keyword,
        "max_results": max_results
    })
    return result[0].text if result else "No results found"


# Memory Stats Tools
@mcp.tool()
async def get_memory_statistics() -> str:
    """
    Get statistics about the memory file system including total files,
    total size, date range, and files per date.
    """
    result = await handle_get_memory_statistics({})
    return result[0].text if result else "No statistics available"


@mcp.tool()
async def delete_memory_file(
    file_path: str
) -> str:
    """
    Delete a specific memory file from the memory file system.
    
    Args:
        file_path: Relative path to the memory file to delete
    """
    result = await handle_delete_memory_file({
        "file_path": file_path
    })
    return result[0].text if result else "File deleted"


@mcp.tool()
async def get_memory_by_date_range(
    start_date: str,
    end_date: str
) -> str:
    """
    Get all memory files within a date range.
    
    Args:
        start_date: Start date in ISO format (YYYY-MM-DD)
        end_date: End date in ISO format (YYYY-MM-DD)
    """
    result = await handle_get_memory_by_date_range({
        "start_date": start_date,
        "end_date": end_date
    })
    return result[0].text if result else "No files found in date range"


# Run the server
if __name__ == "__main__":
    mcp.run(show_banner=False)
