"""FastAPI server for DeepMemory Agent frontend."""

import os
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from dotenv import load_dotenv
load_dotenv()

from src.deep_memory_agent import DeepMemoryAgent
from src.openai_client import OpenAIClient
import deep_memory_mcp.utils as memory_utils

app = FastAPI(title="DeepMemory Agent API")

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify actual origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global agent instance
agent: Optional[DeepMemoryAgent] = None


class MessageRequest(BaseModel):
    message: str


class MessageResponse(BaseModel):
    response: str


class FileInfo(BaseModel):
    path: str
    relative_path: str
    date: str
    size: int
    is_file: bool


class FileTreeItem(BaseModel):
    name: str
    path: str
    relative_path: str
    is_file: bool
    size: Optional[int] = None
    date: Optional[str] = None
    children: Optional[list['FileTreeItem']] = None


FileTreeItem.model_rebuild()


def get_memory_dir() -> Path:
    """Get the memory directory path (use agent's if available, otherwise default)."""
    global agent
    if agent is not None:
        return agent.memory_dir
    return memory_utils.MEMORY_DIR


def create_agent() -> DeepMemoryAgent:
    """Create a new agent instance."""
    memory_dir = get_memory_dir()
    
    # Check if required environment variables are set
    model_name = os.getenv("DS_MODEL_NAME")
    api_key = os.getenv("DS_API_KEY")
    base_url = os.getenv("DS_BASE_URL")
    
    if not model_name or not api_key or not base_url:
        raise ValueError(
            f"Missing required environment variables. "
            f"DS_MODEL_NAME={model_name is not None}, "
            f"DS_API_KEY={api_key is not None}, "
            f"DS_BASE_URL={base_url is not None}"
        )
    
    llm = OpenAIClient(
        model_name=model_name,
        api_key=api_key,
        base_url=base_url,
    )
    agent = DeepMemoryAgent(
        memory_dir=str(memory_dir),
        llm=llm,
        max_iterations=10
    )
    print(f"Agent instance created: {type(agent).__name__}, memory_dir={agent.memory_dir}")
    return agent


@app.on_event("startup")
async def startup_event():
    """Initialize agent on startup."""
    global agent
    if agent is None:
        try:
            print("Creating agent on startup...")
            agent = create_agent()
            print(f"Agent created successfully. Memory dir: {agent.memory_dir}")
        except Exception as e:
            import traceback
            print(f"Error creating agent on startup: {e}\n{traceback.format_exc()}")
            # Don't raise - let it be created on first request


@app.post("/api/conversation/new", response_model=dict)
async def new_conversation():
    """Create a new conversation by deleting and recreating the agent."""
    global agent
    
    # Save current conversation history to memory if agent exists and has history
    if agent is not None and agent.conversation_history:
        try:
            await agent.save_conversation_to_memory()
            print(f"Saved conversation history to memory ({len(agent.conversation_history)} messages)")
        except Exception as e:
            import traceback
            error_msg = f"Error saving conversation to memory: {str(e)}\n{traceback.format_exc()}"
            print(error_msg)
            # Continue anyway - don't fail the new conversation request
    
    # Create new agent
    agent = None
    agent = create_agent()
    return {"status": "success", "message": "New conversation started"}


@app.post("/api/conversation/message", response_model=MessageResponse)
async def send_message(request: MessageRequest):
    """Send a message to the agent."""
    global agent
    if agent is None:
        try:
            agent = create_agent()
        except Exception as e:
            import traceback
            error_msg = f"Failed to create agent: {str(e)}\n{traceback.format_exc()}"
            print(error_msg)
            raise HTTPException(status_code=500, detail=f"Failed to create agent: {str(e)}")
    
    try:
        response = await agent.invoke(request.message)
        return MessageResponse(response=response)
    except Exception as e:
        import traceback
        error_msg = f"Error invoking agent: {str(e)}\n{traceback.format_exc()}"
        print(error_msg)  # Log full error to server console
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/files", response_model=list[FileInfo])
async def list_files():
    """List all memory files."""
    files = memory_utils.list_all_memory_files()
    memory_dir = get_memory_dir()
    
    result = []
    for file_path, date in files:
        try:
            rel_path = str(file_path.relative_to(memory_dir))
            result.append(FileInfo(
                path=str(file_path),
                relative_path=rel_path,
                date=date.isoformat(),
                size=file_path.stat().st_size,
                is_file=True
            ))
        except (ValueError, OSError):
            continue
    
    return result


@app.get("/api/files/tree", response_model=list[FileTreeItem])
async def get_file_tree():
    """Get file tree structure of memory directory."""
    memory_dir = get_memory_dir()
    
    if not memory_dir.exists():
        return []
    
    def build_tree(path: Path, base_path: Path) -> FileTreeItem:
        """Recursively build file tree."""
        rel_path = str(path.relative_to(base_path))
        
        if path.is_file():
            try:
                stat = path.stat()
                # Try to extract date from path structure
                date_str = None
                try:
                    parts = path.parts
                    if len(parts) >= 3:  # memory_dir/YYYY-M/YYYY-M-D/file.txt
                        date_parts = parts[-2].split("-")
                        if len(date_parts) == 3:
                            date_str = "-".join(date_parts)
                except:
                    pass
                
                return FileTreeItem(
                    name=path.name,
                    path=str(path),
                    relative_path=rel_path,
                    is_file=True,
                    size=stat.st_size,
                    date=date_str
                )
            except OSError:
                return FileTreeItem(
                    name=path.name,
                    path=str(path),
                    relative_path=rel_path,
                    is_file=True
                )
        else:
            children_list = []
            try:
                for item in sorted(path.iterdir()):
                    children_list.append(build_tree(item, base_path))
            except (PermissionError, OSError):
                pass
            
            return FileTreeItem(
                name=path.name,
                path=str(path),
                relative_path=rel_path,
                is_file=False,
                children=children_list if children_list else None
            )
    
    root_items = []
    for item in sorted(memory_dir.iterdir()):
        root_items.append(build_tree(item, memory_dir))
    
    return root_items


@app.get("/api/files/{file_path:path}", response_model=dict)
async def read_file(file_path: str):
    """Read a memory file by relative path."""
    memory_dir = get_memory_dir()
    full_path = memory_dir / file_path
    
    # Security check: ensure the path is within memory_dir
    try:
        full_path.resolve().relative_to(memory_dir.resolve())
    except ValueError:
        raise HTTPException(status_code=403, detail="Access denied")
    
    if not full_path.exists():
        raise HTTPException(status_code=404, detail="File not found")
    
    if not full_path.is_file():
        raise HTTPException(status_code=400, detail="Path is not a file")
    
    try:
        content = full_path.read_text(encoding="utf-8")
        stat = full_path.stat()
        return {
            "content": content,
            "path": file_path,
            "size": stat.st_size,
            "modified": stat.st_mtime
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error reading file: {str(e)}")


@app.get("/api/health")
async def health():
    """Health check endpoint."""
    global agent
    return {
        "status": "ok",
        "agent_created": agent is not None,
        "memory_dir": str(get_memory_dir())
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
