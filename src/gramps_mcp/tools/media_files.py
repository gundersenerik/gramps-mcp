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
Media file MCP tools for retrieving, uploading and replacing media files.
"""

import logging
import mimetypes
import os
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
# Media File Tools
# ============================================================================


async def get_media_file_tool(arguments) -> List[TextContent]:
    """
    Get information about a media file (metadata and download URL).

    Note: This returns file metadata. The actual file can be accessed
    via the Gramps Web UI or API directly.
    """
    from ..models.parameters.delete_params import DeleteParams

    try:
        params = _validate_params(arguments, DeleteParams)
        settings = get_settings()
        tree_id = settings.gramps_tree_id

        client = GrampsWebAPIClient()
        try:
            # First get media metadata
            media_info = await client.make_api_call(
                api_call=ApiCalls.GET_MEDIA_ITEM,
                params=None,
                tree_id=tree_id,
                handle=params.handle,
            )

            if not media_info:
                return [
                    TextContent(type="text", text=f"Media not found: {params.handle}")
                ]

            # Format response
            gramps_id = media_info.get("gramps_id", "N/A")
            desc = media_info.get("desc", "No description")
            mime = media_info.get("mime", "Unknown")
            path = media_info.get("path", "")
            checksum = media_info.get("checksum", "")

            result = f"## Media File: {gramps_id}\n\n"
            result += f"**Description:** {desc}\n"
            result += f"**MIME Type:** {mime}\n"
            result += f"**Path:** {path}\n"
            result += f"**Handle:** `{params.handle}`\n"
            if checksum:
                result += f"**Checksum:** {checksum}\n"

            # Provide download URL hint
            api_url = settings.gramps_api_url
            result += (
                f"\n**File URL:** `{api_url}/api/trees/{tree_id}"
                f"/media/{params.handle}/file`\n"
            )

            return [TextContent(type="text", text=result)]

        finally:
            await client.close()
    except Exception as e:
        format_error_response(e, "media file info")


async def upload_media_file_tool(arguments) -> List[TextContent]:
    """
    Upload a new media file from the local filesystem.

    Creates a new media object in Gramps with the uploaded file.
    Supports common image formats (jpg, png, gif, etc.), PDFs, and other media.
    """
    from ..models.parameters.media_params import MediaFileUploadParams

    try:
        params = _validate_params(arguments, MediaFileUploadParams)
        settings = get_settings()
        tree_id = settings.gramps_tree_id

        # Validate file exists
        if not os.path.isfile(params.file_path):
            return [
                TextContent(
                    type="text",
                    text=f"Error: File not found: {params.file_path}",
                )
            ]

        # Read file content
        with open(params.file_path, "rb") as f:
            file_content = f.read()

        # Determine MIME type
        mime_type, _ = mimetypes.guess_type(params.file_path)
        if not mime_type:
            # Default to binary if unknown
            mime_type = "application/octet-stream"

        # Get file size for reporting
        file_size = len(file_content)
        file_name = os.path.basename(params.file_path)

        client = GrampsWebAPIClient()
        try:
            result = await client.upload_media_file(
                file_content=file_content,
                mime_type=mime_type,
                tree_id=tree_id,
            )

            # Extract created media info
            if isinstance(result, list) and result:
                media_data = result[0].get("new", result[0])
            else:
                media_data = result

            handle = media_data.get("handle", "N/A")
            gramps_id = media_data.get("gramps_id", "N/A")
            checksum = media_data.get("checksum", "")

            response = "## Media File Uploaded Successfully\n\n"
            response += f"**File:** {file_name}\n"
            response += f"**Size:** {file_size:,} bytes\n"
            response += f"**MIME Type:** {mime_type}\n"
            response += f"**Gramps ID:** {gramps_id}\n"
            response += f"**Handle:** `{handle}`\n"
            if checksum:
                response += f"**Checksum:** {checksum}\n"

            if params.description:
                response += (
                    "\nNote: To add a description, use `create_media` "
                    f"with handle `{handle}`"
                )

            return [TextContent(type="text", text=response)]

        finally:
            await client.close()
    except Exception as e:
        format_error_response(e, "media file upload")


async def update_media_file_tool(arguments) -> List[TextContent]:
    """
    Update an existing media object's file from the local filesystem.

    Replaces the file content of an existing media object.
    The media object must already exist (use upload_media_file_tool to create new).
    """
    from ..models.parameters.media_params import MediaFileUpdateParams

    try:
        params = _validate_params(arguments, MediaFileUpdateParams)
        settings = get_settings()
        tree_id = settings.gramps_tree_id

        # Validate file exists
        if not os.path.isfile(params.file_path):
            return [
                TextContent(
                    type="text",
                    text=f"Error: File not found: {params.file_path}",
                )
            ]

        # Read file content
        with open(params.file_path, "rb") as f:
            file_content = f.read()

        # Determine MIME type
        mime_type, _ = mimetypes.guess_type(params.file_path)
        if not mime_type:
            mime_type = "application/octet-stream"

        file_size = len(file_content)
        file_name = os.path.basename(params.file_path)

        client = GrampsWebAPIClient()
        try:
            result = await client.update_media_file(
                handle=params.handle,
                file_content=file_content,
                mime_type=mime_type,
                tree_id=tree_id,
            )

            # Extract updated media info
            if isinstance(result, list) and result:
                media_data = result[0].get("new", result[0])
            else:
                media_data = result

            gramps_id = media_data.get("gramps_id", "N/A")
            checksum = media_data.get("checksum", "")

            response = "## Media File Updated Successfully\n\n"
            response += f"**File:** {file_name}\n"
            response += f"**Size:** {file_size:,} bytes\n"
            response += f"**MIME Type:** {mime_type}\n"
            response += f"**Gramps ID:** {gramps_id}\n"
            response += f"**Handle:** `{params.handle}`\n"
            if checksum:
                response += f"**New Checksum:** {checksum}\n"

            return [TextContent(type="text", text=response)]

        finally:
            await client.close()
    except Exception as e:
        format_error_response(e, "media file update")
