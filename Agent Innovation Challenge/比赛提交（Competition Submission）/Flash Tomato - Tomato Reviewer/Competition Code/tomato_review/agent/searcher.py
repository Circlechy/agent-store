"""SearcherAgent: Agent for searching Python PEP documents and coding conventions.

This agent uses PEPKnowledgeBase to research Python coding conventions and best practices.
Uses LLM reasoning through ReActAgent framework.
"""

import threading
from typing import Any, Dict, Optional

from openjiuwen.core.common.schema.param import Param
from openjiuwen.core.foundation.llm import ToolCall, ToolMessage
from openjiuwen.core.foundation.tool import tool
from openjiuwen.core.session.session import Session
from openjiuwen.core.single_agent.agents.react_agent import ReActAgent, ReActAgentConfig
from openjiuwen.core.single_agent.schema.agent_card import AgentCard
from tqdm import tqdm

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
        pbar: Optional[tqdm] = None,
        lock: threading.Lock = threading.Lock(),
    ):
        """Initialize SearcherAgent.

        Args:
            card: Agent card (will be created with defaults if not provided)
            pep_kb: PEPKnowledgeBase instance (will be created if not provided)
            config: ReActAgentConfig (will be created with defaults if not provided)
            pbar: Tqdm progress bar (default: None)
            lock: thread lock
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

        # Progress tracking
        self.pbar = pbar
        self.lock = lock

        # Store PEP knowledge base
        self._pep_kb = pep_kb
        self._last_search_count = 0  # Track search results count

        # Store tool instances for local execution
        self._local_tools: Dict[str, Any] = {}

        # Configure agent if config provided
        if config is not None:
            self.configure(config)
        else:
            # Set configuration from environment variables (all required)
            default_config = ReActAgentConfig()
            configure_from_env(default_config)
            self.configure(default_config)

        # Set up system prompt for LLM reasoning
        self._setup_prompt()

        # Register tools
        self._register_tools()

    def _setup_prompt(self):
        """Set up system prompt for LLM reasoning."""
        system_prompt = """You are a Python coding conventions expert assistant. Your task is to help users find relevant Python Enhancement Proposals (PEPs) that address their questions about Python coding conventions and best practices.

When a user asks a question:
1. Use the search_pep_knowledge_base tool to search for relevant PEPs
2. Analyze the search results to identify the most relevant PEPs
3. Provide a concise yet detailed summary that includes:
   - The most relevant PEP numbers and titles
   - Key recommendations from the PEPs
   - URLs to the PEP documents
   - Any important notes (e.g., if a PEP is superseded)
   - Specific guidance related to the user's question

