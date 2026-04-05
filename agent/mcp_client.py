"""
MCP Client — Step 4
====================
A thin wrapper that starts the MCP server as a subprocess and
communicates with it over stdio transport using the MCP protocol.

This keeps the Agent (reasoning) and Server (tools) fully separated.
"""

import sys
import os
import json
import asyncio
from contextlib import AsyncExitStack

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

# Path to the PPT MCP server script
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
PPT_SERVER_PATH = os.path.join(PROJECT_ROOT, "mcp_servers", "ppt_server.py")
SEARCH_SERVER_PATH = os.path.join(PROJECT_ROOT, "mcp_servers", "search_server.py")

# Python executable (use the venv's python)
PYTHON_EXE = sys.executable


class MCPClient:
    """
    Manages a connection to an MCP server over stdio.

    Usage:
        client = MCPClient()
        await client.connect("ppt")       # starts ppt_server.py
        result = await client.call_tool("create_presentation", {"title": "My Deck"})
        await client.close()
    """

    def __init__(self):
        self._session = None
        self._exit_stack = AsyncExitStack()
        self._tools = []

    async def connect(self, server_type: str = "ppt"):
        """
        Start the MCP server as a subprocess and connect via stdio.

        Args:
            server_type: "ppt" for the PPT server, "search" for web search server.
        """
        if server_type == "search":
            server_path = SEARCH_SERVER_PATH
        else:
            server_path = PPT_SERVER_PATH

        if not os.path.exists(server_path):
            raise FileNotFoundError(f"MCP server not found: {server_path}")

        server_params = StdioServerParameters(
            command=PYTHON_EXE,
            args=[server_path],
        )

        # Start the server subprocess and get read/write streams
        stdio_transport = await self._exit_stack.enter_async_context(
            stdio_client(server_params)
        )
        read_stream, write_stream = stdio_transport

        # Create and initialize the MCP client session
        self._session = await self._exit_stack.enter_async_context(
            ClientSession(read_stream, write_stream)
        )
        await self._session.initialize()

        # Cache the available tools
        tools_response = await self._session.list_tools()
        self._tools = tools_response.tools

        tool_names = [t.name for t in self._tools]
        print(f"[MCP Client] Connected to '{server_type}' server.")
        print(f"[MCP Client] Available tools: {tool_names}")

        return tool_names

    async def call_tool(self, tool_name: str, arguments: dict) -> str:
        """
        Call a tool on the connected MCP server.

        Args:
            tool_name: Name of the tool to call.
            arguments: Dictionary of arguments to pass.

        Returns:
            The tool's response as a string.
        """
        if self._session is None:
            raise RuntimeError("Not connected. Call connect() first.")

        try:
            result = await self._session.call_tool(tool_name, arguments)
            # Extract text content from the result
            if result.content:
                return result.content[0].text
            return json.dumps({"status": "success", "message": "Tool returned no content."})
        except Exception as e:
            return json.dumps({"status": "error", "message": f"Tool call failed: {str(e)}"})

    def list_tools(self):
        """Return the list of available tool names."""
        return [t.name for t in self._tools]

    def get_tool_descriptions(self):
        """Return tool names with their descriptions (for the LLM system prompt)."""
        descriptions = []
        for t in self._tools:
            descriptions.append(f"- {t.name}: {t.description}")
        return "\n".join(descriptions)

    async def close(self):
        """Close the connection and stop the server subprocess."""
        await self._exit_stack.aclose()
        self._session = None
        self._tools = []
        print("[MCP Client] Connection closed.")
