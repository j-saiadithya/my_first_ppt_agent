"""
Auto-PPT Agent — Main Entry Point (Step 9)
============================================
Usage:
    python main.py "Create a 5-slide presentation on AI in healthcare"
    python main.py "Make a presentation about climate change"
    python main.py                          (interactive prompt)
"""

import sys
import os
import asyncio

# Fix Windows console encoding
if sys.platform == "win32":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# Fix import path
sys.path.append(os.path.abspath(os.path.dirname(__file__)))

from agent.agent import AutoPPTAgent


def print_banner():
    """Print the startup banner."""
    print("")
    print("=" * 60)
    print("   AUTO-PPT AGENT")
    print("   AI-Powered Presentation Generator")
    print("=" * 60)
    print("   Architecture: Agent + MCP Tools")
    print("   LLM: Qwen2.5-72B-Instruct (via HuggingFace)")
    print("=" * 60)
    print("")


async def main():
    print_banner()

    # Get prompt from command line or ask interactively
    if len(sys.argv) > 1:
        prompt = " ".join(sys.argv[1:])
    else:
        print("Enter your presentation topic:")
        print("  Examples:")
        print("    - Create a 5-slide presentation on AI in healthcare")
        print("    - Make 7 slides about climate change")
        print("    - Presentation on the future of space exploration")
        print("")
        prompt = input(">> ").strip()

    if not prompt:
        print("No prompt provided. Exiting.")
        return

    print(f"\nPrompt: {prompt}")
    print("-" * 60)

    # Create and run the agent
    agent = AutoPPTAgent()

    try:
        filepath = await agent.run(prompt)
    except Exception as e:
        print(f"\n[ERROR] Agent failed: {e}")
        import traceback
        traceback.print_exc()
        return

    # Final output
    print("\n" + "=" * 60)
    if filepath and os.path.exists(filepath):
        file_size = os.path.getsize(filepath)
        print(f"   SUCCESS!")
        print(f"   File: {filepath}")
        print(f"   Size: {file_size:,} bytes")
    else:
        print("   FAILED to generate presentation.")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
