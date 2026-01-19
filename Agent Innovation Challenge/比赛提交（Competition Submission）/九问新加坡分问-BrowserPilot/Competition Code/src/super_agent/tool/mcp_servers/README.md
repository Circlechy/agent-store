# MCP Servers

This directory contains Model Context Protocol (MCP) server implementations. These servers provide various tool capabilities that LLM agents can use to interact with external services, APIs, and perform complex tasks.

## Overview

MCP servers are standalone processes that expose tools via the Model Context Protocol. Each server provides a specific set of capabilities, such as code execution, vision processing, web search, and more. The servers communicate with the main orchestrator via stdio or SSE transport protocols.

## Available Servers

This directory contains the following MCP servers:

### Active Servers (Started by Default)

These servers are automatically started by the activation scripts:

1. **browser_use_mcp** (`browser_use_mcp_server.py`)
   - Browser automation using the browser-use library
   - Enables agents to interact with web pages programmatically
   - **Tools**: `auto_browser_use`

2. **python** (`python_server.py`)
   - Python code execution in isolated E2B sandboxes
   - Safe execution environment for running arbitrary Python code
   - **Tools**: `create_sandbox`, `run_command`, `run_python_code`, `upload_file_from_local_to_sandbox`, `download_file_from_internet_to_sandbox`, `download_file_from_sandbox_to_local`
   - **Required**: `E2B_API_KEY`

3. **vision** (`vision_mcp_server.py`)
   - Visual question answering with images and videos
   - Supports multiple backends: Claude, OpenAI, Gemini, OpenRouter
   - Automatic OCR (text extraction) from images
   - YouTube video analysis with audio transcription
   - **Tools**: `visual_question_answering`, `visual_audio_youtube_analyzing`
   - **Required**: At least one of `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, `GEMINI_API_KEY`, `OPENROUTER_API_KEY`
   - **Optional**: `ENABLE_CLAUDE_VISION`, `ENABLE_OPENAI_VISION` (flags to enable specific backends)

4. **audio** (`audio_mcp_server.py`)
   - Audio transcription and processing
   - Audio question answering
   - Audio metadata identification (music recognition)
   - **Tools**: `audio_transcription`, `audio_question_answering`, `audio_metadata`
   - **Required**: `OPENAI_API_KEY`, `ACR_ACCESS_KEY`, `ACR_ACCESS_SECRET` (for audio metadata/recognition)

5. **reasoning** (`reasoning_mcp_server.py`)
   - Enhanced reasoning capabilities for complex problems
   - Uses Claude models with chain-of-thought reasoning
   - Designed for math problems, puzzles, riddles, and IQ tests
   - **Tools**: `reasoning`
   - **Required**: `OPENROUTER_API_KEY` and/or `ANTHROPIC_API_KEY`

6. **reading** (`reading_mcp_server.py`)
   - Document reading and processing
   - Supports various file formats: PDF, DOC, PPT, Excel, CSV, ZIP, etc.
   - Can read from local files, URLs, or data URIs
   - **Tools**: `read_file`
   - **Note**: Uses SSE transport (`--transport sse`) when started via scripts
   - **Variants**: `reading_mcp_server_gemini.py` (Gemini-specific implementation)

7. **searching** (`searching_mcp_server.py`)
   - Web search capabilities with multiple engines
   - Wikipedia content retrieval
   - Wayback Machine (archive.org) integration
   - Website scraping
   - **Tools**: `general_search`, `wiki_get_page_content`, `search_wiki_revision`, `search_archived_webpage`, `scrape_website`
   - **Required**: `SERPER_API_KEY`, `JINA_API_KEY`, `PERPLEXITY_API_KEY`, `GEMINI_API_KEY`

8. **wiki** (`wiki_mcp_server.py`)
   - Wikipedia-specific functionality
   - Provides Wikipedia content retrieval and search capabilities
   - **Tools**: (see server implementation for available tools)
   - **Note**: Started by default alongside searching server

### Additional Available Servers

These servers exist but are not started by default:

9. **auto_browser** (`auto_browser.py`)
   - Alternative browser automation solution
   - Different implementation from browser_use_mcp

10. **doubter** (`doubter.py`)
    - Agent action verification and scoring tool
    - Analyzes agent action flows for logical flaws
    - Provides scores and recommendations for improvement
    - **Tools**: `doubter` (verification), `doubter_score` (scoring)
    - **Required**: `OPENROUTER_API_KEY` or `OPENAI_API_KEY`, `GEMINI_API_KEY`
    - **Optional**: `DOUBTER_MODEL`, `DOUBTER_SCORE_MODEL`

11. **perplexity_search** (`perplexity_search.py`)
    - Perplexity-specific search implementation
    - Alternative to the general searching server

## Directory Structure

```
mcp_servers/
├── activate/                    # Startup scripts
│   ├── start_mcp_server.sh      # Mac/Linux (detects venv or uses --no-env)
│   └── start_mcp_servers.ps1    # Windows (detects venv or uses -NoEnv)
├── utils/                       # Shared utilities
│   ├── base_search.py
│   ├── bing_search.py
│   ├── ddg_search.py
│   ├── perplexity.py
│   ├── query_enhancer.py
│   ├── search_content_judge.py
│   └── smart_request.py
├── [server files].py            # Individual server implementations
└── README.md                    # This file
```

## Prerequisites

### Python Environment

- Python 3.12+ required (as specified in `examples/super_agent/tool/pyproject.toml`)
- Use any manager to install the dependencies (uv, conda, venv, etc.)

### Setup

**Option 1: Managed Environment (Recommended)**

The startup scripts will automatically detect and use a virtual environment in `examples/super_agent/tool/`. They prefer, in order:
- `.venv-tool`
- `.venv`
- `venv`

If you need to create the venv manually:

```bash
# Navigate to tooling directory
cd examples/super_agent/tool

