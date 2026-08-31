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
Timeline, event span and type-vocabulary MCP tools.
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


# ============================================================================
# Timeline Tools
# ============================================================================


@with_client
async def get_people_timeline_tool(client, arguments) -> List[TextContent]:
    """
    Get a timeline of events for a group of people.
    """
    try:
        from ..models.parameters.timeline_params import PeopleTimelineParams

        # Extract only explicitly provided arguments (not defaults)
        # to avoid sending extra params the API rejects
        if isinstance(arguments, PeopleTimelineParams):
            params_dict = arguments.model_dump(exclude_unset=True)
        elif isinstance(arguments, dict):
            params_dict = {k: v for k, v in arguments.items() if v is not None}
        else:
            params_dict = {}

        # Only create params if there are explicit values to send
        params = PeopleTimelineParams(**params_dict) if params_dict else None

        settings = get_settings()
        tree_id = settings.gramps_tree_id

        # Get timeline
        timeline = await client.make_api_call(
            api_call=ApiCalls.GET_TIMELINES_PEOPLE,
            params=params,
            tree_id=tree_id,
        )

        if not timeline:
            return [TextContent(type="text", text="No timeline events found.")]

        # Format timeline
        result = "# People Timeline\n\n"

        events = timeline if isinstance(timeline, list) else timeline.get("data", [])
        for event in events[:50]:  # Limit output
            # Date can be a string or dict depending on API version
            date = event.get("date", "Unknown date")
            if isinstance(date, dict):
                date_str = date.get("sortval", date.get("text", "Unknown date"))
            else:
                date_str = str(date) if date else "Unknown date"

            event_type = event.get("type", event.get("label", "Event"))
            description = event.get("description", "")
            age = event.get("age", "")

            # Person info - the person field is a dict with name_display, etc.
            person = event.get("person", {})
            if isinstance(person, dict):
                person_name = person.get("name_display", person.get("name", ""))
            else:
                person_name = ""

            result += f"- **{date_str}** - {event_type}"
            if description:
                result += f": {description}"
            if person_name:
                result += f" ({person_name})"
            if age:
                result += f" [age: {age}]"
            result += "\n"

        return [TextContent(type="text", text=result)]

    except Exception as e:
        format_error_response(e, "people timeline retrieval")


@with_client
async def get_families_timeline_tool(client, arguments) -> List[TextContent]:
    """
    Get a timeline of events for a group of families.
    """
    try:
        from ..models.parameters.timeline_params import FamiliesTimelineParams

        # Extract only explicitly provided arguments (not defaults)
        # to avoid sending extra params the API rejects
        if isinstance(arguments, FamiliesTimelineParams):
            params_dict = arguments.model_dump(exclude_unset=True)
        elif isinstance(arguments, dict):
            params_dict = {k: v for k, v in arguments.items() if v is not None}
        else:
            params_dict = {}

        # Only create params if there are explicit values to send
        params = FamiliesTimelineParams(**params_dict) if params_dict else None

        settings = get_settings()
        tree_id = settings.gramps_tree_id

        # Get timeline
        timeline = await client.make_api_call(
            api_call=ApiCalls.GET_TIMELINES_FAMILIES,
            params=params,
            tree_id=tree_id,
        )

        if not timeline:
            return [TextContent(type="text", text="No family timeline events found.")]

        # Format timeline
        result = "# Families Timeline\n\n"

        events = timeline if isinstance(timeline, list) else timeline.get("data", [])
        for event in events[:50]:  # Limit output
            # Date can be a string or dict depending on API version
            date = event.get("date", "Unknown date")
            if isinstance(date, dict):
                date_str = date.get("sortval", date.get("text", "Unknown date"))
            else:
                date_str = str(date) if date else "Unknown date"

            event_type = event.get("type", event.get("label", "Event"))
            description = event.get("description", "")
            age = event.get("age", "")

            # Person info if available
            person = event.get("person", {})
            if isinstance(person, dict):
                person_name = person.get("name_display", person.get("name", ""))
            else:
                person_name = ""

            result += f"- **{date_str}** - {event_type}"
            if description:
                result += f": {description}"
            if person_name:
                result += f" ({person_name})"
            if age:
                result += f" [age: {age}]"
            result += "\n"

        return [TextContent(type="text", text=result)]

    except Exception as e:
        format_error_response(e, "families timeline retrieval")


