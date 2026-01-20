"""
Integration of PEP documents with openjiuwen knowledge base framework.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional

from openjiuwen.core.common.logging import retrieval_logger
from openjiuwen.core.retrieval import OpenAIEmbedding
from openjiuwen.core.retrieval.common.config import (
    EmbeddingConfig,
    KnowledgeBaseConfig,
    RetrievalConfig,
    VectorStoreConfig,
)
from openjiuwen.core.retrieval.common.document import Document
from openjiuwen.core.retrieval.indexing.indexer.milvus_indexer import MilvusIndexer
from openjiuwen.core.retrieval.indexing.processor.chunker.chunking import TextChunker
from openjiuwen.core.retrieval.indexing.processor.parser.auto_file_parser import AutoFileParser
from openjiuwen.core.retrieval.simple_knowledge_base import SimpleKnowledgeBase
from openjiuwen.core.retrieval.vector_store.milvus_store import MilvusVectorStore

from .get_pep_index import CacheManager
from .pep_models import PEPDocument
from .pep_processor import build_pep_documents

HAS_INIT = False


class PEPKnowledgeBase:
    """Knowledge base for PEP documents using openjiuwen framework."""

    def __init__(
        self,
        kb_id: str = "pep_kb",
        milvus_uri: str = "http://192.168.2.2:19530",
        milvus_token: str = "",
        database_name: str = "pep_kb",
        embedding_model_name: str = "qwen3-embedding-8b",
        embedding_api_key: str = "sk-1234",
        embedding_base_url: str = "http://localhost:11450/v1/embeddings",
        chunk_size: int = 512,
        chunk_overlap: int = 50,
        index_type: str = "hybrid",
        cache_manager: Optional[CacheManager] = None,
    ):
        """Initialize PEP knowledge base.

        Args:
            kb_id: Knowledge base identifier
            milvus_uri: Milvus server URI
            milvus_token: Milvus authentication token
            database_name: Milvus database name
            embedding_model_name: Embedding model name
            embedding_api_key: Embedding API key
            embedding_base_url: Embedding API base URL
            chunk_size: Chunk size for text splitting
            chunk_overlap: Chunk overlap size
            index_type: Index type (vector, bm25, or hybrid)
            cache_manager: Optional CacheManager instance
        """
        self.kb_id = kb_id
        self.cache_manager = cache_manager or CacheManager()

        # Knowledge base configuration
        kb_config = KnowledgeBaseConfig(
            kb_id=kb_id,
            index_type=index_type,
            use_graph=False,
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
        )

        # Vector store configuration
        vector_store_config = VectorStoreConfig(
            collection_name=f"kb_{kb_id}_chunks",
            distance_metric="cosine",
            database_name=database_name,
        )

        # Create vector store
        self.vector_store = MilvusVectorStore(
            config=vector_store_config,
            milvus_uri=milvus_uri,
            milvus_token=milvus_token,
        )

        # Create embedding model
        embedding_config = EmbeddingConfig(
            model_name=embedding_model_name,
            api_key=embedding_api_key,
            base_url=embedding_base_url,
        )
        self.embed_model = OpenAIEmbedding(
            config=embedding_config,
            max_retries=10,
            timeout=60,
        )

        # Create index manager
        self.indexer = MilvusIndexer(
            milvus_uri=milvus_uri,
            milvus_token=milvus_token,
            database_name=database_name,
        )

        # Create parser (for text content)
        self.parser = AutoFileParser()

        # Create chunker
        self.chunker = TextChunker(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            chunk_unit="token",
        )

        # Create knowledge base instance
        self.knowledge_base = SimpleKnowledgeBase(
            config=kb_config,
            vector_store=self.vector_store,
            embed_model=self.embed_model,
            parser=self.parser,
            chunker=self.chunker,
            index_manager=self.indexer,
        )

    def _pep_document_to_openjiuwen_document(self, pep_doc: PEPDocument) -> Document:
        """Convert PEPDocument to openjiuwen Document format.

        Args:
            pep_doc: PEPDocument instance

        Returns:
            openjiuwen Document instance
        """
        # Build searchable text content
        content_parts = []

        # Add title and abstract
        content_parts.append(f"PEP {pep_doc.number}: {pep_doc.title}")
        if pep_doc.abstract:
            content_parts.append(f"\nAbstract: {pep_doc.abstract}")

        # Add metadata as text for better search
        if pep_doc.python_version:
            content_parts.append(f"\nPython Version: {pep_doc.python_version}")
        if pep_doc.status:
            content_parts.append(f"\nStatus: {pep_doc.status}")
        if pep_doc.type:
            content_parts.append(f"\nType: {pep_doc.type}")

        # Add main content (limit length for better chunking)
        if pep_doc.content_type == "rst":
            # For RST, use the content directly
            content_parts.append(f"\n\n{pep_doc.content}")
        else:
            # For HTML (PEP 0), use searchable text
            content_parts.append(f"\n\n{pep_doc.searchable_text}")

        content = "\n".join(content_parts)

        # Build metadata
        metadata: Dict[str, Any] = {
            "pep_number": pep_doc.number,
            "pep_title": pep_doc.title,
            "pep_url": pep_doc.url,
            "status": pep_doc.status.value if hasattr(pep_doc.status, "value") else str(pep_doc.status),
            "type": pep_doc.type.value if hasattr(pep_doc.type, "value") else str(pep_doc.type),
            "python_version": pep_doc.python_version or "",
            "superseded_by": pep_doc.superseded_by or "",
            "replaces": ",".join(map(str, pep_doc.replaces)) if pep_doc.replaces else "",
            "requires": ",".join(map(str, pep_doc.requires)) if pep_doc.requires else "",
            "created": pep_doc.created.isoformat() if isinstance(pep_doc.created, datetime) else str(pep_doc.created),
            "last_updated": pep_doc.last_updated.isoformat()
            if isinstance(pep_doc.last_updated, datetime)
            else str(pep_doc.last_updated),
            "content_type": pep_doc.content_type,
            "keywords": ",".join(pep_doc.keywords) if pep_doc.keywords else "",
        }

        # Add authors if available
        if pep_doc.authors:
            metadata["authors"] = ",".join(pep_doc.authors)
        if pep_doc.author_names:
            metadata["author_names"] = ",".join(pep_doc.author_names)

        # Create Document
        doc = Document(
            text=content,
            metadata=metadata,
        )

        # Set document ID
        doc.id_ = f"pep_{pep_doc.number}"

        return doc

    async def build_and_index_peps(self, filter_status: bool = True) -> Dict[str, Any]:
        """Build PEP documents and index them in the knowledge base.

        For initial setup, this indexes all PEPs. For continuous usage,
        prefer update_changed_peps() which only updates changed documents.

        Note: PEP cache is automatically updated when needed via get_current_pep_collection(),
        which checks for remote updates and downloads changed PEPs.

        Args:
            filter_status: If True, filter out Rejected, Withdrawn, Superseded PEPs

        Returns:
            Dictionary with indexing statistics:
            {
                "added": List[str],     # Document IDs that were added
                "updated": List[str],    # Document IDs that were updated (if any)
                "total": int            # Total documents processed
            }
        """
        stats = {"added": [], "updated": [], "total": 0}

        # Build PEP documents (cache is automatically updated if needed)
        retrieval_logger.info("Building PEP documents from cache...")
        pep_documents = build_pep_documents(self.cache_manager, filter_status=filter_status)

        retrieval_logger.info("Found %d valid PEP documents", len(pep_documents))
        stats["total"] = len(pep_documents)

        # Convert to openjiuwen Document format
        retrieval_logger.info("Converting PEP documents to knowledge base format...")
        documents = []
        for pep_doc in pep_documents:
            try:
                doc = self._pep_document_to_openjiuwen_document(pep_doc)
                documents.append(doc)
            except Exception as e:
                retrieval_logger.error("Failed to convert PEP %r: %r", pep_doc.number, e)
                continue

        retrieval_logger.info("Converted %d documents", len(documents))

        # Add or update documents in knowledge base
        retrieval_logger.info("Indexing documents in knowledge base...")

        # Try to add documents (will handle duplicates if update_documents is used internally)
        doc_ids = await self.knowledge_base.add_documents(documents)
        stats["added"] = doc_ids
        retrieval_logger.info("✓ Successfully indexed %d PEP documents", len(doc_ids))

        return stats

    async def search_peps(self, query: str, top_k: int = 5, filters: Optional[Dict[str, Any]] = None) -> List[Any]:
        """Search PEP documents in the knowledge base.

        Args:
            query: Search query string
            top_k: Number of results to return
            filters: Optional metadata filters (e.g., {"status": "Final", "python_version": "3.9"})

        Returns:
            List of retrieval results
        """
        retrieval_config = RetrievalConfig(
            top_k=top_k,
            filters=filters,
        )

        results = await self.knowledge_base.retrieve(query, config=retrieval_config)
        return results

    async def delete_peps(self, pep_numbers: List[int]) -> bool:
        """Delete PEP documents from the knowledge base.

        Args:
            pep_numbers: List of PEP numbers to delete

        Returns:
            True if successful
        """
        doc_ids = [f"pep_{num}" for num in pep_numbers]
        success = await self.knowledge_base.delete_documents(doc_ids)
        return success

    def _get_peps_to_update(self) -> List[int]:
        """Get list of PEP numbers that need updating.

        Compares local and remote last update dates to identify changed PEPs.

        Returns:
            List of PEP numbers that need updating
        """
        entries_to_update = self.cache_manager.get_entries_to_update()
        pep_numbers = []
        for key in entries_to_update.keys():
            if key != "last_fetched":
                try:
                    pep_numbers.append(int(key))
                except ValueError:
                    continue
        return pep_numbers

    async def update_pep(self, pep_number: int) -> Optional[str]:
        """Update a single PEP document in the knowledge base.

        Uses update_documents instead of delete + add for better performance.

        Args:
            pep_number: PEP number to update

        Returns:
            Document ID if successful, None otherwise
        """
        # First, ensure cache is updated for this PEP
        self.cache_manager.get_current_pep_collection()

        # Rebuild PEP documents (only this one)
        pep_documents = build_pep_documents(
            self.cache_manager,
            filter_status=False,  # Don't filter, we want this specific PEP
        )

        # Find the specific PEP
        pep_doc = next((p for p in pep_documents if p.number == pep_number), None)
        if not pep_doc:
            retrieval_logger.error("PEP %d not found", pep_number)
            return None

        # Convert to Document
        doc = self._pep_document_to_openjiuwen_document(pep_doc)

        # Use update_documents instead of delete + add
        try:
            updated_doc_ids = await self.knowledge_base.update_documents([doc])
            return updated_doc_ids[0] if updated_doc_ids else None
        except Exception as e:
            # Fallback: if update_documents fails, try delete + add
            retrieval_logger.warning("update_documents failed for PEP %d, trying delete + add: %r", pep_number, e)
            await self.delete_peps([pep_number])
            doc_ids = await self.knowledge_base.add_documents([doc])
            return doc_ids[0] if doc_ids else None

    async def update_changed_peps(self, filter_status: bool = True, force_update_all: bool = False) -> Dict[str, Any]:
        """Update only PEP documents that have changed.

        This is the recommended method for continuous usage. It:
        1. Checks which PEPs have been updated remotely
        2. Updates only those PEPs in the knowledge base
        3. Optionally adds new PEPs that weren't indexed before

        Args:
            filter_status: If True, filter out Rejected, Withdrawn, Superseded PEPs
            force_update_all: If True, update all PEPs regardless of change status

        Returns:
            Dictionary with update statistics:
            {
                "updated": List[str],  # Document IDs that were updated
                "added": List[str],     # Document IDs that were added (new PEPs)
                "skipped": int,        # Number of PEPs skipped (no changes)
                "errors": List[str]     # PEP numbers that failed to update
            }
        """
        stats = {"updated": [], "added": [], "skipped": 0, "errors": []}

        # Get PEPs that need updating
        if force_update_all:
            # Get all PEPs
            pep_documents = build_pep_documents(self.cache_manager, filter_status=filter_status)
            pep_numbers_to_update = [p.number for p in pep_documents]
        else:
            # Only get changed PEPs
            pep_numbers_to_update = self._get_peps_to_update()

        if not pep_numbers_to_update:
            retrieval_logger.info("No PEPs need updating.")
            return stats

        retrieval_logger.info("Found %d PEPs to update", len(pep_numbers_to_update))

        # Get all current PEP documents
        all_pep_documents = build_pep_documents(self.cache_manager, filter_status=filter_status)

        # Create a mapping of PEP number to PEPDocument
        pep_doc_map = {p.number: p for p in all_pep_documents}

        # Convert to Documents
        documents_to_update: list[Document] = []

        for pep_number in pep_numbers_to_update:
            pep_doc = pep_doc_map.get(pep_number)
            if not pep_doc:
                stats["errors"].append(str(pep_number))
                continue

            # Check if should be filtered
            if filter_status and not pep_doc.is_valid_for_retrieval():
                stats["skipped"] += 1
                continue

            try:
                doc = self._pep_document_to_openjiuwen_document(pep_doc)

                # Try to determine if this is an update or new addition
                # For now, we'll try update first, and if it fails, it might be a new doc
                documents_to_update.append(doc)
            except Exception as e:
                retrieval_logger.error("Failed to convert PEP %d: %r", pep_number, e)
                stats["errors"].append(str(pep_number))
                continue

        # Update documents in batch
        if documents_to_update:
            retrieval_logger.info("Updating %d PEP documents...", len(documents_to_update))
            try:
                await self.knowledge_base.delete_documents(doc_ids=sorted({doc.id_ for doc in documents_to_update}))
                updated_doc_ids = await self.knowledge_base.add_documents(documents_to_update)
                stats["updated"].extend(updated_doc_ids)
                retrieval_logger.info("✓ Successfully updated %d PEP documents", len(updated_doc_ids))
            except Exception as e:
                retrieval_logger.warning("Batch update failed, trying individual updates: %r", e)
                # Fallback: update individually
                for doc in documents_to_update:
                    try:
                        updated_ids = await self.knowledge_base.update_documents([doc])
                        if updated_ids:
                            stats["updated"].extend(updated_ids)
                        else:
                            # If update returns empty, might be a new document
                            added_ids = await self.knowledge_base.add_documents([doc])
                            if added_ids:
                                stats["added"].extend(added_ids)
                    except Exception:
                        # If update fails, try add (might be new document)
                        try:
                            added_ids = await self.knowledge_base.add_documents([doc])
                            if added_ids:
                                stats["added"].extend(added_ids)
                        except Exception as add_error:
                            pep_num = doc.metadata.get("pep_number", "unknown")
                            retrieval_logger.error("Error updating/adding PEP %r: %r", pep_num, add_error)
                            stats["errors"].append(str(pep_num))

        retrieval_logger.info(
            "Update complete:\n\tUpdated: %d\n\tAdded: %d\n\tSkipped: %d\n\tErrors: %d",
            len(stats["updated"]),
            stats["skipped"],
            len(stats["errors"]),
        )

        return stats


async def create_pep_knowledge_base(
    kb_id: str = "pep_kb",
    milvus_uri: str = "http://192.168.2.2:19530",
    milvus_token: str = "",
    database_name: str = "pep_kb",
    embedding_model_name: str = "qwen3-embedding-8b",
    embedding_api_key: str = "sk-1234",
    embedding_base_url: str = "http://localhost:11450/v1/embeddings",
    **kwargs,
) -> PEPKnowledgeBase:
    """Create and initialize a PEP knowledge base.

    Args:
        kb_id: Knowledge base identifier
        milvus_uri: Milvus server URI
        milvus_token: Milvus authentication token
        database_name: Milvus database name
        embedding_model_name: Embedding model name
        embedding_api_key: Embedding API key
        embedding_base_url: Embedding API base URL
        **kwargs: Additional arguments passed to PEPKnowledgeBase

    Returns:
        PEPKnowledgeBase instance
    """
    global HAS_INIT
    api_key_splitpos = embedding_api_key.find("-")
    if api_key_splitpos > 0:
        head = embedding_api_key[: api_key_splitpos + 1]
        tail = "*" * len(embedding_api_key[api_key_splitpos + 1 :])
        if len(tail) > 5:
            tail = tail[:-4] + embedding_api_key[-4:]
        censored_api_key = head + tail
    else:
        censored_api_key = "*" * len(embedding_api_key)
        if len(censored_api_key) > 5:
            censored_api_key = censored_api_key[:-4] + embedding_api_key[-4:]
    config_str = (
        f"  - {kb_id=}\n  - {milvus_uri=}\n  - {milvus_token=}\n  - {database_name=}\n  - {embedding_model_name=}\n  - "
        + f"embedding_api_key={censored_api_key}\n  - {embedding_base_url=}\n  - {kwargs=}"
    )
    if not HAS_INIT:
        print("Creating PEP Knowledge Base with settings:\n" + config_str)
        HAS_INIT = True
    return PEPKnowledgeBase(
        kb_id=kb_id,
        milvus_uri=milvus_uri,
        milvus_token=milvus_token,
        database_name=database_name,
        embedding_model_name=embedding_model_name,
        embedding_api_key=embedding_api_key,
        embedding_base_url=embedding_base_url,
        **kwargs,
    )
