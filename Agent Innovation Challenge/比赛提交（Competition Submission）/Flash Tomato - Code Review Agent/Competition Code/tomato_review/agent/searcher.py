"""SearcherAgent: Agent for searching Python PEP documents and coding conventions.

This agent uses PEPKnowledgeBase to research Python coding conventions and best practices.
"""

from typing import Any, Dict, Optional

from openjiuwen.core.common.schema.param import Param
from openjiuwen.core.single_agent.agents.react_agent import ReActAgent, ReActAgentConfig
from openjiuwen.core.single_agent.schema.agent_card import AgentCard
from tomato_review.agent.utils import configure_from_env, get_env_var
from tomato_review.pep_kb.pep_knowledge_base import PEPKnowledgeBase, create_pep_knowledge_base


class SearcherAgent(ReActAgent):
    """Agent for searching Python PEP documents and coding conventions.

    This agent uses PEPKnowledgeBase to research topics related to Python coding
    conventions and best practices. It takes a query and optional code snippet,
    searches relevant PEPs, and returns a concise yet detailed summary.
    """

    def __init__(
        self,
        card: Optional[AgentCard] = None,
        pep_kb: Optional[PEPKnowledgeBase] = None,
        config: Optional[ReActAgentConfig] = None,
    ):
        """Initialize SearcherAgent.

        Args:
            card: Agent card (will be created with defaults if not provided)
            pep_kb: PEPKnowledgeBase instance (will be created if not provided)
            config: ReActAgentConfig (will be created with defaults if not provided)
        """
        # Create default card if not provided
        if card is None:
            card = AgentCard(
                name="searcher_agent",
                description=(
                    "Agent for searching Python PEP documents and coding conventions. "
                    "Takes a query about Python coding conventions and an optional code snippet, "
                    "searches relevant PEPs, and returns a concise yet detailed summary."
                ),
                input_params=[
                    Param.string(
                        name="query",
                        description="Query about Python coding conventions or best practices",
                        required=True,
                    ),
                    Param.string(
                        name="code_snippet",
                        description="Optional code snippet related to the query",
                        required=False,
                    ),
                ],
            )

        # Initialize parent
        super().__init__(card)

        # Store PEP knowledge base
        self._pep_kb = pep_kb

        # Configure agent if config provided
        if config is not None:
            self.configure(config)
        else:
            # Set configuration from environment variables (all required)
            default_config = ReActAgentConfig()
            configure_from_env(default_config)
            self.configure(default_config)

    async def _get_pep_kb(self) -> PEPKnowledgeBase:
        """Get or create PEPKnowledgeBase instance.

        Returns:
            PEPKnowledgeBase instance

        Raises:
            ValueError: If required environment variables are not set
        """
        if self._pep_kb is None:
            # Create PEP knowledge base with configuration from environment
            # All variables are required - no defaults
            # Get integer environment variables with validation
            chunk_size_str = get_env_var("PEP_CHUNK_SIZE", required=True)
            chunk_overlap_str = get_env_var("PEP_CHUNK_OVERLAP", required=True)

            try:
                chunk_size = int(chunk_size_str)
                chunk_overlap = int(chunk_overlap_str)
            except ValueError as e:
                raise ValueError(
                    f"Invalid integer value for environment variable: {e}. "
                    f"PEP_CHUNK_SIZE={chunk_size_str}, PEP_CHUNK_OVERLAP={chunk_overlap_str}"
                ) from e

            kb_config = {
                "kb_id": get_env_var("PEP_KB_ID", required=True),
                "milvus_uri": get_env_var("MILVUS_URI", required=True),
                "milvus_token": get_env_var("MILVUS_TOKEN", required=False),
                "database_name": get_env_var("MILVUS_DATABASE", required=True),
                "embedding_model_name": get_env_var("EMBEDDING_MODEL", required=True),
                "embedding_api_key": get_env_var("EMBEDDING_API_KEY", required=True),
                "embedding_base_url": get_env_var("EMBEDDING_BASE_URL", required=True),
                "chunk_size": chunk_size,
                "chunk_overlap": chunk_overlap,
                "index_type": get_env_var("PEP_INDEX_TYPE", required=True),
            }
            self._pep_kb = await create_pep_knowledge_base(**kb_config)
        return self._pep_kb

    async def invoke(
        self,
        inputs: Any,
        session: Optional[Any] = None,
    ) -> Dict[str, Any]:
        """Execute search for Python coding conventions.

        Args:
            inputs: Input dict with 'query' and optional 'code_snippet', or string query
            session: Session object (optional)

        Returns:
            Dict with 'output' (summary) and 'result_type'
        """
        # Normalize inputs
        if isinstance(inputs, dict):
            query = inputs.get("query") or inputs.get("user_input")
            code_snippet = inputs.get("code_snippet", "")
        elif isinstance(inputs, str):
            query = inputs
            code_snippet = ""
        else:
            raise ValueError("Input must be dict with 'query' or str")

        if not query:
            raise ValueError("Query is required")

        # Build enhanced query with code snippet if provided
        enhanced_query = query
        if code_snippet:
            enhanced_query = f"{query}\n\nRelated code:\n{code_snippet}"

        # Get PEP knowledge base
        pep_kb = await self._get_pep_kb()

        # Search for relevant PEPs
        results = await pep_kb.search_peps(enhanced_query, top_k=5)

        # Build summary from results
        if not results:
            summary = (
                f"No relevant PEP documents found for query: '{query}'. "
                "Consider rephrasing the query or checking if the topic is covered in PEPs."
            )
        else:
            summary_parts = [f"Found {len(results)} relevant PEP document(s) for: '{query}'\n"]

            for i, result in enumerate(results, 1):
                metadata = result.metadata
                pep_num = metadata.get("pep_number", "N/A")
                pep_title = metadata.get("pep_title", "N/A")
                status = metadata.get("status", "N/A")
                score = result.score

                summary_parts.append(f"\n[{i}] PEP {pep_num}: {pep_title}")
                summary_parts.append(f"    Status: {status}")
                summary_parts.append(f"    Relevance Score: {score:.4f}")

                # Add Python version if available
                if metadata.get("python_version"):
                    summary_parts.append(f"    Python Version: {metadata.get('python_version')}")

                # Add warning if superseded
                if metadata.get("superseded_by"):
                    summary_parts.append(f"    ⚠️  Note: This PEP is superseded by PEP {metadata.get('superseded_by')}")

                # Add URL
                if metadata.get("pep_url"):
                    summary_parts.append(f"    URL: {metadata.get('pep_url')}")

                # Add text preview (first 200 chars)
                text_preview = result.text[:200] if result.text else ""
                if text_preview:
                    summary_parts.append(f"    Preview: {text_preview}...")

            # Add key recommendations
            summary_parts.append("\n\nKey Recommendations:")
            if results:
                top_result = results[0]
                top_metadata = top_result.metadata
                summary_parts.append(
                    f"- Primary reference: PEP {top_metadata.get('pep_number')} ({top_metadata.get('pep_title')})"
                )
                if top_metadata.get("pep_url"):
                    summary_parts.append(f"  URL: {top_metadata.get('pep_url')}")

            summary = "\n".join(summary_parts)

        return {
            "output": summary,
            "result_type": "answer",
            "query": query,
            "results_count": len(results),
        }


__all__ = ["SearcherAgent"]