Be thorough but concise. Focus on actionable recommendations based on official PEP guidelines."""

        self.config.configure_prompt_template([{"role": "system", "content": system_prompt}])
        self.configure(self.config)

    def _register_tools(self):
        """Register tools as abilities for the LLM to use."""
        # Create search PEP tool - need to bind to instance
        agent_instance = self

        async def search_pep_knowledge_base(query: str, code_snippet: str = "") -> str:
            """Search PEP knowledge base and return formatted results.

            Args:
                query: The search query about Python coding conventions or best practices
                code_snippet: Optional code snippet related to the query for better context

            Returns:
                Formatted search results with PEP information
            """
            # Build enhanced query
            enhanced_query = query
            if code_snippet:
                enhanced_query = f"{query}\n\nRelated code:\n{code_snippet}"

            # Get PEP knowledge base
            pep_kb = await agent_instance.get_pep_kb()

            # Search for relevant PEPs
            results = await pep_kb.search_peps(enhanced_query, top_k=10)

            # Store count for return value (using setattr to avoid linter warning)
            setattr(agent_instance, "_last_search_count", len(results))

            if not results:
                return f"No relevant PEP documents found for query: '{query}'. Consider rephrasing the query."

            # Format results for LLM
            formatted_results = []
            for i, result in enumerate(results, 1):
                metadata = result.metadata
                pep_num = metadata.get("pep_number", "N/A")
                pep_title = metadata.get("pep_title", "N/A")
                status = metadata.get("status", "N/A")
                score = result.score

                result_text = f"[{i}] PEP {pep_num}: {pep_title}\n"
                result_text += f"  Status: {status}\n"
                result_text += f"  Relevance Score: {score:.4f}\n"

                if metadata.get("python_version"):
                    result_text += f"  Python Version: {metadata.get('python_version')}\n"

                if metadata.get("superseded_by"):
                    result_text += f"  ⚠️  Superseded by PEP {metadata.get('superseded_by')}\n"

                if metadata.get("pep_url"):
                    result_text += f"  URL: {metadata.get('pep_url')}\n"

                # Include relevant text excerpt
                text_preview = result.text[:300] if result.text else ""
                if text_preview:
                    result_text += f"  Content excerpt: {text_preview}...\n"

                formatted_results.append(result_text)

            return "\n".join(formatted_results)

        # Create tool from function
        search_tool = tool(
            name="search_pep_knowledge_base",
            description="Search the Python PEP knowledge base for relevant PEP documents related to a query about Python coding conventions or best practices.",
            input_params={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The search query about Python coding conventions or best practices",
                    },
                    "code_snippet": {
                        "type": "string",
                        "description": "Optional code snippet related to the query for better context",
                    },
                },
                "required": ["query"],
            },
        )(search_pep_knowledge_base)

        # Store tool instance for local execution
        self._local_tools["search_pep_knowledge_base"] = search_tool

        # Register the tool card (not the tool instance)
        self.add_ability(search_tool.card)

    async def _execute_ability(self, tool_calls: Any, session: Session) -> list[tuple[Any, ToolMessage]]:
        """Override to handle local tool execution."""
        import json

        # Convert single tool_call to list
        if not isinstance(tool_calls, list):
            tool_calls = [tool_calls]

        results = []
        for tool_call in tool_calls:
            tool_name = tool_call.name if isinstance(tool_call, ToolCall) else tool_call.get("name", "")

            # Check if it's a local tool
            if tool_name in self._local_tools:
                local_tool = self._local_tools[tool_name]
                # Parse arguments
                if isinstance(tool_call, ToolCall):
                    tool_args = (
                        json.loads(tool_call.arguments) if isinstance(tool_call.arguments, str) else tool_call.arguments
                    )
                    tool_call_id = tool_call.id
                else:
                    tool_args = tool_call.get("arguments", {})
                    tool_call_id = tool_call.get("id", "")

                try:
                    result = await local_tool.invoke(tool_args)
                    tool_message = ToolMessage(content=str(result), tool_call_id=tool_call_id)
                    results.append((result, tool_message))
                except Exception as e:
                    error_msg = f"Local tool execution error: {str(e)}"
                    tool_message = ToolMessage(content=error_msg, tool_call_id=tool_call_id)
                    results.append((None, tool_message))
            else:
                # Fall back to parent implementation
                parent_results = await super()._execute_ability(tool_calls, session)
                results.extend(parent_results if isinstance(parent_results, list) else [parent_results])

        return results

    async def get_pep_kb(self) -> PEPKnowledgeBase:
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
        """Execute search for Python coding conventions using LLM reasoning.

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

        # Build user query for LLM
        user_query = query
        if code_snippet:
            user_query = f"{query}\n\nRelated code snippet:\n```python\n{code_snippet}\n```"

        if "qwen3" in self.config.model_name.casefold():
            user_query += " /no_think"

        # Use parent's ReAct loop - LLM will reason and use tools
        result = await super().invoke({"query": user_query}, session)

        # Extract results count if available (from tool execution)
        results_count = getattr(self, "_last_search_count", 0)

        return {
            "output": result.get("output", ""),
            "result_type": result.get("result_type", "answer"),
            "query": query,
            "results_count": results_count,
        }


__all__ = ["SearcherAgent"]