# ============================================================================
# Event Span Tool
# ============================================================================


@with_client
async def get_event_span_tool(client, arguments) -> List[TextContent]:
    """
    Calculate the time span between two events.

    Useful for questions like "How old was X when Y happened?" or
    "How long between marriage and first child?"
    """
    try:
        handle1 = _get_arg(arguments, "handle1")
        handle2 = _get_arg(arguments, "handle2")
        precision = _get_arg(arguments, "precision", 2)
        as_age = _get_arg(arguments, "as_age", True)

        if not handle1 or not handle2:
            raise ValueError("Both handle1 and handle2 are required")

        settings = get_settings()
        tree_id = settings.gramps_tree_id

        # Build query params - only include if explicitly set to non-default values
        params = {}
        if precision is not None and precision != 2:
            params["precision"] = precision
        if as_age is not None and not as_age:
            params["as_age"] = as_age

        # Get event span
        result = await client.make_api_call(
            api_call=ApiCalls.GET_EVENT_SPAN,
            params=params if params else None,
            tree_id=tree_id,
            handle1=handle1,
            handle2=handle2,
        )

        span = result.get("span", "unknown") if isinstance(result, dict) else "unknown"

        response = "## Time Span Between Events\n\n"
        response += f"**Event 1:** `{handle1}`\n"
        response += f"**Event 2:** `{handle2}`\n"
        response += f"**Span:** {span}\n"

        if span == "unknown":
            response += (
                "\n*Note: Span could not be calculated. This usually means "
                "one or both events don't have complete dates.*"
            )

        return [TextContent(type="text", text=response)]

    except Exception as e:
        format_error_response(e, "event span calculation")


# ============================================================================
# Types Reference Tool
# ============================================================================


@with_client
async def get_types_tool(client, arguments) -> List[TextContent]:
    """
    Get all valid type values for Gramps records.

    Returns valid values for event types, name types, place types,
    note types, and more. Useful as a reference when creating records.
    """
    try:
        settings = get_settings()
        tree_id = settings.gramps_tree_id

        # Get default types
        result = await client.make_api_call(
            api_call=ApiCalls.GET_TYPES_DEFAULT,
            params=None,
            tree_id=tree_id,
        )

        if not result:
            return [TextContent(type="text", text="No type information available.")]

        response = "# Gramps Type Reference\n\n"
        response += "Valid values for each record type:\n\n"

        # Format each type category
        type_categories = [
            ("event_types", "Event Types"),
            ("name_types", "Name Types"),
            ("place_types", "Place Types"),
            ("note_types", "Note Types"),
            ("family_relation_types", "Family Relation Types"),
            ("gender_types", "Gender Types"),
            ("repository_types", "Repository Types"),
            ("source_media_types", "Source Media Types"),
            ("name_origin_types", "Name Origin Types"),
            ("event_role_types", "Event Role Types"),
            ("child_reference_types", "Child Reference Types"),
            ("attribute_types", "Attribute Types"),
            ("url_types", "URL Types"),
        ]

        for key, label in type_categories:
            if key in result:
                values = result[key]
                response += f"## {label}\n"
                # Format as comma-separated list, max 8 per line
                for i in range(0, len(values), 8):
                    chunk = values[i : i + 8]
                    response += ", ".join(chunk) + "\n"
                response += "\n"

        return [TextContent(type="text", text=response)]

    except Exception as e:
        format_error_response(e, "types retrieval")
