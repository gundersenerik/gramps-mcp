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
Shared create/update/delete plumbing for the data management tools.

These helpers validate tool arguments, dispatch the Gramps Web API call
and render the response, so each tool module stays a thin wrapper.
"""

import logging
from typing import Dict, List

from mcp.types import TextContent

from ..client import GrampsWebAPIClient
from ..config import get_settings
from ..handlers.citation_handler import format_citation
from ..handlers.event_handler import format_event
from ..handlers.family_handler import format_family
from ..handlers.media_handler import format_media
from ..handlers.note_handler import format_note
from ..handlers.person_handler import format_person
from ..handlers.place_handler import format_place
from ..handlers.repository_handler import format_repository
from ..handlers.source_handler import format_source
from .common import format_error_response

logger = logging.getLogger(__name__)


def _extract_entity_data(result, entity_type: str = None):
    """Extract entity data from API response, handling different formats."""
    if not result:
        return None

    # Handle family creation special case - find Family entry in response list
    if entity_type == "family" and isinstance(result, list) and len(result) > 1:
        family_entry = None
        for entry in result:
            if entry.get("new", {}).get("_class") == "Family":
                family_entry = entry["new"]
                break
        return family_entry if family_entry else result[0].get("new", result[0])

    # Standard case - API may return list or single object
    return (
        result[0]["new"]
        if result and isinstance(result, list) and result[0].get("new")
        else result
    )


def _validate_params(arguments, param_class):
    """Validate parameters - skip if already a validated Pydantic model."""
    from pydantic import BaseModel

    if isinstance(arguments, BaseModel):
        return arguments
    return param_class(**arguments)


async def _handle_crud_operation(
    params, entity_type: str, post_api_call, put_api_call, param_class
) -> List[TextContent]:
    """Common helper for create/update operations."""
    try:
        # Validate parameters - skip if already a validated Pydantic model
        validated_params = _validate_params(params, param_class)

        # Get tree_id from settings
        settings = get_settings()
        tree_id = settings.gramps_tree_id

        # Create client and make unified API call
        client = GrampsWebAPIClient()
        try:
            # Choose API call based on whether handle is provided (update vs create)
            if hasattr(validated_params, "handle") and validated_params.handle:
                # Update existing entity
                result = await client.make_api_call(
                    api_call=put_api_call,
                    params=validated_params,
                    tree_id=tree_id,
                    handle=validated_params.handle,
                )
                operation = "updated"
            else:
                # Create new entity
                result = await client.make_api_call(
                    api_call=post_api_call, params=validated_params, tree_id=tree_id
                )
                operation = "created"

            # Extract entity data from API response
            entity_data = _extract_entity_data(result, entity_type)
            formatted_response = await _format_save_response(
                client, entity_data, entity_type, operation, tree_id
            )
            return [TextContent(type="text", text=formatted_response)]

        finally:
            await client.close()

    except Exception as e:
        return format_error_response(e, f"{entity_type} save")


async def _format_save_response(
    client: GrampsWebAPIClient,
    entity_data: Dict,
    entity_type: str,
    operation: str,
    tree_id: str,
) -> str:
    """Format successful save operation response using appropriate format handler."""
    handle = entity_data.get("handle", "N/A")
    gramps_id = entity_data.get("gramps_id", "N/A")

    try:
        # Use the appropriate format handler to get consistent formatting
        if entity_type == "person":
            formatted_details = await format_person(client, tree_id, handle)
        elif entity_type == "family":
            formatted_details = await format_family(client, tree_id, handle)
        elif entity_type == "event":
            formatted_details = await format_event(client, tree_id, handle)
        elif entity_type == "place":
            formatted_details = await format_place(client, tree_id, handle)
        elif entity_type == "source":
            formatted_details = await format_source(client, tree_id, handle)
        elif entity_type == "citation":
            formatted_details = await format_citation(client, tree_id, handle)
        elif entity_type == "media":
            formatted_details = await format_media(client, tree_id, handle)
        elif entity_type == "note":
            formatted_details = await format_note(client, tree_id, handle)
        elif entity_type == "repository":
            formatted_details = await format_repository(client, tree_id, handle)
        else:
            # Fallback for unknown types
            formatted_details = (
                f"• **{entity_type.title()} {gramps_id}** (Handle: `{handle}`)\n\n"
            )

        # Add success prefix to the formatted details
        result = f"Successfully {operation} {entity_type}:\n\n{formatted_details}"
        return result

    except Exception as e:
        logger.warning(f"Error formatting {entity_type} details: {e}")
        # Fallback to basic formatting if handler fails
        display_name = f"{entity_type.title()} {gramps_id}"
        result = f"Successfully {operation} {entity_type}: **{display_name}**\n\n"
        result += f"**ID:** {gramps_id}\n"
        result += f"**Handle:** `{handle}`\n"
        return result
