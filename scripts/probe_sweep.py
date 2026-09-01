#!/usr/bin/env python3
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

"""
Find and remove every test record, without relying on a stored ledger.

The ledger only ever worked inside a single run: a workflow can read its own
artifacts but not an earlier run's. This scans the tree instead, so a cleanup
works on its own and also catches records an earlier run failed to register.

Nothing is deleted that does not carry the marker. Families are the one
exception, since a family has no text of its own to mark; one is removed only
when every person it references is a marked test person, so a family holding
even one real person is left alone.
"""

import json
from typing import Any, Dict, List, Set

from scripts.probe_lib import MARKER, record
from src.gramps_mcp.client import GrampsWebAPIClient
from src.gramps_mcp.models.api_calls import ApiCalls


class SweepIncomplete(RuntimeError):
    """Raised when a listing failed, so the tree cannot be called clean."""


# Deleted before the records they point at.
SWEEP_ORDER = [
    ("family", ApiCalls.GET_FAMILIES, ApiCalls.DELETE_FAMILY),
    ("event", ApiCalls.GET_EVENTS, ApiCalls.DELETE_EVENT),
    ("person", ApiCalls.GET_PEOPLE, ApiCalls.DELETE_PERSON),
    ("citation", ApiCalls.GET_CITATIONS, ApiCalls.DELETE_CITATION),
    ("source", ApiCalls.GET_SOURCES, ApiCalls.DELETE_SOURCE),
    ("note", ApiCalls.GET_NOTES, ApiCalls.DELETE_NOTE),
]


async def fetch_all(
    client: GrampsWebAPIClient, call: ApiCalls, tree: str
) -> List[Dict]:
    """
    Read every record of one type.

    Args:
        client (GrampsWebAPIClient): Live API client.
        call (ApiCalls): The list endpoint to read.
        tree (str): Tree identifier.

    Returns:
        List[Dict]: The records, or an empty list when the call fails.
    """
    try:
        result = await client.make_api_call(api_call=call, tree_id=tree)
    except Exception as error:
        record(f"- could not list {call.name}: {error}")
        raise SweepIncomplete(f"{call.name}: {error}") from error
    if isinstance(result, dict):
        result = result.get("data", [])
    return [r for r in result if isinstance(r, dict)]


def is_marked(item: Dict) -> bool:
    """
    Is this record one the probes created?

    Args:
        item (Dict): A record from the API.

    Returns:
        bool: True when the marker appears anywhere in it.
    """
    return MARKER in json.dumps(item)


def family_is_ours(family: Dict, marked_people: Set[str]) -> bool:
    """
    Decide whether a family belongs to the probes.

    Args:
        family (Dict): The family record.
        marked_people (Set[str]): Handles of the marked test people.

    Returns:
        bool: True only when the family references people and every one of
            them is a marked test person.
    """
    # Reason: a family carries no name of its own, so the marker cannot appear
    # in it. Membership is the only evidence. Requiring *every* member to be
    # marked means a family holding one real person is never touched.
    referenced = set()
    for key in ("father_handle", "mother_handle"):
        if family.get(key):
            referenced.add(family[key])
    for ref in family.get("child_ref_list") or []:
        if isinstance(ref, dict) and ref.get("ref"):
            referenced.add(ref["ref"])
    return bool(referenced) and referenced <= marked_people


async def sweep(client: GrampsWebAPIClient, tree: str, delete: bool) -> int:
    """
    Report, and optionally remove, every test record in the tree.

    Args:
        client (GrampsWebAPIClient): Live API client.
        tree (str): Tree identifier.
        delete (bool): Remove what is found, rather than only listing it.

    Returns:
        int: Count of records still present after the pass.
    """
    record(f"\n## Sweep for `{MARKER}`")
    # Reason: a listing that failed is not an empty listing. Reporting "clean"
    # after an unreadable tree would be exactly the silent loss this whole
    # exercise exists to prevent, so the failure is surfaced instead.
    try:
        people = await fetch_all(client, ApiCalls.GET_PEOPLE, tree)
    except SweepIncomplete as error:
        record(f"- INCOMPLETE: could not read the tree ({error})")
        record("- nothing was removed, and nothing can be concluded")
        return -1
    marked_people = {p["handle"] for p in people if is_marked(p) and p.get("handle")}

    targets: List[Dict[str, Any]] = []
    try:
        listings = {
            kind: (
                people if kind == "person" else await fetch_all(client, list_call, tree)
            )
            for kind, list_call, _ in SWEEP_ORDER
        }
    except SweepIncomplete as error:
        record(f"- INCOMPLETE: could not read the tree ({error})")
        record("- nothing was removed, and nothing can be concluded")
        return -1

    for kind, _list_call, delete_call in SWEEP_ORDER:
        items = listings[kind]
        for item in items:
            handle = item.get("handle")
            if not handle:
                continue
            ours = (
                family_is_ours(item, marked_people)
                if kind == "family"
                else is_marked(item)
            )
            if ours:
                targets.append(
                    {
                        "kind": kind,
                        "handle": handle,
                        "gramps_id": item.get("gramps_id", "?"),
                        "call": delete_call,
                    }
                )

    if not targets:
        record("- nothing found; the tree is clean")
        return 0

    record(f"- found {len(targets)} record(s):")
    for target in targets:
        record(f"  - {target['kind']} {target['gramps_id']} `{target['handle']}`")

    if not delete:
        record("- listing only; nothing was removed")
        return len(targets)

    left = 0
    for target in targets:
        try:
            await client.make_api_call(
                api_call=target["call"],
                params=None,
                tree_id=tree,
                handle=target["handle"],
            )
            record(f"- removed {target['kind']} {target['gramps_id']}")
        except Exception as error:
            left += 1
            record(f"- LEFT BEHIND {target['kind']} {target['gramps_id']}: {error}")
    record("- tree is clean" if not left else f"- {left} record(s) remain; re-run")
    return left
