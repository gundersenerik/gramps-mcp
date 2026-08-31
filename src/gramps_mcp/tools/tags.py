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
Tag MCP tools for organizing genealogy records.
"""

import logging
from typing import List

from mcp.types import TextContent

from ..client import GrampsWebAPIClient
from ..config import get_settings
from ..models.api_calls import ApiCalls
from .common import format_error_response
from .crud_common import (
    _validate_params,
)

logger = logging.getLogger(__name__)


# ============================================================================
# Tag Tools (CRUD)
# ============================================================================


async def find_tags_tool(arguments) -> List[TextContent]:
    """Find/list all tags in the database."""
    from ..models.parameters.tag_params import TagSearchParams

    try:
        params = _validate_params(arguments, TagSearchParams)
        settings = get_settings()
        tree_id = settings.gramps_tree_id

        client = GrampsWebAPIClient()
        try:
            tags = await client.make_api_call(
                api_call=ApiCalls.GET_TAGS,
                params=params,
                tree_id=tree_id,
            )

            if not tags:
                return [TextContent(type="text", text="No tags found.")]

            result = f"Found {len(tags)} tags:\n\n"
            for tag in tags:
                name = tag.get("name", "Unnamed")
                handle = tag.get("handle", "N/A")
                color = tag.get("color", "")
                priority = tag.get("priority", "")

                result += f"- **{name}** [`{handle}`]"
                if color:
                    result += f" - Color: {color}"
                if priority:
                    result += f" - Priority: {priority}"
                result += "\n"

            return [TextContent(type="text", text=result)]

        finally:
            await client.close()
    except Exception as e:
        return format_error_response(e, "tags search")


async def create_tag_tool(arguments) -> List[TextContent]:
    """Create or update a tag."""
    from ..models.parameters.tag_params import TagSaveParams

    try:
        params = _validate_params(arguments, TagSaveParams)
        settings = get_settings()
        tree_id = settings.gramps_tree_id

        client = GrampsWebAPIClient()
        try:
            if params.handle:
                # Update existing tag
                result = await client.make_api_call(
                    api_call=ApiCalls.PUT_TAG,
                    params=params,
                    tree_id=tree_id,
                    handle=params.handle,
                )
                operation = "updated"
            else:
                # Create new tag
                result = await client.make_api_call(
                    api_call=ApiCalls.POST_TAGS,
                    params=params,
                    tree_id=tree_id,
                )
                operation = "created"

            # Extract tag data
            if isinstance(result, list) and result:
                tag_data = result[0].get("new", result[0])
            else:
                tag_data = result

            name = tag_data.get("name", params.name)
            handle = tag_data.get("handle", "N/A")

            return [
                TextContent(
                    type="text",
                    text=f"Successfully {operation} tag: **{name}** [`{handle}`]",
                )
            ]

        finally:
            await client.close()
    except Exception as e:
        return format_error_response(e, "tag save")


async def delete_tag_tool(arguments) -> List[TextContent]:
    """Delete a tag by handle."""
    from ..models.parameters.delete_params import DeleteParams

    try:
        params = _validate_params(arguments, DeleteParams)
        settings = get_settings()
        tree_id = settings.gramps_tree_id

        client = GrampsWebAPIClient()
        try:
            await client.make_api_call(
                api_call=ApiCalls.DELETE_TAG,
                params=None,
                tree_id=tree_id,
                handle=params.handle,
            )
            return [
                TextContent(
                    type="text",
                    text=f"Successfully deleted tag with handle: {params.handle}",
                )
            ]
        finally:
            await client.close()
    except Exception as e:
        return format_error_response(e, "tag delete")
