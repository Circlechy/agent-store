"""
PEP index management and caching system.
Downloads, caches, and tracks updates for PEP documents from peps.python.org.
"""

import hashlib
import io
import json
import os
import pickle
import re
import threading
import zipfile
from datetime import datetime
from functools import lru_cache
from typing import Any, Optional

import requests
from filelock import FileLock
from openjiuwen.core.common.logging import retrieval_logger

from .helper_funcs import _retrieve_latest_peps_json, parse_date_str

try:
    from tqdm import tqdm
except ImportError:
    tqdm = list

PEPS_DEFAULT_URL = "https://peps.python.org/api/peps.json"
LRU_CACHE_SIZE = 10_000
CURRENT_DIRECTORY = os.path.dirname(__file__)
PEPS_UPDATE_LOCK: FileLock = FileLock(os.path.join(CURRENT_DIRECTORY, "pep.lock"), is_singleton=True)
DATETIME_PATTERN = re.compile(r"[0-9]{2}-[A-Z][a-z]{2}-[0-9]+")
LOCAL_LAST_UPDATED: dict[str, datetime]
REMOTE_LAST_UPDATED: dict[str, datetime]


def load_last_update_date() -> dict[str, datetime]:
    """Load last update date for pep entries"""
    file_path = os.path.join(CURRENT_DIRECTORY, "last_update_date.pkl")
    if os.path.isfile(file_path):
        with open(file_path, "rb") as f:
            loaded_cache_dict = pickle.load(f)
        if isinstance(loaded_cache_dict, dict) and all(isinstance(k, str) for k in loaded_cache_dict):
            # Handle both datetime objects and ISO format strings
            result = {}
            for k, v in loaded_cache_dict.items():
                if isinstance(v, datetime):
                    result[k] = v
                elif isinstance(v, str):
                    result[k] = datetime.fromisoformat(v)
                else:
                    result[k] = v
            return result
    return {}


def get_pep_index(url: str = PEPS_DEFAULT_URL, write_to: Optional[str] = "peps-latest.json") -> dict[str, dict]:
    """Load latest pep index (peps.json)"""
    if write_to:
        with PEPS_UPDATE_LOCK:
            latest_pep_index = _retrieve_latest_peps_json(url)
            with open(os.path.join(CURRENT_DIRECTORY, write_to), "w", encoding="utf-8") as f:
                json.dump(latest_pep_index, f, ensure_ascii=False, indent=4, sort_keys=True)
    return _retrieve_latest_peps_json(url)


def load_timeline(entry: dict[str, Any]) -> list[datetime]:
    """Load the sorted timeline of an entry"""
    timeline_str = (entry["post_history"] or "") + " " + entry["created"]
    timeline = [parse_date_str(dt) for dt in DATETIME_PATTERN.findall(timeline_str)]
    timeline.sort()
    return timeline


def get_remote_last_updated(url: str = PEPS_DEFAULT_URL) -> tuple[dict[str, datetime], dict[str, Any]]:
    """Get last update from remote"""
    with PEPS_UPDATE_LOCK:
        pep_index = get_pep_index(url, write_to=None)
    update_time_dict = {k: load_timeline(v)[-1] for k, v in pep_index.items() if k != "last_fetched"}
    return update_time_dict, pep_index


