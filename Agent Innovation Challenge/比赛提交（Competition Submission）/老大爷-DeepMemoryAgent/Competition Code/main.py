"""Demo script for DeepMemoryAgent."""

import asyncio
import os
from pathlib import Path

from src.openai_client import OpenAIClient

from dotenv import load_dotenv
load_dotenv()

from src.deep_memory_agent import DeepMemoryAgent


async def main():
    """Main demo function showing how to use DeepMemoryAgent."""
    
    # Get memory directory (default to ./memory_dir)
    memory_dir = os.getenv("MEMORY_DIR", "./memory_dir")
    
    # Initialize LLM from environment variables
    # The exact way to create an LLM depends on your openjiuwen setup
    # Common patterns: API keys, model names, etc.
    llm = OpenAIClient(
        model_name = os.getenv("DS_MODEL_NAME"),
        api_key = os.getenv("DS_API_KEY"),
        base_url = os.getenv("DS_BASE_URL"),
    )
    
    # Initialize the DeepMemoryAgent
    print(f"\n{'='*60}")
    print("Initializing DeepMemoryAgent")
    print(f"{'='*60}")
    print(f"Memory Directory: {memory_dir}")
    
    agent = DeepMemoryAgent(
        memory_dir=memory_dir,
        llm=llm,
        max_iterations=10
    )
    
    # Initialize the agent (registers MCP server tools)
    print("\nInitializing agent (registering MCP server tools)...")
    
    # Demo queries
    demo_queries = [
        "记得张三吗",
    ]
    
    print(f"\n{'='*60}")
    print("Running Demo Queries")
    print(f"{'='*60}\n")
    
    # Run demo queries
    for i, query in enumerate(demo_queries, 1):
        print(f"\n--- Query {i} ---")
        print(f"User: {query}")
        
        try:
            # Invoke the agent
            response = await agent.invoke(query)
            
            print(f"Agent: {response}")
            print(f"Conversation history length: {len(agent.conversation_history)} messages")
            
        except Exception as e:
            print(f"Error processing query: {e}")
            import traceback
            traceback.print_exc()
    
    # Show memory statistics
    print(f"\n{'='*60}")
    print("Memory Statistics")
    print(f"{'='*60}\n")
    
    try:
        # The agent should have saved conversations to memory
        memory_path = Path(memory_dir)
        if memory_path.exists():
            # Count memory files
            memory_files = list(memory_path.rglob("*.txt"))
            print(f"Total memory files: {len(memory_files)}")
            
            if memory_files:
                print("\nRecent memory files:")
                for file in sorted(memory_files, key=lambda p: p.stat().st_mtime, reverse=True)[:5]:
                    rel_path = file.relative_to(memory_path)
                    print(f"  - {rel_path}")
        else:
            print("Memory directory does not exist yet.")
    except Exception as e:
        print(f"Error checking memory statistics: {e}")
    
    print(f"\n{'='*60}")
    print("Demo Complete")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    """Run the demo."""
    asyncio.run(main())
