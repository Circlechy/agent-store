"""Utility functions for DeepMemory MCP server."""

import os
from datetime import datetime
from pathlib import Path
from typing import List, Tuple


MEMORY_DIR = Path("./memory_dir")


def ensure_memory_dir() -> Path:
    """Ensure the memory directory exists."""
    MEMORY_DIR.mkdir(exist_ok=True)
    return MEMORY_DIR


def get_date_path(date: datetime) -> Path:
    """Get the path for a given date in format YYYY-M/YYYY-M-D (nested under month directory)."""
    month_str = f"{date.year}-{date.month}"
    date_str = f"{date.year}-{date.month}-{date.day}"
    return MEMORY_DIR / month_str / date_str


def ensure_date_dir(date: datetime) -> Path:
    """Ensure the date directory exists (nested under month directory)."""
    date_path = get_date_path(date)
    date_path.mkdir(parents=True, exist_ok=True)
    return date_path


def get_month_path(date: datetime) -> Path:
    """Get the path for a given month in format YYYY-M."""
    month_str = f"{date.year}-{date.month}"
    return MEMORY_DIR / month_str


def ensure_month_dir(date: datetime) -> Path:
    """Ensure the month directory exists."""
    month_path = get_month_path(date)
    month_path.mkdir(parents=True, exist_ok=True)
    return month_path


def list_all_memory_files() -> List[Tuple[Path, datetime]]:
    """List all memory files with their paths and dates."""
    files = []
    if not MEMORY_DIR.exists():
        return files
    
    # List files in month directories (YYYY-M) which contain date directories (YYYY-M-D)
    for month_dir in MEMORY_DIR.iterdir():
        if month_dir.is_dir():
            try:
                parts = month_dir.name.split("-")
                if len(parts) == 2:
                    # Month directory (YYYY-M)
                    year, month = map(int, parts)
                    
                    # List month summary files directly in month directory
                    for file_path in month_dir.iterdir():
                        if file_path.is_file():
                            # Month summary file
                            date = datetime(year, month, 1)  # Use first day of month as placeholder
                            files.append((file_path, date))
                        elif file_path.is_dir():
                            # Date directory (YYYY-M-D) nested under month directory
                            try:
                                date_parts = file_path.name.split("-")
                                if len(date_parts) == 3:
                                    day = int(date_parts[2])
                                    date = datetime(year, month, day)
                                    
                                    # List all files in this date directory
                                    for date_file in file_path.iterdir():
                                        if date_file.is_file():
                                            files.append((date_file, date))
                            except (ValueError, IndexError):
                                continue
            except (ValueError, IndexError):
                continue
    
    # List files directly in memory_dir (e.g., year summaries)
    for file_path in MEMORY_DIR.iterdir():
        if file_path.is_file():
            # For root-level files like summary_year_YYYY.txt, use file modification time
            # or try to extract date from filename
            try:
                if file_path.name.startswith("summary_year_"):
                    # Extract year from filename: summary_year_YYYY.txt
                    year = int(file_path.name.replace("summary_year_", "").replace(".txt", ""))
                    date = datetime(year, 1, 1)  # Use January 1st as placeholder date
                    files.append((file_path, date))
                else:
                    # For other root files, use modification time
                    import os
                    mtime = os.path.getmtime(file_path)
                    date = datetime.fromtimestamp(mtime)
                    files.append((file_path, date))
            except (ValueError, OSError):
                continue
    
    return sorted(files, key=lambda x: x[1], reverse=True)


def search_in_files(keyword: str, max_results: int = 10) -> List[dict]:
    """Search for keyword in all memory files."""
    results = []
    files = list_all_memory_files()
    
    for file_path, date in files:
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()
                if keyword.lower() in content.lower():
                    # Get a brief excerpt around the keyword
                    lines = content.split("\n")
                    brief = []
                    for i, line in enumerate(lines):
                        if keyword.lower() in line.lower():
                            start = max(0, i - 1)
                            end = min(len(lines), i + 2)
                            brief = lines[start:end]
                            break
                    
                    # Get relative path (for root files, this will be just the filename)
                    try:
                        rel_path = str(file_path.relative_to(MEMORY_DIR))
                    except ValueError:
                        # If file is not relative to MEMORY_DIR, use filename
                        rel_path = file_path.name
                    
                    results.append({
                        "file_path": str(file_path),
                        "date": date.isoformat(),
                        "brief_content": "\n".join(brief),
                        "full_path": rel_path
                    })
                    
                    if len(results) >= max_results:
                        break
        except Exception as e:
            continue
    
    return results


def get_timestamp_filename() -> str:
    """Generate a timestamped filename."""
    now = datetime.now()
    timestamp = now.strftime("%Y%m%d_%H%M%S")
    return f"conversation_{timestamp}.txt"