class CacheManager:
    """Manages caching for PEP documents"""

    _t_lock: threading.Lock = threading.Lock()

    def __init__(self, cache_dir: str = os.path.join(CURRENT_DIRECTORY, ".cache")):
        self._t_lock = CacheManager._t_lock
        self.cache_dir = cache_dir.removesuffix(os.path.sep) + os.path.sep
        self.__cache_dict = {}
        with self._t_lock:
            if os.path.isfile(self.cache_dir):
                raise FileExistsError(f"The selected {cache_dir=} already exists and is a file!")
            os.makedirs(self.cache_dir, exist_ok=True)

    @lru_cache(maxsize=LRU_CACHE_SIZE)
    def _get_cache_key(self, url: str) -> str:
        """Generate a cache key for a URL."""
        return hashlib.md5(url.encode()).hexdigest()

    @lru_cache(maxsize=LRU_CACHE_SIZE)
    def _get_cache_path(self, url: str) -> str:
        """Get the cache file path for a URL."""
        cache_key = self._get_cache_key(url)
        return f"{self.cache_dir}{cache_key}.rst"

    def save_last_update_date(self, update_dict: dict[str, datetime]):
        """Save the last update dates to disk."""
        file_path = os.path.join(CURRENT_DIRECTORY, "last_update_date.pkl")
        # Convert datetime objects to ISO format strings for serialization
        serializable_dict = {k: v.isoformat() if isinstance(v, datetime) else v for k, v in update_dict.items()}
        with open(file_path, "wb") as f:
            pickle.dump(serializable_dict, f, protocol=5)

    def _extract_pep_name(self, url: str) -> str:
        """Extract PEP name from URL by taking the last non-empty part after splitting by '/'."""
        parts = [part for part in url.split("/") if part]
        if not parts:
            raise ValueError(f"Cannot extract PEP name from URL: {url}")
        pep_name = parts[-1]
        # Ensure .rst extension
        if not pep_name.endswith(".rst"):
            pep_name = f"{pep_name}.rst"
        return pep_name

    def _download_repo_zip(self, use_gitee: bool = False) -> zipfile.ZipFile:
        """Download the entire peps repository as a zip file."""
        if use_gitee:
            zip_url = "https://gitee.com/SpikeXue_admin/peps/repository/archive/main.zip"
        else:
            zip_url = "https://github.com/python/peps/archive/refs/heads/main.zip"

        try:
            response = requests.get(zip_url, timeout=60, stream=True)
            response.raise_for_status()
            zip_data = io.BytesIO(response.content)
            return zipfile.ZipFile(zip_data)
        except Exception as e:
            if not use_gitee:
                # Try Gitee as fallback
                return self._download_repo_zip(use_gitee=True)
            raise ConnectionError(f"Unable to download PEPs repository zip from {zip_url}") from e

    def _extract_pep_from_zip(self, zip_file: zipfile.ZipFile, pep_name: str) -> str:
        """Extract a specific PEP file from the downloaded zip."""
        # Zip structure: peps-main/peps/{pep_name} or peps-main/peps/{pep_name}
        possible_paths = [
            f"peps-main/peps/{pep_name}",
            f"peps/peps/{pep_name}",
            f"peps/{pep_name}",
        ]

        for path in possible_paths:
            try:
                if path in zip_file.namelist():
                    return zip_file.read(path).decode("utf-8")
            except Exception:
                continue

        # Try to find by name pattern
        for zip_info in zip_file.namelist():
            if zip_info.endswith(pep_name) and "peps/" in zip_info:
                try:
                    return zip_file.read(zip_info).decode("utf-8")
                except Exception:
                    continue

        raise ValueError(f"PEP {pep_name} not found in repository zip")

    def download_pep_entry(self, url: str) -> str:
        """Download a PEP entry from GitHub or Gitee (fallback for China).

        First tries direct raw URL download, then falls back to downloading
        the entire repository zip and extracting the specific file.

        Special handling for PEP 0 (index page): downloads HTML directly from peps.python.org

        Extracts PEP name from the original URL and constructs download URLs:
        - Primary: https://raw.githubusercontent.com/python/peps/main/peps/{pep_name}.rst
        - Fallback: https://gitee.com/SpikeXue_admin/peps/raw/main/peps/{pep_name}.rst
        - Final fallback: Download entire repo zip and extract file
        - PEP 0 special case: Download HTML from https://peps.python.org/pep-0000/
        """
        pep_name = self._extract_pep_name(url)

        # Special handling for PEP 0 (index page) - it doesn't exist as RST in the repo
        if pep_name == "pep-0000.rst" or url.endswith("/pep-0000/") or "pep-0000" in url:
            try:
                # PEP 0 is the index page, download HTML directly
                response = requests.get("https://peps.python.org/pep-0000/", timeout=30)
                response.raise_for_status()
                if response.status_code == 200 and response.text:
                    return response.text
            except Exception as e:
                raise ConnectionError(f"Unable to download PEP 0 (index page) from peps.python.org: {e}") from e

        # Try GitHub raw URL first
        github_raw_url = f"https://raw.githubusercontent.com/python/peps/main/peps/{pep_name}"
        try:
            response = requests.get(github_raw_url, timeout=30)
            response.raise_for_status()
            if response.status_code == 200 and response.text:
                return response.text
        except Exception:
            pass

        # Try Gitee raw URL
        gitee_raw_url = f"https://gitee.com/SpikeXue_admin/peps/raw/main/peps/{pep_name}"
        try:
            response = requests.get(gitee_raw_url, timeout=30)
            response.raise_for_status()
            if response.status_code == 200 and response.text:
                return response.text
        except Exception:
            pass

        # Final fallback: Download entire repo zip and extract
        try:
            zip_file = self._download_repo_zip(use_gitee=False)
            return self._extract_pep_from_zip(zip_file, pep_name)
        except Exception:
            # Try Gitee zip as last resort
            try:
                zip_file = self._download_repo_zip(use_gitee=True)
                return self._extract_pep_from_zip(zip_file, pep_name)
            except Exception as final_error:
                raise ConnectionError(
                    f"Unable to download PEP entry {pep_name} from any source. "
                    f"Direct downloads failed, and zip extraction failed: {final_error}"
                ) from final_error

    def get_entries_to_update(self) -> dict[str, dict[str, Any]]:
        """Get entries that need updating by comparing local and remote last update dates."""
        local_last_updated = load_last_update_date()
        remote_last_updated, pep_index = get_remote_last_updated()

        entries_to_update = {}
        for key, remote_date in remote_last_updated.items():
            local_date = local_last_updated.get(key)
            if local_date is None or local_date != remote_date:
                entries_to_update[key] = pep_index[key]

        return entries_to_update

    def update_pep_collection(self) -> dict[str, str]:
        """Update the PEP collection by downloading entries that need updating."""
        entries_to_update = self.get_entries_to_update()

        if not entries_to_update:
            # No updates needed, load existing collection
            return self._load_pep_collection()

        # Download and cache entries that need updating
        updated_entries = {}
        successfully_updated_keys = []
        for key, entry_info in tqdm(entries_to_update.items(), desc="Updating PEP Docs"):
            url = entry_info.get("url")
            if not url:
                continue

            try:
                # Download the PEP entry (returns RST text content)
                pep_content = self.download_pep_entry(url)
                updated_entries[key] = pep_content
                successfully_updated_keys.append(key)

                # Cache the entry as RST text file
                cache_path = self._get_cache_path(url)
                with open(cache_path, "w", encoding="utf-8") as f:
                    f.write(pep_content)
            except Exception as e:
                retrieval_logger.warning("Failed to download PEP %s from %s: %r", key, url, e)
                continue

        # Update local last update dates only for successfully downloaded entries
        if successfully_updated_keys:
            remote_last_updated, _ = get_remote_last_updated()
            local_last_updated = load_last_update_date()
            for key in successfully_updated_keys:
                if key in remote_last_updated:
                    local_last_updated[key] = remote_last_updated[key]
            self.save_last_update_date(local_last_updated)

        # Load and merge with existing collection
        current_collection = self._load_pep_collection()
        current_collection.update(updated_entries)

        # Store the updated collection in memory
        self.__cache_dict = current_collection

        return current_collection

    def _load_pep_collection(self) -> dict[str, str]:
        """Load the PEP collection from cache files."""
        collection = {}
        if not os.path.isdir(self.cache_dir):
            return collection

        # Get all PEP entries from the index
        _, pep_index = get_remote_last_updated()

        for key, entry_info in pep_index.items():
            if key == "last_fetched":
                continue
            url = entry_info.get("url")
            if not url:
                continue

            cache_path = self._get_cache_path(url)
            if os.path.isfile(cache_path):
                try:
                    with open(cache_path, "r", encoding="utf-8") as f:
                        collection[key] = f.read()
                except Exception as e:
                    retrieval_logger.error("Failed to load cached PEP %s: %r", key, e)

        return collection

    def get_current_pep_collection(self) -> dict[str, str]:
        """Get the current latest PEP collection in memory, updating if necessary."""
        if not self.__cache_dict:
            self.__cache_dict = self.update_pep_collection()
        return self.__cache_dict
