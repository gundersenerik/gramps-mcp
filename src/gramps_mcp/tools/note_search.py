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
Note search with a workaround for the notes endpoint.

The Gramps Web notes endpoint returns HTTP 500 for Gramps Query Language
filters, so note searches fetch the notes and apply the predicates here
instead. Kept apart from the other searches to hold that workaround in one
place.
"""

import logging
import re
from typing import Dict, List

from mcp.types import TextContent

from ..config import get_settings
from ..handlers.note_handler import format_note
from ..models.api_calls import ApiCalls
from ..models.parameters.note_params import NotesParams
from .common import format_error_response

logger = logging.getLogger(__name__)


# Fields on a note object that client-side note filtering understands.
# "text" maps to the StyledText string payload.
def _note_field_value(note: Dict, field: str):
    """Return the comparable value of a note field for client-side filtering."""
    if field in ("text", "text.string"):
        text = note.get("text")
        if isinstance(text, dict):
            return text.get("string", "")
        return text or ""
    return note.get(field)


def _parse_gql_predicates(gql):
    """Parse a small, safe subset of GQL into (field, op, value) predicates.

    Supported forms (joined by ``and``):
        field = "value"    field == "value"    field != "value"
        "substr" in field

    Returns a list of predicates (empty list means "match everything"), or
    ``None`` if any part of the query cannot be parsed (caller should then
    tell the user the filter is unsupported rather than return wrong results).
    """
    if not gql or not gql.strip():
        return []

    predicates = []
    for part in re.split(r"\s+and\s+", gql.strip(), flags=re.IGNORECASE):
        part = part.strip()
        eq = re.match(r'^(\w+(?:\.\w+)?)\s*(==|=|!=)\s*"([^"]*)"$', part)
        if eq:
            predicates.append((eq.group(1), eq.group(2), eq.group(3)))
            continue
        contains = re.match(
            r'^"([^"]*)"\s+in\s+(\w+(?:\.\w+)?)$', part, flags=re.IGNORECASE
        )
        if contains:
            predicates.append((contains.group(2), "contains", contains.group(1)))
            continue
        return None  # unparseable predicate
    return predicates


def _note_matches(note: Dict, predicates) -> bool:
    """Evaluate parsed predicates against a single note object."""
    for field, op, value in predicates:
        actual = _note_field_value(note, field)
        if op in ("=", "=="):
            if str(actual) != value:
                return False
        elif op == "!=":
            if str(actual) == value:
                return False
        elif op == "contains":
            if value.lower() not in str(actual or "").lower():
                return False
    return True


async def _fetch_all_notes(client, tree_id: str, cap: int = 5000) -> List[Dict]:
    """Fetch all notes WITHOUT a gql filter.

    This backend's /notes endpoint returns HTTP 500 for any ``gql`` query (a
    server-side bug in its GQL engine; other entity types are unaffected).
    Fetching without ``gql`` works, so we page through all notes and filter
    client-side. Paging is capped to avoid unbounded fetches.
    """
    notes: List[Dict] = []
    page = 1
    page_size = 200
    while len(notes) < cap:
        response = await client.make_api_call(
            api_call=ApiCalls.GET_NOTES,
            params=NotesParams(page=page, pagesize=page_size),
            tree_id=tree_id,
        )
        batch = response if isinstance(response, list) else response.get("data", [])
        if not batch:
            break
        notes.extend(batch)
        if len(batch) < page_size:
            break
        page += 1
    return notes


async def find_note_tool(client, arguments: Dict) -> List[TextContent]:
    """
    Search for notes and research notes.

    Works around a grampsweb backend bug: any ``gql`` query against the /notes
    endpoint returns HTTP 500. Instead of sending ``gql``, this fetches notes
    unfiltered and applies a supported subset of GQL client-side. See
    ``_parse_gql_predicates`` for the supported syntax.
    """
    try:
        gql = arguments.get("gql")
        pagesize = arguments.get("pagesize")

        predicates = _parse_gql_predicates(gql)
        settings = get_settings()
        tree_id = settings.gramps_tree_id

        if predicates is None:
            return [
                TextContent(
                    type="text",
                    text=(
                        f"Note search could not apply the filter {gql!r}. "
                        "This backend cannot run GQL against notes, so note "
                        "search supports a subset applied locally: "
                        'field =/==/!= "value" and "substr" in field, '
                        "combined with `and`."
                    ),
                )
            ]

        all_notes = await _fetch_all_notes(client, tree_id)
        matched = [n for n in all_notes if _note_matches(n, predicates)]
        total_count = len(matched)

        if pagesize:
            matched = matched[:pagesize]

        if not matched:
            formatted_results = "No notes found"
        else:
            if total_count > len(matched):
                header = f"Found {total_count} notes (showing {len(matched)}):\n\n"
            else:
                header = f"Found {total_count} notes:\n\n"
            formatted_results = header
            for note in matched:
                handle = note.get("handle", "")
                if handle:
                    formatted_results += await format_note(client, tree_id, handle)

        return [TextContent(type="text", text=formatted_results)]

    except Exception as e:
        format_error_response(e, "notes search")
