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
Answer the open API questions against a live tree, safely.

Only records this run creates are ever written to or deleted. No pre-existing
handle is read for writing, nothing is searched and then modified, and nothing
created here is linked to an existing record. Every created handle is appended
to a ledger so cleanup works on handles alone, and can be re-run on its own if
a probe aborts part way.

Phases, in order:

  verify-delete  create one throwaway note, read it, delete it, confirm it is
                 gone. Nothing else runs until deletion is known to work.
  probe          the experiments that MERGE-SEMANTICS.md cannot settle by
                 reading code.
  cleanup        delete everything in the ledger, newest first.
"""

import argparse
import asyncio
import json
from pathlib import Path
from typing import Any

from scripts.probe_lib import (
    DELETERS,
    LEDGER,
    MARKER,
    _handle_of,
    create,
    create_via_tool,
    fetch,
    findings,
    handle_from_tool,
    ledger_add,
    ledger_read,
    record,
)
from scripts.probe_sweep import sweep
from src.gramps_mcp.client import GrampsWebAPIClient
from src.gramps_mcp.config import get_settings
from src.gramps_mcp.models.api_calls import ApiCalls


def person_params(given: str) -> Any:
    """
    Build a marked, unlinked test person.

    Args:
        given (str): Given name, to tell the test people apart.

    Returns:
        PersonData: Parameters for a person that references nothing existing.
    """
    from src.gramps_mcp.models.parameters.people_params import PersonData

    return PersonData(
        primary_name={"first_name": given, "surname_list": [{"surname": MARKER}]},
        gender=1,
    )


async def verify_delete(client: GrampsWebAPIClient, tree: str) -> bool:
    """
    Prove deletion works before writing anything else.

    Args:
        client (GrampsWebAPIClient): Live API client.
        tree (str): Tree identifier.

    Returns:
        bool: True when the note was created, read back and then gone.
    """
    from src.gramps_mcp.models.parameters.note_params import NoteSaveParams

    record("## Phase 1: deletion")
    params = NoteSaveParams(text=f"{MARKER} delete probe", type="Research")
    handle = await create(client, ApiCalls.POST_NOTES, params, "note", tree)
    if not handle:
        record("- FAIL: the API returned no handle for the new note")
        return False
    if await fetch(client, "note", handle, tree) is None:
        record("- FAIL: the new note could not be read back")
        return False
    await client.make_api_call(
        api_call=ApiCalls.DELETE_NOTE, params=None, tree_id=tree, handle=handle
    )
    if await fetch(client, "note", handle, tree) is not None:
        record("- FAIL: the note still exists after deletion")
        return False
    LEDGER.write_text(json.dumps([e for e in ledger_read() if e["handle"] != handle]))
    record("- PASS: created, read back, deleted, and confirmed gone")
    record("- Every later record is therefore removable.")
    return True


async def probe_attributes(client: GrampsWebAPIClient, tree: str) -> None:
    """
    Point 2: is an attribute stored, and can it be read back?

    Args:
        client (GrampsWebAPIClient): Live API client.
        tree (str): Tree identifier.
    """
    from src.gramps_mcp.tools import create_person_tool
    from src.gramps_mcp.tools.search_details import get_type_tool

    record("\n## Point 2: attributes")
    params = person_params("Attribut")
    params.attribute_list = [{"type": "Occupation", "value": f"{MARKER}-A"}]
    written = await create_person_tool(params)
    handle = handle_from_tool(written)
    if handle is None:
        record("- INCONCLUSIVE: the tool reported no handle")
        return
    ledger_add("person", handle)

    raw = await fetch(client, "person", handle, tree) or {}
    stored = raw.get("attribute_list") or []
    record(f"- stored on the record: {json.dumps(stored)}")
    if not stored:
        record("- NOT stored. Writing is broken, not just reading.")
        return
    record("- stored: the write works")

    body = getattr(written[0], "text", "") if written else ""
    record(
        f"- visible in the create response: {MARKER}-A in body is "
        f"{f'{MARKER}-A' in body}"
    )

    seen = await get_type_tool({"type": "person", "handle": handle})
    seen_text = getattr(seen[0], "text", "") if seen else ""
    record(f"- visible through get_type: {f'{MARKER}-A' in seen_text}")


async def probe_children(client: GrampsWebAPIClient, tree: str) -> None:
    """
    Point 4: are child_handles actually persisted?

    Args:
        client (GrampsWebAPIClient): Live API client.
        tree (str): Tree identifier.
    """
    from src.gramps_mcp.models.parameters.family_params import FamilySaveParams
    from src.gramps_mcp.tools import create_family_tool

    record("\n## Point 4: child_handles")
    kid_a = await create(
        client, ApiCalls.POST_PEOPLE, person_params("BarnA"), "person", tree
    )
    kid_b = await create(
        client, ApiCalls.POST_PEOPLE, person_params("BarnB"), "person", tree
    )
    if not (kid_a and kid_b):
        record("- INCONCLUSIVE: could not create the two test children")
        return
    family = await create_via_tool(
        create_family_tool, FamilySaveParams(child_handles=[kid_a, kid_b]), "family"
    )
    if family is None:
        record("- INCONCLUSIVE: the tool reported no family handle")
        return
    raw = await fetch(client, "family", family, tree) or {}
    refs = raw.get("child_ref_list") or []
    got = {r.get("ref") for r in refs if isinstance(r, dict)}
    record(f"- child_ref_list on the saved family: {json.dumps(refs)}")
    if got >= {kid_a, kid_b}:
        record("- PASS: both children persisted.")
    else:
        record("- FAIL: children did not persist. Issue #24 is still live.")


async def probe_merge(client: GrampsWebAPIClient, tree: str) -> None:
    """
    Point 5: confirm the two traps read out of client.py.

    Args:
        client (GrampsWebAPIClient): Live API client.
        tree (str): Tree identifier.
    """
    from src.gramps_mcp.tools import create_person_tool

    record("\n## Point 5: merge traps")
    params = person_params("Merge")
    params.urls = [
        {"path": "https://example.invalid/one", "type": "Web Home"},
        {"path": "https://example.invalid/two", "type": "Web Home"},
    ]
    params.attribute_list = [{"type": "Occupation", "value": f"{MARKER}-M"}]
    handle = await create(client, ApiCalls.POST_PEOPLE, params, "person", tree)
    if not handle:
        record("- INCONCLUSIVE: could not create the merge test person")
        return

    update = person_params("Merge")
    update.handle = handle
    update.urls = [{"path": "https://example.invalid/one", "type": "Web Home"}]
    update.attribute_list = [{"type": "Occupation", "value": f"{MARKER}-M"}]
    await create_person_tool(update)

    raw = await fetch(client, "person", handle, tree) or {}
    urls = raw.get("urls") or []
    attrs = raw.get("attribute_list") or []
    record(f"- urls after sending 1 of 2: {len(urls)} left")
    record(
        "  - trap 1 confirmed: urls is replaced, the second URL is gone"
        if len(urls) == 1
        else "  - trap 1 NOT confirmed: urls survived, the doc needs correcting"
    )
    record(f"- attribute_list after writing the same attribute twice: {len(attrs)}")
    record(
        "  - trap 2 confirmed: attributes accumulate duplicates"
        if len(attrs) > 1
        else "  - trap 2 NOT confirmed: no duplicate, the doc needs correcting"
    )


async def probe_event_lists(client: GrampsWebAPIClient, tree: str) -> None:
    """
    Point 5 open question: what shape does the API return for citation_list?

    Args:
        client (GrampsWebAPIClient): Live API client.
        tree (str): Tree identifier.
    """
    from src.gramps_mcp.models.parameters.citation_params import CitationData
    from src.gramps_mcp.models.parameters.event_params import EventSaveParams
    from src.gramps_mcp.models.parameters.source_params import SourceSaveParams
    from src.gramps_mcp.tools import create_event_tool

    record("\n## Point 5 open question: event citation_list shape")
    src = await create(
        client,
        ApiCalls.POST_SOURCES,
        SourceSaveParams(title=f"{MARKER} source"),
        "source",
        tree,
    )
    if not src:
        record("- INCONCLUSIVE: could not create the test source")
        return
    cit = await create(
        client,
        ApiCalls.POST_CITATIONS,
        CitationData(source_handle=src),
        "citation",
        tree,
    )
    if not cit:
        record("- INCONCLUSIVE: could not create the test citation")
        return
    event = await create_via_tool(
        create_event_tool,
        EventSaveParams(
            type="Birth", description=f"{MARKER} event", citation_list=[cit]
        ),
        "event",
    )
    if event is None:
        record("- INCONCLUSIVE: the tool reported no event handle")
        return
    raw = await fetch(client, "event", event, tree) or {}
    cl = raw.get("citation_list")
    record(f"- citation_list as returned by GET: {json.dumps(cl)}")
    if cl and isinstance(cl[0], str):
        record("- Returned as bare handles. Repeated event updates WILL duplicate.")
    elif cl:
        record("- Returned as reference mappings. De-duplication works.")
    else:
        record("- Empty: the citation did not attach. Issue #38 is still live.")


async def probe_confidence(client: GrampsWebAPIClient, tree: str) -> None:
    """
    Point 6: does the API accept and store a confidence value?

    Args:
        client (GrampsWebAPIClient): Live API client.
        tree (str): Tree identifier.
    """
    from src.gramps_mcp.models.parameters.source_params import SourceSaveParams

    record("\n## Point 6: citation confidence")
    src = await create(
        client,
        ApiCalls.POST_SOURCES,
        SourceSaveParams(title=f"{MARKER} confidence source"),
        "source",
        tree,
    )
    if not src:
        record("- INCONCLUSIVE: could not create the test source")
        return
    # Reason: make_api_call validates against CitationData, which has no
    # confidence field, so the value would be dropped before it was sent.
    # Posting the body directly is the only way to learn whether the API
    # accepts it, which is what decides if adding the parameter is worth doing.
    url = client._build_url(tree, "citations/")
    try:
        result = await client._make_request(
            "POST",
            url,
            json_data={"source_handle": src, "page": MARKER, "confidence": 1},
        )
    except Exception as error:
        record(f"- The API rejected confidence: {error}")
        record("- Adding the parameter would not help until this is understood.")
        return
    handle = _handle_of(result)
    if handle:
        ledger_add("citation", handle)
        raw = await fetch(client, "citation", handle, tree) or {}
        record(f"- confidence stored as: {raw.get('confidence')!r}")


async def cleanup(client: GrampsWebAPIClient, tree: str) -> None:
    """
    Delete every record the probes created, newest first.

    Args:
        client (GrampsWebAPIClient): Live API client.
        tree (str): Tree identifier.
    """
    record("\n## Cleanup")
    entries = ledger_read()
    if not entries:
        record("- ledger empty, nothing to remove")
        return
    remaining = []
    # Reason: reverse order removes families before the people they point at,
    # and citations before their sources.
    for entry in reversed(entries):
        call = DELETERS.get(entry["kind"])
        if call is None:
            remaining.append(entry)
            continue
        try:
            await client.make_api_call(
                api_call=call, params=None, tree_id=tree, handle=entry["handle"]
            )
            record(f"- removed {entry['kind']} {entry['handle']}")
        except Exception as error:
            remaining.append(entry)
            record(f"- LEFT BEHIND {entry['kind']} {entry['handle']}: {error}")
    LEDGER.write_text(json.dumps(list(reversed(remaining)), indent=2))
    if remaining:
        record(f"- {len(remaining)} record(s) still in the ledger. Re-run cleanup.")
    else:
        record("- ledger empty; nothing of this run is left in the tree")


async def run(phase: str) -> int:
    """
    Run one phase against the configured tree.

    Args:
        phase (str): One of verify-delete, probe, cleanup, all.

    Returns:
        int: Process exit status.
    """
    settings = get_settings()
    tree = settings.gramps_tree_id
    client = GrampsWebAPIClient()
    status = 0
    try:
        record(f"# Live tree probe ({phase})")
        record(f"\nEverything created here is marked `{MARKER}`.\n")
        if phase in ("verify-delete", "all"):
            try:
                passed = await verify_delete(client, tree)
            except Exception as error:
                # Reason: the report is the artifact that gets read, so the
                # reason has to land in it rather than only in the run log.
                record(f"- FAIL: {type(error).__name__}: {error}")
                passed = False
            if not passed:
                record("\n**Stopping.** Nothing else ran.")
                record("Check the ledger artifact: if it is absent or empty,")
                record("nothing was created and there is nothing to clean up.")
                return 1
        if phase in ("probe", "all"):
            for experiment in (
                probe_attributes,
                probe_children,
                probe_merge,
                probe_event_lists,
                probe_confidence,
            ):
                try:
                    await experiment(client, tree)
                except Exception as error:
                    record(f"- ERROR in {experiment.__name__}: {error}")
                    status = 1
        if phase == "sweep":
            # Reason: a review step. Lists what carries the marker and
            # removes nothing, so the set can be checked before deleting.
            if await sweep(client, tree, delete=False) < 0:
                status = 1
        if phase in ("cleanup", "all"):
            await cleanup(client, tree)
            # Reason: the ledger only covers this run, because a workflow
            # cannot read an earlier run's artifacts. The sweep is what makes
            # cleanup work on its own, and it also catches records an earlier
            # run failed to register.
            remaining = await sweep(client, tree, delete=True)
            if remaining:
                # Negative means the tree could not be read at all, which is
                # a failure to report, not a clean result.
                status = 1
    finally:
        await client.close()
        Path("probe-report.md").write_text("\n".join(findings) + "\n")
    return status


def main() -> int:
    """
    Parse arguments and run the requested phase.

    Returns:
        int: Process exit status.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--phase",
        default="all",
        choices=["verify-delete", "probe", "sweep", "cleanup", "all"],
        help="Which phase to run (default: all)",
    )
    args = parser.parse_args()
    return asyncio.run(run(args.phase))


if __name__ == "__main__":
    raise SystemExit(main())
