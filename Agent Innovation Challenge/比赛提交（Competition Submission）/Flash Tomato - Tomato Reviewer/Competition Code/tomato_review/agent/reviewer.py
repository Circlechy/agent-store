"""ReviewerAgent: Agent for code review using pylint and PEP knowledge base.

This agent runs pylint on files, generates questions about errors, searches PEPs
via SearcherAgent, and generates comprehensive markdown reports.
Uses LLM reasoning through ReActAgent framework.
"""

import os
import re
import subprocess
import threading
from pathlib import Path
from typing import Any, Dict, List, Optional

from openjiuwen.core.common.exception.exception import JiuWenBaseException
from openjiuwen.core.common.schema.param import Param
from openjiuwen.core.foundation.llm import ToolCall, ToolMessage
from openjiuwen.core.foundation.tool import tool
from openjiuwen.core.session.session import Session
from openjiuwen.core.single_agent.agents.react_agent import ReActAgent, ReActAgentConfig
from openjiuwen.core.single_agent.schema.agent_card import AgentCard
from tqdm import tqdm

from tomato_review.agent.fixer import FixerAgent
from tomato_review.agent.searcher import SearcherAgent
from tomato_review.agent.utils import (
    backup_file,
    configure_from_env,
    extract_reasoning_content,
    normalize_filename,
    parse_pylint_output,
    setup_file_logger,
    setup_tomato_directories,
)


