"""MCP server for vibecheck - allows AI agents to query and update tool intelligence."""

import json
from datetime import datetime
from typing import Any

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool

from ..config import get_settings
from ..database import CategoriesDB, CommunitiesDB, ToolsDB


def create_server() -> Server:
    """Create and configure the MCP server."""
    server = Server("vibecheck")
    settings = get_settings()

    # Initialize database connections
    tools_db = ToolsDB()
    communities_db = CommunitiesDB()
    categories_db = CategoriesDB()

    @server.list_tools()
    async def list_tools() -> list[Tool]:
        """List available vibecheck tools."""
        return [
            Tool(
                name="vibecheck_search",
                description="Search for AI tools by name, category, or description",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Search query (tool name, category, or keywords)",
                        },
                        "community": {
                            "type": "string",
                            "description": "Filter by community (agi, henkaku, dg)",
                        },
                        "category": {
                            "type": "string",
                            "description": "Filter by category slug",
                        },
                        "limit": {
                            "type": "integer",
                            "description": "Max results (default 10)",
                            "default": 10,
                        },
                    },
                    "required": ["query"],
                },
            ),
            Tool(
                name="vibecheck_get",
                description="Get detailed information about a specific tool",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "slug": {
                            "type": "string",
                            "description": "Tool slug (e.g., 'cursor', 'claude-code')",
                        },
                    },
                    "required": ["slug"],
                },
            ),
            Tool(
                name="vibecheck_list",
                description="List tools, optionally filtered by category or community",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "category": {
                            "type": "string",
                            "description": "Filter by category slug",
                        },
                        "community": {
                            "type": "string",
                            "description": "Filter by community (agi, henkaku, dg)",
                        },
                        "limit": {
                            "type": "integer",
                            "description": "Max results (default 20)",
                            "default": 20,
                        },
                    },
                },
            ),
            Tool(
                name="vibecheck_add",
                description="Add a new tool to vibecheck",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "name": {
                            "type": "string",
                            "description": "Tool name",
                        },
                        "slug": {
                            "type": "string",
                            "description": "URL-safe slug (auto-generated if not provided)",
                        },
                        "url": {
                            "type": "string",
                            "description": "Tool website URL",
                        },
                        "github_url": {
                            "type": "string",
                            "description": "GitHub repository URL",
                        },
                        "description": {
                            "type": "string",
                            "description": "Brief description of the tool",
                        },
                        "categories": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Category slugs",
                        },
                        "communities": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Community slugs where discussed",
                        },
                    },
                    "required": ["name"],
                },
            ),
            Tool(
                name="vibecheck_mention",
                description="Record a tool mention in a community discussion",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "tool_slug": {
                            "type": "string",
                            "description": "Tool slug",
                        },
                        "tool_name": {
                            "type": "string",
                            "description": "Tool name (if slug unknown)",
                        },
                        "community": {
                            "type": "string",
                            "description": "Community slug (agi, henkaku, dg)",
                        },
                        "context": {
                            "type": "string",
                            "description": "Brief context of the mention (sanitized)",
                        },
                        "sentiment": {
                            "type": "string",
                            "enum": ["positive", "negative", "neutral", "question"],
                            "description": "Sentiment of the mention",
                        },
                    },
                    "required": ["community"],
                },
            ),
            Tool(
                name="vibecheck_categories",
                description="List all tool categories",
                inputSchema={
                    "type": "object",
                    "properties": {},
                },
            ),
            Tool(
                name="vibecheck_communities",
                description="List all tracked communities",
                inputSchema={
                    "type": "object",
                    "properties": {},
                },
            ),
            Tool(
                name="vibecheck_recent",
                description="Get recently mentioned tools",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "community": {
                            "type": "string",
                            "description": "Filter by community",
                        },
                        "limit": {
                            "type": "integer",
                            "description": "Max results (default 20)",
                            "default": 20,
                        },
                    },
                },
            ),
        ]

    @server.call_tool()
    async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
        """Handle tool calls."""
        try:
            if name == "vibecheck_search":
                results = tools_db.search_tools(
                    query=arguments["query"],
                    category=arguments.get("category"),
                    limit=arguments.get("limit", 10),
                )
                # Filter by community if specified
                if arguments.get("community"):
                    community_tools = communities_db.get_tools_for_community(
                        arguments["community"]
                    )
                    community_slugs = {
                        t.get("tools", {}).get("slug") for t in community_tools
                    }
                    results = [r for r in results if r.get("slug") in community_slugs]

                return [TextContent(type="text", text=json.dumps(results, indent=2, default=str))]

            elif name == "vibecheck_get":
                tool = tools_db.get_tool(arguments["slug"])
                if not tool:
                    return [TextContent(type="text", text=f"Tool '{arguments['slug']}' not found")]
                
                # Get evaluations and links
                from ..database import EvaluationsDB, LinksDB
                evals_db = EvaluationsDB()
                links_db = LinksDB()
                
                evaluations = evals_db.get_evaluations(tool["id"])
                links = links_db.get_links(tool["id"])
                
                result = {
                    **tool,
                    "evaluations": evaluations,
                    "links": links,
                }
                return [TextContent(type="text", text=json.dumps(result, indent=2, default=str))]

            elif name == "vibecheck_list":
                tools = tools_db.list_tools(
                    category=arguments.get("category"),
                    limit=arguments.get("limit", 20),
                )
                if arguments.get("community"):
                    community_tools = communities_db.get_tools_for_community(
                        arguments["community"]
                    )
                    community_slugs = {
                        t.get("tools", {}).get("slug") for t in community_tools
                    }
                    tools = [t for t in tools if t.get("slug") in community_slugs]
                
                return [TextContent(type="text", text=json.dumps(tools, indent=2, default=str))]

            elif name == "vibecheck_add":
                slug = arguments.get("slug") or arguments["name"].lower().replace(" ", "-")
                slug = "".join(c for c in slug if c.isalnum() or c == "-")
                
                tool = tools_db.create_tool({
                    "slug": slug,
                    "name": arguments["name"],
                    "url": arguments.get("url"),
                    "github_url": arguments.get("github_url"),
                    "description": arguments.get("description"),
                    "categories": arguments.get("categories", []),
                    "source": "mcp",
                })
                
                # Link to communities
                for community in arguments.get("communities", []):
                    communities_db.link_tool_to_community(tool["id"], community)
                
                return [TextContent(type="text", text=json.dumps(tool, indent=2, default=str))]

            elif name == "vibecheck_mention":
                # Find or identify tool
                tool = None
                if arguments.get("tool_slug"):
                    tool = tools_db.get_tool(arguments["tool_slug"])
                
                if not tool and arguments.get("tool_name"):
                    # Try to find by name or create
                    slug = arguments["tool_name"].lower().replace(" ", "-")
                    slug = "".join(c for c in slug if c.isalnum() or c == "-")
                    tool = tools_db.get_tool(slug)
                    
                    if not tool:
                        tool = tools_db.create_tool({
                            "slug": slug,
                            "name": arguments["tool_name"],
                            "source": "mcp-mention",
                        })
                
                if not tool:
                    return [TextContent(type="text", text="Error: Must provide tool_slug or tool_name")]
                
                # Record mention
                mention = communities_db.record_mention(
                    tool_id=tool["id"],
                    community_slug=arguments["community"],
                    mentioned_at=datetime.utcnow().isoformat(),
                    context_snippet=arguments.get("context"),
                    sentiment=arguments.get("sentiment"),
                )
                
                return [TextContent(type="text", text=json.dumps({
                    "status": "recorded",
                    "tool": tool["slug"],
                    "community": arguments["community"],
                }, indent=2))]

            elif name == "vibecheck_categories":
                categories = categories_db.list_categories()
                return [TextContent(type="text", text=json.dumps(categories, indent=2, default=str))]

            elif name == "vibecheck_communities":
                communities = communities_db.list_communities()
                return [TextContent(type="text", text=json.dumps(communities, indent=2, default=str))]

            elif name == "vibecheck_recent":
                mentions = communities_db.get_mention_history(
                    community_slug=arguments.get("community"),
                    limit=arguments.get("limit", 20),
                )
                return [TextContent(type="text", text=json.dumps(mentions, indent=2, default=str))]

            else:
                return [TextContent(type="text", text=f"Unknown tool: {name}")]

        except Exception as e:
            return [TextContent(type="text", text=f"Error: {str(e)}")]

    return server


async def main():
    """Run the MCP server."""
    server = create_server()
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