# Create venv
uv venv .venv-tool --python 3.12
# or
python -m venv .venv-tool

# Install dependencies
# Windows (PowerShell)
.\.venv-tool\Scripts\Activate.ps1
# macOS/Linux
source .venv-tool/Scripts/activate

uv pip install --no-deps -r requirements.txt
# or
pip install --no-deps -r requirements.txt
```

**Option 2: User-Managed Environment**

If you prefer to manage your own Python environment (venv, conda, system Python, etc.):

1. Activate your environment first
2. Install dependencies: `pip install --no-deps -r requirements.txt`
3. Run the scripts with the `--no-env` flag (see below)

### Environment Variables

Each server may require specific API keys. Set these in your `.env` file or environment:

**Common API Keys:**
- `OPENAI_API_KEY` - Used by audio, vision, doubter servers
- `ANTHROPIC_API_KEY` - Used by vision, reasoning servers
- `GEMINI_API_KEY` - Used by vision, browser_use_mcp, doubter, searching servers
- `OPENROUTER_API_KEY` - Used by vision, reasoning, doubter, searching servers

**Server-Specific Keys:**
- `E2B_API_KEY` - Required for python server (sandbox execution)
- `SERPER_API_KEY` - For Google search in searching server
- `JINA_API_KEY` - For Jina deep search in searching server
- `PERPLEXITY_API_KEY` - For Perplexity search in searching server
- `ACR_ACCESS_KEY`, `ACR_ACCESS_SECRET` - For audio metadata recognition (optional)

---

## Optional: Starting the Servers (Only if use sse for all the mcp servers)

> This section is optional. Skip it unless you want to run all MCP servers via SSE.

All startup scripts are located in the `activate/` directory. The scripts automatically:
- Detect the repository root
- Detect and use a Python virtual environment (managed mode) or use your current Python (user-managed mode)
- Start all active servers in parallel using the selected Python executable

### Windows

**Managed Environment (Default):**
```powershell
# From repository root
.\examples\super_agent\tool\mcp_servers\activate\start_mcp_servers.ps1

# Or from the mcp_servers directory
.\activate\start_mcp_servers.ps1
```

**User-Managed Environment:**
```powershell
# Activate your venv first (if using one)
. .venv-tool\Scripts\Activate.ps1

