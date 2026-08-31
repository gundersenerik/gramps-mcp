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
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

"""
Shared plumbing for the live-tree probes.

Holds the ledger of records the probes create, so cleanup can work from
handles alone even if a probe aborts part way through.
"""

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.gramps_mcp.client import GrampsWebAPIClient
from src.gramps_mcp.models.api_calls import ApiCalls

MARKER = "ZZMCPTEST"
LEDGER = Path("probe-ledger.json")

# Ledger kind -> the call that removes it. Cleanup walks the ledger backwards,
# so children are removed before the records they point at.
DELETERS = {
    "person": ApiCalls.DELETE_PERSON,
    "family": ApiCalls.DELETE_FAMILY,
    "event": ApiCalls.DELETE_EVENT,
    "note": ApiCalls.DELETE_NOTE,
    "citation": ApiCalls.DELETE_CITATION,
    "source": ApiCalls.DELETE_SOURCE,
}
GETTERS = {
    "person": ApiCalls.GET_PERSON,
    "family": ApiCalls.GET_FAMILY,
    "event": ApiCalls.GET_EVENT,
    "note": ApiCalls.GET_NOTE,
    "citation": ApiCalls.GET_CITATION,
}

findings: List[str] = []


def record(line: str) -> None:
    """
    Add one line to the report and echo it.

    Args:
        line (str): Markdown line to record.
    """
    findings.append(line)
    print(line, flush=True)


def ledger_read() -> List[Dict[str, str]]:
    """
    Read the ledger of records this tooling created.

    Returns:
        List[Dict[str, str]]: Entries of {"kind": ..., "handle": ...}.
    """
    if not LEDGER.exists():
        return []
    return json.loads(LEDGER.read_text())


def ledger_add(kind: str, handle: str) -> None:
    """
    Append a created record to the ledger immediately.

    Args:
        kind (str): One of the keys in DELETERS.
        handle (str): The handle the API assigned.
    """
    # Reason: written before anything else happens to the record, so an abort
    # still leaves a complete list for cleanup.
    entries = ledger_read()
    entries.append({"kind": kind, "handle": handle})
    LEDGER.write_text(json.dumps(entries, indent=2))


async def create(
    client: GrampsWebAPIClient, call: ApiCalls, params: Any, kind: str, tree: str
) -> Optional[str]:
    """
    Create one record and register it in the ledger.

    Args:
        client (GrampsWebAPIClient): Live API client.
        call (ApiCalls): The POST call to make.
        params (Any): Validated parameter model.
        kind (str): Ledger kind for cleanup.
        tree (str): Tree identifier.

    Returns:
        Optional[str]: The new handle, or None when the API returned none.
    """
    result = await client.make_api_call(api_call=call, params=params, tree_id=tree)
    handle = _handle_of(result)
    if handle:
        ledger_add(kind, handle)
    return handle


def _handle_of(result: Any) -> Optional[str]:
    """
    Pull the new record's handle out of whatever shape the API returned.

    Args:
        result (Any): Decoded API response.

    Returns:
        Optional[str]: The handle if one is present.
    """
    if isinstance(result, dict):
        if "handle" in result:
            return result["handle"]
        for key in ("new", "data"):
            nested = result.get(key)
            if isinstance(nested, list) and nested:
                return _handle_of(nested[0])
            if isinstance(nested, dict):
                return _handle_of(nested)
    if isinstance(result, list) and result:
        return _handle_of(result[0])
    return None


async def fetch(
    client: GrampsWebAPIClient, kind: str, handle: str, tree: str
) -> Optional[Dict]:
    """
    Read a record back as ground truth, bypassing the formatting layer.

    Args:
        client (GrampsWebAPIClient): Live API client.
        kind (str): Ledger kind.
        handle (str): Record handle.
        tree (str): Tree identifier.

    Returns:
        Optional[Dict]: The raw record, or None when it is gone.
    """
    try:
        return await client.make_api_call(
            api_call=GETTERS[kind], tree_id=tree, handle=handle
        )
    except Exception:
        return None
