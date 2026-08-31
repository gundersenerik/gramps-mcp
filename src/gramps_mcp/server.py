# gramps-mcp - AI-Powered Genealogy Research & Management
# Copyright (C) 2025 cabout.me
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

"""
MCP server main entry point with HTTP transport.

This module wires the FastMCP application to the tool registry and exposes
the genealogy tools for Gramps Web API integration over HTTP and stdio.
"""

import asyncio
import logging
import os
import sys
from typing import Optional

from mcp.server import Server
from mcp.server.fastmcp import FastMCP
from mcp.server.stdio import stdio_server
from mcp.types import Tool

# Import all parameter models
from .models.parameters.simple_params import (
    EmptyParams,
)
from .tool_registry import TOOL_REGISTRY

# Import all tool functions

# Setup logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create FastMCP app with stateless HTTP (no SSE)
app = FastMCP("gramps", stateless_http=True, json_response=True)


# ============================================================================
# Dynamic FastMCP Tool Registration
# ============================================================================


def _build_tool_handler(handler_func, schema, tool_name, description):
    """
    Build the FastMCP-facing handler for a single tool registry entry.

    Args:
        handler_func (Callable): Tool implementation to delegate to.
        schema (type): Pydantic model describing the tool arguments.
        tool_name (str): Name to expose the tool under.
        description (str): Tool description shown to MCP clients.

    Returns:
        Callable: Async handler annotated with the tool's argument schema.
    """
    # Reason: handler_func is captured by this closure rather than bound as a
    # keyword-argument default. A default would put "handler" in the handler's
    # signature, and FastMCP derives each tool's JSON schema from that
    # signature, so every tool would advertise a bogus "handler" parameter.
    if schema == EmptyParams:
        # For tools with no parameters, make arguments optional
        async def tool_handler(arguments: Optional[EmptyParams] = None):
            return await handler_func(arguments or {})

        tool_handler.__annotations__ = {"arguments": Optional[EmptyParams]}
    else:

        async def tool_handler(arguments):
            return await handler_func(arguments)

        tool_handler.__annotations__ = {"arguments": schema}

    # Set proper metadata
    tool_handler.__name__ = tool_name
    tool_handler.__doc__ = description
    return tool_handler


# Register all tools dynamically from the registry
def register_tools():
    """Register all tools from the registry with FastMCP."""
    for tool_name, tool_config in TOOL_REGISTRY.items():
        description = tool_config["description"]

        # Pass the validated Pydantic model directly to the handler
        # Handlers will check if they receive a BaseModel and skip re-validation
        tool_handler = _build_tool_handler(
            tool_config["handler"], tool_config["schema"], tool_name, description
        )

        # Register with FastMCP
        app.tool(description=description)(tool_handler)


register_tools()


# ============================================================================
# Resource Management
# ============================================================================


def load_resource(filename: str) -> str:
    """Load content from resources folder with error handling."""
    try:
        # Get the path to the resources directory relative to this file
        current_dir = os.path.dirname(os.path.abspath(__file__))
        resource_path = os.path.join(current_dir, "resources", filename)

        with open(resource_path, "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        return f"Resource file '{filename}' not found."
    except Exception as e:
        return f"Error loading resource '{filename}': {str(e)}"


@app.resource("gql://documentation")
def get_gql_documentation() -> str:
    """
    Complete GQL documentation, syntax, examples, and property
    reference for Gramps queries.
    """
    return load_resource("gql-documentation.md")


@app.resource("gramps://usage-guide")
def get_usage_guide() -> str:
    """
    IMPORTANT: Read this first before using ANY creation tools -
    explains proper genealogy workflow and tool usage order.
    """
    return load_resource("gramps-usage-guide.md")


# Add custom routes to the FastMCP app
@app.custom_route("/", ["GET"])
async def root(request):
    """Root endpoint with server information."""
    from starlette.responses import JSONResponse

    return JSONResponse(
        {
            "service": "Gramps MCP Server",
            "version": "1.0.0",
            "description": "MCP server for Gramps Web API genealogy operations",
            "mcp_endpoint": "/mcp",
            "tools_count": 39,
        }
    )


@app.custom_route("/health", ["GET"])
async def health_check(request):
    """Health check endpoint."""
    from starlette.responses import JSONResponse

    return JSONResponse(
        {"status": "healthy", "service": "Gramps MCP Server", "tools": 39}
    )


async def run_stdio_server():
    """Run the MCP server with stdio transport."""
    # Create a standard MCP server for stdio transport
    server = Server("gramps")

    @server.list_tools()
    async def handle_list_tools():
        """List all available tools."""
        return [
            Tool(
                name=tool_name,
                description=tool_config["description"],
                inputSchema=tool_config["schema"].model_json_schema(),
            )
            for tool_name, tool_config in TOOL_REGISTRY.items()
        ]

    @server.call_tool()
    async def handle_call_tool(name: str, arguments: dict):
        """Handle tool calls."""
        if name in TOOL_REGISTRY:
            return await TOOL_REGISTRY[name]["handler"](arguments)
        else:
            raise ValueError(f"Unknown tool: {name}")

    # Run the server with stdio transport
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream, write_stream, server.create_initialization_options()
        )


if __name__ == "__main__":
    # Determine transport type from command line arguments or environment
    transport_type = sys.argv[1] if len(sys.argv) > 1 else "streamable-http"

    if transport_type == "stdio":
        # Run with stdio transport for CLI usage
        asyncio.run(run_stdio_server())
    else:
        # Run the FastMCP server with streamable HTTP transport
        # Configure server settings
        app.settings.host = "0.0.0.0"  # Listen on all interfaces for Docker
        app.settings.port = 8000

        # Run with streamable-http transport for production use
        app.run(transport="streamable-http")