# Then run with -NoEnv flag
.\examples\super_agent\tool\mcp_servers\activate\start_mcp_servers.ps1 -NoEnv
```

### Mac/Linux

**Managed Environment (Default):**
```bash
# From repository root
bash examples/super_agent/tool/mcp_servers/activate/start_mcp_server.sh

# Or from the tool directory
bash mcp_servers/activate/start_mcp_server.sh
```

**User-Managed Environment:**
```bash
# Activate your venv first (if using one)
source .venv-tool/bin/activate

# Then run with --no-env flag
bash examples/super_agent/tool/mcp_servers/activate/start_mcp_server.sh --no-env
```

### Environment Detection

**Managed Mode (Default):**
- Automatically detects the repository root
- Looks for a virtual environment in `examples/super_agent/tool/` (prefers `.venv-tool`, `.venv`, or `venv` in that order)
- Uses the venv's Python executable directly (no activation needed)

**User-Managed Mode (`--no-env` / `-NoEnv`):**
- Uses Python from your current shell
- If `$VIRTUAL_ENV` is set (venv activated), uses that venv's Python
- Otherwise uses system Python (`python` or `python3`)
- Respects your current environment setup

**Manual Override:**
If needed, you can explicitly set these using environment variables:
- `REPO_ROOT` — Set to the path of your repo root to force a specific directory
- `VENV_NAME` — Set to the name of the venv directory to use inside `examples/super_agent/tool` (managed mode only)

```powershell
# Windows PowerShell
$env:REPO_ROOT = 'C:\path\to\your\repo'
$env:VENV_NAME = '.venv-tool'
```

```bash
# Unix shells
export REPO_ROOT=/path/to/your/repo
export VENV_NAME=.venv-tool
```  


### Starting Individual Servers

You can also start servers individually. First, ensure your Python environment is set up:

```bash
# Navigate to tooling directory
cd examples/super_agent/tool

# Activate venv (if using managed venv)
# Windows (PowerShell)
. .venv-tool\Scripts\Activate.ps1
# macOS/Linux
source .venv-tool/bin/activate
```

Then run individual servers while you're still in the tooling directory:

```bash
# Python server
python -u -m mcp_servers.python_server

# Reading server (with SSE transport)
python -u -m mcp_servers.reading_mcp_server --transport sse

# Other servers
python -u -m mcp_servers.[server_name]
```

### Server Transport Protocols

- Most servers use **sse** transport (default), but **stdio** can also be utilised to start the servers up. 
- The **reading** server uses **SSE** (Server-Sent Events) transport when started via scripts
- Transport can be specified: `--transport sse` or `--transport stdio`

---

## Configuration

### Environment Variables Setup

Create a `.env` file in the repository root or set environment variables:

```bash
# Example .env file
OPENAI_API_KEY=your_openai_key_here
ANTHROPIC_API_KEY=your_anthropic_key_here
GEMINI_API_KEY=your_gemini_key_here
E2B_API_KEY=your_e2b_key_here
SERPER_API_KEY=your_serper_key_here
JINA_API_KEY=your_jina_key_here
PERPLEXITY_API_KEY=your_perplexity_key_here
OPENROUTER_API_KEY=your_openrouter_key_here
ACR_ACCESS_KEY=your_acr_key_here
ACR_ACCESS_SECRET=your_acr_secret_here
```
## Notes

- Servers are designed to run as long-lived processes
- Use Ctrl+C to stop all servers when started via scripts (trap handles cleanup in bash, manual cleanup needed in PowerShell)
- Each server runs in its own process for isolation
- Servers communicate via stdio or SSE protocols with the orchestrator
- The `reading` server uses SSE transport for better compatibility with certain use cases
- The scripts use Python executables directly (no venv activation needed)
- When using `--no-env` mode, the scripts respect your active venv if `$VIRTUAL_ENV` is set 
- Dependencies are installed with `--no-deps` flag to avoid dependency resolution conflicts (as specified in `pyproject.toml`)
- The tooling project has its own `pyproject.toml` with `aiohttp==3.12.15` to avoid conflicts with the root project's dependencies
