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
Delete MCP tools for genealogy records.

Each tool removes a single record from the Gramps Web database by handle.
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
# Delete Tools (2 tools)
# ============================================================================


async def delete_person_tool(arguments) -> List[TextContent]:
    """Delete a person by handle."""
    from ..models.parameters.delete_params import DeleteParams

    try:
        params = _validate_params(arguments, DeleteParams)
        settings = get_settings()
        tree_id = settings.gramps_tree_id

        client = GrampsWebAPIClient()
        try:
            await client.make_api_call(
                api_call=ApiCalls.DELETE_PERSON,
                params=None,
                tree_id=tree_id,
                handle=params.handle,
            )
            return [
                TextContent(
                    type="text",
                    text=f"Successfully deleted person with handle: {params.handle}",
                )
            ]
        finally:
            await client.close()
    except Exception as e:
        return format_error_response(e, "person delete")


async def delete_family_tool(arguments) -> List[TextContent]:
    """Delete a family by handle."""
    from ..models.parameters.delete_params import DeleteParams

    try:
        params = _validate_params(arguments, DeleteParams)
        settings = get_settings()
        tree_id = settings.gramps_tree_id

        client = GrampsWebAPIClient()
        try:
            await client.make_api_call(
                api_call=ApiCalls.DELETE_FAMILY,
                params=None,
                tree_id=tree_id,
                handle=params.handle,
            )
            return [
                TextContent(
                    type="text",
                    text=f"Successfully deleted family with handle: {params.handle}",
                )
            ]
        finally:
            await client.close()
    except Exception as e:
        return format_error_response(e, "family delete")


async def delete_event_tool(arguments) -> List[TextContent]:
    """Delete an event by handle."""
    from ..models.parameters.delete_params import DeleteParams

    try:
        params = _validate_params(arguments, DeleteParams)
        settings = get_settings()
        tree_id = settings.gramps_tree_id

        client = GrampsWebAPIClient()
        try:
            await client.make_api_call(
                api_call=ApiCalls.DELETE_EVENT,
                params=None,
                tree_id=tree_id,
                handle=params.handle,
            )
            return [
                TextContent(
                    type="text",
                    text=f"Successfully deleted event with handle: {params.handle}",
                )
            ]
        finally:
            await client.close()
    except Exception as e:
        return format_error_response(e, "event delete")


async def delete_note_tool(arguments) -> List[TextContent]:
    """Delete a note by handle."""
    from ..models.parameters.delete_params import DeleteParams

    try:
        params = _validate_params(arguments, DeleteParams)
        settings = get_settings()
        tree_id = settings.gramps_tree_id

        client = GrampsWebAPIClient()
        try:
            await client.make_api_call(
                api_call=ApiCalls.DELETE_NOTE,
                params=None,
                tree_id=tree_id,
                handle=params.handle,
            )
            return [
                TextContent(
                    type="text",
                    text=f"Successfully deleted note with handle: {params.handle}",
                )
            ]
        finally:
            await client.close()
    except Exception as e:
        return format_error_response(e, "note delete")


async def delete_citation_tool(arguments) -> List[TextContent]:
    """Delete a citation by handle."""
    from ..models.parameters.delete_params import DeleteParams

    try:
        params = _validate_params(arguments, DeleteParams)
        settings = get_settings()
        tree_id = settings.gramps_tree_id

        client = GrampsWebAPIClient()
        try:
            await client.make_api_call(
                api_call=ApiCalls.DELETE_CITATION,
                params=None,
                tree_id=tree_id,
                handle=params.handle,
            )
            return [
                TextContent(
                    type="text",
                    text=f"Successfully deleted citation with handle: {params.handle}",
                )
            ]
        finally:
            await client.close()
    except Exception as e:
        return format_error_response(e, "citation delete")


async def delete_source_tool(arguments) -> List[TextContent]:
    """Delete a source by handle."""
    from ..models.parameters.delete_params import DeleteParams

    try:
        params = _validate_params(arguments, DeleteParams)
        settings = get_settings()
        tree_id = settings.gramps_tree_id

        client = GrampsWebAPIClient()
        try:
            await client.make_api_call(
                api_call=ApiCalls.DELETE_SOURCE,
                params=None,
                tree_id=tree_id,
                handle=params.handle,
            )
            return [
                TextContent(
                    type="text",
                    text=f"Successfully deleted source with handle: {params.handle}",
                )
            ]
        finally:
            await client.close()
    except Exception as e:
        return format_error_response(e, "source delete")


async def delete_place_tool(arguments) -> List[TextContent]:
    """Delete a place by handle."""
    from ..models.parameters.delete_params import DeleteParams

    try:
        params = _validate_params(arguments, DeleteParams)
        settings = get_settings()
        tree_id = settings.gramps_tree_id

        client = GrampsWebAPIClient()
        try:
            await client.make_api_call(
                api_call=ApiCalls.DELETE_PLACE,
                params=None,
                tree_id=tree_id,
                handle=params.handle,
            )
            return [
                TextContent(
                    type="text",
                    text=f"Successfully deleted place with handle: {params.handle}",
                )
            ]
        finally:
            await client.close()
    except Exception as e:
        return format_error_response(e, "place delete")


async def delete_repository_tool(arguments) -> List[TextContent]:
    """Delete a repository by handle."""
    from ..models.parameters.delete_params import DeleteParams

    try:
        params = _validate_params(arguments, DeleteParams)
        settings = get_settings()
        tree_id = settings.gramps_tree_id

        client = GrampsWebAPIClient()
        try:
            await client.make_api_call(
                api_call=ApiCalls.DELETE_REPOSITORY,
                params=None,
                tree_id=tree_id,
                handle=params.handle,
            )
            return [
                TextContent(
                    type="text",
                    text=(
                        f"Successfully deleted repository with handle: {params.handle}"
                    ),
                )
            ]
        finally:
            await client.close()
    except Exception as e:
        return format_error_response(e, "repository delete")


async def delete_media_tool(arguments) -> List[TextContent]:
    """Delete a media item by handle."""
    from ..models.parameters.delete_params import DeleteParams

    try:
        params = _validate_params(arguments, DeleteParams)
        settings = get_settings()
        tree_id = settings.gramps_tree_id

        client = GrampsWebAPIClient()
        try:
            await client.make_api_call(
                api_call=ApiCalls.DELETE_MEDIA_ITEM,
                params=None,
                tree_id=tree_id,
                handle=params.handle,
            )
            return [
                TextContent(
                    type="text",
                    text=f"Successfully deleted media with handle: {params.handle}",
                )
            ]
        finally:
            await client.close()
    except Exception as e:
        return format_error_response(e, "media delete")
