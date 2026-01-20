"""
Pydantic models for PEP data storage and retrieval.
"""

from datetime import datetime
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field, field_validator


class PEPStatus(str, Enum):
    """PEP status values as defined in PEP 0."""

    ACCEPTED = "Accepted"
    ACTIVE = "Active"
    DEFERRED = "Deferred"
    DRAFT = "Draft"
    FINAL = "Final"
    PROVISIONAL = "Provisional"
    REJECTED = "Rejected"
    SUPERSEDED = "Superseded"
    WITHDRAWN = "Withdrawn"


class PEPType(str, Enum):
    """PEP type values."""

    STANDARDS_TRACK = "Standards Track"
    INFORMATIONAL = "Informational"
    PROCESS = "Process"


class PEPDocument(BaseModel):
    """Complete PEP document with metadata and content for retrieval."""

    # Core identification
    number: int = Field(..., description="PEP number")
    title: str = Field(..., description="PEP title")
    url: str = Field(..., description="URL to the PEP on peps.python.org")

    # Status and type
    status: PEPStatus = Field(..., description="Current status of the PEP")
    type: PEPType = Field(..., description="Type of PEP")

    # Authors and dates
    authors: List[str] = Field(default_factory=list, description="List of author names")
    author_names: List[str] = Field(default_factory=list, description="List of author display names")
    created: datetime = Field(..., description="Creation date")
    last_updated: datetime = Field(..., description="Last update date (from timeline)")

    # Python version and relationships
    python_version: Optional[str] = Field(None, description="Python version this PEP applies to (e.g., '3.9', '3.12')")
    superseded_by: Optional[int] = Field(None, description="PEP number that supersedes this one")
    replaces: Optional[List[int]] = Field(default_factory=list, description="List of PEP numbers this PEP replaces")
    requires: Optional[List[int]] = Field(default_factory=list, description="List of PEP numbers this PEP requires")

    # Content and metadata
    content: str = Field(..., description="Full PEP content (RST or HTML for PEP 0)")
    content_type: str = Field(default="rst", description="Content type: 'rst' or 'html'")
    abstract: Optional[str] = Field(None, description="Extracted abstract/summary from PEP content")

    # Additional metadata
    topic: Optional[str] = Field(None, description="Topic category")
    discussions_to: Optional[str] = Field(None, description="Discussion thread URL")
    resolution: Optional[str] = Field(None, description="Resolution information")
    post_history: Optional[str] = Field(None, description="Post history information")

    # Search and retrieval fields
    keywords: List[str] = Field(default_factory=list, description="Extracted keywords for search")
    searchable_text: str = Field(default="", description="Processed text for search/RAG")

    @field_validator("superseded_by", mode="before")
    @classmethod
    def parse_superseded_by(cls, v):
        """Parse superseded_by from string to int."""
        if v is None or v == "":
            return None
        if isinstance(v, str):
            try:
                return int(v)
            except ValueError:
                return None
        return v

    @field_validator("replaces", "requires", mode="before")
    @classmethod
    def parse_pep_list(cls, v):
        """Parse PEP number lists from strings."""
        if v is None or v == "":
            return []
        if isinstance(v, str):
            # Handle comma-separated or space-separated lists
            parts = v.replace(",", " ").split()
            result = []
            for part in parts:
                try:
                    result.append(int(part))
                except ValueError:
                    continue
            return result
        if isinstance(v, list):
            return [int(x) if isinstance(x, str) else x for x in v if x]
        return []

    @field_validator("authors", "author_names", mode="before")
    @classmethod
    def parse_author_list(cls, v):
        """Parse author lists from various formats."""
        if v is None or v == "":
            return []
        if isinstance(v, str):
            # Handle comma-separated lists
            return [author.strip() for author in v.split(",") if author.strip()]
        if isinstance(v, list):
            return [str(author) for author in v if author]
        return []

    def is_valid_for_retrieval(self) -> bool:
        """Check if this PEP should be included in retrieval (not filtered out)."""
        # Filter out rejected, withdrawn, and superseded PEPs
        excluded_statuses = {PEPStatus.REJECTED, PEPStatus.WITHDRAWN, PEPStatus.SUPERSEDED}
        return self.status not in excluded_statuses

    def get_search_text(self) -> str:
        """Get searchable text combining title, abstract, and content."""
        parts = [self.title]
        if self.abstract:
            parts.append(self.abstract)
        # Add first part of content (avoid too much text)
        if self.content:
            # For RST, extract text content; for HTML, we might want to parse it
            content_preview = self.content[:5000]  # Limit content for search
            parts.append(content_preview)
        return " ".join(parts)

    class Config:
        """Pydantic BaseModel Config"""

        use_enum_values = True
        json_encoders = {
            datetime: lambda v: v.isoformat(),
        }
