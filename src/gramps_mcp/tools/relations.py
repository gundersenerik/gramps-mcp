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
Relationship and person-fact MCP tools.

These tools resolve how two people are related, whether a person counts
as living, and the computed facts Gramps derives for a tree.
"""

import logging
from typing import List

from mcp.types import TextContent

from ..config import get_settings
from ..models.api_calls import ApiCalls
from .analysis_common import (
    _get_arg,
)
from .common import format_error_response
from .search_basic import with_client

logger = logging.getLogger(__name__)


@with_client
async def get_relations_tool(client, arguments) -> List[TextContent]:
    """
    Find the relationship between two people.
    """
    try:
        handle1 = _get_arg(arguments, "handle1")
        handle2 = _get_arg(arguments, "handle2")

        if not handle1 or not handle2:
            raise ValueError("Both handle1 and handle2 are required")

        settings = get_settings()
        tree_id = settings.gramps_tree_id

        # Get relationship using the API
        relations = await client.make_api_call(
            api_call=ApiCalls.GET_RELATIONS,
            params=None,
            tree_id=tree_id,
            handle1=handle1,
            handle2=handle2,
        )

        if not relations:
            return [
                TextContent(
                    type="text",
                    text="No relationship found between these two people.",
                )
            ]

        # Format the relationship result
        # API returns: {"distance_common_origin": N,
        # "distance_common_other": M, "relationship_string": "..."}
        result = "## Relationship Found\n\n"

        if isinstance(relations, dict):
            relationship = relations.get("relationship_string", "Unknown")
            dist_origin = relations.get("distance_common_origin")
            dist_other = relations.get("distance_common_other")

            result += f"**Relationship:** {relationship}\n"

            if dist_origin is not None and dist_other is not None:
                total_distance = dist_origin + dist_other
                result += f"**Total Distance:** {total_distance} generations\n"
                result += f"  - From person 1 to common ancestor: {dist_origin}\n"
                result += f"  - From common ancestor to person 2: {dist_other}\n"
        else:
            result += str(relations)

        return [TextContent(type="text", text=result)]

    except Exception as e:
        return format_error_response(e, "relationship lookup")


# ============================================================================
# Relations All Tool
# ============================================================================


@with_client
async def get_relations_all_tool(client, arguments) -> List[TextContent]:
    """
    Find ALL possible relationship paths between two people.
    """
    try:
        handle1 = _get_arg(arguments, "handle1")
        handle2 = _get_arg(arguments, "handle2")

        if not handle1 or not handle2:
            raise ValueError("Both handle1 and handle2 are required")

        settings = get_settings()
        tree_id = settings.gramps_tree_id

        # Get all relationships
        relations = await client.make_api_call(
            api_call=ApiCalls.GET_RELATIONS_ALL,
            params=None,
            tree_id=tree_id,
            handle1=handle1,
            handle2=handle2,
        )

        if not relations:
            return [
                TextContent(
                    type="text",
                    text="No relationships found between these two people.",
                )
            ]

        # Format all relationships
        result = "## All Relationship Paths\n\n"

        if isinstance(relations, list):
            for i, rel in enumerate(relations, 1):
                relationship = rel.get("relationship_string", "Unknown")
                dist_origin = rel.get("distance_common_origin")
                dist_other = rel.get("distance_common_other")

                result += f"**Path {i}:** {relationship}\n"
                if dist_origin is not None and dist_other is not None:
                    result += f"  - Distance: {dist_origin + dist_other} generations\n"
                result += "\n"
        else:
            result += str(relations)

        return [TextContent(type="text", text=result)]

    except Exception as e:
        return format_error_response(e, "all relationships lookup")


# ============================================================================
# Living Status Tools
# ============================================================================


@with_client
async def get_living_tool(client, arguments) -> List[TextContent]:
    """
    Check if a person is considered living (for privacy purposes).
    """
    try:
        handle = _get_arg(arguments, "handle")

        if not handle:
            raise ValueError("handle is required")

        settings = get_settings()
        tree_id = settings.gramps_tree_id

        # Get living status
        result = await client.make_api_call(
            api_call=ApiCalls.GET_LIVING,
            params=None,
            tree_id=tree_id,
            handle=handle,
        )

        # Format response
        is_living = result.get("living", False) if isinstance(result, dict) else result
        status = "LIVING" if is_living else "DECEASED"

        return [
            TextContent(
                type="text",
                text=f"**Living Status:** {status}\n\nHandle: `{handle}`",
            )
        ]

    except Exception as e:
        return format_error_response(e, "living status check")


# ============================================================================
# Facts Tools
# ============================================================================


@with_client
async def get_facts_tool(client, arguments) -> List[TextContent]:
    """
    Get computed facts and statistics about the family tree.
    """
    try:
        from ..models.parameters.facts_params import FactsParams

        # Extract only explicitly provided arguments (not defaults)
        # to avoid sending extra params the API rejects
        if isinstance(arguments, FactsParams):
            # Get only user-provided values
            params_dict = arguments.model_dump(exclude_unset=True)
        elif isinstance(arguments, dict):
            params_dict = {k: v for k, v in arguments.items() if v is not None}
        else:
            params_dict = {}

        # Only create params if there are explicit values to send
        params = FactsParams(**params_dict) if params_dict else None

        settings = get_settings()
        tree_id = settings.gramps_tree_id

        # Get facts
        facts = await client.make_api_call(
            api_call=ApiCalls.GET_FACTS,
            params=params,
            tree_id=tree_id,
        )

        # Format response
        if not facts:
            return [TextContent(type="text", text="No facts available.")]

        result = "# Tree Facts\n\n"

        if isinstance(facts, dict):
            for key, value in facts.items():
                if isinstance(value, dict):
                    result += f"## {key.replace('_', ' ').title()}\n"
                    for sub_key, sub_value in value.items():
                        result += f"- **{sub_key}:** {sub_value}\n"
                    result += "\n"
                elif isinstance(value, list):
                    result += f"## {key.replace('_', ' ').title()}\n"
                    for item in value[:10]:  # Limit to first 10
                        result += f"- {item}\n"
                    result += "\n"
                else:
                    result += f"- **{key.replace('_', ' ').title()}:** {value}\n"
        else:
            result += str(facts)

        return [TextContent(type="text", text=result)]

    except Exception as e:
        return format_error_response(e, "facts retrieval")
