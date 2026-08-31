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
Tool registry for the Gramps MCP server.

Single source of truth mapping each tool name to its description, its
Pydantic argument schema and the handler that implements it. The server
imports this to publish tools over both the HTTP and stdio transports.
"""

from typing import Any, Dict, Optional

from pydantic import BaseModel, Field

# Import all parameter models
from .models.parameters.citation_params import CitationData
from .models.parameters.delete_params import DeleteParams
from .models.parameters.event_params import EventSaveParams, EventSpanParams
from .models.parameters.facts_params import FactsParams
from .models.parameters.family_params import FamilySaveParams
from .models.parameters.living_params import LivingParams
from .models.parameters.media_params import (
    MediaFileUpdateParams,
    MediaFileUploadParams,
    MediaSaveParams,
)
from .models.parameters.note_params import NoteSaveParams
from .models.parameters.people_params import PersonData
from .models.parameters.place_params import PlaceSaveParams
from .models.parameters.relations_params import RelationParams
from .models.parameters.repository_params import RepositoryData
from .models.parameters.simple_params import (
    EmptyParams,
    SimpleFindParams,
    SimpleGetParams,
    SimpleSearchParams,
)
from .models.parameters.source_params import SourceSaveParams
from .models.parameters.tag_params import TagSaveParams, TagSearchParams
from .models.parameters.timeline_params import (
    FamiliesTimelineParams,
    PeopleTimelineParams,
)
from .models.parameters.transactions_params import TransactionHistoryParams

# Import all tool functions
from .tools import (
    create_citation_tool,
    create_event_tool,
    create_family_tool,
    create_media_tool,
    create_note_tool,
    create_person_tool,
    create_place_tool,
    create_repository_tool,
    create_source_tool,
    create_tag_tool,
    delete_citation_tool,
    delete_event_tool,
    delete_family_tool,
    delete_media_tool,
    delete_note_tool,
    delete_person_tool,
    delete_place_tool,
    delete_repository_tool,
    delete_source_tool,
    delete_tag_tool,
    find_anything_tool,
    find_tags_tool,
    get_ancestors_tool,
    get_descendants_tool,
    get_event_span_tool,
    get_facts_tool,
    get_families_timeline_tool,
    get_living_tool,
    get_media_file_tool,
    get_people_timeline_tool,
    get_recent_changes_tool,
    get_relations_all_tool,
    get_relations_tool,
    get_tree_info_tool,
    get_types_tool,
    update_media_file_tool,
    upload_media_file_tool,
)
from .tools.search_basic import find_type_tool
from .tools.search_details import get_type_tool

# Simple analysis models for tools that use direct dict access


# Simple analysis models for tools that use direct dict access
class TreeInfoParams(BaseModel):
    include_statistics: bool = Field(True, description="Include statistics")


class DescendantsParams(BaseModel):
    gramps_id: str = Field(..., description="Person ID")
    max_generations: Optional[int] = Field(
        5,
        description=(
            "Max generations to retrieve (default: 5, use higher values "
            "carefully as they can overflow context)"
        ),
    )


class AncestorsParams(BaseModel):
    gramps_id: str = Field(..., description="Person ID")
    max_generations: Optional[int] = Field(
        5,
        description=(
            "Max generations to retrieve (default: 5, use higher values "
            "carefully as they can overflow context)"
        ),
    )


# Tool registry - single source of truth for all tools

TOOL_REGISTRY: Dict[str, Dict[str, Any]] = {
    # Search & Retrieval Tools
    "find_type": {
        "description": (
            "Search any entity type using GQL - read gql://documentation "
            "resource first to understand syntax"
        ),
        "schema": SimpleFindParams,
        "handler": find_type_tool,
    },
    "find_anything": {
        "description": (
            "Text search across all record types - matches literal text "
            "within records, not logical combinations"
        ),
        "schema": SimpleSearchParams,
        "handler": find_anything_tool,
    },
    "get_type": {
        "description": "Get full details for person or family by handle or gramps_id",
        "schema": SimpleGetParams,
        "handler": get_type_tool,
    },
    # Data Management Tools
    "create_person": {
        "description": (
            "Create or update person information including family links "
            "and event associations"
        ),
        "schema": PersonData,
        "handler": create_person_tool,
    },
    "create_family": {
        "description": "Create or update family unit including member relationships",
        "schema": FamilySaveParams,
        "handler": create_family_tool,
    },
    "create_event": {
        "description": (
            "Create or update life event including person/place associations"
        ),
        "schema": EventSaveParams,
        "handler": create_event_tool,
    },
    "create_place": {
        "description": "Create or update geographic location",
        "schema": PlaceSaveParams,
        "handler": create_place_tool,
    },
    "create_source": {
        "description": "Create or update source document",
        "schema": SourceSaveParams,
        "handler": create_source_tool,
    },
    "create_citation": {
        "description": "Create or update citation including object associations",
        "schema": CitationData,
        "handler": create_citation_tool,
    },
    "create_note": {
        "description": "Create or update textual note including object associations",
        "schema": NoteSaveParams,
        "handler": create_note_tool,
    },
    "create_media": {
        "description": "Create or update media files including object associations",
        "schema": MediaSaveParams,
        "handler": create_media_tool,
    },
    "create_repository": {
        "description": "Create or update repository information",
        "schema": RepositoryData,
        "handler": create_repository_tool,
    },
    # Delete Tools
    "delete_person": {
        "description": "Delete a person by handle",
        "schema": DeleteParams,
        "handler": delete_person_tool,
    },
    "delete_family": {
        "description": "Delete a family by handle",
        "schema": DeleteParams,
        "handler": delete_family_tool,
    },
    "delete_event": {
        "description": "Delete an event by handle",
        "schema": DeleteParams,
        "handler": delete_event_tool,
    },
    "delete_note": {
        "description": "Delete a note by handle",
        "schema": DeleteParams,
        "handler": delete_note_tool,
    },
    "delete_citation": {
        "description": "Delete a citation by handle",
        "schema": DeleteParams,
        "handler": delete_citation_tool,
    },
    "delete_source": {
        "description": "Delete a source by handle",
        "schema": DeleteParams,
        "handler": delete_source_tool,
    },
    "delete_place": {
        "description": "Delete a place by handle",
        "schema": DeleteParams,
        "handler": delete_place_tool,
    },
    "delete_repository": {
        "description": "Delete a repository by handle",
        "schema": DeleteParams,
        "handler": delete_repository_tool,
    },
    "delete_media": {
        "description": "Delete a media item by handle",
        "schema": DeleteParams,
        "handler": delete_media_tool,
    },
    # Analysis Tools
    "tree_stats": {
        "description": (
            "Get information about a specific tree including statistics "
            "(counts of people, families, events, etc.)"
        ),
        "schema": TreeInfoParams,
        "handler": get_tree_info_tool,
    },
    "get_descendants": {
        "description": (
            "Find all descendants of a person - WARNING: Very token-heavy "
            "operation, minimize generations (default: 5)"
        ),
        "schema": DescendantsParams,
        "handler": get_descendants_tool,
    },
    "get_ancestors": {
        "description": (
            "Find all ancestors of a person - WARNING: Very token-heavy "
            "operation, minimize generations (default: 5)"
        ),
        "schema": AncestorsParams,
        "handler": get_ancestors_tool,
    },
    "recent_changes": {
        "description": "Get recent changes/modifications to the family tree",
        "schema": TransactionHistoryParams,
        "handler": get_recent_changes_tool,
    },
    "get_relations": {
        "description": (
            "Find the relationship between two people (e.g., cousins, uncle/nephew)"
        ),
        "schema": RelationParams,
        "handler": get_relations_tool,
    },
    "get_relations_all": {
        "description": "Find ALL possible relationship paths between two people",
        "schema": RelationParams,
        "handler": get_relations_all_tool,
    },
    # Living & Facts Tools
    "get_living": {
        "description": "Check if a person is considered living (for privacy purposes)",
        "schema": LivingParams,
        "handler": get_living_tool,
    },
    "get_facts": {
        "description": "Get computed facts and statistics about the family tree",
        "schema": FactsParams,
        "handler": get_facts_tool,
    },
    # Tag Tools
    "find_tags": {
        "description": "Find/list all tags in the database",
        "schema": TagSearchParams,
        "handler": find_tags_tool,
    },
    "create_tag": {
        "description": "Create or update a tag for organizing records",
        "schema": TagSaveParams,
        "handler": create_tag_tool,
    },
    "delete_tag": {
        "description": "Delete a tag by handle",
        "schema": DeleteParams,
        "handler": delete_tag_tool,
    },
    # Timeline Tools
    "get_people_timeline": {
        "description": "Get a timeline of events for a group of people",
        "schema": PeopleTimelineParams,
        "handler": get_people_timeline_tool,
    },
    "get_families_timeline": {
        "description": "Get a timeline of events for a group of families",
        "schema": FamiliesTimelineParams,
        "handler": get_families_timeline_tool,
    },
    # Media File Tools
    "get_media_file": {
        "description": "Get information about a media file (metadata and download URL)",
        "schema": DeleteParams,
        "handler": get_media_file_tool,
    },
    "upload_media_file": {
        "description": (
            "Upload a new media file from the local filesystem - "
            "creates a new media object with the file content"
        ),
        "schema": MediaFileUploadParams,
        "handler": upload_media_file_tool,
    },
    "update_media_file": {
        "description": (
            "Update an existing media object's file from the local filesystem - "
            "replaces the file content for an existing media object"
        ),
        "schema": MediaFileUpdateParams,
        "handler": update_media_file_tool,
    },
    # Event & Type Tools
    "get_event_span": {
        "description": (
            "Calculate time span between two events - useful for "
            "'how old was X when Y happened' queries"
        ),
        "schema": EventSpanParams,
        "handler": get_event_span_tool,
    },
    "get_types": {
        "description": (
            "Get all valid type values (event types, name types, place types, etc.) - "
            "reference for creating records"
        ),
        "schema": EmptyParams,
        "handler": get_types_tool,
    },
}
