"""FixerAgent: Agent for generating fixed versions of code files.

This agent takes review results and applies fixes to generate corrected versions
of Python files based on PEP guidelines.
Uses LLM reasoning through ReActAgent framework.
"""

import re
import subprocess
import sys
import threading
from pathlib import Path
from typing import Any, Dict, List, Optional

from openjiuwen.core.common.schema.param import Param
from openjiuwen.core.foundation.llm import ToolCall, ToolMessage
from openjiuwen.core.foundation.tool import tool
from openjiuwen.core.session.session import Session
from openjiuwen.core.single_agent.agents.react_agent import ReActAgent, ReActAgentConfig
from openjiuwen.core.single_agent.schema.agent_card import AgentCard
from tqdm import tqdm

from tomato_review.agent.utils import configure_from_env, parse_pylint_output


class FixerAgent(ReActAgent):
    """Agent for generating fixed versions of code files.

    This agent takes review results from ReviewerAgent and applies fixes to
    generate corrected versions of Python files based on PEP guidelines.
    """

    def __init__(
        self,
        card: Optional[AgentCard] = None,
        config: Optional[ReActAgentConfig] = None,
        pbar: Optional[tqdm] = None,
        lock: threading.Lock = threading.Lock(),
    ):
        """Initialize FixerAgent.

        Args:
            card: Agent card (will be created with defaults if not provided)
            config: ReActAgentConfig (will be created with defaults if not provided)
            pbar: Tqdm progress bar (default: None)
            lock: thread lock
        """
        # Create default card if not provided
        if card is None:
            card = AgentCard(
                name="fixer_agent",
                description=(
                    "Agent for generating fixed versions of code files. "
                    "Takes review results and applies fixes to generate corrected "
                    "versions based on PEP guidelines."
                ),
                input_params=[
                    Param.string(
                        name="file_path",
                        description="Path to the source file to fix",
                        required=True,
                    ),
                    Param.object(
                        name="review_results",
                        description="Review results from ReviewerAgent containing proposed changes",
                        required=True,
                        properties=[
                            Param.array(
                                name="proposed_changes",
                                description="List of proposed changes with fixes",
                                required=True,
                                items=Param.object(
                                    name="change",
                                    description="A proposed change",
                                    required=True,
                                    properties=[
                                        Param.integer(name="line", description="Line number", required=True),
                                        Param.string(
                                            name="original_code", description="Original code line", required=False
                                        ),
                                        Param.string(name="fixed_code", description="Fixed code line", required=False),
                                        Param.string(name="code", description="Error code", required=False),
                                        Param.string(name="message", description="Error message", required=False),
                                    ],
                                ),
                            ),
                        ],
                    ),
                ],
            )

        # Initialize parent
        super().__init__(card)

        # Progress tracking
        self.pbar = pbar
        self.lock = lock

        # Store tool instances for local execution
        self._local_tools: Dict[str, Any] = {}

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
        system_prompt = """You are an expert Python code fixer. Your task is to apply fixes to Python code based on review recommendations from the ReviewerAgent and PEP guidelines from the SearcherAgent.

When fixing code:
1. Use read_file to read the current file content
2. Use read_file_context to understand code around specific lines that need fixing
3. Carefully analyze the proposed changes provided by the reviewer, which include:
   - Error descriptions with line numbers and error codes
   - PEP references and guidelines from the searcher
   - Code context and suggested fixes
4. Apply fixes systematically, addressing each issue:
   - Follow the PEP guidelines referenced in the proposed changes
   - Preserve code logic and functionality
   - Fix naming conventions, docstrings, imports, and style issues
   - Ensure fixes align with the reviewer's recommendations
5. Use write_file to write the fixed code
6. Use run_pylint to verify the fixes resolved the issues
7. Use run_ruff_format and run_ruff_check_fix to ensure proper formatting

Your fixes should:
- Follow PEP 8 and other relevant PEP guidelines as specified in the review
- Maintain code functionality - never break working code
- Improve code quality and readability
- Address all identified issues systematically
- Respect the reviewer's instructions and PEP context provided

Be precise and careful - don't break working code. When in doubt, preserve the original logic while fixing style and convention issues."""

        self.config.configure_prompt_template([{"role": "system", "content": system_prompt}])
        self.configure(self.config)

    def _register_tools(self):
        """Register tools as abilities for the LLM to use."""
        agent_instance = self

        # Tool: Read file
        async def read_file(file_path: str) -> str:
            """Read the contents of a file.

            Args:
                file_path: Path to the file to read

            Returns:
                File contents as string
            """
            with open(file_path, "r", encoding="utf-8") as f:
                return f.read()

        # Tool: Read file context
        async def read_file_context(file_path: str, line_num: int, context_lines: int = 5) -> str:
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

        # Tool: Write file
        async def write_file(file_path: str, content: str) -> str:
            """Write content to a file.

            Args:
                file_path: Path to the file to write
                content: Content to write

            Returns:
                Success message
            """
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(content)
            return f"Successfully wrote {len(content)} characters to {file_path}"

        # Tool: Run pylint
        async def run_pylint(file_path: str) -> str:
            """Run pylint on a file to check for remaining errors.

            Args:
                file_path: Path to the file to check

            Returns:
                JSON string with errors
            """
            import json

            result = await agent_instance.run_pylint_tool(file_path)
            errors = result.get("errors", [])
            return json.dumps({"errors": errors, "count": len(errors)}, indent=2)

        # Tool: Run ruff format
        async def run_ruff_format(file_path: str) -> str:
            """Format a file using ruff format.

            Args:
                file_path: Path to the file to format

            Returns:
                Success message
            """
            result = await agent_instance.run_ruff_format_tool(file_path)
            if result.get("success"):
                return "File formatted successfully"
            return f"Formatting failed: {result.get('stderr', 'Unknown error')}"

        # Tool: Run ruff check --fix
        async def run_ruff_check_fix(file_path: str) -> str:
            """Auto-fix issues in a file using ruff check --fix.

            Args:
                file_path: Path to the file to fix

            Returns:
                Message with number of fixes applied
            """
            result = await agent_instance.run_ruff_check_fix_tool(file_path)
            fixed_count = result.get("fixed_count", 0)
            return f"Ruff auto-fixed {fixed_count} issue(s)"

        # Tool: Run Python code
        async def run_code(code_or_file: str, is_file: bool = True) -> str:
            """Execute Python code or run a Python file using the current Python environment.

            Args:
                code_or_file: Either a file path to execute, or Python code as a string
                is_file: If True, treat code_or_file as a file path. If False, treat as code string.

            Returns:
                JSON string with execution results including stdout, stderr, returncode, and success status
            """
            import json

            result = await agent_instance.run_code_tool(code_or_file, is_file)
            return json.dumps(result, indent=2)

        # Create and register tools
        read_tool = tool(
            name="read_file",
            description="Read the contents of a Python file.",
            input_params={
                "type": "object",
                "properties": {"file_path": {"type": "string", "description": "Path to the file to read"}},
                "required": ["file_path"],
            },
        )(read_file)

        read_context_tool = tool(
            name="read_file_context",
            description="Read a file with context around a specific line number. Useful for understanding code context when applying fixes.",
            input_params={
                "type": "object",
                "properties": {
                    "file_path": {"type": "string", "description": "Path to the file to read"},
                    "line_num": {"type": "integer", "description": "Line number (1-indexed) to get context around"},
                    "context_lines": {
                        "type": "integer",
                        "description": "Number of lines before and after to include (default: 5)",
                        "default": 5,
                    },
                },
                "required": ["file_path", "line_num"],
            },
        )(read_file_context)

        write_tool = tool(
            name="write_file",
            description="Write content to a Python file. Use this to apply fixes.",
            input_params={
                "type": "object",
                "properties": {
                    "file_path": {"type": "string", "description": "Path to the file to write"},
                    "content": {"type": "string", "description": "Content to write to the file"},
                },
                "required": ["file_path", "content"],
            },
        )(write_file)

        pylint_tool = tool(
            name="run_pylint",
            description="Run pylint to check for remaining errors after applying fixes.",
            input_params={
                "type": "object",
                "properties": {"file_path": {"type": "string", "description": "Path to the file to check"}},
                "required": ["file_path"],
            },
        )(run_pylint)

        ruff_format_tool = tool(
            name="run_ruff_format",
            description="Format a Python file using ruff format.",
            input_params={
                "type": "object",
                "properties": {"file_path": {"type": "string", "description": "Path to the file to format"}},
                "required": ["file_path"],
            },
        )(run_ruff_format)

        ruff_fix_tool = tool(
            name="run_ruff_check_fix",
            description="Auto-fix issues in a Python file using ruff check --fix.",
            input_params={
                "type": "object",
                "properties": {"file_path": {"type": "string", "description": "Path to the file to fix"}},
                "required": ["file_path"],
            },
        )(run_ruff_check_fix)

        run_code_tool = tool(
            name="run_code",
            description="Execute Python code or run a Python file using the current Python environment. Use this to test if your fixes work correctly by running the code.",
            input_params={
                "type": "object",
                "properties": {
                    "code_or_file": {
                        "type": "string",
                        "description": "Either a file path to execute, or Python code as a string",
                    },
                    "is_file": {
                        "type": "boolean",
                        "description": "If true, treat code_or_file as a file path. If false, treat as code string (default: true)",
                        "default": True,
                    },
                },
                "required": ["code_or_file"],
            },
        )(run_code)

        # Store tool instances for local execution
        self._local_tools["read_file"] = read_tool
        self._local_tools["read_file_context"] = read_context_tool
        self._local_tools["write_file"] = write_tool
        self._local_tools["run_pylint"] = pylint_tool
        self._local_tools["run_ruff_format"] = ruff_format_tool
        self._local_tools["run_ruff_check_fix"] = ruff_fix_tool
        self._local_tools["run_code"] = run_code_tool

        # Register tool cards
        self.add_ability(read_tool.card)
        self.add_ability(read_context_tool.card)
        self.add_ability(write_tool.card)
        self.add_ability(pylint_tool.card)
        self.add_ability(ruff_format_tool.card)
        self.add_ability(ruff_fix_tool.card)
        self.add_ability(run_code_tool.card)

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

    async def run_pylint_tool(self, file_path: str) -> Dict[str, Any]:
        """Public method for running pylint (used by tools)."""
        return await self._run_pylint(file_path)

    async def run_ruff_format_tool(self, file_path: str) -> Dict[str, Any]:
        """Public method for running ruff format (used by tools)."""
        return await self._run_ruff_format(file_path)

    async def run_ruff_check_fix_tool(self, file_path: str) -> Dict[str, Any]:
        """Public method for running ruff check --fix (used by tools)."""
        return await self._run_ruff_check_fix(file_path)

    def read_file_context_tool(self, file_path: str, line_num: int, context_lines: int = 5) -> Dict[str, Any]:
        """Public method for reading file context (used by tools)."""
        return self._read_file_context(file_path, line_num, context_lines)

    async def run_code_tool(self, code_or_file: str, is_file: bool = True) -> Dict[str, Any]:
        """Public method for running Python code (used by tools)."""
        return await self._run_code(code_or_file, is_file)

    def _read_file_context(self, file_path: str, line_num: int, context_lines: int = 5) -> Dict[str, Any]:
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

    async def _run_code(self, code_or_file: str, is_file: bool = True) -> Dict[str, Any]:
        """Execute Python code or run a Python file using the current Python environment.

        Args:
            code_or_file: Either a file path to execute, or Python code as a string
            is_file: If True, treat code_or_file as a file path. If False, treat as code string.

        Returns:
            Dict with 'success', 'stdout', 'stderr', 'returncode', and 'error' (if any)
        """
        try:
            # Get current Python interpreter
            python_executable = sys.executable

            if is_file:
                # Execute a file
                if not Path(code_or_file).exists():
                    return {
                        "success": False,
                        "stdout": "",
                        "stderr": f"File not found: {code_or_file}",
                        "returncode": -1,
                        "error": "FileNotFoundError",
                    }

                # Run the file
                result = subprocess.run(
                    [python_executable, code_or_file],
                    capture_output=True,
                    text=True,
                    timeout=30,  # 30 second timeout
                    check=False,
                )
            else:
                # Execute code string
                # Use -c flag to execute code
                result = subprocess.run(
                    [python_executable, "-c", code_or_file],
                    capture_output=True,
                    text=True,
                    timeout=30,  # 30 second timeout
                    check=False,
                )

            return {
                "success": result.returncode == 0,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "returncode": result.returncode,
            }

        except subprocess.TimeoutExpired:
            return {
                "success": False,
                "stdout": "",
                "stderr": "Code execution timed out after 30 seconds",
                "returncode": -1,
                "error": "TimeoutExpired",
            }
        except Exception as e:
            return {
                "success": False,
                "stdout": "",
                "stderr": f"Error executing code: {str(e)}",
                "returncode": -1,
                "error": type(e).__name__,
            }

    def _apply_naming_fix(self, line: str, error_code: str, message: str) -> str:
        """Apply naming convention fixes.

        Args:
            line: Original line of code
            error_code: Pylint error code
            message: Error message

        Returns:
            Fixed line
        """
        fixed_line = line

        # Constant naming (UPPER_CASE)
        if "constant" in message.lower() and "uppercase" in message.lower():
            # Find constant assignment
            const_match = re.search(r"^(\s*)(\w+)\s*=\s*(.+)$", line)
            if const_match:
                indent, var_name, value = const_match.groups()
                upper_name = var_name.upper().replace("-", "_")
                fixed_line = f"{indent}{upper_name} = {value}"

        # Function naming (snake_case)
        elif "function" in message.lower() and "snake_case" in message.lower():
            func_match = re.search(r"^(\s*)def\s+(\w+)(.*)$", line)
            if func_match:
                indent, func_name, rest = func_match.groups()
                # Convert CamelCase or mixed to snake_case
                snake_name = re.sub(r"(?<!^)(?=[A-Z])", "_", func_name).lower()
                fixed_line = f"{indent}def {snake_name}{rest}"

        # Class naming (PascalCase)
        elif "class" in message.lower() and "pascalcase" in message.lower():
            class_match = re.search(r"^(\s*)class\s+(\w+)(.*)$", line)
            if class_match:
                indent, class_name, rest = class_match.groups()
                # Convert snake_case or mixed to PascalCase
                pascal_name = "".join(word.capitalize() for word in class_name.split("_"))
                fixed_line = f"{indent}class {pascal_name}{rest}"

        # Variable naming (snake_case)
        elif "variable" in message.lower() or ("invalid-name" in error_code.lower() and "variable" in message.lower()):
            # This is more complex, would need AST parsing for full support
            # For now, handle simple cases
            var_match = re.search(r"^(\s*)(\w+)\s*=\s*(.+)$", line)
            if var_match and not line.strip().startswith(("def ", "class ", "import ", "from ")):
                indent, var_name, value = var_match.groups()
                snake_name = re.sub(r"(?<!^)(?=[A-Z])", "_", var_name).lower()
                fixed_line = f"{indent}{snake_name} = {value}"

        return fixed_line

    def _apply_docstring_fix(self, lines: List[str], line_num: int, error_code: str, message: str) -> List[str]:
        """Apply docstring fixes.

        Args:
            lines: All lines of the file
            line_num: Line number where error occurs (1-indexed)
            error_code: Pylint error code
            message: Error message

        Returns:
            Modified lines list
        """
        fixed_lines = lines.copy()
        line_idx = line_num - 1

        if line_idx < 0 or line_idx >= len(fixed_lines):
            return fixed_lines

        current_line = fixed_lines[line_idx]

        # Missing function docstring
        if "missing-function-docstring" in error_code.lower() or "missing function" in message.lower():
            # Check if it's a function definition
            if re.match(r"^\s*def\s+\w+", current_line):
                # Add docstring after function definition
                indent_match = re.match(r"^(\s*)", current_line)
                indent = indent_match.group(1) if indent_match else "    "

                # Check if next line is already a docstring or code
                if line_idx + 1 < len(fixed_lines):
                    next_line = fixed_lines[line_idx + 1].strip()
                    if next_line.startswith('"""') or next_line.startswith("'''"):
                        # Docstring already exists, skip
                        return fixed_lines
                    elif next_line and not next_line.startswith("#"):
                        # There's code, insert docstring with newline
                        docstring = f'{indent}    """TODO: Add docstring."""\n'
                        fixed_lines.insert(line_idx + 1, docstring)
                else:
                    # End of file, add docstring with newline
                    docstring = f'{indent}    """TODO: Add docstring."""\n'
                    fixed_lines.insert(line_idx + 1, docstring)

        # Missing class docstring
        elif "missing-class-docstring" in error_code.lower() or "missing class" in message.lower():
            # Check if it's a class definition
            if re.match(r"^\s*class\s+\w+", current_line):
                indent_match = re.match(r"^(\s*)", current_line)
                indent = indent_match.group(1) if indent_match else "    "

                # Check if next line is already a docstring
                if line_idx + 1 < len(fixed_lines):
                    next_line = fixed_lines[line_idx + 1].strip()
                    if next_line.startswith('"""') or next_line.startswith("'''"):
                        return fixed_lines
                    elif next_line and not next_line.startswith("#"):
                        docstring = f'{indent}    """TODO: Add class docstring."""\n'
                        fixed_lines.insert(line_idx + 1, docstring)
                else:
                    docstring = f'{indent}    """TODO: Add class docstring."""\n'
                    fixed_lines.insert(line_idx + 1, docstring)

        return fixed_lines

    def _apply_whitespace_fix(self, line: str) -> str:
        """Apply whitespace fixes (trailing whitespace, etc.).

        Args:
            line: Original line

        Returns:
            Fixed line
        """
        # Remove trailing whitespace
        return line.rstrip() + "\n" if line.endswith("\n") else line.rstrip()

    def _apply_import_fix(self, lines: List[str]) -> List[str]:
        """Apply import organization fixes (PEP 8).

        Args:
            lines: All lines of the file

        Returns:
            Modified lines list
        """
        # This is a simplified version - full import sorting would need more work
        # For now, just ensure imports are at the top and remove duplicates
        import_lines = []
        other_lines = []
        in_imports = True

        for line in lines:
            stripped = line.strip()
            if stripped.startswith(("import ", "from ")):
                if line not in import_lines:  # Remove duplicates
                    import_lines.append(line)
            elif stripped and not stripped.startswith("#"):
                in_imports = False
                other_lines.append(line)
            else:
                if in_imports and not stripped:
                    # Empty line in imports section
                    continue
                other_lines.append(line)

        # Sort imports: stdlib, third-party, local (simplified)
        stdlib_imports = []
        third_party_imports = []
        local_imports = []

        for imp in import_lines:
            if any(pkg in imp for pkg in ["sys", "os", "pathlib", "typing", "collections", "itertools"]):
                stdlib_imports.append(imp)
            elif imp.startswith("from .") or imp.startswith("import ."):
                local_imports.append(imp)
            else:
                third_party_imports.append(imp)

        # Combine: stdlib, blank line, third-party, blank line, local
        organized_imports = stdlib_imports
        if third_party_imports:
            if organized_imports:
                organized_imports.append("\n")
            organized_imports.extend(third_party_imports)
        if local_imports:
            if organized_imports:
                organized_imports.append("\n")
            organized_imports.extend(local_imports)

        return organized_imports + (["\n"] if organized_imports and other_lines else []) + other_lines

    async def _run_ruff_format(self, file_path: str) -> Dict[str, Any]:
        """Run ruff format on a file.

        Args:
            file_path: Path to the Python file

        Returns:
            Dict with 'success' and 'stdout', 'stderr'
        """
        try:
            result = subprocess.run(
                ["ruff", "format", file_path],
                capture_output=True,
                text=True,
                timeout=30,
                check=False,
            )
            result2 = subprocess.run(
                ["ruff", "check", "--select", "I", "--fix", file_path],
                capture_output=True,
                text=True,
                timeout=30,
                check=False,
            )
            return {
                "success": (result.returncode == 0) and (result2.returncode == 0),
                "stdout": result.stdout + "\n\n" + result2.stdout,
                "stderr": result.stderr + "\n\n" + result2.stderr,
                "returncode": result.returncode or result2.returncode,
            }
        except FileNotFoundError:
            return {
                "success": False,
                "stdout": "",
                "stderr": "ruff not found. Please install ruff: pip install ruff",
                "returncode": -1,
            }
        except Exception as e:
            return {
                "success": False,
                "stdout": "",
                "stderr": f"Error running ruff format: {str(e)}",
                "returncode": -1,
            }

    async def _run_ruff_check_fix(self, file_path: str) -> Dict[str, Any]:
        """Run ruff check --fix on a file.

        Args:
            file_path: Path to the Python file

        Returns:
            Dict with 'success', 'stdout', 'stderr', and 'fixed_count'
        """
        try:
            result = subprocess.run(
                ["ruff", "check", "--fix", file_path],
                capture_output=True,
                text=True,
                timeout=30,
                check=False,
            )
            # Try to extract number of fixes from output
            fixed_count = 0
            if "fixed" in result.stdout.lower():
                # Look for patterns like "1 error fixed" or "Fixed 2 errors"
                matches = re.findall(r"(\d+)\s+error.*?fixed", result.stdout, re.IGNORECASE)
                if matches:
                    fixed_count = int(matches[0])

            return {
                "success": result.returncode == 0 or "fixed" in result.stdout.lower(),
                "stdout": result.stdout,
                "stderr": result.stderr,
                "returncode": result.returncode,
                "fixed_count": fixed_count,
            }
        except FileNotFoundError:
            return {
                "success": False,
                "stdout": "",
                "stderr": "ruff not found. Please install ruff: pip install ruff",
                "returncode": -1,
                "fixed_count": 0,
            }
        except Exception as e:
            return {
                "success": False,
                "stdout": "",
                "stderr": f"Error running ruff check --fix: {str(e)}",
                "returncode": -1,
                "fixed_count": 0,
            }

    async def _run_pylint(self, file_path: str) -> Dict[str, Any]:
        """Run pylint on a file and return parsed errors.

        Args:
            file_path: Path to the Python file

        Returns:
            Dict with 'errors' list
        """
        try:
            result = subprocess.run(
                ["pylint", file_path, "--output-format=text"],
                capture_output=True,
                text=True,
                timeout=60,
                check=False,
            )

            # Parse errors using shared utility function
            errors = parse_pylint_output(result.stdout)

            return {"errors": errors, "stdout": result.stdout}
        except Exception as e:
            return {"errors": [], "stdout": "", "error": str(e)}

    def _apply_fixes(self, file_path: str, proposed_changes: List[Dict[str, Any]]) -> str:
        """Apply fixes to a file based on proposed changes.

        Args:
            file_path: Path to the source file
            proposed_changes: List of proposed changes from ReviewerAgent

        Returns:
            Fixed file content as string
        """
        # Read original file
        with open(file_path, "r", encoding="utf-8") as f:
            lines = f.readlines()

        # Sort changes by line number (descending) to avoid line number shifts
        sorted_changes = sorted(proposed_changes, key=lambda x: x.get("line", 0), reverse=True)

        # Track which lines have been modified
        modified_lines = set()

        # Apply fixes
        for change in sorted_changes:
            line_num = change.get("line", 0)
            if line_num <= 0 or line_num > len(lines):
                continue

            line_idx = line_num - 1
            error_code = change.get("code", "")
            message = change.get("message", "")
            original_code = change.get("original_code", "")
            fixed_code = change.get("fixed_code", "")

            # Skip if already modified
            if line_idx in modified_lines:
                continue

            current_line = lines[line_idx]

            # Apply fix based on error type
            if fixed_code and fixed_code != original_code:
                # Use the provided fixed code
                lines[line_idx] = fixed_code + ("\n" if not fixed_code.endswith("\n") else "")
                modified_lines.add(line_idx)

            elif "naming" in message.lower() or "invalid-name" in error_code.lower():
                # Apply naming fix
                fixed_line = self._apply_naming_fix(current_line, error_code, message)
                if fixed_line != current_line:
                    lines[line_idx] = fixed_line + ("\n" if not fixed_line.endswith("\n") else "")
                    modified_lines.add(line_idx)

            elif "docstring" in message.lower() or "missing" in message.lower():
                # Apply docstring fix (may insert new lines)
                old_len = len(lines)
                lines = self._apply_docstring_fix(lines, line_num, error_code, message)
                # If a line was inserted, update modified_lines indices
                if len(lines) > old_len:
                    # A line was inserted after line_idx, shift all subsequent indices
                    new_modified = set()
                    for idx in modified_lines:
                        if idx > line_idx:
                            new_modified.add(idx + 1)
                        else:
                            new_modified.add(idx)
                    modified_lines = new_modified
                    modified_lines.add(line_idx + 1)  # Mark the inserted docstring line

            elif "trailing" in message.lower() or "whitespace" in message.lower():
                # Apply whitespace fix
                fixed_line = self._apply_whitespace_fix(current_line)
                if fixed_line != current_line:
                    lines[line_idx] = fixed_line
                    modified_lines.add(line_idx)

        # Apply import organization (once, at the end)
        if any("import" in str(change.get("message", "")).lower() for change in proposed_changes):
            lines = self._apply_import_fix(lines)

        return "".join(lines)

    def _format_proposed_changes_for_llm(self, proposed_changes: List[Dict[str, Any]]) -> str:
        """Format proposed changes with PEP context for LLM input.

        Args:
            proposed_changes: List of proposed changes from ReviewerAgent

        Returns:
            Formatted string with all proposed changes and PEP context
        """
        if not proposed_changes:
            return "No proposed changes to apply."

        formatted_parts = [
            "## Proposed Changes from Reviewer",
            "",
            f"Total issues to fix: {len(proposed_changes)}",
            "",
        ]

        for i, change in enumerate(proposed_changes, 1):
            formatted_parts.append(f"### Issue {i}")
            formatted_parts.append("")

            # Add description (includes line number, error code, message, and PEP references)
            description = change.get("description", "")
            if description:
                formatted_parts.append(description)
                formatted_parts.append("")

            # Add line number and error details
            line_num = change.get("line", 0)
            code = change.get("code", "")
            message = change.get("message", "")
            if line_num:
                formatted_parts.append(f"- **Line**: {line_num}")
            if code:
                formatted_parts.append(f"- **Error Code**: {code}")
            if message:
                formatted_parts.append(f"- **Error Message**: {message}")
            formatted_parts.append("")

            # Add PEP references
            pep_refs = change.get("pep_references", [])
            if pep_refs:
                formatted_parts.append("**Relevant PEP Guidelines:**")
                for ref in pep_refs:
                    pep_num = ref.get("number", "")
                    pep_url = ref.get("url", "")
                    if pep_url:
                        formatted_parts.append(f"- [PEP {pep_num}]({pep_url})")
                    else:
                        formatted_parts.append(f"- PEP {pep_num}")
                formatted_parts.append("")

            # Add code context
            code_snippet = change.get("code_snippet", "")
            original_code = change.get("original_code", "")
            fixed_code = change.get("fixed_code", "")

            if code_snippet:
                formatted_parts.append("**Code Context:**")
                formatted_parts.append("```python")
                formatted_parts.append(code_snippet)
                formatted_parts.append("```")
                formatted_parts.append("")

            # Add before/after if available
            if original_code and fixed_code and original_code != fixed_code:
                formatted_parts.append("**Suggested Fix:**")
                formatted_parts.append("")
                formatted_parts.append("**Before:**")
                formatted_parts.append("```python")
                formatted_parts.append(original_code)
                formatted_parts.append("```")
                formatted_parts.append("")
                formatted_parts.append("**After:**")
                formatted_parts.append("```python")
                formatted_parts.append(fixed_code)
                formatted_parts.append("```")
                formatted_parts.append("")
            elif original_code:
                formatted_parts.append("**Original Code:**")
                formatted_parts.append("```python")
                formatted_parts.append(original_code)
                formatted_parts.append("```")
                formatted_parts.append("")

            formatted_parts.append("---")
            formatted_parts.append("")

        return "\n".join(formatted_parts)

    async def invoke(
        self,
        inputs: Any,
        session: Optional[Any] = None,
    ) -> Dict[str, Any]:
        """Generate fixed version of a file using LLM reasoning.

        Args:
            inputs: Input dict with 'file_path' and 'review_results', or dict with 'file_path' and 'proposed_changes'
            session: Session object (optional)

        Returns:
            Dict with 'fixed_file_path', 'original_file_path', 'fixed_content', 'changes_applied'
        """
        # Normalize inputs
        if isinstance(inputs, dict):
            file_path = inputs.get("file_path")
            review_results = inputs.get("review_results", {})
            proposed_changes = inputs.get("proposed_changes") or review_results.get("proposed_changes", [])
            file_logger = inputs.get("file_logger")
        else:
            raise ValueError("Input must be dict with 'file_path' and 'review_results' or 'proposed_changes'")

        if not file_path:
            raise ValueError("file_path is required")

        if not Path(file_path).exists():
            raise ValueError(f"File not found: {file_path}")

        if not proposed_changes:
            return {
                "success": True,
                "fixed_file_path": None,
                "original_file_path": file_path,
                "fixed_content": None,
                "changes_applied": 0,
                "message": "No proposed changes to apply",
            }

        # Format proposed changes with PEP context for LLM
        changes_summary = self._format_proposed_changes_for_llm(proposed_changes)

        # Build user query for LLM
        user_query = f"""Please fix the Python file: {file_path}

The reviewer has identified the following issues that need to be fixed:

{changes_summary}

Your task:
1. Use read_file to read the current file content
2. For each issue, use read_file_context to understand the code around the problematic line
3. Apply fixes based on the reviewer's recommendations and PEP guidelines
4. Use write_file to write the fixed code
5. Use run_code to test the fixed code and ensure it still works correctly
6. Use run_pylint to verify the fixes resolved the issues
7. Use run_ruff_format and run_ruff_check_fix to ensure proper formatting

Important:
- Follow the PEP guidelines referenced in each issue
- Preserve code logic and functionality - test with run_code to verify
- Address all {len(proposed_changes)} issues systematically
- Be precise and careful - don't break working code
- Always test your fixes with run_code before finalizing"""
        if "qwen3" in self.config.model_name.casefold():
            user_query += " /no_think"

        try:
            # Use parent's ReAct loop - LLM will reason and use tools
            llm_result = await super().invoke({"query": user_query}, session=session)

            # Check if file was actually modified by reading it
            fixed_content = None
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    fixed_content = f.read()
            except Exception as e:
                if file_logger:
                    file_logger.warning("Could not read fixed file: %s", e)

            # Format the file with ruff (in place)
            ruff_format_result = await self._run_ruff_format(file_path)
            if file_logger and not ruff_format_result.get("success"):
                file_logger.warning("ruff format failed: %s", ruff_format_result.get("stderr", ""))

            # Auto-fix with ruff (in place)
            ruff_fix_result = await self._run_ruff_check_fix(file_path)
            if file_logger and ruff_fix_result.get("fixed_count", 0) > 0:
                file_logger.info("ruff fixed %d issue(s) in %s", ruff_fix_result["fixed_count"], file_path)

            # Verify fixes with pylint
            pylint_result = await self._run_pylint(file_path)
            remaining_errors = pylint_result.get("errors", [])
            if file_logger:
                file_logger.info(
                    "After fixing: %d errors remaining (was %d issues to fix)",
                    len(remaining_errors),
                    len(proposed_changes),
                )

            return {
                "success": True,
                "fixed_file_path": file_path,  # Same as original, modified in place
                "original_file_path": file_path,
                "fixed_content": fixed_content,
                "changes_applied": len(proposed_changes),
                "ruff_fixes": ruff_fix_result.get("fixed_count", 0),
                "remaining_errors": len(remaining_errors),
                "message": f"File modified in place: {file_path}",
                "llm_output": llm_result.get("output", ""),
            }

        except Exception as e:
            if file_logger:
                file_logger.error("LLM fix failed: %s, falling back to rule-based fix", e)

            # Fallback to rule-based fix
            try:
                fixed_content = self._apply_fixes(file_path, proposed_changes)

                # Write fixed content back to original file (in place)
                with open(file_path, "w", encoding="utf-8") as f:
                    f.write(fixed_content)

                # Format the file with ruff (in place)
                ruff_format_result = await self._run_ruff_format(file_path)
                if file_logger and not ruff_format_result.get("success"):
                    file_logger.warning("ruff format failed: %s", ruff_format_result.get("stderr", ""))

                # Auto-fix with ruff (in place)
                ruff_fix_result = await self._run_ruff_check_fix(file_path)
                if file_logger and ruff_fix_result.get("fixed_count", 0) > 0:
                    file_logger.info("ruff fixed %d issue(s) in %s", ruff_fix_result["fixed_count"], file_path)

                return {
                    "success": True,
                    "fixed_file_path": file_path,
                    "original_file_path": file_path,
                    "fixed_content": fixed_content,
                    "changes_applied": len(proposed_changes),
                    "ruff_fixes": ruff_fix_result.get("fixed_count", 0),
                    "message": f"File modified in place (rule-based fallback): {file_path}",
                    "fallback_used": True,
                }
            except Exception as fallback_error:
                return {
                    "success": False,
                    "fixed_file_path": None,
                    "original_file_path": file_path,
                    "fixed_content": None,
                    "changes_applied": 0,
                    "message": f"Error applying fixes: {str(e)} (fallback also failed: {str(fallback_error)})",
                    "error": str(e),
                    "fallback_error": str(fallback_error),
                }


__all__ = ["FixerAgent"]
