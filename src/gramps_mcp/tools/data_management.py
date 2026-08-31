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
Create and update MCP tools for genealogy records.

This module contains the tools that create or update people, families,
events, places, sources, citations, notes, media records and repositories.
"""

import logging
import mimetypes
import os
from typing import Dict, List

from mcp.types import TextContent

from ..client import GrampsAPIError, GrampsWebAPIClient
from ..config import get_settings
from ..models.api_calls import ApiCalls
from ..models.parameters.citation_params import CitationData
from ..models.parameters.event_params import EventSaveParams
from ..models.parameters.family_params import FamilySaveParams
from ..models.parameters.media_params import MediaSaveParams
from ..models.parameters.note_params import NoteSaveParams
from ..models.parameters.people_params import PersonData
from ..models.parameters.place_params import PlaceSaveParams
from ..models.parameters.repository_params import RepositoryData
from ..models.parameters.source_params import SourceSaveParams
from .common import format_error_response
from .crud_common import (
    _extract_entity_data,
    _format_save_response,
    _handle_crud_operation,
    _validate_params,
)

logger = logging.getLogger(__name__)


# ============================================================================
# Data Management Tools (8 tools)
# ============================================================================


async def create_person_tool(arguments: Dict) -> List[TextContent]:
    """
    Create or update person information including family links and event associations.
    """
    return await _handle_crud_operation(
        arguments, "person", ApiCalls.POST_PEOPLE, ApiCalls.PUT_PERSON, PersonData
    )


async def create_family_tool(arguments) -> List[TextContent]:
    """
    Create or update family unit including member relationships.
    """
    try:
        # Validate parameters - handles both dict and BaseModel inputs
        params = _validate_params(arguments, FamilySaveParams)

        # Get tree_id from settings
        settings = get_settings()
        tree_id = settings.gramps_tree_id

        # Create client and make unified API call
        client = GrampsWebAPIClient()
        try:
            # Choose API call based on whether handle is provided (update vs create)
            if params.handle:
                # Update existing family
                result = await client.make_api_call(
                    api_call=ApiCalls.PUT_FAMILY,
                    params=params,
                    tree_id=tree_id,
                    handle=params.handle,
                )
                operation = "updated"
            else:
                # Create new family
                result = await client.make_api_call(
                    api_call=ApiCalls.POST_FAMILIES, params=params, tree_id=tree_id
                )
                operation = "created"

            # Extract entity data from API response (handles family special case)
            entity_data = _extract_entity_data(result, "family")
            formatted_response = await _format_save_response(
                client, entity_data, "family", operation, tree_id
            )
            return [TextContent(type="text", text=formatted_response)]

        finally:
            await client.close()

    except Exception as e:
        format_error_response(e, "family save")


async def create_event_tool(arguments: Dict) -> List[TextContent]:
    """
    Create or update life event including person/place associations.
    """
    return await _handle_crud_operation(
        arguments, "event", ApiCalls.POST_EVENTS, ApiCalls.PUT_EVENT, EventSaveParams
    )


async def create_place_tool(arguments: Dict) -> List[TextContent]:
    """
    Create or update geographic location.
    """
    return await _handle_crud_operation(
        arguments, "place", ApiCalls.POST_PLACES, ApiCalls.PUT_PLACE, PlaceSaveParams
    )


async def create_source_tool(arguments: Dict) -> List[TextContent]:
    """
    Create or update source document.
    """
    return await _handle_crud_operation(
        arguments,
        "source",
        ApiCalls.POST_SOURCES,
        ApiCalls.PUT_SOURCE,
        SourceSaveParams,
    )


async def create_citation_tool(arguments: Dict) -> List[TextContent]:
    """
    Create or update citation including object associations.
    """
    return await _handle_crud_operation(
        arguments,
        "citation",
        ApiCalls.POST_CITATIONS,
        ApiCalls.PUT_CITATION,
        CitationData,
    )


async def create_note_tool(arguments: Dict) -> List[TextContent]:
    """
    Create or update textual note including object associations.
    """
    return await _handle_crud_operation(
        arguments, "note", ApiCalls.POST_NOTES, ApiCalls.PUT_NOTE, NoteSaveParams
    )


async def create_media_tool(arguments) -> List[TextContent]:
    """
    Create or update media files including object associations.
    """
    from pydantic import BaseModel

    try:
        # Handle both dict and BaseModel inputs
        if isinstance(arguments, BaseModel):
            # Convert to dict for processing
            args_dict = arguments.model_dump()
        else:
            args_dict = arguments

        # Extract file_location separately (not part of MediaSaveParams)
        file_location = args_dict.get("file_location")

        # All other arguments are for metadata
        media_params = {k: v for k, v in args_dict.items() if k != "file_location"}
        params = MediaSaveParams(**media_params) if media_params else None

        settings = get_settings()
        tree_id = settings.gramps_tree_id

        client = GrampsWebAPIClient()
        try:
            # If a handle is provided, we are updating an existing media object
            if params and params.handle:
                result = await client.make_api_call(
                    api_call=ApiCalls.PUT_MEDIA_ITEM,
                    params=params,
                    tree_id=tree_id,
                    handle=params.handle,
                )
                operation = "updated"
                entity_data = _extract_entity_data(result)
            else:
                # If no handle, we are creating a new media object,
                # which requires a file
                if not file_location:
                    raise ValueError("file_location is required to create new media.")
                if not os.path.isfile(file_location):
                    raise FileNotFoundError(f"File not found: {file_location}")

                # 1. Upload the file to create the initial media object
                with open(file_location, "rb") as f:
                    file_content = f.read()
                mime_type, _ = mimetypes.guess_type(file_location)
                if not mime_type:
                    mime_type = "application/octet-stream"

                upload_result = await client.upload_media_file(
                    file_content, mime_type, tree_id
                )

                if not (
                    upload_result
                    and isinstance(upload_result, list)
                    and "new" in upload_result[0]
                ):
                    raise GrampsAPIError(
                        "Media upload did not return the expected new object."
                    )
                initial_media_object = upload_result[0]["new"]
                media_handle = initial_media_object["handle"]

                # 2. Merge initial object with metadata and update via PUT
                final_media_data = initial_media_object.copy()
                if params:
                    final_media_data.update(params.model_dump(exclude_none=True))

                result = await client.make_api_call(
                    api_call=ApiCalls.PUT_MEDIA_ITEM,
                    params=final_media_data,
                    tree_id=tree_id,
                    handle=media_handle,
                )
                operation = "created"
                entity_data = _extract_entity_data(result)

            formatted_response = await _format_save_response(
                client, entity_data, "media", operation, tree_id
            )
            return [TextContent(type="text", text=formatted_response)]

        finally:
            await client.close()

    except Exception as e:
        format_error_response(e, "media save")


async def create_repository_tool(arguments) -> List[TextContent]:
    """
    Create or update repository information.
    """
    try:
        # Validate parameters - handles both dict and BaseModel inputs
        params = _validate_params(arguments, RepositoryData)

        # Assert required parameters
        if not params.name:
            return [
                TextContent(
                    type="text",
                    text="Error: 'name' parameter is required for repository",
                )
            ]
        if not params.type:
            return [
                TextContent(
                    type="text",
                    text="Error: 'type' parameter is required for repository",
                )
            ]

        # Get tree_id from settings
        settings = get_settings()
        tree_id = settings.gramps_tree_id

        # Create client and make unified API call
        client = GrampsWebAPIClient()
        try:
            # Choose API call based on whether handle is provided (update vs create)
            if params.handle:
                # Update existing repository
                result = await client.make_api_call(
                    api_call=ApiCalls.PUT_REPOSITORY,
                    params=params,
                    tree_id=tree_id,
                    handle=params.handle,
                )
                operation = "updated"
            else:
                # Create new repository
                result = await client.make_api_call(
                    api_call=ApiCalls.POST_REPOSITORIES, params=params, tree_id=tree_id
                )
                operation = "created"

            # Extract entity data from API response
            entity_data = _extract_entity_data(result)
            formatted_response = await _format_save_response(
                client, entity_data, "repository", operation, tree_id
            )
            return [TextContent(type="text", text=formatted_response)]

        finally:
            await client.close()

    except Exception as e:
        format_error_response(e, "repository save")