class ReviewerAgent(ReActAgent):
    """Agent for code review using pylint and PEP knowledge base.

    This agent:
    1. Runs pylint on a list of files one-by-one
    2. For each file's errors, prepares questions requiring PEP checks
    3. Dispatches questions to SearcherAgent to search PEPs
    4. Proposes changes for each error
    5. Generates full markdown report for each file
    """

    def __init__(
        self,
        card: Optional[AgentCard] = None,
        searcher_agent: Optional[SearcherAgent] = None,
        fixer_agent: Optional[FixerAgent] = None,
        config: Optional[ReActAgentConfig] = None,
        generate_fixed_files: bool = True,
        max_iterations: int = 10,
        pbar: Optional[tqdm] = None,
        lock: threading.Lock = threading.Lock(),
    ):
        """Initialize ReviewerAgent.

        Args:
            card: Agent card (will be created with defaults if not provided)
            searcher_agent: SearcherAgent instance (will be created if not provided)
            fixer_agent: FixerAgent instance (will be created if not provided)
            config: ReActAgentConfig (will be created with defaults if not provided)
            generate_fixed_files: Whether to automatically generate fixed files (default: True)
            max_iterations: Maximum iterations of file fixing (default: 10)
            pbar: Tqdm progress bar (default: None)
            lock: thread lock
        """
        # Create default card if not provided
        if card is None:
            card = AgentCard(
                name="reviewer_agent",
                description=(
                    "Agent for code review using pylint and PEP knowledge base. "
                    "Runs pylint on files, generates questions about errors, searches PEPs, "
                    "and generates comprehensive markdown reports."
                ),
                input_params=[
                    Param.array(
                        name="files",
                        description="List of file paths to review",
                        required=True,
                        items=Param.string(
                            name="file_path",
                            description="Path to a Python file to review",
                            required=True,
                        ),
                    ),
                ],
            )

        # Initialize parent
        super().__init__(card)

        # Progress tracking
        self.max_iterations = max_iterations
        self.pbar_unit = 1 / self.max_iterations
        self.pbar = pbar
        self.lock = lock

        # Set up tomato directories
        self._tomato_dirs = setup_tomato_directories()

        # Store searcher agent
        self._searcher_agent = searcher_agent
        if searcher_agent:
            searcher_agent.pbar = pbar
            searcher_agent.lock = lock

        # Store fixer agent
        self._fixer_agent = fixer_agent
        self._generate_fixed_files = generate_fixed_files
        if fixer_agent:
            fixer_agent.pbar = pbar
            fixer_agent.lock = lock

        # File loggers will be created per-file in invoke
        self._file_loggers = {}

        # Store tool instances for local execution
        self._local_tools: Dict[str, Any] = {}

        # OpenJiuwen doesn't support this yet
        # Add searcher agent as an ability if provided
        # if searcher_agent is not None:
        #     searcher_card = AgentCard(
        #         name="searcher_agent",
        #         description=searcher_agent.card.description,
        #         input_params=searcher_agent.card.input_params,
        #     )
        #     self.add_ability(searcher_card)

        # Configure agent if config provided
        if config is not None:
            self.config = config
            self.configure(config)
        else:
            # Set default configuration
            default_config = ReActAgentConfig()
            configure_from_env(default_config)
            self.config = default_config
            self.configure(default_config)

        # Set up system prompt and tools
        self._setup_prompt()
        self._register_tools()

    def _setup_prompt(self):
        """Set up system prompt for LLM reasoning."""
        system_prompt = """You are an expert Python code reviewer. Your task is to review Python files for code quality, style, and best practices.

When reviewing a file:
1. Use run_pylint tool to check for linting errors
2. For each error, use read_file_context to understand the code around the error
3. Use search_peps (via searcher_agent) to find relevant PEP guidelines for each error
4. Analyze the errors and PEP guidelines to propose fixes
5. Use generate_report to create a comprehensive markdown report

Your review should:
- Identify all code quality issues
- Reference relevant PEP guidelines
- Propose specific, actionable fixes
- Provide clear explanations for each recommendation

Be thorough, accurate, and focus on Python best practices."""

        self.config.configure_prompt_template([{"role": "system", "content": system_prompt}])
        self.configure(self.config)

    def _register_tools(self):
        """Register tools as abilities for the LLM to use."""
        agent_instance = self

        # Tool: Run pylint
        async def run_pylint(file_path: str) -> str:
            """Run pylint on a Python file and return parsed errors.

            Args:
                file_path: Path to the Python file to check

            Returns:
                JSON string with errors list, each error has: file, line, column, type, code, message, symbol
            """
            import json

            result = await agent_instance.run_pylint_tool(file_path)
            errors = result.get("errors", [])
            return json.dumps({"errors": errors, "count": len(errors)}, indent=2)

        # Tool: Read file context
        async def read_file_context(file_path: str, line_num: int, context_lines: int = 3) -> str:
            """Read file content with context around a specific line.

            Args:
                file_path: Path to the file
                line_num: Line number (1-indexed)
                context_lines: Number of lines before and after to include

            Returns:
                JSON string with context information
            """
            import json

            context = agent_instance.read_file_context_tool(file_path, line_num, context_lines)
            return json.dumps(context, indent=2)

        # Tool: Search PEPs (uses searcher agent)
        async def search_peps(question: str, code_snippet: str = "") -> str:
            """Search PEP knowledge base for relevant guidelines.

            Args:
                question: Question about Python coding conventions
                code_snippet: Optional code snippet for context

            Returns:
                Summary of relevant PEPs
            """
            searcher = agent_instance.get_searcher_agent()
            if searcher is None:
                searcher = SearcherAgent(pbar=self.pbar, lock=self.lock)
                setattr(agent_instance, "_searcher_agent", searcher)

            result = await searcher.invoke(
                {
                    "query": question,
                    "code_snippet": code_snippet,
                }
            )
            return result.get("output", "No results found.")

        # Create tools
        pylint_tool = tool(
            name="run_pylint",
            description="Run pylint static analysis on a Python file to find code quality issues, style violations, and best practice violations.",
            input_params={
                "type": "object",
                "properties": {"file_path": {"type": "string", "description": "Path to the Python file to analyze"}},
                "required": ["file_path"],
            },
        )(run_pylint)

        read_tool = tool(
            name="read_file_context",
            description="Read a file with context around a specific line number. Useful for understanding code context when analyzing errors.",
            input_params={
                "type": "object",
                "properties": {
                    "file_path": {"type": "string", "description": "Path to the file to read"},
                    "line_num": {"type": "integer", "description": "Line number (1-indexed) to get context around"},
                    "context_lines": {
                        "type": "integer",
                        "description": "Number of lines before and after to include (default: 3)",
                        "default": 3,
                    },
                },
                "required": ["file_path", "line_num"],
            },
        )(read_file_context)

        search_tool = tool(
            name="search_peps",
            description="Search Python Enhancement Proposals (PEPs) for guidelines related to a question about Python coding conventions or best practices.",
            input_params={
                "type": "object",
                "properties": {
                    "question": {
                        "type": "string",
                        "description": "Question about Python coding conventions or best practices",
                    },
                    "code_snippet": {"type": "string", "description": "Optional code snippet related to the question"},
                },
                "required": ["question"],
            },
        )(search_peps)

        # Store tool instances for local execution
        self._local_tools["run_pylint"] = pylint_tool
        self._local_tools["read_file_context"] = read_tool
        self._local_tools["search_peps"] = search_tool

        # Register tool cards
        self.add_ability(pylint_tool.card)
        self.add_ability(read_tool.card)
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

    def get_searcher_agent(self) -> Optional[SearcherAgent]:
        """Get searcher agent instance."""
        return self._searcher_agent

    async def run_pylint_tool(self, file_path: str) -> Dict[str, Any]:
        """Public method for running pylint (used by tools)."""
        return await self._run_pylint(file_path)

    def read_file_context_tool(self, file_path: str, line_num: int, context_lines: int = 3) -> Dict[str, Any]:
        """Public method for reading file context (used by tools)."""
        return self._read_file_context(file_path, line_num, context_lines)

    async def _run_pylint(self, file_path: str) -> Dict[str, Any]:
        """Run pylint on a file and return results.

        Args:
            file_path: Path to the Python file

        Returns:
            Dict with 'stdout', 'stderr', 'returncode', and parsed 'errors'
        """
        try:
            # Run pylint
            result = subprocess.run(
                ["pylint", file_path, "--output-format=text"],
                capture_output=True,
                text=True,
                timeout=60,
                check=False,  # Don't raise exception on non-zero exit
            )

            # Parse errors from output
            errors = parse_pylint_output(result.stdout)

            return {
                "stdout": result.stdout,
                "stderr": result.stderr,
                "returncode": result.returncode,
                "errors": errors,
            }
        except subprocess.TimeoutExpired:
            return {
                "stdout": "",
                "stderr": "pylint execution timed out",
                "returncode": -1,
                "errors": [],
            }
        except FileNotFoundError:
            return {
                "stdout": "",
                "stderr": "pylint not found. Please install pylint: pip install pylint",
                "returncode": -1,
                "errors": [],
            }
        except Exception as e:
            return {
                "stdout": "",
                "stderr": f"Error running pylint: {str(e)}",
                "returncode": -1,
                "errors": [],
            }

    def _generate_pep_questions(self, errors: List[Dict[str, str]]) -> List[Dict[str, str]]:
        """Generate questions about errors that require PEP checks.

        Args:
            errors: List of parsed pylint errors

        Returns:
            List of question dicts with 'error', 'question', 'code_snippet'
        """
        questions = []

        for error in errors:
            error_type = error.get("type", "")
            code = error.get("code", "")
            message = error.get("message", "")
            symbol = error.get("symbol", "")

            # Generate question based on error type and code
            question = None
            code_snippet = None

            # Type-related errors
            if error_type == "C" or "type" in message.lower() or "typing" in message.lower():
                question = f"What are the PEP guidelines for type hints related to: {message}?"
                code_snippet = f"Error: {message} (code: {code})"

            # Naming convention errors
            elif "naming" in message.lower() or "name" in message.lower():
                question = f"What are the PEP 8 naming conventions for: {message}?"
                code_snippet = f"Error: {message} (code: {code})"

            # Style errors
            elif error_type == "W" or "style" in message.lower():
                question = f"What are the PEP 8 style guidelines for: {message}?"
                code_snippet = f"Error: {message} (code: {code})"

            # Import errors
            elif "import" in message.lower():
                question = f"What are the PEP guidelines for import statements: {message}?"
                code_snippet = f"Error: {message} (code: {code})"

            # Docstring errors
            elif "docstring" in message.lower() or "doc" in message.lower():
                question = f"What are the PEP 257 docstring conventions for: {message}?"
                code_snippet = f"Error: {message} (code: {code})"

            # Generic question for other errors
            else:
                question = f"What are the Python PEP best practices for: {message}?"
                code_snippet = f"Error: {message} (code: {code}, symbol: {symbol})"

            if question:
                questions.append(
                    {
                        "error": error,
                        "question": question,
                        "code_snippet": code_snippet,
                    }
                )

        return questions

    async def _search_peps(self, question: str, file_path: str, code_snippet: Optional[str] = None) -> str:
        """Search PEPs using SearcherAgent.

        Args:
            question: Question to search
            file_path: File path
            code_snippet: Optional code snippet

        Returns:
            Search summary string
        """
        if self._searcher_agent is None:
            # Create searcher agent if not provided
            self._searcher_agent = SearcherAgent(pbar=self.pbar, lock=self.lock)

        # Call searcher agent
        inputs = {
            "query": question,
            "code_snippet": code_snippet or "",
        }

        try:
            result = await self._searcher_agent.invoke(inputs)
            output = result.get("output", "No results found.")
            # Check if the output indicates an error
            if "error" in output.lower() or "failed" in output.lower() or "exception" in output.lower():
                self._file_loggers[file_path].warning(
                    "PEP search may have failed: %s", "\n".join(output.splitlines()[:10])
                )
            return output
        except Exception as e:
            error_msg = f"Error searching PEPs: {str(e)}"
            self._file_loggers[file_path].error(error_msg)
            # Return error message that will be visible in the report
            return f"Error: {error_msg}. Please check your API configuration and network connection."

    def _read_file_context(self, file_path: str, line_num: int, context_lines: int = 3) -> Dict[str, Any]:
        """Read file content with context around a specific line.

        Args:
            file_path: Path to the file
            line_num: Line number (1-indexed)
            context_lines: Number of lines before and after to include

        Returns:
            Dict with 'original_line', 'context_before', 'context_after', 'full_context'
        """
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                lines = f.readlines()

            # Convert to 0-indexed
            line_idx = line_num - 1

            if line_idx < 0 or line_idx >= len(lines):
                return {
                    "original_line": "",
                    "context_before": [],
                    "context_after": [],
                    "full_context": "",
                }

            # Get context window
            start_idx = max(0, line_idx - context_lines)
            end_idx = min(len(lines), line_idx + context_lines + 1)

            context_before = lines[start_idx:line_idx]
            original_line = lines[line_idx] if line_idx < len(lines) else ""
            context_after = lines[line_idx + 1 : end_idx]

            # Build full context with line numbers
            full_context_lines = []
            for i in range(start_idx, end_idx):
                line_num_display = i + 1
                prefix = ">>>" if i == line_idx else "   "
                full_context_lines.append(f"{prefix} {line_num_display:4d} | {lines[i].rstrip()}")

            return {
                "original_line": original_line.rstrip(),
                "context_before": [line.rstrip() for line in context_before],
                "context_after": [line.rstrip() for line in context_after],
                "full_context": "\n".join(full_context_lines),
                "line_number": line_num,
            }
        except Exception as e:
            return {
                "original_line": "",
                "context_before": [],
                "context_after": [],
                "full_context": f"Error reading file: {e}",
            }

    def _generate_code_fix(self, error: Dict[str, str], original_line: str, pep_summary: str) -> str:
        """Generate a code fix suggestion based on error and PEP guidelines.

        Args:
            error: Error dict
            original_line: Original line of code
            pep_summary: PEP search summary

        Returns:
            Suggested fixed code line
        """
        message = error.get("message", "").lower()
        code = error.get("code", "")
        symbol = error.get("symbol", "")

        # Try to generate fix based on error type
        fixed_line = original_line

        # Naming convention fixes
        if "naming" in message or "invalid-name" in symbol:
            if "constant" in message and "uppercase" in message:
                # Convert constant to UPPER_CASE
                # Extract variable name and convert
                var_match = re.search(r'["\']?(\w+)["\']?', original_line)
                if var_match:
                    var_name = var_match.group(1)
                    upper_name = var_name.upper().replace("-", "_")
                    fixed_line = original_line.replace(var_name, upper_name)
            elif "function" in message and "snake_case" in message:
                # Convert function name to snake_case
                func_match = re.search(r"def\s+(\w+)", original_line)
                if func_match:
                    func_name = func_match.group(1)
                    snake_name = re.sub(r"(?<!^)(?=[A-Z])", "_", func_name).lower()
                    fixed_line = original_line.replace(func_name, snake_name)
            elif "class" in message and "pascalcase" in message:
                # Convert class name to PascalCase
                class_match = re.search(r"class\s+(\w+)", original_line)
                if class_match:
                    class_name = class_match.group(1)
                    # Convert snake_case or mixed to PascalCase
                    pascal_name = "".join(word.capitalize() for word in class_name.split("_"))
                    fixed_line = original_line.replace(class_name, pascal_name)

        # Type hint fixes
        elif "type" in message or code.startswith("C"):
            # This is more complex, would need AST parsing
            # For now, just indicate that type hints should be added
            pass

        # Import fixes
        elif "import" in message:
            # Would need to reorganize imports
            pass

        return fixed_line if fixed_line != original_line else original_line

    def _propose_changes(
        self, error: Dict[str, str], pep_summary: str, code_context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Propose changes for an error based on PEP summary.

        Args:
            error: Error dict
            pep_summary: PEP search summary
            code_context: Optional code context from file

        Returns:
            Dict with 'description', 'original_code', 'fixed_code', 'pep_reference'
        """
        error_type = error.get("type", "")
        message = error.get("message", "")
        line = error.get("line", 0)
        code = error.get("code", "")

        # Extract PEP numbers and URLs from summary
        pep_refs = []  # List of dicts with 'number' and 'url'
        if "PEP" in pep_summary:
            # Extract PEP numbers
            pep_matches = re.findall(r"PEP\s+(\d+)", pep_summary)
            # Extract URLs (looking for pep_url in the summary)
            url_matches = re.findall(r"URL:\s*(https?://[^\s]+)", pep_summary)

            # Match PEP numbers with URLs
            pep_dict = {}
            for pep_num in pep_matches:
                if pep_num not in pep_dict:
                    pep_dict[pep_num] = None

            # Try to match URLs with PEP numbers (URLs often contain PEP number)
            for url in url_matches:
                url_pep_match = re.search(r"pep-?(\d+)", url, re.IGNORECASE)
                if url_pep_match:
                    pep_num = url_pep_match.group(1)
                    if pep_num in pep_dict:
                        pep_dict[pep_num] = url

            # Also look for explicit URL patterns in the summary
            for pep_num in pep_dict.keys():
                # Look for URL on same line or nearby mentioning this PEP
                pattern = rf"PEP\s+{pep_num}[^\n]*\n[^\n]*URL:\s*(https?://[^\s]+)"
                match = re.search(pattern, pep_summary)
                if match and not pep_dict[pep_num]:
                    pep_dict[pep_num] = match.group(1)

            # Build list of PEP references
            for pep_num, url in pep_dict.items():
                if url:
                    pep_refs.append({"number": pep_num, "url": url})
                else:
                    # Default PEP URL format (zero-padded to 4 digits)
                    pep_num_int = int(pep_num)
                    pep_refs.append({"number": pep_num, "url": f"https://peps.python.org/pep-{pep_num_int:04d}/"})

        # Deduplicate by PEP number
        seen = set()
        unique_pep_refs = []
        for ref in pep_refs:
            if ref["number"] not in seen:
                seen.add(ref["number"])
                unique_pep_refs.append(ref)

        pep_ref = ""
        if unique_pep_refs:
            pep_nums = [ref["number"] for ref in unique_pep_refs]
            pep_ref = f" (see PEP {', '.join(pep_nums)})"

        # Get code context if available
        original_code = ""
        fixed_code = ""
        code_snippet = ""

        if code_context:
            original_code = code_context.get("original_line", "")
            code_snippet = code_context.get("full_context", "")
            fixed_code = self._generate_code_fix(error, original_code, pep_summary)

        # Generate description
        description = f"**Line {line}** ({code}): {message}\n\n"
        description += f"**Issue**: Based on PEP guidelines{pep_ref}, "

        # Add specific suggestions based on error type
        if error_type == "C":
            description += "ensure proper type hints are used."
        elif "naming" in message.lower():
            description += "follow PEP 8 naming conventions."
        elif error_type == "W":
            description += "follow PEP 8 style guidelines."
        elif "import" in message.lower():
            description += "organize imports according to PEP 8."
        elif "docstring" in message.lower():
            description += "add or fix docstrings according to PEP 257."
        else:
            description += "address the issue according to Python best practices."

        return {
            "description": description,
            "original_code": original_code,
            "fixed_code": fixed_code,
            "code_snippet": code_snippet,
            "pep_references": unique_pep_refs,  # List of dicts with 'number' and 'url'
            "line": line,
            "code": code,
            "message": message,
        }

    async def _review_file(self, file_path: str) -> Dict[str, Any]:
        """Review a single file using LLM reasoning.

        Args:
            file_path: Path to the file to review

        Returns:
            Dict with 'file_path', 'errors', 'questions', 'pep_results', 'proposed_changes', 'report'
        """
        # Check if file exists
        if not Path(file_path).exists():
            return {
                "file_path": file_path,
                "errors": [],
                "questions": [],
                "pep_results": {},
                "proposed_changes": [],
                "report": f"# Code Review Report: {file_path}\n\n**Error**: File not found.",
            }

        # Use LLM to review the file - LLM will use tools to:
        # 1. Run pylint
        # 2. Read file context for errors
        # 3. Search PEPs for guidelines
        # 4. Generate recommendations

        user_query = f"""Please review the Python file: {file_path}

Your task:
1. Use run_pylint tool to check for linting errors
2. For each error found, use read_file_context to understand the code around the error
3. Use search_peps to find relevant PEP guidelines for each error
4. Analyze the errors and PEP guidelines
5. Provide a comprehensive review with:
   - List of all errors found
   - For each error: explanation, relevant PEP guidelines, and proposed fix
   - A summary of recommendations

Format your response as a detailed markdown report."""

        try:
            # Use parent's ReAct loop - LLM will reason and use tools
            llm_result = await super().invoke({"query": user_query}, session=None)
            llm_output, llm_reasoning = extract_reasoning_content(llm_result.get("output", ""))

            # Run pylint ourselves to get structured error data (for compatibility with existing code)
            pylint_result = await self._run_pylint(file_path)
            errors = pylint_result.get("errors", [])

            # Generate a structured report from LLM output
            no_issues = "\n\n✅ No issues found by pylint." if not errors else ""
            sep = "\n" + "-" * 80 + "\n"
            report = f"# Code Review Report:\n`{file_path}`{no_issues}\n\n{llm_output}"

            if not errors:
                return {
                    "file_path": file_path,
                    "errors": [],
                    "questions": [],
                    "pep_results": {},
                    "proposed_changes": [],
                    "report": report,
                }

            # Extract proposed changes from LLM output (basic parsing)
            # In a full implementation, the LLM would structure this better or we'd parse tool call results
            proposed_changes = self._extract_changes_from_llm_output(llm_output, errors)

            # Extract PEP references from LLM output
            pep_refs = self._extract_pep_references_from_llm_output(llm_output)
            if pep_refs:
                report += f"\n{sep}\n## The following PEPs were referenced in this review:\n"
                for ref in sorted(pep_refs, key=lambda x: int(x["number"])):
                    report += f"- [PEP {ref['number']}]({ref['url']})\n"

            if llm_reasoning:
                report += "\n" + sep + f"\n**Tomato Reviewer's Thinking Process:**\n{llm_reasoning}\n" + sep

            return {
                "file_path": file_path,
                "errors": errors,
                "questions": [],  # LLM handles this internally
                "pep_results": {},  # LLM handles this internally
                "proposed_changes": proposed_changes,
                "pep_references": pep_refs,
                "report": report,
            }
        except JiuWenBaseException:
            raise
        except Exception as e:
            self._file_loggers[file_path].error("LLM review failed for %s: %s", file_path, e)
            # Fallback to rule-based review
            return await self._review_file_rule_based(file_path)

    def _extract_changes_from_llm_output(self, llm_output: str, errors: List[Dict[str, str]]) -> List[Dict[str, Any]]:
        """Extract proposed changes from LLM output.

        This is a basic parser - in a full implementation, the LLM would
        return structured data or we'd use a more sophisticated extraction.
        """
        changes = []
        # Basic extraction - look for error mentions and line numbers
        for error in errors:
            line_num = error.get("line", 0)
            code = error.get("code", "")
            message = error.get("message", "")

            # Check if LLM mentioned this error
            if str(line_num) in llm_output or code in llm_output:
                changes.append(
                    {
                        "line": line_num,
                        "code": code,
                        "message": message,
                        "description": f"LLM recommendation for {code}: {message}",
                        "original_code": "",
                        "fixed_code": "",
                        "code_snippet": "",
                        "pep_references": [],
                    }
                )
        return changes

    def _extract_pep_references_from_llm_output(self, llm_output: str) -> List[Dict[str, str]]:
        """Extract PEP references from LLM output."""
        pep_refs = []
        # Look for PEP references in the format: PEP 8, PEP 257, etc.
        pep_pattern = r"PEP\s+(\d+)"
        for match in re.finditer(pep_pattern, llm_output, re.IGNORECASE):
            pep_num = match.group(1)
            # Try to find URL in nearby text
            url = f"https://peps.python.org/pep-{pep_num.zfill(4)}/"
            pep_refs.append({"number": pep_num, "url": url})

        # Deduplicate
        seen = set()
        unique_refs = []
        for ref in pep_refs:
            if ref["number"] not in seen:
                seen.add(ref["number"])
                unique_refs.append(ref)

        return unique_refs

    async def _review_file_rule_based(self, file_path: str) -> Dict[str, Any]:
        """Fallback rule-based review (original implementation)."""
        # Check if file exists
        if not Path(file_path).exists():
            return {
                "file_path": file_path,
                "errors": [],
                "questions": [],
                "pep_results": {},
                "proposed_changes": [],
                "report": f"# Code Review Report: {file_path}\n\n**Error**: File not found.",
            }

        # Run pylint
        pylint_result = await self._run_pylint(file_path)
        errors = pylint_result.get("errors", [])

        if not errors:
            return {
                "file_path": file_path,
                "errors": [],
                "questions": [],
                "pep_results": {},
                "proposed_changes": [],
                "report": f"# Code Review Report: {file_path}\n\n✅ No issues found by pylint.",
            }

        # Read file content for context
        file_content = {}
        for error in errors:
            line_num = error.get("line", 0)
            if line_num > 0:
                file_content[line_num] = self._read_file_context(file_path, line_num, context_lines=3)

        # Generate questions
        questions = self._generate_pep_questions(errors)

        # Search PEPs for each question
        pep_results = {}
        pep_search_errors = []
        for q in questions:
            question = q["question"]
            error = q["error"]
            line_num = error.get("line", 0)

            # Include actual code context in search
            code_context = file_content.get(line_num, {})
            code_snippet_for_search = code_context.get("full_context", q.get("code_snippet", ""))

            try:
                pep_summary = await self._search_peps(question, file_path, code_snippet_for_search)
                pep_results[question] = pep_summary
                # Track if search failed
                if pep_summary and ("Error:" in pep_summary or "error" in pep_summary.lower()):
                    pep_search_errors.append(question)
            except JiuWenBaseException:
                raise
            except Exception as e:
                # PEP search failed - log and continue, but mark as error
                error_msg = f"PEP search failed for question '{question}': {str(e)}"
                self._file_loggers[file_path].error(error_msg)
                pep_results[question] = f"Error: {error_msg}"
                pep_search_errors.append(question)

        # If all PEP searches failed, raise an exception to stop processing
        if pep_search_errors and len(pep_search_errors) == len(questions):
            raise RuntimeError(
                f"All PEP searches failed. This usually indicates a configuration error. "
                f"Please check your API keys and knowledge base configuration. "
                f"First error: {pep_results.get(questions[0]['question'], 'Unknown error')}"
            )

        # Propose changes with code context
        proposed_changes = []
        all_pep_refs = []  # Collect all PEP references for deduplication

        for q in questions:
            error = q["error"]
            question = q["question"]
            line_num = error.get("line", 0)
            pep_summary = pep_results.get(question, "")
            code_context = file_content.get(line_num, {})

            change = self._propose_changes(error, pep_summary, code_context)
            proposed_changes.append(change)
            # Collect PEP references
            if change.get("pep_references"):
                all_pep_refs.extend(change["pep_references"])

        # Deduplicate all PEP references across all changes
        seen_peps = set()
        unique_all_pep_refs = []
        for ref in all_pep_refs:
            if ref["number"] not in seen_peps:
                seen_peps.add(ref["number"])
                unique_all_pep_refs.append(ref)

        # Generate markdown report
        report = self._generate_markdown_report(
            file_path, errors, questions, pep_results, proposed_changes, unique_all_pep_refs
        )

        return {
            "file_path": file_path,
            "errors": errors,
            "questions": questions,
            "pep_results": pep_results,
            "proposed_changes": proposed_changes,
            "report": report,
            "pep_references": unique_all_pep_refs,
        }

    def _generate_markdown_report(
        self,
        file_path: str,
        errors: List[Dict[str, str]],
        questions: List[Dict[str, str]],
        pep_results: Dict[str, str],
        proposed_changes: List[Dict[str, Any]],
        all_pep_refs: List[Dict[str, str]],
    ) -> str:
        """Generate markdown report for a file.

        Args:
            file_path: File path
            errors: List of errors
            questions: List of questions
            pep_results: Dict mapping questions to PEP summaries
            proposed_changes: List of proposed changes

        Returns:
            Markdown report string
        """
        report_parts = [
            f"# Code Review Report:\n`{file_path}`",
            "",
            "## Summary",
            "",
            f"- **Total Issues**: {len(errors)}",
            f"- **Issues Requiring PEP Check**: {len(questions)}",
            "",
            "## Issues Found",
            "",
        ]

        # Add error list
        for i, error in enumerate(errors, 1):
            report_parts.append(f"### Issue {i}")
            report_parts.append(f"- **Line**: {error.get('line', 'N/A')}")
            report_parts.append(f"- **Type**: {error.get('type', 'N/A')}")
            report_parts.append(f"- **Code**: {error.get('code', 'N/A')}")
            report_parts.append(f"- **Message**: {error.get('message', 'N/A')}")
            report_parts.append(f"- **Symbol**: {error.get('symbol', 'N/A')}")
            report_parts.append("")

        # Add PEP-based recommendations with code fixes
        if questions:
            report_parts.append("## PEP-Based Recommendations")
            report_parts.append("")

            for i, change in enumerate(proposed_changes, 1):
                report_parts.append(f"### Recommendation {i}")
                report_parts.append(change.get("description", ""))
                report_parts.append("")

                # Add code snippet with context
                if change.get("code_snippet"):
                    report_parts.append("**Code Context:**")
                    report_parts.append("```python")
                    report_parts.append(change["code_snippet"])
                    report_parts.append("```")
                    report_parts.append("")

                # Add before/after if we have a fix
                if change.get("original_code") and change.get("fixed_code"):
                    if change["original_code"] != change["fixed_code"]:
                        report_parts.append("**Suggested Fix:**")
                        report_parts.append("")
                        report_parts.append("**Before:**")
                        report_parts.append("```python")
                        report_parts.append(change["original_code"])
                        report_parts.append("```")
                        report_parts.append("")
                        report_parts.append("**After:**")
                        report_parts.append("```python")
                        report_parts.append(change["fixed_code"])
                        report_parts.append("```")
                        report_parts.append("")
                    else:
                        report_parts.append("**Note:** Manual fix required based on PEP guidelines.")
                        report_parts.append("")

                # Add PEP references for this change
                if change.get("pep_references"):
                    report_parts.append("**PEP References:**")
                    for ref in change["pep_references"]:
                        report_parts.append(f"- [PEP {ref['number']}]({ref['url']})")
                    report_parts.append("")

                report_parts.append("---")
                report_parts.append("")

        # Add consolidated PEP references section
        if all_pep_refs:
            report_parts.append("## PEP References")
            report_parts.append("")
            report_parts.append("The following PEPs were referenced in this review:")
            report_parts.append("")
            for ref in sorted(all_pep_refs, key=lambda x: int(x["number"])):
                report_parts.append(f"- [PEP {ref['number']}]({ref['url']})")
            report_parts.append("")

        return "\n".join(report_parts)

    async def _review_fix_cycle(
        self, original_file_path: str, initial_review: Dict[str, Any], file_logger: Optional[Any] = None
    ) -> Optional[str]:
        """Finite State Machine: Review → Fix → Review → Fix → ... until no errors.

        States:
        - REVIEW: Review file and find errors
        - FIX: Apply fixes and generate fixed file

        Args:
            original_file_path: Path to the original source file
            initial_review: Initial review results with proposed changes

        Returns:
            Path to final fixed file, or None if fixing failed
        """
        if self._fixer_agent is None:
            self._fixer_agent = FixerAgent(pbar=self.pbar, lock=self.lock)

        iteration = 0
        current_file_path = original_file_path
        current_proposed_changes = initial_review.get("proposed_changes", [])
        cycle_history = []  # Track each cycle
        final_fixed_file_path = None
        last_review_errors = initial_review.get("errors", [])

        while iteration < self.max_iterations:
            with self.lock:
                self.pbar.update(self.pbar_unit)
            iteration += 1
            state = "FIX" if iteration > 1 else "INITIAL_FIX"

            # State: FIX - Apply fixes to current file
            try:
                fix_result = await self._fixer_agent.invoke(
                    {
                        "file_path": current_file_path,
                        "proposed_changes": current_proposed_changes,
                    }
                )

                if not fix_result.get("success"):
                    if file_logger:
                        file_logger.warning(
                            "Fixer failed in iteration %d: %s", iteration, fix_result.get("message", "")
                        )
                    break

                # File is modified in place, so fixed_file_path_str is the same as current_file_path
                fixed_file_path_str = current_file_path
                final_fixed_file_path = fixed_file_path_str

                cycle_history.append(
                    {
                        "iteration": iteration,
                        "state": state,
                        "file_path": fixed_file_path_str,
                        "changes_applied": fix_result.get("changes_applied", 0),
                        "ruff_fixes": fix_result.get("ruff_fixes", 0),
                    }
                )

                if file_logger:
                    file_logger.info(
                        "Iteration %d: Applied %d changes, ruff fixed %d issues",
                        iteration,
                        fix_result.get("changes_applied", 0),
                        fix_result.get("ruff_fixes", 0),
                    )

                # State: REVIEW - Review the fixed file
                try:
                    fixed_review = await self._review_file(fixed_file_path_str)
                except Exception as e:
                    # If review fails (e.g., PEP search error), stop the cycle
                    if file_logger:
                        file_logger.error("Review failed in iteration %d: %s", iteration, e)
                    break

                remaining_errors = fixed_review.get("errors", [])
                last_review_errors = remaining_errors

                cycle_history[-1]["errors_after_fix"] = len(remaining_errors)

                # Check if PEP search failed (indicated by error messages in proposed changes)
                proposed_changes = fixed_review.get("proposed_changes", [])
                pep_search_failed = False
                for change in proposed_changes:
                    description = change.get("description", "")
                    if "Error:" in description or "error" in description.lower():
                        # Check if it's a PEP search error
                        if "PEP" in description and ("error" in description.lower() or "failed" in description.lower()):
                            pep_search_failed = True
                            break

                if pep_search_failed:
                    if file_logger:
                        file_logger.warning("PEP search failed, stopping fix cycle")
                    break

                # If no errors remain, we're done
                if not remaining_errors:
                    if file_logger:
                        file_logger.info("File fixed successfully after %d iteration(s)", iteration)
                    break

                # Filter fixable errors for next iteration
                fixable_errors = [
                    e
                    for e in remaining_errors
                    if any(
                        keyword in e.get("message", "").lower() or keyword in e.get("symbol", "").lower()
                        for keyword in [
                            "naming",
                            "invalid-name",
                            "docstring",
                            "missing",
                            "trailing",
                            "whitespace",
                            "import",
                        ]
                    )
                ]

                if not fixable_errors:
                    # No more fixable errors
                    if file_logger:
                        file_logger.info("No more fixable errors after %d iteration(s)", iteration)
                    break

                # Prepare for next iteration: use fixed file and new proposed changes
                current_file_path = fixed_file_path_str
                current_proposed_changes = fixed_review.get("proposed_changes", [])

                if not current_proposed_changes:
                    # No proposed changes, can't continue
                    break

            except Exception as e:
                if file_logger:
                    file_logger.error("Error in review-fix cycle iteration %d: %s", iteration, e)
                break

        if iteration < self.max_iterations:
            with self.lock:
                self.pbar.update(1 - iteration * self.pbar_unit)

        # Store cycle history in the review for debugging
        initial_review["fix_cycle_history"] = cycle_history
        initial_review["fix_iterations"] = iteration
        initial_review["final_errors"] = len(last_review_errors)

        return final_fixed_file_path

    async def invoke(
        self,
        inputs: Any,
        session: Optional[Any] = None,
    ) -> Dict[str, Any]:
        """Execute code review on list of files using LLM reasoning.

        Args:
            inputs: Input dict with 'files' (list of file paths), or list of file paths
            session: Session object (optional)

        Returns:
            Dict with 'output' (combined reports), 'result_type', and 'reports' (per-file)
        """
        # Normalize inputs
        if isinstance(inputs, dict):
            files = inputs.get("files") or inputs.get("file_list", [])
        elif isinstance(inputs, list):
            files = inputs
        else:
            raise ValueError("Input must be dict with 'files' or list of file paths")

        if not files:
            raise ValueError("Files list is required and cannot be empty")

        # For now, use LLM to review each file individually
        # The LLM will use tools to: run pylint, read context, search PEPs, and generate recommendations
        # We still handle file processing, backup, and report generation in the orchestration layer
        # but let LLM make the review decisions

        # Process files in parallel
        async def process_file(file_path: str) -> Dict[str, Any]:
            """Process a single file: backup, review, generate report, and optionally fix."""

            # Set up file logger for this file
            normalized_name = normalize_filename(file_path)
            log_file_path = self._tomato_dirs["logs"] / Path(f"{file_path}.log").relative_to(Path.cwd())
            os.makedirs(os.path.dirname(log_file_path), exist_ok=True)
            file_logger = setup_file_logger(log_file_path, f"tomato_review_{normalized_name}")
            self._file_loggers[file_path] = file_logger

            # Backup original file
            try:
                backup_path = backup_file(file_path, self._tomato_dirs["backup"])
            except Exception as e:
                file_logger.error("Failed to backup file %s: %s", file_path, e)
                backup_path = None

            file_logger.info("Starting review for file: %s", file_path)
            if backup_path:
                file_logger.info("Backed up to: %s", backup_path)

            # Review file
            file_report = await self._review_file(file_path)
            file_logger.info("Review completed. Found %d errors", len(file_report.get("errors", [])))

            report_file_path = None

            # Generate individual markdown report file
            if file_report.get("report"):
                try:
                    # Use normalized filename for review
                    review_filename = f"{file_path}-report.md"
                    report_file_path = self._tomato_dirs["reviews"] / Path(review_filename).relative_to(Path.cwd())
                    os.makedirs(os.path.dirname(report_file_path), exist_ok=True)

                    with open(report_file_path, "w", encoding="utf-8") as f:
                        f.write(file_report["report"])
                    file_logger.info("Review report written to: %s", report_file_path)
                except Exception as e:
                    file_logger.error("Failed to write report file %s: %s", report_file_path, e)
                    report_file_path = None

            # Generate fixed file using FSM (Review → Fix → Review → ...)
            # This will modify the file in place
            if self._generate_fixed_files and file_report.get("proposed_changes"):
                file_logger.info(
                    "Starting fix cycle with %d proposed changes", len(file_report.get("proposed_changes", []))
                )
                fixed_file_path = await self._review_fix_cycle(file_path, file_report, file_logger)
                if fixed_file_path:
                    file_report["fixed_file_path"] = fixed_file_path
                    file_logger.info("Fix cycle completed. Final file: %s", fixed_file_path)
                else:
                    file_logger.warning("Fix cycle did not produce a fixed file")

            file_logger.info("Processing completed for file: %s", file_path)

            return {
                "file_report": file_report,
                "report_file_path": str(report_file_path) if report_file_path else None,
                "fixed_file_path": file_path if self._generate_fixed_files else None,  # File is modified in place
            }

        # Process all files in parallel
        import asyncio

        results = await asyncio.gather(*[process_file(f) for f in files], return_exceptions=True)

        # Collect results
        reports = []
        report_files = []
        fixed_files = []

        for i, result in enumerate(results):
            if isinstance(result, Exception):
                self._file_loggers[files[i]].error("Error processing file %s: %s", files[i], result)
                continue

            reports.append(result["file_report"])
            if result["report_file_path"]:
                report_files.append(result["report_file_path"])
            if result["fixed_file_path"]:
                fixed_files.append(result["fixed_file_path"])

        # Combine all reports for summary output
        combined_report_parts = [
            "# Code Review Report - Multiple Files",
            "",
            f"**Total Files Reviewed**: {len(files)}",
            "",
            "## Generated Reports",
            "",
            "Individual markdown reports have been generated in `tomato/reviews/`:",
            "",
        ]

        for report_file in report_files:
            report_path = Path(report_file)
            combined_report_parts.append(f"- [{report_path.name}]({report_file})")

        combined_report_parts.append("")

        # Add fixed files section if any were modified
        if fixed_files:
            combined_report_parts.append("## Modified Files")
            combined_report_parts.append("")
            combined_report_parts.append(
                "The following files have been modified in place (backups stored in `tomato/backup`):"
            )
            combined_report_parts.append("")
            for fixed_file in fixed_files:
                fixed_path = Path(fixed_file)
                combined_report_parts.append(f"- {fixed_path}")
            combined_report_parts.append("")

        combined_report_parts.append("---")
        combined_report_parts.append("")

        # Add summary of each file
        for report in reports:
            file_path = report.get("file_path", "Unknown")
            error_count = len(report.get("errors", []))
            combined_report_parts.append(f"### {Path(file_path).name}")
            combined_report_parts.append(f"- **Issues Found**: {error_count}")
            if report.get("pep_references"):
                pep_count = len(report["pep_references"])
                combined_report_parts.append(f"- **PEPs Referenced**: {pep_count}")
            combined_report_parts.append("")

        combined_report = "\n".join(combined_report_parts)

        return {
            "output": combined_report,
            "result_type": "answer",
            "files_reviewed": len(files),
            "reports": reports,
            "report_files": report_files,  # List of generated report file paths
            "fixed_files": fixed_files,  # List of generated fixed file paths
        }


__all__ = ["ReviewerAgent"]
