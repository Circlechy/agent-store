"""
PEP processing and retrieval system.
Processes PEP content and metadata into structured Pydantic models.
"""

import re
from datetime import datetime
from typing import Dict, List, Optional

from openjiuwen.core.common.logging import retrieval_logger

from .get_pep_index import CacheManager, get_remote_last_updated
from .helper_funcs import parse_date_str
from .pep_models import PEPDocument, PEPStatus, PEPType

# Patterns for extracting information from RST content
RST_ABSTRACT_PATTERN = re.compile(r"^Abstract\s*=\s*\n(.*?)(?=\n\n|\n[A-Z][a-z]+\s*=|$)", re.MULTILINE | re.DOTALL)
RST_TITLE_PATTERN = re.compile(r"^PEP:\s*\d+\s*\nTitle:\s*(.+?)\s*\n", re.MULTILINE)
RST_SECTION_PATTERN = re.compile(
    r"^([A-Z][a-zA-Z\s]+)\s*=\s*\n(.*?)(?=\n\n|\n[A-Z][a-z]+\s*=|$)", re.MULTILINE | re.DOTALL
)


def extract_abstract_from_rst(content: str) -> Optional[str]:
    """Extract abstract section from RST content."""
    # Look for Abstract section
    abstract_match = RST_ABSTRACT_PATTERN.search(content)
    if abstract_match:
        abstract = abstract_match.group(1).strip()
        # Clean up the abstract (remove extra whitespace, newlines)
        abstract = re.sub(r"\s+", " ", abstract)
        return abstract[:500]  # Limit length

    # Alternative: look for content after Abstract header
    abstract_header = re.search(r"^Abstract\s*\n[-=]+\n(.*?)(?=\n\n[A-Z]|\Z)", content, re.MULTILINE | re.DOTALL)
    if abstract_header:
        abstract = abstract_header.group(1).strip()
        abstract = re.sub(r"\s+", " ", abstract)
        return abstract[:500]

    return None


def extract_keywords_from_content(content: str, title: str) -> List[str]:
    """Extract keywords from PEP content for search."""
    keywords = []

    # Add words from title
    title_words = re.findall(r"\b[a-zA-Z]{3,}\b", title.lower())
    keywords.extend(title_words)

    # Look for Keywords section in RST
    keywords_section = re.search(r"Keywords?:\s*(.+?)(?=\n\n|\Z)", content, re.MULTILINE | re.IGNORECASE)
    if keywords_section:
        kw_text = keywords_section.group(1)
        kw_list = [k.strip() for k in re.split(r"[,;]", kw_text) if k.strip()]
        keywords.extend([k.lower() for k in kw_list])

    # Extract important terms (capitalized words, module names, etc.)
    important_terms = re.findall(r"\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\b", content[:2000])
    keywords.extend([term.lower().replace(" ", "_") for term in important_terms[:10]])

    # Remove duplicates and return
    return list(set(keywords))[:20]  # Limit to 20 keywords


