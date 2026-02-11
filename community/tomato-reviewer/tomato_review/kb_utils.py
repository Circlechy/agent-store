"""
Knowledge base validation and setup utilities.
"""

from typing import Optional

from pymilvus import MilvusClient

from tomato_review.config import get_kb_config
from tomato_review.pep_kb.pep_knowledge_base import PEPKnowledgeBase, create_pep_knowledge_base


def check_knowledge_base(
    kb_config: Optional[dict[str, str]] = None, is_create: bool = False
) -> tuple[bool, Optional[str], bool]:
    """Check if knowledge base exists and is accessible.

    Steps:
    a. Create MilvusClient on default (checks whether can connect to this address)
    b. MilvusClient.list_databases (checks if database exists)
    c. MilvusClient.use_database (switch to correct database)
    d. MilvusClient.list_collections (check if f"kb_{kb_id}_chunks" is in it)
    e. MilvusClient.close

    Args:
        kb_config: Knowledge base configuration dict (if None, loads from config)
        is_create: Allows knowledge base to be created (set to True if creating KB)

    Returns:
        Tuple of (is_valid, error_message, should_continue)
        - is_valid: True if KB exists and is accessible
        - error_message: None if valid, otherwise error description
        - should_continue: True if we can continue (KB just needs to be created),
          False if there's a configuration/connection issue that must be fixed
    """
    if kb_config is None:
        kb_config = get_kb_config()

    kb_id = kb_config.get("kb_id")
    milvus_uri = kb_config.get("milvus_uri")
    milvus_token = kb_config.get("milvus_token", "")
    database_name = kb_config.get("database_name")

    # Missing configuration - cannot continue
    if not all([kb_id, milvus_uri, database_name]):
        missing = [
            k for k, v in {"kb_id": kb_id, "milvus_uri": milvus_uri, "database_name": database_name}.items() if not v
        ]
        return False, f"Missing required KB configuration: {', '.join(missing)}", False

    client = None
    try:
        # Step a: Create MilvusClient (checks connection)
        try:
            client = MilvusClient(uri=milvus_uri, token=milvus_token)
        except Exception as e:
            # Cannot connect - cannot continue
            return False, f"Cannot connect to Milvus at {milvus_uri}: {e}", False

        # Step b: Check if database exists
        try:
            databases = client.list_databases()
            if database_name not in databases:
                if is_create:
                    client.create_database(database_name)
                else:
                    # Database doesn't exist - cannot continue
                    return (
                        False,
                        f"Database '{database_name}' does not exist in Milvus, run tomato-review --build",
                        False,
                    )
        except Exception as e:
            # Cannot list databases - cannot continue
            return False, f"Cannot list databases: {e}", False

        # Step c: Switch to database
        try:
            client.use_database(database_name)
        except Exception as e:
            # Cannot switch to database - cannot continue
            return False, f"Cannot switch to database '{database_name}': {e}", False

        # Step d: Check if collection exists
        collection_name = f"kb_{kb_id}_chunks"
        try:
            collections = client.list_collections()
            if is_create and collection_name in collections:
                client.drop_collection(collection_name)
            if collection_name not in collections:
                if not is_create:
                    # Collection doesn't exist, but infrastructure is OK - can continue (create KB)
                    return False, f"Collection '{collection_name}' does not exist (KB not created)", True
        except Exception as e:
            # Cannot list collections - cannot continue
            return False, f"Cannot list collections: {e}", False

        # All checks passed
        if is_create:
            return False, database_name, True
        return True, None, True

    finally:
        # Step e: Close client
        if client is not None:
            try:
                client.close()
            except Exception:
                pass


async def setup_knowledge_base_if_needed(kb_config: Optional[dict[str, str]] = None) -> PEPKnowledgeBase:
    """Check if knowledge base exists, create it if needed, and update changed PEPs.

    Args:
        kb_config: Knowledge base configuration dict (if None, loads from config)

    Returns:
        PEPKnowledgeBase instance
    """
    if kb_config is None:
        kb_config = get_kb_config()

    # Check if KB exists
    is_valid, error, should_continue = check_knowledge_base(kb_config, is_create=True)

    if not is_valid:
        if not should_continue:
            # This shouldn't happen if called from CLI (CLI checks first)
            # But handle it gracefully
            raise ValueError(f"Cannot create knowledge base: {error}")

        print(f"Knowledge base not found: {error}")
        print("Creating knowledge base...")

        # Create KB
        pep_kb = await create_pep_knowledge_base(**kb_config)

        # Build initial index
        print("Building initial index (this may take several minutes)...")
        await pep_kb.build_and_index_peps(filter_status=True)

        print("✓ Knowledge base created and indexed!")
    else:
        print("✓ Knowledge base found and accessible")
        # Create KB instance (doesn't rebuild)
        pep_kb = await create_pep_knowledge_base(**kb_config)

    # Always update changed PEPs
    print("Getting latest PEPs...")
    stats = await pep_kb.update_changed_peps(filter_status=True)

    print(f"✓ Update complete: {len(stats['updated'])} updated, {len(stats['added'])} added")

    return pep_kb
