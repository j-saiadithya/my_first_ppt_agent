"""
Web Search MCP Server — Step 7 (Bonus)
=======================================
Optional MCP server that provides web search capability.
The agent can use this to gather real-world information before
generating slide content, making presentations more factual.

Tools provided:
  - search_web(query) -> Returns top search results as text summaries
"""

import json
from mcp.server.fastmcp import FastMCP

# ---------------------------------------------------------------------------
# MCP Server Instance
# ---------------------------------------------------------------------------
mcp = FastMCP("search-server")


# ---------------------------------------------------------------------------
# Tool: search_web
# ---------------------------------------------------------------------------
@mcp.tool()
def search_web(query: str) -> str:
    """
    Search the web for information on a given topic.

    Args:
        query: The search query string.

    Returns:
        A JSON string with the top 3 search results containing
        title, snippet, and URL.
    """
    try:
        from duckduckgo_search import DDGS

        results = []
        with DDGS() as ddgs:
            for r in ddgs.text(query, max_results=3):
                results.append({
                    "title": r.get("title", ""),
                    "snippet": r.get("body", ""),
                    "url": r.get("href", ""),
                })

        if not results:
            return json.dumps({
                "status": "success",
                "message": "No results found.",
                "results": [],
            })

        return json.dumps({
            "status": "success",
            "message": f"Found {len(results)} results for '{query}'.",
            "results": results,
        })

    except ImportError:
        return json.dumps({
            "status": "error",
            "message": "duckduckgo-search package not installed. Run: pip install duckduckgo-search",
            "results": [],
        })
    except Exception as e:
        return json.dumps({
            "status": "error",
            "message": f"Search failed: {str(e)}",
            "results": [],
        })


# ---------------------------------------------------------------------------
# Run the MCP server (stdio transport)
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    mcp.run()