def process_pep_content(pep_number: str, api_metadata: Dict, content: str, last_updated: datetime) -> PEPDocument:
    """Process PEP API metadata and content into a PEPDocument model.

    Args:
        pep_number: PEP number as string (e.g., "484")
        api_metadata: Metadata from peps.json API
        content: Full PEP content (RST or HTML)
        last_updated: Last update datetime from timeline

    Returns:
        PEPDocument instance
    """
    # Determine content type
    content_type = "html" if content.strip().startswith("<!DOCTYPE") or content.strip().startswith("<html") else "rst"

    # Extract abstract
    abstract = None
    if content_type == "rst":
        abstract = extract_abstract_from_rst(content)

    # Extract keywords
    keywords = extract_keywords_from_content(content, api_metadata.get("title", ""))

    # Build searchable text
    searchable_text = f"{api_metadata.get('title', '')} {abstract or ''} {content[:2000]}"

    # Parse status and type
    status_str = api_metadata.get("status", "").strip()
    try:
        status = PEPStatus(status_str)
    except ValueError:
        # Default to Draft if status is unknown
        status = PEPStatus.DRAFT

    type_str = api_metadata.get("type", "").strip()
    try:
        pep_type = PEPType(type_str)
    except ValueError:
        # Default to Informational if type is unknown
        pep_type = PEPType.INFORMATIONAL

    # Parse created date
    created_str = api_metadata.get("created", "")
    try:
        created = parse_date_str(created_str)
    except (ValueError, TypeError):
        created = last_updated  # Fallback to last_updated

    # Build PEPDocument
    pep_doc = PEPDocument(
        number=int(pep_number),
        title=api_metadata.get("title", ""),
        url=api_metadata.get("url", ""),
        status=status,
        type=pep_type,
        authors=api_metadata.get("authors", ""),
        author_names=api_metadata.get("author_names", ""),
        created=created,
        last_updated=last_updated,
        python_version=api_metadata.get("python_version"),
        superseded_by=api_metadata.get("superseded_by"),
        replaces=api_metadata.get("replaces"),
        requires=api_metadata.get("requires"),
        content=content,
        content_type=content_type,
        abstract=abstract,
        topic=api_metadata.get("topic"),
        discussions_to=api_metadata.get("discussions_to"),
        resolution=api_metadata.get("resolution"),
        post_history=api_metadata.get("post_history"),
        keywords=keywords,
        searchable_text=searchable_text,
    )

    return pep_doc


def build_pep_documents(cache_manager: Optional[CacheManager] = None, filter_status: bool = True) -> List[PEPDocument]:
    """Build PEPDocument list from current PEP collection.

    Args:
        cache_manager: CacheManager instance (creates new one if None)
        filter_status: If True, filter out Rejected, Withdrawn, Superseded PEPs

    Returns:
        List of PEPDocument instances
    """
    if cache_manager is None:
        cache_manager = CacheManager()

    # Get PEP collection (content)
    pep_collection = cache_manager.update_pep_collection()

    # Get API metadata
    remote_last_updated, pep_index = get_remote_last_updated()

    pep_documents = []

    for pep_number, content in pep_collection.items():
        if pep_number == "last_fetched":
            continue

        # Get metadata from API
        api_metadata = pep_index.get(pep_number)
        if not api_metadata:
            continue

        # Get last updated date
        last_updated = remote_last_updated.get(pep_number)

        try:
            # Process into PEPDocument
            pep_doc = process_pep_content(
                pep_number=pep_number, api_metadata=api_metadata, content=content, last_updated=last_updated
            )

            # Filter by status if requested
            if filter_status and not pep_doc.is_valid_for_retrieval():
                continue

            pep_documents.append(pep_doc)

        except Exception as e:
            retrieval_logger.error("Failed to process PEP %s: %r", pep_number, e)
            continue

    return pep_documents


def search_peps(query: str, pep_documents: List[PEPDocument], limit: int = 10) -> List[PEPDocument]:
    """Simple text search through PEP documents.

    Args:
        query: Search query string
        pep_documents: List of PEPDocument instances
        limit: Maximum number of results

    Returns:
        List of PEPDocument instances matching the query, sorted by relevance
    """
    query_lower = query.lower()
    query_words = set(query_lower.split())

    scored_peps = []

    for pep_doc in pep_documents:
        score = 0

        # Check title
        title_lower = pep_doc.title.lower()
        if query_lower in title_lower:
            score += 10
        for word in query_words:
            if word in title_lower:
                score += 5

        # Check abstract
        if pep_doc.abstract:
            abstract_lower = pep_doc.abstract.lower()
            if query_lower in abstract_lower:
                score += 5
            for word in query_words:
                if word in abstract_lower:
                    score += 2

        # Check keywords
        for keyword in pep_doc.keywords:
            if query_lower in keyword or any(word in keyword for word in query_words):
                score += 3

        # Check searchable text
        searchable_lower = pep_doc.searchable_text.lower()
        for word in query_words:
            if word in searchable_lower:
                score += 1

        if score > 0:
            scored_peps.append((score, pep_doc))

    # Sort by score (descending) and return
    scored_peps.sort(key=lambda x: x[0], reverse=True)
    return [pep_doc for _, pep_doc in scored_peps[:limit]]
