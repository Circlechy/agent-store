"""
Helper functions for PEP data retrieval and validation.
"""

import json
import time
from datetime import datetime
from typing import Any

import requests

PEP_FIELDS = {
    "number",
    "title",
    "authors",
    "discussions_to",
    "status",
    "type",
    "topic",
    "created",
    "python_version",
    "post_history",
    "resolution",
    "requires",
    "replaces",
    "superseded_by",
    "author_names",
    "url",
}


def _retrieve_latest_peps_json(url: str) -> dict[str, dict]:
    try:
        response_text = requests.get(url).text
        peps_loaded = json.loads(response_text)
        # Validation: response is a json object with more than 100 keys and all of them are strings
        if not isinstance(peps_loaded, dict):
            raise ValueError(f"Retrieved PEP information json does not look right:\n{response_text}")
        for k, v in peps_loaded.items():
            validate_pep_entry(k, v)
    except Exception as e:
        raise ConnectionError(f"Unable to get latest PEP information from {url=}") from e
    peps_loaded["last_fetched"] = dict(timestamp=time.time(), iso=datetime.now().isoformat(timespec="seconds"))
    return peps_loaded


def validate_pep_entry(pep_index: str | Any, entry: dict[str, Any] | Any):
    """Validate pep entry's correctness"""
    if not isinstance(pep_index, str):
        raise ValueError(f"Retrieved PEP information is not a real json object as it has a non-string key: {pep_index}")
    if not isinstance(entry, dict):
        raise ValueError(f"Retrieved PEP information is corrupted: entry {pep_index} is not a json object: {entry=}")
    missing_keys = PEP_FIELDS - entry.keys()
    if missing_keys:
        raise ValueError(
            f"Retrieved PEP information is corrupted: entry {pep_index} lacks the following keys: {missing_keys}"
        )


def parse_date_str(date_str: str) -> datetime:
    """Parse date string in peps.json"""
    return datetime.strptime(date_str, "%d-%b-%Y")
