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
Shared helpers for the analysis tool modules.
"""

import asyncio
import logging
from typing import Dict, List

from ..client import GrampsAPIError, GrampsWebAPIClient
from ..utils import get_gramps_id_from_handle

logger = logging.getLogger(__name__)


def _get_arg(arguments, key, default=None):
    """Get argument value from either dict or BaseModel."""
    from pydantic import BaseModel

    if isinstance(arguments, BaseModel):
        return getattr(arguments, key, default)
    return arguments.get(key, default)


async def _format_recent_changes(
    transactions: List[Dict], client: GrampsWebAPIClient, tree_id: str
) -> str:
    """Format transaction history results."""
    if not transactions:
        return "No recent changes found."

    result = f"Found {len(transactions)} recent changes:\n\n"

    for transaction in transactions:
        # Extract transaction information
        timestamp = transaction.get("timestamp", "Unknown time")
        description = transaction.get("description", "Transaction")

        # Convert timestamp to human readable format
        if isinstance(timestamp, (int, float)):
            from datetime import datetime

            formatted_time = datetime.fromtimestamp(timestamp).strftime(
                "%Y-%m-%d %H:%M:%S"
            )
        else:
            formatted_time = str(timestamp)

        # User information
        connection = transaction.get("connection", {})
        user = connection.get("user", {})
        user_name = user.get("name", "Unknown") if user else "Unknown"

        # Changes in this transaction
        changes = transaction.get("changes", [])
        change_count = len(changes)

        result += f"• **{description}**\n"
        result += f"  Time: {formatted_time}\n"
        result += f"  User: {user_name}\n"

        if changes:
            result += "  Objects changed:\n"
            for change in changes[:3]:  # Show first 3 changes
                obj_class = change.get("obj_class", "Unknown")
                obj_handle = change.get("obj_handle", "N/A")

                # Get gramps_id from handle using utility function
                gramps_id = await get_gramps_id_from_handle(
                    client, obj_class, obj_handle, tree_id
                )
                result += f"    - {obj_class}: {gramps_id}\n"
            if len(changes) > 3:
                result += f"    - ... and {len(changes) - 3} more\n"
        else:
            result += f"  Changes: {change_count} objects modified\n"

        result += "\n"

    return result


async def _wait_for_task_completion(
    client: GrampsWebAPIClient, task_id: str, tree_id: str, timeout: int = 60
) -> Dict:
    """
    Wait for an async task to complete by polling its status.

    Args:
        client: Gramps API client
        task_id: Task ID to poll
        tree_id: Tree ID (unused for tasks, but kept for compatibility)
        timeout: Maximum wait time in seconds

    Returns:
        Dict: Completed task result containing filename

    Raises:
        GrampsAPIError: If task fails or times out
    """
    start_time = asyncio.get_event_loop().time()
    sleep_interval = 2  # Start with 2 second intervals
    max_sleep = 10  # Maximum sleep interval

    while True:
        elapsed = asyncio.get_event_loop().time() - start_time
        if elapsed > timeout:
            raise GrampsAPIError(f"Task {task_id} timed out after {timeout} seconds")

        try:
            # Poll task status using direct HTTP call
            # (tasks are global, not tree-specific)
            task_url = f"{client.base_url}/tasks/{task_id}"
            task_status = await client._make_request("GET", task_url)

            logger.debug(f"Task {task_id} status: {task_status}")

            # Check if task is complete (use 'state' field, not 'status')
            state = task_status.get("state", "").upper()
            if state == "SUCCESS":
                # Task completed successfully, return the result_object
                result = task_status.get("result_object") or task_status.get("result")
                if result:
                    return result
                else:
                    logger.warning(
                        f"Task {task_id} succeeded but no result found: {task_status}"
                    )
                    return task_status
            elif state == "FAILURE" or state == "FAILED":
                error_msg = task_status.get("info", "Task failed")
                raise GrampsAPIError(f"Task {task_id} failed: {error_msg}")

            # Task still running, wait before checking again
            logger.debug(
                f"Task {task_id} still running (state: {state}), "
                f"waiting {sleep_interval}s..."
            )
            await asyncio.sleep(sleep_interval)

            # Exponential backoff, but cap at max_sleep
            sleep_interval = min(sleep_interval * 1.5, max_sleep)

        except Exception as e:
            if isinstance(e, GrampsAPIError):
                raise
            raise GrampsAPIError(f"Error polling task {task_id}: {str(e)}")
