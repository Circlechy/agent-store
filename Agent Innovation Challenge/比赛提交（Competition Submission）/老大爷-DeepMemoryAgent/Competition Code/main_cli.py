"""Interactive CLI for DeepMemoryAgent."""

import asyncio
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
load_dotenv()

from src.openai_client import OpenAIClient
from src.deep_memory_agent import DeepMemoryAgent


async def main():
    """Main CLI function for interactive conversation with DeepMemoryAgent."""
    
    # Get memory directory (default to ./memory_dir)
    memory_dir = os.getenv("MEMORY_DIR", "./memory_dir")
    
    # Initialize LLM from environment variables
    print("Initializing LLM...")
    llm = OpenAIClient(
        model_name=os.getenv("DS_MODEL_NAME"),
        api_key=os.getenv("DS_API_KEY"),
        base_url=os.getenv("DS_BASE_URL"),
    )
    
    # Initialize the DeepMemoryAgent
    print(f"\n{'='*60}")
    print("Initializing DeepMemoryAgent")
    print(f"{'='*60}")
    print(f"Memory Directory: {memory_dir}")
    print("\nInitializing agent (registering MCP server tools)...")
    
    try:
        agent = DeepMemoryAgent(
            memory_dir=memory_dir,
            llm=llm,
            max_iterations=10
        )
        print("Agent initialized successfully!")
    except Exception as e:
        print(f"Error initializing agent: {e}")
        import traceback
        traceback.print_exc()
        return
    
    # Interactive conversation loop
    print(f"\n{'='*60}")
    print("DeepMemory Agent CLI")
    print(f"{'='*60}")
    print("Type your messages below. Type '\\exit' to quit.\n")
    
    while True:
        try:
            # Get user input
            user_input = input("You: ").strip()
            
            # Check for exit command
            if user_input.lower() in ['\\exit', '\\quit', '/exit', '/quit']:
                await agent.save_conversation_to_memory()
                print("\nGoodbye!")
                break
            
            # Skip empty input
            if not user_input:
                continue
            
            # Process query through agent
            print("\nAgent: ", end="", flush=True)
            try:
                response = await agent.invoke(user_input)
                print(response)
                print()  # Empty line for readability
            except KeyboardInterrupt:
                print("\n\nInterrupted by user. Type '\\exit' to quit.")
                continue
            except Exception as e:
                print(f"\nError: {e}")
                import traceback
                traceback.print_exc()
                print()  # Empty line for readability
                continue
                
        except KeyboardInterrupt:
            print("\n\nInterrupted by user. Type '\\exit' to quit.")
            continue
        except EOFError:
            print("\n\nGoodbye!")
            break
        except Exception as e:
            print(f"\nUnexpected error: {e}")
            import traceback
            traceback.print_exc()
            print()  # Empty line for readability


if __name__ == "__main__":
    """Run the CLI."""
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\nGoodbye!")
        sys.exit(0)
